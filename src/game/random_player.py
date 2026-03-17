# これは将来クラス
from __future__ import annotations

# ランダムとリスト扱いやすくするためのやつ
import random
from typing import List


class RandomPlayer:
    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def choose_discard(self, hand: List[str], drawn_tile: str | None = None) -> int:
        return self.random.randrange(len(hand))

    def choose_riichi(self, available: bool) -> bool:
        return available and self.random.random() < 0.35

    def choose_tsumo(self, can_win: bool) -> bool:
        return can_win

    def choose_ron(self, can_win: bool) -> bool:
        return can_win

    def choose_pon(self, available: bool) -> bool:
        return available and self.random.random() < 0.25

    def choose_chi(self, options_count: int) -> int:
        if options_count == 0:
            return -1
        return self.random.randrange(options_count + 1) - 1

    def choose_kan(self, available: bool) -> bool:
        return available and self.random.random() < 0.15
