from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

from .tile import Meld, index_to_tile, is_honor, is_terminal_or_honor, tile_to_index, tiles_to_counts
from .rules import (
    BAIMAN_CHILD,
    BAIMAN_PARENT,
    HANEMAN_CHILD,
    HANEMAN_PARENT,
    MANGAN_CHILD,
    MANGAN_PARENT,
    SANBAIMAN_CHILD,
    SANBAIMAN_PARENT,
    YAKUMAN_BASE_CHILD,
    YAKUMAN_BASE_PARENT,
    YONBAIMAN_CHILD,
    YONBAIMAN_PARENT,
)


@dataclass
class WinContext:
    seat: int
    round_wind: int
    is_tsumo: bool
    is_riichi: bool
    is_double_riichi: bool
    is_ippatsu: bool
    is_rinshan: bool
    is_chankan: bool
    is_haitei: bool
    is_houtei: bool
    is_tenhou: bool
    is_chiihou: bool
    open_melds: List[Meld]
    closed_melds: List[Meld]
    winning_tile: str


@dataclass
class HandScore:
    han: int
    fu: int
    yaku: List[Tuple[str, int]]
    yakuman: int
    total_points: int
    ron_points: int
    tsumo_child_pay: int
    tsumo_parent_pay: int


def _remove_melds(counts: List[int], path: List[Tuple[str, int]], out: List[List[Tuple[str, int]]]) -> None:
    i = next((j for j, c in enumerate(counts) if c > 0), -1)
    if i == -1:
        out.append(path.copy())
        return
    if counts[i] >= 3:
        counts[i] -= 3
        path.append(('triplet', i))
        _remove_melds(counts, path, out)
        path.pop()
        counts[i] += 3
    if i < 27 and i % 9 <= 6 and counts[i + 1] > 0 and counts[i + 2] > 0:
        counts[i] -= 1
        counts[i + 1] -= 1
        counts[i + 2] -= 1
        path.append(('sequence', i))
        _remove_melds(counts, path, out)
        path.pop()
        counts[i] += 1
        counts[i + 1] += 1
        counts[i + 2] += 1


@lru_cache(maxsize=None)
def _standard_decompositions(counts_key: Tuple[int, ...]) -> Tuple[Tuple[Tuple[str, int], ...], ...]:
    counts = list(counts_key)
    result: List[List[Tuple[str, int]]] = []
    for i in range(34):
        if counts[i] >= 2:
            counts[i] -= 2
            partial: List[List[Tuple[str, int]]] = []
            _remove_melds(counts, [('pair', i)], partial)
            result.extend(partial)
            counts[i] += 2
    return tuple(tuple(x) for x in result)


def standard_decompositions(counts: List[int]) -> List[List[Tuple[str, int]]]:
    return [list(x) for x in _standard_decompositions(tuple(counts))]


def is_chiitoitsu(counts: List[int]) -> bool:
    return len([c for c in counts if c == 2]) == 7


def is_kokushi(counts: List[int]) -> bool:
    req = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
    return all(counts[i] >= 1 for i in req) and sum(counts) == 14 and sum(counts[i] == 2 for i in req) == 1


def is_ryuuiisou(counts: List[int]) -> bool:
    allowed = {19, 20, 21, 23, 25, 32}
    return all(c == 0 or i in allowed for i, c in enumerate(counts))


def yakuhai_han(index: int, seat: int, round_wind: int) -> int:
    han = 0
    if index in (31, 32, 33):
        han += 1
    if index == 27 + seat:
        han += 1
    if index == 27 + round_wind:
        han += 1
    return han


def wait_type(decomp: List[Tuple[str, int]], win_idx: int, pair: int) -> str:
    if pair == win_idx:
        return 'tanki'
    for kind, idx in decomp:
        if kind == 'sequence' and idx <= win_idx <= idx + 2:
            pos = win_idx - idx
            if pos == 1:
                return 'kanchan'
            if pos == 0 and idx % 9 == 6:
                return 'penchan'
            if pos == 2 and idx % 9 == 0:
                return 'penchan'
            return 'ryanmen'
    return 'shanpon'


