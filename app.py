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

# Custom CSS reproducing the exact Google Doodle Othello board and Chess.com valid move rings
st.markdown("""
<style>
    /* Dark app background matching the Doodle theme */
    .stApp {
        background-color: #191b1a;
        color: #ffffff;
    }
    
    /* Hide default header/footer padding */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 580px !important;
    }
    
    /* Top Scoreboard Card */
    .score-card {
        background-color: #242625;
        border-radius: 14px;
        padding: 22px 42px 18px 42px;
        margin-bottom: 14px;
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
    }
    
    .score-player {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    
    .score-disc {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        display: inline-block;
    }
    
    .score-disc.black {
        background: #181a19;
        box-shadow: 0 3px 6px rgba(0, 0, 0, 0.5);
    }
    
    .score-disc.white {
        background: #f4fdfb;
        box-shadow: 0 3px 6px rgba(0, 0, 0, 0.25);
    }
    
    .score-number {
        color: #ffffff;
        font-size: 26px;
        font-weight: 700;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .turn-pill-container {
        width: 100%;
        display: flex;
        justify-content: center;
        margin-top: 14px;
    }
    
    .turn-pill {
        background-color: #2b76ee;
        color: #ffffff;
        font-size: 13px;
        font-weight: 700;
        padding: 5px 16px;
        border-radius: 14px;
        display: inline-block;
        letter-spacing: 0.2px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
    }
    
    /* Board Outer Frame */
    .othello-board-wrapper {
        width: 100%;
        max-width: 540px;
        margin: 0 auto;
        background-color: #009668; /* Iconic Google Doodle green */
        border: 3px solid #00452f;
        border-radius: 4px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }
    
    /* Star Points (Hoshi dots) on the board intersections */
    .hoshi {
        width: 8px;
        height: 8px;
        background-color: #00281b;
        border-radius: 50%;
        position: absolute;
        transform: translate(-50%, -50%);
        z-index: 5;
        pointer-events: none;
    }
    
    /* Eliminate all column gaps */
    div[data-testid="stHorizontalBlock"] {
        gap: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    div[data-testid="column"] {
        padding: 0 !important;
        margin: 0 !important;
        min-width: 0 !important;
    }
    
    .stButton {
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
    }
    
    /* Square Buttons */
    .stButton > button {
        width: 100% !important;
        aspect-ratio: 1 / 1 !important;
        height: auto !important;
        min-height: 58px !important;
        padding: 0 !important;
        margin: 0 !important;
        border-radius: 0 !important;
        background-color: #009668 !important;
        border: 1px solid #004d35 !important;
        box-shadow: none !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        position: relative !important;
        transition: none !important;
    }
    
    /* Keep disabled squares fully visible and green */
    .stButton > button:disabled {
        opacity: 1 !important;
        cursor: default !important;
        background-color: #009668 !important;
        border: 1px solid #004d35 !important;
    }
    
    /* Hide button text */
    .stButton > button p {
        display: none !important;
    }
    
    /* Black Piece: Perfect round circular disc */
    button[aria-label="black"]::after {
        content: "" !important;
        width: 80% !important;
        height: 80% !important;
        border-radius: 50% !important;
        background: #181b19 !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.45) !important;
        display: block !important;
    }
    
    /* White Piece: Perfect round circular disc */
    button[aria-label="white"]::after {
        content: "" !important;
        width: 80% !important;
        height: 80% !important;
        border-radius: 50% !important;
        background: #f4fdfb !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.25) !important;
        display: block !important;
    }
    
    /* Valid Move: Hollow ring matching Chess.com and the Google Doodle image */
    button[aria-label="valid"] {
        cursor: pointer !important;
    }
    
    button[aria-label="valid"]::after {
        content: "" !important;
        width: 74% !important;
        height: 74% !important;
        border-radius: 50% !important;
        border: 2px solid rgba(0, 50, 35, 0.7) !important;
        background: transparent !important;
        display: block !important;
        transition: transform 0.15s ease, border-color 0.15s ease, background-color 0.15s ease !important;
    }
    
    button[aria-label="valid"]:hover::after {
        border-color: rgba(0, 30, 20, 0.95) !important;
        background-color: rgba(0, 0, 0, 0.08) !important;
        transform: scale(1.05) !important;
    }
    
    /* Empty squares */
    button[aria-label="empty"]::after {
        content: "" !important;
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)


def create_ai_agent(algorithm_name, depth, search_mode, time_limit):
    """Factory function for creating AI players."""
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
    """Initialize or reset session game state."""
    st.session_state.board = Board()
    st.session_state.current_colour = 1  # Black moves first
    st.session_state.game_over = False
    st.session_state.history = []
    st.session_state.pass_message = None


if "board" not in st.session_state:
    init_game()


# --- SIDEBAR CONTROLS ---
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


# Player instances
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
    algo_label = "AI thinking..."
    turn_text = algo_label


# --- RENDER TOP SCORE CARD (Matching the image exactly) ---
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


# --- RENDER 8x8 BOARD WITH HOSHI DOTS & VALID HOLLOW RINGS ---
board_matrix = board.board

st.markdown('<div class="othello-board-wrapper">', unsafe_allow_html=True)

# 4 Star Points (Hoshi dots) exactly as positioned in the image
st.markdown("""
<div class="hoshi" style="top: 25%; left: 25%;"></div>
<div class="hoshi" style="top: 25%; left: 75%;"></div>
<div class="hoshi" style="top: 75%; left: 25%;"></div>
<div class="hoshi" style="top: 75%; left: 75%;"></div>
""", unsafe_allow_html=True)

for r in range(8):
    cols = st.columns(8, gap=0)
    for c in range(8):
        cell_val = board_matrix[r][c]
        is_legal = (r, c) in valid_moves
        button_key = f"c_{r}_{c}"

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

        with cols[c]:
            if st.button(label, key=button_key, disabled=disabled):
                board.make_move(current_player, r, c)
                st.session_state.history.append((current_player.colour, (r, c)))
                st.session_state.current_colour = -current_player.colour
                st.rerun()

st.markdown('</div>', unsafe_allow_html=True)


# --- AI TURN HANDLING ---
if not st.session_state.game_over and current_player.is_bot:
    ai_can_step = True
    if game_mode == "AI vs AI" and not auto_step:
        ai_can_step = st.button("▶️ Step AI Move", use_container_width=True)

    if ai_can_step:
        time.sleep(0.15)  # Visual pause so human perceives turn transition
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
