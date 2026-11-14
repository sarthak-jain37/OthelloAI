from board import Board
from player import Player
from minimax import MinimaxAI
from baseline_ai import GreedyAI, RandomAI
from terminal_ui import display_board


class Game:

    def __init__(self, algorithm1=None, algorithm2=None, display_mode="pretty"):
        self.board = Board()

        # None = Human, otherwise the supplied AI
        self.players = [
            Player(1, is_bot=(algorithm1 is not None), algorithm=algorithm1),
            Player(-1, is_bot=(algorithm2 is not None), algorithm=algorithm2)
        ]

        self.current_player = self.players[0]
    
        if display_mode not in ("pretty", "matrix"):
            display_mode = "pretty"

        self.display_mode = display_mode

    def switch_turn(self):
        if self.current_player == self.players[0]:
            self.current_player = self.players[1]
        else:
            self.current_player = self.players[0]

    def is_game_over(self):
        black_moves = self.board.get_valid_moves(self.players[0])
        white_moves = self.board.get_valid_moves(self.players[1])

        return not black_moves and not white_moves
    
    def show_board(self, valid_moves, black_score, white_score):

        if self.display_mode == "pretty":
            display_board(
                self.board.board,
                valid_moves,
                self.current_player,
                black_score,
                white_score
            )

        elif self.display_mode == "matrix":
            for row in self.board.board:
                print(row)

    def game_loop(self):

        while not self.is_game_over():

            valid_moves = self.board.get_valid_moves(
                self.current_player
            )

            # Handle skipped turn
            if not valid_moves:
                print(
                    f"{'BLACK' if self.current_player.colour == 1 else 'WHITE'} "
                    "has no valid moves. Passing turn."
                )

                self.switch_turn()
                continue

            # Calculate scores
            black_score = self.board.count_tokens(self.players[0])
            white_score = self.board.count_tokens(self.players[1])

            # Display board
            self.show_board(valid_moves, black_score, white_score)

            # Get current player's colour
            colour = "Black" if self.current_player.colour == 1 else "White"

            # AI's turn
            if self.current_player.is_bot:
            
                algorithm_name = self.current_player.algorithm.__class__.__name__.replace("AI", "")
                if getattr(self.current_player.algorithm, "use_pruning", False):
                    algorithm_name += " (AlphaBeta)"
                elif getattr(self.current_player.algorithm, "use_pruning", None) is False:
                    algorithm_name += " (No Pruning)"

                print(f"\n{colour} ({algorithm_name}) is thinking...")

                move = self.current_player.algorithm.find_best_move(
                    self.board,
                    self.current_player
                )

                if move is None:
                    print(f"{colour} has no valid move.")
                    self.switch_turn()
                    continue
                
                pos_i, pos_j = move

                print(f"{colour} ({algorithm_name}) plays: {pos_i} {pos_j}")

                self.board.make_move(
                    self.current_player,
                    pos_i,
                    pos_j
                )

            # Human's turn
            else:
            
                print(f"\nYour Turn ({colour}):")

                while True:
                    try:
                        pos_i, pos_j = map(
                            int,
                            input("Enter row and column: ").split()
                        )
                    except ValueError:
                        print("Enter two numbers separated by a space.")
                        continue
                    
                    if self.board.make_move(
                        self.current_player,
                        pos_i,
                        pos_j
                    ):
                        break
                    
                    print("Invalid move! Try again.")

            self.switch_turn()

        # Game over
        black_score = self.board.count_tokens(self.players[0])
        white_score = self.board.count_tokens(self.players[1])

        self.show_board(valid_moves, black_score, white_score)
        

        print("\n========== GAME OVER ==========")
        print(f"Black: {black_score}")
        print(f"White:  {white_score}")

        if black_score > white_score:
            print("BLACK WINS!")
        elif white_score > black_score:
            print("WHITE WINS!")
        else:
            print("IT'S A DRAW!")


if __name__ == "__main__":
    # Minimax without pruning (Black) vs Minimax with Alpha-Beta pruning (White) in Iterative mode
    game = Game(
        algorithm1=MinimaxAI(depth=10, search_mode="iterative", time_limit=2, use_pruning=False),
        algorithm2=MinimaxAI(depth=10, search_mode="iterative", time_limit=2, use_pruning=True),
        display_mode="pretty"
    )
    game.game_loop()
