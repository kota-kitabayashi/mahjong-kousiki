from .game import MahjongGame


def main() -> None:
    game = MahjongGame(seed=42)
    game.play_hanchan()


if __name__ == '__main__':
    main()
