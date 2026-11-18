import time
from core.board import valid_moves_grid, apply_move_grid


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
    """
    Minimax search with optional alpha-beta pruning and move ordering.

    Public interface (unchanged): find_best_move(board, player) takes a Board
    and a Player and returns (row, col), or None if there is no legal move.

    Inside the search, positions are plain 8x8 lists ("grid": 1 = Black,
    -1 = White, 0 = empty) and players are colour ints (1 or -1), so no
    Board or Player objects are created at each node.
    """

    def __init__(self, depth=4, search_mode="fixed", time_limit=5, use_pruning=True, use_move_ordering=True, heuristic=None):
        self.depth = depth
        self.search_mode = search_mode
        self.time_limit = time_limit
        self.use_pruning = use_pruning
        self.use_move_ordering = use_move_ordering
        self.start_time = None
        self.nodes_evaluated = 0
        # Best root score of the last completed search (for tests/experiments)
        self.last_score = None
        # Heuristic: callable h(grid, colour, to_move) -> score from colour's
        # point of view (higher = better for colour). grid is an 8x8 list,
        # colour and to_move are 1 (Black) or -1 (White). to_move is the side
        # to move at that position. None = disc difference (original behaviour).
        self.heuristic = heuristic

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
        Python's sort is stable, so moves with equal priority keep their
        row-by-row order from valid_moves_grid.
        """
        return sorted(moves, key=self.get_move_priority, reverse=True)

    # Evaluation of a position that is NOT finished: the heuristic if one was
    # given, otherwise disc difference. to_move = side to move at this position.
    def evaluate(self, grid, colour, to_move=None):
        if self.heuristic is not None:
            return self.heuristic(grid, colour, to_move)
        return self.disc_difference(grid, colour)

    # Actual disc difference (colour's discs minus the opponent's).
    # Also used to score finished games, which must use the real result.
    def disc_difference(self, grid, colour):
        mine = theirs = 0
        for row in grid:
            mine += row.count(colour)
            theirs += row.count(-colour)
        return mine - theirs

    # Check whether time limit has expired
    def check_time(self):
        if time.perf_counter() - self.start_time >= self.time_limit:
            raise SearchTimeout

    # Minimax algorithm with optional Alpha-Beta pruning and move ordering.
    # grid: position; colour: side to move; ai_colour: the AI at the root
    # (every score is from ai_colour's point of view).
    def minimax(self, grid, depth, colour, maximizing, ai_colour, alpha=float("-inf"), beta=float("inf")):
        self.check_time()
        self.nodes_evaluated += 1

        moves = valid_moves_grid(grid, colour)

        if not moves:
            # The opponent's moves are only needed when this side has none
            # 1. Terminal state: neither side can move
            if not valid_moves_grid(grid, -colour):
                # Finished game: score by the actual result, never by the heuristic
                score = self.disc_difference(grid, ai_colour)

                if score > 0:
                    return 100000 + score
                elif score < 0:
                    return -100000 + score

                return 0

            # 2. Handle skipped turn
            # Passing does not consume search depth
            return self.minimax(grid, depth, -colour, not maximizing, ai_colour, alpha, beta)

        # 3. Depth limit: estimate with the heuristic, telling it who is to move
        if depth == 0:
            return self.evaluate(grid, ai_colour, colour)

        # 4. Move ordering: only applied when Alpha-Beta pruning is enabled
        if self.should_order_moves:
            moves = self.order_moves_list(moves)

        # 5. Maximizing node
        if maximizing:
            best_score = float("-inf")

            for i, j in moves:
                self.check_time()

                new_grid = apply_move_grid(grid, colour, i, j)

                score = self.minimax(new_grid, depth - 1, -colour, False, ai_colour, alpha, beta)

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

                new_grid = apply_move_grid(grid, colour, i, j)

                score = self.minimax(new_grid, depth - 1, -colour, True, ai_colour, alpha, beta)

                best_score = min(best_score, score)

                if self.use_pruning:
                    beta = min(beta, best_score)
                    if beta <= alpha:
                        break

            return best_score

    # Fixed-depth search
    def fixed_depth_search(self, board, player):
        grid, colour = board.board, player.colour
        valid_moves = valid_moves_grid(grid, colour)

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

        try:
            for i, j in valid_moves:
                self.check_time()

                new_grid = apply_move_grid(grid, colour, i, j)

                score = self.minimax(new_grid, self.depth - 1, -colour, False, colour, alpha, beta)

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

        self.last_score = best_score
        return best_move

    # Iterative deepening search
    def iterative_deepening_search(self, board, player):
        grid, colour = board.board, player.colour
        valid_moves = valid_moves_grid(grid, colour)

        if not valid_moves:
            return None

        self.start_time = time.perf_counter()
        self.nodes_evaluated = 0

        # Apply move ordering only when using Alpha-Beta pruning
        if self.should_order_moves:
            valid_moves = self.order_moves_list(valid_moves)

        # Safe fallback if depth 1 cannot finish
        best_move = valid_moves[0]

        for depth in range(1, self.depth + 1):
            try:
                current_best_move = None
                best_score = float("-inf")
                alpha = float("-inf")
                beta = float("inf")

                for i, j in valid_moves:
                    self.check_time()

                    new_grid = apply_move_grid(grid, colour, i, j)

                    score = self.minimax(new_grid, depth - 1, -colour, False, colour, alpha, beta)

                    if score > best_score:
                        best_score = score
                        current_best_move = (i, j)

                    if self.use_pruning:
                        alpha = max(alpha, best_score)

                # Update only after the entire iteration finishes
                best_move = current_best_move
                self.last_score = best_score

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
