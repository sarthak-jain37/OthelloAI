"""Tests for algorithms/heuristics.py and the heuristic hook in MinimaxAI and NegamaxAI.

Run from the repository root:  python -m unittest tests.test_heuristics -v
"""
import random
import unittest

# core must be imported before algorithms (see the explanation doc, "Import order")
from core.board import Board
from core.player import Player
import algorithms.heuristics as H

BLACK, WHITE = 1, -1


def empty_grid():
    return [[0] * 8 for _ in range(8)]


def random_game_positions(seed, n_games=50):
    """Yield (grid, to_move) for every position along random games."""
    rng = random.Random(seed)
    for _ in range(n_games):
        b = Board()
        to_move = BLACK
        while True:
            yield [row[:] for row in b.board], to_move
            moves = b.get_valid_moves(Player(to_move))
            if not moves:
                if not b.get_valid_moves(Player(-to_move)):
                    break
                to_move = -to_move
                continue
            b.make_move(Player(to_move), *rng.choice(moves))
            to_move = -to_move


def random_game_trace(seed):
    """List of grids along one random game."""
    rng = random.Random(seed)
    b, to_move, trace = Board(), BLACK, []
    while True:
        trace.append([row[:] for row in b.board])
        moves = b.get_valid_moves(Player(to_move))
        if not moves:
            if not b.get_valid_moves(Player(-to_move)):
                return trace
            to_move = -to_move
            continue
        b.make_move(Player(to_move), *rng.choice(moves))
        to_move = -to_move


class TestOpening(unittest.TestCase):
    def test_opening_mobility(self):
        g = Board().board
        self.assertEqual(H.move_counts(g, BLACK), (4, 4))
        # standard start: White d4 (3,3) and e5 (4,4), Black e4 (3,4) and d5 (4,3)
        self.assertEqual(Board().get_valid_moves(Player(BLACK)),
                         [(2, 3), (3, 2), (4, 5), (5, 4)])

    def test_opening_scores_symmetric_and_zero(self):
        g = Board().board
        for cls in (H.H0, H.H1, H.H2):
            self.assertEqual(cls()(g, BLACK), 0)
        self.assertEqual(H.H3().phase(g), 0.0)

    def test_after_first_move(self):
        b = Board()
        self.assertTrue(b.make_move(Player(BLACK), 2, 3))
        self.assertEqual(H.disc_counts(b.board, BLACK), (4, 1))
        self.assertAlmostEqual(H.disc_diff(b.board, BLACK), 60.0)


class TestMoveGeneration(unittest.TestCase):
    def test_matches_board_get_valid_moves(self):
        for g, _ in random_game_positions(seed=1, n_games=40):
            b = Board()
            b.board = g
            expected = (len(b.get_valid_moves(Player(BLACK))),
                        len(b.get_valid_moves(Player(WHITE))))
            self.assertEqual(H.move_counts(g, BLACK), expected)
            self.assertEqual(H.move_counts(g, WHITE), expected[::-1])

    def test_ring_example(self):
        g = empty_grid()
        for r in range(2, 6):
            for c in range(2, 6):
                g[r][c] = BLACK
        for r in (3, 4):
            for c in (3, 4):
                g[r][c] = WHITE
        self.assertEqual(H.move_counts(g, BLACK), (0, 20))
        self.assertAlmostEqual(H.mobility(g, BLACK), -100.0)


