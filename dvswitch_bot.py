#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 DVSwitch ログ監視・自動音声応答システム（デーモン版 / config-driven）
 — JJ2YYK デジピーター自動応答システム  V1.70 —

 本ファイルは V1.69（V1.68 + 機械可読 __version__）に、watchdog 経路専用の
 カーチャンク上限 WATCHDOG_RX_MAX_SEC を追加したもの。

【V1.70 での変更点（watchdog 経路の判定上限を分離）】
  - 🔴 watchdog 擬似終端経路のカーチャンク上限を、end 経路と別の専用定数
    WATCHDOG_RX_MAX_SEC（既定 5.0 秒）で判定するようにした。
    背景: watchdog 経過秒は MMDVM のタイムアウト（約2秒）を含んで長めに出るため、
    短い SFR キーチャンクでも 2.6〜4.1 秒として記録される。これに end 用の
    RX_DURATION_MAX_SEC（カーチャンク上限, 通常 2.5 前後）を当てると「Normal QSO」
    に誤判定され、ID 応答しないばかりか 15 秒の抑制まで走り、後続の本物の
    キーチャンク（例 2.3 秒）まで巻き添えで抑制された（2026-06-23 実機で確認）。
    対策: _handle_rx_duration() で source="watchdog" のときだけ上限を
    WATCHDOG_RX_MAX_SEC に差し替える。end 経路（source="eot"）は従来どおり
    RX_DURATION_MAX_SEC を使い、挙動は一切変えない。
    下限(MIN)は両経路とも RX_DURATION_MIN_SEC を据え置き。
  - 実測（2026-06-23）の谷: SFR キーチャンクの watchdog 経過秒は 2.3〜4.1s、本物の
    QSO は 8.8s 以上。5.0 はその中間で、両者を確実に分離できる。
  - 🔵 本値はソース定数（bot_config.json では未管理）。将来 GUI 調整したくなったら
    任意キー化＋bot_setup.py / app.py 対応を別途行う。

【V1.69 での変更点（機械可読バージョン __version__ の追加）】
  - 🔵 ファイル冒頭付近（docstring 直後）に __version__ = "V1.69" を新設。
    ダッシュボード app.py（V2.75〜）がこの固定行を最優先で参照してバージョンを
    表示する。docstring（人間向けの "Document Version:"）が長くなっても、版表示が
    取りこぼされないようにするための恒久対策。
    背景: app.py V2.73〜V2.74 は bot 先頭 4000 バイトだけを読んで版を抽出して
    いたが、V1.68 で docstring が伸び "Document Version:" 行が 9600 バイト超に
    なり、ダッシュボードのバージョン表示が空になった。app.py 側は全体読みの
    フォールバックを入れて堅牢化（V2.75）。bot 側は本固定行で確実性を担保する。
  - 機能面は V1.68 と完全に同一（watchdog 擬似終端 + TX_GAIN）。挙動変更なし。
  - 版を更新する際は __version__ と "Document Version:" を必ず一致させること。

【V1.68 での変更点（送出音量ゲイン TX_GAIN の追加）】
  - 🔴 bot が送出する音声すべて（カーチャンクID / 時報 / 30分案内 / 起動・ナイト
    アナウンス / 定時メッセージ 001・002）の音量を、設定ファイルの任意キー
    TX_GAIN（線形倍率, 1.0=等倍）で一律に調整できるようにした。
    Analog_Bridge.ini の usrpGain と同じ「1.0=等倍」の倍率表現。主用途は減衰
    （<1.0）。実装は SoX の vol 効果を 1 段付与する。
      * 合成系（_generate_hybrid）: 最終結合コマンドに vol を付与。
      * 固定再生（fixed_file=001/002）: _generate_hybrid を通らないため、送出前に
        vol をかけた一時ファイルを作って送出する。
    TX_GAIN == 1.0 のときは vol を付けない＝V1.67 と完全に同一の出力。
  - 🔵 後方／前方互換（重要）:
      * TX_GAIN は任意キー。REQUIRED_KEYS には入れない。
      * 旧 JSON（TX_GAIN 無し）+ 新 bot → 既定 1.0（等倍）で動作。起動拒否しない。
      * 新 JSON（TX_GAIN 有り）+ 旧 bot（V1.67以前）→ 旧 bot は未知キーを無視する
        （REQUIRED_KEYS の欠落のみ検査）ため無影響。電波・動作に影響しない。
  - 🔵 フェイルセーフ（音量は安全に直結しないため exit しない）:
    TX_GAIN が「数値でない / 0以下 / 範囲外（>5.0）」の場合は、送出を止めず
    1.0（等倍）にフォールバックし、警告ログを出す。RF パラメータ（TG/周波数）の
    ような fatal 扱いはしない（音量の誤設定で送信そのものを止める方が有害なため）。
  - ⚠️ 注意（永続性）: bot_setup.py / app.py（ダッシュボード）は現状 TX_GAIN を
    認識せず、保存時に bot_config.json を「知っているキーだけで」書き直す。よって
    手で TX_GAIN を入れても、それらのツールで保存し直すと消える。GUI/対話から
    恒久的に扱いたい場合は bot_setup.py / app.py 側にも TX_GAIN 対応が必要。

【V1.67 での変更点（V1.64 への watchdog 擬似終端の統合）】
 本ファイルは V1.64（JJ2YYK 系 / TIME_SIGNAL_MODE で時報を30分対応にした系統）
 をベースに、別系統 V1.65 の「watchdog 擬似終端」機能のみを統合したもの。

 ⚠️ ブランチ注意（系統の整理）:
   - V1.64 : JJ2YYK 系。TIME_SIGNAL_MODE で毎正時/30分の時報切替に対応。
   - V1.66 : JJ2ZAR 系（実機稼働）。watchdog 擬似終端(V1.65) + late entry 救済(V1.66)。
   本 V1.67 は「V1.64 + V1.65(watchdog 擬似終端のみ)」である。
   🔵 V1.66 の late entry 開始イベント救済（LATE_ENTRY_AS_START）は
      「擬似終端」ではなく「開始イベントの救済」であり、今回の統合対象外。
      必要になった場合は別途追加すること。

