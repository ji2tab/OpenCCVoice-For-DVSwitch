# dvswitch_bot.py ソフトウェア仕様書（JT版 V1.93 / VV版 V1.96vv）

**対象ファイル:** `/opt/dvswitch_bot/bin/dvswitch_bot.py`
**対象バージョン:** JT版（`dvs_ocv_JT/`）**V1.93** ／ VV版（`dvs_ocv_vv/`）**V1.96vv**
**本文の扱い:** 本文（第1〜13章）は **JT版・VV版で共通の仕様** を記述する。VV版（VOICEVOX）固有の差分は末尾の『VV版差分（V1.96vv）』章にまとめる。
**JT版 V1.93 の反映範囲:** 無線局運用規則第30条対応・応答音声キャッシュ・watchdog擬似終端・SET_INFO メタデータ・送信直列化・第30条セッションのギャップ判定バグ修正 まで。
**版番号の "vv" サフィックス:** VOICEVOX 系ノード用ファイルであることを示す命名規約（Open JTalk 系 Pi ノード用の同名ファイルと区別する）。
**役割:** MMDVM_Bridge のログを監視し、カーチャンク自動応答・時報・定時メッセージ・長時間通信時の識別信号（法令対応）を
USRP プロトコルで送出する常駐デーモン。

この文書は**スクリプト本体の内部仕様**を記述する技術文書です。システム全体の構成
（各ソフトの関係・配線）は別冊『システム仕様書』を参照してください。バージョンごとの
変更履歴は本文書では扱わず、リポジトリ直下の `Changelog.md` を参照してください。

---

## 目次

