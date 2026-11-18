# Changes in branch `heuristics-integration`

Base: `main` at commit `325d4e1` ("Update board.py", standard starting position).
Purpose: plug the evaluation heuristics (H0–H3) into `MinimaxAI`, fix the two problems that appear once a heuristic is plugged in, and speed up the search so that genetic-algorithm (GA) tuning and the experiments run in hours instead of days.

**The AI plays exactly the same moves as before** in every mode, except for C1–C4, which are deliberate (see the table). This was checked against the previous code; see [Verification](#verification).

Line numbers below refer to this branch ("new") and to `main` at `325d4e1` ("old").

---

## Summary

| ID | Change | Files and new lines | Changes which move is played? | Why |
|---|---|---|---|---|
| C1 | Heuristic plug-in (`heuristic=` argument) | `minimax.py` 36, 50, 83–86 | Only if a heuristic is passed | Lets H0–H3 (or any evaluation) be used without editing `MinimaxAI` |
| C2 | Finished games scored by the real disc count | `minimax.py` 90–95, 116 | Yes, once a heuristic is used | Otherwise a lost game can be scored as a win |
| C3 | Heuristic is told whose turn it is | `minimax.py` 83, 131 | Only for heuristics that use it (H3) | H3's parity feature needs the side to move |
| C4 | Moves always listed row by row | `board.py` 25–51, 89–92 | Only when moves tie on score | Makes tie-breaking fixed and reproducible |
| C5 | Cheap board copy instead of `copy.deepcopy` | `board.py` 54–73; `minimax.py` 144, 164, 203, 253 | No (speed only) | `deepcopy` was a major cost at every node |
| C6 | Moves applied inside the search without re-checking legality | same as C5 | No (speed only) | `make_move` regenerated all legal moves just to validate one |
| C7 | Opponent's moves generated only when needed | `minimax.py` 109–127 | No (speed only) | They were generated at every node but only needed when the side to move has no moves |
| C8 | Search works on plain lists and colour numbers | `minimax.py` 24–34, 105, 179, 227 | No (speed only) | Avoids creating `Board` and `Player` objects at every node |
| C9 | `Board.get_valid_moves` and `make_move` use the shared helpers | `board.py` 89–101 | No | One move generator for the whole project |
| C10 | Precomputed directions (`RAYS`) in `board.py` | `board.py` 7–22; `heuristics.py` 32–35 | No | Shared by the move generator and the heuristics |
| C11 | Removed stray `p1 = Player(1)` and its import | `board.py` (old lines 1, 95) | No | Unused object created on import |
| C12 | `last_score` recorded after each search | `minimax.py` 45, 222, 266 | No | Lets tests and experiments read the best score |
| — | New `heuristics.py` | whole file | — | H0–H3 |
| — | New `test_heuristics.py` | whole file | — | 24 tests, including C1–C3 |

**Unchanged:** `app.py`, `game.py`, `terminal_ui.py`, `baseline_ai.py`, `player.py`, `requirements.txt`, `README.md`. The public interface `MinimaxAI(...).find_best_move(board, player)` is unchanged, and all existing constructor arguments work as before.

---

## How to verify

```
python -m unittest test_heuristics -v
```

All 24 tests should pass (about 10 seconds). The `TestMinimaxIntegration` class checks C1–C3 directly.

---

## Behaviour changes (C1–C4)

### C1. Heuristic plug-in

**Where:** `minimax.py`
- line 36: `__init__(..., heuristic=None)`
- line 50: `self.heuristic = heuristic`
- lines 83–86: `evaluate`

**Before** (old `minimax.py` lines 64–78): `evaluate(board, player)` always returned the disc difference. Using a different evaluation meant editing the class.

**After:**
```python
def evaluate(self, grid, colour, to_move=None):
    if self.heuristic is not None:
        return self.heuristic(grid, colour, to_move)
    return self.disc_difference(grid, colour)
```

**How to use:**
```python
from heuristics import H2
ai = MinimaxAI(depth=4, search_mode="fixed", heuristic=H2())
```

**Heuristic interface:** `h(grid, colour, to_move) -> number`
- `grid`: 8×8 list, `1` = Black, `-1` = White, `0` = empty.
- `colour`: the player to score for (`1` or `-1`). Higher must mean better for that player.
- `to_move`: the side to move in that position (`1` or `-1`).
- The heuristics in `heuristics.py` also accept a `Board` and a `Player` instead.
- Keep values well below 100000 in size (see C2).

`heuristic=None` (the default) behaves exactly as before.

### C2. Finished games are scored by the actual result

**Where:** `minimax.py` lines 114–123 (uses the new `disc_difference`, lines 90–95).

**Before** (old `minimax.py` line 96):
```python
# 1. Terminal state
if not moves and not opponent_moves:
    score = self.evaluate(board, ai_player)       # <- old line 96
    if score > 0:
        return 100000 + score                     # old line 99
    elif score < 0:
        return -100000 + score                    # old line 101
    return 0
```

**After** (new line 116):
```python
score = self.disc_difference(grid, ai_colour)
```

**Why:** when neither player can move, the game is over and the winner is known. The code adds ±100000 so a real win beats any estimate and a real loss is worse than any estimate. **The sign of `score` decides win or loss.** In the old code `score` came from `evaluate`. That was correct while `evaluate` *was* the disc count, but once `evaluate` returns a heuristic score, the heuristic decides who "won".

**Concrete failure** (this is `test_finished_game_scored_by_result_not_heuristic`):
- Full board: Black on all 28 edge squares, White on the 36 interior squares. Neither side can move, and **Black has lost 28–36**.
- H2 scores this position **+5187.5** for Black, because Black holds all corners and all stable discs.
- With only C1 applied, the search returns **+105187.5**, a certain win, and steers toward this lost game.
- With C2 it returns **−100008**, a loss by 8.

This was not a bug in the old code with its placeholder evaluation. It becomes one as soon as a heuristic is plugged in.

### C3. The heuristic is told whose turn it is

**Where:** `minimax.py` line 131.

**Before** (old line 120): `return self.evaluate(board, ai_player)`
**After:** `return self.evaluate(grid, ai_colour, colour)`

**Why:** leaves are always scored from the AI's point of view (`ai_colour`), and that is unchanged. But the heuristic was never told *whose turn it is* at the leaf. H3's parity feature needs it ("who makes the last move?"). Without it, H3 has to guess from the number of empty squares, assuming nobody has passed, and the guess is wrong for the rest of the game after any pass. `colour` is the side to move at that node. The pass case is handled before this line, so `colour` is always the side that is actually about to move. H0–H2 ignore this argument.

Checked by `test_side_to_move_reaches_heuristic`.

### C4. Moves are always listed in row-by-row order

**Where:** `board.py` lines 25–51 (`valid_moves_grid`) and lines 89–92 (`Board.get_valid_moves`).

**Before** (old `board.py` line 54): `return list(set(valid_moves))`. A Python set's order depends on how it stores the tuples, so the order was consistent but not row by row.

**After:** squares are scanned row by row and each legal square is added once, giving e.g. `[(2, 3), (3, 2), (4, 5), (5, 4)]` at the start.

**Why:** when two moves have the same score, the search keeps the first one it examined (`if score > best_score`). So the order of the move list decides ties. Move ordering sorts by `MOVE_ORDER_WEIGHTS` first; Python's sort keeps the existing order among equal weights, so ties are now broken by **table weight, then row, then column**. This is a fixed, easy-to-state rule, and it is needed for C5–C8 to give exactly the same moves.

---

## Speed-only changes (C5–C12)

These do not change any move, score or node count (see [Verification](#verification)).

### C5 + C6. Applying a move in the search

**Where:**
- the new function `apply_move_grid`, `board.py` lines 54–73;
- the four places it's used in `minimax.py`: lines 144, 164 (`minimax`), 203 (`fixed_depth_search`) and 253 (`iterative_deepening_search`).

**Before** (old `minimax.py` lines 133–134, 162–163, 211–212, 270–271):
```python
new_board = copy.deepcopy(board)
new_board.make_move(current_player, i, j)
```

**After:**
```python
new_grid = apply_move_grid(grid, colour, i, j)
```

**Why:**
- `copy.deepcopy` copies objects generically and is slow; `apply_move_grid` copies the 8 rows with `[row[:] for row in grid]` (C5).
- `make_move` first calls `get_valid_moves` again just to check that the move is legal. Inside the search the move always comes from the legal-move list, so the check is skipped (C6).
- **Only call `apply_move_grid` with a legal move.** Outside the search, keep using `Board.make_move`, which still checks.

### C7. Opponent's moves only when needed

**Where:** `minimax.py` lines 109–127.

**Before** (old lines 89–92):
```python
opponent = Player(-current_player.colour)
moves = board.get_valid_moves(current_player)
opponent_moves = board.get_valid_moves(opponent)
```
This generated both players' moves at every node.

**After:**
```python
moves = valid_moves_grid(grid, colour)
if not moves:
    if not valid_moves_grid(grid, -colour):
        ...finished game (C2)...
    ...pass...
```
The opponent's moves are only needed to tell "game over" from "pass", and only when the side to move has no moves. The order of the checks is the same as before: finished game, then pass, then depth limit.

### C8. Plain lists and colour numbers inside the search

**Where:** `minimax.py`
- the class docstring, lines 24–34;
- the signature of `minimax` (line 105): `minimax(self, grid, depth, colour, maximizing, ai_colour, alpha, beta)`;
- `fixed_depth_search` and `iterative_deepening_search` convert once at the start (lines 179 and 227): `grid, colour = board.board, player.colour`.

**Before:** `Board` and `Player` objects were passed down, and a new `Player` was created at every node (old lines 89, 205, 258).

**Note for anyone calling internal methods directly:** `minimax`, `evaluate` and `disc_difference` now take an 8×8 list and colour numbers (`1`/`-1`) instead of `Board` and `Player` objects. `find_best_move(board, player)` is unchanged, and it's the only method `app.py` and `game.py` use.

### C9. `Board` uses the same helpers

**Where:** `board.py` lines 89–101.
- `get_valid_moves` returns `valid_moves_grid(self.board, player.colour)`.
- `make_move` still returns `False` for an illegal move and changes nothing. For a legal move it applies `apply_move_grid` and copies the result **into the existing rows** (`self.board[r][:] = new[r]`), so any code holding a reference to `board.board` or one of its rows still sees the update.

Checked against the old `Board` on every square (legal and illegal) of 300 positions, for both colours.

### C10. Precomputed directions

**Where:** `board.py` lines 7–22 (`RAYS`); `heuristics.py` lines 32–35 imports it.

`RAYS[r][c]` lists, for each direction from square `(r, c)`, the squares in that direction, nearest first. It's computed once when the module loads, instead of stepping through coordinates and checking board bounds every time. Shared by the move generator and the mobility feature in `heuristics.py`.

### C11. Removed stray object

Old `board.py` line 95 created `p1 = Player(1)` at module level, which was unused; old line 1 imported `Player` only for that. Both removed; `board.py` now has no imports.

### C12. `last_score`

`minimax.py` line 45 (initialised), line 222 (set by `fixed_depth_search`), line 266 (set by `iterative_deepening_search` after each completed depth). This is the best root score of the last search. It's used by the tests and is useful for logging experiments.

---

## New files

### `heuristics.py`
Four evaluation functions, increasing in features and cost:

| Class | Features | Weights to tune |
|---|---|---|
| `H0` (line 402) | Disc difference only (baseline) | 0 |
| `H1` (line 413) | Static positional table + disc difference | 5 |
| `H2` (line 441) | Corners, X/C-squares (only while the corner is empty), discs, mobility, frontier, edge-walk stability | 7 |
| `H3` (line 474) | H2 with exact stability, plus move parity, with opening/endgame weights blended by game phase | 16 |

- All features are scored from the given player's point of view and scaled to −100…+100.
- `h(s, Black) == −h(s, White)` for every position.
- Weights are dicts with `to_vector()` / `from_vector()` for the GA.
- Defaults are the literature-based starting values, with two deliberate exceptions:
  - **H1's disc weight is 1.0 rather than 25,** so the disc term doesn't swamp the table.
  - **Stability uses linear scaling,** `100 × (my stable − their stable) / 64` (`_stable_score`, line 292), not the ratio form `100 × (M − T) / (M + T)` used for the other counts. Stable discs are few for most of the game, and the ratio scores 1 stable disc vs 0 the same as 30 vs 0 (+100). On 7,086 positions from H2 self-play, the ratio sat at exactly ±100 in 28% of positions just because one side had any stable discs. This is the same reason corners use linear scaling.
  - **Because of that, the stability weights were rescaled** from the literature's 25 so the average contribution stays the same: H2 25 → **150**; H3 opening 25 → **175** and endgame 25 → **85**. The two H3 weights were matched separately for each phase of its blend. The measured average contributions before and after are 755 vs 704 (H2) and 710 vs 668 (H3).

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

## Verification

The new `board.py` and `minimax.py` were compared with the previous version (`main` plus C1–C4 only, without the speedups) on **300 positions from random games**, at depth 3.

**Modes checked:** fixed and iterative search, each with:
- alpha-beta with move ordering;
- alpha-beta without move ordering;
- plain minimax (60 positions, since it's slower).

**Heuristics checked:** H0–H3 in every mode.

**Result:** the identical move, node count and (in fixed mode) score in every case.

Also checked:
- the default evaluation (`heuristic=None`) at depth 4;
- the timeout path in both modes;
- complete games against `GreedyAI` and `RandomAI`;
- `app.py`, `game.py` and `terminal_ui.py` compile and use only unchanged methods.

**Speed** (same positions, new vs previous): 8× faster with no heuristic or H0, 7× with H1, 3.5× with H2 and 2× with H3. Whole games at depth 4 on an Intel Core Ultra 7 155H, one core:

| | H1 | H2 | H3 |
|---|---|---|---|
| Before (s/game) | 3.84 | 5.30 | 6.15 |
| After (s/game) | 0.56 | 1.50 | 2.28 |

---

## Not in this branch (open decisions)

- **Greedy with the shared heuristic:** `GreedyAI` still maximizes raw disc count with random tie-breaks. For fair comparisons, greedy could be `MinimaxAI(depth=1, heuristic=h)`.
- **`requirements.txt`** is saved as UTF-16, which `pip` may fail to read on some systems. Not changed here.