def point_table_ron(han: int, fu: int, dealer: bool) -> int:
    if han >= 13:
        return YONBAIMAN_PARENT if dealer else YONBAIMAN_CHILD
    if han >= 11:
        return SANBAIMAN_PARENT if dealer else SANBAIMAN_CHILD
    if han >= 8:
        return BAIMAN_PARENT if dealer else BAIMAN_CHILD
    if han >= 6:
        return HANEMAN_PARENT if dealer else HANEMAN_CHILD
    base = fu * (2 ** (han + 2))
    if han >= 5 or ((dealer and base * 6 >= 12000) or ((not dealer) and base * 4 >= 8000)):
        return MANGAN_PARENT if dealer else MANGAN_CHILD
    mult = 6 if dealer else 4
    return ((base * mult + 99) // 100) * 100


def point_table_tsumo(han: int, fu: int, dealer: bool) -> Tuple[int, int, int]:
    if han >= 13:
        return (YONBAIMAN_PARENT, 16000, 16000) if dealer else (YONBAIMAN_CHILD, 8000, 16000)
    if han >= 11:
        return (SANBAIMAN_PARENT, 12000, 12000) if dealer else (SANBAIMAN_CHILD, 6000, 12000)
    if han >= 8:
        return (BAIMAN_PARENT, 8000, 8000) if dealer else (BAIMAN_CHILD, 4000, 8000)
    if han >= 6:
        return (HANEMAN_PARENT, 6000, 6000) if dealer else (HANEMAN_CHILD, 3000, 6000)
    base = fu * (2 ** (han + 2))
    if han >= 5 or ((dealer and base * 6 >= 12000) or ((not dealer) and base * 4 >= 8000)):
        return (MANGAN_PARENT, 4000, 4000) if dealer else (MANGAN_CHILD, 2000, 4000)
    if dealer:
        each = ((base * 2 + 99) // 100) * 100
        return each * 3, each, each
    child = ((base + 99) // 100) * 100
    parent = ((base * 2 + 99) // 100) * 100
    return child * 2 + parent, child, parent


def calculate_fu(decomp: List[Tuple[str, int]], ctx: WinContext, yaku_names: Iterable[str]) -> int:
    names = set(yaku_names)
    if '七対子' in names:
        return 25
    if '平和' in names and ctx.is_tsumo:
        return 20
    fu = 20
    pair = next(idx for kind, idx in decomp if kind == 'pair')
    if yakuhai_han(pair, ctx.seat, ctx.round_wind):
        fu += 2
    if ctx.is_tsumo:
        fu += 2
    else:
        fu += 10
    wait = wait_type(decomp, tile_to_index(ctx.winning_tile), pair)
    if wait in ('kanchan', 'penchan', 'tanki'):
        fu += 2
    for kind, idx in decomp:
        if kind == 'triplet':
            fu += 8 if is_terminal_or_honor(idx) else 4
    for meld in ctx.open_melds + ctx.closed_melds:
        idx = tile_to_index(meld.tiles[0])
        if meld.kind == 'triplet':
            fu += 4 if is_terminal_or_honor(idx) else 2
        elif meld.kind in ('minkan', 'kakan'):
            fu += 16 if is_terminal_or_honor(idx) else 8
        elif meld.kind == 'ankan':
            fu += 32 if is_terminal_or_honor(idx) else 16
    return ((fu + 9) // 10) * 10


def eval_standard(counts: List[int], decomp: List[Tuple[str, int]], ctx: WinContext) -> Tuple[int, int, List[Tuple[str, int]], int]:
    pair = next(idx for kind, idx in decomp if kind == 'pair')
    triplets = [idx for kind, idx in decomp if kind == 'triplet']
    sequences = [idx for kind, idx in decomp if kind == 'sequence']
    all_counts = counts[:]
    for meld in ctx.open_melds + ctx.closed_melds:
        for t in meld.tiles:
            all_counts[tile_to_index(t)] += 1
    triplet_like = triplets + [tile_to_index(m.tiles[0]) for m in ctx.open_melds + ctx.closed_melds if m.kind in ('triplet', 'ankan', 'minkan', 'kakan')]
    sequence_like = sequences + [tile_to_index(m.tiles[0]) for m in ctx.open_melds if m.kind == 'sequence']
    quads = [m for m in ctx.open_melds + ctx.closed_melds if m.kind in ('ankan', 'minkan', 'kakan')]

    yakuman_names: List[str] = []
    if is_ryuuiisou(all_counts):
        yakuman_names.append('緑一色')
    if sum(1 for x in triplet_like if x in (31, 32, 33)) == 3:
        yakuman_names.append('大三元')
    wind_trip = sum(1 for x in triplet_like if x in (27, 28, 29, 30))
    if wind_trip == 4:
        yakuman_names.append('大四喜')
    elif wind_trip == 3 and pair in (27, 28, 29, 30):
        yakuman_names.append('小四喜')
    if len(quads) == 4:
        yakuman_names.append('四槓子')
    if len(triplets) == 4 and pair == tile_to_index(ctx.winning_tile):
        yakuman_names.append('四暗刻')
    if ctx.is_tsumo and ctx.is_tenhou:
        yakuman_names.append('天和')
    if ctx.is_tsumo and ctx.is_chiihou:
        yakuman_names.append('地和')
    if yakuman_names:
        return 0, 0, [(name, 13) for name in dict.fromkeys(yakuman_names)], len(dict.fromkeys(yakuman_names))

    yaku: Dict[str, int] = {}
    if len(ctx.open_melds) == 0 and ctx.is_tsumo:
        yaku['門前清自摸和'] = 1
    if ctx.is_double_riichi:
        yaku['ダブル立直'] = 2
    elif ctx.is_riichi:
        yaku['立直'] = 1
    if ctx.is_chankan:
        yaku['槍槓'] = 1
    if ctx.is_rinshan:
        yaku['嶺上開花'] = 1
    if ctx.is_haitei:
        yaku['海底撈月'] = 1
    if ctx.is_houtei:
        yaku['河底撈魚'] = 1
    if all(not is_terminal_or_honor(i) for i, c in enumerate(all_counts) for _ in range(c)):
        yaku['断么九'] = 1
    seq_counter: Dict[int, int] = {}
    for s in sequences:
        seq_counter[s] = seq_counter.get(s, 0) + 1
    if len(ctx.open_melds) == 0:
        pair_seq = sum(v // 2 for v in seq_counter.values())
        if pair_seq >= 2:
            yaku['二盃口'] = 3
        elif pair_seq >= 1:
            yaku['一盃口'] = 1
    yakuhai = sum(yakuhai_han(idx, ctx.seat, ctx.round_wind) for idx in triplet_like)
    if yakuhai:
        yaku['役牌'] = yakuhai
    if len(triplet_like) == 4:
        yaku['対々和'] = 2
    closed_trip = len(triplets) + sum(1 for m in ctx.closed_melds if m.kind == 'ankan')
    if closed_trip >= 3:
        yaku['三暗刻'] = 2
    if len(quads) >= 3:
        yaku['三槓子'] = 2
    for num in range(9):
        if all(x in triplet_like for x in (num, num + 9, num + 18)):
            yaku['三色同刻'] = 2
            break
    for num in range(7):
        if all(x in sequence_like for x in (num, num + 9, num + 18)):
            yaku['三色同順'] = 2 if len(ctx.open_melds) == 0 else 1
            break
    for suit in range(3):
        suit_bases = {x % 9 for x in sequence_like if x // 9 == suit}
        if {0, 3, 6}.issubset(suit_bases):
            yaku['一気通貫'] = 2 if len(ctx.open_melds) == 0 else 1
            break
    if all(all_counts[i] == 0 or is_terminal_or_honor(i) for i in range(34)):
        yaku['混老頭'] = 2
    unique_suits = {i // 9 for i in range(27) if all_counts[i] > 0}
    has_honor = any(all_counts[i] > 0 for i in range(27, 34))
    if len(unique_suits) == 1 and has_honor:
        yaku['混一色'] = 3 if len(ctx.open_melds) == 0 else 2
    if len(unique_suits) == 1 and not has_honor:
        yaku['清一色'] = 6 if len(ctx.open_melds) == 0 else 5
    if sum(1 for x in triplet_like if x in (31, 32, 33)) == 2 and pair in (31, 32, 33):
        yaku['小三元'] = 2

    all_groups = [(k, i) for k, i in decomp if k != 'pair']
    all_groups.extend([(m.kind if m.kind == 'sequence' else 'triplet', tile_to_index(m.tiles[0])) for m in ctx.open_melds + ctx.closed_melds])
    def group_has_yaochu(kind: str, idx: int) -> bool:
        if kind == 'sequence':
            return idx % 9 in (0, 6)
        return is_terminal_or_honor(idx)
    if all(group_has_yaochu(kind, idx) for kind, idx in all_groups) and is_terminal_or_honor(pair):
        if any(i >= 27 for _, i in all_groups) or pair >= 27:
            yaku['混全帯么九'] = 2 if len(ctx.open_melds) == 0 else 1
        else:
            yaku['純全帯么九'] = 3 if len(ctx.open_melds) == 0 else 2

    if len(ctx.open_melds) == 0 and len(sequences) == 4 and yakuhai_han(pair, ctx.seat, ctx.round_wind) == 0:
        if wait_type(decomp, tile_to_index(ctx.winning_tile), pair) == 'ryanmen':
            yaku['平和'] = 1

    han = sum(yaku.values())
    if han == 0:
        return 0, 0, [], 0
    yaku_names = list(yaku.items())
    fu = calculate_fu(decomp, ctx, yaku.keys())
    return han, fu, yaku_names, 0


def evaluate_hand(closed_tiles: List[str], ctx: WinContext) -> HandScore | None:
    all_counts = tiles_to_counts(closed_tiles)
    for meld in ctx.open_melds + ctx.closed_melds:
        for t in meld.tiles:
            all_counts[tile_to_index(t)] += 1
    best: HandScore | None = None

    if is_kokushi(all_counts):
        ron = YAKUMAN_BASE_PARENT if ctx.seat == 0 else YAKUMAN_BASE_CHILD
        total, c, p = point_table_tsumo(13, 0, ctx.seat == 0)
        return HandScore(13, 0, [('国士無双', 13)], 1, total, ron, c, p)

    if is_chiitoitsu(all_counts) and len(ctx.open_melds) == 0:
        yaku = {'七対子': 2}
        if ctx.is_tsumo:
            yaku['門前清自摸和'] = 1
        if ctx.is_double_riichi:
            yaku['ダブル立直'] = 2
        elif ctx.is_riichi:
            yaku['立直'] = 1
        han = sum(yaku.values())
        if han > 0:
            ron = point_table_ron(han, 25, ctx.seat == 0)
            total, c, p = point_table_tsumo(han, 25, ctx.seat == 0)
            best = HandScore(han, 25, list(yaku.items()), 0, total, ron, c, p)

    for decomp in standard_decompositions(all_counts):
        han, fu, yaku, yakuman = eval_standard(tiles_to_counts(closed_tiles), decomp, ctx)
        if yakuman:
            ron = (YAKUMAN_BASE_PARENT if ctx.seat == 0 else YAKUMAN_BASE_CHILD) * yakuman
            total, c, p = point_table_tsumo(13 * yakuman, 0, ctx.seat == 0)
            cand = HandScore(13 * yakuman, 0, yaku, yakuman, total, ron, c, p)
        elif han > 0:
            ron = point_table_ron(han, fu, ctx.seat == 0)
            total, c, p = point_table_tsumo(han, fu, ctx.seat == 0)
            cand = HandScore(han, fu, yaku, 0, total, ron, c, p)
        else:
            continue
        if best is None or (cand.ron_points, cand.han, cand.fu) > (best.ron_points, best.han, best.fu):
            best = cand
    return best


def winning_tiles_for_tenpai(closed_tiles: List[str], open_melds: List[Meld], closed_melds: List[Meld], seat: int, round_wind: int) -> List[str]:
    counts = tiles_to_counts(closed_tiles)
    result: List[str] = []
    for i in range(34):
        if counts[i] >= 4:
            continue
        trial = closed_tiles + [index_to_tile(i)]
        ctx = WinContext(
            seat=seat,
            round_wind=round_wind,
            is_tsumo=True,
            is_riichi=False,
            is_double_riichi=False,
            is_ippatsu=False,
            is_rinshan=False,
            is_chankan=False,
            is_haitei=False,
            is_houtei=False,
            is_tenhou=False,
            is_chiihou=False,
            open_melds=open_melds,
            closed_melds=closed_melds,
            winning_tile=index_to_tile(i),
        )
        if evaluate_hand(trial, ctx) is not None:
            result.append(index_to_tile(i))
    return result
