class Player:
    def __init__(self, colour, is_bot=False, algorithm=None):
        self.colour = colour
        self.is_bot = is_bot
        self.tokens = 2
        self.algorithm = algorithm