【V1.67 での変更点（V1.64 への watchdog 擬似終端の統合）】
  - 🔴 network watchdog を擬似終端として扱う分岐を追加（V1.65 から移植）。
    背景: DB40-D の SFR（単一周波数中継）で中継すると、入力 DMR ストリームの
    終端パケットが落ち、MMDVM_Bridge が
      "received network end of voice transmission"
    を記録せず
      "network watchdog has expired, X.X seconds, NN% packet loss"
    で打ち切るケースが多発する。従来は end of voice transmission でしか dur を
    計算しなかったため、watchdog で切れた送信はカーチャンク判定に到達せず
    （last_cs が次のヘッダで上書きされて消えるだけ）応答できなかった。
    対策: voice header を受けた後に watchdog 行が来たら、その行の経過秒を
    擬似的な受信時間として扱い、従来の end of voice transmission と同じ
    カーチャンク判定ルート（_handle_rx_duration）に流す。
  - 🔴 過剰応答の防止ガード WATCHDOG_MAX_LOSS_PCT（既定 75%）を新設。
    watchdog 行に出ている packet loss がこの値を超える送信は「壊れていて
    用をなさない受信」とみなし、擬似終端として拾わない（無視）。
    （V1.65 では既定 50% だったが、実ログのロス分布 31〜75% に合わせ 75% を採用。
      全部拾うなら 100、厳しくするなら 30〜50 に調整可。）
  - 🔴 WATCHDOG_PSEUDO_END_ENABLED（既定 True）で本機能を一括 ON/OFF できる。
    False にすれば従来 V1.64 と完全に同一の挙動（end でのみ判定）に戻る。
  - 🔵 カーチャンク判定/抑制ロジックを _handle_rx_duration() に切り出し、
    end of voice transmission 経路と watchdog 経路で同一ロジックを共有する。
    ログ表記は source 引数で "(watchdog)" を付して区別する（挙動は同一）。
  - 🔵 watchdog の経過秒について:
    MMDVM の watchdog タイムアウト（約2秒）を含むため、実際のキーダウン時間
    より長めに出る点に注意。真のキーダウン時間ではなく「ヘッダ受信〜watchdog
    までの経過」に近い。カーチャンク検知の目的（短時間キーアップの検出）には
    十分だが、RX_DURATION の閾値はこの特性を踏まえて調整すること。

【V1.64 での変更点】
  - 🔴 TIME_SIGNAL_MODE（0/1/2）を新設。時刻案内の頻度を選べるようにした。
      * 0 : 時刻案内しない
      * 1 : 毎正時のみ「○○時です」（従来動作）
      * 2 : 毎正時「○○時です」＋毎30分「○○時30分です」
    30 分案内は新モード half_hour_signal として _reply_executor に追加。
    TIME_INTRO_WAV を流用し、中間テキストを "{時}時30分です" とする。
  - 🔴 _get_trigger_minutes() を TIME_SIGNAL_MODE 依存に再設計。
  - 🔴 スケジューラを :00 / :30 の両境界で lead 発火するよう一般化。
  - 🔵 30分案内のナイトモード抑制は「定時メッセージと同じ窓（N1時〜N2時）」を採用。
  - 🔵 TIME_SIGNAL_MODE は任意キー。未設定の既存 bot_config.json は従来動作
    （mode 1）として扱い、起動を拒否しない（アップグレード互換）。

【V1.63 での変更点】
  - 🔴 _find_latest_log() を「0バイトファイルをスキップ」するよう改良。
    （2026-06-06 実機で発生した、空の日付付きログを掴んで前日ログを見失う
    事故への対策。詳細は _find_latest_log() のコメント参照。）

【V1.62 での変更点】
  - 🔴 起動アナウンスを追加（起動 N 秒後に「起動しました。」を 1 回送出）。

【V1.61 での変更点】
  - 🔴 ナイトモードの抑制を「時報」と「定時メッセージ」で分離。
  - 🔴 ログローテーション選択を getctime からファイル名ベースに修正。

【V1.60 からの変更点（デーモン化）】
  - 起動時の対話設定を廃止し、設定ファイル(JSON)読み込みに置き換え。
  - 🔴 フェイルセーフ: 設定が無い/壊れ/欠落/不正なら exit(1)。

【設定項目（bot_config.json）】
  RX_DURATION_MIN_SEC : 最小受信時間（秒, 0 < MIN < MAX）
  RX_DURATION_MAX_SEC : 最大受信時間（秒, カーチャンク上限）
  ANNOUNCE_FREQ       : 1時間あたりの放送回数（TIME_SIGNAL_MODE 依存）
  TIME_SIGNAL_MODE    : 時刻案内モード（0/1/2, 任意キー。未設定なら 1）
  NIGHT_MODE_ENABLED  : ナイトモード有効（true / false）
  NIGHT_START_HOUR    : ナイトモード開始 N1（0〜23）
  NIGHT_END_HOUR      : ナイトモード終了 N2（0〜23）

【機能】
  - 起動アナウンス（起動 N 秒後に「起動しました。」を 1 回送出）
  - ナイトモード（時報は N1+1時〜N2時を抑制／定時メッセージは N1時〜N2時を抑制。
    N1時は時報＋突入アナウンスを出す。kerchunk は24時間応答）
  - 毎正時の時報（lead 秒前に発火）/ 30分案内 / 定時メッセージ（001/002 交互）
  - カーチャンク検知応答 / 重複応答防止 / イントロ・アウトロ結合
  - 🔴 watchdog 擬似終端救済（SFR 中継で end が落ちた送信を拾う）
  - 絶対時刻同期の UDP 送信（ドリフト補正）
  - ログローテーション対応 / Graceful shutdown

【固定 WAV（事前作成が必要）】
  /opt/dvswitch_bot/fixed_intro.wav / fixed_outro.wav / time_intro.wav
  /opt/dvswitch_bot/001.wav / 002.wav
  ※ time_outro.wav は不要（動的合成に統合）

【配置】
  /opt/dvswitch_bot/bin/dvswitch_bot.py
  （WAV・設定 JSON は /opt/dvswitch_bot/ 直下。BOT_DIR 参照）

【使い方】
  1) sudo python3 /opt/dvswitch_bot/bin/bot_setup.py     # 先に設定ファイルを作成
  2) python3 /opt/dvswitch_bot/bin/dvswitch_bot.py       # または systemd で常駐

 Document Version: V1.70 (daemon, V1.69 + watchdog-specific kerchunk max)
 Last Updated: 2026-06-23
