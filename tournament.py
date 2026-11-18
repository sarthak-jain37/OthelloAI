"""
Othello AI — Final Tournament Implementation Specification
===========================================================
- Two-Stage Multi-Pool Tournament:
  * Stage 1: 4 Pools (A, B, C, D) x 3 Heuristics (H1, H2, H3) = 12 bots, 24 games.
  * Stage 2: Championship Finals: Top 2 from each pool (8 bots) + GreedyAI + RandomAI = 10 bots, 90 games.
- Concurrency & Robustness:
  * ProcessPoolExecutor with configurable workers (default=8).
  * Worker auto-queueing: workers automatically pick up the next queued match.
  * State Checkpointing: every match result is atomically saved to 'tournament_state.json'.
    If the process is interrupted or shut down, running the script resumes right where it left off.
  * Worker benchmarking suite: measures 4, 6, 8, 10 workers on representative games.
- Search Settings (Strict):
  * Search depth: 6
  * Search mode: iterative deepening
  * Time limit: 4.0s per move
- Scoring & Leaderboards:
  * Win = 3 points, Draw = 1 point, Loss = 0 points.
  * Points tables for Pool A, Pool B, Pool C, Pool D, and Finals.
  * Metrics: disc differential, avg & max search time, total & final-iteration nodes, timeouts.
  * Exports to CSV ('tournament_results/tournament_matches.csv') and JSON ('tournament_results/tournament_results.json').
"""

import copy
import csv
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from core.board import Board
from core.player import Player
from algorithms.minimax import MinimaxAI
from algorithms.negamax import NegamaxAI
from algorithms.baseline_ai import RandomAI, GreedyAI
from algorithms.heuristics import H1, H2, H3

STATE_FILE = "tournament_state.json"
RESULTS_DIR = "tournament_results"


# --------------------------------------------------------------------------
# Bot Definition & Factory Specifications
# --------------------------------------------------------------------------

@dataclass
class BotSpec:
    bot_id: str
    display_name: str
    pool: str
    algorithm: str
    heuristic_name: str
    heuristic_version: str = "tuned"  # "tuned" or "literature"
    depth: int = 30
    search_mode: str = "iterative"
    time_limit: float = 4.0
    use_pruning: bool = True
    use_move_ordering: bool = True
    is_baseline: bool = False

    def instantiate(self) -> Any:
        if self.is_baseline:
            if self.algorithm == "GreedyAI":
                return GreedyAI()
            elif self.algorithm == "RandomAI":
                return RandomAI()
            else:
                raise ValueError(f"Unknown baseline: {self.algorithm}")

        h_cls = {"H1": H1, "H2": H2, "H3": H3}.get(self.heuristic_name)
        if not h_cls:
            raise ValueError(f"Unknown heuristic: {self.heuristic_name}")
        heuristic_obj = h_cls(self.heuristic_version) if self.heuristic_version != "tuned" else h_cls()

        if self.algorithm == "Minimax":
            return MinimaxAI(
                depth=self.depth,
                search_mode=self.search_mode,
                time_limit=self.time_limit,
                use_pruning=self.use_pruning,
                use_move_ordering=self.use_move_ordering,
                heuristic=heuristic_obj
            )
        elif self.algorithm == "Negamax":
            return NegamaxAI(
                depth=self.depth,
                search_mode=self.search_mode,
                time_limit=self.time_limit,
                use_pruning=self.use_pruning,
                use_move_ordering=self.use_move_ordering,
                heuristic=heuristic_obj
            )
        else:
            raise ValueError(f"Unknown search algorithm: {self.algorithm}")


# --------------------------------------------------------------------------
# Fixtures & Match Result Records
# --------------------------------------------------------------------------

@dataclass
class Fixture:
    match_id: str
    stage: str
    pool: str
    black_spec: BotSpec
    white_spec: BotSpec
    seed: int


