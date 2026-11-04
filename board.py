from player import Player

DIRECTIONS = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]

class Board():
    
    def __init__(self):
        self.board = [[0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 1, -1, 0, 0, 0],
                 [0, 0, 0, -1, 1, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0, 0]]
        

    def get_valid_moves(self, player):
        valid_moves = []
        opponent_colour = -player.colour

        for i in range(8):
            for j in range(8):

                if self.board[i][j] != 0:
                    continue

                for di, dj in DIRECTIONS:
                    x = i + di
                    y = j + dj

                    if not (0 <= x < 8 and 0 <= y < 8):
                        continue

                    if self.board[x][y] != opponent_colour:
                        continue

                    while 0 <= x < 8 and 0 <= y < 8:

                        if self.board[x][y] == 0:
                            break

                        if self.board[x][y] == player.colour:
                            valid_moves.append((i, j))
                            break

                        x += di
                        y += dj

        return list(set(valid_moves))
    
    def make_move(self, player, pos_i, pos_j):
        valid_moves = self.get_valid_moves(player)

        if (pos_i, pos_j) not in valid_moves:
            return False

        self.board[pos_i][pos_j] = player.colour

        opponent_colour = -player.colour

        for di, dj in DIRECTIONS:
            x = pos_i + di
            y = pos_j + dj

            coins_to_flip = []

            while 0 <= x < 8 and 0 <= y < 8:

                if self.board[x][y] == opponent_colour:
                    coins_to_flip.append((x, y))

                elif self.board[x][y] == player.colour:

                    for r, c in coins_to_flip:
                        self.board[r][c] = player.colour

                    break

                else:
                    break

                x += di
                y += dj

        return True
    
    def count_tokens(self, player):
        return sum(row.count(player.colour) for row in self.board)
                    
p1 = Player(1)


