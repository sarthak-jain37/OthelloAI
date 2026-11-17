"""
Evaluation heuristics for the Othello AI project.

    H0  disc difference only (baseline, no weights)
    H1  static positional table (5 square classes) + disc difference
    H2  corners, X/C (only while the corner is empty), disc difference,
        mobility, frontier, edge-walk stability
    H3  H2's features with exact iterative stability, plus move parity,
        with opening/endgame weight sets blended by board fullness

Every heuristic is a callable:

    h(board, player, to_move=None) -> float

* board    a Board object (uses board.board) or a raw 8x8 list of lists
           (1 = Black, -1 = White, 0 = empty)
* player   the player whose perspective we score from (Player or colour int).
           Higher is better for this player; h(s, Black) == -h(s, White).
* to_move  colour of the side to move at this position. Only H3's parity
           feature uses it. If omitted it is inferred assuming no passes
           have happened (an even number of empties means Black to move).

All features are oriented "higher is better for me" and scaled to -100..+100.
Weights are stored as ordered dicts so they map directly onto a GA genome:
see `to_vector` / `from_vector`.
"""

# --------------------------------------------------------------------------
# Board geometry (precomputed once)
# --------------------------------------------------------------------------

N = 8
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# For each square, the rays in all 8 directions as lists of (r, c).
RAYS = [[[] for _ in range(N)] for _ in range(N)]
for _r in range(N):
    for _c in range(N):
        for _dr, _dc in DIRECTIONS:
            ray = []
            x, y = _r + _dr, _c + _dc
            while 0 <= x < N and 0 <= y < N:
                ray.append((x, y))
                x += _dr
                y += _dc
            if len(ray) >= 2:          # a capture needs at least 2 squares
                RAYS[_r][_c].append(ray)

# 8-neighbours of each square (for frontier).
NEIGHBOURS = [[[(_r + dr, _c + dc) for dr, dc in DIRECTIONS
                if 0 <= _r + dr < N and 0 <= _c + dc < N]
               for _c in range(N)] for _r in range(N)]

# corner -> (X-square, (C-square, C-square))
CORNER_INFO = {
    (0, 0): ((1, 1), ((0, 1), (1, 0))),
    (0, 7): ((1, 6), ((0, 6), (1, 7))),
    (7, 0): ((6, 1), ((7, 1), (6, 0))),
    (7, 7): ((6, 6), ((7, 6), (6, 7))),
}

# Edges for edge-walk stability: each corner and the two directions along
# its edges.
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

# The four line axes (as one direction of each pair), for exact stability.
AXES = [(0, 1), (1, 0), (1, 1), (1, -1)]


def _line_id(r, c, axis):
    """Identifier of the full line through (r, c) along an axis."""
    if axis == 0:
        return r                # row
    if axis == 1:
        return c                # column
    if axis == 2:
        return r - c            # main diagonal (-7..7)
    return r + c                # anti-diagonal (0..14)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _grid(board):
    return board.board if hasattr(board, "board") else board


def _colour(player):
    return player.colour if hasattr(player, "colour") else player


def ratio(m, t):
    """100 * (m - t) / (m + t), or 0 when both are 0."""
    s = m + t
    return 100.0 * (m - t) / s if s else 0.0


# --------------------------------------------------------------------------
# Feature functions. Each takes the raw grid `b` and my colour `me`.
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
    """Sum of table values over my discs minus over their discs (unnormalized)."""
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
    """25 * (their - my) discs on X-squares next to EMPTY corners."""
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
    """12.5 * (their - my) discs on C-squares next to EMPTY corners."""
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
    """Number of legal move squares for me and for them (each square once)."""
    mine = theirs = 0
    for r in range(N):
        row = b[r]
        for c in range(N):
            if row[c]:
                continue
            m_ok = t_ok = False
            for ray in RAYS[r][c]:
                x, y = ray[0]
                first = b[x][y]
                if first == 0:
                    continue
                # first disc belongs to `first`'s opponent's capture target:
                # a run of `first` discs closed by -first is a move for -first
                for (x, y) in ray[1:]:
                    v = b[x][y]
                    if v == first:
                        continue
                    if v == -first:
                        if first == me:
                            t_ok = True
                        else:
                            m_ok = True
                    break
                if m_ok and t_ok:
                    break
            mine += m_ok
            theirs += t_ok
    return mine, theirs