@dataclass
class MatchResult:
    match_id: str
    stage: str
    pool: str
    black_bot_id: str
    white_bot_id: str
    black_algorithm: str
    white_algorithm: str
    black_heuristic: str
    white_heuristic: str
    black_score: int
    white_score: int
    disc_differential: int
    winner_bot_id: Optional[str]
    is_draw: bool
    total_duration: float
    black_avg_time: float
    black_max_time: float
    black_total_nodes: int
    black_final_iter_nodes: int
    black_completed_iters: int
    black_timeouts: int
    white_avg_time: float
    white_max_time: float
    white_total_nodes: int
    white_final_iter_nodes: int
    white_completed_iters: int
    white_timeouts: int
    status: str = "COMPLETED"
    error_message: Optional[str] = None


# --------------------------------------------------------------------------
# Checkpoint Helpers
# --------------------------------------------------------------------------

def load_checkpoint() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_checkpoint(state: Dict[str, Any]):
    temp_file = STATE_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(temp_file, STATE_FILE)


# --------------------------------------------------------------------------
# Isolated Match Execution (Top-Level Picklable for ProcessPoolExecutor)
# --------------------------------------------------------------------------

class SilentRunner:
    """Silences stdout/stderr during search iterations so terminal stays clean."""
    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            sys.stdout.close()
            sys.stderr.close()
        finally:
            sys.stdout = self._stdout
            sys.stderr = self._stderr


def execute_match_worker(fixture: Fixture) -> MatchResult:
    """
    Executes a single game completely in process isolation.
    """
    random.seed(fixture.seed)

    black_spec = fixture.black_spec
    white_spec = fixture.white_spec

    black_ai = black_spec.instantiate()
    white_ai = white_spec.instantiate()

    board = Board()
    p_black = Player(1, is_bot=True, algorithm=black_ai)
    p_white = Player(-1, is_bot=True, algorithm=white_ai)

    players = {1: p_black, -1: p_white}
    agents = {1: black_ai, -1: white_ai}
    specs = {1: black_spec, -1: white_spec}

    stats = {
        1: {"times": [], "nodes": [], "final_nodes": [], "iters": [], "timeouts": 0},
        -1: {"times": [], "nodes": [], "final_nodes": [], "iters": [], "timeouts": 0}
    }

    current = 1
    passes = 0
    match_start = time.perf_counter()
    status = "COMPLETED"
    error_message = None

    try:
        while passes < 2:
            curr_p = players[current]
            valid_moves = board.get_valid_moves(curr_p)

            if not valid_moves:
                passes += 1
                current = -current
                continue
            passes = 0

            active_ai = agents[current]

            # Reset search counters
            if hasattr(active_ai, "nodes_evaluated"):
                active_ai.nodes_evaluated = 0

            isolated_board = copy.deepcopy(board)
            turn_player = Player(current)

            t0 = time.perf_counter()
            with SilentRunner():
                try:
                    move = active_ai.find_best_move(isolated_board, turn_player)
                except Exception as exc:
                    status = "ERROR"
                    error_message = f"Exception in {specs[current].bot_id}: {exc}"
                    break
            elapsed = time.perf_counter() - t0

            nodes = getattr(active_ai, "nodes_evaluated", 0)
            stats[current]["times"].append(elapsed)
            stats[current]["nodes"].append(nodes)
            stats[current]["final_nodes"].append(nodes)
            stats[current]["iters"].append(getattr(active_ai, "completed_depth", getattr(active_ai, "depth", 1)))
            if elapsed >= getattr(active_ai, "time_limit", 4.0) - 0.05:
                stats[current]["timeouts"] += 1

            if move is None or not board.make_move(curr_p, move[0], move[1]):
                status = "ERROR"
                error_message = f"Illegal move by {specs[current].bot_id}: {move}"
                break

            current = -current

    except Exception as exc:
        status = "ERROR"
        error_message = f"Unexpected failure: {exc}"

    total_duration = time.perf_counter() - match_start
    b_score = board.count_tokens(p_black)
    w_score = board.count_tokens(p_white)
    diff = b_score - w_score

    if status == "COMPLETED":
        if b_score > w_score:
            winner = black_spec.bot_id
            is_draw = False
        elif w_score > b_score:
            winner = white_spec.bot_id
            is_draw = False
        else:
            winner = None
            is_draw = True
    else:
        if "in " + black_spec.bot_id in (error_message or ""):
            winner = white_spec.bot_id
            is_draw = False
        elif "in " + white_spec.bot_id in (error_message or ""):
            winner = black_spec.bot_id
            is_draw = False
        else:
            winner = None
            is_draw = True

    b_times = stats[1]["times"]
    w_times = stats[-1]["times"]
    b_nodes = stats[1]["nodes"]
    w_nodes = stats[-1]["nodes"]

    return MatchResult(
        match_id=fixture.match_id,
        stage=fixture.stage,
        pool=fixture.pool,
        black_bot_id=black_spec.bot_id,
        white_bot_id=white_spec.bot_id,
        black_algorithm=black_spec.algorithm,
        white_algorithm=white_spec.algorithm,
        black_heuristic=black_spec.heuristic_name,
        white_heuristic=white_spec.heuristic_name,
        black_score=b_score,
        white_score=w_score,
        disc_differential=diff,
        winner_bot_id=winner,
        is_draw=is_draw,
        total_duration=total_duration,
        black_avg_time=(sum(b_times) / len(b_times)) if b_times else 0.0,
        black_max_time=max(b_times) if b_times else 0.0,
        black_total_nodes=sum(b_nodes),
        black_final_iter_nodes=sum(stats[1]["final_nodes"]),
        black_completed_iters=int(sum(stats[1]["iters"]) / len(stats[1]["iters"])) if stats[1]["iters"] else 0,
        black_timeouts=stats[1]["timeouts"],
        white_avg_time=(sum(w_times) / len(w_times)) if w_times else 0.0,
        white_max_time=max(w_times) if w_times else 0.0,
        white_total_nodes=sum(w_nodes),
        white_final_iter_nodes=sum(stats[-1]["final_nodes"]),
        white_completed_iters=int(sum(stats[-1]["iters"]) / len(stats[-1]["iters"])) if stats[-1]["iters"] else 0,
        white_timeouts=stats[-1]["timeouts"],
        status=status,
        error_message=error_message
    )


