import time
import streamlit as st
from board import Board
from player import Player
from minimax import MinimaxAI
from baseline_ai import GreedyAI, RandomAI

st.set_page_config(
    page_title="Othello AI Studio",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for classic Othello board look and responsive square buttons
st.markdown("""
<style>
    /* Main container styling */
    .main-title {
        text-align: center;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        text-align: center;
        color: #666;
        margin-bottom: 1rem;
    }
    
    /* Board styling */
    .othello-grid-wrapper {
        display: flex;
        justify-content: center;
        margin: 10px 0;
    }
    
    /* Button styles */
    div[data-testid="stHorizontalBlock"] {
        gap: 0.3rem !important;
        justify-content: center;
    }
    
    .stButton > button {
        width: 100% !important;
        height: 54px !important;
        font-size: 26px !important;
        line-height: 1 !important;
        padding: 0 !important;
        border-radius: 6px !important;
        background-color: #1e7039 !important;
        color: #ffffff !important;
        border: 2px solid #0f4520 !important;
        transition: all 0.15s ease-in-out !important;
    }
    
    .stButton > button:hover:not(:disabled) {
        background-color: #278d49 !important;
        border-color: #90ee90 !important;
        transform: scale(1.04);
        box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
    }
    
    .stButton > button:disabled {
        background-color: #185a2e !important;
        border-color: #0d3819 !important;
        opacity: 0.95 !important;
        color: #ffffff !important;
    }
    
    /* Turn badges */
    .turn-badge {
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 10px;
    }
    .turn-black {
        background-color: #111111;
        color: #ffffff;
        border: 2px solid #555555;
    }
    .turn-white {
        background-color: #f7f7f7;
        color: #111111;
        border: 2px solid #cccccc;
    }
</style>
""", unsafe_allow_html=True)


def create_ai_agent(algorithm_name, depth, search_mode, time_limit):
    """Instantiate the chosen AI agent."""
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


def init_game_state():
    """Reset or initialize the session game state."""
    st.session_state.board = Board()
    st.session_state.current_colour = 1  # Black always moves first
    st.session_state.game_over = False
    st.session_state.history = []
    st.session_state.last_move = None
    st.session_state.last_stats = None
    st.session_state.pass_message = None


# Initialize session state if missing
if "board" not in st.session_state:
    init_game_state()


# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Game Settings")

    game_mode = st.selectbox(
        "Game Mode",
        [
            "Human (Black) vs AI (White)",
            "AI (Black) vs Human (White)",
            "Human vs Human",
            "AI vs AI"
        ],
        index=0,
        help="Select whether you play against an AI, play with a friend locally, or watch two AIs duel."
    )

    ai_options = [
        "Alpha-Beta + Move Ordering",
        "Alpha-Beta (No Move Ordering)",
        "Plain Minimax (No Pruning)",
        "Greedy AI",
        "Random AI"
    ]

    # Configure Black player
    st.markdown("---")
    st.subheader("⚫ Black Player")
    black_is_bot = "AI (Black)" in game_mode or game_mode == "AI vs AI"
    black_agent = None
    if black_is_bot:
        black_algo = st.selectbox("Black AI Algorithm", ai_options, index=0, key="b_algo")
        black_depth = st.slider("Black Search Depth", 1, 10, 6, key="b_depth")
        black_mode = st.selectbox("Black Search Mode", ["iterative", "fixed"], index=0, key="b_mode")
        black_time = st.slider("Black Time Limit (s)", 1, 5, 2, key="b_time")
        black_agent = create_ai_agent(black_algo, black_depth, black_mode, black_time)
    else:
        st.write("Controlled by **Human**")

    # Configure White player
    st.markdown("---")
    st.subheader("⚪ White Player")
    white_is_bot = "AI (White)" in game_mode or game_mode == "AI vs AI"
    white_agent = None
    if white_is_bot:
        white_algo = st.selectbox("White AI Algorithm", ai_options, index=0, key="w_algo")
        white_depth = st.slider("White Search Depth", 1, 10, 6, key="w_depth")
        white_mode = st.selectbox("White Search Mode", ["iterative", "fixed"], index=0, key="w_mode")
        white_time = st.slider("White Time Limit (s)", 1, 5, 2, key="w_time")
        white_agent = create_ai_agent(white_algo, white_depth, white_mode, white_time)
    else:
        st.write("Controlled by **Human**")

    st.markdown("---")
    col_reset, col_auto = st.columns(2)
    with col_reset:
        if st.button("🔄 Reset Game", use_container_width=True):
            init_game_state()
            st.rerun()

    auto_step = False
    if game_mode == "AI vs AI":
        with col_auto:
            auto_step = st.checkbox("Auto-Play", value=False)
        step_delay = st.slider("Move Delay (s)", 0.1, 2.0, 0.5, step=0.1)


# Setup Players
player_black = Player(1, is_bot=black_is_bot, algorithm=black_agent)
player_white = Player(-1, is_bot=white_is_bot, algorithm=white_agent)

current_player = player_black if st.session_state.current_colour == 1 else player_white
opponent_player = player_white if st.session_state.current_colour == 1 else player_black

board = st.session_state.board
black_score = board.count_tokens(player_black)
white_score = board.count_tokens(player_white)


# Check for valid moves
valid_moves = board.get_valid_moves(current_player)
opponent_valid_moves = board.get_valid_moves(opponent_player)

# Handle Game Over or Forced Pass
if not valid_moves and not opponent_valid_moves:
    st.session_state.game_over = True
elif not valid_moves and not st.session_state.game_over:
    # Current player has no moves; must pass
    colour_name = "Black" if current_player.colour == 1 else "White"
    st.session_state.pass_message = f"**{colour_name}** has no legal moves. Passing turn!"
    st.session_state.current_colour = -st.session_state.current_colour
    st.rerun()
else:
    st.session_state.pass_message = None


# --- MAIN UI ---
st.markdown('<h1 class="main-title">🟢 Othello AI Studio</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Adversarial Tree Search with Minimax, Alpha-Beta Pruning & Positional Move Ordering</p>', unsafe_allow_html=True)

# Top Metric Banner
col1, col2, col3, col4 = st.columns([1.5, 1.5, 2.5, 2])

with col1:
    st.metric("⚫ Black Discs", black_score)

with col2:
    st.metric("⚪ White Discs", white_score)

with col3:
    if st.session_state.game_over:
        if black_score > white_score:
            st.success(f"🏆 Game Over: Black Wins ({black_score} - {white_score})!")
        elif white_score > black_score:
            st.success(f"🏆 Game Over: White Wins ({white_score} - {black_score})!")
        else:
            st.info("🤝 Game Over: It's a Draw!")
    else:
        turn_str = "⚫ Black's Turn" if current_player.colour == 1 else "⚪ White's Turn"
        controller_str = "(Human)" if not current_player.is_bot else f"({current_player.algorithm.__class__.__name__})"
        st.info(f"**Turn:** {turn_str} {controller_str}")

with col4:
    if st.session_state.last_move:
        r, c = st.session_state.last_move
        st.write(f"**Last Move:** Row {r}, Col {c}")
    if st.session_state.last_stats:
        st.caption(st.session_state.last_stats)

if st.session_state.pass_message:
    st.warning(st.session_state.pass_message)


# --- INTERACTIVE 8x8 BOARD ---
board_matrix = board.board
col_letters = ["A", "B", "C", "D", "E", "F", "G", "H"]

# Header Row with column letters
header_cols = st.columns([0.4] + [1] * 8 + [0.4])
for i, letter in enumerate(col_letters):
    header_cols[i + 1].markdown(f"<div style='text-align:center; font-weight:bold; color:#555;'>{letter}</div>", unsafe_allow_html=True)

for r in range(8):
    cols = st.columns([0.4] + [1] * 8 + [0.4])
    # Row Number Label (1-8)
    cols[0].markdown(f"<div style='text-align:center; padding-top:14px; font-weight:bold; color:#555;'>{r + 1}</div>", unsafe_allow_html=True)

    for c in range(8):
        cell_val = board_matrix[r][c]
        is_legal = (r, c) in valid_moves
        button_key = f"cell_{r}_{c}"

        # Determine icon and state
        if cell_val == 1:
            icon = "⚫"
            disabled = True
        elif cell_val == -1:
            icon = "⚪"
            disabled = True
        elif is_legal and not current_player.is_bot and not st.session_state.game_over:
            icon = "✦"
            disabled = False
        elif is_legal:
            icon = "·"
            disabled = True
        else:
            icon = ""
            disabled = True

        with cols[c + 1]:
            if st.button(icon, key=button_key, disabled=disabled, use_container_width=True):
                # Human player clicked a legal square
                board.make_move(current_player, r, c)
                st.session_state.history.append((current_player.colour, (r, c)))
                st.session_state.last_move = (r, c)
                st.session_state.last_stats = None
                st.session_state.current_colour = -current_player.colour
                st.rerun()

    cols[9].markdown("")


# --- AI MOVE EXECUTION ---
if not st.session_state.game_over and current_player.is_bot:
    ai_should_move = True

    if game_mode == "AI vs AI" and not auto_step:
        ai_should_move = st.button("▶️ Execute Next AI Move", type="primary", use_container_width=True)

    if ai_should_move:
        with st.spinner(f"🤖 {current_player.algorithm.__class__.__name__} is thinking..."):
            start_t = time.perf_counter()
            move = current_player.algorithm.find_best_move(board, current_player)
            elapsed = time.perf_counter() - start_t

            if move:
                r, c = move
                board.make_move(current_player, r, c)
                st.session_state.history.append((current_player.colour, move))
                st.session_state.last_move = move

                nodes = getattr(current_player.algorithm, "nodes_evaluated", "N/A")
                st.session_state.last_stats = f"Nodes: {nodes} | Time: {elapsed:.2f}s"
                st.session_state.current_colour = -current_player.colour

                if game_mode == "AI vs AI" and auto_step:
                    time.sleep(step_delay)

                st.rerun()


# --- GAME OVER CELEBRATION & STATS ---
if st.session_state.game_over:
    st.balloons()
    st.success("🏁 Game completed!")

with st.expander("📜 Move History & Game Log", expanded=False):
    if st.session_state.history:
        history_rows = []
        for i, (col, (mr, mc)) in enumerate(st.session_state.history, 1):
            p_name = "Black (⚫)" if col == 1 else "White (⚪)"
            notation = f"{col_letters[mc]}{mr + 1}"
            history_rows.append(f"**Turn {i}**: {p_name} played at `{notation}` (Row {mr}, Col {mc})")
        st.markdown("\n".join(history_rows))
    else:
        st.write("No moves played yet.")
