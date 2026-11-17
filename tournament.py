import copy
import random
from board import Board
from player import Player
from minimax import MinimaxAI
from negamax import NegamaxAI
from baseline_ai import RandomAI, GreedyAI

# 1. ADD YOUR HEURISTICS HERE: [("Name", func), ...]
HEURISTICS = [
    ("H1", None),
    ("H2", None),
    ("H3", None),
]


def play_game(bot1, bot2):
    """Plays 1 game: bot1 is Black (1), bot2 is White (-1). Returns (b_score, w_score)."""
    board = Board()
    current = 1
    players = {1: Player(1, is_bot=True, algorithm=bot1), -1: Player(-1, is_bot=True, algorithm=bot2)}
    passes = 0

    while passes < 2:
        moves = board.get_valid_moves(players[current])
        if not moves:
            passes += 1
            current = -current
            continue
        passes = 0
        move = players[current].algorithm.find_best_move(copy.deepcopy(board), Player(current))
        if not move or not board.make_move(players[current], *move):
            break
        current = -current

    return board.count_tokens(players[1]), board.count_tokens(players[-1])


def run_pool(bots, name="Tournament"):
    """Round-robin: each pair plays twice (swapping colours). Win=1, Draw=0.5, Loss=0."""
    scores = {bot: {"pts": 0.0, "diff": 0} for bot in bots}
    names = list(bots.keys())

    print(f"\n--- {name} ---")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            b1, b2 = names[i], names[j]
            for black, white in [(b1, b2), (b2, b1)]:
                s_b, s_w = play_game(bots[black](), bots[white]())
                scores[black]["diff"] += s_b - s_w
                scores[white]["diff"] += s_w - s_b

                if s_b > s_w:
                    scores[black]["pts"] += 1.0
                elif s_w > s_b:
                    scores[white]["pts"] += 1.0
                else:
                    scores[black]["pts"] += 0.5
                    scores[white]["pts"] += 0.5

                print(f"{black} (B) {s_b} - {s_w} (W) {white}")

    # Rank by points, tie-break by disc differential
    ranked = sorted(names, key=lambda x: (scores[x]["pts"], scores[x]["diff"]), reverse=True)
    print("\nStandings:")
    for r, b in enumerate(ranked, 1):
        print(f"  {r}. {b:<15} Pts: {scores[b]['pts']}  Diff: {scores[b]['diff']:+d}")
    return ranked


if __name__ == "__main__":
    depth = 3

    # Stage 1: Minimax without pruning
    s1 = run_pool(
        {name: (lambda fn=fn: MinimaxAI(depth=depth, use_pruning=False, use_move_ordering=False, heuristic=fn)) for name, fn in HEURISTICS},
        "Stage 1: Heuristics"
    )

    # Stage 2: Minimax AB vs Negamax AB
    p2 = run_pool(
        {f"MM_AB_{name}": (lambda fn=fn: MinimaxAI(depth=depth, use_pruning=True, use_move_ordering=True, heuristic=fn)) for name, fn in HEURISTICS},
        "Stage 2: Minimax (AB + MO)"
    )
    p3 = run_pool(
        {f"Nega_AB_{name}": (lambda fn=fn: NegamaxAI(depth=depth, use_pruning=True, use_move_ordering=True, heuristic=fn)) for name, fn in HEURISTICS},
        "Stage 2: Negamax (AB + MO)"
    )

    # Stage 3: Top 2 from each pool + Baselines
    championship = {
        s1[0]: (lambda: MinimaxAI(depth=depth, use_pruning=False, use_move_ordering=False)),
        s1[1]: (lambda: MinimaxAI(depth=depth, use_pruning=False, use_move_ordering=False)),
        p2[0]: (lambda: MinimaxAI(depth=depth, use_pruning=True, use_move_ordering=True)),
        p2[1]: (lambda: MinimaxAI(depth=depth, use_pruning=True, use_move_ordering=True)),
        p3[0]: (lambda: NegamaxAI(depth=depth, use_pruning=True, use_move_ordering=True)),
        p3[1]: (lambda: NegamaxAI(depth=depth, use_pruning=True, use_move_ordering=True)),
        "RandomAI": (lambda: RandomAI()),
        "GreedyAI": (lambda: GreedyAI()),
    }
    champ = run_pool(championship, "Stage 3: Championship")
    print(f"\nWINNER: {champ[0]}")
