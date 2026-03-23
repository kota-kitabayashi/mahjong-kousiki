# これは将来クラス
from __future__ import annotations

# ランダムとリスト扱いやすくするためのやつ
import random
from typing import List


# 全ての選択においてランダムな選択をするプレイヤー
class RandomPlayer:
    # 疑似乱数であるrandom.Random(seed)を持つrandomを定義
    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    # ランダムに切る牌を決める
    def choose_discard(self, hand: List[str], drawn_tile: str | None = None) -> int:
        return self.random.randrange(len(hand))

    # リーチするかどうかを決める
    # なぜか35%の確率で立直する
    def choose_riichi(self, available: bool) -> bool:
        return available and self.random.random() < 0.35

    # ツモアガリするかを決める。ここはすべての場合でツモアガリするようになっている
    def choose_tsumo(self, can_win: bool) -> bool:
        return can_win

    # ロンするか決める。すべての場合でロンする
    def choose_ron(self, can_win: bool) -> bool:
        return can_win

    # ポンするか決める。25%の確率になっている
    def choose_pon(self, available: bool) -> bool:
        return available and self.random.random() < 0.25

    # チーするか決める
    # チーの候補数でoptions_countが渡されるのでチーする場合はどのパターンでチーするかを
    # ランダムで決める
    def choose_chi(self, options_count: int) -> int:
        if options_count == 0:
            return -1
        return self.random.randrange(options_count + 1) - 1

    # カンするかどうかは15%の確率でする
    def choose_kan(self, available: bool) -> bool:
        return available and self.random.random() < 0.15
