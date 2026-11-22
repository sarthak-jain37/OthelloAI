"""
Genetic algorithm for tuning the heuristic weights (H1, H2, H3).

Run from the repository root:
    python -m tuning.tune --heuristic H2         full run (20 x 20 x 40, depth 4)
    python -m tuning.tune --heuristic H2 --resume    continue after a stop or crash
    python -m tuning.tune --heuristic H2 --quick     tiny run to check everything works

Design (see the project's GA design doc):
  * Genome: one gene per tunable weight. One weight per heuristic is fixed to
    set the scale (minimax only compares scores, so scaling every weight by
    the same factor plays identically): H1 corner square = 100, H2 corner =
    30, H3 opening corner = 30. Free genes: H1 5, H2 6, H3 15.
  * Fitness: score (wins + 0.5 draws) over 40 games per generation:
    20 vs the anchor (literature weights) and 20 vs the champion (best of the
    previous generation; the anchor in generation 0), each opening played
    with both colours. Every individual gets the same openings within a
    generation; new openings each generation; the whole population, elites
    included, is re-evaluated every generation.
  * Evolution: elitism 2, tournament of 3, blend crossover (BLX-0.3) with
    probability 0.7, per-gene mutation probability 0.25 with sigma shrinking
    from 10% to 3% of the gene's range, all clipped to bounds.
  * Final: playoff of the last generation's top 4 plus the last 3 champions,
    200 games each vs the anchor; the winner is saved as the tuned weights.

Search: MinimaxAI from minimax.py, alpha-beta + move ordering, fixed depth,
no time limit, i.e. exactly what the experiments use.

Outputs (in tuning/results/<heuristic>/):
  generations.csv    one row per generation (for convergence plots)
  individuals.csv    every individual of every generation
  checkpoint.json    saved after every generation (used by --resume)
  tuned_weights.json final weights, playoff table, settings, run time
Openings are generated once into tuning/results/openings.json: a tuning pool and a
separate held-out set (for validation and the final experiments).
"""
import argparse
import csv
import json
import multiprocessing as mp
import os
import platform
import random
import statistics
import sys
import time

# core must be imported before algorithms (see the explanation doc, "Import order")
from core.board import Board, valid_moves_grid, apply_move_grid
from core.player import Player
from algorithms.minimax import MinimaxAI
import algorithms.heuristics as H

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

INF_TIME = 1e9
TERMINAL_OFFSET = 100000


# --------------------------------------------------------------------------
# Genes: (name, start, low, high). Fixed weights are not genes.
# --------------------------------------------------------------------------

def _rule(name, start):
    """H2/H3 bounds: 0 .. max(3 x start, 60)."""
    return (name, start, 0.0, float(max(3 * start, 60)))


def gene_spec(hname):
    if hname == "H1":
        return [("x", -50, -100.0, 0.0),
                ("c", -20, -100.0, 0.0),
                ("edge_base", 5, -10.0, 20.0),
                ("interior_base", -1, -10.0, 10.0),
                ("disc", 1.0, 0.0, 10.0)], {}
    if hname == "H2":
        d = H.H2.DEFAULTS
        return [_rule(k, d[k]) for k in d if k != "corner"], {"corner": d["corner"]}
    if hname == "H3":
        d = H.H3.DEFAULTS
        return [_rule(k, d[k]) for k in d if k != "corner_o"], {"corner_o": d["corner_o"]}
    raise ValueError(f"unknown heuristic {hname}")


def to_weights(hname, genome):
    spec, fixed = gene_spec(hname)
    w = dict(fixed)
    w.update({name: value for (name, *_), value in zip(spec, genome)})
    return w


def max_possible_score(hname, weights):
    """Upper bound on |heuristic| for a weight set (must stay below 100000)."""
    if hname == "H1":
        t = H.build_table(weights["x"], weights["c"], weights["edge_base"], weights["interior_base"])
        return sum(abs(v) for row in t for v in row) + 100 * abs(weights["disc"])

    def phase_bound(w):
        # corner and X/C features are mutually exclusive per corner
        other = sum(abs(v) for k, v in w.items() if k not in ("corner", "x", "c"))
        return 100 * (max(abs(w["corner"]), abs(w["x"]) + abs(w["c"])) + other)

    if hname == "H2":
        return phase_bound(weights)
    feats = H.H3_FEATURES
    return max(phase_bound({f: weights[f + s] for f in feats}) for s in ("_o", "_e"))


