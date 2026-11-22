"""
Evaluation heuristics for Othello AI: H0, H1, H2, and H3.

Each heuristic is callable:
    h = H1()                 # uses GA-tuned weights by default
    h = H1("literature")     # uses literature baseline weights
    score = h(board, player, to_move=None)
"""

N = 8
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# Precomputed rays: for each square (r, c), squares in all 8 directions
RAYS = [[[] for _ in range(N)] for _ in range(N)]
for _r in range(N):
    for _c in range(N):
        for _dr, _dc in DIRECTIONS:
            _ray = []
            _x, _y = _r + _dr, _c + _dc
            while 0 <= _x < N and 0 <= _y < N:
                _ray.append((_x, _y))
                _x += _dr
                _y += _dc
            if len(_ray) >= 2:
                RAYS[_r][_c].append(_ray)

# 8-neighbours for frontier check
NEIGHBOURS = [[[(_r + dr, _c + dc) for dr, dc in DIRECTIONS
                if 0 <= _r + dr < N and 0 <= _c + dc < N]
               for _c in range(N)] for _r in range(N)]

CORNER_INFO = {
    (0, 0): ((1, 1), ((0, 1), (1, 0))),
    (0, 7): ((1, 6), ((0, 6), (1, 7))),
    (7, 0): ((6, 1), ((7, 1), (6, 0))),
    (7, 7): ((6, 6), ((7, 6), (6, 7))),
}

CORNER_WALKS = {
    (0, 0): ((0, 1), (1, 0)),
    (0, 7): ((0, -1), (1, 0)),
    (7, 0): ((0, 1), (-1, 0)),
    (7, 7): ((0, -1), (-1, 0)),
}

EDGES = [
    [(0, c) for c in range(N)],
    [(7, c) for c in range(N)],
    [(r, 0) for r in range(N)],
    [(r, 7) for r in range(N)],
]

AXES = [(0, 1), (1, 0), (1, 1), (1, -1)]


def _line_id(r, c, axis):
    if axis == 0:
        return r
    if axis == 1:
        return c
    if axis == 2:
        return r - c
    return r + c


def _grid(board):
    return board.board if hasattr(board, "board") else board


def _colour(player):
    return player.colour if hasattr(player, "colour") else player


def ratio(m, t):
    s = m + t
    return 100.0 * (m - t) / s if s else 0.0


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------

def disc_counts(b, me):
    mine = theirs = 0
    for row in b:
        for v in row:
            if v == me:
                mine += 1
            elif v == -me:
                theirs += 1
    return mine, theirs


def disc_diff(b, me):
    return ratio(*disc_counts(b, me))


def positional(b, me, table):
    s = 0
    for r in range(N):
        row, trow = b[r], table[r]
        for c in range(N):
            v = row[c]
            if v:
                s += trow[c] if v == me else -trow[c]
    return s


def corners(b, me):
    s = 0
    for (r, c) in CORNER_INFO:
        v = b[r][c]
        if v == me:
            s += 1
        elif v == -me:
            s -= 1
    return 25.0 * s


def x_squares(b, me):
    s = 0
    for (r, c), ((xr, xc), _) in CORNER_INFO.items():
        if b[r][c] == 0:
            v = b[xr][xc]
            if v == -me:
                s += 1
            elif v == me:
                s -= 1
    return 25.0 * s


def c_squares(b, me):
    s = 0
    for (r, c), (_, cs) in CORNER_INFO.items():
        if b[r][c] == 0:
            for (cr, cc) in cs:
                v = b[cr][cc]
                if v == -me:
                    s += 1
                elif v == me:
                    s -= 1
    return 12.5 * s


def move_counts(b, me):
    m_count = opp_count = 0
    for r in range(N):
        row = b[r]
        for c in range(N):
            if row[c]:
                continue
            m_legal = opp_legal = False
            for ray in RAYS[r][c]:
                if not m_legal and b[ray[0][0]][ray[0][1]] == -me:
                    for (x, y) in ray[1:]:
                        v = b[x][y]
                        if v != -me:
                            if v == me:
                                m_legal = True
                            break
                if not opp_legal and b[ray[0][0]][ray[0][1]] == me:
                    for (x, y) in ray[1:]:
                        v = b[x][y]
                        if v != me:
                            if v == -me:
                                opp_legal = True
                            break
                if m_legal and opp_legal:
                    break
            if m_legal:
                m_count += 1
            if opp_legal:
                opp_count += 1
    return m_count, opp_count


def mobility(b, me):
    return ratio(*move_counts(b, me))


def frontier(b, me):
    m_front = opp_front = 0
    for r in range(N):
        row = b[r]
        for c in range(N):
            v = row[c]
            if not v:
                continue
            if any(b[nr][nc] == 0 for (nr, nc) in NEIGHBOURS[r][c]):
                if v == me:
                    m_front += 1
                else:
                    opp_front += 1
    return ratio(opp_front, m_front)


