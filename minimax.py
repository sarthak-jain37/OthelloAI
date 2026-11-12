
import copy
import time
from player import Player


class SearchTimeout(Exception):
    pass


class MinimaxAI:

    def __init__(self, depth=4, search_mode="fixed", time_limit=5):
        self.depth = depth
        self.search_mode = search_mode
        self.time_limit = time_limit
        self.start_time = None

        if search_mode not in ("fixed", "iterative"):
            raise ValueError("Search mode must be 'fixed' or 'iterative'")

    # Evaluation function
    def evaluate(self, board, player):
        opponent_colour = -player.colour

        player_score = sum(
            row.count(player.colour)
            for row in board.board
        )

        opponent_score = sum(
            row.count(opponent_colour)
            for row in board.board
        )

        return player_score - opponent_score

    # Check whether time limit has expired
    def check_time(self):
        if time.perf_counter() - self.start_time >= self.time_limit:
            raise SearchTimeout

    # Minimax algorithm
    def minimax(self, board, depth, current_player, maximizing, ai_player):

        self.check_time()

        opponent = Player(-current_player.colour)

        moves = board.get_valid_moves(current_player)
        opponent_moves = board.get_valid_moves(opponent)

        # 1. Terminal state
        if not moves and not opponent_moves:
            score = self.evaluate(board, ai_player)

            if score > 0:
                return 100000 + score
            elif score < 0:
                return -100000 + score

            return 0

        # 2. Handle skipped turn
        # Passing does not consume search depth
        if not moves:
            return self.minimax(
                board,
                depth,
                opponent,
                not maximizing,
                ai_player
            )

        # 3. Depth limit
        if depth == 0:
            return self.evaluate(board, ai_player)

        # 4. Maximizing node
        if maximizing:

            best_score = float("-inf")

            for i, j in moves:

                self.check_time()

                new_board = copy.deepcopy(board)
                new_board.make_move(current_player, i, j)

                score = self.minimax(
                    new_board,
                    depth - 1,
                    opponent,
                    False,
                    ai_player
                )

                best_score = max(best_score, score)

            return best_score

        # 5. Minimizing node
        else:

            best_score = float("inf")

            for i, j in moves:

                self.check_time()

                new_board = copy.deepcopy(board)
                new_board.make_move(current_player, i, j)

                score = self.minimax(
                    new_board,
                    depth - 1,
                    opponent,
                    True,
                    ai_player
                )

                best_score = min(best_score, score)

            return best_score

    # Fixed-depth search
    def fixed_depth_search(self, board, player):

        valid_moves = board.get_valid_moves(player)

        if not valid_moves:
            return None

        # Start timer for this search
        self.start_time = time.perf_counter()

        # Safe fallback if search times out
        best_move = valid_moves[0]
        best_score = float("-inf")

        opponent = Player(-player.colour)

        try:
            for i, j in valid_moves:

                self.check_time()

                new_board = copy.deepcopy(board)
                new_board.make_move(player, i, j)

                score = self.minimax(
                    new_board,
                    self.depth - 1,
                    opponent,
                    False,
                    player
                )

                if score > best_score:
                    best_score = score
                    best_move = (i, j)

        except SearchTimeout:
            print("Time limit reached during fixed-depth search.")
            print(f"Playing fallback/best completed move: {best_move}")

        return best_move

    # Iterative deepening search
    def iterative_deepening_search(self, board, player):

        valid_moves = board.get_valid_moves(player)

        if not valid_moves:
            return None

        self.start_time = time.perf_counter()

        # Safe fallback if depth 1 cannot finish
        best_move = valid_moves[0]

        opponent = Player(-player.colour)

        for depth in range(1, self.depth + 1):

            try:
                current_best_move = None
                best_score = float("-inf")

                for i, j in valid_moves:

                    self.check_time()

                    new_board = copy.deepcopy(board)
                    new_board.make_move(player, i, j)

                    score = self.minimax(
                        new_board,
                        depth - 1,
                        opponent,
                        False,
                        player
                    )

                    if score > best_score:
                        best_score = score
                        current_best_move = (i, j)

                # Update only after the entire iteration finishes
                best_move = current_best_move

                print(f"Completed depth {depth} | Best move: {best_move}")

            except SearchTimeout:
                print(f"Time limit reached during depth {depth}")
                break

        return best_move

    # Public method: select search strategy
    def find_best_move(self, board, player):

        if self.search_mode == "fixed":
            return self.fixed_depth_search(board, player)

        elif self.search_mode == "iterative":
            return self.iterative_deepening_search(board, player)