1） [概要と責務](#1-概要と責務)
2） [依存・実行環境](#2-依存実行環境)
3） [定数仕様](#3-定数仕様)
4） [設定ファイルと検証仕様](#4-設定ファイルと検証仕様)
5） [グローバル状態と排他制御](#5-グローバル状態と排他制御)
6） [関数仕様](#6-関数仕様)
7） [処理フロー](#7-処理フロー)
8） [USRP パケット仕様](#8-usrp-パケット仕様)
9） [音声生成パイプラインとキャッシュ](#9-音声生成パイプラインとキャッシュ)
10） [ナイトモード仕様](#10-ナイトモード仕様)
11） [ログ出力仕様](#11-ログ出力仕様)
12） [スレッド構成と終了処理](#12-スレッド構成と終了処理)
13） [改修時の注意点](#13-改修時の注意点)
14） [VV版差分（V1.96vv）](#14-vv版差分v196vv)

---

## 1. 概要と責務

`dvswitch_bot.py` は単一プロセスの常駐デーモンで、次の処理を行う。

1） 起動アナウンス — 起動後一定秒数おいて「起動しました。」を 1 回送出（V1.62）
2） カーチャンク自動応答 — MMDVM_Bridge ログから短時間送信を検知し、応答音声を送出。V1.75〜でキャッシュを先行生成して即応答化
3） watchdog 擬似終端の救済 — SFR 中継で終端パケットが落ちた送信も、watchdog ログから拾って判定に流す（V1.67〜）
4） 時報 — 毎正時に「〇〇時です」を送出。TIME_SIGNAL_MODE により 30 分案内も追加可能（V1.64〜）
5） 定時メッセージ — 1 時間に 0〜4 回、001/002 を交互送出
6） 無線局運用規則第30条対応 — 長時間通信（Normal QSO）セッションが継続中は、10分ごとに自局識別信号（fixed_intro.wav）を強制送信（V1.74〜）
7） SET_INFO メタデータ送出 — 送信前に DVSwitch 公式クライアント（pyUC）同様のメタデータを Analog_Bridge へ通知し、Talker Alias を自局に保つ（V1.83, V1.90〜）
8） ナイトモード — 時報は N1+1 時〜N2 時、定時メッセージは N1 時〜N2 時を抑制。kerchunk は24時間応答
9） 送信直列化 — 起動アナウンス・応答・時報・ナイト・10分ID のすべてを _tx_lock で直列化し、二重送信を防止（V1.91）

入出力の境界は次のとおり。

| 区分 | 内容 |
|---|---|
| 入力 | MMDVM_Bridge ログ（`/var/log/mmdvm/`）、設定 JSON、固定 WAV 群 |
| 出力 | USRP パケット（UDP 127.0.0.1:51000 → Analog_Bridge）。送信前に SET_INFO メタデータを任意で付加 |
| 一時ファイル | `/dev/shm/`（RAM）に合成中間ファイルと応答キャッシュを保持。プロセス再起動で自動クリア |
| 外部プロセス起動 | `open_jtalk`（音声合成）、`sox`（音声変換・連結・音量調整） |
| 対話 | なし（設定は JSON 読み込みのみ。systemd 常駐向け） |

---
## 2. 依存・実行環境

### 標準ライブラリ

`os` / `sys` / `json` / `time` / `glob` / `re` / `socket` / `struct` / `wave` /
`signal` / `logging` / `threading` / `subprocess` / `math` / `datetime`

すべて Python 3 標準。**サードパーティ製パッケージへの依存はない。**（`math` は V1.84 でリード音のトーン生成に使用開始）

### 外部コマンド（PATH 上に必要）

| コマンド | 用途 |
|---|---|
| `open_jtalk` | テキスト → 48kHz WAV の音声合成 |
| `sox` | 8kHz/mono/16bit への変換、無音パディング、WAV 連結、音量調整（vol） |

### 必要なファイル・ディレクトリ

| パス | 必須 | 用途 |
|---|---|---|
| `/opt/dvswitch_bot/bot_config.json` | ◎ | 動作設定（無いと起動拒否） |
| `/opt/dvswitch_bot/fixed_intro.wav` ほか | ◎ | 固定 WAV 群 |
| `/var/lib/mecab/dic/open-jtalk/naist-jdic` | ◎ | Open JTalk 辞書 |
| `/usr/share/hts-voice/mei/mei_normal.htsvoice` | ◎ | 音声モデル |
| `/var/log/mmdvm/MMDVM_Bridge-*.log` | ◎ | 監視対象ログ |
| `/dev/shm/` | ◎ | 一時 WAV（RAM）と応答キャッシュ（V1.75〜） |

---

## 3. 定数仕様

### パス・ネットワーク

| 定数 | 値 | 意味 |
|---|---|---|
| `LOG_DIR` | `/var/log/mmdvm` | ログ格納ディレクトリ |
| `LOG_PATTERN` | `MMDVM_Bridge-*.log` | 監視対象ログのグロブパターン |
| `UDP_IP` | `127.0.0.1` | 送信先（Analog_Bridge） |
| `UDP_PORT` | `51000` | 送信先ポート（Analog_Bridge の rxPort と一致） |
| `MY_CALLSIGN` | `JJ2YYK` | 自局。これと一致する送信は無視（ループ防止） |
| `MY_DMR_ID` | `4402396` | 🔴V1.83 自局 DMR ID。Analog_Bridge.ini の gatewayDmrId と一致させる（SET_INFO 用） |
| `TX_METADATA_ENABLED` | `True` | 🔴V1.83 送信前に SET_INFO メタデータを送るか。False で V1.82 と同一（メタデータなし） |
| `DICT_PATH` | `/var/lib/mecab/dic/open-jtalk/naist-jdic` | Open JTalk 辞書 |
| `VOICE_PATH` | `/usr/share/hts-voice/mei/mei_normal.htsvoice` | 音声モデル |
| `BOT_DIR` | `/opt/dvswitch_bot` | WAV・JSON の基準ディレクトリ |
| `CONFIG_PATH` | `{BOT_DIR}/bot_config.json` | 設定ファイル |

### 固定 WAV

| 定数 | ファイル |
|---|---|
| `FIXED_INTRO_WAV` | `fixed_intro.wav`（カーチャンク応答・起動・ナイト・10分IDイントロ共通） |
| `FIXED_OUTRO_WAV` | `fixed_outro.wav`（カーチャンク応答アウトロ） |
| `TIME_INTRO_WAV` | `time_intro.wav`（時報イントロ） |
| `TIME_OUTRO_WAV` | `time_outro.wav`（定義のみ。現行ロジックで未使用） |
| `MSG_FILES` | `[001.wav, 002.wav]`（定時メッセージ） |

### カスタム WAV（V1.73〜）

標準 WAV の代わりに利用者が用意する差し替え音声。`USE_CSTM_*` が True かつ実ファイルが存在するときだけ使い、無ければ標準へフォールバックする（`_resolve_wav` 参照）。

| 定数 | ファイル |
|---|---|
| `CSTM_INTRO_WAV` | `cstm_intro.wav`（intro の差し替え。応答・起動・ナイトの3か所共通） |
| `CSTM_MSG_FILES` | `[cstm_001.wav, cstm_002.wav]`（001/002 の差し替え） |



**注:** 🔴V1.74 の識別信号強制送信（regulatory_id）は法令上の内容保証のため、`USE_CSTM_INTRO` に関わらず常に `FIXED_INTRO_WAV`（標準）を使用し、カスタム音声には差し替えない。

### 一時ファイル（PID 付き・/dev/shm）

| 定数 | パス |
|---|---|
| `TEMP_FINAL` | `/dev/shm/reply_final_{PID}.wav`（送出する完成品） |
| `TEMP_48K` | `/dev/shm/tmp_48k_{PID}.wav`（open_jtalk 出力） |
| `TEMP_8K` | `/dev/shm/tmp_8k_{PID}.wav`（8kHz 変換後） |
| `TEMP_INTRO_PADDED` | `/dev/shm/tmp_intro_padded_{PID}.wav`（無音付与後イントロ） |

PID を付けるのは、複数プロセスや再起動時のファイル衝突を避けるため。🔴V1.91 で、これら共有一時ファイルの実行中削除を廃止し、掃除は起動時の一括削除と `_generate_hybrid` の生成直後（V1.92）のみで行う方針に変更（詳細は9章）。

### タイミング・パディング

| 定数 | 値 | 意味 |
|---|---|---|
| `EMPTY_HEADER_THRESHOLD_SEC` | `0.1` | （予約的定数） |
| `SUPPRESS_DURATION_SEC` | `15.0` | 応答後・通常QSO後の抑制時間（秒） |
| `QSO_SESSION_GAP_SEC` | `60.0` | 🔴V1.93 第30条セッション継続とみなす無通信ギャップの上限（秒）。従来は `SUPPRESS_DURATION_SEC`（15秒）のエイリアスだったが、独立定数化し 60.0 に変更（TGIFChanger-Py の自TG復帰判定＝無音60秒と運用上の一貫性を優先） |
| `PACKET_INTERVAL` | `0.02` | USRP パケット送信間隔（20ms） |
| `PRE_POST_PADDING_PACKETS` | `75` | 音声前後の無音パケット数（75×20ms＝1.5秒） |
| `USRP_EOT_REPEAT` | `1` | 🔴V1.82 送信終端（keyup=0）の送出回数。取りこぼし対策で複数回送出可 |
| `ROTATION_CHECK_INTERVAL` | `5.0` | ログ切替チェック間隔（秒） |
| `GAP_AFTER_INTRO_SEC` | `0.5` | イントロ後の無音（連結時の「間」） |
| `STARTUP_ANNOUNCE_DELAY_SEC` | `5.0` | 起動後この秒数おいて起動アナウンスを送出（V1.62） |
| `TIME_SIGNAL_LEAD_SEC` | `7` | 時報を正時の何秒前に発火させるか |
| `NIGHT_ANN_GAP_SEC` | `1.0` | 時報とナイトモードアナウンスの間隔 |
| `PRE_AUDIO_SILENCE_SEC` | `1.5` | 🔴V1.80/V1.87 kerchunk応答の実音声前に焼き込む無音パッド（受信側の途中参加同期の助走） |


### 🔴 リード音（ノイズ充填・ゲートバースト）— TGIF 先頭無音スキップ対策（V1.84〜V1.89）

前パディングの完全無音ブロックを、TGIF 中継が先頭無音を転送せず捨ててしまう問題（受信側の途中参加・スタック要因）への対策として、聞こえないレベルの信号に置き換える。

| 定数 | 値 | 意味 |
|---|---|---|
| `NOISE_FILL_ENABLED` | `True` | 🔴V1.84 前パディングの無音をリード音（トーン）に置換するか |
| `NOISE_FILL_AMP` | `150` | 🔴V1.89 トーン振幅（150/32768 ≈ -47dBFS）。100Hz 微小トーンでAMBEに非無音として符号化させる |
| `NOISE_LEAD_PACKETS` | `65` | 🔴V1.88 前パディング75個中、先頭何個をリード音にするか（65×20ms=1.3秒）。残りは無音 |
| `GATE_BURST_PACKETS` | `0` | 🔴V1.85 ゲート開放バースト（先頭の強めのヒス）パケット数。0 で無効（既定） |
| `GATE_BURST_AMP` | `2500` | バースト振幅（2500/32768 ≈ -22dBFS）。GATE_BURST_PACKETS>0 のときのみ使用 |

**V1.89 での変更点:** リード音はホワイトノイズから100Hz微小トーンへ変更した。AMBE（音声ボコーダ）はノイズを歪みとして符号化しやすいが、周期信号（トーン）は綺麗なハムとして符号化される。末尾5ブロックはフェードアウトし、無音への遷移ポップを防ぐ（`_TONE_FADES` / `_FADE_STEPS`）。

**V1.86 での変更点:** WAV本体中の無音とストリーム後パディングは、実測でTGIF転送に問題ないことを確認したため、ノイズ充填の対象から除外し真の無音に戻した。ノイズ充填は前パディングの先頭のみに限定している。

### 🔴 送出音量ゲイン（V1.68〜）

| 定数 | 値 | 意味 |
|---|---|---|
| `TX_GAIN_DEFAULT` | `1.0` | 既定値（等倍）。bot_config.json の任意キー TX_GAIN が無いときに使用 |
| `TX_GAIN_MIN` | `0.0` | 有効範囲の下限（この値より大きいこと。0以下は無音化防止のため無効） |
| `TX_GAIN_MAX` | `5.0` | 有効範囲の上限（Analog_Bridge.ini の usrpGain と同じ 0.0〜5.0 レンジ） |

TX_GAIN は線形倍率。bot が出す音すべて（応答/時報/30分案内/起動・ナイト案内/001・002/10分ID）に一律で効く。

### カナ変換テーブル `CHAR_TO_KANA`

英大文字 A〜Z、数字 0〜9、記号 `-`（ダッシュ）`/`（スラッシュ）を日本語カナ読みへ
マップする辞書。コールサインを1文字ずつ読み上げるために使用（例: `JJ2YYK` →
ジェイジェイツーワイワイケー）。テーブルに無い文字はそのまま使われる。

---

## 4. 設定ファイルと検証仕様

設定は `bot_config.json` から `_load_config()` が読み込む。フェイルセーフ設計で、
不備があれば誤動作させず `sys.exit(1)` で停止する。

### 必須キー `REQUIRED_KEYS`

| キー | 型 | 検証ルール |
|---|---|---|
| `RX_DURATION_MIN_SEC` | float | `> 0` かつ `< MAX` |
| `RX_DURATION_MAX_SEC` | float | `MIN < MAX` |
| `ANNOUNCE_FREQ` | int | `TIME_SIGNAL_MODE` に応じた有効範囲内（下表） |
| `NIGHT_MODE_ENABLED` | bool | `true / false`（厳密に bool 型であること） |
| `NIGHT_START_HOUR` | int | `0〜23` |
| `NIGHT_END_HOUR` | int | `0〜23` |

### 🔴 ANNOUNCE_FREQ の有効範囲（TIME_SIGNAL_MODE 依存）

`TIME_SIGNAL_MODE` の値ごとに `ANNOUNCE_FREQ` の有効な値の集合が異なる。

| TIME_SIGNAL_MODE | 有効な ANNOUNCE_FREQ | 発火する分（例） |
|---|---|---|
| 0（時刻案内なし） | 0/1/2/3/4 | なし/[0]/[0,30]/[0,20,40]/[0,15,30,45] |
| 1（毎正時のみ、既定） | 0/1/2/3 | なし/[30]/[20,40]/[15,30,45] |
| 2（毎正時+毎30分） | 0/2 | なし/[15,45] |

mode 1/2 では :00（と mode2 は :30 も）を時刻案内が占有するため、定時メッセージのトリガー分からは除外される。

### 任意キー（`REQUIRED_KEYS` に含めない・後方互換）

未設定でも起動できる任意キー。旧設定ファイルとの互換のため必須化していない。

| キー | 型 | 既定 | 意味 |
|---|---|---|---|
| `TIME_SIGNAL_MODE` | int | 1 | 時刻案内モード（0=なし/1=毎正時/2=毎正時+毎30分）。未設定時は警告ログを出し1を採用。V1.64〜 |
| `TX_GAIN` | float | 1.0 | 送出音量の線形倍率（0.0超〜5.0以下）。不正値は1.0にフォールバック＋警告。V1.68〜 |
| `USE_CSTM_INTRO` | bool | false | intro にカスタム音声を使う。V1.73〜 |
| `USE_CSTM_001` | bool | false | 001 にカスタム音声を使う。V1.73〜 |
| `USE_CSTM_002` | bool | false | 002 にカスタム音声を使う。V1.73〜 |

任意キーは検証で欠落してもエラーにせず既定値を採用する。USE_CSTM_* は bool 以外（不正値含む）を安全側に false（標準）として扱い、起動は止めない。TX_GAIN も型不正や範囲外は fatal にせず1.0にフォールバックする（音量はRF安全に直結しないため）。

### 検証段階（順に実施し、いずれか失敗で即終了）

1） ファイル存在確認（無ければ終了）
2） JSON パース（失敗で終了）
3） オブジェクト（dict）であることの確認
4） 必須キーの存在確認（欠落キーを列挙して終了）
5） 型変換と範囲チェック（上表のルール。ANNOUNCE_FREQ は TIME_SIGNAL_MODE 確定後に検証）
6） TX_GAIN・USE_CSTM_* など任意キーの検証（不正でも fatal にせずフォールバック）
7） 全通過したらグローバルへ反映し、Config loaded をログ出力

設計意図として、設定不備で意図しない送信パラメータのまま電波を出すことを防ぐ。systemd では `Restart=on-failure` のため、設定不備時は再起動を繰り返し、運用者が異常に気づける。

---

## 5. グローバル状態と排他制御

| 変数 | 型 | 役割 |
|---|---|---|
| `should_exit` | bool | 終了フラグ。シグナルで `True` になり全ループが抜ける |
| `suppress_until` | float | この `monotonic` 時刻まで応答を抑制 |
| `is_talking` | bool | 送出中フラグ。多重送出を防ぐ |
| `_reply_lock` | Lock | `is_talking` を保護する排他ロック |
| `_gen_lock` | Lock | 🔵V1.75 合成パイプライン（共有一時ファイル使用）を直列化するロック |
| `_tx_lock` | Lock | 🔴V1.91 送信フロー全体（生成→送出）を直列化するロック。起動アナウンス・応答・時報・ナイト・10分IDの同時実行による二重送信を防ぐ |
| `_cache_build_locks` / `_cache_locks_guard` | dict / Lock | 🔵V1.75 コールサイン単位のキャッシュ構築ロック（プリキャッシュと応答の競合防止） |
| `qso_session_start` / `qso_session_last_end` / `qso_session_id_count` | float / float / int | 🔴V1.74 長時間通信セッションの追跡状態（time.monotonic() 基準） |
| `RX_DURATION_MIN_SEC` ほか設定値 | — | bot_config.json 由来。起動時は `None`、`_load_config()` で確定（TX_GAIN 含む） |

ロック順序は `_tx_lock`（外）→ `_gen_lock`（内）。プリキャッシュ（`_prewarm_reply`）は `_gen_lock` のみ取得し（送信ではないため `_tx_lock` は取らない）、デッドロックは発生しない設計になっている。

`is_talking` により、応答・時報・定時メッセージ・10分ID・起動/ナイトアナウンスは同時に1つしか走らない（カーチャンク中に時報が重なっても、後発はスキップされる）。

---

## 6. 関数仕様

### 設定・基盤

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `_fmt(tag, action, target, extra)` | ログ行を整形 | 整形済み文字列 |
| `_fatal_config(msg)` | 設定エラーを出力し `exit(1)` | プロセス終了 |
| `_load_config()` | JSON 読込・検証・グローバル反映 | 不正なら `exit(1)` |
| `_resolve_wav(use_cstm, cstm_path, fixed_path, label)` | カスタム使用フラグと実ファイルの有無から実際に再生するパスを決める（V1.73） | カスタム有効＆存在→cstm、無ければ標準＋警告ログ |
| `_handle_signal(signum, frame)` | SIGTERM/SIGINT で `should_exit=True` | 終了開始 |

### 🔴 SET_INFO メタデータ（V1.83、V1.90）

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `_usrp_set_info_payload(callsign, dmr_id)` | pyUC の sendMetadata() と同一の TLV_TAG_SET_INFO(8) ペイロードを組む | bytes（DMR ID・repeaterID=0・TG=0・TS=0・CC=0・callsign+NUL） |
| `_send_usrp_metadata(sock, seq)` | 音声送出前に SET_INFO メタデータを送信（pyUC 互換ヘッダ） | 次に使う seq を返す |
| `_assert_identity()` | 🔴V1.90 自局アイデンティティを Analog_Bridge に再主張。他局受信終了ごと・起動時・送信直前の三重主張で Talker Alias の引きずりを防ぐ | UDP送信（TX_METADATA_ENABLED=False時は何もしない） |

### 🔴 リード音生成（V1.84、V1.89）

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `_init_noise_blocks()` | 100Hz トーンブロックとフェード用ブロック群を初回生成 | `_TONE_BLOCK` / `_TONE_FADES` を設定 |
| `_lead_block(i, lead_total)` | 前パディング i 番目のリード音ブロックを返す（末尾はフェード） | bytes（320バイトPCM） |
| `_noise_block()` | 互換用。リード音の基本ブロックを返す（無効時はゼロ） | bytes |
| `_fill_if_silent(data)` | PCMブロックが完全ゼロなら微小ノイズに置換 | bytes |

### 送信

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `send_usrp_wav_with_padding(wav_path)` | WAV を USRP 送信（前後パディング＋絶対時刻同期、SET_INFO送出、EOT複数回送出） | UDP 送信。末尾で PTT OFF を USRP_EOT_REPEAT 回送出 |

### ナイトモード・スケジューラ

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `_is_night_suppressed(hour)` | 時報の抑制判定 | bool |
| `_is_night_suppressed_message(hour)` | 定時メッセージの抑制判定 | bool |
| `_get_trigger_minutes()` | TIME_SIGNAL_MODE・ANNOUNCE_FREQ→発火する分のリスト | 例: [30] / [20,40] / [15,30,45] |
| `_announcement_scheduler()` | 時報・定時の発火を監視（別スレッド） | `_start_worker` を呼ぶ |
| `_start_worker(mode, val, extra)` | 多重チェックして応答スレッド起動 | 起動できたら True、is_talking 中は False（V1.74で戻り値追加） |

### 🔴 無線局運用規則第30条対応（V1.74）

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `_handle_rx_duration(cs, dur, source)` | 受信時間に基づくカーチャンク/Normal QSO判定（eot/watchdog共通ロジック）。Normal QSO検知時に `_handle_qso_session` を呼ぶ | ログ出力、`_start_worker` 呼び出し |
| `_handle_qso_session(now)` | Normal QSO検知のたびに呼ばれ、セッション経過時間を積算。10分の倍数を跨ぐたびに `regulatory_id` ワーカーを起動 | `qso_session_*` グローバルを更新。送信できなかった場合はカウンタを更新せず次回再試行 |

### 🔵 応答音声キャッシュ（V1.75）

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `_cache_path(cs)` | コールサインからキャッシュファイルパスを算出 | 文字列パス |
| `_mtime(path)` | ファイルの mtime を文字列で返す（無ければ"0"） | 文字列 |
| `_reply_signature()` | キャッシュ整合性の署名（intro実体・outro・GAP・頭無音・TX_GAIN・音声モデル・スキーマ版から算出） | 文字列 |
| `_cs_build_lock(cs)` | コールサイン単位のビルド用ロックを取得/作成 | Lock |
| `_cache_valid(path, sig_path, sig_now)` | キャッシュファイルと署名が現行設定と一致するか | bool |
| `_ensure_cached(cs)` | cs の応答WAVを返す。無ければ生成して /dev/shm に格納 | (path, was_hit) のタプル。失敗時 (None, False) |
| `_prewarm_reply(cs)` | ヘッダ受信時に呼ぶ。未キャッシュなら背景で先行生成 | 既にキャッシュ済みなら何もしない |
| `_init_reply_cache()` | 起動時にキャッシュディレクトリを作り直す（RAM上・毎起動クリア） | ディレクトリ再作成 |

### アナウンス・応答実行

| 関数 | 役割 | 主な戻り値・副作用 |
|---|---|---|
| `_send_startup_announcement()` | 起動アナウンス送出（V1.62）。V1.91で `_tx_lock` 取得に変更 | USRP 送信 |
| `_send_night_mode_announcement()` | ナイトモード突入アナウンス送出 | USRP 送信 |
| `_reply_executor(mode, val, extra)` | 応答の実体（キャッシュ取得/合成→送出→後始末）。V1.91で `_tx_lock` 取得に変更 | 抑制設定、is_talking解除 |
| `_generate_hybrid(intro, middle_text, outro, out_path, head_silence)` | イントロ＋合成音声＋アウトロを結合。V1.75でout_path/head_silence引数追加 | bool（成功/失敗）。V1.92で中間ファイル掃除をfinally内に実施 |
| `_log_startup_info()` | 起動時に設定値・各機能のON/OFF状態をログ出力 | — |
| `_find_latest_log()` | 最新ログファイルのパスを返す。V1.63で0バイトファイルをスキップ | パス or None |
| `_open_log_file(path)` | ログを開いて末尾へシーク | (file, inode) |
| `monitor_and_reply()` | メイン。ログ監視ループ | プログラム全体の駆動 |

### mode（`_reply_executor` の `mode` 引数）

| mode | 内容 | 音声構成 |
|---|---|---|
| `kerchunk` | カーチャンク応答（キャッシュ優先） | イントロ＋「〇〇局の、」＋アウトロ |
| `time_signal` | 時報 | 時報イントロ＋「〇〇時です」 |
| `half_hour_signal` | 🔴V1.64 30分案内 | 時報イントロ＋「〇〇時30分です」 |
| `fixed_file` | 定時メッセージ | 既成 WAV（001/002）をそのまま送出（TX_GAIN適用） |
| `regulatory_id` | 🔴V1.74 識別信号強制送信 | FIXED_INTRO_WAV をそのまま送出（TX_GAIN適用、カスタム音声不可） |

---

## 7. 処理フロー

### 7-1. 起動シーケンス（monitor_and_reply）

起動時の処理順序は次のとおり。

1） `_load_config()` で設定読込・検証（不正なら `exit(1)`）
2） `_init_reply_cache()` でキャッシュディレクトリを作り直す（V1.75〜）
3） `_log_startup_info()` で設定値・各機能のON/OFF状態をログ出力
4） スケジューラスレッド（`_announcement_scheduler`）を起動
5） `_find_latest_log()` で最新ログを探し、`_open_log_file()` で末尾へシーク
6） 起動時の共有一時ファイル（TEMP_FINAL等）を一括削除（V1.91）
7） `Bot ready` 出力、`_assert_identity()` で自局アイデンティティを主張（V1.90）
8） `threading.Timer` で起動アナウンスを `STARTUP_ANNOUNCE_DELAY_SEC` 秒後に予約
9） ログ監視ループへ入る

### 7-2. ログ監視ループ（カーチャンク検知・watchdog擬似終端）

行を1行ずつ読み、正規表現でマッチさせる。

| パターン | 正規表現 | 意味 |
|---|---|---|
| 開始 | `received network voice header from ([A-Z0-9/\-]+)` | 送信開始＋コールサイン |
| 終了 | `received network end of voice transmission` | 送信終了（正常終端） |
| watchdog | `network watchdog has expired, ([\d.]+) seconds, (\d+)% packet loss` | 🔴V1.67 擬似終端候補（経過秒・ロス率） |
| 時刻 | `(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})` | ログのタイムスタンプ |

判定ロジック:

1） 開始行を検知 → コールサイン（MY_CALLSIGN以外）と開始時刻を記憶。🔵V1.75 同時に `_prewarm_reply(cs)` を呼び、未キャッシュなら背景合成を開始
2） 終了行（正常終端）を検知 → `dur = 終了 − 開始` を算出し `_handle_rx_duration(cs, dur, source="eot")` を呼ぶ
3） 🔴V1.67 watchdog行を検知（正常終端が来なかった場合）→ ロスが `WATCHDOG_MAX_LOSS_PCT` 以下なら擬似終端として `_handle_rx_duration(cs, dur, source="watchdog")` を呼ぶ。超過なら「壊れた受信」として無視
4） `_handle_rx_duration` は経路ごとの上限（eot: RX_DURATION_MAX_SEC / watchdog: WATCHDOG_RX_MAX_SEC）で以下に分岐

| 条件 | 動作 |
|---|---|
| MIN ≤ dur < 上限 かつ抑制時間外 | カーチャンクと判定し応答（`_start_worker("kerchunk")`） |
| MIN ≤ dur < 上限 かつ抑制中 | 残り抑制時間をログに出して無視 |
| dur ≥ 上限 | Normal QSOとみなし、以後SUPPRESS_DURATION_SEC抑制。🔴V1.74 `_handle_qso_session()` を呼びセッション管理・10分ID判定を行う |
| dur < MIN | 短すぎ→無視 |

他局の受信終了直後（cs != MY_CALLSIGN）には `_assert_identity()` を呼び、Analog_Bridge の「最後に聞いた局」状態を自局に上書きする（V1.90）。

### 7-3. 応答実行（kerchunkの例、キャッシュ優先）

kerchunk 応答は次の順で処理される。

1） `_ensure_cached(cs)` を呼び、キャッシュ命中（was_hit=True）ならそのまま、ミスなら合成してキャッシュに格納
2） キャッシュ命中時のみ `REPLY_TX_LEAD_DELAY_SEC` 秒待機（SFR折り返し保護。V1.77）
3） `send_usrp_wav_with_padding()` で USRP 送出（TX_METADATA_ENABLED なら送出前に SET_INFO メタデータも送信）
4） `suppress_until` を設定（15秒抑制）
5） `is_talking=False`、`_tx_lock` 解放

### 7-4. 無線局運用規則第30条対応の流れ（V1.74）

1） Normal QSO 検知のたびに `_handle_qso_session(now, dur)` が呼ばれる（🔴V1.93 で今回の送信時間 `dur` を渡すよう変更）
2） 🔴V1.93 `now` は今回送信の「終了」時刻なので `tx_start = now - dur`（今回送信の開始時刻の近似）を求め、前回の Normal QSO の「終了」から今回送信の「開始」までの純粋な無音時間 `(tx_start - qso_session_last_end)` を評価する。これが `QSO_SESSION_GAP_SEC`（60秒）超なら新セッションとして0から再開（開始時刻も `tx_start` に合わせ、最初の送信の通話時間も経過時間に含める）。それ以外は既存セッションを継続
3） セッション経過時間が `QSO_ID_INTERVAL_SEC`（10分）の倍数を新たに跨いだら `_start_worker("regulatory_id", FIXED_INTRO_WAV)` を呼び、直近の送信終了直後というタイミングで識別信号を強制送信
4） 送信が競合（is_talking中）でスキップされた場合はカウンタを更新せず、次回のNormal QSO検知時に再試行される（取りこぼし防止）

### 7-5. 起動アナウンス（_send_startup_announcement, V1.62／V1.91で直列化）

デーモン起動後、ログ監視を開始する直前に `threading.Timer` で `STARTUP_ANNOUNCE_DELAY_SEC`（5.0秒）遅延させ、「起動しました。」を1回だけ送出する。V1.91で `_tx_lock` を取得するよう変更され、起動直後に他局受信への応答と重なっても二重送信・ストリーム破壊が起きない設計になった（V1.90以前は無ロックで、起動直後に他局を受信すると応答と衝突する場合があった）。

---

## 8. USRP パケット仕様

`send_usrp_wav_with_padding()` が組み立てる USRP パケットの構造。

### ヘッダ（`struct.pack("!4sIIIIIII", ...)`）

| フィールド | 型 | 値 | 意味 |
|---|---|---|---|
| マジック | 4s | `b"USRP"` | プロトコル識別子 |
| シーケンス | I | `seq` | 0 から増加するパケット連番 |
| （memory） | I | `0` | — |
| keyup（PTT） | I | `1`（送信中）/ `0`（終了） | PTT 状態 |
| 残り5フィールド | I×4 | `0`（メタデータ送出時は type ワードに変化あり） | 未使用/メタデータ用 |

ヘッダ長は 4＋4×7 ＝ 32 バイト。ペイロードは音声送出時 320 バイト固定（160 サンプル × 16bit）。

### 🔴 SET_INFO メタデータパケット（V1.83）

`TX_METADATA_ENABLED=True` のとき、音声送出の前に1回、`_send_usrp_metadata()` が以下を送出する。ヘッダは keyup=0、type ワードに `(USRP_TYPE_TEXT=2) << 24` を格納（pyUC の sendUSRPCommand() と同一のバイト列）。

| フィールド | 長さ | 内容 |
|---|---|---|
| tag | 1B | `8`（TLV_TAG_SET_INFO） |
| len | 1B | 以降のペイロード長 |
| DMR ID | 3B | `MY_DMR_ID` |
| repeater ID | 4B | `0` |
| TG | 3B | `0`（実際のTG/TS/CCはAnalog_Bridge.iniのtxTg/txTs/colorCodeが使われる） |
| TS | 1B | `0` |
| CC | 1B | `0` |
| callsign | 可変 | `MY_CALLSIGN` の ASCII + NUL |

`_assert_identity()`（V1.90）は、他局受信終了ごと・起動時・送信直前に同じペイロードを再送し、Analog_Bridge の Talker Alias 状態を自局に上書きし続ける。

### 送信シーケンス

1） 🔴V1.83 `TX_METADATA_ENABLED` なら SET_INFO メタデータを1回送出
2） 前パディング: `PRE_POST_PADDING_PACKETS`（75）回。🔴V1.84〜V1.89 先頭 `NOISE_LEAD_PACKETS`（65）個は100Hzリード音（末尾フェード）、残りは無音
3） 本体: WAV から `readframes(160)` で読み、320バイトに満たなければ0詰め。🔵V1.86 本体中の無音は置換しない（真の無音のまま送る）
4） 後パディング: 無音（`\x00`×320）を75回。🔵V1.86 後パディングは常に真の無音
5） PTT OFF: keyup=0 のヘッダ＋無音を `USRP_EOT_REPEAT`（既定1）回送って終了。🔴V1.82 取りこぼし対策で複数回送出可能

### 絶対時刻同期（ドリフト補正）

基準時刻 `next_send_time = time.monotonic()` から、各パケット送出後に `PACKET_INTERVAL`（20ms）を加算し、その時刻まで `time.sleep()` する。単純な `time.sleep(0.02)` の積み上げではなく基準時刻からの累積で次回送出時刻を決めるため、処理時間のブレ（ドリフト）が蓄積しない。`time.monotonic()` を使うのは NTP 等の時刻補正で巻き戻らないため。

---

## 9. 音声生成パイプラインとキャッシュ

### 9-1. 合成パイプライン（_generate_hybrid）

`_generate_hybrid(intro, middle_text, outro, out_path=TEMP_FINAL, head_silence=0.0)` の処理。`intro`/`outro` は WAV パス、`middle_text` は読み上げる日本語テキスト。🔵V1.75 で `out_path`（キャッシュ用の任意出力先）と `head_silence`（頭無音の焼き込み秒数）の引数を追加。

1） open_jtalk: middle_text → TEMP_48K（48kHz WAV）。stdin へ communicate() で UTF-8 を流し込む
2） sox: TEMP_48K → TEMP_8K（8kHz / mono / 16bit）
3） sox: intro に `pad head_silence GAP_AFTER_INTRO_SEC` で先頭無音（🔴V1.80、kerchunk応答のみ）と末尾無音を付与 → TEMP_INTRO_PADDED
4） sox: TEMP_INTRO_PADDED + TEMP_8K [+ outro] を連結。TX_GAIN が1.0以外なら `vol` 効果を付与 → out_path

outro が None の場合は連結しない（時報・起動・ナイト・10分IDはアウトロなし）。戻り値は True/False。途中の open_jtalk/sox が失敗したら False を返し、呼び出し側は送出しない。

🔴V1.92 での変更点: 中間ファイル（TEMP_48K/TEMP_8K/TEMP_INTRO_PADDED）の掃除は「生成の責任」として、`_gen_lock` 保持のまま `finally` 節内で行うよう変更（レビュー指摘の採用）。ロック内なので他スレッドの生成と競合せず、作業ファイルの寿命が明確になる。out_path（TEMP_FINAL やキャッシュ本体）は呼び出し元が送信で読むため、ここでは削除しない。

| mode | intro | middle_text | outro |
|---|---|---|---|
| kerchunk | fixed_intro（head_silence=PRE_AUDIO_SILENCE_SEC） | 「（カナ）局の、」 | fixed_outro |
| time_signal / half_hour_signal | time_intro | 「〇〇時です」/「〇〇時30分です」 | なし |
| startup_announce | fixed_intro | 「起動しました。」 | なし |
| night_announce | fixed_intro | 「ただいまより…ナイトモードに入ります。」 | なし |
| fixed_file / regulatory_id | — | （合成せず既成WAVをそのまま送出、TX_GAIN適用） | — |

### 9-2. 応答音声キャッシュ（🔵V1.75〜、即応答化）

置き場所は `/dev/shm`（RAM）。プロセス再起動で自動クリアされ、設定は起動時のみ読むため、キャッシュは常に現在の設定と整合する。intro（cstm差し替え含む）/outro/GAP/頭無音/TX_GAIN/音声モデル/スキーマ版のシグネチャを `.sig` として併存させ、変化したら自動再生成する。

処理の流れ:

1） ヘッダ受信時に `_prewarm_reply(cs)` を呼び、未キャッシュなら背景スレッドで先行生成を開始
2） `_ensure_cached(cs)` はロック外の高速ヒット判定を行い、命中していれば即座に (path, True) を返す
3） 未命中時は `_cs_build_lock(cs)` を取得し、待機中に他スレッドが生成済みでないか再確認してから合成
4） 合成は `.building.wav` の一時名で行い、完成後 `os.replace()` で原子的に本名へ差し替える（🔴V1.76: 一時ファイルも必ず.wav拡張子にする。SoXは拡張子でフォーマット判別するため）
5） 署名ファイル（`.sig`）を書き込み、以後のヒット判定に使う

REPLY_CACHE_ENABLED=False のときは V1.74 と同一挙動（毎回 TEMP_FINAL に生成、キャッシュ機構を経由しない）。

---

## 10. ナイトモード仕様

時報と定時メッセージで抑制開始時刻が異なる（V1.61の要点。以降のバージョンでも変更なし）。

| 判定関数 | 対象 | 抑制範囲 | 例（N1=22, N2=5） |
|---|---|---|---|
| `_is_night_suppressed` | 時報 | N1+1 時 〜 N2 時 | 23〜5時を抑制（22時の時報は出す） |
| `_is_night_suppressed_message` | 定時メッセージ | N1 時 〜 N2 時 | 22〜5時を抑制（22時台から止める） |

両関数とも、`suppress_start <= suppress_end` か否かで日跨ぎを処理する。

### 動作例（N1=22, N2=5）

| 時刻 | 時報(:00) | 定時 |
|---|---|---|
| 〜21時台 | 出す | 出す |
| 22:00 | 出す（＋突入アナウンス） | — |
| 22時台の定時 | — | 抑制 |
| 23〜翌5時台 | 抑制 | 抑制 |
| 6:00〜 | 再開 | 再開 |

### 突入アナウンス

時報送出時、`NIGHT_MODE_ENABLED` かつ `val == NIGHT_START_HOUR` の場合のみ、時報の後に `_send_night_mode_announcement()` を呼ぶ。文面は「ただいまより、このデジピーターは、明朝〇時まで、ナイトモードに入ります。」（〇＝N2+1時）。

カーチャンク応答・🔴V1.74の識別信号強制送信（regulatory_id）は、いずれもナイトモードの影響を受けない（24時間動作）。抑制対象は時報と定時メッセージのみ。

---

## 11. ログ出力仕様

`_fmt(tag, action, target, extra)` で整形し、stdout（systemdではjournal）へ出力。

書式: `YYYY-MM-DD HH:MM:SS,mmm [tag] action target extra`

| tag | 意味 |
|---|---|
| `..` | 情報・トリガ・スケジューラ・QSOセッション開始等 |
| `TX` | 送出関連（Generate/Cached/Sending/Complete/RegID等） |
| `--` | 抑制（Suppress） |
| `!!` | エラー・警告 |

主なメッセージ例:

| 出力 | 意味 |
|---|---|
| `Config loaded ...` | 設定読込成功 |
| `Bot ready — monitoring DMR traffic` | 監視開始 |
| `Startup ann scheduled in 5.0s` | 起動アナウンスを予約（V1.62） |
| `receive:Kerchunk detected: <CS> (0.9s) trigger` | カーチャンク検知・応答 |
| `receive:watchdog pseudo-end: <CS> (...)` | 🔴V1.67 watchdog擬似終端で救済 |
| `receive:watchdog ignored (high loss): <CS> (...)` | watchdogロス過大で無視 |
| `receive:Normal QSO detected: <CS>` | 通常QSO（長い送信）扱い |
| `QSO session start ...` | 🔴V1.74 長時間通信セッション開始 |
| `TX Regulatory ID ... (#N, rule 30)` | 🔴V1.74 10分IDを送信 |
| `Regulatory ID deferred (busy) ...` | 10分IDが競合でスキップ・次回再試行 |
| `TX Cached <CS>` / `TX Generate <CS>` | 🔵V1.75 キャッシュ命中／新規生成 |
| `Precache <CS> ready` / `failed` | 🔵V1.75 プリキャッシュ結果 |
| `TX lead <CS> 1.0s` | 🔴V1.77 キャッシュ命中時の送出前待機 |
| `NightSkip ... suppressed (night mode)` | ナイトモードで抑制 |
| `Log rotation detected: A -> B` | ログ切替 |

---

## 12. スレッド構成と終了処理

### スレッド

| スレッド | 関数 | 役割 |
|---|---|---|
| メイン | `monitor_and_reply` | ログ監視ループ |
| スケジューラ | `_announcement_scheduler`（daemon） | 時報・定時の発火監視（1秒間隔） |
| ワーカー | `_reply_executor`（daemon、都度生成） | 応答・時報・10分ID等の合成・送出 |
| プリキャッシュ | `_prewarm_reply` 内の worker（daemon、都度生成） | 🔵V1.75 ヘッダ受信時の背景合成 |
| 起動アナウンス | `threading.Timer` → `_send_startup_announcement` | 起動N秒後に1回だけ送出（V1.62） |

ワーカーは応答の都度 `_start_worker` から生成される使い捨てスレッド。`is_talking`＋`_reply_lock` で同時実行は1つに制限。🔴V1.91 で送信フロー全体（起動アナウンス含む）が `_tx_lock` でも直列化されるようになり、二重送信・共有一時ファイルの上書き競合・UDPストリーム混線を防ぐ。ロック順序は `_tx_lock`（外）→`_gen_lock`（内）で固定されておりデッドロックしない。プリキャッシュは `_gen_lock` のみ取得する（送信ではないため）。

### ログローテーション追従

メインループは行が無いとき `ROTATION_CHECK_INTERVAL`（5秒）ごとに最新ログを確認し、(a) ファイルパスが変わった、(b) 同じパスだがinodeが変わった（置換）場合に開き直す。

`_find_latest_log()` は、日付付きログ（`MMDVM_Bridge-YYYY-MM-DD.log`）を**ファイル名の辞書順**（`max(logs, key=os.path.basename)`）で比較して最新日付を選ぶ。🔴V1.63 で、サイズが0バイトのファイルは候補から除外するよう変更（セットアップ残骸や日付切り替わり直前の空ファイルを誤って「最新」として掴み、実際に書かれている前日ログを見失う事故を防止）。中身のあるログが1つもなければ、従来どおり全日付付きログから名前最大を選ぶ。日付付きログが1つも無い場合のみ、日付なしの `MMDVM_Bridge.log` にフォールバックする。

### 終了処理（Graceful Shutdown）

1） SIGTERM / SIGINT を `_handle_signal` が捕捉し `should_exit=True`
2） 各ループが条件を抜ける
3） メインはログファイルを閉じ、スケジューラスレッドを最大15秒join
4） `Bot stopped — goodbye 73` を出力して終了

送出中（`send_usrp_wav_with_padding` のループ）も `should_exit` を見ており、中断時はfinallyでPTT OFF（USRP_EOT_REPEAT回）を送ってからソケットを閉じる。

---

## 13. 改修時の注意点

| 項目 | 注意 |
|---|---|
| 絶対時刻同期ロジック | `send_usrp_wav_with_padding` の `next_send_time` 方式は音質の核心。単純な `time.sleep(0.02)` に書き換えると音がプツプツになる |
| UDP_PORTの一致 | `UDP_PORT(51000)` は Analog_Bridge の `rxPort` と必ず一致 |
| 設定は本体を編集しない | 動作パラメータは `bot_config.json`（bot_setup.pyで編集）。本体定数を直接いじらない |
| WAVは毎回読む | 送出のたびに `wave.open` するため、WAVを上書きすれば再起動なしで反映される |
| 辞書パス | `DICT_PATH` は `open-jtalk/` を含む正しいパスであること |
| ナイトモードの2関数 | 時報用と定時用で抑制範囲が違う。片方だけ直すと不整合になる |
| time_outroは未使用 | 定数は残るが現行ロジックで参照しない。将来再利用のための残置 |
| カスタム音声のフォールバック | `_resolve_wav` は送出のたびに実ファイルの有無を見る。ONでもファイルが無ければ標準で鳴り、送出は止まらない。regulatory_id（10分ID）だけは常に標準を使い、カスタムに差し替わらない |
| ログ時刻はタイムスタンプ差 | 受信時間はログの時刻差で測る。MMDVMのフレーム数長とは別物 |
| ログ選択はファイル名ベース | `_find_latest_log()` は `key=os.path.basename`。0バイトファイルは除外（V1.63） |
| 起動アナウンスは_tx_lock経由 | V1.91以降 `_send_startup_announcement` は `_tx_lock` を取得する。ロック順序（`_tx_lock`外→`_gen_lock`内）を崩すとデッドロックしうる |
| watchdog救済のロス閾値 | `WATCHDOG_MAX_LOSS_PCT` を緩めすぎると壊れた受信まで応答してしまう。実測分布（31〜75%）を踏まえて調整すること |
| 10分IDのカウンタ | `_handle_qso_session` は送信が競合してスキップされた場合カウンタを更新しない。ここを安易に更新すると法令上の識別信号漏れにつながる |
| キャッシュの整合性 | `_reply_signature()` に影響する要素（intro実体・GAP・頭無音・TX_GAIN・音声モデル）を追加/変更したら、必ず署名の対象に含めること。含め漏れると設定変更が反映されないキャッシュが残る |
| リード音とAMBE | ノイズ充填やゲートバーストの振幅・パケット数を変更する際は、AMBE（音声ボコーダ）が歪みとして符号化しない範囲（-40dB台以下が目安）に収めること |
| 中間ファイル掃除の責任分界 | V1.92以降、TEMP_48K等の掃除は `_generate_hybrid` の finally 内でのみ行う。実行中の横取り削除を復活させると生成中ファイルの競合（sox FAIL）を再発させる |

---

## 14. VV版差分（V1.96vv）

本章は **VV版（`dvs_ocv_vv/dvswitch_bot.py` V1.96vv）** に固有の差分のみを記述する。第1〜13章の本文（判定ロジック・第30条対応・USRP パケット・キャッシュ機構・ナイトモード・スレッド構成など）は JT版・VV版で共通であり、下記以外は本文どおりに動作する。

> 版番号の `vv` サフィックスは VOICEVOX 系ノード用ファイルであることを示す命名規約（Open JTalk 系 Pi ノード用の同名ファイルと区別する）。

---

### 14-1. 音声合成エンジンの置き換え（Open JTalk → VOICEVOX CORE）

| 項目 | JT版（本文 第9章） | VV版（V1.96vv） |
|---|---|---|
| 合成方式 | Open JTalk を **サブプロセス**（`open_jtalk`）で都度起動し WAV を生成 | VOICEVOX CORE の **同一プロセス内ライブラリ**（`voicevox_core.blocking`）で合成 |
| モデルのロード | 都度（プロセス起動のたび） | **起動時に 1 回だけ**ロードし、以降は常駐 |
| 合成パイプライン | `open_jtalk` → SoX(48k→8k) | `Synthesizer.create_audio_query` → `synthesis`（ネイティブ 24kHz）→ SoX(→8k) |

起動時に `Onnxruntime.load_once()` / `OpenJtalk(dict)` / `Synthesizer` を構築し、`VoiceModelFile.open()` で音声モデル（`.vvm`）を `load_voice_model()` する。以降の動的合成（時報の時刻・コールサイン読み等）はこの常駐シンセサイザで行う。中間 48kHz WAV を経ず、ネイティブ出力を SoX で 8kHz / mono / 16bit に変換する（`query.output_sampling_rate=48000` のハードコードは撤去済み）。

---

### 14-2. 話者（style_id / vvm）の決定と反映

- 話者は起動時に **`wav_source.json` の `"voice"`**（`style_id` と `vvm`）を読んで確定する（`_bootstrap_voice()`）。固定 WAV 側（`create_wav.sh` → `vv_say.py`）と bot の動的合成が **同一の話者選択を共有** する設計。
- `"voice"` が **無い / 壊れている / 指定 `vvm` が実在しない** 場合は、既定の **No.7（アナウンス）= `style_id 30` / `6.vvm`** へフォールバックする（`DEFAULT_VOICE_STYLE_ID = 30` / `DEFAULT_VOICE_VVM = "6.vvm"`）。`style_id` と `vvm` は不一致による合成失敗を避けるため必ずセットで扱う。
- 話者はプロセス起動時に **1 回だけ**ロードするため、**話者を変更した場合の動的合成への反映には bot の再起動が必要**（固定 WAV は送出のたびに読み直すため再起動不要、という本文の性質は VV版でも同じ）。

---

### 14-3. 応答音声キャッシュ署名への話者の追加

本文 第9-2章のキャッシュ署名（`_reply_signature()`）に、旧 Open JTalk の音声パスに代えて **VOICEVOX の `style_id`（`VOICEVOX_STYLE_ID`）とモデルパス（`VOICEVOX_VVM_PATH` + mtime）** を含める。これにより **話者・モデルを変更すると署名が変わり、キャッシュが自動的に無効化・再生成** される。intro/outro・GAP・頭無音・TX_GAIN・スキーマ版に依存する点は本文どおり。

---

### 14-4. onnxruntime .so のバージョン非依存解決

ONNX Runtime 共有ライブラリのパスをバージョン直書き（`libvoicevox_onnxruntime.so.1.17.3` 等）にせず、`glob` で `.../onnxruntime/lib/libvoicevox_onnxruntime.so*` を解決する（`_resolve_voicevox_so()`）。リリースにより `.so` の版番号が変わっても壊れない。見つからなければ `FileNotFoundError` で停止する。

---

### 14-5. 実行環境（venv 必須）

VV版は `voicevox_core` を含む **venv の Python で起動する**こと。

- 実行/起動: `/opt/dvswitch_bot/venv/bin/python3 /opt/dvswitch_bot/bin/dvswitch_bot.py`
- systemd 常駐化時も `ExecStart` を **venv の python3** にする（システムの `/usr/bin/python3` では `voicevox_core` が import できず `ImportError/ModuleNotFoundError` で即死する）。詳細は『システム仕様書』第8章の VV版ユニット例を参照。

---

*dvswitch_bot.py ソフトウェア仕様書（JT版 V1.93 / VV版 V1.96vv）*
*対象: /opt/dvswitch_bot/bin/dvswitch_bot.py（JT版 daemon, V1.60〜V1.93 の集大成）／ dvs_ocv_vv/dvswitch_bot.py（VV版 V1.96vv）*
*Contributors: JA2CCV / JI2TAB / JJ2YYK / OpenCCVoice Contributors*