def edge_walk_stable(b):
    stable = [[False] * N for _ in range(N)]
    for (cr, cc), (r_step, c_step) in CORNER_WALKS.items():
        v = b[cr][cc]
        if not v:
            continue
        for dr, dc in (r_step, c_step):
            r, c = cr, cc
            while 0 <= r < N and 0 <= c < N and b[r][c] == v:
                stable[r][c] = True
                r += dr
                c += dc
    for edge in EDGES:
        if all(b[r][c] != 0 for r, c in edge):
            for r, c in edge:
                stable[r][c] = True
    return stable


def exact_stable(b):
    stable = [[False] * N for _ in range(N)]
    for (cr, cc) in CORNER_INFO:
        if b[cr][cc]:
            stable[cr][cc] = True

    full_lines = [set() for _ in range(4)]
    for r in range(N):
        for c in range(N):
            if b[r][c] == 0:
                for a in range(4):
                    full_lines[a].add(_line_id(r, c, a))

    changed = True
    while changed:
        changed = False
        for r in range(N):
            for c in range(N):
                if stable[r][c] or not b[r][c]:
                    continue
                v = b[r][c]
                is_st = True
                for a, (dr, dc) in enumerate(AXES):
                    if _line_id(r, c, a) not in full_lines[a]:
                        continue
                    side1 = side2 = False
                    cr, cc = r + dr, c + dc
                    while 0 <= cr < N and 0 <= cc < N:
                        if stable[cr][cc] and b[cr][cc] == v:
                            side1 = True
                            break
                        cr += dr
                        cc += dc
                    if not (0 <= r + dr < N and 0 <= c + dc < N):
                        side1 = True
                    cr, cc = r - dr, c - dc
                    while 0 <= cr < N and 0 <= cc < N:
                        if stable[cr][cc] and b[cr][cc] == v:
                            side2 = True
                            break
                        cr -= dr
                        cc -= dc
                    if not (0 <= r - dr < N and 0 <= c - dc < N):
                        side2 = True
                    if not (side1 and side2):
                        is_st = False
                        break
                if is_st:
                    stable[r][c] = True
                    changed = True
    return stable


def _stable_score(b, me, stable_grid):
    s = 0
    for r in range(N):
        row, srow = b[r], stable_grid[r]
        for c in range(N):
            if srow[c]:
                s += 1 if row[c] == me else -1
    return 100.0 * s / 64.0


def stability_edgewalk(b, me):
    return _stable_score(b, me, edge_walk_stable(b))


def stability_exact(b, me):
    return _stable_score(b, me, exact_stable(b))


def parity(b, me, to_move=None):
    if to_move is None:
        empties = sum(row.count(0) for row in b)
        to_move = 1 if (empties % 2 == 0) else -1
    empties = sum(row.count(0) for row in b)
    if empties % 2 == 1:
        return 100.0 if to_move == me else -100.0
    return -100.0 if to_move == me else 100.0


def build_table(x, c, edge_base, interior_base):
    table = [[interior_base] * N for _ in range(N)]
    for i in range(2, 6):
        table[0][i] = table[7][i] = table[i][0] = table[i][7] = edge_base
    table[0][2] = table[0][5] = table[7][2] = table[7][5] = 2 * edge_base
    table[2][0] = table[5][0] = table[2][7] = table[5][7] = 2 * edge_base
    for (cr, cc), ((xr, xc), ((c1r, c1c), (c2r, c2c))) in CORNER_INFO.items():
        table[cr][cc] = 100
        table[xr][xc] = x
        table[c1r][c1c] = c
        table[c2r][c2c] = c
    return table


# --------------------------------------------------------------------------
# Heuristics Base Class
# --------------------------------------------------------------------------

class Heuristic:
    name = "Heuristic"
    DEFAULTS = {}
    TUNED = {}
    LITERATURE = {}

    def __init__(self, weights=None):
        if weights == "literature":
            self.weights = dict(self.LITERATURE or self.DEFAULTS)
        elif weights == "tuned" or weights is None:
            self.weights = dict(self.TUNED or self.DEFAULTS)
        elif isinstance(weights, dict):
            for k in weights:
                if k not in self.DEFAULTS:
                    raise KeyError(f"Unknown weight {k!r} for {self.name}")
            w = dict(self.TUNED or self.DEFAULTS)
            w.update(weights)
            self.weights = w
        else:
            self.weights = dict(self.TUNED or self.DEFAULTS)
        self._setup()

    def _setup(self):
        pass

    @classmethod
    def keys(cls):
        return list(cls.DEFAULTS.keys())

    def to_vector(self):
        return [float(self.weights[k]) for k in self.keys()]

    @classmethod
    def from_vector(cls, vec):
        keys = cls.keys()
        if len(vec) != len(keys):
            raise ValueError(f"{cls.name} expects {len(keys)} weights, got {len(vec)}")
        return cls(dict(zip(keys, vec)))

    def terms(self, board, player, to_move=None):
        raise NotImplementedError

    def __call__(self, board, player, to_move=None):
        raise NotImplementedError

    def __repr__(self):
        return f"{self.name}({self.weights})"


