DIRECTIONS = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]

# RAYS[r][c] lists, for each of the 8 directions from square (r, c), the
# squares in that direction (nearest first). Directions with fewer than 2
# squares are left out, because a capture needs at least one opponent disc
# followed by one of your own. Computed once, when this module is loaded.
RAYS = [[[] for _ in range(8)] for _ in range(8)]
for _r in range(8):
    for _c in range(8):
        for _dr, _dc in DIRECTIONS:
            _ray = []
            _x, _y = _r + _dr, _c + _dc
            while 0 <= _x < 8 and 0 <= _y < 8:
                _ray.append((_x, _y))
                _x += _dr
                _y += _dc
            if len(_ray) >= 2:
                RAYS[_r][_c].append(_ray)


def valid_moves_grid(grid, colour):
    """
    Legal moves for `colour` (1 or -1) on an 8x8 list, in row-by-row order.
    A square is legal if, in some direction, it is followed by one or more
    opponent discs and then one of the player's own discs.
    """
    moves = []
    for r in range(8):
        row = grid[r]
        for c in range(8):
            if row[c]:
                continue
            legal = False
            for ray in RAYS[r][c]:
                x, y = ray[0]
                if grid[x][y] != -colour:
                    continue            # must start with an opponent disc
                for (x, y) in ray[1:]:
                    v = grid[x][y]
                    if v != -colour:
                        legal = (v == colour)   # closed by own disc -> legal
                        break
                if legal:
                    break               # one direction is enough
            if legal:
                moves.append((r, c))
    return moves


def apply_move_grid(grid, colour, r, c):
    """
    New 8x8 list after `colour` plays (r, c). Does NOT check that the move
    is legal: only call it with a move from valid_moves_grid. `grid` itself
    is not changed.
    """
    new = [row[:] for row in grid]
    new[r][c] = colour
    for ray in RAYS[r][c]:
        flips = []
        for (x, y) in ray:
            v = new[x][y]
            if v == -colour:
                flips.append((x, y))
            else:
                if v == colour:         # closed by own disc: flip the run
                    for (fx, fy) in flips:
                        new[fx][fy] = colour
                break
    return new


class Board():

    def __init__(self):
        self.board = [[0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, -1, 1, 0, 0, 0],
                 [0, 0, 0, 1, -1, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0]]


    def get_valid_moves(self, player):
        # Row-by-row order. When moves tie on score, the search keeps the
        # first one, so this fixed order is what breaks ties.
        return valid_moves_grid(self.board, player.colour)

    def make_move(self, player, pos_i, pos_j):
        if (pos_i, pos_j) not in self.get_valid_moves(player):
            return False

        new = apply_move_grid(self.board, player.colour, pos_i, pos_j)
        for r in range(8):
            self.board[r][:] = new[r]   # update in place: same list objects
        return True

    def count_tokens(self, player):
        return sum(row.count(player.colour) for row in self.board)
