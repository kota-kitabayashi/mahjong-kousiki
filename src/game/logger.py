from __future__ import annotations

from pathlib import Path


class MahjongLogger:
    def __init__(self, path: str = 'logs/mahjong_log.txt') -> None:
        self.path = Path(path)
        self.path.write_text('', encoding='utf-8')

    def log(self, message: str) -> None:
        with self.path.open('a', encoding='utf-8') as f:
            f.write(message + '\n')
