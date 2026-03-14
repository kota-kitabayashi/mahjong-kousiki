# これは将来クラス
from __future__ import annotations

# パスもモジュール。パスの扱いが楽になる
from pathlib import Path


class MahjongLogger:
    # 麻雀ログクラス
    def __init__(self, path: str = 'logs/mahjong_log.txt') -> None:
        # このクラス生成時にpathを再設定し、テキストを空にする
        self.path = Path(path)
        self.path.write_text('', encoding='utf-8')

    def log(self, message: str) -> None:
        # ログを追記する
        with self.path.open('a', encoding='utf-8') as f:
            f.write(message + '\n')