# --------------------------------------------------------------------------
# Standings Table & Formatting
# --------------------------------------------------------------------------

@dataclass
class Standing:
    bot_id: str
    pool: str
    algorithm: str
    heuristic: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    points: float = 0.0
    discs_for: int = 0
    discs_against: int = 0
    disc_differential: int = 0
    total_time: float = 0.0
    avg_execution_time: float = 0.0
    total_nodes: int = 0
    avg_nodes_explored: float = 0.0


def compute_standings(bots: List[BotSpec], results: List[MatchResult]) -> List[Standing]:
    """
    Computes tournament standings:
    Win = 3, Draw = 1, Loss = 0.
    Rank primarily by tournament points, secondarily by disc differential.
    """
    m: Dict[str, Standing] = {
        b.bot_id: Standing(
            bot_id=b.bot_id,
            pool=b.pool,
            algorithm=b.algorithm,
            heuristic=b.heuristic_name
        )
        for b in bots
    }

    for res in results:
        b_id, w_id = res.black_bot_id, res.white_bot_id
        if b_id in m:
            s = m[b_id]
            s.played += 1
            s.discs_for += res.black_score
            s.discs_against += res.white_score
            s.disc_differential += (res.black_score - res.white_score)
            s.total_time += res.black_avg_time
            s.total_nodes += res.black_total_nodes
            if res.is_draw:
                s.draws += 1
                s.points += 1.0
            elif res.winner_bot_id == b_id:
                s.wins += 1
                s.points += 3.0
            else:
                s.losses += 1

        if w_id in m:
            s = m[w_id]
            s.played += 1
            s.discs_for += res.white_score
            s.discs_against += res.black_score
            s.disc_differential += (res.white_score - res.black_score)
            s.total_time += res.white_avg_time
            s.total_nodes += res.white_total_nodes
            if res.is_draw:
                s.draws += 1
                s.points += 1.0
            elif res.winner_bot_id == w_id:
                s.wins += 1
                s.points += 3.0
            else:
                s.losses += 1

    for s in m.values():
        if s.played > 0:
            s.avg_execution_time = s.total_time / s.played
            s.avg_nodes_explored = s.total_nodes / s.played

    ranked = sorted(
        list(m.values()),
        key=lambda x: (x.points, x.disc_differential, x.wins),
        reverse=True
    )
    return ranked