# --------------------------------------------------------------------------
# Openings
# --------------------------------------------------------------------------

def generate_openings(path, seed, plies, n_tune, n_heldout):
    rng = random.Random(f"openings-{seed}")
    seen, openings = set(), []
    attempts = 0
    while len(openings) < n_tune + n_heldout:
        attempts += 1
        if attempts > 200000:
            raise RuntimeError("could not generate enough distinct openings")
        grid, cur, moves = Board().board, 1, []
        while len(moves) < plies:
            legal = valid_moves_grid(grid, cur)
            if not legal:
                break
            m = rng.choice(legal)
            moves.append(list(m))
            grid = apply_move_grid(grid, cur, *m)
            cur = -cur
        if len(moves) < plies:
            continue
        key = (tuple(map(tuple, grid)), cur)
        if key in seen:
            continue
        seen.add(key)
        openings.append(moves)
    data = {"seed": seed, "plies": plies,
            "tuning": openings[:n_tune], "heldout": openings[n_tune:],
            "note": "Moves from the standard start, Black first, (row, col). "
                    "Held-out positions are disjoint from tuning positions."}
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def load_openings(path, args):
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        if data["plies"] != args.plies or data["seed"] != args.seed:
            raise SystemExit(f"{path} was made with different --plies/--seed; delete it or match them")
        return data
    return generate_openings(path, args.seed, args.plies, args.n_tune, args.n_heldout)


# --------------------------------------------------------------------------
# One game (runs in a worker process)
# --------------------------------------------------------------------------

def play_game(task):
    """task = (key, hname, weights_a, weights_b, opening_moves, a_is_black, depth)
    Returns (key, score for A (1 / 0.5 / 0), disc margin for A)."""
    key, hname, wa, wb, opening, a_is_black, depth = task
    cls = H.HEURISTICS[hname]
    ai_a = MinimaxAI(depth=depth, search_mode="fixed", time_limit=INF_TIME, heuristic=cls(wa))
    ai_b = MinimaxAI(depth=depth, search_mode="fixed", time_limit=INF_TIME, heuristic=cls(wb))
    a_colour = 1 if a_is_black else -1
    b = Board()
    cur = 1
    for (r, c) in opening:
        b.make_move(Player(cur), r, c)
        cur = -cur
    while True:
        p = Player(cur)
        ai = ai_a if cur == a_colour else ai_b
        move = ai.find_best_move(b, p)
        if move is None:
            if not b.get_valid_moves(Player(-cur)):
                break
            cur = -cur
            continue
        b.make_move(p, *move)
        cur = -cur
    margin = b.count_tokens(Player(a_colour)) - b.count_tokens(Player(-a_colour))
    score = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
    return key, score, margin


def run_games(pool, tasks):
    """Run tasks in parallel; returns {key: (score, margin)} averaged per key."""
    acc = {}
    for key, score, margin in pool.imap_unordered(play_game, tasks, chunksize=1):
        s = acc.setdefault(key, [0.0, 0.0, 0])
        s[0] += score
        s[1] += margin
        s[2] += 1
    return {k: (v[0] / v[2], v[1] / v[2], v[2]) for k, v in acc.items()}


# --------------------------------------------------------------------------
# Genetic operators
# --------------------------------------------------------------------------

def clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def initial_population(spec, size, rng):
    anchor = [g[1] for g in spec]
    pop = [list(anchor)]
    while len(pop) < size:
        pop.append([clip(s + rng.gauss(0, 0.15 * (hi - lo)), lo, hi) for (_, s, lo, hi) in spec])
    return pop


def tournament(pop, fitness, rng, k=3):
    idx = rng.sample(range(len(pop)), k)
    return pop[max(idx, key=lambda i: fitness[i])]


