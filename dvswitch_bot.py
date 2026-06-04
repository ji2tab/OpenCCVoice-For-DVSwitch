#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 DVSwitch ログ監視・自動音声応答システム（デーモン版 / config-driven）
 — JJ2YYK デジピーター自動応答システム  V1.61 —

 本ファイルは V1.60 をベースにデーモン化し、V1.61 でナイトモードの
 抑制ロジックを改良したもの。

【V1.61 での変更点】
  - 🔴 ナイトモードの抑制を「時報」と「定時メッセージ」で分離した。
      * 時報         : N1+1 時 〜 N2 時を抑制（N1 時の時報は送出）
      * 定時メッセージ : N1 時 〜 N2 時を抑制（N1 時台から即抑制）
    意図: N1 時は「最後の時報＋ナイトモード突入アナウンス」を出すが、
    その後の同じ時間帯の定時メッセージ（例 N1=22 のとき 22:20）は出さない。
    V1.60 では定時メッセージも N1+1 時からの抑制だったため、22:20 等が
    送出されてしまっていた。これを修正。
  - 起動ログに時報／定時それぞれの抑制時間帯を表示するようにした。

【V1.60 からの変更点（デーモン化）】
  - 起動時の対話設定（_interactive_setup）を廃止し、
    設定ファイル(JSON)を読み込む _load_config() に置き換えた。
    → systemd 等の非対話環境でも EOFError で落ちない。
  - 🔴 フェイルセーフ:
    設定ファイルが「無い / 壊れている / 必須キー欠落 / 値が不正」の場合、
    デフォルト値で誤動作させず、エラーログを出して sys.exit(1) で停止する。
    （意図しない送信パラメータで電波を出すことを防ぐ安全策）
    → 設定は必ず bot_setup.py で作成してから本デーモンを起動すること。
  - 設定の置き場所: /opt/dvswitch_bot/bot_config.json

【設定項目（bot_config.json）】
  RX_DURATION_MIN_SEC : 最小受信時間（秒, 0 < MIN < MAX）
  RX_DURATION_MAX_SEC : 最大受信時間（秒, カーチャンク上限）
  ANNOUNCE_FREQ       : 1時間あたりの放送回数（1 / 2 / 3）
  NIGHT_MODE_ENABLED  : ナイトモード有効（true / false）
  NIGHT_START_HOUR    : ナイトモード開始 N1（0〜23）
  NIGHT_END_HOUR      : ナイトモード終了 N2（0〜23）

【機能】
  - ナイトモード（時報は N1+1時〜N2時を抑制／定時メッセージは N1時〜N2時を抑制。
    N1時は時報＋突入アナウンスを出す。kerchunk は24時間応答）
  - 毎正時の時報（lead 秒前に発火）/ 定時メッセージ（001/002 交互）
  - カーチャンク検知応答 / 重複応答防止 / イントロ・アウトロ結合
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

 Document Version: V1.61 (daemon, based on V1.60)
 Last Updated: 2026-06-04