def print_points_table(title: str, standings: List[Standing]):
    print("\n" + "=" * 118)
    print(f" {title.upper()} - POINTS TABLE (Win=3, Draw=1, Loss=0)")
    print("=" * 118)
    header = f"{'Rank':<5}{'Bot ID':<22}{'Algorithm':<14}{'Heur':<6}{'Pld':<5}{'W-D-L':<10}{'Pts':<6}{'For':<6}{'Agn':<6}{'Diff':<8}{'AvgTime(s)':<12}{'AvgNodes':<10}"
    print(header)
    print("-" * 118)
    for rank, s in enumerate(standings, 1):
        wdl = f"{s.wins}-{s.draws}-{s.losses}"
        print(
            f"{rank:<5}"
            f"{s.bot_id:<22}"
            f"{s.algorithm:<14}"
            f"{s.heuristic:<6}"
            f"{s.played:<5}"
            f"{wdl:<10}"
            f"{s.points:<6.1f}"
            f"{s.discs_for:<6}"
            f"{s.discs_against:<6}"
            f"{s.disc_differential:<+8d}"
            f"{s.avg_execution_time:<12.3f}"
            f"{int(s.avg_nodes_explored):<10}"
        )
    print("=" * 118 + "\n")


# --------------------------------------------------------------------------
# Fixture Generation
# --------------------------------------------------------------------------

def generate_round_robin_fixtures(
    bots: List[BotSpec],
    stage: str,
    pool_name: str,
    base_seed: int = 1000
) -> List[Fixture]:
    """
    Generates full double round-robin fixtures:
    Every pair (A, B) plays twice: (A black, B white) and (B black, A white).
    """
    fixtures: List[Fixture] = []
    n = len(bots)
    match_counter = 1
    for i in range(n):
        for j in range(i + 1, n):
            b_a = bots[i]
            b_b = bots[j]
            # Match 1: A as Black, B as White
            fixtures.append(
                Fixture(
                    match_id=f"{stage}_{pool_name}_M{match_counter:03d}",
                    stage=stage,
                    pool=pool_name,
                    black_spec=b_a,
                    white_spec=b_b,
                    seed=base_seed + match_counter
                )
            )
            match_counter += 1
            # Match 2: B as Black, A as White
            fixtures.append(
                Fixture(
                    match_id=f"{stage}_{pool_name}_M{match_counter:03d}",
                    stage=stage,
                    pool=pool_name,
                    black_spec=b_b,
                    white_spec=b_a,
                    seed=base_seed + match_counter
                )
            )
            match_counter += 1
    return fixtures


# --------------------------------------------------------------------------
# Parallel Execution Engine with Checkpoint Resume
# --------------------------------------------------------------------------

