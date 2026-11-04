from board import Board
from player import Player
from terminal_ui import display_board # temp

class Game:
    def __init__(self):
        self.board = Board()

        self.players = [
            Player(1),
            Player(-1)
        ]

        self.current_player = self.players[0]

    def switch_turn(self):
        if self.current_player == self.players[0]:
            self.current_player = self.players[1]
        else:
            self.current_player = self.players[0]

    def is_game_over(self):
        black_moves = self.board.get_valid_moves(self.players[0])
        white_moves = self.board.get_valid_moves(self.players[1])

        return not black_moves and not white_moves

    
    def game_loop(self):

        while not self.is_game_over():

            valid_moves = self.board.get_valid_moves(
                self.current_player
            )

            if not valid_moves:
                print("No valid moves. Passing turn.")
                self.switch_turn()
                input("Press Enter to continue...")
                continue

            black_score = self.board.count_tokens(self.players[0])
            white_score = self.board.count_tokens(self.players[1])

            display_board(  #temp
                self.board.board,
                valid_moves,
                self.current_player,
                black_score,
                white_score
            )

            while True:
                try:
                    pos_i, pos_j = map(int, input("Move: ").split())
                except ValueError:
                    print("Enter two numbers.")
                    continue
                
                if self.board.make_move(self.current_player, pos_i, pos_j):
                    break
                
                print("Invalid move! Try again.")

            self.switch_turn()

        black_score = self.board.count_tokens(self.players[0])
        white_score = self.board.count_tokens(self.players[1])

        display_board(self.board.board,[],self.current_player,black_score,white_score)

        print("\nGAME OVER!")

        if black_score > white_score:
            print("BLACK WINS!")
        elif white_score > black_score:
            print("WHITE WINS!")
        else:
            print("IT'S A DRAW!")



Game().game_loop()