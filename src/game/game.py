# これは将来クラス
from __future__ import annotations

# randomとクラスを作りやすくするデータクラス。typingからリストとタプル
import random
from dataclasses import dataclass
from typing import List, Tuple

# 今まで作ったやつから色々持ってきてるってことよ！
from .evaluator import WinContext, evaluate_hand, winning_tiles_for_tenpai
from .logger import MahjongLogger
from .player import PlayerState
from .random_player import RandomPlayer
from .rules import HONBA_VALUE, RIICHI_STICK, ROUND_WIND_NAMES, SEAT_WIND_NAMES, START_SCORE, UMA_ONE_FLOAT, UMA_THREE_FLOAT, UMA_TWO_FLOAT
from .tile import Meld, index_to_tile, tile_sort_key, tile_to_index, tiles_to_string


# 局結果を返すRoundResult
@dataclass
class RoundResult:
    win: bool                   # アガリで終わったか？
    winner: int | None = None   # アガリ者の席番号
    loser: int | None = None    # 誰からロンしたか？
    by_tsumo: bool = False      # そのアガリがツモかどうか  
    renchan: bool = False       # 連荘しているかどうか
    reason: str = ''            # 結果の詳細を格納する。"tsumo", "ron"とか


# 麻雀ゲーム本体クラス
class MahjongGame:
    # 初期化関数
    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)                                           # 乱数生成器
        self.players = [PlayerState(i, START_SCORE) for i in range(4)]              # 4人のプレイヤーステートを作る
        self.ai = [RandomPlayer(self.random.randrange(1 << 30)) for _ in range(4)]  # 4人のプレイヤーを作る
        self.logger = MahjongLogger('mahjong_log.txt')                              # 麻雀ログを作る
        self.dealer = 0                         # 親は0
        self.round_wind = 0                     # 場風は0(東)
        self.round_number = 1                   # 局は0局
        self.honba = 0                          # 本場は0本
        self.riichi_sticks = 0                  # リー棒は出ていない
        self.wall: List[str] = []               # 牌山
        self.dead_wall: List[str] = []          # 王牌
        self.dora_indicator = ''                # ドラ表示牌
        self.rinshan: List[str] = []            # 槓専用ツモ牌
        self.current_turn = 0                   # 今、誰の手番か
        self.last_discard: str | None = None    # 直前に捨てられた牌
        self.last_discarder: int | None = None  # 直前に捨てられた牌を捨てた人のプレイヤー番号(0, 1, 2, 3で入る)
        self.first_cycle = True                 # まだ局の1巡目かどうか？ダブル立直や天和などに使う

    # 牌山を作成する関数
    # 34種各4枚の合計136枚の牌を作成しシャッフルする
    def build_wall(self) -> List[str]:
        wall = [index_to_tile(i) for i in range(34) for _ in range(4)]  # 34種各4枚の合計136枚の牌を作成
        self.random.shuffle(wall)                                       # シャッフル
        return wall

    # 1局開始時の初期化
    def setup_round(self) -> None:
        self.wall = self.build_wall()           # 山を作成
        self.dead_wall = self.wall[-14:]        # 王牌を作成
        self.wall = self.wall[:-14]             # 牌山から王牌分を削除
        self.rinshan = self.dead_wall[:4]       # 嶺上牌を王牌から作成
        self.dora_indicator = self.dead_wall[4] # ドラ表示牌を設定
        for p in self.players:                  # 各プレイヤーの局状態初期化
            p.reset_round_state()
        for _ in range(13):                     # 手牌を作成
            for i in range(4):
                self.players[(self.dealer + i) % 4].hand.append(self.wall.pop(0))
        for p in self.players:                  # 各プレイヤーの手牌を整列
            p.sort_hand()
        self.current_turn = self.dealer         # 親が最初の手番
        self.last_discard = None                # 直前に捨てられた牌はない
        self.last_discarder = None              # 捨てたやつもいねえ
        self.first_cycle = True                 # 1巡目
        self.log_round_start()                  # 開局ログを出す

    # 局初めのログ
    def log_round_start(self) -> None:
        name = f'{ROUND_WIND_NAMES[self.round_wind]}{self.round_number}局'                  # 「東何局」をnameに格納 
        self.logger.log(f'===== {name} {self.honba}本場 供託{self.riichi_sticks} =====')    # 「東何局」+「何本場 供託何本」をログ
        self.logger.log(f'山 {tiles_to_string(self.wall)}')                                 # 山を1m3mなどでログ
        for i in range(4):                                                                  # 各プレイヤーの手牌をログ
            p = self.players[i]
            self.logger.log(f'{SEAT_WIND_NAMES[(i - self.dealer) % 4]}家手牌:{p.hand_string()}')
        self.logger.log(f'ドラ表示牌:{self.dora_indicator}')    # ドラ表示牌をログ
        self.logger.log(self.score_line())                      # 各プレイヤーの点数をログ

    # 各プレイヤーの点数を返す関数
    # 点数 東家:12000点南家:34000点...といった文字列を返す
    def score_line(self) -> str:
        return '点数 ' + ' '.join(f'{SEAT_WIND_NAMES[(i - self.dealer) % 4]}家:{p.score}点' for i, p in enumerate(self.players))

    # 最後のツモかどうかを判定する関数
    def is_last_draw(self) -> bool:
        return len(self.wall) == 0  # 牌山に牌が0であればTrue

    # リーチできるかどうかを判定する関数
    def can_riichi(self, seat: int) -> bool:
        p = self.players[seat]
        # リーチしている or 面前ではない or スコアが1000点以下だと立直できない
        if p.riichi_declared or not p.is_menzen() or p.score < 1000:
            return False
        waits = winning_tiles_for_tenpai(p.hand, [], p.melds, seat, self.round_wind)    # 待ち牌があるかどうか
        return len(waits) > 0

    # 牌山から牌を引いて手牌に入れる関数
    def draw_tile(self, seat: int, rinshan: bool = False) -> str:
        tile = self.rinshan.pop(0) if rinshan else self.wall.pop(0) # 嶺上であれば嶺上牌を、そのほかは牌山から牌を引く
        self.players[seat].hand.append(tile)                        # 
        self.players[seat].sort_hand()                              # 
        return tile

    # ツモアガリできるかを判定し、プレイヤーにツモアガリするかを選択させる関数
    def try_tsumo(self, seat: int, drawn_tile: str, rinshan: bool = False) -> bool:
        p = self.players[seat]                          # プレイヤーを準備、p.何々などで使う
        ctx = WinContext(                               # アガリ状況を作成
            seat=(seat - self.dealer) % 4,
            round_wind=self.round_wind,
            is_tsumo=True,
            is_riichi=p.riichi_declared,                # プレイヤーが立直しているか
            is_double_riichi=p.double_riichi,           # プレイヤーがダブル立直しているか
            is_ippatsu=False,
            is_rinshan=rinshan,                         # 嶺上かどうか
            is_chankan=False,                           # 槍槓かどうか。ツモなので槍槓ではない
            is_haitei=self.is_last_draw(),              # 最後のツモかどうか
            is_houtei=False,
            is_tenhou=(seat == self.dealer and p.first_turn and self.first_cycle),  # 親＆最初のツモ＆１巡目かどうか
            is_chiihou=(seat != self.dealer and p.first_turn and self.first_cycle), # 子＆最初のツモ＆１巡目かどうか
            open_melds=[m for m in p.melds if m.opened],                            # 鳴き面子
            closed_melds=[m for m in p.melds if not m.opened],                      # 鳴き面子ではない確定面子、カンとか
            winning_tile=drawn_tile,                    # 引いた牌(ツモ牌)
        )
        score = evaluate_hand(p.hand, ctx)              # スコアを算出
        if score and self.ai[seat].choose_tsumo(True):  # スコアがあるか(NoneだとFalse)＆プレイヤーががツモというか
            self.apply_tsumo(seat, score)               # ツモアガリ処理
            return True
        return False                                    # ツモするかどうかをTrueFalseで返す

    # 今捨てられた牌をロンアガリできるかを判定し、プレイヤーにロンアガリするかを選択させる関数
    def try_ron_claimers(self, tile: str, discarder: int) -> bool:
        candidates: List[Tuple[int, object]] = []               # ロンできる人の候補一覧。[(席番号, アガリ結果)...]
        for offset in range(1, 4):                              # 牌を捨てた人以外を見る
            seat = (discarder + offset) % 4                     # discarder=2なら 3→1→2(下家、対面、上家の順)
            p = self.players[seat]
            if tile in p.furiten_tiles or p.temp_furiten_turn:  # フリテンなら飛ばす
                continue
            trial = p.hand + [tile]                             # その人の手牌にその牌を追加
            ctx = WinContext(
                seat=(seat - self.dealer) % 4,
                round_wind=self.round_wind,
                is_tsumo=False,
                is_riichi=p.riichi_declared,                    # プレイヤーが立直しているか
                is_double_riichi=p.double_riichi,               # プレイヤーがダブル立直しているか
                is_ippatsu=False,
                is_rinshan=False,
                is_chankan=False,                               # 槍槓かどうか。未実装
                is_haitei=False,
                is_houtei=(len(self.wall) == 0),                # なぜここでis_last_draw関数を使っていないのか？
                is_tenhou=False,
                is_chiihou=False,
                open_melds=[m for m in p.melds if m.opened],
                closed_melds=[m for m in p.melds if not m.opened],
                winning_tile=tile,                              # ロン牌
            )
            result = evaluate_hand(trial, ctx)                  # 点数
            if result and self.ai[seat].choose_ron(True):       # プレイヤーがロンするか？
                candidates.append((seat, result))
            else:                                               # プレイヤーがロンしなかったら
                waits = winning_tiles_for_tenpai(               # 聴牌が確認する
                    p.hand, [m for m in p.melds if m.opened],
                    [m for m in p.melds if not m.opened],
                    (seat - self.dealer) % 4, self.round_wind
                    )
                if tile in waits:                               # 聴牌してるのにロンしないなら
                    p.temp_furiten_turn = True                  # フリテン処理
        if candidates:                                          # ロンした人がいるなら
            winner, score = candidates[0]                       # 下家から
            self.apply_ron(winner, discarder, tile, score)      # ロン処理
            return True
        return False                                            # TFを返す

    # ポンできるかどうかを返す
    def available_pon(self, seat: int, tile: str) -> bool:
        return self.players[seat].hand.count(tile) >= 2     # その牌が2枚以上ならポンできるよ！

    # チーできるかを判定し、チー可能なパターンを返す
    def available_chi_options(self, seat: int, tile: str) -> List[List[str]]:
        idx = tile_to_index(tile)       # 1m→0みたいなこと
        if idx >= 27:                   # 字牌なら何もないリストを返す
            return []
        suit = idx // 9                 # 何牌か？
        num = idx % 9                   # 数をみる
        hand = self.players[seat].hand  # 手牌を代入
        options: List[List[str]] = []   # チー可能なパターンが入るoptions
        
        # 数牌の数numについて、3つのパターンでチーできるかどうかを判定する
        for a, b in ((num - 2, num - 1), (num - 1, num + 1), (num + 1, num + 2)):
            if 0 <= a <= 8 and 0 <= b <= 8:                     # -1にはならない
                t1 = index_to_tile(suit * 9 + a)                # 1mや8sなど牌にする
                t2 = index_to_tile(suit * 9 + b)                # 牌にする
                if hand.count(t1) >= 1 and hand.count(t2) >= 1: # 手牌にチーできる牌が2つともあれば
                    options.append([t1, tile, t2])              # optionsに追加
        return options                                          # optionsを返す

    # ロンがなかった後の鳴きを処理
    def resolve_calls(self, tile: str, discarder: int) -> bool:
        pon_claimers = []                                   # ポンしたいプレイヤーが入る
        for offset in range(1, 4):                          # 4人全員に聞く。
            seat = (discarder + offset) % 4
            if self.available_pon(seat, tile) and self.ai[seat].choose_pon(True):
                pon_claimers.append(seat)                   # ポンするなら候補に入れる
        if pon_claimers:                                    # ポンするならポン処理
            seat = pon_claimers[0]                          # ポンするなら
            p = self.players[seat]                          # プレイヤーを指定
            p.hand.remove(tile)                             # 牌を消す
            p.hand.remove(tile)
            p.melds.append(Meld('triplet', [tile, tile, tile], True, tile, discarder))      # 鳴き面子を入れる
            p.sort_hand()                                                                   # 手牌をソート
            self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 ポン {tile}')   # ログを吐く
            self.current_turn = seat                        # 手番を鳴いた人に移す
            return True
        seat = (discarder + 1) % 4                          # 出した人の下家
        options = self.available_chi_options(seat, tile)    # チーのオプションを出す
        choice = self.ai[seat].choose_chi(len(options))     # チーが可能かどうか？
        if choice >= 0:                                     # チョイスするかどうか
            selected = options[choice]                      # 選んだ鳴きパターン
            p = self.players[seat]
            for t in selected:                              # 鳴いた牌以外の牌は手牌から消す      
                if t != tile:
                    p.hand.remove(t)
            p.melds.append(Meld('sequence', sorted(selected, key=tile_sort_key), True, tile, discarder))    # 鳴き面子として登録
            p.sort_hand()                                                                                   # ソート
            self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 チー {"".join(selected)}')      # ログだす
            self.current_turn = seat                                                                        # 手番をその人にする
            return True
        return False

    # 誰が何を切るかを決め、局情報を更新する
    def choose_and_discard(self, seat: int, drawn_tile: str | None) -> str:
        p = self.players[seat]      # プレイヤーを決める
        if p.riichi_declared:       # リーチしていれば、自摸切り状態(自模った牌があれば違う牌を切る構造)
            idx = p.hand.index(drawn_tile) if drawn_tile in p.hand else len(p.hand) - 1
        else:                       # リーチでない場合はツモと打牌
            idx = self.ai[seat].choose_discard(p.hand, drawn_tile)
        tile = p.hand.pop(idx)      # 打牌した牌を手牌からなくす
        p.discards.append(tile)     # 河に出す
        p.sort_hand()               # 理牌
        for x in set(p.discards):   # 捨て牌にxがある場合、フリテンにする
            p.furiten_tiles.add(x)
        self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 打牌 {tile} 手牌:{p.hand_string()}')    # ログ
        self.last_discard = tile    # 最後の捨て牌をtileに定義
        self.last_discarder = seat  # 最後の捨てた人を更新
        return tile                 # 捨てた牌を戻り値

    # 立直処理
    def maybe_declare_riichi(self, seat: int) -> None:
        p = self.players[seat]                                          # 席
        if self.can_riichi(seat) and self.ai[seat].choose_riichi(True): # リーチできるかどうかを調べ、リーチ処理をする
            p.riichi_declared = True                                    # リーチをtrue
            p.double_riichi = p.first_turn and self.first_cycle         # 1巡目で一回目ならだぶりー
            p.score -= RIICHI_STICK                                     # リーチ棒を点数から引く
            self.riichi_sticks += 1                                     # リーチ棒を局として追加
            self.logger.log(f'{SEAT_WIND_NAMES[(seat - self.dealer) % 4]}家 立直!') # ログ

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