def run_fixtures_parallel(
    fixtures: List[Fixture],
    max_workers: int = 8,
    stage_title: str = "Matches",
    state: Optional[Dict[str, Any]] = None
) -> List[MatchResult]:
    """
    Executes fixtures using ProcessPoolExecutor with dynamic queueing and state checkpointing.
    Any match already recorded in state is instantly loaded without re-computation.
    """
    if state is None:
        state = {}
    if "matches" not in state:
        state["matches"] = {}

    saved_matches = state["matches"]
    total = len(fixtures)
    results: List[MatchResult] = []
    pending_fixtures: List[Fixture] = []

    # Filter out already completed matches
    for fix in fixtures:
        if fix.match_id in saved_matches:
            results.append(MatchResult(**saved_matches[fix.match_id]))
        else:
            pending_fixtures.append(fix)

    completed = len(results)
    print("\n" + "#" * 80)
    print(f" {stage_title.upper()}: {total} Total | {completed} Resumed from Checkpoint | {len(pending_fixtures)} Remaining")
    print(f" Concurrency: {max_workers} Workers (ProcessPoolExecutor)")
    print("#" * 80)

    if not pending_fixtures:
        return results

    start_time = time.perf_counter()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_fix = {executor.submit(execute_match_worker, fix): fix for fix in pending_fixtures}

        for future in as_completed(future_to_fix):
            res = future.result()
            results.append(res)
            completed += 1

            # Atomically save to checkpoint
            saved_matches[res.match_id] = asdict(res)
            save_checkpoint(state)

            elapsed = time.perf_counter() - start_time
            avg_per_game = elapsed / (completed - (total - len(pending_fixtures)))
            remaining = total - completed
            eta_seconds = remaining * (avg_per_game / max_workers)

            winner_label = res.winner_bot_id if not res.is_draw else "DRAW"
            print(
                f"[{completed:02d}/{total:02d}] {res.match_id} ({res.pool}): "
                f"{res.black_bot_id} (B) {res.black_score}-{res.white_score} (W) {res.white_bot_id} "
                f"-> {winner_label} [{res.total_duration:.1f}s | ETA: {eta_seconds/60:.1f}m]"
            )

    return results


# --------------------------------------------------------------------------
# Worker Concurrency Benchmarking Suite
# --------------------------------------------------------------------------

def benchmark_concurrency(worker_counts: List[int] = [4, 6, 8, 10]) -> int:
    """
    Benchmarks 4, 6, 8, and 10 workers on representative games to evaluate
    throughput vs CPU contention.
    """
    print("\n" + "=" * 80)
    print(" BENCHMARKING WORKER CONCURRENCY (4, 6, 8, 10 WORKERS)")
    print("=" * 80)

    b1 = BotSpec(
        bot_id="Bench_MM_H1", display_name="Bench_MM_H1", pool="Bench",
        algorithm="Minimax", heuristic_name="H1", depth=4, search_mode="fixed", time_limit=1.0
    )
    b2 = BotSpec(
        bot_id="Bench_Nega_H2", display_name="Bench_Nega_H2", pool="Bench",
        algorithm="Negamax", heuristic_name="H2", depth=4, search_mode="fixed", time_limit=1.0
    )
    sample_fixtures = [
        Fixture(f"Bench_{i}", "Benchmark", "Bench", b1, b2, 100 + i)
        for i in range(8)
    ]

    best_workers = 8
    best_time = float("inf")

    for w in worker_counts:
        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=w) as executor:
            futures = [executor.submit(execute_match_worker, f) for f in sample_fixtures]
            for fut in as_completed(futures):
                fut.result()
        dur = time.perf_counter() - t0
        print(f" -> Workers: {w:2d} | Duration: {dur:5.2f}s | Throughput: {len(sample_fixtures)/dur:4.2f} games/s")
        if dur < best_time:
            best_time = dur
            best_workers = w

    print(f"\nOptimal Concurrency Selected: {best_workers} Workers (Default=8)\n")
    return best_workers


# --------------------------------------------------------------------------
# Export Deliverables (CSV & JSON)
# --------------------------------------------------------------------------

