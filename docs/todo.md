# タスク一覧

## 未着手
- [] フリテン判定の機能確認と訂正(2-5m待ちで2mは捨てているけど、5mではロンアガリできてしまうかもしれない)
- [] 加槓の機能追加。evaluator.pyでは"kakan"というkindがmeldにあるように実装されているが、加槓はできないのではないか？
- [] Player.pyのPlayerStateクラス未活用インスタンス変数の削除検討と修正
- [] evaluator.pyのyakuhai_hanの下にyakuhai_huを追加し、雀頭用の動作を作る
- [] 役牌があるときに翻数を返すyakuhai_hanを雀頭での動作の際に使用しているため、それをyakuhai_huに置き換え、必要に応じてバグ修正を行う
- [] ロンで完成した刻子に関して明刻扱いになるか怪しいので修正を入れる
- [] evaluator.pyにおいてwait_typeが同じ分解形において複数の待ち方がある場合、これを検知できない。すべての待ち方を列挙し、それぞれについて点数を出すように設計するべきである。
- [] evaluator.pyのcalculate_fuについて、鳴いていてもロンしたら10符つくバグを修正
- [] evaluator.pyのeval_standardについて、四暗刻の判定が四暗刻単騎の判定になってしまっているため修正する。三暗刻と同じく、暗刻なのか、明刻なのかの判定を追加すべきである。
- [] evaluator.pyのeval_standardで役牌ではなく、役牌名を役の名前にしたい
- [] evaluator.pyのeval_standardがあまりにも関数をうまく使えていない。同じ処理については関数化し、見やすく、整えるべき
- [] evaluator.pyのevaluate_handについて七対子の複合役があまりに少ないので追加し是正する
- [] game.pyのMahjongGameクラスsetup_round関数での王牌の嶺上牌とドラ表示牌の位置が実際と異なる。