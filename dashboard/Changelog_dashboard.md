# Changelog — Web ダッシュボード（app.py）

> app.py V3.0 から、ダッシュボードの変更履歴を本ファイルへ分離した
> （dvswitch_bot.py V1.92 の Changelog.md 分離と同じ整理方針）。
> リポジトリの Changelog.md にセクションとして統合しても、独立ファイルの
> ままでもよい。新しい版が上に来る降順で記載する。

---

## V3.21 (2026-08-13)

天気読み上げカードのレイアウト変更のみ（機能は V3.2 と同一）。

1. 🔵 左セルの縦積みから、「読み上げ内容」と同じ全幅カードへ移し、内部を「天気を付ける対象｜取得座標」の2カラム横並びにしてコンパクトにした。カードは save-form 内のままなので `weather_*` は従来どおり `/save_all` に送信される。
2. 非 JTW ノードのグレーアウト・保存ルート・検証はいずれも V3.2 から不変。

---

## V3.2 (2026-08-13)

天気読み上げ（JTW版）設定への対応と、保存ルートの欠陥修正。

1. 🔵 「天気読み上げ — JTW版」カードを新設（Bot 設定カードの下・左セル内）。次を編集できるようにした。
   - `WEATHER_ENABLED`（親スイッチ）
   - `WEATHER_ON_TIME_SIGNAL`（時報 :00・30分案内 :30 に付与）
   - `WEATHER_ON_MESSAGE`（定時メッセージ 001/002 に付与）
   - `WEATHER_LATITUDE` / `WEATHER_LONGITUDE`（取得座標）
   付与先を系統ごとに選べるのは dvswitch_bot.py / bot_setup.py **V2.04jtw** から。検証条件（付与先が最低1つ・座標必須・範囲）は三者で同一。
2. 🔵 JTW 以外のノードでは天気カードを丸ごとグレーアウトし、注記のみ表示（共有ダッシュボードの流儀。VOICEVOX 話者変更 UI と同じ考え方）。判定 `jtw_available()` は `/opt/dvswitch_bot/bin/voice_make.py` の存在、または bot の版文字列に "jtw" を含むか、を OR で判定する。
3. 🔴 未知キー保護を追加（V3.11 以前の欠陥の修正）。従来の保存ルートは bot_config.json を「ダッシュボードが知っているキーだけ」で作り直していたため、JTW ノードで保存すると `WEATHER_*` が黙って消えていた（JTW版 README の警告はこの挙動を指す）。V3.2 では既存ファイルを土台にして差分更新するため、ダッシュボードが知らないキーは保存しても失われない。将来 bot 側にキーが増えても、ダッシュボードを更新するまでの間に設定を壊さない。
4. 🔵 bot_config.json の組み立て・検証を `build_bot_cfg()` / `validate_bot_cfg()` に集約し、`/bot_config` と `/save_all` の重複（従来2箇所に同じ dict と assert が並んでいた）を解消した。検証条件の追加漏れが起きない構造にする。

---

## V3.11 (2026-07-14)

「保存して再生成」ボタンを保存行の右端へ移動（CSS のみ）。一括保存ボタンとの
取り違え防止（実運用フィードバック対応）。動作ロジックの変更はなし。

---

## V3.1 (2026-07-14)

読み上げテキストの編集を Open JTalk（Pi）ノードでも可能にした（共用対応の拡張）。
これまで読み上げ内容カードの入力UIは `voicevox_available()` で丸ごと隠していたため、
jtalk ノードでは閲覧のみだった。話者が1つの jtalk でもテキスト7項目を編集できるように
分離した。

1. 🔵 テンプレート: 7項目編集テーブル（コールサイン/読み・地名・メッセージ1,2/読み）
   と「保存して再生成」ボタンの表示条件を `voicevox_ok` から `wav_source.exists` へ変更
   （jtalk / VOICEVOX 両方で表示）。話者選択 select は従来どおり `voicevox_ok and voices`
   のときのみ表示。保存ヒットの文言も出し分け。
2. 🔵 `/wav_source_config` を jtalk / VOICEVOX で分岐。
   - VOICEVOX: 従来どおり話者(voice)を検証・記録し、話者変更時のみ bot を再起動。
   - Open JTalk: 話者は扱わず（voice を書かない）、`--regen` で固定WAVを作り直すのみ。
     固定WAVは bot が送出のたびに読み直す（reply cache も mtime で自動無効化する）ため
     bot 再起動はしない。
