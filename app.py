import time
import streamlit as st
from board import Board
from player import Player
from minimax import MinimaxAI
from baseline_ai import GreedyAI, RandomAI

st.set_page_config(
    page_title="Othello",
    page_icon="🟢",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Robust CSS injection using st.markdown(..., unsafe_allow_html=True)
st.markdown("""
<style>
    /* Dark app background matching Google Doodle theme */
    .stApp {
        background-color: #181a19 !important;
        color: #ffffff !important;
    }
    
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 560px !important;
    }
    
    /* Top Scoreboard Card */
    .score-card {
        max-width: 520px !important;
        margin: 0 auto 12px auto !important;
        background-color: #242625 !important;
        border-radius: 14px !important;
        padding: 20px 38px 16px 38px !important;
        display: flex !important;
        flex-wrap: wrap !important;
        justify-content: space-between !important;
        align-items: center !important;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4) !important;
    }
    
    .score-player {
        display: flex !important;
        align-items: center !important;
        gap: 16px !important;
    }
    
    .score-disc {
        width: 48px !important;
        height: 48px !important;
        border-radius: 50% !important;
        display: inline-block !important;
    }
    
    .score-disc.black {
        background: #191c1b !important;
        box-shadow: 0 3px 6px rgba(0, 0, 0, 0.5) !important;
        border: 1px solid #101211 !important;
    }
    
    .score-disc.white {
        background: #f5fdfc !important;
        box-shadow: 0 3px 6px rgba(0, 0, 0, 0.25) !important;
        border: 1px solid #d8e2de !important;
    }
    
    .score-number {
        color: #ffffff !important;
        font-size: 26px !important;
        font-weight: 700 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    
    .turn-pill-container {
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
        margin-top: 12px !important;
    }
    
    .turn-pill {
        background-color: #2b76ee !important;
        color: #ffffff !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        padding: 5px 16px !important;
        border-radius: 14px !important;
        display: inline-block !important;
        letter-spacing: 0.2px !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Othello Board Outer Container */
    div.st-key-board_container {
        max-width: 520px !important;
        margin: 0 auto !important;
        background-color: #009668 !important;
        border: 3px solid #00452f !important;
        border-radius: 4px !important;
        padding: 0px !important;
        position: relative !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5) !important;
    }
    
    /* Strip away all gaps and margins between rows and columns */
    div.st-key-board_container div[data-testid="stVerticalBlock"] {
        gap: 0px !important;
        padding: 0px !important;
        margin: 0px !important;
    }
    
    div.st-key-board_container div[data-testid="stHorizontalBlock"] {
        gap: 0px !important;
        padding: 0px !important;
        margin: 0px !important;
    }
    
    div.st-key-board_container div[data-testid="column"],
    div.st-key-board_container div[data-testid="stColumn"] {
        padding: 0px !important;
        margin: 0px !important;
        min-width: 0px !important;
        flex: 1 1 0px !important;
    }
    
    div.st-key-board_container .stButton {
        margin: 0px !important;
        padding: 0px !important;
        width: 100% !important;
        line-height: 0 !important;
    }
    
    /* Exact Square Buttons */
    div.st-key-board_container .stButton > button {
        width: 100% !important;
        aspect-ratio: 1 / 1 !important;
        height: auto !important;
        min-height: 56px !important;
        max-height: 64px !important;
        padding: 0px !important;
        margin: 0px !important;
        border-radius: 0px !important;
        background-color: #009668 !important;
        border: 1px solid #004d35 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: none !important;
        position: relative !important;
    }
    
    div.st-key-board_container .stButton > button:disabled {
        opacity: 1 !important;
        cursor: default !important;
        background-color: #009668 !important;
        border: 1px solid #004d35 !important;
    }
    
    /* Direct styling on the <p> DOM element inside the button for 100% cross-browser rendering */
    div.st-key-board_container button p {
        margin: 0 auto !important;
        padding: 0px !important;
        display: block !important;
        line-height: 0 !important;
    }
    
    /* 1. Black Coin: True 100% round geometric circle */
    div.st-key-board_container button[aria-label="black"] p,
    div.st-key-board_container div[class*="_black"] button p {
        font-size: 0px !important;
        width: 44px !important;
        height: 44px !important;
        border-radius: 50% !important;
        background: #191c1b !important;
        box-shadow: 0 3px 6px rgba(0, 0, 0, 0.45) !important;
        border: 1px solid #101211 !important;
        display: block !important;
    }
    
    /* 2. White Coin: True 100% round geometric circle */
    div.st-key-board_container button[aria-label="white"] p,
    div.st-key-board_container div[class*="_white"] button p {
        font-size: 0px !important;
        width: 44px !important;
        height: 44px !important;
        border-radius: 50% !important;
        background: #f5fdfc !important;
        box-shadow: 0 3px 6px rgba(0, 0, 0, 0.25) !important;
        border: 1px solid #d8e2de !important;
        display: block !important;
    }
    
    /* 3. Valid Move: Hollow ring matching Chess.com and Google Doodle */
    div.st-key-board_container button[aria-label="valid"],
    div.st-key-board_container div[class*="_valid"] button {
        cursor: pointer !important;
    }
    
    div.st-key-board_container button[aria-label="valid"] p,
    div.st-key-board_container div[class*="_valid"] button p {
        font-size: 0px !important;
        width: 40px !important;
        height: 40px !important;
        border-radius: 50% !important;
        border: 2.5px solid rgba(0, 55, 35, 0.75) !important;
        background: transparent !important;
        display: block !important;
        transition: transform 0.15s ease, border-color 0.15s ease, background-color 0.15s ease !important;
    }
    
    div.st-key-board_container button[aria-label="valid"]:hover p,
    div.st-key-board_container div[class*="_valid"] button:hover p {
        border-color: rgba(0, 25, 15, 0.95) !important;
        background-color: rgba(0, 0, 0, 0.08) !important;
        transform: scale(1.08) !important;
    }
    
    /* 4. Empty Square: completely clear */
    div.st-key-board_container button[aria-label="empty"] p,
    div.st-key-board_container div[class*="_empty"] button p {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)


def create_ai_agent(algorithm_name, depth, search_mode, time_limit):
    """Instantiate AI agent."""
    if algorithm_name == "Alpha-Beta + Move Ordering":
        return MinimaxAI(depth=depth, search_mode=search_mode, time_limit=time_limit, use_pruning=True, use_move_ordering=True)
    elif algorithm_name == "Alpha-Beta (No Move Ordering)":
        return MinimaxAI(depth=depth, search_mode=search_mode, time_limit=time_limit, use_pruning=True, use_move_ordering=False)
    elif algorithm_name == "Plain Minimax (No Pruning)":
        return MinimaxAI(depth=depth, search_mode=search_mode, time_limit=time_limit, use_pruning=False, use_move_ordering=False)
    elif algorithm_name == "Greedy AI":
        return GreedyAI()
    elif algorithm_name == "Random AI":
        return RandomAI()
    return None


def init_game():
    """Reset session game state."""
    st.session_state.board = Board()
    st.session_state.current_colour = 1  # Black moves first
    st.session_state.game_over = False
    st.session_state.history = []
    st.session_state.pass_message = None


if "board" not in st.session_state:
    init_game()


# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Game Options")

    game_mode = st.selectbox(
        "Game Mode",
        [
            "Human (Black) vs AI (White)",
            "AI (Black) vs Human (White)",
            "Human vs Human",
            "AI vs AI"
        ],
        index=0
    )

    ai_options = [
        "Alpha-Beta + Move Ordering",
        "Alpha-Beta (No Move Ordering)",
        "Plain Minimax (No Pruning)",
        "Greedy AI",
        "Random AI"
    ]

    black_is_bot = "AI (Black)" in game_mode or game_mode == "AI vs AI"
    black_agent = None
    if black_is_bot:
        st.subheader("⚫ Black AI Settings")
        b_algo = st.selectbox("Algorithm", ai_options, index=0, key="b_algo")
        b_depth = st.slider("Depth", 1, 10, 6, key="b_depth")
        b_mode = st.selectbox("Mode", ["iterative", "fixed"], index=0, key="b_mode")
        b_time = st.slider("Time Limit (s)", 1, 5, 2, key="b_time")
        black_agent = create_ai_agent(b_algo, b_depth, b_mode, b_time)

    white_is_bot = "AI (White)" in game_mode or game_mode == "AI vs AI"
    white_agent = None
    if white_is_bot:
        st.subheader("⚪ White AI Settings")
        w_algo = st.selectbox("Algorithm", ai_options, index=0, key="w_algo")
        w_depth = st.slider("Depth", 1, 10, 6, key="w_depth")
        w_mode = st.selectbox("Mode", ["iterative", "fixed"], index=0, key="w_mode")
        w_time = st.slider("Time Limit (s)", 1, 5, 2, key="w_time")
        white_agent = create_ai_agent(w_algo, w_depth, w_mode, w_time)

    st.markdown("---")
    if st.button("🔄 New Game", use_container_width=True):
        init_game()
        st.rerun()

    auto_step = False
    if game_mode == "AI vs AI":
        auto_step = st.checkbox("Auto-Play", value=True)
        step_delay = st.slider("Delay (s)", 0.1, 2.0, 0.5, step=0.1)


# Setup Players
player_black = Player(1, is_bot=black_is_bot, algorithm=black_agent)
player_white = Player(-1, is_bot=white_is_bot, algorithm=white_agent)

current_player = player_black if st.session_state.current_colour == 1 else player_white
opponent_player = player_white if st.session_state.current_colour == 1 else player_black

board = st.session_state.board
black_score = board.count_tokens(player_black)
white_score = board.count_tokens(player_white)

valid_moves = board.get_valid_moves(current_player)
opponent_valid_moves = board.get_valid_moves(opponent_player)

# Game status detection
if not valid_moves and not opponent_valid_moves:
    st.session_state.game_over = True
elif not valid_moves and not st.session_state.game_over:
    # Must pass
    colour_name = "Black" if current_player.colour == 1 else "White"
    st.session_state.pass_message = f"{colour_name} has no valid moves. Passing turn."
    st.session_state.current_colour = -st.session_state.current_colour
    st.rerun()
else:
    st.session_state.pass_message = None


# Determine Turn Pill Text
if st.session_state.game_over:
    if black_score > white_score:
        turn_text = "Black wins!"
    elif white_score > black_score:
        turn_text = "White wins!"
    else:
        turn_text = "It's a draw!"
elif not current_player.is_bot:
    turn_text = "Your turn"
else:
    turn_text = "AI thinking..."


# --- TOP SCORE CARD (Rendered via st.markdown for proper styling) ---
st.markdown(f"""
<div class="score-card">
    <div class="score-player">
        <div class="score-disc black"></div>
        <span class="score-number">{black_score}</span>
    </div>
    <div class="score-player">
        <div class="score-disc white"></div>
        <span class="score-number">{white_score}</span>
    </div>
    <div class="turn-pill-container">
        <span class="turn-pill">{turn_text}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# --- 8x8 BOARD WITH 4 HOSHI DOTS & VALID HOLLOW RINGS ---
board_matrix = board.board

with st.container(key="board_container"):
    # 4 Star Points (Hoshi dots) exactly on the intersections at 25% and 75%
    st.markdown("""
    <div style="position: absolute; width: 100%; height: 100%; top: 0; left: 0; pointer-events: none; z-index: 10;">
        <div style="position: absolute; top: 25%; left: 25%; width: 8px; height: 8px; background: #00281b; border-radius: 50%; transform: translate(-50%, -50%);"></div>
        <div style="position: absolute; top: 25%; left: 75%; width: 8px; height: 8px; background: #00281b; border-radius: 50%; transform: translate(-50%, -50%);"></div>
        <div style="position: absolute; top: 75%; left: 25%; width: 8px; height: 8px; background: #00281b; border-radius: 50%; transform: translate(-50%, -50%);"></div>
        <div style="position: absolute; top: 75%; left: 75%; width: 8px; height: 8px; background: #00281b; border-radius: 50%; transform: translate(-50%, -50%);"></div>
    </div>
    """, unsafe_allow_html=True)

    for r in range(8):
        cols = st.columns(8, gap=0)
        for c in range(8):
            cell_val = board_matrix[r][c]
            is_legal = (r, c) in valid_moves

            if cell_val == 1:
                label = "black"
                disabled = True
            elif cell_val == -1:
                label = "white"
                disabled = True
            elif is_legal and not current_player.is_bot and not st.session_state.game_over:
                label = "valid"
                disabled = False
            elif is_legal:
                label = "valid"
                disabled = True
            else:
                label = "empty"
                disabled = True

            button_key = f"c_{r}_{c}_{label}"

            with cols[c]:
                if st.button(label, key=button_key, disabled=disabled):
                    board.make_move(current_player, r, c)
                    st.session_state.history.append((current_player.colour, (r, c)))
                    st.session_state.current_colour = -current_player.colour
                    st.rerun()


# --- AI TURN HANDLING ---
if not st.session_state.game_over and current_player.is_bot:
    ai_can_step = True
    if game_mode == "AI vs AI" and not auto_step:
        ai_can_step = st.button("▶️ Step AI Move", use_container_width=True)

    if ai_can_step:
        time.sleep(0.15)
        move = current_player.algorithm.find_best_move(board, current_player)
        if move:
            r, c = move
            board.make_move(current_player, r, c)
            st.session_state.history.append((current_player.colour, move))
            st.session_state.current_colour = -current_player.colour
            if game_mode == "AI vs AI" and auto_step:
                time.sleep(step_delay)
            st.rerun()


# --- PASS NOTIFICATION & LOGS ---
if st.session_state.pass_message:
    st.toast(st.session_state.pass_message)

if st.session_state.game_over:
    st.balloons()

with st.expander("Move History"):
    if st.session_state.history:
        for i, (col, (mr, mc)) in enumerate(st.session_state.history, 1):
            p = "Black" if col == 1 else "White"
            st.write(f"{i}. {p}: row {mr}, col {mc}")
    else:
        st.write("No moves yet.")