class TestCornersXC(unittest.TestCase):
    def test_x_square_trap(self):
        g = empty_grid()
        g[1][1] = WHITE
        g[2][2] = BLACK
        self.assertEqual(H.x_squares(g, BLACK), 25.0)    # their disc on X: good for me
        self.assertEqual(H.x_squares(g, WHITE), -25.0)
        self.assertEqual(H.corners(g, BLACK), 0.0)
        b = Board()
        b.board = g
        self.assertIn((0, 0), b.get_valid_moves(Player(BLACK)))
        b.make_move(Player(BLACK), 0, 0)
        self.assertEqual(b.board[1][1], BLACK)
        self.assertEqual(H.corners(b.board, BLACK), 25.0)
        # corner taken -> X penalty no longer applies
        self.assertEqual(H.x_squares(b.board, BLACK), 0.0)

    def test_c_square_only_while_corner_empty(self):
        g = empty_grid()
        g[0][1] = BLACK          # C-square of (0,0)
        g[7][6] = WHITE          # C-square of (7,7)
        self.assertEqual(H.c_squares(g, BLACK), 0.0)    # -12.5 + 12.5
        g[7][7] = WHITE          # corner taken -> White's C disc no longer counts
        self.assertEqual(H.c_squares(g, BLACK), -12.5)

    def test_all_corners_scale(self):
        g = empty_grid()
        for r, c in H.CORNER_INFO:
            g[r][c] = BLACK
        self.assertEqual(H.corners(g, BLACK), 100.0)


class TestStability(unittest.TestCase):
    def test_corner_walk(self):
        g = empty_grid()
        g[0][0] = g[0][1] = g[0][2] = g[1][0] = g[1][1] = BLACK
        g[0][3] = WHITE
        ew = H.edge_walk_stable(g)
        self.assertTrue(ew[0][0] and ew[0][1] and ew[0][2] and ew[1][0])
        self.assertFalse(ew[0][3])          # walk stops at opponent disc
        self.assertFalse(ew[1][1])          # edge-walk never marks interior
        ex = H.exact_stable(g)
        self.assertTrue(ex[0][0] and ex[0][1] and ex[0][2] and ex[1][0])
        self.assertTrue(ex[1][1])           # anti-diagonal anchored by stable (0,2)
        g[0][2] = g[0][3] = 0               # now (0,2) and (2,0) are both empty
        self.assertFalse(H.exact_stable(g)[1][1])
        g[2][0] = BLACK                     # (2,0) is stable via the left-edge walk
        self.assertTrue(H.exact_stable(g)[1][1])

    def test_full_edge_any_colour(self):
        g = empty_grid()
        for c in range(8):
            g[0][c] = BLACK if c % 2 else WHITE
        ew = H.edge_walk_stable(g)
        self.assertTrue(all(ew[0][c] for c in range(8)))
        ex = H.exact_stable(g)
        self.assertTrue(all(ex[0][c] for c in range(8)))

    def test_linear_scaling(self):
        # 1 stable disc vs 0 must NOT score like 30 vs 0 (the ratio form did)
        g = empty_grid()
        g[0][0] = BLACK
        g[4][4] = WHITE                   # keeps the position non-trivial
        one = H.stability_exact(g, BLACK)
        self.assertAlmostEqual(one, 100 / 64)
        for c in range(1, 8):
            g[0][c] = BLACK               # whole top edge: 8 stable discs
        self.assertAlmostEqual(H.stability_exact(g, BLACK), 8 * 100 / 64)
        self.assertAlmostEqual(H.stability_edgewalk(g, BLACK), 8 * 100 / 64)
        self.assertAlmostEqual(H.stability_exact(g, WHITE), -8 * 100 / 64)
        full = [[BLACK] * 8 for _ in range(8)]
        self.assertAlmostEqual(H.stability_exact(full, BLACK), 100.0)

    def test_full_board_all_stable(self):
        g = [[BLACK if (r + c) % 3 else WHITE for c in range(8)] for r in range(8)]
        ex = H.exact_stable(g)
        self.assertTrue(all(all(row) for row in ex))

    def test_exact_superset_of_edgewalk(self):
        for g, _ in random_game_positions(seed=3, n_games=30):
            ew, ex = H.edge_walk_stable(g), H.exact_stable(g)
            for r in range(8):
                for c in range(8):
                    if ew[r][c]:
                        self.assertTrue(ex[r][c], (r, c))

    def test_stable_discs_never_flip(self):
        """Soundness: a disc marked stable keeps its colour for the rest of the game."""
        for seed in range(500):
            trace = random_game_trace(seed)
            for i, g in enumerate(trace):
                for fn in (H.edge_walk_stable, H.exact_stable):
                    mask = fn(g)
                    for r in range(8):
                        for c in range(8):
                            if mask[r][c]:
                                for later in trace[i + 1:]:
                                    self.assertEqual(later[r][c], g[r][c],
                                                     f"{fn.__name__} seed {seed} ({r},{c})")


