# これは将来クラス
from __future__ import annotations

# パスもモジュール。パスの扱いが楽になる
from pathlib import Path


# 麻雀ログクラス
class MahjongLogger:
    # このクラス生成時にpathを再設定し、テキストを空にする
    def __init__(self, path: str = 'logs/mahjong_log.txt') -> None:
        self.path = Path(path)
        self.path.write_text('', encoding='utf-8')

    # ログを追記する
    def log(self, message: str) -> None:
        with self.path.open('a', encoding='utf-8') as f:
            f.write(message + '\n')