================================================================================
"""

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
    global RX_DURATION_MIN_SEC, RX_DURATION_MAX_SEC, ANNOUNCE_FREQ
    global NIGHT_MODE_ENABLED, NIGHT_START_HOUR, NIGHT_END_HOUR

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
    if freq not in (1, 2, 3):
        _fatal_config(f"ANNOUNCE_FREQ は 1 / 2 / 3 のいずれかです（現在: {freq}）")
    if not (0 <= n1 <= 23):
        _fatal_config(f"NIGHT_START_HOUR は 0〜23 です（現在: {n1}）")
    if not (0 <= n2 <= 23):
        _fatal_config(f"NIGHT_END_HOUR は 0〜23 です（現在: {n2}）")

    # 5) 反映
    RX_DURATION_MIN_SEC = rx_min
    RX_DURATION_MAX_SEC = rx_max
    ANNOUNCE_FREQ = freq
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
    if ANNOUNCE_FREQ == 1:
        return [30]
    elif ANNOUNCE_FREQ == 2:
        return [20, 40]
    elif ANNOUNCE_FREQ == 3:
        return [15, 30, 45]
    return []


def _announcement_scheduler():
    fired_time_signal_for = None
    fired_message_minute = None
    msg_index = 0

    logger.info(_fmt("..", "Scheduler", "started"))

    while not should_exit:
        now = datetime.now()

        next_hour_dt = (now.replace(minute=0, second=0, microsecond=0)
                        + timedelta(hours=1))
        seconds_until_next_hour = (next_hour_dt - now).total_seconds()

        if 0 < seconds_until_next_hour <= TIME_SIGNAL_LEAD_SEC:
            target_hour = next_hour_dt.hour
            if fired_time_signal_for != target_hour:
                fired_time_signal_for = target_hour
                if _is_night_suppressed(target_hour):
                    logger.info(_fmt("..", "NightSkip", f"{target_hour:02d}:00",
                                     "time_signal suppressed (night mode)"))
                else:
                    logger.info(_fmt("..", "Trigger", f"{target_hour:02d}:00",
                                     f"time_signal (lead {TIME_SIGNAL_LEAD_SEC}s)"))
                    _start_worker("time_signal", target_hour)

        m = now.minute
        if m != 0 and m in _get_trigger_minutes():
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

        elif mode == "fixed_file":
            basename = os.path.basename(val)
            if os.path.exists(val):
                logger.info(_fmt("TX", "Sending", basename, "scheduled"))
                send_usrp_wav_with_padding(val)
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
    logger.info(f"DVSwitch Bot V1.61 (daemon, based on V1.60) starting up (PID: {_PID})")
    logger.info(f"  My callsign       : {MY_CALLSIGN}")
    logger.info(f"  Target            : {UDP_IP}:{UDP_PORT}")
    logger.info(f"  Log dir           : {LOG_DIR}")
    logger.info(f"  Bot dir           : {BOT_DIR}")
    logger.info(f"  Config            : {CONFIG_PATH}")
    logger.info(f"  RX duration       : min={RX_DURATION_MIN_SEC}s / max={RX_DURATION_MAX_SEC}s")
    logger.info(f"  Suppress duration : {SUPPRESS_DURATION_SEC}s")
    logger.info(f"  Gap after intro   : {GAP_AFTER_INTRO_SEC}s")
    logger.info(f"  Announce freq     : {ANNOUNCE_FREQ}/h (at minutes {_get_trigger_minutes()})")
    logger.info(f"  Time signal       : every hour at :00 (lead {TIME_SIGNAL_LEAD_SEC}s)")
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
    logs = glob.glob(os.path.join(LOG_DIR, LOG_PATTERN))
    standard_log = os.path.join(LOG_DIR, "MMDVM_Bridge.log")
    if os.path.exists(standard_log):
        logs.append(standard_log)
    if not logs:
        return None
    return max(logs, key=os.path.getctime)


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

            if end_pattern.search(line) and last_cs is not None and last_start_dt is not None:
                m_t = ts_pattern.search(line)
                if m_t:
                    end_dt = datetime.strptime(m_t.group(1), "%Y-%m-%d %H:%M:%S.%f")
                    dur = (end_dt - last_start_dt).total_seconds()
                    now = time.monotonic()

                    if RX_DURATION_MIN_SEC <= dur < RX_DURATION_MAX_SEC:
                        if suppress_until - now <= 0:
                            logger.info(f"receive:Kerchunk detected: {last_cs} ({dur:.1f}s) trigger")
                            _start_worker("kerchunk", last_cs, extra=dur)
                        else:
                            remain = suppress_until - now
                            logger.info(f"receive:suppressed: {last_cs} ({dur:.1f}s, remaining {remain:.1f}s)")
                    elif dur >= RX_DURATION_MAX_SEC:
                        suppress_until = now + SUPPRESS_DURATION_SEC
                        logger.info(f"receive:Normal QSO detected: {last_cs} ({dur:.1f}s)")
                        logger.info(f"process:suppress start ({SUPPRESS_DURATION_SEC:.1f}s)　{last_cs}")
                    else:
                        logger.info(f"receive:Too short, ignored: {last_cs} ({dur:.1f}s, min={RX_DURATION_MIN_SEC}s)")

                last_cs = None
                last_start_dt = None

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
