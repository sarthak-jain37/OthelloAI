
# OthelloAI

A Python implementation of the classic Othello (Reversi) board game.

## Features

- 8x8 Othello board
- Legal move generation in all eight directions
- Piece flipping according to Othello rules
- Turn management and forced passes
- Score tracking and winner determination
- Rich-powered terminal interface

## Tech Stack

- Python 3.10+
- Rich

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/sarthak-jain37/OthelloAI.git
cd OthelloAI
```

### 2. Create a virtual environment

Windows:

```bash
py -m venv .venv
.venv\Scripts\activate
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Run the game

```bash
python game.py
```

## Project Structure

```text
OthelloAI/
├── board.py
├── player.py
├── game.py
├── terminal_ui.py
├── requirements.txt
└── README.md
```

## Future Improvements

- Minimax AI
- Alpha-Beta pruning
- Heuristic board evaluation
- Human vs AI gameplay
- AI vs AI gameplay
