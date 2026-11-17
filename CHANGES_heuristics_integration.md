# Changes in branch `heuristics-integration`

Base: `main` at commit `325d4e1` ("Update board.py", standard starting position).
Purpose: plug the evaluation heuristics into `MinimaxAI`, and fix the two problems that appear once a heuristic is plugged in.

This version contains **only the necessary changes**. The search code is otherwise exactly as on `main`: it still uses `copy.deepcopy`, `Board` and `Player` objects. A faster version that makes exactly the same decisions exists and can be proposed separately.

Line numbers below refer to this branch ("new") and to `main` at `325d4e1` ("old").

---

## Summary

| ID | Change | Files and new lines | Changes which move is played? | Why |
|---|---|---|---|---|
| C1 | Heuristic plug-in (`heuristic=` argument) | `minimax.py` 27, 38, 69–72 | Only if a heuristic is passed | Lets the heuristics (or any evaluation) be used without editing `MinimaxAI` |
| C2 | Finished games scored by the real disc count | `minimax.py` 76–89, 109 | Yes, once a heuristic is used | Otherwise a lost game can be scored as a win |
| C3 | Heuristic is told whose turn it is | `minimax.py` 69, 133 | Only for heuristics that use it (H3) | H3's parity feature needs the side to move |
| C4 | Moves always listed row by row | `board.py` 52–54 | Only when moves tie on score | Makes tie-breaking fixed and reproducible |
| C5 | Removed stray `p1 = Player(1)` and its import | `board.py` (old lines 1, 95) | No | Unused object created on import |
| C6 | `last_score` recorded after each fixed-depth search | `minimax.py` 35, 252 | No | Lets tests and experiments read the best score |
| — | New `heuristics.py` | whole file | — | H0–H3 |
| — | New `test_heuristics.py` | whole file | — | 24 tests, including C1–C3 |

**Unchanged:** `app.py`, `game.py`, `terminal_ui.py`, `baseline_ai.py`, `player.py`, `requirements.txt`, `README.md`. All existing constructor arguments and `find_best_move(board, player)` work as before.

**H0** (disc difference) is included in `heuristics.py` as an option; using it as a baseline is still to be agreed.

---

## How to verify

```
python -m unittest test_heuristics -v
```

All 24 tests should pass. The `TestMinimaxIntegration` class (line 251) checks C1–C3 directly.

---

## C1. Heuristic plug-in

**Where:** `minimax.py`
- line 27: `__init__(..., heuristic=None)`
- line 38: `self.heuristic = heuristic`
- lines 69–72: `evaluate`

**Before** (old `minimax.py` line 64): `evaluate(board, player)` always returned the disc difference. Using a different evaluation meant editing the class.

**After:**
```python
def evaluate(self, board, player, to_move=None):
    if self.heuristic is not None:
        return self.heuristic(board, player, to_move)
    return self.disc_difference(board, player)
```

**How to use:**
```python
from heuristics import H2
ai = MinimaxAI(depth=4, search_mode="fixed", heuristic=H2())
```

**Heuristic interface:** `h(board, player, to_move) -> number`
- `board`: a `Board`.
- `player`: the `Player` to score for. Higher must mean better for that player.
- `to_move`: the colour (`1` or `-1`) of the side to move in that position.
- Keep values well below 100000 in size (see C2).

`heuristic=None` (the default) behaves exactly as before.

## C2. Finished games are scored by the actual result

**Where:** `minimax.py` line 109 (uses the new `disc_difference`, lines 76–89, which is the old body of `evaluate`).

**Before** (old `minimax.py` lines 94–103):
```python
# 1. Terminal state
if not moves and not opponent_moves:
    score = self.evaluate(board, ai_player)       # <- old line 96
    if score > 0:
        return 100000 + score
    elif score < 0:
        return -100000 + score
    return 0
```

**After** (new line 109):
```python
score = self.disc_difference(board, ai_player)
```

**Why:** when neither player can move, the game is over and the winner is known. The code adds ±100000 so a real win beats any estimate and a real loss is worse than any estimate. **The sign of `score` decides win or loss.** In the old code `score` came from `evaluate`. That was correct while `evaluate` *was* the disc count, but once `evaluate` returns a heuristic score, the heuristic decides who "won".

**Concrete failure** (this is `test_finished_game_scored_by_result_not_heuristic`):
- Full board: Black on all 28 edge squares, White on the 36 interior squares. Neither side can move, and **Black has lost 28–36**.
- H2 scores this position **positive** for Black, because Black holds all corners and all stable discs.
- With only C1 applied, the search would return more than +100000, a certain win, and steer toward this lost game.
- With C2 it returns **−100008**, a loss by 8.

