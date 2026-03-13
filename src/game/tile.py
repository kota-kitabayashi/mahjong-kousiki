# 世の中には将来クラスというものがあるらしい。
# 使うクラスがどんなものか見なくてもいいんだってさ
# よってクラス書く順番気にしなくていいらしい。ただの便利
from __future__ import annotations

# self.name = aaaをname: aaaにできる。クラスを簡潔にできるらしい
# このプログラムはデータ持つだけのクラスが多いので便利らしい
from dataclasses import dataclass
# リストの型を明示したいらしい
from typing import List

# HONOR(字牌)だけ別で書いてるのは数牌に比べて性質が違うかららしい
SUITS = ('m', 'p', 's', 'z')
HONORS = {27: '1z', 28: '2z', 29: '3z', 30: '4z', 31: '5z', 32: '6z', 33: '7z'}
WIND_NAMES = ['東', '南', '西', '北']
ROUND_NAMES = ['東', '南']


def tile_to_index(tile: str) -> int:
    num = int(tile[0])
    suit = tile[1]
    if suit == 'm':
        return num - 1
    if suit == 'p':
        return 9 + num - 1
    if suit == 's':
        return 18 + num - 1
    if suit == 'z':
        return 27 + num - 1
    raise ValueError(f'invalid tile: {tile}')


def index_to_tile(index: int) -> str:
    if index < 0 or index > 33:
        raise ValueError(index)
    if index < 27:
        if index < 9:
            return f'{index + 1}m'
        if index < 18:
            return f'{index - 8}p'
        return f'{index - 17}s'
    return HONORS[index]


def tile_sort_key(tile: str) -> int:
    return tile_to_index(tile)


def tiles_to_counts(tiles: List[str]) -> List[int]:
    counts = [0] * 34
    for tile in tiles:
        counts[tile_to_index(tile)] += 1
    return counts


def counts_to_tiles(counts: List[int]) -> List[str]:
    result: List[str] = []
    for i, c in enumerate(counts):
        result.extend([index_to_tile(i)] * c)
    return result


def tiles_to_string(tiles: List[str]) -> str:
    ordered = sorted(tiles, key=tile_sort_key)
    parts = []
    for suit in SUITS:
        suit_tiles = [t for t in ordered if t[1] == suit]
        if suit_tiles:
            parts.append(''.join(t[0] for t in suit_tiles) + suit)
    return ''.join(parts)


def is_terminal_or_honor(index: int) -> bool:
    if index >= 27:
        return True
    n = index % 9 + 1
    return n in (1, 9)


def is_honor(index: int) -> bool:
    return index >= 27


def same_suit(a: int, b: int) -> bool:
    return a < 27 and b < 27 and a // 9 == b // 9


@dataclass(frozen=True)
class Meld:
    kind: str
    tiles: List[str]
    opened: bool
    called_tile: str | None = None
    from_player: int | None = None
