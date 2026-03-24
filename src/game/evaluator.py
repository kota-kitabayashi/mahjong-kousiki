# これは将来クラス
from __future__ import annotations

# クラスを使いやすくするデータクラス
from dataclasses import dataclass
# 計算結果を覚えておき、再計算せずにすぐ応答できる機能を関数に与える
from functools import lru_cache

# 型を詳細に書きたいときのtyping。
# list[str] = ["waa", "uoo"]みたいなことね
from typing import Dict, Iterable, List, Tuple

# 牌py(意味深)からMeld(面子クラス)、整数を牌に治す(27=白みたいな)index_to_tile
# 19字牌かを判定するis_terminal_or_honor、牌から整数に治す(白=27)tile_to_index
# 牌の数を数える
# is_honorはなんなんかよくわからない。使いたかったけどなぜか使ってないね
from .tile import Meld, index_to_tile, is_honor, is_terminal_or_honor, tile_to_index, tiles_to_counts
# ルールからいろんな定数を持ってくる
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


# アガリ判定が起こった時の状況を渡すクラスWinContextクラス
@dataclass
class WinContext:
    seat: int                   # 自風の位置
    round_wind: int             # 東風か南風か
    is_tsumo: bool              # ツモであるか
    is_riichi: bool             # 立直しているか
    is_double_riichi: bool      # ダブル立直しているか
    is_ippatsu: bool            # いっぱつであるか？これはいらんやろ
    is_rinshan: bool            # 嶺上であるか
    is_chankan: bool            # 槍槓であるか
    is_haitei: bool             # 海底撈月であるか
    is_houtei: bool             # ホーテイロンであるかどうか
    is_tenhou: bool             # 天和であるか
    is_chiihou: bool            # 地和であるか
    open_melds: List[Meld]      # 鳴き面子
    closed_melds: List[Meld]    # 手牌。暗槓の面子
    winning_tile: str           # あがった牌


# アガリ時の翻、符、役、点数等を渡すためのクラス
@dataclass
class HandScore:
    han: int                        # 何翻か 
    fu: int                         # 何符か
    yaku: List[Tuple[str, int]]     # 役の中身。[(立直, 1), (ホンイツ, 3)]みたいに、(役名, 翻数)のタプルがまとめられている
    yakuman: int                    # 何倍役満か？役満でない場合は0
    total_points: int               # 全て合わせた点数
    ron_points: int                 # ロンの時の点数
    tsumo_child_pay: int            # ツモの時、子供が払う点数
    tsumo_parent_pay: int           # ツモの時、親が払う点数


# 雀頭を除いた残りの牌を順子や刻子へ分解する関数
# counts = 残り枚数
# path = 現在までの分解結果
# out = 完成した分解候補の格納先
def _remove_melds(counts: List[int], path: List[Tuple[str, int]], out: List[List[Tuple[str, int]]]) -> None:
    # counts = [0] * 34これに対して枚数を付与したのがcountsに入っているイメージ。
    # countsの中でインデックス順に見て最初に残っている牌のインデックスをiに格納。なければ-1を格納。next(イテレータ)は
    # 今回next(ジェネレータ, -1)の形で作られており、ジェネレータではcountsの値が0以上のものを抽出してインデックスをiに格納する。
    i = next((j for j, c in enumerate(counts) if c > 0), -1)
    
    # countsが空
    # pathからコピーしてきてoutに格納し、終わる
    if i == -1:
        out.append(path.copy())
        return
    
    # iの牌数が3以上の場合
    # 刻子をpathに格納していく
    if counts[i] >= 3:
        counts[i] -= 3                      # 3以上の牌のcountsを-3する
        path.append(('triplet', i))         # pathにtriplet(刻子)として格納
        _remove_melds(counts, path, out)    # 再帰
        path.pop()                          # pathをそのままは良くないのでpop
        counts[i] += 3                      # countsも回復
        
    # iの数が数牌で、i+1、i+2の牌がある場合
    # 順子をpathに格納していく
    if i < 27 and i % 9 <= 6 and counts[i + 1] > 0 and counts[i + 2] > 0:
        counts[i] -= 1                      # 順子に使う牌たちをcountsから消す
        counts[i + 1] -= 1
        counts[i + 2] -= 1
        path.append(('sequence', i))        # pathにsequence(順子)として格納        ※シークエンスは、「連続」、「一連のもの」という意味らしい。スケートのジャンプシークエンスはジャンプを続けてするから、シークエンスってつくんだと初めて知った。ウケる
        _remove_melds(counts, path, out)    # 再帰
        path.pop()
        counts[i] += 1                      #countsに復活させる
        counts[i + 1] += 1
        counts[i + 2] += 1