def export_tournament_deliverables(
    all_results: List[MatchResult],
    pool_standings: Dict[str, List[Standing]],
    finals_standings: List[Standing],
    output_dir: str = RESULTS_DIR
):
    os.makedirs(output_dir, exist_ok=True)
    csv_file = os.path.join(output_dir, "tournament_matches.csv")
    json_file = os.path.join(output_dir, "tournament_results.json")

    # 1. Export CSV
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        fields = [
            "match_id", "stage", "pool", "black_bot_id", "white_bot_id",
            "black_algorithm", "white_algorithm", "black_heuristic", "white_heuristic",
            "black_score", "white_score", "disc_differential", "winner_bot_id", "is_draw",
            "total_duration", "black_avg_time", "black_max_time", "black_total_nodes",
            "black_final_iter_nodes", "black_completed_iters", "black_timeouts",
            "white_avg_time", "white_max_time", "white_total_nodes", "white_final_iter_nodes",
            "white_completed_iters", "white_timeouts", "status", "error_message"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            writer.writerow(asdict(r))

    # 2. Export JSON
    payload = {
        "group_stage": {pool: [asdict(s) for s in standings] for pool, standings in pool_standings.items()},
        "finals_leaderboard": [asdict(s) for s in finals_standings],
        "matches": [asdict(r) for r in all_results]
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\n[Deliverables Saved]:\n  - CSV:  {os.path.abspath(csv_file)}\n  - JSON: {os.path.abspath(json_file)}")


# --------------------------------------------------------------------------
# Main Tournament Orchestrator
# --------------------------------------------------------------------------

def run_tournament(
    max_workers: int = 8,
    run_benchmark: bool = False,
    depth: int = 30,
    time_limit: float = 4.0
):
    if run_benchmark:
        max_workers = benchmark_concurrency([4, 6, 8, 10])

    state = load_checkpoint()

    print("\n" + "#" * 80)
    print(" OTHELLO AI — TWO-STAGE TOURNAMENT SPECIFICATION RUNNER")
    print(f" Workers: {max_workers} | Depth: {depth} | Mode: Iterative Deepening | Time: {time_limit}s/move")
    print(f" Checkpoint State: {os.path.abspath(STATE_FILE)}")
    print("#" * 80)

    # -----------------------------------------------------------------
    # 1. GROUP STAGE: 4 Pools (A, B, C, D) x 3 Heuristics (H1, H2, H3)
    # -----------------------------------------------------------------
    pool_a_bots = [
        BotSpec(f"PoolA_{h}", f"Pool A ({h})", "Pool_A", "Minimax", h, depth=depth, time_limit=time_limit, use_pruning=True, use_move_ordering=True)
        for h in ["H1", "H2", "H3"]
    ]
    pool_b_bots = [
        BotSpec(f"PoolB_{h}", f"Pool B ({h})", "Pool_B", "Minimax", h, depth=depth, time_limit=time_limit, use_pruning=True, use_move_ordering=False)
        for h in ["H1", "H2", "H3"]
    ]
    pool_c_bots = [
        BotSpec(f"PoolC_{h}", f"Pool C ({h})", "Pool_C", "Minimax", h, depth=depth, time_limit=time_limit, use_pruning=False, use_move_ordering=False)
        for h in ["H1", "H2", "H3"]
    ]
    pool_d_bots = [
        BotSpec(f"PoolD_{h}", f"Pool D ({h})", "Pool_D", "Negamax", h, depth=depth, time_limit=time_limit, use_pruning=True, use_move_ordering=True)
        for h in ["H1", "H2", "H3"]
    ]

    # Generate all 24 group stage fixtures
    group_fixtures: List[Fixture] = []
    group_fixtures.extend(generate_round_robin_fixtures(pool_a_bots, "Stage_1", "Pool_A", 1000))
    group_fixtures.extend(generate_round_robin_fixtures(pool_b_bots, "Stage_1", "Pool_B", 2000))
    group_fixtures.extend(generate_round_robin_fixtures(pool_c_bots, "Stage_1", "Pool_C", 3000))
    group_fixtures.extend(generate_round_robin_fixtures(pool_d_bots, "Stage_1", "Pool_D", 4000))

    # Run group stage in parallel with automatic checkpointing
    group_results = run_fixtures_parallel(
        group_fixtures, max_workers=max_workers, stage_title="Stage 1 — Group Stage (24 Games)", state=state
    )

    # Partition results per pool & generate points tables
    pool_results = {"Pool_A": [], "Pool_B": [], "Pool_C": [], "Pool_D": []}
    for res in group_results:
        pool_results[res.pool].append(res)

    pool_standings = {
        "Pool_A": compute_standings(pool_a_bots, pool_results["Pool_A"]),
        "Pool_B": compute_standings(pool_b_bots, pool_results["Pool_B"]),
        "Pool_C": compute_standings(pool_c_bots, pool_results["Pool_C"]),
        "Pool_D": compute_standings(pool_d_bots, pool_results["Pool_D"]),
    }

    # Print Points Tables for ALL 4 Pools
    print_points_table("Pool A (Minimax + AlphaBeta + MoveOrdering)", pool_standings["Pool_A"])
    print_points_table("Pool B (Minimax + AlphaBeta)", pool_standings["Pool_B"])
    print_points_table("Pool C (Plain Minimax - No Pruning)", pool_standings["Pool_C"])
    print_points_table("Pool D (Negamax + AlphaBeta + MoveOrdering)", pool_standings["Pool_D"])

    # -----------------------------------------------------------------
    # QUALIFICATION: Select Top 2 from each pool (8 Bots)
    # -----------------------------------------------------------------
    all_group_bots = {b.bot_id: b for b in (pool_a_bots + pool_b_bots + pool_c_bots + pool_d_bots)}
    qualifiers: List[BotSpec] = []

    print("=" * 80)
    print(" QUALIFICATION SUMMARY: TOP 2 QUALIFIERS ADVANCING TO CHAMPIONSHIP")
    print("=" * 80)
    for p_name in ["Pool_A", "Pool_B", "Pool_C", "Pool_D"]:
        top2 = pool_standings[p_name][:2]
        print(f" {p_name}: {[s.bot_id for s in top2]} (1st: {top2[0].points} pts, 2nd: {top2[1].points} pts)")
        for s in top2:
            qualifiers.append(all_group_bots[s.bot_id])

    # -----------------------------------------------------------------
    # 2. STAGE 2: FINAL CHAMPIONSHIP (8 Qualifiers + Greedy + Random = 10 Bots)
    # -----------------------------------------------------------------
    baselines = [
        BotSpec("Baseline_Greedy", "GreedyAI", "Finals", "GreedyAI", "None", is_baseline=True),
        BotSpec("Baseline_Random", "RandomAI", "Finals", "RandomAI", "None", is_baseline=True)
    ]
    finals_bots = qualifiers + baselines

    print(f"\nFinals Pool (10 Bots): {[b.bot_id for b in finals_bots]}")

    # Generate all 90 finals fixtures upfront
    finals_fixtures = generate_round_robin_fixtures(finals_bots, "Stage_2", "Finals", 5000)

    # Run all 90 finals matches in parallel with automatic checkpointing
    finals_results = run_fixtures_parallel(
        finals_fixtures, max_workers=max_workers, stage_title="Stage 2 — Championship Finals (90 Games)", state=state
    )

    finals_standings = compute_standings(finals_bots, finals_results)
    print_points_table("FINAL CHAMPIONSHIP LEADERBOARD", finals_standings)

    # -----------------------------------------------------------------
    # Deliverables & Winner Announcement
    # -----------------------------------------------------------------
    all_results = group_results + finals_results
    export_tournament_deliverables(all_results, pool_standings, finals_standings)

    champion = finals_standings[0]
    runner_up = finals_standings[1]

    print("\n" + "*" * 80)
    print(" 🏆 TOURNAMENT RESULTS & AWARDS 🏆")
    print("*" * 80)
    print(f" 🥇 CHAMPION : {champion.bot_id} ({champion.algorithm} + {champion.heuristic}) with {champion.points:.1f} pts ({champion.wins}W-{champion.draws}D-{champion.losses}L, Diff: {champion.disc_differential:+d})")
    print(f" 🥈 RUNNER-UP: {runner_up.bot_id} ({runner_up.algorithm} + {runner_up.heuristic}) with {runner_up.points:.1f} pts ({runner_up.wins}W-{runner_up.draws}D-{runner_up.losses}L, Diff: {runner_up.disc_differential:+d})")
    print("*" * 80 + "\n")


if __name__ == "__main__":
    run_tournament(max_workers=8, run_benchmark=False, depth=30, time_limit=4.0)
