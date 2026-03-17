# これは将来クラス
from __future__ import annotations

# ランダムとリスト扱いやすくするためのやつ
import random
from typing import List


class RandomPlayer:
    # 全ての選択においてランダムな選択をするプレイヤー
    def __init__(self, seed: int | None = None) -> None:
        # 疑似乱数であるrandom.Random(seed)を持つrandomを定義
        self.random = random.Random(seed)

    def choose_discard(self, hand: List[str], drawn_tile: str | None = None) -> int:
        # ランダムに切る牌を決める
        return self.random.randrange(len(hand))

    def choose_riichi(self, available: bool) -> bool:
        # リーチするかどうかを決める
        # なぜか35%の確率で立直する
        return available and self.random.random() < 0.35

    def choose_tsumo(self, can_win: bool) -> bool:
        # ツモアガリするかを決める。ここはすべての場合でツモアガリするようになっている
        return can_win

    def choose_ron(self, can_win: bool) -> bool:
        # ロンするか決める。すべての場合でロンする
        return can_win

    def choose_pon(self, available: bool) -> bool:
        # ポンするか決める。25%の確率になっている
        return available and self.random.random() < 0.25

    def choose_chi(self, options_count: int) -> int:
        # チーするか決める
        # チーの候補数でoptions_countが渡されるのでチーする場合はどのパターンでチーするかを
        # ランダムで決める
        if options_count == 0:
            return -1
        return self.random.randrange(options_count + 1) - 1

    def choose_kan(self, available: bool) -> bool:
        # カンするかどうかは15%の確率でする
        return available and self.random.random() < 0.15
