from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple

from .evaluator import WinContext, evaluate_hand, winning_tiles_for_tenpai
from .logger import MahjongLogger
from .player import PlayerState
from .random_player import RandomPlayer
from .rules import HONBA_VALUE, RIICHI_STICK, ROUND_WIND_NAMES, SEAT_WIND_NAMES, START_SCORE, UMA_ONE_FLOAT, UMA_THREE_FLOAT, UMA_TWO_FLOAT
from .tile import Meld, index_to_tile, tile_sort_key, tile_to_index, tiles_to_string


@dataclass
class RoundResult:
    win: bool
    winner: int | None = None
    loser: int | None = None
    by_tsumo: bool = False
    renchan: bool = False
    reason: str = ''


class MahjongGame:
    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)
        self.players = [PlayerState(i, START_SCORE) for i in range(4)]
        self.ai = [RandomPlayer(self.random.randrange(1 << 30)) for _ in range(4)]
        self.logger = MahjongLogger('mahjong_log.txt')
        self.dealer = 0
        self.round_wind = 0
        self.round_number = 1
        self.honba = 0
        self.riichi_sticks = 0
        self.wall: List[str] = []
        self.dead_wall: List[str] = []
        self.dora_indicator = ''
        self.rinshan: List[str] = []
        self.current_turn = 0
        self.last_discard: str | None = None
        self.last_discarder: int | None = None
        self.first_cycle = True

    def build_wall(self) -> List[str]:
        wall = [index_to_tile(i) for i in range(34) for _ in range(4)]
        self.random.shuffle(wall)
        return wall

    def setup_round(self) -> None:
        self.wall = self.build_wall()
        self.dead_wall = self.wall[-14:]
        self.wall = self.wall[:-14]
        self.rinshan = self.dead_wall[:4]
        self.dora_indicator = self.dead_wall[4]
        for p in self.players:
            p.reset_round_state()
        for _ in range(13):
            for i in range(4):
                self.players[(self.dealer + i) % 4].hand.append(self.wall.pop(0))
        for p in self.players:
            p.sort_hand()
        self.current_turn = self.dealer
        self.last_discard = None
        self.last_discarder = None
        self.first_cycle = True
        self.log_round_start()

    def log_round_start(self) -> None:
        name = f'{ROUND_WIND_NAMES[self.round_wind]}{self.round_number}局'
        self.logger.log(f'===== {name} {self.honba}本場 供託{self.riichi_sticks} =====')
        self.logger.log(f'山 {tiles_to_string(self.wall)}')
        for i in range(4):
            p = self.players[i]
            self.logger.log(f'{SEAT_WIND_NAMES[(i - self.dealer) % 4]}家手牌:{p.hand_string()}')
        self.logger.log(f'ドラ表示牌:{self.dora_indicator}')
        self.logger.log(self.score_line())

    def score_line(self) -> str:
        return '点数 ' + ' '.join(f'{SEAT_WIND_NAMES[(i - self.dealer) % 4]}家:{p.score}点' for i, p in enumerate(self.players))

    def is_last_draw(self) -> bool:
        return len(self.wall) == 0

    def can_riichi(self, seat: int) -> bool:
        p = self.players[seat]
        if p.riichi_declared or not p.is_menzen() or p.score < 1000:
            return False
        waits = winning_tiles_for_tenpai(p.hand, [], p.melds, seat, self.round_wind)
        return len(waits) > 0

    def draw_tile(self, seat: int, rinshan: bool = False) -> str:
        tile = self.rinshan.pop(0) if rinshan else self.wall.pop(0)
        self.players[seat].hand.append(tile)
        self.players[seat].sort_hand()
        return tile

    def try_tsumo(self, seat: int, drawn_tile: str, rinshan: bool = False) -> bool:
        p = self.players[seat]
        ctx = WinContext(
            seat=(seat - self.dealer) % 4,
            round_wind=self.round_wind,
            is_tsumo=True,
            is_riichi=p.riichi_declared,
            is_double_riichi=p.double_riichi,
            is_ippatsu=False,
            is_rinshan=rinshan,
            is_chankan=False,
            is_haitei=self.is_last_draw(),
            is_houtei=False,
            is_tenhou=(seat == self.dealer and p.first_turn and self.first_cycle),
            is_chiihou=(seat != self.dealer and p.first_turn and self.first_cycle),
            open_melds=[m for m in p.melds if m.opened],
            closed_melds=[m for m in p.melds if not m.opened],
            winning_tile=drawn_tile,
        )
        score = evaluate_hand(p.hand, ctx)
        if score and self.ai[seat].choose_tsumo(True):
            self.apply_tsumo(seat, score)
            return True
        return False

    def try_ron_claimers(self, tile: str, discarder: int) -> bool:
        candidates: List[Tuple[int, object]] = []
        for offset in range(1, 4):
            seat = (discarder + offset) % 4
            p = self.players[seat]
            if tile in p.furiten_tiles or p.temp_furiten_turn:
                continue
            trial = p.hand + [tile]
            ctx = WinContext(
                seat=(seat - self.dealer) % 4,
                round_wind=self.round_wind,
                is_tsumo=False,
                is_riichi=p.riichi_declared,
                is_double_riichi=p.double_riichi,
                is_ippatsu=False,
                is_rinshan=False,
                is_chankan=False,
                is_haitei=False,
                is_houtei=(len(self.wall) == 0),
                is_tenhou=False,
                is_chiihou=False,
                open_melds=[m for m in p.melds if m.opened],
                closed_melds=[m for m in p.melds if not m.opened],
                winning_tile=tile,
            )
            result = evaluate_hand(trial, ctx)
            if result and self.ai[seat].choose_ron(True):
                candidates.append((seat, result))
            else:
                waits = winning_tiles_for_tenpai(p.hand, [m for m in p.melds if m.opened], [m for m in p.melds if not m.opened], (seat - self.dealer) % 4, self.round_wind)
                if tile in waits:
                    p.temp_furiten_turn = True
        if candidates:
            winner, score = candidates[0]
            self.apply_ron(winner, discarder, tile, score)
            return True
        return False

    def available_pon(self, seat: int, tile: str) -> bool:
        return self.players[seat].hand.count(tile) >= 2

    def available_chi_options(self, seat: int, tile: str) -> List[List[str]]:
        idx = tile_to_index(tile)
        if idx >= 27:
            return []
        suit = idx // 9
        num = idx % 9
        hand = self.players[seat].hand
        options: List[List[str]] = []
        for a, b in ((num - 2, num - 1), (num - 1, num + 1), (num + 1, num + 2)):
            if 0 <= a <= 8 and 0 <= b <= 8:
                t1 = index_to_tile(suit * 9 + a)
                t2 = index_to_tile(suit * 9 + b)
                if hand.count(t1) >= 1 and hand.count(t2) >= 1:
                    options.append([t1, tile, t2])
        return options

    def resolve_calls(self, tile: str, discarder: int) -> bool:
        pon_claimers = []
        for offset in range(1, 4):
            seat = (discarder + offset) % 4
            if self.available_pon(seat, tile) and self.ai[seat].choose_pon(True):
                pon_claimers.append(seat)
        if pon_claimers:
            seat = pon_claimers[0]
            p = self.players[seat]
            p.hand.remove(tile)
            p.hand.remove(tile)
            p.melds.append(Meld('triplet', [tile, tile, tile], True, tile, discarder))
            p.sort_hand()
            self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 ポン {tile}')
            self.current_turn = seat
            return True
        seat = (discarder + 1) % 4
        options = self.available_chi_options(seat, tile)
        choice = self.ai[seat].choose_chi(len(options))
        if choice >= 0:
            selected = options[choice]
            p = self.players[seat]
            for t in selected:
                if t != tile:
                    p.hand.remove(t)
            p.melds.append(Meld('sequence', sorted(selected, key=tile_sort_key), True, tile, discarder))
            p.sort_hand()
            self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 チー {"".join(selected)}')
            self.current_turn = seat
            return True
        return False

    def choose_and_discard(self, seat: int, drawn_tile: str | None) -> str:
        p = self.players[seat]
        if p.riichi_declared:
            idx = p.hand.index(drawn_tile) if drawn_tile in p.hand else len(p.hand) - 1
        else:
            idx = self.ai[seat].choose_discard(p.hand, drawn_tile)
        tile = p.hand.pop(idx)
        p.discards.append(tile)
        p.sort_hand()
        for x in set(p.discards):
            p.furiten_tiles.add(x)
        self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 打牌 {tile} 手牌:{p.hand_string()}')
        self.last_discard = tile
        self.last_discarder = seat
        return tile

    def maybe_declare_riichi(self, seat: int) -> None:
        p = self.players[seat]
        if self.can_riichi(seat) and self.ai[seat].choose_riichi(True):
            p.riichi_declared = True
            p.double_riichi = p.first_turn and self.first_cycle
            p.score -= RIICHI_STICK
            self.riichi_sticks += 1
            self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 立直!')

    def apply_tsumo(self, winner: int, score) -> None:
        w = self.players[winner]
        if winner == self.dealer:
            pay = score.tsumo_parent_pay + self.honba * 100
            for i in range(4):
                if i != winner:
                    self.players[i].score -= pay
                    w.score += pay
        else:
            child = score.tsumo_child_pay + self.honba * 100
            parent = score.tsumo_parent_pay + self.honba * 100
            for i in range(4):
                if i == winner:
                    continue
                payment = parent if i == self.dealer else child
                self.players[i].score -= payment
                w.score += payment
        w.score += self.riichi_sticks * 1000
        self.logger.log(f'ツモアガリ {SEAT_WIND_NAMES[(winner - self.dealer) % 4]}家 {score.han}翻{score.fu}符 {score.yaku} {self.score_line()}')
        self.riichi_sticks = 0
        self.round_end(RoundResult(True, winner, None, True, winner == self.dealer, 'tsumo'))

    def apply_ron(self, winner: int, loser: int, tile: str, score) -> None:
        payment = score.ron_points + self.honba * 300
        self.players[loser].score -= payment
        self.players[winner].score += payment + self.riichi_sticks * 1000
        self.logger.log(f'ロンアガリ {SEAT_WIND_NAMES[(winner - self.dealer) % 4]}家 <- {SEAT_WIND_NAMES[(loser - self.dealer) % 4]}家 {tile} {score.han}翻{score.fu}符 {score.yaku} {self.score_line()}')
        self.riichi_sticks = 0
        self.round_end(RoundResult(True, winner, loser, False, winner == self.dealer, 'ron'))

    def apply_draw(self) -> None:
        tenpais = []
        for i, p in enumerate(self.players):
            waits = winning_tiles_for_tenpai(p.hand, [m for m in p.melds if m.opened], [m for m in p.melds if not m.opened], (i - self.dealer) % 4, self.round_wind)
            tenpai = len(waits) > 0
            tenpais.append(tenpai)
            status = '聴牌' if tenpai else 'ノーテン'
            self.logger.log(f"{SEAT_WIND_NAMES[(i - self.dealer) % 4]}家 {status} 待ち:{''.join(waits)}")
        count = sum(tenpais)
        if count == 1:
            for i, flag in enumerate(tenpais):
                self.players[i].score += 3000 if flag else -1000
        elif count == 2:
            for i, flag in enumerate(tenpais):
                self.players[i].score += 1500 if flag else -1500
        elif count == 3:
            for i, flag in enumerate(tenpais):
                self.players[i].score += 1000 if flag else -3000
        self.logger.log(f'流局 {self.score_line()}')
        self.round_end(RoundResult(False, None, None, False, tenpais[self.dealer], 'draw'))

    def round_end(self, result: RoundResult) -> None:
        print(f'{ROUND_WIND_NAMES[self.round_wind]}{self.round_number}局 {self.honba}本場 結果:{result.reason} {self.score_line()}')
        if result.renchan:
            self.honba += 1
        else:
            self.honba = 0
            self.dealer = (self.dealer + 1) % 4
            self.round_number += 1
            if self.round_number == 5:
                self.round_number = 1
                self.round_wind += 1

    def play_round(self) -> None:
        self.setup_round()
        while True:
            if len(self.wall) == 0:
                self.apply_draw()
                return
            seat = self.current_turn
            p = self.players[seat]
            drawn = self.draw_tile(seat)
            self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 ツモ {drawn} 手牌:{p.hand_string()}')
            if self.try_tsumo(seat, drawn):
                return
            self.maybe_declare_riichi(seat)
            discard = self.choose_and_discard(seat, drawn)
            if self.try_ron_claimers(discard, seat):
                return
            if self.resolve_calls(discard, seat):
                for pl in self.players:
                    pl.temp_furiten_turn = False
                self.first_cycle = False
                continue
            p.first_turn = False
            for i in range(4):
                if i != seat:
                    self.players[i].temp_furiten_turn = False
            self.first_cycle = False
            if len(self.wall) == 0:
                self.apply_draw()
                return
            self.current_turn = (seat + 1) % 4

    def final_scores(self) -> List[Tuple[int, float]]:
        ranking = sorted([(i, p.score) for i, p in enumerate(self.players)], key=lambda x: (-x[1], x[0]))
        floats = sum(1 for _, s in ranking if s >= 30000)
        uma = UMA_ONE_FLOAT if floats == 1 else UMA_TWO_FLOAT if floats == 2 else UMA_THREE_FLOAT
        results = []
        for rank, (i, score) in enumerate(ranking):
            results.append((i, score / 1000 + uma[rank]))
        return sorted(results)

    def play_hanchan(self) -> None:
        while self.round_wind < 2:
            self.play_round()
        self.logger.log('===== 半荘終了 =====')
        for i, p in enumerate(self.players):
            self.logger.log(f'最終素点 {SEAT_WIND_NAMES[i]}:{p.score}')
        final = self.final_scores()
        for i, pt in final:
            print(f'{SEAT_WIND_NAMES[i]}家 最終素点:{self.players[i].score} 半荘スコア:{pt:.1f}')
            self.logger.log(f'{SEAT_WIND_NAMES[i]}家 半荘スコア:{pt:.1f}')