def blend_crossover(a, b, spec, rng, alpha=0.3):
    child = []
    for x, y, (_, _, lo, hi) in zip(a, b, spec):
        low, high = min(x, y), max(x, y)
        span = high - low
        child.append(clip(rng.uniform(low - alpha * span, high + alpha * span), lo, hi))
    return child


def mutate(genome, spec, rng, sigma_frac, p=0.25):
    return [clip(v + rng.gauss(0, sigma_frac * (hi - lo)), lo, hi) if rng.random() < p else v
            for v, (_, _, lo, hi) in zip(genome, spec)]


def next_generation(pop, fitness, spec, rng, gen, total_gens, elites, cx_prob):
    order = sorted(range(len(pop)), key=lambda i: -fitness[i])
    new = [list(pop[i]) for i in order[:elites]]
    progress = gen / max(1, total_gens - 1)
    sigma = 0.10 + (0.03 - 0.10) * progress
    while len(new) < len(pop):
        p1 = tournament(pop, fitness, rng)
        if rng.random() < cx_prob:
            p2 = tournament(pop, fitness, rng)
            child = blend_crossover(p1, p2, spec, rng)
        else:
            child = list(p1)
        new.append(mutate(child, spec, rng, sigma))
    return new


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------

def fmt_genome(spec, genome):
    return {name: round(v, 3) for (name, *_), v in zip(spec, genome)}


def evaluate_generation(pool, args, hname, pop, champion, openings, rng):
    """Fitness for every individual: games vs anchor and vs champion."""
    anchor_w = to_weights(hname, [g[1] for g in gene_spec(hname)[0]])
    champ_w = to_weights(hname, champion)
    per_side = args.games // 4                      # openings per opponent (x2 colours)
    chosen = rng.sample(range(len(openings)), 2 * per_side)
    ops_anchor, ops_champ = chosen[:per_side], chosen[per_side:]
    tasks = []
    for i, genome in enumerate(pop):
        w = to_weights(hname, genome)
        for opp, opp_w, ops in (("anchor", anchor_w, ops_anchor), ("champion", champ_w, ops_champ)):
            for o in ops:
                for a_black in (True, False):
                    tasks.append(((i, opp), hname, w, opp_w, openings[o], a_black, args.depth))
    res = run_games(pool, tasks)
    rows = []
    for i in range(len(pop)):
        sa, ma, na = res[(i, "anchor")]
        sc, mc, nc = res[(i, "champion")]
        fit = (sa * na + sc * nc) / (na + nc)
        rows.append({"fitness": fit, "vs_anchor": sa, "vs_champion": sc,
                     "margin": (ma * na + mc * nc) / (na + nc), "games": na + nc})
    return rows, chosen