3. 🔵 対応: jtalk 側は create_wav.sh **V1.2 以降**（--regen 対応）が必要。
   dvswitch_bot.py（Open JTalk 系）は**無改修**（V1.93 のまま動作）。

---

## V3.0 (2026-07-14) — メジャーバージョン

V2 系（V2.0〜V2.87bvv）の機能を統合した、jtalk / VOICEVOX 両ノード共用の
メジャーバージョン。VOICEVOX 未導入ノードでは話者変更・読み上げ内容編集の
UI を自動的に隠すため、jtalk ノードに置いても従来どおり動作する。
共用ファイルのため版番号に "vv" サフィックスは付けない。

1. 🔵 V2 系機能の統合・整理。機能セットは V2.87bvv と同一。長大な変更履歴を
   本ファイルへ分離し、版表記を機械可読の `__version__` に一元化
   （テンプレートは `{{ app_version }}` で参照。版更新箇所は docstring と
   `__version__` の2箇所のみ）。
2. 🔵 テスト送信機能を追加。サービス制御カード（変更モード）から固定WAV
   （fixed_intro / fixed_outro / time_intro / 001 / 002、実在すれば cstm_*.wav）
   を選んで単発送信できる（POST /test_send → bin/test_send.py 実行）。
   bot は停止しない（停止→再開だと起動アナウンスが送出されるため）。
   時報・定時メッセージの発火時刻直前の実行は二重送信になり得るため避ける
   （confirm で注意喚起）。
3. 🔵 label の CSS typo 修正（display:blockcolor → display:block;color）。
   V2.58/V2.59 の typo 修正と同系統。入力ラベルが本来意図の淡色表示になる。

---

## V2 系の変更履歴（V2.87bvv → V2.0）

### V2.87bvv

🔵 版番号の命名規約変更＋bot版抽出の対応（機能変更なし）。
VOICEVOX 系ノード用ファイルは版番号末尾に "vv" を付ける規約を導入
（Open JTalk 系 Pi ノード用の同名ファイルと区別）。対象: app.py /
dvswitch_bot.py(V1.96vv) / create_wav.sh(V1.3avv) / vv_say.py(V2.0vv)。
あわせて get_bot_version() の3パターンを V[\d.]+ → V[\d.]+[a-z]* に拡張
（"V1.96vv" や "V1.95a" の英字サフィックスを切り落とさず表示するため）。

### V2.87b

🔵 表示微調整のみ（機能変更なし）。入力値テーブルの入力枠を固定幅
（280px/520px）から列幅いっぱい（width:100% + box-sizing:border-box）に
変更し、全行の右端を揃えた（下の読み上げ内容プレビュー表と同じ幅感）。
通常モード・変更モード共通。

### V2.87a

🔵 表示微調整のみ（機能変更なし）。「読み自動生成」ボタンを読み仮名の
入力枠の後ろからラベル側（枠の前）へ移動し、表記を「自動生成」に短縮。
ラベル列幅を 170px→210px に拡大。onclick/autoKana のロジックは無変更。

### V2.87

🔵 読み上げ内容カードを「話者のみ変更」から「話者＋入力テキストの統合編集」へ拡張。
(1) CLI（create_wav.sh 対話モード）と同じ7項目（コールサイン/読み仮名・
地名・メッセージ1/読み・メッセージ2/読み）を変更モードで編集可能に。
入力値と読み上げ値（読み仮名）を併記表示。
(2) 「読み自動生成」ボタンを読み仮名欄に追加（CLI のプリフィルと同一の
英数字→カナ変換を JS 移植。コールサインは英語読み数字、メッセージは
日本語読み数字）。読み欄を空で保存した場合はサーバ側でも同じ変換で
自動生成する（Python 移植 callsign_to_kana / msg_alphanum_to_kana）。
(3) 保存ボタンを1つに統合（保存して再生成）。/voice_config を廃止し
/wav_source_config へ置き換え。texts はサーバ側 build_wav_texts で
再計算（create_wav.sh の組み立てと厳密に同一。変更時は必ず両方揃える）。
(4) bot 再起動は「話者が変わった場合のみ」実行（テキストのみの変更は
bot が送出のたびに WAV を読み直すため再起動不要。RF 中断を最小化）。
(5) Web で変更した値は wav_source.json 経由で CLI 側のプリフィルにも
そのまま反映される（同一ファイルを共有）。

### V2.86