def mobility(b, me):
    return ratio(*move_counts(b, me))


def frontier(b, me):
    """Fewer frontier discs is better: ratio(their frontier, my frontier)."""
    mine = theirs = 0
    for r in range(N):
        row = b[r]
        for c in range(N):
            v = row[c]
            if not v:
                continue
            for (x, y) in NEIGHBOURS[r][c]:
                if b[x][y] == 0:
                    if v == me:
                        mine += 1
                    else:
                        theirs += 1
                    break
    return ratio(theirs, mine)


def edge_walk_stable(b):
    """64-square mask of discs found stable by the edge-walk approximation."""
    stable = [[False] * N for _ in range(N)]
    for (r, c), dirs in CORNER_WALKS.items():
        owner = b[r][c]
        if owner == 0:
            continue
        stable[r][c] = True
        for dr, dc in dirs:
            x, y = r + dr, c + dc
            while 0 <= x < N and 0 <= y < N and b[x][y] == owner:
                stable[x][y] = True
                x += dr
                y += dc
    for edge in EDGES:
        if all(b[x][y] != 0 for (x, y) in edge):
            for (x, y) in edge:
                stable[x][y] = True
    return stable


def exact_stable(b):
    """
    Iterative stability. A disc is stable if, for each of its 4 axes, the
    whole line along that axis is full, or a neighbour along that axis (in
    one of the two directions) is the board edge or a stable disc of the
    same colour. Rescan until nothing changes.
    """
    # Which full lines contain no empty square?
    full = [dict() for _ in AXES]
    for r in range(N):
        for c in range(N):
            empty = b[r][c] == 0
            for a in range(4):
                k = _line_id(r, c, a)
                full[a][k] = full[a].get(k, True) and not empty

    stable = [[False] * N for _ in range(N)]
    changed = True
    while changed:
        changed = False
        for r in range(N):
            row = b[r]
            for c in range(N):
                v = row[c]
                if not v or stable[r][c]:
                    continue
                ok = True
                for a, (dr, dc) in enumerate(AXES):
                    if full[a][_line_id(r, c, a)]:
                        continue
                    anchored = False
                    for s in (1, -1):
                        x, y = r + s * dr, c + s * dc
                        if not (0 <= x < N and 0 <= y < N):
                            anchored = True
                            break
                        if stable[x][y] and b[x][y] == v:
                            anchored = True
                            break
                    if not anchored:
                        ok = False
                        break
                if ok:
                    stable[r][c] = True
                    changed = True
    return stable


def _stable_score(b, me, mask):
    """
    Linear: 100 * (my stable discs - their stable discs) / 64.

    Not the ratio form: stable discs are few for most of the game, and the
    ratio scores 1 stable disc vs 0 the same as 30 vs 0 (+100). Measured on
    7,086 positions from H2 self-play, the ratio sat at exactly +-100 in 28%
    of positions (edge-walk) just because one side had any stable discs.
    Same reasoning as linear scaling for corners.
    """
    mine = theirs = 0
    for r in range(N):
        for c in range(N):
            if mask[r][c]:
                v = b[r][c]
                if v == me:
                    mine += 1
                elif v == -me:
                    theirs += 1
    return 100.0 * (mine - theirs) / 64


def stability_edgewalk(b, me):
    return _stable_score(b, me, edge_walk_stable(b))


def stability_exact(b, me):
    return _stable_score(b, me, exact_stable(b))


def parity(b, me, to_move=None):
    """+100 if I am expected to make the last move, -100 if they are."""
    empties = sum(row.count(0) for row in b)
    if empties == 0:
        return 0.0
    if to_move is None:
        to_move = 1 if empties % 2 == 0 else -1   # assumes no passes so far
    last = to_move if empties % 2 == 1 else -to_move
    return 100.0 if last == me else -100.0


# --------------------------------------------------------------------------
# Heuristic classes
# --------------------------------------------------------------------------