def playoff(pool, args, hname, candidates, openings, rng, log):
    anchor_w = to_weights(hname, [g[1] for g in gene_spec(hname)[0]])
    n_ops = args.playoff_games // 2
    ops = rng.sample(range(len(openings)), min(n_ops, len(openings)))
    tasks = []
    for i, (label, genome) in enumerate(candidates):
        w = to_weights(hname, genome)
        for o in ops:
            for a_black in (True, False):
                tasks.append(((i,), hname, w, anchor_w, openings[o], a_black, args.depth))
    res = run_games(pool, tasks)
    table = []
    for i, (label, genome) in enumerate(candidates):
        s, m, n = res[(i,)]
        table.append({"candidate": label, "score_vs_anchor": s, "mean_margin": m, "games": n,
                      "weights": to_weights(hname, genome)})
    table.sort(key=lambda r: (-r["score_vs_anchor"], -r["mean_margin"]))
    for r in table:
        log(f"  {r['candidate']:<22} {100 * r['score_vs_anchor']:5.1f}%  margin {r['mean_margin']:+6.2f}  ({r['games']} games)")
    return table


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--heuristic", required=True, choices=["H1", "H2", "H3"])
    ap.add_argument("--pop", type=int, default=20)
    ap.add_argument("--gens", type=int, default=20)
    ap.add_argument("--games", type=int, default=40, help="games per individual per generation (multiple of 4)")
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--elites", type=int, default=2)
    ap.add_argument("--cx-prob", type=float, default=0.7)
    ap.add_argument("--playoff-games", type=int, default=200)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--plies", type=int, default=6, help="random moves per opening")
    ap.add_argument("--n-tune", type=int, default=600)
    ap.add_argument("--n-heldout", type=int, default=400)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--quick", action="store_true", help="tiny run: pop 6, 3 gens, 8 games, depth 2")
    args = ap.parse_args()

    if args.quick:
        args.pop, args.gens, args.games, args.depth = 6, 3, 8, 2
        args.playoff_games, args.out = 20, os.path.join(args.out, "quick")
    if args.games % 4:
        raise SystemExit("--games must be a multiple of 4 (2 opponents x 2 colours)")

    hname = args.heuristic
    spec, fixed = gene_spec(hname)
    bound = max_possible_score(hname, to_weights(hname, [hi if abs(hi) >= abs(lo) else lo
                                                       for (_, _, lo, hi) in spec]))
    if bound >= TERMINAL_OFFSET:
        raise SystemExit(f"bounds allow heuristic values up to {bound}, not below {TERMINAL_OFFSET}")

    out_dir = os.path.join(args.out, hname)
    os.makedirs(out_dir, exist_ok=True)
    openings = load_openings(os.path.join(args.out, "openings.json"), args)["tuning"]
    ckpt_path = os.path.join(out_dir, "checkpoint.json")
    log_path = os.path.join(out_dir, "log.txt")

    def log(msg):
        print(msg)
        sys.stdout.flush()
        with open(log_path, "a") as f:
            f.write(msg + "\n")

    settings = {k: v for k, v in vars(args).items() if k not in ("resume", "workers", "quick")}
    if args.resume and os.path.exists(ckpt_path):
        with open(ckpt_path) as f:
            ck = json.load(f)
        if ck["settings"] != settings:
            raise SystemExit("settings differ from the checkpoint; use the same arguments as the original run")
        gen, pop, champion = ck["next_gen"], ck["population"], ck["champion"]
        champions, elapsed = ck["champions"], ck["elapsed_seconds"]
        # drop any CSV rows written after the last checkpoint (stop between the two writes)
        for name in ("generations.csv", "individuals.csv"):
            p = os.path.join(out_dir, name)
            if os.path.exists(p):
                with open(p, newline="") as f:
                    rows = list(csv.reader(f))
                with open(p, "w", newline="") as f:
                    csv.writer(f).writerows([rows[0]] + [r for r in rows[1:] if int(r[0]) < gen])
        log(f"Resuming {hname} at generation {gen} ({elapsed / 3600:.2f} h done)")
    else:
        if os.path.exists(ckpt_path) and not args.resume:
            raise SystemExit(f"{ckpt_path} exists: use --resume, or delete {out_dir} to start over")
        for name in ("generations.csv", "individuals.csv", "log.txt"):
            p = os.path.join(out_dir, name)
            if os.path.exists(p):
                os.remove(p)
        gen, elapsed = 0, 0.0
        pop = initial_population(spec, args.pop, random.Random(f"init-{args.seed}-{hname}"))
        champion = [g[1] for g in spec]              # generation 0: the anchor
        champions = []
        log(f"Tuning {hname}: {len(spec)} free genes, fixed {fixed}; pop {args.pop}, "
            f"{args.gens} generations, {args.games} games each, depth {args.depth}, "
            f"{args.workers} workers; max |score| {bound:.0f}")
        log(f"Python {sys.version.split()[0]} on {platform.platform()}, {os.cpu_count()} logical processors")

    gen_csv = os.path.join(out_dir, "generations.csv")
    ind_csv = os.path.join(out_dir, "individuals.csv")
    gene_names = [g[0] for g in spec]
    if not os.path.exists(gen_csv):
        with open(gen_csv, "w", newline="") as f:
            csv.writer(f).writerow(["gen", "best_fitness", "mean_fitness", "median_fitness",
                                    "best_vs_anchor", "mean_vs_anchor", "best_vs_champion",
                                    "seconds"] + [f"best_{g}" for g in gene_names])
    if not os.path.exists(ind_csv):
        with open(ind_csv, "w", newline="") as f:
            csv.writer(f).writerow(["gen", "individual", "fitness", "vs_anchor", "vs_champion",
                                    "mean_margin", "games"] + gene_names)

    with mp.Pool(args.workers) as pool:
        last_rows = None
        while gen < args.gens:
            t0 = time.time()
            rng = random.Random(f"gen-{args.seed}-{hname}-{gen}")   # deterministic, resumable
            rows, _ = evaluate_generation(pool, args, hname, pop, champion, openings, rng)
            fitness = [r["fitness"] for r in rows]
            best = max(range(len(pop)), key=lambda i: fitness[i])
            secs = time.time() - t0
            elapsed += secs

            with open(gen_csv, "a", newline="") as f:
                csv.writer(f).writerow([gen, fitness[best], statistics.mean(fitness),
                                        statistics.median(fitness), rows[best]["vs_anchor"],
                                        statistics.mean(r["vs_anchor"] for r in rows),
                                        rows[best]["vs_champion"], round(secs, 1)] + pop[best])
            with open(ind_csv, "a", newline="") as f:
                w = csv.writer(f)
                for i, r in enumerate(rows):
                    w.writerow([gen, i, r["fitness"], r["vs_anchor"], r["vs_champion"],
                                round(r["margin"], 3), r["games"]] + pop[i])
            log(f"gen {gen:>2}: best {100 * fitness[best]:5.1f}% (vs anchor {100 * rows[best]['vs_anchor']:5.1f}%, "
                f"vs champion {100 * rows[best]['vs_champion']:5.1f}%), mean {100 * statistics.mean(fitness):5.1f}%, "
                f"{secs / 60:.1f} min | {fmt_genome(spec, pop[best])}")

            champion = list(pop[best])
            champions.append({"gen": gen, "genome": champion, "fitness": fitness[best]})
            last_rows = (list(pop), fitness)
            gen += 1
            if gen < args.gens:
                pop = next_generation(pop, fitness, spec, rng, gen - 1, args.gens, args.elites, args.cx_prob)
            with open(ckpt_path, "w") as f:
                json.dump({"settings": settings, "next_gen": gen, "population": pop,
                           "champion": champion, "champions": champions,
                           "last_fitness": fitness, "elapsed_seconds": elapsed}, f)

        # ---- playoff ----
        if last_rows is None:                         # resumed after the last generation
            with open(ckpt_path) as f:
                ck = json.load(f)
            last_rows = (ck["population"], ck["last_fitness"])
        final_pop, final_fit = last_rows
        order = sorted(range(len(final_pop)), key=lambda i: -final_fit[i])
        candidates, seen = [], set()
        for i in order[:4]:
            key = tuple(round(v, 9) for v in final_pop[i])
            if key not in seen:
                seen.add(key)
                candidates.append((f"final gen #{len(candidates) + 1}", final_pop[i]))
        for c in champions[-3:]:
            key = tuple(round(v, 9) for v in c["genome"])
            if key not in seen:
                seen.add(key)
                candidates.append((f"champion gen {c['gen']}", c["genome"]))
        log(f"\nPlayoff: {len(candidates)} candidates x {args.playoff_games} games vs the anchor")
        t0 = time.time()
        table = playoff(pool, args, hname, candidates, openings,
                        random.Random(f"playoff-{args.seed}-{hname}"), log)
        elapsed += time.time() - t0

    best = table[0]
    result = {"heuristic": hname, "tuned_weights": best["weights"],
              "literature_weights": to_weights(hname, [g[1] for g in spec]),
              "playoff": table, "settings": settings,
              "wall_hours": elapsed / 3600, "workers": args.workers,
              "approx_cpu_hours": elapsed * args.workers / 3600,
              "python": sys.version.split()[0], "platform": platform.platform()}
    with open(os.path.join(out_dir, "tuned_weights.json"), "w") as f:
        json.dump(result, f, indent=2)
    log(f"\nTuned {hname} weights: {best['weights']}")
    log(f"Score vs literature weights in playoff: {100 * best['score_vs_anchor']:.1f}%")
    log(f"Total time {elapsed / 3600:.2f} h. Saved {os.path.join(out_dir, 'tuned_weights.json')}")


if __name__ == "__main__":      # required on Windows for multiprocessing
    mp.freeze_support()
    main()
