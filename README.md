# OthelloAI

A feature-rich, high-performance Python implementation of the classic **Othello (Reversi)** board game with adversarial game-playing AI agents, including **Minimax**, **Alpha-Beta Pruning**, **Move Ordering**, and baseline opponents.

---

## Features

- **Standard 8x8 Othello Rules**:
  - Legal move generation across all 8 directions.
  - Directional disc flipping with outflank detection.
  - Automatic turn switching, forced pass handling, and game-over detection.
- **Multiple Game Modes**:
  - Human vs. AI
  - AI vs. AI (benchmarking and performance comparison)
  - Human vs. Human
- **Rich Terminal Interface**:
  - Powered by [Rich](https://github.com/Textualize/rich) with formatted game boards, active turn indicators, legal move highlights (`✦`), and live scoreboards.
  - Matrix view option for simplified logging.
- **Multiple AI Algorithms**:
  - **Random AI**: Uniform random legal move selection.
  - **Greedy AI**: 1-ply lookahead maximizing immediate token count.
  - **Minimax AI**: Full zero-sum game tree search with terminal state evaluation.
  - **Alpha-Beta Pruning**: Eliminates suboptimal subtrees, drastically reducing node evaluations.
  - **Move Ordering**: Positional weight heuristics prioritizing corners and edges, maximizing Alpha-Beta cutoffs towards $\mathcal{O}(b^{d/2})$.
- **Advanced Search Controls**:
  - **Fixed-Depth Search**: Exhaustive evaluation to a specified depth.
  - **Iterative Deepening Search**: Progressive deepening ($d = 1, 2, 3, \dots$) with real-time timeout protection and fallback moves.

---

## AI Algorithms & Search Strategies

### 1. Baseline Agents
- **RandomAI** (`baseline_ai.py`): Selects randomly among available legal moves. Useful as a baseline.
- **GreedyAI** (`baseline_ai.py`): Simulates each legal move and plays the one that maximizes immediate piece differential.

### 2. Minimax & Alpha-Beta Pruning
Implemented in `minimax.py`:
- **Minimax**: Evaluates recursive outcomes assuming both players make optimal decisions.
- **Alpha-Beta Pruning**: Dynamically tracks search bounds ($\alpha$ and $\beta$) to prune branches that cannot influence the final decision.
- **Pass Handling**: Consecutive turns due to forced passes are handled correctly without consuming search depth.
- **Terminal State Evaluation**: Endgames award $\pm 100,000$ points for guaranteed wins/losses, prioritizing decisive victory over short-term disc counts.

### 3. Move Ordering Optimization
Alpha-Beta pruning performs best when the strongest moves are evaluated first. Using the **Positional Weight Table**, candidate moves are ordered prior to subtree evaluation:

```
[ +100,  -20,   10,    5,    5,   10,  -20,  +100 ]
[  -20,  -50,   -2,   -2,   -2,   -2,  -50,   -20 ]
[   10,   -2,   -1,   -1,   -1,   -1,   -2,    10 ]
[    5,   -2,   -1,    0,    0,   -1,   -2,     5 ]
[    5,   -2,   -1,    0,    0,   -1,   -2,     5 ]
[   10,   -2,   -1,   -1,   -1,   -1,   -2,    10 ]
[  -20,  -50,   -2,   -2,   -2,   -2,  -50,   -20 ]
[ +100,  -20,   10,    5,    5,   10,  -20,  +100 ]
```

- **Corners (`+100`)**: Captured corners can never be flipped and serve as permanent anchors.
- **Safe Edges (`+10`, `+5`)**: High stability, limited attack angles.
- **Center Squares (`0`, `-1`)**: Safe opening/midgame moves maintaining mobility.
- **C-Squares (`-20`) & X-Squares (`-50`)**: Squares adjacent to open corners; heavily deprioritized to avoid conceding corners.

Move ordering is guarded by `use_move_ordering` and automatically activates only when Alpha-Beta pruning is enabled (`use_pruning=True`).

---

## Tech Stack

- **Python 3.10+**
- **Rich**: Terminal formatting and rendering

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/sarthak-jain37/OthelloAI.git
cd OthelloAI
```

### 2. Create and Activate a Virtual Environment

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```bash
py -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Game

**Option A: Interactive Streamlit Web UI (Recommended)**
```bash
streamlit run app.py
```

**Option B: Terminal Interface**
```bash
python game.py
```

---

## Configuring Matches

You can configure matchups inside `game.py`:

```python
from game import Game
from minimax import MinimaxAI
from baseline_ai import GreedyAI, RandomAI

# Example 1: Alpha-Beta with Move Ordering (Black) vs. GreedyAI (White)
game = Game(
    algorithm1=MinimaxAI(depth=10, search_mode="iterative", time_limit=2, use_pruning=True, use_move_ordering=True),
    algorithm2=GreedyAI(),
    display_mode="pretty"
)
game.game_loop()

# Example 2: Human (Black) vs. Minimax AI (White)
# (Pass None for algorithm1 to play as human)
game = Game(
    algorithm1=None,
    algorithm2=MinimaxAI(depth=6, search_mode="fixed", use_pruning=True, use_move_ordering=True),
    display_mode="pretty"
)
game.game_loop()
```

---

## Project Structure

```text
OthelloAI/
├── algorithms/                 # Adversarial Search & Heuristic Evaluation Engines
│   ├── baseline_ai.py          # Baseline AI implementations (RandomAI, GreedyAI)
│   ├── heuristics.py           # Evaluation functions (H0 Disc Diff, H1 Positional Table, H2 CMAC, H3 9-feature)
│   ├── minimax.py              # Minimax, Alpha-Beta pruning, Move Ordering & Iterative Deepening
│   └── negamax.py              # Zero-sum Negamax search engine with symmetric evaluation
├── core/                       # Core Game Rules & Domain Models
│   ├── board.py                # Board state, legal move validation, raycasting & disc flipping
│   ├── game.py                 # Main game loop, turn coordinator, display manager & match runner
│   └── player.py               # Player model (tokens, color, bot flag, algorithm assignment)
├── ui/                         # Presentation Layer
│   └── terminal_ui.py          # Rich terminal board rendering & UI helpers
├── tournament_results/         # Generated tournament exports (CSV, JSON)
├── app.py                      # Interactive Streamlit Web UI (click-to-play board & visual controls)
├── tournament.py               # Two-stage parallel tournament runner with auto-checkpointing
├── tournament_state.json       # Resumable tournament checkpoint state
├── requirements.txt            # Python dependencies (streamlit, rich, etc.)
└── README.md                   # Project documentation
```