CLASS_MAP = [
    "KCAEEACK",
    "CXIIIIXC",
    "AIiiiiIA",
    "EIiiiiIE",
    "EIiiiiIE",
    "AIiiiiIA",
    "CXIIIIXC",
    "KCAEEACK",
]


def build_table(x, c, edge_base, interior_base, corner=100):
    values = {
        "K": corner, "X": x, "C": c,
        "A": 2 * edge_base, "E": edge_base,
        "I": 2 * interior_base, "i": interior_base,
    }
    return [[values[ch] for ch in row] for row in CLASS_MAP]


class Heuristic:
    """Base class: weights in a fixed key order, convertible to/from vectors."""
    DEFAULTS = {}
    name = "H?"

    def __init__(self, weights=None):
        w = dict(self.DEFAULTS)
        if weights:
            unknown = set(weights) - set(w)
            if unknown:
                raise KeyError(f"{self.name}: unknown weights {sorted(unknown)}")
            w.update(weights)
        self.weights = w
        self._setup()

    def _setup(self):
        pass

    # GA helpers
    @classmethod
    def keys(cls):
        return list(cls.DEFAULTS)

    def to_vector(self):
        return [self.weights[k] for k in self.DEFAULTS]

    @classmethod
    def from_vector(cls, vec):
        keys = cls.keys()
        if len(vec) != len(keys):
            raise ValueError(f"{cls.name} expects {len(keys)} weights, got {len(vec)}")
        return cls(dict(zip(keys, vec)))

    def terms(self, board, player, to_move=None):
        """Per-feature raw values (before weighting). For logging/debugging."""
        raise NotImplementedError

    def __call__(self, board, player, to_move=None):
        raise NotImplementedError

    def __repr__(self):
        return f"{self.name}({self.weights})"


class H0(Heuristic):
    """Disc difference only (baseline). No weights."""
    name = "H0"

    def terms(self, board, player, to_move=None):
        return {"disc": disc_diff(_grid(board), _colour(player))}

    def __call__(self, board, player, to_move=None):
        return disc_diff(_grid(board), _colour(player))


class H1(Heuristic):
    """
    Static positional table + disc difference.

    Tunable (5): x, c, edge_base, interior_base (square values; corner fixed
    at 100) and disc (weight of the ±100 disc-difference term). The table's
    own coefficient is fixed at 1 and the table sum is left unnormalized.

    disc defaults to 1.0, not the literature's 25: the table sum is typically
    in the tens to low hundreds, so 25 x (±100) would swamp it and turn H1
    into a disc maximizer (see project summary 5.3).
    """
    name = "H1"
    DEFAULTS = {"x": -50, "c": -20, "edge_base": 5, "interior_base": -1, "disc": 1.0}

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
    """
    Exact corners/X/C, disc difference, mobility, frontier, edge-walk stability.

    Stability weight 150: the literature value 25 was for the ratio form.
    With linear scaling the feature is about 6x smaller on average (31.0 vs
    5.2 mean |value| over H2 self-play positions), so 25 x 5.95 ~= 150 keeps
    the same average contribution.
    """
    name = "H2"
    DEFAULTS = {"corner": 30, "x": 15, "c": 6, "disc": 25,
                "mobility": 5, "frontier": 10, "stability": 150}

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
    """
    H2's features with exact stability, plus move parity. Two weight sets
    (opening '_o', endgame '_e') blended by t = (discs on board - 4) / 60.

    Stability weights 175 / 85: the literature value 25 was for the ratio
    form. Rescaled so the linear feature's average contribution matches,
    measured separately for each phase of the blend over H2 self-play
    positions (factors 6.97 and 3.38).
    """
    name = "H3"
    DEFAULTS = {}
    _open = {"corner": 30, "x": 15, "c": 6, "disc": 5, "mobility": 5,
             "frontier": 10, "stability": 175, "parity": 0}
    _end = {"corner": 30, "x": 5, "c": 5, "disc": 30, "mobility": 5,
            "frontier": 5, "stability": 85, "parity": 10}
    for _f in H3_FEATURES:
        DEFAULTS[_f + "_o"] = _open[_f]
    for _f in H3_FEATURES:
        DEFAULTS[_f + "_e"] = _end[_f]
    del _f

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
