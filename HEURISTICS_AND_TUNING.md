# Heuristics, search fixes and tuned weights

Branch `heuristics-integration-v2`, based on `main` at commit `a43b12f` (the `core/`, `algorithms/`, `ui/` reorganisation).

This branch:
1. adds three evaluation heuristics (**H1, H2, H3**, plus a disc-count option **H0**) in `algorithms/heuristics.py`;
2. fixes two problems in `MinimaxAI` **and** `NegamaxAI` that appear as soon as a heuristic is plugged in;
3. makes the minimax search **2–8× faster without changing a single move**;
4. adds the **tuned weights** for H1–H3 (genetic algorithm), their validation, the scripts that produced them, and helpers for using them in the tournament.

Everything below gives the exact file and line, what changed, and why. Line numbers are for this branch ("new") and for `main` at `a43b12f` ("old").

**Quick check that everything works** (from the repository root):
```
python -m unittest tests.test_heuristics -v
```
All 27 tests should pass (about 20 seconds).

---

## Contents
1. [Files in this branch](#1-files-in-this-branch)
2. [Import order (existing issue on main)](#2-import-order-existing-issue-on-main)
3. [Code changes](#3-code-changes)
4. [The heuristics](#4-the-heuristics)
5. [How the weights were tuned](#5-how-the-weights-were-tuned)
6. [Results](#6-results)
7. [Using the heuristics in the tournament](#7-using-the-heuristics-in-the-tournament)
8. [Reproducing the results](#8-reproducing-the-results)
9. [What was verified](#9-what-was-verified)
10. [Caveats and open decisions](#10-caveats-and-open-decisions)

---

## 1. Files in this branch

| File | Status | What it is |
|---|---|---|
| `core/board.py` | changed | Shared move generator and move application; fixed move order (C4–C11) |
| `algorithms/minimax.py` | changed | Heuristic interface, the two fixes, faster search (C1–C3, C5–C8, C12–C13) |
| `algorithms/negamax.py` | changed | Heuristic interface and the two fixes only (C1–C3) |
| `algorithms/__init__.py` | changed | Also exports `H0`–`H3` (C14) |
| `algorithms/heuristics.py` | new | H0–H3 |
| `tests/__init__.py`, `tests/test_heuristics.py` | new | 27 tests |
| `tuning/tune.py` | new | Genetic algorithm that tuned the weights |
| `tuning/validate.py` | new | Validation on held-out openings |
| `tuning/weights.py` | new | Helpers: load tuned weights and openings |
| `tuning/results/` | new | All tuning and validation output (section 6) |
| `HEURISTICS_AND_TUNING.md` | new | This file |

Unchanged: `app.py`, `core/game.py`, `core/player.py`, `core/__init__.py`, `algorithms/baseline_ai.py`, `ui/`, `README.md`, `requirements.txt`, `.gitignore`. The way `app.py` and `core/game.py` create and use the AIs works exactly as before.

---

## 2. Import order (existing issue on main)

This exists on `main` already; this branch does not cause it or change it.

`core/__init__.py` imports `core.game`, which imports `algorithms.minimax`, which imports from `core`. So if **`algorithms` is imported before `core`**, Python hits a circular import:

```python
from algorithms.minimax import MinimaxAI      # fails on main too, if nothing from core was imported first
```

It works when `core` comes first, which is why `app.py` (it imports `core.board` first) is fine. All new code in this branch imports `core` first. When writing your own scripts, start with:

```python
import core                       # or: from core.board import Board
from algorithms import MinimaxAI, NegamaxAI, H2
```

**Suggested fix (not applied here, since it changes the reorganisation):** remove `from core.game import Game` (and `"Game"` from `__all__`) in `core/__init__.py`, and import it as `from core.game import Game` where needed.

---

## 3. Code changes

### Summary

| ID | Change | Where (new lines) | Changes which move is played? |
|---|---|---|---|
| C1 | Heuristics are called as `h(grid, colour, to_move)` | `minimax.py` 36, 50, 83–86; `negamax.py` 71–74 | Only when a heuristic is passed |
| C2 | Finished games scored by the actual disc count | `minimax.py` 90–95, 116; `negamax.py` 78, 111 | Yes, once a heuristic is used |
| C3 | Heuristic is told whose turn it is | `minimax.py` 131; `negamax.py` 140 | Only for heuristics that use it (H3) |
| C4 | Moves always listed row by row | `core/board.py` 25–51, 89–92 | Only when moves tie on score |
| C5 | Cheap board copy instead of `copy.deepcopy` | `core/board.py` 54–73; `minimax.py` 144, 164, 203, 253 | No (speed) |
| C6 | Moves applied in the search without re-checking legality | same as C5 | No (speed) |
| C7 | Opponent's moves generated only when needed | `minimax.py` 109–127 | No (speed) |
| C8 | Search works on plain lists and colour numbers | `minimax.py` 24–34, 105, 179, 227 | No (speed) |
| C9 | `Board` uses the shared helpers | `core/board.py` 89–101 | No |
| C10 | Precomputed directions (`RAYS`) | `core/board.py` 7–22; `heuristics.py` 35 | No |
| C11 | Removed stray `p1 = Player(1)` and its import | old `core/board.py` 1, 95 | No |
| C12 | `last_score` recorded after each search | `minimax.py` 45, 222, 266 | No |
| C13 | `should_order_moves` is a property again | `minimax.py` 56 | No |
| C14 | `H0`–`H3` exported from `algorithms` | `algorithms/__init__.py` | No |

C1–C3 are needed for the heuristics to work correctly. C4 makes tie-breaking reproducible. C5–C13 only make the minimax search faster or tidier; `NegamaxAI` got only C1–C3 (it uses `Board`'s methods, so C4 and C9 apply to it automatically).

### C1. Heuristic interface: `h(grid, colour, to_move)`

**Before:** `main` already had `heuristic=None` in both constructors (from the negamax merge), and both called `self.heuristic(board, player)` with `Board` and `Player` objects (old `minimax.py` 71, old `negamax.py` 71).

**After:** both call the heuristic the same way:

```python
h(grid, colour, to_move) -> number
```
- `grid`: the 8×8 list (`board.board`): `1` = Black, `-1` = White, `0` = empty;
- `colour`: the player to score for (`1` or `-1`); **higher must mean better for that player**;
- `to_move`: the colour of the side to move in that position (see C3).

`minimax.py` 83–86 (`evaluate`), `negamax.py` 71–74 (`evaluate`, which passes `board.board, player.colour, to_move`). The heuristics in `algorithms/heuristics.py` accept this form and also `(Board, Player)`. Any custom heuristic must accept the three arguments above. Keep values well below 100000 in size (see C2). `heuristic=None` (the default) gives the original disc-difference evaluation.

**Why plain lists:** the fast search (C8) has no `Board`/`Player` objects inside the tree; using the same form in negamax means one heuristic works with both.

### C2. Finished games are scored by the actual result

**Where:** `minimax.py` line 116 and `negamax.py` line 111 now call a new `disc_difference` method (`minimax.py` 90–95, `negamax.py` 78), which holds the old body of `evaluate`.

**Before** (old `minimax.py` 102–111, same in old `negamax.py` 102–111):
```python
# 1. Terminal state
if not moves and not opponent_moves:
    score = self.evaluate(board, ai_player)       # old line 104
    if score > 0:
        return 100000 + score
    elif score < 0:
        return -100000 + score
    return 0
```

**After:** `score = self.disc_difference(...)`.

**Why:** when neither player can move, the game is over and the winner is known. The code adds ±100000 so that a real win beats any estimate and a real loss is worse than any estimate. **The sign of `score` decides "win" or "loss".** While `evaluate` was the disc count, that was correct. Once `evaluate` returns a heuristic score, the heuristic decides who "won".

**Concrete failure** (tested in `tests/test_heuristics.py`, `test_finished_game_scored_by_result_not_heuristic`, for both classes):
- full board, Black on all 28 edge squares, White on the 36 interior squares: **Black has lost 28–36**;
- H2 scores this position **positive** for Black (all corners, all stable discs);
- without C2 the search returns more than +100000, a certain "win", and steers toward this lost game;
- with C2 it returns **−100008**, a loss by 8.

### C3. The heuristic is told whose turn it is

**Where:** `minimax.py` 131: `return self.evaluate(grid, ai_colour, colour)`; `negamax.py` 140: `return self.evaluate(board, current_player, current_player.colour)`.

**Before** (old `minimax.py` 128, old `negamax.py` 133): the heuristic was not told whose turn it was at the leaf.

**Why:** H3's parity feature ("who makes the last move?") needs it. Without it, H3 guesses from the number of empty squares assuming nobody has passed, and the guess is wrong for the rest of the game after any pass. The pass case is handled before these lines, so the colour passed is always the side actually about to move. H0–H2 ignore it.

In minimax every leaf is scored from the AI's point of view (`ai_colour`), unchanged. In negamax each leaf is scored from the side to move's point of view, unchanged, so there `colour == to_move`. Tested by `test_side_to_move_reaches_heuristic` (both classes).

### C4. Moves are always listed row by row

**Where:** `core/board.py` 25–51 (`valid_moves_grid`) and 89–92 (`Board.get_valid_moves`).

**Before** (old `core/board.py` 54): `return list(set(valid_moves))`. A Python set's order depends on how it stores the tuples: consistent, but not row by row.

**After:** squares are scanned row by row and each legal square is added once, e.g. `[(2, 3), (3, 2), (4, 5), (5, 4)]` at the start.

**Why:** when two moves have the same score, the search keeps the first one it examined (`if score > best_score`), so the list order decides ties. Move ordering sorts by `MOVE_ORDER_WEIGHTS` first; Python's sort keeps the existing order among equal weights. Ties are now broken by **table weight, then row, then column**: a fixed rule, and needed for C5–C8 to give exactly the same moves.

### C5 + C6. Applying a move in the search

**Where:** new function `apply_move_grid`, `core/board.py` 54–73; used in `minimax.py` 144, 164 (`minimax`), 203 (`fixed_depth_search`), 253 (`iterative_deepening_search`).

**Before** (old `minimax.py` 141–142, 170–171, 219–220, 278–279):
```python
new_board = copy.deepcopy(board)
new_board.make_move(current_player, i, j)
```
**After:**
```python
new_grid = apply_move_grid(grid, colour, i, j)
```
**Why:** `copy.deepcopy` is slow; `apply_move_grid` copies the 8 rows (C5). `make_move` first regenerates all legal moves just to check the move; inside the search the move always comes from the legal-move list, so the check is skipped (C6). **Only call `apply_move_grid` with a legal move**; elsewhere use `Board.make_move`, which still checks.

### C7. Opponent's moves only when needed

**Where:** `minimax.py` 109–127.

**Before** (old `minimax.py` 97–100): both players' moves were generated at every node.

**After:**
```python
moves = valid_moves_grid(grid, colour)
if not moves:
    if not valid_moves_grid(grid, -colour):
        ...finished game (C2)...
    ...pass...
```
The opponent's moves are only needed to tell "game over" from "pass", and only when the side to move has no moves. The order of checks is unchanged: finished game, pass, depth limit.

### C8. Plain lists and colour numbers inside the search

**Where:** `minimax.py` class docstring 24–34; `minimax(self, grid, depth, colour, maximizing, ai_colour, alpha, beta)` at 105; `fixed_depth_search` (179) and `iterative_deepening_search` (227) convert once: `grid, colour = board.board, player.colour`.

**Before:** `Board` and `Player` objects were passed down, and a new `Player` was created at every node (old `minimax.py` 97, 213, 266).

`find_best_move(board, player)` is unchanged and is the only method `app.py` and `core/game.py` use. If you call `MinimaxAI.minimax`, `evaluate` or `disc_difference` directly, they now take the 8×8 list and colour numbers.

### C9. `Board` uses the shared helpers

**Where:** `core/board.py` 89–101. `get_valid_moves` returns `valid_moves_grid(self.board, player.colour)`. `make_move` still returns `False` for an illegal move and changes nothing; for a legal move it applies `apply_move_grid` and copies the result **into the existing rows** (`self.board[r][:] = new[r]`), so code holding a reference to `board.board` still sees the update. Checked against the old `Board` on every square (legal and illegal) of 300 positions, both colours.

### C10. Precomputed directions

**Where:** `core/board.py` 7–22 (`RAYS`); `algorithms/heuristics.py` 35 imports it. `RAYS[r][c]` lists, for each direction from `(r, c)`, the squares in that direction, nearest first, computed once at import. Shared by the move generator and the heuristics' mobility feature.

### C11. Removed stray object

Old `core/board.py` line 95 created `p1 = Player(1)` at module level (unused), and line 1 imported `Player` only for it. Both removed; `core/board.py` has no imports.

### C12. `last_score`

`minimax.py` 45 (initialised), 222 (`fixed_depth_search`), 266 (`iterative_deepening_search`, after each completed depth): the best root score of the last search. Used by tests; useful for logging.

### C13. `should_order_moves`

`main` turned it into a plain attribute set in `__init__` (old `minimax.py` 41). Here it is a read-only property (`minimax.py` 56) with the same value (`use_pruning and use_move_ordering`). `core/game.py` reads it with `getattr`, which works the same. `negamax.py` keeps its attribute.

### C14. Package exports

`algorithms/__init__.py` also exports `H0, H1, H2, H3`.

---

## 4. The heuristics

`algorithms/heuristics.py`. Each heuristic is a callable object, built from a weight dict: `H2()` gives the literature starting weights, `H2(weights)` custom ones.

| Class | Features | Weights to tune |
|---|---|---|
| `H0` (line 402) | Disc difference only | 0 |
| `H1` (line 413) | Static positional table (5 square classes) + disc difference | 5 |
| `H2` (line 441) | Corners, X/C-squares (only while the corner is empty), discs, mobility, frontier, edge-walk stability | 7 |
| `H3` (line 474) | H2's features with exact stability, plus move parity; opening and endgame weight sets blended by how full the board is | 16 |

- Features are scored from the given player's point of view and scaled to −100…+100; `h(s, Black) == −h(s, White)`.
- Counts use the ratio `100 × (mine − theirs) / (mine + theirs)` (`ratio`, line 92), except corners, X/C-squares and stability, which use linear scaling.
- **Stability uses linear scaling** `100 × (my stable − their stable) / 64` (`_stable_score`, line 292), not the ratio form of the literature. Stable discs are few for most of the game, and the ratio scores 1 stable disc vs 0 the same as 30 vs 0 (+100). On 7,086 positions from H2 self-play the ratio sat at exactly ±100 in 28% of positions. The literature stability weight (25) was rescaled so the average contribution stays the same: H2 → 150; H3 opening → 175, endgame → 85.
- **H1's disc weight starts at 1.0, not 25**, so the disc term doesn't swamp the table.
- **H0** is included as an option; using it as a baseline is still to be agreed. It was not tuned.
- Weights are dicts with `to_vector()` / `from_vector()` for the genetic algorithm.

Evaluation cost per position: H0 2.9 µs, H1 5.3 µs (1.8×), H2 32 µs (11×), H3 99 µs (34×).

---

## 5. How the weights were tuned

`tuning/tune.py`, a genetic algorithm, each heuristic tuned separately with the same budget.

- **Search:** `MinimaxAI` with alpha-beta and move ordering, **fixed depth 4**. The weights are tuned for depth 4. Minimax and negamax make identical moves (section 9), so the weights apply to both.
- **Genome:** one gene per weight. One weight per heuristic is fixed to set the scale, because multiplying every weight by the same number plays identically: H1's corner square (100), H2's corner (30), H3's opening corner (30). Free genes: H1 5, H2 6, H3 15. Bounds keep every heuristic below 100000 in size.
- **Population 20, 20 generations, 40 games per individual per generation** (16,000 games per heuristic), starting from the literature weights plus 19 random variations.
- **Fitness:** score (wins + ½ draws) in 20 games against the literature weights and 20 against the previous generation's best. Every individual gets the same openings within a generation, new openings each generation; the whole population is re-evaluated every generation.
- **Evolution:** best 2 kept unchanged; parents chosen by tournaments of 3; blend crossover (probability 0.7); each gene mutated with probability 0.25, by a random amount shrinking from 10% to 3% of its range.
- **Final choice:** a playoff of the last generation's top 4 plus the last 3 champions, 200 games each against the literature weights. The winner is the tuned weight set.
- **Openings:** random 6-move openings from the standard start: **600 for tuning, 400 held out** (no position in both), in `tuning/results/openings.json`.
- **Machine:** Intel Core Ultra 7 155H, 14 worker processes, Windows 11, Python 3.13.15.
- **Tuning time:** H1 0.43 h, H2 1.27 h, H3 3.16 h (≈ 1 : 3 : 7.4).

The runs are reproducible: same settings and seed (2026) give the same results, checked on two machines.

---

## 6. Results

### Tuned weights (official)

`tuning/results/<H>/tuned_weights.json`, key `"tuned_weights"`. Rounded here; use the files (or `tuning/weights.py`) for full precision.

| Weight | H1 literature | **H1 tuned** |
|---|---|---|
| x (X-square value) | −50 | **−39.92** |
| c (C-square value) | −20 | **−9.18** |
| edge_base | 5 | **2.12** |
| interior_base | −1 | **−3.51** |
| disc | 1.0 | **0.84** |

H1's corner square value is fixed at 100.

| Weight | H2 literature | **H2 tuned** |
|---|---|---|
| corner | 30 (fixed) | **30** |
| x | 15 | **20.82** |
| c | 6 | **9.83** |
| disc | 25 | **15.54** |
| mobility | 5 | **27.64** |
| frontier | 10 | **22.90** |
| stability | 150 | **233.32** |

| Weight | H3 opening, literature | **H3 opening, tuned** | H3 endgame, literature | **H3 endgame, tuned** |
|---|---|---|---|---|
| corner | 30 (fixed) | **30** | 30 | **33.75** |
| x | 15 | **11.37** | 5 | **16.53** |
| c | 6 | **24.89** | 5 | **0.00** |
| disc | 5 | **2.30** | 30 | **18.38** |
| mobility | 5 | **23.09** | 5 | **17.83** |
| frontier | 10 | **11.79** | 5 | **16.83** |
| stability | 175 | **411.78** | 85 | **57.08** |
| parity | 0 | **3.51** | 10 | **18.12** |

What changed (trends consistent across the later generations):
- **H1:** edges valued less, interior squares penalised more, C-squares penalised less.
- **H2:** mobility and frontier raised strongly, disc count lowered, stability raised. This matches standard Othello strategy: mobility matters, grabbing discs early doesn't.
- **H3:** disc weight near 0 in the opening, mobility and stability up. H2's single disc weight (15.5) lies between H3's opening (2.3) and endgame (18.4) values: the compromise that H3's phase weights avoid.
- H3's parity weights and endgame C-square weight varied a lot between generations, so their values are uncertain.

### Validation on the held-out openings

`tuning/validate.py`: each match on all 400 held-out openings, each with both colours (800 games). Score = wins + ½ draws for the first-named player; ± is a 95% confidence interval.

| | tuned vs literature | gen-0 best vs literature | tuned vs gen-0 best |
|---|---|---|---|
| H1 | **85.2% ± 2.4** | 77.5% ± 2.8 | **44.1% ± 3.4** |
| H2 | **87.5% ± 2.3** | 85.1% ± 2.3 | **65.6% ± 3.2** |
| H3 | **83.1% ± 2.6** | 75.2% ± 3.0 | **78.4% ± 2.6** |

"Gen-0 best" = the best individual of the GA's first generation (a random variation of the literature weights).

- **Tuning generalises:** each tuned heuristic beats its literature version 83–88% of the time on openings it never saw. (The playoff scores on tuning openings were 89%; the drop is expected.)
- **These numbers do not compare H1, H2 and H3 with each other.** Each was compared only with its own literature version. Comparing heuristics is the tournament's job.
- **H2 and H3:** the later generations clearly improved on the first generation's best; H3 gained the most, as expected with the most weights.

### The two H1 versions

H1 shows a **non-transitive** result: tuned H1 beats the literature weights more often than the gen-0 best does (85.2% vs 77.5%), **but loses to the gen-0 best head-to-head** (44.1%). So neither is clearly "the best H1": it depends on the opponent. The likely reason is the fitness design: the GA only measured play against the literature weights and its own previous champions, so it can specialise against those opponents.

| Weight | H1 tuned (official) | H1 gen-0 best (alternative) |
|---|---|---|
| x | −39.92 | −42.37 |
| c | −9.18 | −5.44 |
| edge_base | 2.12 | 9.67 |
| interior_base | −3.51 | −8.78 |
| disc | 0.84 | 0.31 |

- **Tuned H1 is the official H1**, chosen by the rule fixed before tuning (the playoff winner).
- **The gen-0 best is provided as a documented alternative**, in `tuning/results/H1/gen0_best_weights.json`. It values edges much more and penalises the interior more.
- **Suggested use:** the main tournament uses tuned H1; if wanted, run the gen-0 H1 as one extra, clearly labelled check. Choosing between them *after* seeing tournament results would be selection on results; if both are run, report both.
- For completeness, `gen0_best_weights.json` also exists for H2 and H3, but their tuned versions clearly beat them, so use the tuned ones.

---

## 7. Using the heuristics in the tournament

### Loading weights and openings

`tuning/weights.py` does the file reading:

```python
import core                                        # must come before algorithms (section 2)
from algorithms import MinimaxAI, NegamaxAI
from tuning.weights import load_heuristic, load_openings, start_position

h1 = load_heuristic("H1")                          # tuned (official)
h1_alt = load_heuristic("H1", version="gen0")      # gen-0 best (alternative)
h2_lit = load_heuristic("H2", version="literature")# starting weights, if ever needed

ai = MinimaxAI(depth=4, search_mode="fixed", time_limit=1e9, heuristic=load_heuristic("H2"))
greedy = MinimaxAI(depth=1, search_mode="fixed", time_limit=1e9, heuristic=load_heuristic("H3"))

for opening in load_openings():                    # the 400 held-out openings
    board, to_move = start_position(opening)       # Black (1) to move after 6 moves
    ...
```

`load_heuristic` returns an object usable with both `MinimaxAI` and `NegamaxAI`. The `tournament` branch's `HEURISTICS` list (`("H1", None)`, ...) can be filled with `("H1", load_heuristic("H1"))`, etc. Note that branch still uses the old flat file layout.

### Conditions for a fair comparison

1. **Use the held-out openings only** (`load_openings()`). The tuning openings shaped the weights and would favour them.
2. **Play every opening twice, swapping colours.** The AIs are deterministic; without varied openings and colour swaps two players replay the same game.
3. **Enough games per pairing:** about 400 games gives roughly ±5 percentage points; 50 games only ±14.
4. **Same depth (or same time per move) for everyone.** The weights were tuned at depth 4.
5. **Greedy with the same heuristics:** `MinimaxAI(depth=1, heuristic=h)` is greedy with heuristic `h`. `GreedyAI` only counts discs (and breaks ties randomly).
6. **Minimax vs alpha-beta vs negamax:** at the same depth they reach the same scores (and here even the same moves), so compare them on **nodes evaluated** (`ai.nodes_evaluated`) and **time per move**, not on wins.
7. **Fixed-depth matches:** `search_mode="fixed"` with a very large `time_limit` (e.g. `1e9`), so a timeout never changes a move. Fixed-time matches use `search_mode="iterative"`, where search speed decides the depth reached.
8. **Log per game:** opening index, colours, algorithm and heuristic of each side, depth, result, disc margin, nodes and time per move.

**Speed note:** `MinimaxAI` has the faster search (C5–C8); `NegamaxAI` still uses `copy.deepcopy`, so it is several times slower at the same depth while making the same moves. This matters for fixed-time comparisons and for node/time comparisons between them. The speed difference comes from the implementation, not the algorithm.

---

## 8. Reproducing the results

From the repository root:

```
python -m tuning.tune --heuristic H1 --quick       # 1-minute check that everything runs
python -m tuning.tune --heuristic H1               # then H2, H3: about 5 h in total with 14 workers
python -m tuning.validate                          # about 40 min
```

- `--workers N` sets the number of parallel processes (default 14; best on the 22-thread laptop used).
- `--resume` continues a stopped run.
- Outputs go to `tuning/results/`; `--quick` runs go to `tuning/results/quick/`. Don't commit that folder (it's only a test run); delete it after checking.
- A new full run refuses to overwrite existing results: delete or move `tuning/results/<H>/` first.

`tune.py` and `validate.py` are the scripts that produced the results, with only their import lines, default output folder and usage text changed for the new layout. The search and heuristic code is the code the GA ran, with only the import lines changed.

### Files in `tuning/results/`

| File | Contents |
|---|---|
| `openings.json` | 600 tuning + 400 held-out openings (moves from the standard start, Black first, `(row, col)`) |
| `<H>/tuned_weights.json` | Tuned and literature weights, playoff table, settings, run time |
| `<H>/gen0_best_weights.json` | Best individual of generation 0, with validation numbers and a note |
| `<H>/generations.csv` | One row per generation: best/mean/median fitness, scores vs literature and vs champion, best weights (for convergence plots) |
| `<H>/individuals.csv` | Every individual of every generation: fitness, scores, weights |
| `<H>/log.txt` | Printed output of the tuning run |
| `<H>/checkpoint.json` | Final GA state |
| `validation.json` | The validation table |
| `validation_games.csv` | Every validation game (heuristic, match, opening, colour, score, disc margin) |

---

## 9. What was verified

- **Unit tests:** 27 tests in `tests/test_heuristics.py`, all passing:
  - the opening position;
  - move generation against `Board`;
  - corners and X/C-squares;
  - stability: no disc marked stable is ever flipped later, over 500 random games;
  - linear stability scaling;
  - parity and phase;
  - the weight interface;
  - the zero-sum property;
  - C2 and C3 for both `MinimaxAI` and `NegamaxAI`;
  - negamax = minimax.
- **This branch vs the code the GA ran:** 996 of 996 searches with the tuned weights (depth 3, all pruning modes) gave the identical move, score and node count.
- **Replays:** 36 sampled validation games replayed on this branch's code gave identical results and disc margins.
- **Negamax vs minimax:** 516 of 516 searches with the tuned H1–H3 (depth 3, fixed and iterative, all pruning modes) gave the same move and node count.
- **Speed version vs original search:** identical moves, scores and node counts on 300 positions in every search mode.
- **Results files:**
  - all three runs are complete;
  - summaries match the detailed files;
  - all validation percentages recompute exactly from the 7,200 games;
  - the openings are legal and distinct, with no overlap, and `tune.py` regenerates them exactly.
- **Windows-style worker processes:** the tuning and validation scripts run with workers started the way Windows starts them.
- **Existing code:**
  - full games through the existing interfaces work (minimax with heuristics, negamax, greedy, random, iterative mode);
  - every board and AI attribute `app.py` uses exists;
  - all files compile.

---

## 10. Caveats and open decisions

- **Depth:** the weights were tuned at depth 4; at other depths (and for greedy at depth 1) they are not necessarily optimal.
- **Fitness design:** the H1 non-transitivity (section 6) is a limitation of measuring fitness only against the literature weights and the GA's own champions. A broader opponent pool would reduce it.
- **H3:** has 15 free weights on the same budget as the others; some (parity, endgame C-square) are not well determined.
- **Stability formula** differs from the literature (section 4); this should be stated in the report.
- **Import order:** the existing circular import on `main` (section 2).
- **H0 as a baseline:** still to be agreed.
- **Greedy:** whether the tournament's greedy is `MinimaxAI(depth=1, heuristic=h)` or the disc-count `GreedyAI` (or both).
- **`requirements.txt`** is saved as UTF-16, which `pip` may fail to read on some systems.
