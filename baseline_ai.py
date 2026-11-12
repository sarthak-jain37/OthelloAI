import random
from copy import deepcopy

class RandomAI:

    def find_best_move(self, board, player):
        valid_moves = board.get_valid_moves(player)

        if not valid_moves:
            return None

        return random.choice(valid_moves)


class GreedyAI:

    def find_best_move(self, board, player):
        valid_moves = board.get_valid_moves(player)

        if not valid_moves:
            return None

        best_score = float("-inf")
        best_moves = []

        for i, j in valid_moves:
            # Simulate the move on a separate board
            new_board = deepcopy(board)
            new_board.make_move(player, i, j)

            # Evaluate immediate piece count
            score = new_board.count_tokens(player)

            if score > best_score:
                best_score = score
                best_moves = [(i, j)]

            elif score == best_score:
                best_moves.append((i, j))

        # Random tie-breaking
        return random.choice(best_moves)
