# 将来クラス
from __future__ import annotations

# dataclassesはクラスを作りやすくする。fieldは可変オブジェクトを可能にしている
# 例えば、list = []これはクラスを作った時にすべてのインスタンスで同じリストが共有されてしまう
# しかしlist = field(default_factory=list)とすることによって同じリストを共有しない
from dataclasses import dataclass, field
# リストを使いやすくする
from typing import List

# ここは牌クラスの面子クラス、牌をソートするために整数にする関数、牌を人間が読みやすい形にする関数
from .tile import Meld, tile_sort_key, tiles_to_string


@dataclass
class PlayerState:
    # ここは基本的な変数。席がどれか？スコアがどれかハンドがどれかなど
    # discardsは河、meldsは鳴き面子格納リストriichi_declearedは立直宣言の有無
    # riichi_acceptedは立直が正常に受理されたかどうか？ただし未活用とのこと
    # ippatsu_validは一発が有効かどうか？これについても未活用
    # furiten_tilesフリテン判定用の牌集合。これは重複なしの河だと思えばいい
    # menzen_before_winアガリ前まで面前だったかどうかを保持したかったらしいが、未活用とのこと。
    seat: int
    score: int = 30000
    hand: List[str] = field(default_factory=list)
    discards: List[str] = field(default_factory=list)
    melds: List[Meld] = field(default_factory=list)
    riichi_declared: bool = False
    riichi_accepted: bool = False
    double_riichi: bool = False
    ippatsu_valid: bool = False
    furiten_tiles: set[str] = field(default_factory=set)
    temp_furiten_turn: bool = False
    first_turn: bool = True
    menzen_before_win: bool = True

    def sort_hand(self) -> None:
        # 手牌を整列する関数
        self.hand.sort(key=tile_sort_key)

    def hand_string(self) -> str:
        # 手牌を表示用の文字列に変換する関数
        return tiles_to_string(self.hand)

    def closed_tiles(self) -> List[str]:
        # 手牌を返す関数
        return list(self.hand)

    def is_menzen(self) -> bool:
        # 面前かどうかを返す関数
        return all(not m.opened for m in self.melds)

    def reset_round_state(self) -> None:
        self.hand.clear()
        self.discards.clear()
        self.melds.clear()
        self.riichi_declared = False
        self.riichi_accepted = False
        self.double_riichi = False
        self.ippatsu_valid = False
        self.furiten_tiles.clear()
        self.temp_furiten_turn = False
        self.first_turn = True
        self.menzen_before_win = True