# 通常手の全ての分解形を列挙する関数
# [0,3,1,0,0, ...]みたいな牌の配列を分解形をすべて列挙したタプルをまとめたタプルを出力する。キャッシュ付き
# ＊＊＊＊＊　なぜ「リスト→タプル→リスト」という流れで入力したり、出力したりされているのか？　＊＊＊＊＊
# 後に出てくるstandard_decompositionsではcounts_key(counts)をリストにして、
# なぜこっちに来るときにタプルにしているかというと簡潔に言えばキャッシュを使うからである。
# lru_cacheは引数がハッシュ可能でないと用いることができない。リストは可変なのでハッシュ不可
# タプルは不変なのでハッシュ可能である。よってハッシュ可能なタプルで渡しているのだ。ちなみに戻り値に関しては
# lru_cacheが拒否するわけではないが、可変であるリストを使ってキャッシュすると外側からそのリストを変えられた時に
# キャッシュそのものが壊れる可能性があるため、不変なタプルを用いている。
# じゃあ！！すべてタプルでいいじゃねええか！という疑問が生まれてくるが、counts[i] += 2とかができなくなるので
# この関数の内部でも他の所でもcountsみたいなものはリストで扱いたいのである。
# よって_standard_decompositionsに入れるときだけ　リスト→タプル→リスト　という不自然な流れが生まれるのだ
@lru_cache(maxsize=None)
def _standard_decompositions(counts_key: Tuple[int, ...]) -> Tuple[Tuple[Tuple[str, int], ...], ...]:
    counts = list(counts_key)                               # counts_keyをリスト化
    result: List[List[Tuple[str, int]]] = []                # resultをあらかじめ用意
    
    # この関数では雀頭を抜いてから_remove_meldsしている
    # よってすべての牌において2つであればそれを一旦雀頭としておき、その他の部分で_remove_meldsを実施する
    for i in range(34):
        if counts[i] >= 2:
            counts[i] -= 2                                  # countsで指定の牌を2個減らす
            partial: List[List[Tuple[str, int]]] = []       # partialを用意し、それをresultに繋げる
            _remove_melds(counts, [('pair', i)], partial)   # pathにpair(雀頭)を追加した状態でremove_meldsする
            result.extend(partial)
            counts[i] += 2                                  # countsを元に戻す
    return tuple(tuple(x) for x in result)                  # タプルにして出力


# 通常手の全ての分解形を列挙する関数
# _standard_decompositionsはキャッシュを使用したり、そのためにタプルにしたりと外部向けではないため
# 外部窓口用のこの関数を設置している
def standard_decompositions(counts: List[int]) -> List[List[Tuple[str, int]]]:
    return [list(x) for x in _standard_decompositions(tuple(counts))]   # 説明通りリスト化し出力


# 七対子が成立しているか判定する関数
def is_chiitoitsu(counts: List[int]) -> bool:
    return len([c for c in counts if c == 2]) == 7      # countsの中に2枚の牌が7ペアあるか確認している


# 国士無双が成立しているか判定する関数
def is_kokushi(counts: List[int]) -> bool:
    req = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
    # reqがすべて一枚以上あるか＆countsが14枚であるか＆reqの中の牌で2枚ある牌が1種類だけあるかを確認している
    return all(counts[i] >= 1 for i in req) and sum(counts) == 14 and sum(counts[i] == 2 for i in req) == 1


# 緑一色が成立しているか判定する関数
def is_ryuuiisou(counts: List[int]) -> bool:
    allowed = {19, 20, 21, 23, 25, 32}
    # 牌が0ならスルー or iがallowedの牌であるかについて確認している
    # countsに格納されている牌において牌数0でない時にその牌がallowedの牌であるかということ
    return all(c == 0 or i in allowed for i, c in enumerate(counts))


# 役牌の翻数を返す関数
# index=刻子の牌、seat=自風、round_wind=場風
def yakuhai_han(index: int, seat: int, round_wind: int) -> int:
    han = 0
    if index in (31, 32, 33):       # 三元牌
        han += 1
    if index == 27 + seat:          # 自風の時
        han += 1
    if index == 27 + round_wind:    # 場風の時
        han += 1
    return han