This was not a bug in the old code with its placeholder evaluation. It becomes one as soon as a heuristic is plugged in.

## C3. The heuristic is told whose turn it is

**Where:** `minimax.py` line 133.

**Before** (old line 120): `return self.evaluate(board, ai_player)`
**After:** `return self.evaluate(board, ai_player, current_player.colour)`

**Why:** leaves are always scored from the AI's point of view (`ai_player`), and that is unchanged. But the heuristic was never told *whose turn it is* at the leaf. H3's parity feature needs it ("who makes the last move?"). Without it, H3 has to guess from the number of empty squares, assuming nobody has passed, and the guess is wrong for the rest of the game after any pass. `current_player` is the side to move at that node. The pass case is handled before this line, so it is always the side that is actually about to move. H0–H2 ignore this argument.

Checked by `test_side_to_move_reaches_heuristic`.

## C4. Moves are always listed in row-by-row order

**Where:** `board.py` line 54 (comment on lines 52–53).

**Before** (old `board.py` line 54): `return list(set(valid_moves))`. A Python set's order depends on how it stores the tuples, so the order was consistent but not row by row.
**After:** `return sorted(set(valid_moves))`, e.g. `[(2, 3), (3, 2), (4, 5), (5, 4)]` at the start.

**Why:** when two moves have the same score, the search keeps the first one it examined (`if score > best_score`). So the order of the move list decides ties. Move ordering sorts by `MOVE_ORDER_WEIGHTS` first; Python's sort keeps the existing order among equal weights, so ties are now broken by **table weight, then row, then column**. This is a fixed, easy-to-state rule, and it lets a faster implementation be checked to give exactly the same moves.

## C5. Removed stray object

Old `board.py` line 95 created `p1 = Player(1)` at module level, which was unused; old line 1 imported `Player` only for that. Both removed.

## C6. `last_score`

`minimax.py` line 35 (initialised) and line 252 (set at the end of `fixed_depth_search`). This is the best root score of the last search. It's used by the tests and is useful for logging experiments.

---

## New files

### `heuristics.py`

| Class | Features | Weights to tune |
|---|---|---|
| `H0` (line 414) | Disc difference only (option; baseline use to be agreed) | 0 |
| `H1` (line 425) | Static positional table + disc difference | 5 |
| `H2` (line 453) | Corners, X/C-squares (only while the corner is empty), discs, mobility, frontier, edge-walk stability | 7 |
| `H3` (line 486) | H2 with exact stability, plus move parity, with opening/endgame weights blended by game phase | 16 |

- All features are scored from the given player's point of view and scaled to −100…+100.
- `h(s, Black) == −h(s, White)` for every position.
- Weights are dicts with `to_vector()` / `from_vector()` for the genetic algorithm.
- Defaults are the literature-based starting values, with two deliberate exceptions:
  - **H1's disc weight is 1.0 rather than 25,** so the disc term doesn't swamp the table.
  - **Stability uses linear scaling,** `100 × (my stable − their stable) / 64` (`_stable_score`, line 304), not the ratio form `100 × (M − T) / (M + T)` used for the other counts. Stable discs are few for most of the game, and the ratio scores 1 stable disc vs 0 the same as 30 vs 0 (+100). On 7,086 positions from H2 self-play, the ratio sat at exactly ±100 in 28% of positions just because one side had any stable discs. This is the same reason corners use linear scaling.
  - **Because of that, the stability weights were rescaled** from the literature's 25 so the average contribution stays the same: H2 25 → **150**; H3 opening 25 → **175** and endgame 25 → **85**. The two H3 weights were matched separately for each phase of its blend.

### `test_heuristics.py`
24 tests:
- opening position;
- move generation against `Board`;
- corners and X/C-squares;
- stability: soundness over 500 random games, checking that no disc marked stable is ever flipped later, plus the linear scaling;
- parity and phase;
- the weight-vector interface and zero-sum property;
- `TestMinimaxIntegration` (line 251) for C1–C3.

---

## Not in this branch (open decisions)

- **Search speedups:** a faster version of the search, with the same decisions (identical move, score and node count, checked on 300 positions in every search mode), runs 2–8× faster. It's needed for GA tuning, and helps the experiments. It can be proposed as a separate change.
- **Greedy with the shared heuristic:** `GreedyAI` still maximizes raw disc count with random tie-breaks. For fair comparisons, greedy could be `MinimaxAI(depth=1, heuristic=h)`.
- **`requirements.txt`** is saved as UTF-16, which `pip` may fail to read on some systems.