🔵 読み上げ内容カードに「話者（VOICEVOX 音声キャラクター）」の表示と変更を追加。
(1) 現在の話者（wav_source.json の voice: label/style_id/vvm）を常時表示。
(2) 変更モードで話者プルダウン＋「話者を変更して再生成」ボタンを表示。
一覧は venv 側 python で models/vvms/*.vvm の metas をスキャン
（VoiceModelFile のみ・onnx 非ロードで軽量。dir mtime でキャッシュ）。
選択値はサーバ側でスキャン結果と照合して検証（クライアント値を信用しない）。
(3) 変更フロー: wav_source.json の voice 更新 → create_wav.sh --regen
（記録済み texts で固定WAVを非対話再生成: create_wav.sh V1.3）→
dvswitch-bot のみ再起動（bot V1.96 は起動時に voice を読む）。
bridges/md380-emu は音声経路に無関係のため触らない（RF 中断を最小化）。
(4) VOICEVOX 未導入ノード（Open JTalk の Pi ノード等）では変更UIを出さず
注記のみ表示（共有ダッシュボード対応。他機能は従来どおり）。
(5) 話者フォームは save-form との入れ子を避けるため HTML5 form 属性方式
（フォーム本体は save-form 閉じタグ直後、コントロールはカード内）。
🔵 読み上げ内容の可変部分（コールサイン読み・地名・メッセージ読み＝
create_wav.sh の入力で変わる箇所）を太字表示。固定ハードコード部分との
区別がひと目で付く。分割はサーバ側（_split_variable_segments）で行い、
Jinja2 自動エスケープを維持（|safe 不使用）。
※ sudoers 注意: 本ルートは sudo で create_wav.sh を実行する。ダッシュボード
実行ユーザーに NOPASSWD 許可が systemctl のみの場合は
/opt/dvswitch_bot/bin/create_wav.sh の追加が必要。

### V2.85

🔵 サービス制御カードに、外部サービスへのリンクを追加。
「DVSwitch Dashboard」（ポート80）と「Monit」（ポート2812）へのリンクを、
bot バージョン表示の右隣に置いた。リンク先のホスト名は、サーバー側では
埋め込まず、ブラウザの window.location.hostname から JS で組み立てる。
これにより LAN でも Tailscale でも、アクセス中の経路に応じた正しい URL に
なる（別タブ target="_blank" で開く）。表示のみで設定には無関係。

### V2.84

🔵 セクションタイトル（.section-title）の文字と下線の間隔を詰めた。
padding-bottom を 4px → 1px に変更。下線と次要素の間隔（margin-bottom:10px）
は据え置き。見た目のみの微調整。

### V2.83

🔵 「カスタム音声」を Bot設定カードから独立カードへ分離し、中央カラムの
DVSwitch設定カードの下に配置した。中央セルを「DVSwitch設定 + カスタム音声」
の2カード縦積み（display:grid;gap:12px のラッパー）構成にした。
チェックボックスの name 属性（use_cstm_*）は変更なしのため、保存ルート
（bot_config / save_all）は無変更。表示位置の変更のみ。

### V2.82

🔴 Bot設定カードに「カスタム音声（差し替え）」を追加（dvswitch_bot.py
V1.73 / bot_setup.py 対応）。intro / 001 / 002 を個別に標準⇄カスタム
(cstm)で切り替えるチェックボックス3つを追加。bot_config / save_all の
保存ルートに USE_CSTM_INTRO / USE_CSTM_001 / USE_CSTM_002（bool）を追加。
チェックボックスは view-mode で自動グレーアウト（編集モードでのみ操作可）。
任意キーのため常に書き出す。旧 bot は未知キーを無視するので無影響。
実ファイル(cstm_*.wav)が無ければ本体が標準へ自動フォールバックする。

### V2.81

🔵 読み上げ内容カードを全6項目表示に戻す。
V2.80 で除外した fixed_outro / time_intro / time_outro を再表示し、
wav_source.json の texts 全6項目（fixed_intro/fixed_outro/time_intro/
001/002/time_outro）を表示するよう get_wav_source() の order を戻した。
表示のみの変更で保存ルート・記録には影響しない。

### V2.80

🔵 読み上げ内容カードの表示を主要3件に絞る。
fixed_outro（固定文言「カーチャンクです。」）/ time_intro（名乗りの一部で
fixed_intro と内容が冗長）/ time_outro（現行 bot 未使用）の3件を表示対象
から除外し、fixed_intro / 001 / 002 のみ表示するよう get_wav_source() の
order を整理した。wav_source.json 自体は全項目を保持（記録は従来どおり）。
表示の絞り込みのみで保存ルート・記録には影響しない。

### V2.79

🔵 読み上げ内容カードが上のグリッドにめり込んで見える不具合を修正。
原因: card は box-shadow（周囲8px）を持つが、3カラム(grid3)の直下に
余白ゼロで置いていたため、影同士が重なってカードがめり込んで見えた。
対策: 読み上げ内容カードに card-below-grid（margin-top:16px）を付与し、
grid3 との間に影が重ならない間隔を確保した。表示のみの修正。

### V2.78

🔵 3カラムの下に「読み上げ内容」カードを追加（wav_source.json 表示）。
create_wav.sh（V1.0〜）が記録する各WAVの実際の読み上げテキストを、
3カラム(grid3)の下に幅いっぱいの表示専用ブロックとして並べる。
get_wav_source() で wav_source.json を読み、texts の6項目（fixed_intro/
fixed_outro/time_intro/001/002/time_outro）を「ファイル名／用途／読み上げ
内容」の表で表示する。生成日時も併記。
本ブロックは input/select ではなく表示テキストのため、編集モードに
切り替えてもグレー系のまま編集不可で、フォーム送信・保存・再起動の対象に
一切ならない（save_all 等の保存ルートは無変更）。ファイルが無い場合は
案内文を表示する。閲覧のみで bot_config.json には無関係。

### V2.77

🔵 ヘッダーのコールサイン / 送信TG をベタ書きから実値表示に変更。
従来 tagline は "JJ2YYK / TGIF TG168" を固定文字列で持っていたが、
これを {{ dvs.callsign }} / TG{{ dvs.txtg }} に置換し、MMDVM_Bridge.ini /
Analog_Bridge.ini の実値を表示するようにした。dvs は既に index() で
テンプレートへ渡しているため Python 側の追加は不要。サーバー側
レンダリングのため値の反映は保存→リロード時（ポーリング非追従）。表示のみ。

### V2.76

🔴 バージョン表示が V1.69 に化ける不具合を修正。
原因: __version__ 抽出の最優先パターンが行頭固定でなかったため、bot 本体の
変更履歴コメント内にあった例示文字列 __version__ = "V1.69"（説明用）に先に
マッチし、本物の代入行（__version__ = "V1.70"）より前で拾ってしまった。
対策: 最優先パターンを (?m)^__version__... と行頭固定にし、コメント中の
例示（先頭が空白/記号で始まる）を除外。本物の代入行だけを拾う。
併せて bot 本体 V1.71 でコメントの例示文字列も誤検出しない表記に修正。

### V2.75

🔴 bot バージョン取得を堅牢化（V2.73 のバージョン表示が空になる不具合の修正）。
背景: get_bot_version() は先頭 4000 バイトだけを読んでいたが、bot 本体
V1.68 でヘッダ docstring が伸び、"Document Version:" 行が 9602 バイト目に
なって読み取り範囲外に落ち、表示が空になっていた。
対策(2点):
1) bot 本体ファイル冒頭付近に機械可読の固定行 __version__ = "Vx.yy" を
新設（dvswitch_bot.py V1.69〜）。docstring の長さに依存しない。
2) get_bot_version() を「__version__ を最優先 → Document Version: →
起動バナー」の順で探索し、先頭 20000 バイトで見つからなければ
ファイル全体を読んで再探索するフォールバックを追加。
これでヘッダがいくら伸びても版を取りこぼさない。表示のみで設定に影響なし。

### V2.74

🔴 Bot設定カードに「送出音量（TX_GAIN）」を追加（dvswitch_bot.py V1.68 対応）。
送出音量の線形倍率（1.0=等倍, 0.0超〜5.0以下）。bot が出す音すべてに効く。
bot_config / save_all の保存ルートに TX_GAIN を追加し、範囲を厳格に検証
（VALID 外は保存を弾く）。書き出し時は常に TX_GAIN を含めるため、保存し直しで
キーが消えることはない。旧 bot（V1.67以前）は未知キーを無視するため無影響。
未設定の旧 config に対してはフォーム既定 1.0 を表示する。

### V2.73

🔵 サービス制御カードに dvswitch_bot 本体のバージョンを表示（active の右側）。
systemctl cat dvswitch-bot の ExecStart から「実際に起動中の」スクリプト
パスを特定し、その先頭ドキュメントの "Document Version: Vx.yy" を抽出して
表示する。これにより bin/ と直下の重複ファイルがあっても稼働中の版を
正しく表示できる（取得不能時は空表示）。/api/status にも bot_version を
追加し、状態ポーリング時に併せて更新する。
本機能は閲覧のみ。bot_config.json には一切影響しない。
※ ここで言う「バージョン」は dvswitch_bot.py 本体（例 V1.67）であり、
本ダッシュボード app.py のバージョン（V2.73）とは別物である点に注意。

### V2.72

定時メッセージのプルダウン選択肢を簡潔な表記に変更（例: :00 :30）。

### V2.71

通常モードの入力欄を「枠あり・グレー背景・テキスト薄色」に変更。
従来の「枠なし・透明背景」より視認性が向上し、編集不可であることが
明確になった。
Bot設定カードに「時刻案内モード」プルダウンを追加し、「定時メッセージ」の
選択肢を時刻案内モードに連動して切り替え（JS rebuildFreq）。
mode0: 0/1/2/3/4   mode1: 0/1/2/3   mode2: 0/2
保存ルート（bot_config / save_all）に TIME_SIGNAL_MODE を追加し、
ANNOUNCE_FREQ 検証をモード依存（VALID_FREQ_BY_MODE）に変更。
旧キー未設定の bot_config.json は本体側が mode1 既定で扱うため、
フォーム既定値も 1 とした。

### V2.69

サービス制御カードの高さを通常モード/変更モードで統一（操作領域に
min-height を確保し、モード切替でカードが伸縮しないようにした）。
3カードヘッダーの絵文字アイコン（🤖📡📍）を削除。

### V2.68

🔴 再起動ロジックを「同時 restart」から「依存順＋待機つきの順序 restart」へ変更。
背景: 従来は subprocess.run(["systemctl","restart","dvswitch-bot",
"analog_bridge","mmdvm_bridge"]) のように複数サービスを同時に再起動して
いたため、Analog_Bridge 起動時に相手側（MMDVM_Bridge / md380-emu）が
まだ準備できておらず、TLV/AMBE 経路の確立に失敗して「音が出ない・ケロる・
応答しない（プロセスは Started だが中身は半死）」状態に陥ることがあった
（2026-06-06 実機で発生）。さらに AMBE エンコードの相手である md380-emu が
再起動対象に含まれていなかった。
対策: safe_restart_services() を新設し、
md380-emu → analog_bridge → mmdvm_bridge → (dvswitch-bot)
の依存順に、各サービス間へ待機（RESTART_GAP_SEC）を挟んで再起動する。
save_all / dvs_config_save / info_config_save の3箇所をこの関数に統一。

### V2.67

変更ボタンのアイコン削除・ラベルを「変更モード」に変更

### V2.66

操作ボタンを右寄せ、アイコン削除（テキストのみ）

### V2.65

操作ボタンをPi-star風テキストボタン（オレンジ統一・| 区切り）に変更

### V2.64

サービス状態を●(緑)active / ●(赤)inactive の丸印表現に変更

### V2.63

通常/変更モード追加（通常は閲覧専用＋変更ボタンのみ、変更で編集＋操作ボタン表示）

### V2.62

ボタンサイズ縮小（幅120→84px、高さ42→34px）

### V2.61

ボタンに固定height/box-sizing追加で完全同一サイズ化

### V2.60

サービス制御の5ボタンを同じ幅・高さに統一

### V2.59

.btn/.section-title のCSS typo修正（ボタン肥大化）、ボタンを大きく、
section-titleを通常フォント化（半角括弧を細く表示）

### V2.58

メッセージ頭切れ修正（main上余白追加）、status-pillのCSS typo修正

### V2.57

3カードを一括保存に統合、保存ボタンをサービス制御行へ、変更ログ非表示、
保存時に dvswitch-bot/analog_bridge/mmdvm_bridge を一括再起動

### V2.56

配置コメントを実態（/opt/dvswitch_bot/web）に修正

### V2.55

メッセージをURLパラメータから内部保持に変更（URL 2バイト文字除去）

### V2.54

受信時間フィルタを縦並びに変更

### V2.53

Bot設定/DVSwitch設定/MMDVM Info を3カラム横並びに変更

### V2.52

MMDVM_Bridge [Info] セクション編集機能を追加

### V2.51

フォント11pt統一、iniバックアップ一覧を非表示、ヘッダにバージョン表示

### V2.5

 配色をDVSwitch Dashboard実ソースに合わせて変更

### V2.4

 UIスタイルをDVSwitch Dashboard風に変更

### V2.3

 ログ表示機能を削除（音声化け対策）
DVSwitch設定保存後に analog_bridge / mmdvm_bridge を自動再起動

### V2.2

 V2.1実機ソースのクリーンアップ

### V2.1

 タイトル変更、ポート8081、ログディレクトリ修正、変更ログ機能追加

### V2.0

 初版リリース
