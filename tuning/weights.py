"""
Helpers for using the tuning results (e.g. in the tournament).

    import core                                   # import core before algorithms
    from tuning.weights import load_heuristic, load_openings, start_position

    h2 = load_heuristic("H2")                     # tuned H2 (official)
    h1_alt = load_heuristic("H1", version="gen0") # generation-0 best H1 (alternative)
    for opening in load_openings():               # the 400 held-out openings
        board, to_move = start_position(opening)

These only read files in tuning/results; they do not change any weights.
"""
import json
import os

from core.board import Board
from core.player import Player
from algorithms.heuristics import H1, H2, H3

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
_CLASSES = {"H1": H1, "H2": H2, "H3": H3}


def load_weights(name, version="tuned"):
    """Weight dict. name: "H1", "H2" or "H3". version: "tuned" (official),
    "gen0" (best of the GA's first generation) or "literature" (starting values)."""
    if name not in _CLASSES:
        raise ValueError(f"name must be H1, H2 or H3, not {name!r}")
    if version == "gen0":
        with open(os.path.join(RESULTS, name, "gen0_best_weights.json")) as f:
            return json.load(f)["gen0_best_weights"]
    if version in ("tuned", "literature"):
        with open(os.path.join(RESULTS, name, "tuned_weights.json")) as f:
            return json.load(f)["tuned_weights" if version == "tuned" else "literature_weights"]
    raise ValueError(f"version must be 'tuned', 'gen0' or 'literature', not {version!r}")


def load_heuristic(name, version="tuned"):
    """Heuristic object ready for MinimaxAI(heuristic=...) or NegamaxAI(heuristic=...)."""
    weights = load_weights(name, version)       # checks name and version first
    return _CLASSES[name](weights)


def load_openings(kind="heldout"):
    """List of openings (each a list of 6 (row, col) moves from the standard start,
    Black first). kind: "heldout" (400, for the tournament) or "tuning" (600)."""
    with open(os.path.join(RESULTS, "openings.json")) as f:
        return json.load(f)[kind]


def start_position(opening):
    """(board, colour to move) after playing an opening. With 6 moves and no
    passes, Black (1) is to move."""
    board, cur = Board(), 1
    for r, c in opening:
        if not board.make_move(Player(cur), r, c):
            raise ValueError(f"illegal move {(r, c)} in opening")
        cur = -cur
    return board, cur