# --------------------------------------------------------------------------
# H0, H1, H2, H3
# --------------------------------------------------------------------------

class H0(Heuristic):
    name = "H0"

    def terms(self, board, player, to_move=None):
        return {"disc": disc_diff(_grid(board), _colour(player))}

    def __call__(self, board, player, to_move=None):
        return disc_diff(_grid(board), _colour(player))


class H1(Heuristic):
    name = "H1"
    DEFAULTS = {"x": -50, "c": -20, "edge_base": 5, "interior_base": -1, "disc": 1.0}
    LITERATURE = {"x": -50, "c": -20, "edge_base": 5, "interior_base": -1, "disc": 1.0}
    TUNED = {
        "x": -39.9155, "c": -9.1767, "edge_base": 2.1165, "interior_base": -3.5067, "disc": 0.8366
    }

    def _setup(self):
        w = self.weights
        self.table = build_table(w["x"], w["c"], w["edge_base"], w["interior_base"])

    def terms(self, board, player, to_move=None):
        b, me = _grid(board), _colour(player)
        return {"positional": positional(b, me, self.table), "disc": disc_diff(b, me)}

    def __call__(self, board, player, to_move=None):
        b, me = _grid(board), _colour(player)
        return positional(b, me, self.table) + self.weights["disc"] * disc_diff(b, me)


class H2(Heuristic):
    name = "H2"
    DEFAULTS = {"corner": 30, "x": 15, "c": 6, "disc": 25, "mobility": 5, "frontier": 10, "stability": 150}
    LITERATURE = {"corner": 30, "x": 15, "c": 6, "disc": 25, "mobility": 5, "frontier": 10, "stability": 150}
    TUNED = {
        "corner": 30.0, "x": 20.8237, "c": 9.8262, "disc": 15.5392,
        "mobility": 27.6403, "frontier": 22.8981, "stability": 233.3190
    }

    def terms(self, board, player, to_move=None):
        b, me = _grid(board), _colour(player)
        return {
            "corner": corners(b, me),
            "x": x_squares(b, me),
            "c": c_squares(b, me),
            "disc": disc_diff(b, me),
            "mobility": mobility(b, me),
            "frontier": frontier(b, me),
            "stability": stability_edgewalk(b, me),
        }

    def __call__(self, board, player, to_move=None):
        w = self.weights
        return sum(w[k] * v for k, v in self.terms(board, player, to_move).items())


H3_FEATURES = ["corner", "x", "c", "disc", "mobility", "frontier", "stability", "parity"]


class H3(Heuristic):
    name = "H3"
    DEFAULTS = {}
    _open = {"corner": 30, "x": 15, "c": 6, "disc": 5, "mobility": 5, "frontier": 10, "stability": 175, "parity": 0}
    _end = {"corner": 30, "x": 5, "c": 5, "disc": 30, "mobility": 5, "frontier": 5, "stability": 85, "parity": 10}
    for _f in H3_FEATURES:
        DEFAULTS[_f + "_o"] = _open[_f]
        DEFAULTS[_f + "_e"] = _end[_f]

    LITERATURE = dict(DEFAULTS)
    TUNED = {
        "corner_o": 30.0, "x_o": 11.3717, "c_o": 24.8901, "disc_o": 2.2962,
        "mobility_o": 23.0872, "frontier_o": 11.7920, "stability_o": 411.7773, "parity_o": 3.5067,
        "corner_e": 33.7474, "x_e": 16.5309, "c_e": 0.0, "disc_e": 18.3757,
        "mobility_e": 17.8336, "frontier_e": 16.8328, "stability_e": 57.0821, "parity_e": 18.1167
    }

    def terms(self, board, player, to_move=None):
        b, me = _grid(board), _colour(player)
        return {
            "corner": corners(b, me),
            "x": x_squares(b, me),
            "c": c_squares(b, me),
            "disc": disc_diff(b, me),
            "mobility": mobility(b, me),
            "frontier": frontier(b, me),
            "stability": stability_exact(b, me),
            "parity": parity(b, me, to_move),
        }

    def phase(self, board):
        b = _grid(board)
        discs = sum(1 for row in b for v in row if v)
        return (discs - 4) / 60.0

    def __call__(self, board, player, to_move=None):
        w = self.weights
        t = self.phase(board)
        total = 0.0
        for f, v in self.terms(board, player, to_move).items():
            total += ((1 - t) * w[f + "_o"] + t * w[f + "_e"]) * v
        return total


HEURISTICS = {"H0": H0, "H1": H1, "H2": H2, "H3": H3}
