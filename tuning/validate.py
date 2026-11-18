"""
Validate the tuned weights on the HELD-OUT openings (never used in tuning).

Run from the repository root:
    python -m tuning.validate                      all heuristics, all 400 held-out openings
    python -m tuning.validate --heuristics H2      one heuristic
    python -m tuning.validate --openings 100       fewer openings (faster, less precise)

For each heuristic, three matches (each opening played with both colours):
  1. tuned      vs literature   does tuning beat the starting weights?
  2. gen-0 best vs literature   how much did the first random variations already gain?
  3. tuned      vs gen-0 best   did the later generations add anything?

Uses the same depth and search as tuning (read from tuned_weights.json).
Needs, from tune.py runs: tuning/results/openings.json,
tuning/results/<H>/tuned_weights.json and tuning/results/<H>/generations.csv.

Writes tuning/results/validation.json (summary) and tuning/results/validation_games.csv
(one row per game).
"""
import argparse
import csv
import json
import math
import multiprocessing as mp
import os
import sys
import time

from tuning.tune import play_game, gene_spec, to_weights, DEFAULT_OUT


def load_gen0_best(path, hname):
    spec, _ = gene_spec(hname)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["gen"] == "0":
                return to_weights(hname, [float(row[f"best_{name}"]) for (name, *_) in spec])
    raise SystemExit(f"no generation 0 in {path}")


def run_match(pool, hname, wa, wb, openings, depth):
    """A vs B on every opening, both colours. Returns per-game rows and a summary."""
    tasks = []
    for i, ops in enumerate(openings):
        for a_black in (True, False):
            tasks.append(((i, a_black), hname, wa, wb, ops, a_black, depth))
    t0 = time.time()
    games = []
    for (i, a_black), score, margin in pool.imap_unordered(play_game, tasks, chunksize=1):
        games.append({"opening": i, "a_is_black": a_black, "score": score, "margin": margin})
    secs = time.time() - t0
    games.sort(key=lambda g: (g["opening"], not g["a_is_black"]))
    n = len(games)
    scores = [g["score"] for g in games]
    mean = sum(scores) / n
    # 95% confidence interval: games are grouped in colour-swapped pairs on the
    # same opening, so use the pair averages as the independent samples
    pairs = [(games[k]["score"] + games[k + 1]["score"]) / 2 for k in range(0, n, 2)]
    m = len(pairs)
    var = sum((p - mean) ** 2 for p in pairs) / (m - 1) if m > 1 else 0.0
    half = 1.96 * math.sqrt(var / m) if m > 1 else float("nan")
    summary = {"score": mean, "ci95": half,
               "wins": sum(s == 1.0 for s in scores), "draws": sum(s == 0.5 for s in scores),
               "losses": sum(s == 0.0 for s in scores),
               "mean_margin": sum(g["margin"] for g in games) / n, "games": n, "minutes": secs / 60}
    return games, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--heuristics", default="H1,H2,H3")
    ap.add_argument("--openings", type=int, default=400, help="number of held-out openings (max 400)")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--results", default=DEFAULT_OUT)
    ap.add_argument("--no-gen0", action="store_true", help="skip the two gen-0 matches")
    args = ap.parse_args()

    with open(os.path.join(args.results, "openings.json")) as f:
        heldout = json.load(f)["heldout"][: args.openings]
    out_json = os.path.join(args.results, "validation.json")
    out_csv = os.path.join(args.results, "validation_games.csv")
    summary = {}
    if os.path.exists(out_json):
        with open(out_json) as f:
            summary = json.load(f)          # keep results of heuristics not rerun
    rerun = [h.strip() for h in args.heuristics.split(",")]
    if os.path.exists(out_csv):             # drop old rows for heuristics being rerun
        with open(out_csv, newline="") as f:
            rows = list(csv.reader(f))
        with open(out_csv, "w", newline="") as f:
            csv.writer(f).writerows([rows[0]] + [r for r in rows[1:] if r[0] not in rerun])
    new_csv = not os.path.exists(out_csv)

    print(f"Held-out openings: {len(heldout)} (x2 colours = {2 * len(heldout)} games per match), "
          f"{args.workers} workers")
    with mp.Pool(args.workers) as pool, open(out_csv, "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if new_csv:
            w.writerow(["heuristic", "match", "opening", "a_is_black", "score_a", "margin_a"])
        for hname in rerun:
            hdir = os.path.join(args.results, hname)
            with open(os.path.join(hdir, "tuned_weights.json")) as f:
                tuned_file = json.load(f)
            depth = tuned_file["settings"]["depth"]
            tuned, lit = tuned_file["tuned_weights"], tuned_file["literature_weights"]
            matches = [("tuned vs literature", tuned, lit)]
            if not args.no_gen0:
                gen0 = load_gen0_best(os.path.join(hdir, "generations.csv"), hname)
                matches += [("gen-0 best vs literature", gen0, lit), ("tuned vs gen-0 best", tuned, gen0)]
            print(f"\n=== {hname} (depth {depth}) ===")
            summary[hname] = {"depth": depth, "openings": len(heldout), "matches": {}}
            for label, wa, wb in matches:
                games, s = run_match(pool, hname, wa, wb, heldout, depth)
                for g in games:
                    w.writerow([hname, label, g["opening"], g["a_is_black"], g["score"], g["margin"]])
                fcsv.flush()
                summary[hname]["matches"][label] = s
                print(f"  {label:<26} {100 * s['score']:5.1f}% ± {100 * s['ci95']:4.1f}  "
                      f"(W {s['wins']} / D {s['draws']} / L {s['losses']}), "
                      f"margin {s['mean_margin']:+6.2f}, {s['minutes']:.1f} min")
                sys.stdout.flush()
            with open(out_json, "w") as f:
                json.dump(summary, f, indent=2)
    print(f"\nSaved {out_json} and {out_csv}")


if __name__ == "__main__":      # required on Windows for multiprocessing
    mp.freeze_support()
    main()
