# Terminal UI for Othello without third-party dependencies (no rich required)

def display_board(board, valid_moves, current_player, black_score, white_score):
    # ANSI Escape codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    DIM_GREEN = "\033[2;32m"
    WHITE = "\033[97m"
    BLACK_PIECE = "\033[90m●\033[0m"
    WHITE_PIECE = "\033[97m●\033[0m"

    print("\n" + "=" * 45)
    print(f"{BOLD}{CYAN}             O T H E L L O{RESET}")
    print("=" * 45)
    print(f"      {BOLD}BLACK:{RESET} {black_score}    |    {BOLD}WHITE:{RESET} {white_score}")
    print("-" * 45)

    # Column headers
    header = "    " + "   ".join(str(j) for j in range(8))
    print(f"{BOLD}{CYAN}{header}{RESET}")
    print("  +" + "---+" * 8)

    for i in range(8):
        row_str = f"{BOLD}{CYAN}{i}{RESET} |"
        for j in range(8):
            cell_val = board[i][j]
            if cell_val == 1:
                piece = BLACK_PIECE
            elif cell_val == -1:
                piece = WHITE_PIECE
            elif (i, j) in valid_moves:
                piece = f"{GREEN}✦{RESET}"
            else:
                piece = f"{DIM_GREEN}·{RESET}"
            row_str += f" {piece} |"
        print(row_str)
        print("  +" + "---+" * 8)

    colour_name = "BLACK" if current_player.colour == 1 else "WHITE"
    print(f"\n{BOLD}{colour_name}'S TURN{RESET}")
    print("=" * 45 + "\n")