================================================================================
"""

# ============================================================
# 🔵 機械可読バージョン（固定行 / ダッシュボード app.py が最優先で参照）
# ============================================================
# この行はファイル冒頭付近に固定で置く。docstring（人間向けの "Document Version:"）
# が長くなっても、ダッシュボードはこの __version__ を確実に拾える。
# 版を上げるときは下の文字列も必ず更新すること（docstring と一致させる）。
__version__ = "V1.70"

import os
import sys
import json
import time
import glob
import re
import socket
import struct
import wave
import signal
import logging
import threading
import subprocess
from datetime import datetime, timedelta

# ============================================================
# 基本設定
# ============================================================
LOG_DIR = "/var/log/mmdvm"
LOG_PATTERN = "MMDVM_Bridge-*.log"
UDP_IP = "127.0.0.1"
UDP_PORT = 51000

MY_CALLSIGN = "JJ2YYK"
DICT_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"

# 固定 WAV ファイルのパス
BOT_DIR = "/opt/dvswitch_bot"
FIXED_INTRO_WAV = f"{BOT_DIR}/fixed_intro.wav"
FIXED_OUTRO_WAV = f"{BOT_DIR}/fixed_outro.wav"
TIME_INTRO_WAV  = f"{BOT_DIR}/time_intro.wav"
TIME_OUTRO_WAV  = f"{BOT_DIR}/time_outro.wav"
MSG_FILES = [f"{BOT_DIR}/001.wav", f"{BOT_DIR}/002.wav"]

# 🔴 設定ファイル（bot_setup.py が作成する）
CONFIG_PATH = f"{BOT_DIR}/bot_config.json"
REQUIRED_KEYS = [
    "RX_DURATION_MIN_SEC",
    "RX_DURATION_MAX_SEC",
    "ANNOUNCE_FREQ",
    "NIGHT_MODE_ENABLED",
    "NIGHT_START_HOUR",
    "NIGHT_END_HOUR",
]

# 一時ファイル(/dev/shm = RAM ディスクで SD カード保護)
_PID = os.getpid()
TEMP_FINAL = f"/dev/shm/reply_final_{_PID}.wav"
TEMP_48K   = f"/dev/shm/tmp_48k_{_PID}.wav"
TEMP_8K    = f"/dev/shm/tmp_8k_{_PID}.wav"
TEMP_INTRO_PADDED = f"/dev/shm/tmp_intro_padded_{_PID}.wav"

# タイミング関連
EMPTY_HEADER_THRESHOLD_SEC = 0.1
SUPPRESS_DURATION_SEC = 15.0
PACKET_INTERVAL = 0.02
PRE_POST_PADDING_PACKETS = 75
ROTATION_CHECK_INTERVAL = 5.0
GAP_AFTER_INTRO_SEC = 0.5

# 🔴 起動アナウンス遅延（秒）。起動後この秒数だけ待ってから送出する。
STARTUP_ANNOUNCE_DELAY_SEC = 5.0

# ============================================================
# 🔴 V1.67: watchdog 擬似終端の設定（V1.65 から移植）
# ============================================================
# SFR 中継で終端パケットが落ち、end of voice transmission が記録されず
# watchdog で打ち切られる送信を、擬似終端として拾ってカーチャンク判定に流すか。
# False にすると V1.64 と完全に同一の挙動（end でのみ判定）に戻る。
WATCHDOG_PSEUDO_END_ENABLED = True

# watchdog 擬似終端のロス上限（%）。watchdog 行の packet loss がこの値を超える
# 送信は「壊れていて用をなさない受信」とみなし、擬似終端として拾わない。
# 例) 75 のとき: 75% 以下 → 救済 / 76〜100% loss → 無視。
# 実ログの watchdog ロス分布（31〜75%）に合わせ既定 75。
# さらに全部拾うなら 100（ロスガード事実上無効）、厳しくするなら 30〜50。
WATCHDOG_MAX_LOSS_PCT = 75

# 🔴 V1.70: watchdog 経路専用のカーチャンク上限（秒）。
# watchdog 経過秒は MMDVM のタイムアウト（約2秒）を含んで長めに出るため、end 用の
# RX_DURATION_MAX_SEC（カーチャンク上限, 通常 2.5 前後）をそのまま当てると、短い
# キーチャンクが Normal QSO に誤判定される。watchdog 経路だけこの値で判定する。
# 実測（2026-06-23）: SFR キーチャンクの watchdog 経過秒は 2.3〜4.1s、本物の QSO は
# 8.8s 以上で、その間に谷がある。5.0 はその谷の中央＝両者をきれいに分離できる値。
# end 経路（通常終端）はこの値を使わず RX_DURATION_MAX_SEC のまま（挙動不変）。
WATCHDOG_RX_MAX_SEC = 5.0

# ============================================================
# 🔴 V1.68: 送出音量ゲイン（任意キー TX_GAIN）の既定値と有効範囲
# ============================================================
# TX_GAIN は線形倍率（1.0=等倍）。Analog_Bridge.ini の usrpGain と同じ表現。
# 主用途は減衰（<1.0）。bot が出す音すべて（ID/時報/30分案内/起動・ナイト案内/
# 001・002）に一律で効く。bot_config.json の任意キーで、無ければ等倍。
TX_GAIN_DEFAULT = 1.0
TX_GAIN_MIN = 0.0    # これより大きいこと（0 以下は無効＝無音化を防ぐ）
TX_GAIN_MAX = 5.0    # これ以下（usrpGain と同じ 0.0–5.0 レンジ。>1.0 はクリップ注意）

# ============================================================
# グローバル状態 / 設定値
# ============================================================
should_exit = False
suppress_until = 0.0
is_talking = False
_reply_lock = threading.Lock()

# 設定値（_load_config() が JSON から設定する。初期値はあくまでプレースホルダ）
RX_DURATION_MIN_SEC = None
RX_DURATION_MAX_SEC = None
ANNOUNCE_FREQ = None
TIME_SIGNAL_MODE = None
TX_GAIN = None
NIGHT_MODE_ENABLED = None
NIGHT_START_HOUR = None
NIGHT_END_HOUR = None

# コールサイン → カナ変換テーブル
CHAR_TO_KANA = {
    "A": "エー", "B": "ビー", "C": "シー", "D": "ディー", "E": "イー",
    "F": "エフ", "G": "ジー", "H": "エイチ", "I": "アイ", "J": "ジェイ",
    "K": "ケー", "L": "エル", "M": "エム", "N": "エヌ", "O": "オー",
    "P": "ピー", "Q": "キュー", "R": "アール", "S": "エス", "T": "ティー",
    "U": "ユー", "V": "ブイ", "W": "ダブリュー", "X": "エックス", "Y": "ワイ",
    "Z": "ゼット", "0": "ゼロ", "1": "ワン", "2": "ツー", "3": "スリー",
    "4": "フォー", "5": "ファイブ", "6": "シックス", "7": "セブン", "8": "エイト",
    "9": "ナイン", "-": "ダッシュ", "/": "スラッシュ",
}

# ============================================================
# ロガー
# ============================================================
logger = logging.getLogger("dvswitch_bot")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
logger.addHandler(_handler)


def _fmt(tag, action, target="", extra=""):
    action_str = f"{action:<12}"
    if extra:
        target_str = f"{target:<10}" if target else " " * 10
        return f"[{tag}]  {action_str} {target_str}  {extra}".rstrip()
    else:
        return f"[{tag}]  {action_str} {target}".rstrip()


# ============================================================
# 🔴 設定読み込み + 検証（フェイルセーフ）
# ============================================================
def _fatal_config(msg):
    """設定エラーで安全に停止する。誤動作させずに exit(1)。"""
    logger.error("=" * 70)
    logger.error(_fmt("!!", "Config error", "", msg))
    logger.error(_fmt("!!", "Hint", "", f"設定ファイル: {CONFIG_PATH}"))
    logger.error(_fmt("!!", "Hint", "", "先に 'sudo python3 /opt/dvswitch_bot/bin/bot_setup.py' を実行して設定を作成してください"))
    logger.error("デフォルト値での起動は安全のため行いません（意図しない送信を防止）。")
    logger.error("=" * 70)
    sys.exit(1)


def _load_config():
    """bot_config.json を読み込み、厳格に検証してグローバルへ反映する。
    無い / 壊れている / 必須キー欠落 / 値が不正 のいずれでも exit(1)。
    """
    global RX_DURATION_MIN_SEC, RX_DURATION_MAX_SEC, ANNOUNCE_FREQ, TIME_SIGNAL_MODE
    global TX_GAIN, NIGHT_MODE_ENABLED, NIGHT_START_HOUR, NIGHT_END_HOUR

    # 1) 存在確認
    if not os.path.exists(CONFIG_PATH):
        _fatal_config(f"設定ファイルが見つかりません: {CONFIG_PATH}")

    # 2) JSON パース
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
            cfg = json.load(fp)
    except Exception as e:
        _fatal_config(f"JSON の読み込みに失敗しました: {e}")

    if not isinstance(cfg, dict):
        _fatal_config("設定ファイルの形式が不正です（オブジェクトではありません）")

    # 3) 必須キーの存在確認
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        _fatal_config(f"必須キーが不足しています: {', '.join(missing)}")

    # 4) 型・範囲の検証
    try:
        rx_min = float(cfg["RX_DURATION_MIN_SEC"])
        rx_max = float(cfg["RX_DURATION_MAX_SEC"])
        freq = int(cfg["ANNOUNCE_FREQ"])
        # TIME_SIGNAL_MODE は任意キー。無い既存設定は従来動作(=毎正時の時報)である
        # mode 1 として扱う（アップグレード時に起動を拒否しないため）。
        if "TIME_SIGNAL_MODE" in cfg:
            ts_mode = int(cfg["TIME_SIGNAL_MODE"])
        else:
            ts_mode = 1
            logger.info(_fmt("..", "Config", "TIME_SIGNAL_MODE",
                             "未設定のため既定値 1（毎正時の時報）を使用"))
        night_enabled = cfg["NIGHT_MODE_ENABLED"]
        n1 = int(cfg["NIGHT_START_HOUR"])
        n2 = int(cfg["NIGHT_END_HOUR"])
    except (ValueError, TypeError) as e:
        _fatal_config(f"値の型が不正です: {e}")

    if not isinstance(night_enabled, bool):
        _fatal_config("NIGHT_MODE_ENABLED は true / false で指定してください")

    if not (rx_min > 0):
        _fatal_config(f"RX_DURATION_MIN_SEC は 0 より大きい必要があります（現在: {rx_min}）")
    if not (rx_min < rx_max):
        _fatal_config(f"RX_DURATION_MIN_SEC < RX_DURATION_MAX_SEC である必要があります（現在: {rx_min} / {rx_max}）")
    if ts_mode not in (0, 1, 2):
        _fatal_config(f"TIME_SIGNAL_MODE は 0 / 1 / 2 のいずれかです（現在: {ts_mode}）")
    # ANNOUNCE_FREQ の有効範囲は TIME_SIGNAL_MODE に依存する
    #   mode 0: 0/1/2/3/4   mode 1: 0/1/2/3   mode 2: 0/2
    _valid_freq = {0: (0, 1, 2, 3, 4), 1: (0, 1, 2, 3), 2: (0, 2)}[ts_mode]
    if freq not in _valid_freq:
        _fatal_config(
            f"ANNOUNCE_FREQ は TIME_SIGNAL_MODE={ts_mode} のとき "
            f"{'/'.join(map(str, _valid_freq))} のいずれかです（現在: {freq}）")
    if not (0 <= n1 <= 23):
        _fatal_config(f"NIGHT_START_HOUR は 0〜23 です（現在: {n1}）")
    if not (0 <= n2 <= 23):
        _fatal_config(f"NIGHT_END_HOUR は 0〜23 です（現在: {n2}）")

    # 🔴 V1.68: TX_GAIN（任意キー / 送出音量の線形倍率, 1.0=等倍）
    # 無ければ等倍（=従来挙動）。値が不正でも送出は止めず 1.0 にフォールバックして
    # 警告する（音量は RF 安全に直結しないため fatal にしない）。
    tx_gain = TX_GAIN_DEFAULT
    if "TX_GAIN" in cfg:
        try:
            _g = float(cfg["TX_GAIN"])
        except (ValueError, TypeError):
            _g = None
        if _g is None or not (TX_GAIN_MIN < _g <= TX_GAIN_MAX):
            logger.warning(_fmt("!!", "TX_GAIN", str(cfg.get("TX_GAIN")),
                                 f"不正な値のため {TX_GAIN_DEFAULT}（等倍）にフォールバック "
                                 f"（有効範囲: {TX_GAIN_MIN} 超 〜 {TX_GAIN_MAX} 以下）"))
            tx_gain = TX_GAIN_DEFAULT
        else:
            tx_gain = _g
            if tx_gain > 1.0:
                logger.warning(_fmt("..", "TX_GAIN", f"{tx_gain}",
                                    "1.0 超のため増幅（クリップに注意）"))
    else:
        logger.info(_fmt("..", "TX_GAIN", "未設定",
                         f"既定 {TX_GAIN_DEFAULT}（等倍 / 音量変更なし）を使用"))

    # 5) 反映
    RX_DURATION_MIN_SEC = rx_min
    RX_DURATION_MAX_SEC = rx_max
    ANNOUNCE_FREQ = freq
    TIME_SIGNAL_MODE = ts_mode
    TX_GAIN = tx_gain
    NIGHT_MODE_ENABLED = night_enabled
    NIGHT_START_HOUR = n1
    NIGHT_END_HOUR = n2

    logger.info(_fmt("..", "Config", "loaded", CONFIG_PATH))


def _handle_signal(signum, frame):
    global should_exit
    sig_name = signal.Signals(signum).name
    logger.info(_fmt("..", "Signal", sig_name, "shutting down"))
    should_exit = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ============================================================
# 送信・生成
# ============================================================
def send_usrp_wav_with_padding(wav_path):
    """WAV を USRP プロトコルで送信(前後 1.5 秒のパディング付き、絶対時刻同期)"""
    sock = None
    wf = None
    seq = 0
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        wf = wave.open(wav_path, "rb")

        next_send_time = time.monotonic()

        for _ in range(PRE_POST_PADDING_PACKETS):
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

        while not should_exit:
            data = wf.readframes(160)
            if not data:
                break
            if len(data) < 320:
                data += b"\x00" * (320 - len(data))
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + data, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

        for _ in range(PRE_POST_PADDING_PACKETS):
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

    except Exception as e:
        logger.error(_fmt("!!", "Send error", "", str(e)))
    finally:
        if sock:
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 0, 0, 0, 0, 0)
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            sock.close()
        if wf:
            wf.close()


# ============================================================
# ナイトモード判定
# ============================================================
def _is_night_suppressed(hour):
    """時報の抑制判定。N1時の時報は出す（突入アナウンスのため）。
    抑制は N1+1 時 〜 N2 時。例) N1=22, N2=5 → 23,0,1,2,3,4,5 時を抑制。"""
    if not NIGHT_MODE_ENABLED:
        return False
    suppress_start = (NIGHT_START_HOUR + 1) % 24
    suppress_end = NIGHT_END_HOUR % 24
    if suppress_start <= suppress_end:
        return suppress_start <= hour <= suppress_end
    else:
        return hour >= suppress_start or hour <= suppress_end


def _is_night_suppressed_message(hour):
    """定時メッセージの抑制判定。N1 時台から即抑制する
    （N1 時の時報＋突入アナウンスの後、同じ時間帯の定時メッセージは出さない）。
    抑制は N1 時 〜 N2 時。例) N1=22, N2=5 → 22,23,0,1,2,3,4,5 時を抑制。"""
    if not NIGHT_MODE_ENABLED:
        return False
    suppress_start = NIGHT_START_HOUR % 24
    suppress_end = NIGHT_END_HOUR % 24
    if suppress_start <= suppress_end:
        return suppress_start <= hour <= suppress_end
    else:
        return hour >= suppress_start or hour <= suppress_end


# ============================================================
# スケジューラー
# ============================================================
TIME_SIGNAL_LEAD_SEC = 7


def _get_trigger_minutes():
    """定時メッセージ（001/002交互）のトリガー分を返す。
    TIME_SIGNAL_MODE で占有される分（mode1:0 / mode2:0,30）は表に含めない。"""
    if TIME_SIGNAL_MODE == 0:
        table = {0: [], 1: [0], 2: [0, 30], 3: [0, 20, 40], 4: [0, 15, 30, 45]}
    elif TIME_SIGNAL_MODE == 1:
        table = {0: [], 1: [30], 2: [20, 40], 3: [15, 30, 45]}
    elif TIME_SIGNAL_MODE == 2:
        table = {0: [], 2: [15, 45]}
    else:
        table = {}
    return table.get(ANNOUNCE_FREQ, [])


def _announcement_scheduler():
    fired_signal_key = None       # 直近に発火した時刻案内の境界キー (date, hour, minute)
    fired_message_minute = None
    msg_index = 0

    logger.info(_fmt("..", "Scheduler", "started"))

    while not should_exit:
        now = datetime.now()

        # ---- 時刻案内（time_signal :00 / half_hour_signal :30）----
        # lead 秒前に発火。mode1=:00 のみ、mode2=:00 と :30。
        if TIME_SIGNAL_MODE >= 1:
            boundary_minutes = [0] if TIME_SIGNAL_MODE == 1 else [0, 30]
            for bmin in boundary_minutes:
                cand = now.replace(minute=bmin, second=0, microsecond=0)
                if cand <= now:
                    cand += timedelta(hours=1)
                secs = (cand - now).total_seconds()
                if 0 < secs <= TIME_SIGNAL_LEAD_SEC:
                    key = (cand.date(), cand.hour, bmin)
                    if fired_signal_key != key:
                        fired_signal_key = key
                        target_hour = cand.hour
                        if bmin == 0:
                            # 時報: N1 時は送出（突入アナウンスのため）
                            if _is_night_suppressed(target_hour):
                                logger.info(_fmt("..", "NightSkip", f"{target_hour:02d}:00",
                                                 "time_signal suppressed (night mode)"))
                            else:
                                logger.info(_fmt("..", "Trigger", f"{target_hour:02d}:00",
                                                 f"time_signal (lead {TIME_SIGNAL_LEAD_SEC}s)"))
                                _start_worker("time_signal", target_hour)
                        else:
                            # 30分案内: 定時メッセージと同じ抑制窓（N1時〜N2時）を使う。
                            # → N1:00 の突入アナウンス後に N1:30 が鳴らないようにするため。
                            if _is_night_suppressed_message(target_hour):
                                logger.info(_fmt("..", "NightSkip", f"{target_hour:02d}:30",
                                                 "half_hour_signal suppressed (night mode)"))
                            else:
                                logger.info(_fmt("..", "Trigger", f"{target_hour:02d}:30",
                                                 f"half_hour_signal (lead {TIME_SIGNAL_LEAD_SEC}s)"))
                                _start_worker("half_hour_signal", target_hour)

        # ---- 定時メッセージ（001/002 交互）----
        # トリガー分ちょうどに発火（リード無し）。:00 は TIME_SIGNAL_MODE==0 のときのみ
        # _get_trigger_minutes() に含まれる（mode1/2 では時刻案内が占有）。
        m = now.minute
        if m in _get_trigger_minutes():
            current_minute_key = (now.hour, m)
            if fired_message_minute != current_minute_key:
                fired_message_minute = current_minute_key
                if _is_night_suppressed_message(now.hour):
                    logger.info(_fmt("..", "NightSkip",
                                     f"{now.hour:02d}:{m:02d}",
                                     "scheduled_message suppressed (night mode)"))
                else:
                    target = MSG_FILES[msg_index % len(MSG_FILES)]
                    logger.info(_fmt("..", "Trigger",
                                     os.path.basename(target),
                                     "scheduled_message"))
                    _start_worker("fixed_file", target)
                    msg_index += 1

        time.sleep(1)

    logger.info(_fmt("..", "Scheduler", "stopped"))


def _start_worker(mode, val, extra=None):
    global is_talking
    with _reply_lock:
        if is_talking:
            logger.info(_fmt("..", "Skipped", str(val), f"already talking ({mode})"))
            return
        is_talking = True
    threading.Thread(target=_reply_executor, args=(mode, val, extra), daemon=True).start()


# ============================================================
# 🔴 V1.67: 受信時間に基づくカーチャンク判定/抑制（共通ロジック / V1.65 から移植）
# ============================================================
def _handle_rx_duration(cs, dur, source="eot"):
    """受信時間 dur(秒) に基づいてカーチャンク判定・抑制を行う。
    end of voice transmission 経路と watchdog 擬似終端経路で共有する。

    source : "eot"      = 正常終端（received network end of voice transmission）
             "watchdog" = 擬似終端（network watchdog has expired）

    🔴 V1.70: watchdog 経路はカーチャンク上限を専用値 WATCHDOG_RX_MAX_SEC に
    差し替える。watchdog 経過秒は MMDVM のタイムアウト（約2秒）を含んで長めに
    出るため、end 用の RX_DURATION_MAX_SEC（カーチャンク上限）をそのまま当てると
    短いキーチャンクが「Normal QSO」に誤判定され、応答せず＆15秒抑制まで走って
    後続のキーチャンクも巻き添えになる（2026-06-23 実機で発生）。
    end 経路（source="eot"）は従来どおり RX_DURATION_MAX_SEC を使い、挙動不変。
    下限(MIN)は両経路とも RX_DURATION_MIN_SEC を据え置き（watchdog 値は最小でも
    2s 超で MIN を余裕で超えるため取りこぼさない）。
    """
    global suppress_until
    now = time.monotonic()
    tag = "" if source == "eot" else " (watchdog)"

    # カーチャンク上限を経路で選び分ける（end は据え置き / watchdog は専用値）
    rx_max = RX_DURATION_MAX_SEC if source == "eot" else WATCHDOG_RX_MAX_SEC

    if RX_DURATION_MIN_SEC <= dur < rx_max:
        if suppress_until - now <= 0:
            logger.info(f"receive:Kerchunk detected{tag}: {cs} ({dur:.1f}s) trigger")
            _start_worker("kerchunk", cs, extra=dur)
        else:
            remain = suppress_until - now
            logger.info(f"receive:suppressed{tag}: {cs} ({dur:.1f}s, remaining {remain:.1f}s)")
    elif dur >= rx_max:
        suppress_until = now + SUPPRESS_DURATION_SEC
        logger.info(f"receive:Normal QSO detected{tag}: {cs} ({dur:.1f}s, max={rx_max}s)")
        logger.info(f"process:suppress start ({SUPPRESS_DURATION_SEC:.1f}s)　{cs}")
    else:
        logger.info(f"receive:Too short, ignored{tag}: {cs} ({dur:.1f}s, min={RX_DURATION_MIN_SEC}s)")


# ============================================================
# 🔴 起動アナウンス（V1.62）
# ============================================================
def _send_startup_announcement():
    """起動アナウンス。起動後 STARTUP_ANNOUNCE_DELAY_SEC 秒遅延して
    「起動しました。」を 1 回だけ送出する。
    is_talking と競合しないよう _start_worker は経由せず直接実行する。"""
    if should_exit:
        return
    started_at = time.monotonic()
    middle_text = "起動しました。"
    logger.info(_fmt("TX", "Generate", "startup", "startup_announce"))
    if _generate_hybrid(FIXED_INTRO_WAV, middle_text, None):
        logger.info(_fmt("TX", "Sending", "startup", "startup_announce"))
        send_usrp_wav_with_padding(TEMP_FINAL)
        elapsed = time.monotonic() - started_at
        logger.info(_fmt("TX", "Startup", "startup", f"{elapsed:.1f}s"))
    else:
        logger.error(_fmt("!!", "Gen failed", "startup", "startup_announce"))
    # 一時ファイルの後始末（_reply_executor の finally と同等）
    for tmp in (TEMP_FINAL, TEMP_48K, TEMP_8K, TEMP_INTRO_PADDED):
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError as e:
                logger.error(_fmt("!!", "Tmp rm err", os.path.basename(tmp), str(e)))


# ============================================================
# ナイトモード開始アナウンス
# ============================================================
NIGHT_ANN_GAP_SEC = 1.0


def _send_night_mode_announcement():
    started_at = time.monotonic()
    resume_hour = (NIGHT_END_HOUR + 1) % 24
    middle_text = f"ただいまより、このデジピーターは、明朝{resume_hour}時まで、ナイトモードに入ります。"
    label = f"N1={NIGHT_START_HOUR:02d}"

    time.sleep(NIGHT_ANN_GAP_SEC)

    logger.info(_fmt("TX", "Generate", label, "night_announce"))
    if _generate_hybrid(FIXED_INTRO_WAV, middle_text, None):
        logger.info(_fmt("TX", "Sending", label, "night_announce"))
        send_usrp_wav_with_padding(TEMP_FINAL)
        elapsed = time.monotonic() - started_at
        logger.info(_fmt("TX", "NightAnn", label, f"{elapsed:.1f}s"))
    else:
        logger.error(_fmt("!!", "Gen failed", label, "night_announce"))


def _reply_executor(mode, val, extra=None):
    global is_talking, suppress_until
    started_at = time.monotonic()
    try:
        if mode == "kerchunk":
            cs_kana = "".join([CHAR_TO_KANA.get(ch, ch) for ch in val.upper()])
            middle = f"{cs_kana}局の、"
            logger.info(_fmt("TX", "Generate", val))
            if _generate_hybrid(FIXED_INTRO_WAV, middle, FIXED_OUTRO_WAV):
                logger.info(_fmt("TX", "Sending", val))
                send_usrp_wav_with_padding(TEMP_FINAL)
                elapsed = time.monotonic() - started_at
                logger.info(_fmt("TX", "Complete", val, f"{elapsed:.1f}s"))
                suppress_until = time.monotonic() + SUPPRESS_DURATION_SEC
                logger.info(_fmt("--", "Suppress", val, f"{SUPPRESS_DURATION_SEC:.1f}s"))
            else:
                logger.error(_fmt("!!", "Gen failed", val, "hybrid audio"))

        elif mode == "time_signal":
            middle = f"{val}時です"
            target_str = f"{val:02d}:00"
            logger.info(_fmt("TX", "Generate", target_str, "time_signal"))
            if _generate_hybrid(TIME_INTRO_WAV, middle, None):
                logger.info(_fmt("TX", "Sending", target_str, "time_signal"))
                send_usrp_wav_with_padding(TEMP_FINAL)
                elapsed = time.monotonic() - started_at
                logger.info(_fmt("TX", "TimeSignal", target_str, f"{elapsed:.1f}s"))

                if NIGHT_MODE_ENABLED and val == NIGHT_START_HOUR:
                    _send_night_mode_announcement()
            else:
                logger.error(_fmt("!!", "Gen failed", target_str, "time_signal"))

        elif mode == "half_hour_signal":
            middle = f"{val}時30分です"
            target_str = f"{val:02d}:30"
            logger.info(_fmt("TX", "Generate", target_str, "half_hour_signal"))
            if _generate_hybrid(TIME_INTRO_WAV, middle, None):
                logger.info(_fmt("TX", "Sending", target_str, "half_hour_signal"))
                send_usrp_wav_with_padding(TEMP_FINAL)
                elapsed = time.monotonic() - started_at
                logger.info(_fmt("TX", "HalfHour", target_str, f"{elapsed:.1f}s"))
            else:
                logger.error(_fmt("!!", "Gen failed", target_str, "half_hour_signal"))

        elif mode == "fixed_file":
            basename = os.path.basename(val)
            if os.path.exists(val):
                # 🔴 V1.68: 固定再生（001/002）にも同じ送出音量ゲインを適用する。
                # fixed_file は _generate_hybrid を通らないため、ここで個別に vol を
                # かけた一時ファイルを作って送出する。失敗時は素のファイルで送る
                # （音量調整に失敗しても無音化・送出停止は避ける）。
                play_path = val
                if TX_GAIN is not None and TX_GAIN != 1.0:
                    try:
                        subprocess.run(
                            ["sox", val, TEMP_FINAL, "vol", f"{TX_GAIN}"],
                            check=True,
                        )
                        play_path = TEMP_FINAL
                    except subprocess.CalledProcessError as e:
                        logger.error(_fmt("!!", "Gain failed", basename, f"rc={e.returncode}"))
                        play_path = val
                logger.info(_fmt("TX", "Sending", basename, "scheduled"))
                send_usrp_wav_with_padding(play_path)
                elapsed = time.monotonic() - started_at
                logger.info(_fmt("TX", "Scheduled", basename, f"{elapsed:.1f}s"))
            else:
                logger.error(_fmt("!!", "File missing", basename, val))

        else:
            logger.error(_fmt("!!", "Unknown mode", str(mode)))

    except Exception as e:
        logger.error(_fmt("!!", "Executor err", str(mode), str(e)))
    finally:
        for tmp in (TEMP_FINAL, TEMP_48K, TEMP_8K, TEMP_INTRO_PADDED):
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError as e:
                    logger.error(_fmt("!!", "Tmp rm err", os.path.basename(tmp), str(e)))
        with _reply_lock:
            is_talking = False


def _generate_hybrid(intro, middle_text, outro):
    try:
        p = subprocess.Popen(
            ["open_jtalk", "-x", DICT_PATH, "-m", VOICE_PATH, "-ow", TEMP_48K],
            stdin=subprocess.PIPE,
        )
        p.communicate(middle_text.encode("utf-8"))
        if p.returncode != 0:
            logger.error(_fmt("!!", "open_jtalk", "", f"rc={p.returncode}"))
            return False

        subprocess.run(
            ["sox", TEMP_48K, "-r", "8000", "-c", "1", "-b", "16", TEMP_8K],
            check=True,
        )

        subprocess.run(
            ["sox", intro, TEMP_INTRO_PADDED, "pad", "0", f"{GAP_AFTER_INTRO_SEC}"],
            check=True,
        )

        concat_cmd = ["sox", TEMP_INTRO_PADDED, TEMP_8K]
        if outro is not None:
            concat_cmd.append(outro)
        concat_cmd.append(TEMP_FINAL)
        # 🔴 V1.68: 送出音量ゲイン。1.0(等倍)以外のときだけ vol 効果を付与する。
        # 結合後の出力全体（intro + 合成音 + outro）に一律で効く。
        if TX_GAIN is not None and TX_GAIN != 1.0:
            concat_cmd += ["vol", f"{TX_GAIN}"]
        subprocess.run(concat_cmd, check=True)

        return True

    except subprocess.CalledProcessError as e:
        logger.error(_fmt("!!", "SoX failed", "", f"rc={e.returncode}"))
        return False
    except FileNotFoundError as e:
        logger.error(_fmt("!!", "File missing", "", str(e)))
        return False
    except Exception as e:
        logger.error(_fmt("!!", "Gen error", "", str(e)))
        return False


# ============================================================
# 設定値ダンプ
# ============================================================
def _log_startup_info():
    logger.info("=" * 70)
    logger.info(f"DVSwitch Bot V1.70 (daemon, V1.69 + watchdog-specific kerchunk max) starting up (PID: {_PID})")
    logger.info(f"  My callsign       : {MY_CALLSIGN}")
    logger.info(f"  Target            : {UDP_IP}:{UDP_PORT}")
    logger.info(f"  Log dir           : {LOG_DIR}")
    logger.info(f"  Bot dir           : {BOT_DIR}")
    logger.info(f"  Config            : {CONFIG_PATH}")
    logger.info(f"  RX duration       : min={RX_DURATION_MIN_SEC}s / max={RX_DURATION_MAX_SEC}s")
    logger.info(f"  Suppress duration : {SUPPRESS_DURATION_SEC}s")
    logger.info(f"  Gap after intro   : {GAP_AFTER_INTRO_SEC}s")
    # 🔴 V1.68: 送出音量ゲインの状態
    if TX_GAIN == 1.0:
        logger.info(f"  TX gain           : {TX_GAIN} (等倍 / 音量変更なし)")
    else:
        _g_dir = "減衰" if TX_GAIN < 1.0 else "増幅(クリップ注意)"
        logger.info(f"  TX gain           : {TX_GAIN} ({_g_dir} / vol 効果を全送出に付与)")
    logger.info(f"  Startup announce  : {STARTUP_ANNOUNCE_DELAY_SEC}s 後に「起動しました。」を送出")
    logger.info(f"  Announce freq     : {ANNOUNCE_FREQ} (at minutes {_get_trigger_minutes()})")
    _ts_desc = {0: "なし", 1: "毎正時 :00", 2: "毎正時 :00 + 毎30分 :30"}.get(TIME_SIGNAL_MODE, "?")
    logger.info(f"  Time signal mode  : {TIME_SIGNAL_MODE} ({_ts_desc}, lead {TIME_SIGNAL_LEAD_SEC}s)")
    # 🔴 V1.67: watchdog 擬似終端の状態を表示
    if WATCHDOG_PSEUDO_END_ENABLED:
        logger.info(f"  Watchdog rescue   : ON  (watchdog を擬似終端として拾う / "
                    f"loss <= {WATCHDOG_MAX_LOSS_PCT}% のみ救済)")
        logger.info(f"  Watchdog kerchunk : max={WATCHDOG_RX_MAX_SEC}s "
                    f"(watchdog 専用上限 / end は {RX_DURATION_MAX_SEC}s)")
    else:
        logger.info(f"  Watchdog rescue   : OFF (end of voice transmission のみで判定)")
    if NIGHT_MODE_ENABLED:
        resume_hour = (NIGHT_END_HOUR + 1) % 24
        ts_suppress_start = (NIGHT_START_HOUR + 1) % 24   # 時報の抑制開始
        msg_suppress_start = NIGHT_START_HOUR % 24        # 定時メッセージの抑制開始
        logger.info(f"  Night mode        : ON  (N1={NIGHT_START_HOUR:02d} N2={NIGHT_END_HOUR:02d} "
                    f"/ resume {resume_hour:02d}:00)")
        logger.info(f"    - time_signal   : suppress {ts_suppress_start:02d}-{NIGHT_END_HOUR:02d} "
                    f"(N1={NIGHT_START_HOUR:02d}:00 は送出)")
        logger.info(f"    - sched_message : suppress {msg_suppress_start:02d}-{NIGHT_END_HOUR:02d} "
                    f"(N1 時台から抑制)")
        if TIME_SIGNAL_MODE == 2:
            logger.info(f"    - half_hour     : suppress {msg_suppress_start:02d}:30-{NIGHT_END_HOUR:02d}:30 "
                        f"(定時メッセージと同じ窓 / N1:30 から抑制)")
    else:
        logger.info(f"  Night mode        : OFF (24時間送出)")
    logger.info("-" * 70)

    required_files = {
        "Fixed intro": FIXED_INTRO_WAV,
        "Fixed outro": FIXED_OUTRO_WAV,
        "Time intro ": TIME_INTRO_WAV,
    }
    for label, path in required_files.items():
        if os.path.exists(path):
            logger.info(f"  OK   {label} : {path}")
        else:
            logger.error(f"  MISS {label} : {path}  (NOT FOUND)")
    for msg in MSG_FILES:
        if os.path.exists(msg):
            logger.info(f"  OK   Message     : {msg}")
        else:
            logger.error(f"  MISS Message     : {msg}  (NOT FOUND)")

    logger.info("=" * 70)


# ============================================================
# ログファイル管理（ローテーション対応）
# ============================================================
def _find_latest_log():
    # 日付付きログ（MMDVM_Bridge-YYYY-MM-DD.log）を優先。
    # ファイル名の辞書順 = 日付の昇順なので max() で最新日付を選ぶ。
    # getctime（作成時刻）は、ローテーション後に旧ファイルが touch されると
    # 古いファイルが「最新」に化けるため使わない。
    #
    # 🔴 V1.63: 0バイトファイルをスキップする。
    # セットアップ残骸や、日付切り替わり直前に作られた空の日付付きログを
    # 「名前が最大だから」という理由で掴んでしまい、実際に書かれている
    # 前日ログを見失う事故を防ぐ（2026-06-06 実機で発生）。
    # 中身のあるログ（size>0）の中から名前最大を選ぶ。
    dated_logs = glob.glob(os.path.join(LOG_DIR, LOG_PATTERN))
    if dated_logs:
        non_empty = []
        for p in dated_logs:
            try:
                if os.path.getsize(p) > 0:
                    non_empty.append(p)
            except OSError:
                continue
        if non_empty:
            return max(non_empty, key=os.path.basename)
        # フォールバック: 候補が全て0バイト（中身のあるログが1つも無い）。
        # 起動直後などで正規の空ファイルしか無い状況。監視対象を見失わない
        # よう、従来どおり全日付付きログから名前最大を選んでおく
        # （最初の行が書かれた時点で size>0 となり、次回チェックで正しく選ばれる）。
        return max(dated_logs, key=os.path.basename)
    # 日付付きが無い場合のみ、日付なしの標準ログにフォールバック
    standard_log = os.path.join(LOG_DIR, "MMDVM_Bridge.log")
    if os.path.exists(standard_log):
        return standard_log
    return None


def _open_log_file(path):
    f = open(path, "r", encoding="utf-8", errors="ignore")
    f.seek(0, 2)
    ino = os.stat(path).st_ino
    return f, ino


# ============================================================
# メイン
# ============================================================
def monitor_and_reply():
    global should_exit, suppress_until

    # 🔴 対話設定の代わりに JSON を読み込む（不正なら exit(1)）
    _load_config()
    _log_startup_info()

    scheduler_thread = threading.Thread(target=_announcement_scheduler, daemon=True)
    scheduler_thread.start()

    start_pattern = re.compile(r"received network voice header from ([A-Z0-9/\-]+)")
    end_pattern = re.compile(r"received network end of voice transmission")
    ts_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
    # 🔴 V1.67: watchdog 行から「経過秒」と「packet loss(%)」を抽出する（V1.65 から移植）。
    #   例) "network watchdog has expired, 2.6 seconds, 40% packet loss, BER: 4.0%"
    wd_pattern = re.compile(
        r"network watchdog has expired, ([\d.]+) seconds, (\d+)% packet loss"
    )

    current_path = None
    while not current_path and not should_exit:
        current_path = _find_latest_log()
        if not current_path:
            logger.info(f"No log file found in {LOG_DIR}, waiting...")
            time.sleep(1)

    if should_exit:
        return

    logger.info(f"Monitoring log file: {current_path}")
    f, current_ino = _open_log_file(current_path)
    logger.info("Bot ready — monitoring DMR traffic")

    # 🔴 起動アナウンス（V1.62）: STARTUP_ANNOUNCE_DELAY_SEC 秒後に 1 回送出
    threading.Timer(STARTUP_ANNOUNCE_DELAY_SEC, _send_startup_announcement).start()
    logger.info(_fmt("..", "Startup ann", "", f"scheduled in {STARTUP_ANNOUNCE_DELAY_SEC}s"))

    last_cs = None
    last_start_dt = None
    last_rotation_check = time.monotonic()

    try:
        while not should_exit:
            line = f.readline()

            if not line:
                time.sleep(0.1)
                now_mono = time.monotonic()
                if now_mono - last_rotation_check >= ROTATION_CHECK_INTERVAL:
                    last_rotation_check = now_mono
                    latest_path = _find_latest_log()
                    if latest_path and latest_path != current_path:
                        try:
                            logger.info(f"Log rotation detected: {current_path} -> {latest_path}")
                            f.close()
                            current_path = latest_path
                            f, current_ino = _open_log_file(current_path)
                        except OSError as e:
                            logger.error(f"Log rotation switch failed: {e}")
                    elif latest_path == current_path:
                        try:
                            new_ino = os.stat(current_path).st_ino
                            if new_ino != current_ino:
                                logger.info(f"Log file replaced (inode changed): {current_path}")
                                f.close()
                                f, current_ino = _open_log_file(current_path)
                        except OSError as e:
                            logger.error(f"Inode check failed: {e}")
                continue

            m_s = start_pattern.search(line)
            if m_s:
                cs = m_s.group(1)
                if cs != MY_CALLSIGN:
                    m_t = ts_pattern.search(line)
                    if m_t:
                        last_cs = cs
                        last_start_dt = datetime.strptime(m_t.group(1), "%Y-%m-%d %H:%M:%S.%f")
                continue

            # ---- 正常終端（received network end of voice transmission）----
            if end_pattern.search(line) and last_cs is not None and last_start_dt is not None:
                m_t = ts_pattern.search(line)
                if m_t:
                    end_dt = datetime.strptime(m_t.group(1), "%Y-%m-%d %H:%M:%S.%f")
                    dur = (end_dt - last_start_dt).total_seconds()
                    _handle_rx_duration(last_cs, dur, source="eot")

                last_cs = None
                last_start_dt = None
                continue

            # ---- 🔴 V1.67: 擬似終端（network watchdog has expired）----（V1.65 から移植）
            # SFR 中継で終端パケットが落ち、end of voice transmission が記録され
            # なかった送信を救済する。voice header を受けた後の watchdog のみ対象。
            if WATCHDOG_PSEUDO_END_ENABLED:
                m_wd = wd_pattern.search(line)
                if m_wd and last_cs is not None and last_start_dt is not None:
                    wd_dur = float(m_wd.group(1))
                    wd_loss = int(m_wd.group(2))

                    if wd_loss > WATCHDOG_MAX_LOSS_PCT:
                        # ロスが大きすぎる＝壊れた受信。救済しない。
                        logger.info(
                            f"receive:watchdog ignored (high loss): "
                            f"{last_cs} ({wd_dur:.1f}s, {wd_loss}% loss "
                            f"> {WATCHDOG_MAX_LOSS_PCT}%)")
                    else:
                        # ロスが許容範囲。擬似終端として通常の判定に流す。
                        # 注: wd_dur は MMDVM の watchdog タイムアウト(約2s)を
                        #     含むため、真のキーダウン時間より長めに出る。
                        logger.info(
                            f"receive:watchdog pseudo-end: "
                            f"{last_cs} ({wd_dur:.1f}s, {wd_loss}% loss)")
                        _handle_rx_duration(last_cs, wd_dur, source="watchdog")

                    last_cs = None
                    last_start_dt = None
                    continue

    except Exception as e:
        logger.error(f"monitor_and_reply error: {e}")
    finally:
        if f:
            f.close()
        logger.info("Monitor stopped")
        scheduler_thread.join(timeout=15)
        logger.info("Bot stopped — goodbye 73")


if __name__ == "__main__":
    monitor_and_reply()
