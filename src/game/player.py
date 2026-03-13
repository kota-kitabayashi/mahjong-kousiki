from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .tile import Meld, tile_sort_key, tiles_to_string


@dataclass
class PlayerState:
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
        self.hand.sort(key=tile_sort_key)

    def hand_string(self) -> str:
        return tiles_to_string(self.hand)

    def closed_tiles(self) -> List[str]:
        return list(self.hand)

    def is_menzen(self) -> bool:
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