# 待ち方を判定する関数
def wait_type(decomp: List[Tuple[str, int]], win_idx: int, pair: int) -> str:
    # 雀頭にアガリ牌が含まれる時は単騎待ち
    if pair == win_idx:
        return 'tanki'
    
    # decompから面子を取ってきて判定
    for kind, idx in decomp:
        # 面子の種類が順子でアガリ牌がその順子にあるか？
        if kind == 'sequence' and idx <= win_idx <= idx + 2:
            pos = win_idx - idx             # アガリ牌と順子の最初の牌の差
            if pos == 1:                    # 1になる時は真ん中なのでカンチャン
                return 'kanchan'
            if pos == 0 and idx % 9 == 6:   # 789のペンチャンはここで判定
                return 'penchan'
            if pos == 2 and idx % 9 == 0:   # 123のペンチャンはここで判定
                return 'penchan'
            return 'ryanmen'                # その他は両面
    return 'shanpon'                        # 順子でない場合はシャンポン


# ロンの点数を計算する
def point_table_ron(han: int, fu: int, dealer: bool) -> int:
    # 4倍満の場合
    if han >= 13:
        return YONBAIMAN_PARENT if dealer else YONBAIMAN_CHILD
    
    # 3倍満の場合
    if han >= 11:
        return SANBAIMAN_PARENT if dealer else SANBAIMAN_CHILD
    
    # 倍満の場合
    if han >= 8:
        return BAIMAN_PARENT if dealer else BAIMAN_CHILD
    
    # 跳満の場合
    if han >= 6:
        return HANEMAN_PARENT if dealer else HANEMAN_CHILD
    
    # 基本点baseを計算し、親なら6倍、子なら4倍した数が満貫に到達していれば満貫へまとめる。その他は100点単位で切り上げ、点数とする
    base = fu * (2 ** (han + 2))
    if han >= 5 or ((dealer and base * 6 >= 12000) or ((not dealer) and base * 4 >= 8000)):
        return MANGAN_PARENT if dealer else MANGAN_CHILD
    mult = 6 if dealer else 4
    return ((base * mult + 99) // 100) * 100        # ここで+99とすることで切り上げ処理をしている


# ツモの点数を計算する
# 出力は(点数の合計, 子の支払い, 親の支払い)となっている。あがった人が親であるときには親の支払いも表示になってしまっているが、しゃーなし
def point_table_tsumo(han: int, fu: int, dealer: bool) -> Tuple[int, int, int]:
    # 4倍満の場合
    if han >= 13:
        return (YONBAIMAN_PARENT, 16000, 16000) if dealer else (YONBAIMAN_CHILD, 8000, 16000)
    
    # 3倍満の場合
    if han >= 11:
        return (SANBAIMAN_PARENT, 12000, 12000) if dealer else (SANBAIMAN_CHILD, 6000, 12000)
    
    # 倍満の場合
    if han >= 8:
        return (BAIMAN_PARENT, 8000, 8000) if dealer else (BAIMAN_CHILD, 4000, 8000)
    
    # 跳満の場合
    if han >= 6:
        return (HANEMAN_PARENT, 6000, 6000) if dealer else (HANEMAN_CHILD, 3000, 6000)
    
    # 基本点baseを計算し、親なら6倍、子なら4倍した数が満貫に到達していれば満貫へまとめる。その他は100点単位で切り上げ、点数とする
    base = fu * (2 ** (han + 2))
    if han >= 5 or ((dealer and base * 6 >= 12000) or ((not dealer) and base * 4 >= 8000)):
        return (MANGAN_PARENT, 4000, 4000) if dealer else (MANGAN_CHILD, 2000, 4000)
    if dealer:
        each = ((base * 2 + 99) // 100) * 100       # 基本点を2倍にしてそれを100点単位で切り上げ
        return each * 3, each, each
    child = ((base + 99) // 100) * 100              # 基本点をそのまま100点単位切り上げ
    parent = ((base * 2 + 99) // 100) * 100         # 親は2倍
    return child * 2 + parent, child, parent


# 符計算をする関数
# decomp=分解形、ctx=アガリ状況、yaku_names=成立役名
# Iterable[str]はリストなどに限らない、順番に取り出せるもの。
def calculate_fu(decomp: List[Tuple[str, int]], ctx: WinContext, yaku_names: Iterable[str]) -> int:
    names = set(yaku_names)         # 重複がない役名の集合体を作成
    
    # 七対子の時は25符
    if '七対子' in names:               
        return 25
    
    # 平和の時は30符
    if '平和' in names and ctx.is_tsumo:
        return 20
    
    # 基本符を20符とし、まずは雀頭に注目する
    fu = 20
    pair = next(idx for kind, idx in decomp if kind == 'pair')
    
    # ＊＊＊警告＊＊＊　雀頭が役牌であれば2符付けようとしているが、ここはおかしいエラーが出る
    if yakuhai_han(pair, ctx.seat, ctx.round_wind):
        fu += 2
        
    # ツモであれば2符。その他はロンなので10符という処理だが、ロンで10符つくのは面前の時のみなのでこれはおかしい
    if ctx.is_tsumo:
        fu += 2
    else:
        fu += 10
        
    # 待ち方を抽出し、各待ち方について符を足す
    wait = wait_type(decomp, tile_to_index(ctx.winning_tile), pair)
    
    # カンチャン、ペンチャン、単騎の時は2符足す
    if wait in ('kanchan', 'penchan', 'tanki'):
        fu += 2
        
    # 刻子や槓子についての符計算を行う。まず手牌の刻子について行い、そのあと鳴いた面子に対して行う。
    for kind, idx in decomp:
        if kind == 'triplet':
            fu += 8 if is_terminal_or_honor(idx) else 4     # 手牌にある刻子が19字牌なら8符、それ以外なら4符
    for meld in ctx.open_melds + ctx.closed_melds:
        idx = tile_to_index(meld.tiles[0])                  # 牌を整数化
        if meld.kind == 'triplet':
            fu += 4 if is_terminal_or_honor(idx) else 2     # 副露にある刻子が19字牌なら4符、それ以外なら2符
        elif meld.kind in ('minkan', 'kakan'):
            fu += 16 if is_terminal_or_honor(idx) else 8    # 副露にある明槓が19字牌なら16符、それ以外なら8符
        elif meld.kind == 'ankan':
            fu += 32 if is_terminal_or_honor(idx) else 16   # 副露にある明槓が19字牌なら32符、それ以外なら16符
    return ((fu + 9) // 10) * 10                            # 符を10単位で切りあげて出力


# 面子手用。一つの分解形について、翻・符・役名、役満数を計算し、返す
def eval_standard(counts: List[int], decomp: List[Tuple[str, int]], ctx: WinContext) -> Tuple[int, int, List[Tuple[str, int]], int]:
    # まずは役や翻を出すための準備をする
    pair = next(idx for kind, idx in decomp if kind == 'pair')      # 雀頭は1つしかないためnext()を使う
    triplets = [idx for kind, idx in decomp if kind == 'triplet']   # 刻子を格納したリスト
    sequences = [idx for kind, idx in decomp if kind == 'sequence'] # 順子を格納したリスト
    
    all_counts = counts[:]  # countsをコピー
    
    # 手牌と鳴き面子を合わせる作業。
    # まずall_countsにすべての牌を格納するため鳴き面子の牌を追加で格納
    for meld in ctx.open_melds + ctx.closed_melds:
        for t in meld.tiles:
            all_counts[tile_to_index(t)] += 1
            
    # 手牌と鳴き面子を合わせたtriplet_like, sequence_likeを作成。槓子をmeldから取り出し、quadsを作成
    triplet_like = triplets + [tile_to_index(m.tiles[0]) for m in ctx.open_melds + ctx.closed_melds if m.kind in ('triplet', 'ankan', 'minkan', 'kakan')]
    sequence_like = sequences + [tile_to_index(m.tiles[0]) for m in ctx.open_melds if m.kind == 'sequence']
    quads = [m for m in ctx.open_melds + ctx.closed_melds if m.kind in ('ankan', 'minkan', 'kakan')]

    # 役満を判定する。
    # なぜすべての役満について関数を作らないのかは不明。優先度は低いが、作るべき
    yakuman_names: List[str] = []
    if is_ryuuiisou(all_counts):                                        # 緑一色は関数を使って判定
        yakuman_names.append('緑一色')
    if sum(1 for x in triplet_like if x in (31, 32, 33)) == 3:          # 鳴いていても良いのでtriplet_likeに白發中があれば
        yakuman_names.append('大三元')
    wind_trip = sum(1 for x in triplet_like if x in (27, 28, 29, 30))   # 大四喜と小四喜のためのwind_tripを作成
    if wind_trip == 4:                                                  # wind_tripが4つであれば大四喜
        yakuman_names.append('大四喜')
    elif wind_trip == 3 and pair in (27, 28, 29, 30):                   # 3つとpairであれば小四喜、elifを使う。
        yakuman_names.append('小四喜')
    if len(quads) == 4:                                                 # 4つ槓があれば4槓子
        yakuman_names.append('四槓子')
    if len(triplets) == 4 and pair == tile_to_index(ctx.winning_tile):  # 四暗刻単騎の判定になっているので、四暗刻の判定にすべき
        yakuman_names.append('四暗刻')
    if ctx.is_tsumo and ctx.is_tenhou:                                  # ツモで、天和であれば
        yakuman_names.append('天和')
    if ctx.is_tsumo and ctx.is_chiihou:                                 # ツモで、地和であれば
        yakuman_names.append('地和')
    if yakuman_names:                                                   # 役満があれば、その時点でreturn
        # 翻数0, 符数0, [(役満の名前, 翻数)], 役満数
        return 0, 0, [(name, 13) for name in dict.fromkeys(yakuman_names)], len(dict.fromkeys(yakuman_names))

    # 役を判定する
    # 役を入れるためのyakuを作成
    yaku: Dict[str, int] = {}
    if len(ctx.open_melds) == 0 and ctx.is_tsumo:   # 鳴いてない上に、ツモなら門前清自摸和成立
        yaku['門前清自摸和'] = 1
    if ctx.is_double_riichi:                        # ダブル立直していればダブりー
        yaku['ダブル立直'] = 2
    elif ctx.is_riichi:                             # ダブりーしていない時、リーチしていれば立直
        yaku['立直'] = 1
    if ctx.is_chankan:                              # 槍槓が発生したら槍槓
        yaku['槍槓'] = 1
    if ctx.is_rinshan:                              # 嶺上であがれば嶺上
        yaku['嶺上開花'] = 1
    if ctx.is_haitei:                               # 海底なら海底撈月
        yaku['海底撈月'] = 1
    if ctx.is_houtei:                               # 河底なら河底撈魚
        yaku['河底撈魚'] = 1
    if all(not is_terminal_or_honor(i) for i, c in enumerate(all_counts) for _ in range(c)):    # 全ての牌が2~8なら
        yaku['断么九'] = 1
    
    # 同じ順子を数えて、二盃口や一盃口を判定する
    # seq_counter={順子の一番初めの牌: その順子が何回出てきたか, ...}
    # {0: 2, 2:, 1}は123が2個、345が1個みたいなものを作る。
    seq_counter: Dict[int, int] = {}
    for s in sequences:                                         # sequencesは分解形
        seq_counter[s] = seq_counter.get(s, 0) + 1              # seq_counter.get(s, 0)はsがまだなければ0を格納。あればそれを格納。それに+1
    if len(ctx.open_melds) == 0:                                # 面前なら                             
        pair_seq = sum(v // 2 for v in seq_counter.values())    # 同じ順子の組み合わせが何個あるか？
        if pair_seq >= 2:                                       # 2つあると二盃口
            yaku['二盃口'] = 3
        elif pair_seq >= 1:                                     # 1つあると一盃口
            yaku['一盃口'] = 1
    
    # これは役牌が何個あるか
    yakuhai = sum(yakuhai_han(idx, ctx.seat, ctx.round_wind) for idx in triplet_like)
    if yakuhai:
        yaku['役牌'] = yakuhai
    if len(triplet_like) == 4:  # 対々和は刻子(triplet_like)が4つ
        yaku['対々和'] = 2
        
    # 暗刻がいくつあるかの判定するclosed_tripを作成
    closed_trip = len(triplets) + sum(1 for m in ctx.closed_melds if m.kind == 'ankan')
    if closed_trip >= 3:                                                # しかし、ロンでできた刻子も入れてしまう
        yaku['三暗刻'] = 2
    if len(quads) >= 3:                                                 # 3つ槓があれば、3槓子
        yaku['三槓子'] = 2
    for num in range(9):                                                # 0~8について
        if all(x in triplet_like for x in (num, num + 9, num + 18)):    # 萬,筒,索の全てで同じ数の刻子があるか
            yaku['三色同刻'] = 2
            break
    for num in range(7):                                                # 0~6について(順子は起点のみ)
        if all(x in sequence_like for x in (num, num + 9, num + 18)):   # 萬,筒,索の全てで同じ数の順子があるか
            yaku['三色同順'] = 2 if len(ctx.open_melds) == 0 else 1     # もし副露していれば1翻
            break
    for suit in range(3):                                               # 萬,筒,索に分ける
        suit_bases = {x % 9 for x in sequence_like if x // 9 == suit}   # 今見てる牌の種類かを確認し、x % 9を格納
        if {0, 3, 6}.issubset(suit_bases):                              # suit_basesに{0, 3, 6}が全てあるかどうか？
            yaku['一気通貫'] = 2 if len(ctx.open_melds) == 0 else 1     # もし副露していれば1翻
            break
    if all(all_counts[i] == 0 or is_terminal_or_honor(i) for i in range(34)):   # 19字牌かどうかの確認
        yaku['混老頭'] = 2
    
    # ここで一色手を判定
    unique_suits = {i // 9 for i in range(27) if all_counts[i] > 0}     # 数牌部分でどの種類の牌が含まれているかを萬子=0,筒子=1,索子=2で分ける。setなので重複なし
    has_honor = any(all_counts[i] > 0 for i in range(27, 34))           # 字牌を1枚でも持っているかどうか
    if len(unique_suits) == 1 and has_honor:                            # 数牌が一色で、字牌を持っているならホンイツ
        yaku['混一色'] = 3 if len(ctx.open_melds) == 0 else 2           # 鳴いているなら2翻
    if len(unique_suits) == 1 and not has_honor:                        # 数牌のみの場合は清一色
        yaku['清一色'] = 6 if len(ctx.open_melds) == 0 else 5           # 鳴いているなら5翻
    if sum(1 for x in triplet_like if x in (31, 32, 33)) == 2 and pair in (31, 32, 33): # 3元牌の刻子が2つと、雀頭が一つ
        yaku['小三元'] = 2

    # 帯么九関連の判定
    # まず、雀頭を除いた分解形(手牌)と鳴き面子をallgroupに格納し、そこからそれらが役を満たすか確認
    all_groups = [(k, i) for k, i in decomp if k != 'pair']
    # 鳴き面子をallgroupにdecompと同じようなタプル(面子の種類, 始まりの牌)の形式で追加
    all_groups.extend([(m.kind if m.kind == 'sequence' else 'triplet', tile_to_index(m.tiles[0])) for m in ctx.open_melds + ctx.closed_melds])
    
    # 帯么九面子であるかどうかの確認する関数
    def group_has_yaochu(kind: str, idx: int) -> bool:
        if kind == 'sequence':
            return idx % 9 in (0, 6)        # 順子が条件を満たすか
        return is_terminal_or_honor(idx)    # 順子でない場合、19字牌か？
    
    # 面子の全てが帯么九面子であるかを確認し、雀頭が19字牌かどうかを確認
    if all(group_has_yaochu(kind, idx) for kind, idx in all_groups) and is_terminal_or_honor(pair):
        if any(i >= 27 for _, i in all_groups) or pair >= 27:           # 字牌があれば
            yaku['混全帯么九'] = 2 if len(ctx.open_melds) == 0 else 1   # 混全帯么九。鳴いたら1翻
        else:                                                           # 字牌がなければ
            yaku['純全帯么九'] = 3 if len(ctx.open_melds) == 0 else 2   # 純全帯么九。鳴いたら2翻

    # 平和の判定
    # 鳴いていない＆順子が4つある＆役牌がない
    if len(ctx.open_melds) == 0 and len(sequences) == 4 and yakuhai_han(pair, ctx.seat, ctx.round_wind) == 0:
        if wait_type(decomp, tile_to_index(ctx.winning_tile), pair) == 'ryanmen':   # 待ち方が両面
            yaku['平和'] = 1

    han = sum(yaku.values())                        # yakuから翻数を取り出す
    if han == 0:                                    # 0翻なら0, 0, [], 0を返す
        return 0, 0, [], 0
    yaku_names = list(yaku.items())                 # yakuをリスト化し、yaku_namesを作成
    fu = calculate_fu(decomp, ctx, yaku.keys())     # 符計算
    return han, fu, yaku_names, 0                   # 出力


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
