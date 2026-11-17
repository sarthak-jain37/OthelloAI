import copy
import time
from player import Player


class SearchTimeout(Exception):
    pass


# Positional weight table for move ordering to maximize alpha-beta pruning.
# Prioritizes corners (100), followed by edges (10, 5), and center moves (0, -1),
# while deprioritizing risky squares adjacent to corners (-20, -50).
MOVE_ORDER_WEIGHTS = [
    [100, -20,  10,   5,   5,  10, -20, 100],
    [-20, -50,  -2,  -2,  -2,  -2, -50, -20],
    [ 10,  -2,  -1,  -1,  -1,  -1,  -2,  10],
    [  5,  -2,  -1,   0,   0,  -1,  -2,   5],
    [  5,  -2,  -1,   0,   0,  -1,  -2,   5],
    [ 10,  -2,  -1,  -1,  -1,  -1,  -2,  10],
    [-20, -50,  -2,  -2,  -2,  -2, -50, -20],
    [100, -20,  10,   5,   5,  10, -20, 100],
]


class MinimaxAI:

    def __init__(self, depth=4, search_mode="fixed", time_limit=5, use_pruning=True, use_move_ordering=True):
        self.depth = depth
        self.search_mode = search_mode
        self.time_limit = time_limit
        self.use_pruning = use_pruning
        self.use_move_ordering = use_move_ordering
        self.start_time = None
        self.nodes_evaluated = 0

        if search_mode not in ("fixed", "iterative"):
            raise ValueError("Search mode must be 'fixed' or 'iterative'")

    @property
    def should_order_moves(self):
        # Move ordering only works when Minimax is using Alpha-Beta pruning
        return self.use_pruning and self.use_move_ordering

    def get_move_priority(self, move):
        """
        Calculates priority score for a move:
        Corners: highest score (100)
        Edges: intermediate score (10, 5)
        Center: neutral score (0, -1)
        Danger squares adjacent to corners: negative score (-20, -50)
        """
        r, c = move
        return MOVE_ORDER_WEIGHTS[r][c]

    def order_moves_list(self, moves):
        """
        Move Ordering (Maximizes Alpha-Beta Pruning):
        Sorts moves so that the most promising moves are examined first
        (e.g., checking corners like (0, 0) or (7, 7) before edge or center moves).
        """
        return sorted(moves, key=self.get_move_priority, reverse=True)

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

    # Minimax algorithm with optional Alpha-Beta pruning and move ordering
    def minimax(self, board, depth, current_player, maximizing, ai_player, alpha=float("-inf"), beta=float("inf")):
        self.check_time()
        self.nodes_evaluated += 1

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
                ai_player,
                alpha,
                beta
            )

        # 3. Depth limit
        if depth == 0:
            return self.evaluate(board, ai_player)

        # 4. Move ordering: only applied when Alpha-Beta pruning is enabled
        if self.should_order_moves:
            moves = self.order_moves_list(moves)

        # 5. Maximizing node
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
                    ai_player,
                    alpha,
                    beta
                )

                best_score = max(best_score, score)

                if self.use_pruning:
                    alpha = max(alpha, best_score)
                    if beta <= alpha:
                        break

            return best_score

        # 6. Minimizing node
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
                    ai_player,
                    alpha,
                    beta
                )

                best_score = min(best_score, score)

                if self.use_pruning:
                    beta = min(beta, best_score)
                    if beta <= alpha:
                        break

            return best_score

    # Fixed-depth search
    def fixed_depth_search(self, board, player):
        valid_moves = board.get_valid_moves(player)

        if not valid_moves:
            return None

        # Start timer for this search
        self.start_time = time.perf_counter()
        self.nodes_evaluated = 0

        # Apply move ordering only when using Alpha-Beta pruning
        if self.should_order_moves:
            valid_moves = self.order_moves_list(valid_moves)

        # Safe fallback if search times out
        best_move = valid_moves[0]
        best_score = float("-inf")
        alpha = float("-inf")
        beta = float("inf")

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
                    player,
                    alpha,
                    beta
                )

                if score > best_score:
                    best_score = score
                    best_move = (i, j)

                if self.use_pruning:
                    alpha = max(alpha, best_score)

        except SearchTimeout:
            if self.use_pruning:
                mode_name = "alpha-beta + move ordering" if self.should_order_moves else "alpha-beta"
            else:
                mode_name = "minimax"
            print(f"Time limit reached during fixed-depth {mode_name} search.")
            print(f"Playing fallback/best completed move: {best_move}")

        return best_move

    # Iterative deepening search
    def iterative_deepening_search(self, board, player):
        valid_moves = board.get_valid_moves(player)

        if not valid_moves:
            return None

        self.start_time = time.perf_counter()
        self.nodes_evaluated = 0

        # Apply move ordering only when using Alpha-Beta pruning
        if self.should_order_moves:
            valid_moves = self.order_moves_list(valid_moves)

        # Safe fallback if depth 1 cannot finish
        best_move = valid_moves[0]

        opponent = Player(-player.colour)

        for depth in range(1, self.depth + 1):
            try:
                current_best_move = None
                best_score = float("-inf")
                alpha = float("-inf")
                beta = float("inf")

                for i, j in valid_moves:
                    self.check_time()

                    new_board = copy.deepcopy(board)
                    new_board.make_move(player, i, j)

                    score = self.minimax(
                        new_board,
                        depth - 1,
                        opponent,
                        False,
                        player,
                        alpha,
                        beta
                    )

                    if score > best_score:
                        best_score = score
                        current_best_move = (i, j)

                    if self.use_pruning:
                        alpha = max(alpha, best_score)

                # Update only after the entire iteration finishes
                best_move = current_best_move

                if self.use_pruning:
                    prune_label = "AlphaBeta + MoveOrdering" if self.should_order_moves else "AlphaBeta"
                else:
                    prune_label = "Minimax"
                print(f"[{prune_label}] Completed depth {depth} | Best move: {best_move} | Nodes: {self.nodes_evaluated}")

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