class TestParityAndPhase(unittest.TestCase):
    def test_parity(self):
        g = [[BLACK] * 8 for _ in range(8)]
        g[0][0] = 0                      # 1 empty
        self.assertEqual(H.parity(g, BLACK, to_move=BLACK), 100.0)
        self.assertEqual(H.parity(g, BLACK, to_move=WHITE), -100.0)
        g[0][1] = 0                      # 2 empties: the other side moves last
        self.assertEqual(H.parity(g, BLACK, to_move=BLACK), -100.0)
        # inferred (no passes): 2 empties -> Black to move -> White moves last
        self.assertEqual(H.parity(g, WHITE), 100.0)

    def test_phase_blend_endpoints(self):
        h = H.H3()
        full = [[BLACK] * 8 for _ in range(8)]
        self.assertEqual(h.phase(full), 1.0)


class TestHeuristicInterface(unittest.TestCase):
    def test_h1_literature_table(self):
        t = H.build_table(x=-50, c=-20, edge_base=5, interior_base=-1)
        expected = [
            [100, -20, 10, 5, 5, 10, -20, 100],
            [-20, -50, -2, -2, -2, -2, -50, -20],
            [10, -2, -1, -1, -1, -1, -2, 10],
            [5, -2, -1, -1, -1, -1, -2, 5],
            [5, -2, -1, -1, -1, -1, -2, 5],
            [10, -2, -1, -1, -1, -1, -2, 10],
            [-20, -50, -2, -2, -2, -2, -50, -20],
            [100, -20, 10, 5, 5, 10, -20, 100],
        ]
        self.assertEqual(t, expected)

    def test_vector_sizes_and_roundtrip(self):
        for cls, n in ((H.H1, 5), (H.H2, 7), (H.H3, 16)):
            h = cls()
            v = h.to_vector()
            self.assertEqual(len(v), n)
            self.assertEqual(cls.from_vector(v).weights, h.weights)

    def test_accepts_board_or_grid_and_player_or_int(self):
        b = Board()
        self.assertTrue(b.make_move(Player(BLACK), 2, 3))
        for cls in (H.H0, H.H1, H.H2, H.H3):
            h = cls()
            self.assertEqual(h(b, Player(BLACK)), h(b.board, BLACK))

    def test_zero_sum(self):
        hs = [H.H0(), H.H1(), H.H2(), H.H3()]
        for g, to_move in random_game_positions(seed=2, n_games=20):
            for h in hs:
                self.assertAlmostEqual(h(g, BLACK, to_move), -h(g, WHITE, to_move), places=9)

    def test_unknown_weight_rejected(self):
        with self.assertRaises(KeyError):
            H.H2({"mobilty": 3})


class TestMinimaxIntegration(unittest.TestCase):
    """Checks of the heuristic hook in MinimaxAI (minimax.py)."""

    def test_finished_game_scored_by_result_not_heuristic(self):
        # Black owns every edge square (28 discs), White the 36 interior ones.
        # Neither side can move: Black has LOST 28-36.
        from algorithms.minimax import MinimaxAI
        b = Board()
        b.board = [[BLACK if r in (0, 7) or c in (0, 7) else WHITE for c in range(8)]
                   for r in range(8)]
        self.assertEqual(b.get_valid_moves(Player(BLACK)), [])
        self.assertEqual(b.get_valid_moves(Player(WHITE)), [])
        h = H.H2()
        self.assertGreater(h(b, Player(BLACK)), 0)      # the heuristic likes Black's position...
        ai = MinimaxAI(depth=2, time_limit=1e9, heuristic=h)
        ai.start_time = __import__("time").perf_counter()
        score = ai.minimax(b.board, 2, BLACK, True, BLACK)
        self.assertEqual(score, -100000 - 8)            # ...but the search must see a loss by 8

    def test_side_to_move_reaches_heuristic(self):
        from algorithms.minimax import MinimaxAI
        seen = []

        def recorder(grid, colour, to_move=None):
            seen.append((colour, to_move))
            return 0

        # Depth 1 from the opening: Black moves, so every leaf has White to move
        MinimaxAI(depth=1, time_limit=1e9, heuristic=recorder).find_best_move(Board(), Player(BLACK))
        self.assertTrue(seen)
        self.assertTrue(all(s == (BLACK, WHITE) for s in seen))
        # Depth 2: Black, then White moved, so Black is to move at the leaves
        seen.clear()
        MinimaxAI(depth=2, time_limit=1e9, heuristic=recorder).find_best_move(Board(), Player(BLACK))
        self.assertTrue(seen)
        self.assertTrue(all(s == (BLACK, BLACK) for s in seen))

    def test_no_heuristic_matches_disc_difference(self):
        from algorithms.minimax import MinimaxAI
        plain = MinimaxAI(depth=3, time_limit=1e9)
        h0 = MinimaxAI(depth=3, time_limit=1e9, heuristic=lambda grid, colour, t=None:
                       sum(r.count(colour) - r.count(-colour) for r in grid))
        for g, to_move in random_game_positions(seed=7, n_games=2):
            b = Board()
            b.board = g
            m1 = plain.find_best_move(b, Player(to_move))
            m2 = h0.find_best_move(b, Player(to_move))
            self.assertEqual((m1, plain.last_score), (m2, h0.last_score))


class TestNegamaxIntegration(unittest.TestCase):
    """The same checks for NegamaxAI (algorithms/negamax.py)."""

    def test_finished_game_scored_by_result_not_heuristic(self):
        from algorithms.negamax import NegamaxAI
        import time as _time
        b = Board()
        b.board = [[BLACK if r in (0, 7) or c in (0, 7) else WHITE for c in range(8)]
                   for r in range(8)]
        h = H.H2()
        self.assertGreater(h(b, Player(BLACK)), 0)      # the heuristic likes Black's position...
        ai = NegamaxAI(depth=2, time_limit=1e9, heuristic=h)
        ai.start_time = _time.perf_counter()
        # negamax scores from the side to move (Black here): a loss by 8
        self.assertEqual(ai.negamax(b, 2, Player(BLACK)), -100000 - 8)

    def test_side_to_move_reaches_heuristic(self):
        from algorithms.negamax import NegamaxAI
        seen = []

        def recorder(grid, colour, to_move=None):
            seen.append((colour, to_move))
            return 0

        # negamax evaluates from the side to move, so colour == to_move at every leaf
        NegamaxAI(depth=1, time_limit=1e9, heuristic=recorder).find_best_move(Board(), Player(BLACK))
        self.assertTrue(seen)
        self.assertTrue(all(s == (WHITE, WHITE) for s in seen))
        seen.clear()
        NegamaxAI(depth=2, time_limit=1e9, heuristic=recorder).find_best_move(Board(), Player(BLACK))
        self.assertTrue(seen)
        self.assertTrue(all(s == (BLACK, BLACK) for s in seen))

    def test_same_moves_as_minimax(self):
        """Negamax and minimax are the same search written two ways: same move, same node count."""
        from algorithms.minimax import MinimaxAI
        from algorithms.negamax import NegamaxAI
        for cls in (H.H1, H.H2, H.H3):
            for pr, mo in ((True, True), (True, False), (False, False)):
                mm = MinimaxAI(depth=2, time_limit=1e9, use_pruning=pr, use_move_ordering=mo, heuristic=cls())
                ng = NegamaxAI(depth=2, time_limit=1e9, use_pruning=pr, use_move_ordering=mo, heuristic=cls())
                for g, to_move in random_game_positions(seed=11, n_games=2):
                    b = Board()
                    b.board = g
                    m1 = mm.find_best_move(b, Player(to_move))
                    m2 = ng.find_best_move(b, Player(to_move))
                    self.assertEqual((m1, mm.nodes_evaluated), (m2, ng.nodes_evaluated))


if __name__ == "__main__":
    unittest.main()
