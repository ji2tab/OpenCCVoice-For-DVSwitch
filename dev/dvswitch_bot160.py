#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 DVSwitch ログ監視・自動音声応答システム V1.60
 — JJ2YYK デジピーター自動応答システム —

【V1.60 での修正点(V1.58 からの改良)】
  - ナイトモード機能を追加
    指定された時間帯(N1+1時 〜 N2時)は時報・定時メッセージを抑制する
    デフォルト: ナイトモード有効 / N1=22時 / N2=5時
    例) N1=22, N2=5 のとき:
        22時の時報まで送出 → 23時〜翌5時は抑制 → 6時の時報から再開
  - N1時の時報直後にナイトモード開始アナウンスを送出
    「ただいまより、このデジピーターは、明朝{N2+1}時まで、ナイトモードに入ります。」
    イントロは fixed_intro.wav を流用
  - 起動時の対話設定にナイトモードの確認を追加(有効/無効、N1、N2)
  - スケジューラに _is_night_suppressed() 判定を追加
  - 時報抑制時は [..] NightSkip ログを出力
  - カーチャンク応答(kerchunk)はナイトモード対象外 → 24時間応答する
  - 起動時ログにナイトモード設定を表示

【V1.58 での修正点(V1.57 からの改良)】
  - 時報のアウトロ WAV を廃止し、動的合成に「です」まで含めるよう変更
    例: 旧 [time_intro.wav]+「21時」+[time_outro.wav]
        新 [time_intro.wav]+「21時です」
    → 「時」と「です」の境界が滑らかになり、抑揚が自然に
  - _generate_hybrid() を outro 引数 None で呼び出し可能に拡張
  - 必須ファイル確認から time_outro.wav を除外
    (TIME_OUTRO_WAV 定数自体は将来の再利用のため残置)

【V1.57 での修正点(V1.56 からの改良)】
  - 課題1修正: _last_cs を関数スコープで明示初期化(locals() 廃止)
  - 課題2修正: イントロ/アウトロ WAV パスを定数化(BOT_DIR 配下)
  - 課題3修正: _generate_hybrid() の例外を logger.error() で記録
  - 課題4修正: ログローテーション処理を実装(日付変わりで自動切替)
  - ログ強化: 起動時環境情報・カーチャンク検知・抑制状態・終了処理など各イベントを記録

【V1.56 からの継承機能(維持)】
  - 対話設定で最小/最大受信時間と放送回数を起動時に変更可能
  - 毎正時(00分)は「時報のみ」固定
  - 定時メッセージ(001/002)を正時を避けて交互ローテーション
  - カーチャンク検知(短時間 PTT のみ応答)
  - 重複応答防止(SUPPRESS_DURATION_SEC)
  - イントロ/アウトロの固定 WAV 結合
  - logging モジュールで構造化ログ
  - シグナルハンドラ(Graceful shutdown)
  - マルチスレッド処理(応答中も監視継続)
  - 共有メモリ(/dev/shm)で SD カード保護
  - PRE/POST パディング(前後 1.5 秒の無音)
  - time.monotonic() で時刻巻き戻り耐性

【⭐ 核心技術】
  UDP パケット送信は「絶対時刻同期方式(ドリフト補正)」を採用。
  time.monotonic() ベースで next_send_time を毎回 20ms ずつ進めることで、
  処理時間のブレを吸収し、Analog_Bridge への安定したパケット供給を実現する。
  詳細は完全マニュアル V2.x の「教訓 8」/「魔法 1」を参照。

【依存パッケージ】
  - open-jtalk / open-jtalk-mecab-naist-jdic / sox
  - メイの音声モデル(/usr/share/hts-voice/mei/mei_normal.htsvoice)

【固定 WAV(事前作成が必要)】
  - /opt/dvswitch_bot/fixed_intro.wav   カーチャンク応答のイントロ
  - /opt/dvswitch_bot/fixed_outro.wav   カーチャンク応答のアウトロ
  - /opt/dvswitch_bot/time_intro.wav    時報のイントロ
  - /opt/dvswitch_bot/001.wav           定時メッセージ1
  - /opt/dvswitch_bot/002.wav           定時メッセージ2
  ※ time_outro.wav は V1.58 で不要になりました(動的合成に統合)

【使い方】
  python3 dvswitch_bot160.py

 Document Version: V1.60
 Last Updated: May 2026
================================================================================
"""

import os
import sys
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

# 固定 WAV ファイルのパス(⭐ 課題2修正:すべて定数化)
BOT_DIR = "/opt/dvswitch_bot"
FIXED_INTRO_WAV = f"{BOT_DIR}/fixed_intro.wav"   # カーチャンク応答のイントロ
FIXED_OUTRO_WAV = f"{BOT_DIR}/fixed_outro.wav"   # カーチャンク応答のアウトロ
TIME_INTRO_WAV  = f"{BOT_DIR}/time_intro.wav"    # 時報のイントロ
TIME_OUTRO_WAV  = f"{BOT_DIR}/time_outro.wav"    # 時報のアウトロ(V1.58 で未使用、将来再利用のため定数は残置)
MSG_FILES = [f"{BOT_DIR}/001.wav", f"{BOT_DIR}/002.wav"]

# 一時ファイル(/dev/shm = RAM ディスクで SD カード保護)
_PID = os.getpid()
TEMP_FINAL = f"/dev/shm/reply_final_{_PID}.wav"
TEMP_48K   = f"/dev/shm/tmp_48k_{_PID}.wav"
TEMP_8K    = f"/dev/shm/tmp_8k_{_PID}.wav"
TEMP_INTRO_PADDED = f"/dev/shm/tmp_intro_padded_{_PID}.wav"  # イントロ + 末尾無音

# タイミング関連
EMPTY_HEADER_THRESHOLD_SEC = 0.1
SUPPRESS_DURATION_SEC = 15.0   # 応答後の抑制時間
PACKET_INTERVAL = 0.02         # 20ms = 1 パケット(DMR 規格)
PRE_POST_PADDING_PACKETS = 75  # 前後の無音パディング(75 x 20ms = 1.5秒)
ROTATION_CHECK_INTERVAL = 5.0  # ログローテーション確認間隔(秒)
GAP_AFTER_INTRO_SEC = 0.5      # イントロとコールサインの間に挿入する無音(秒)

# ============================================================
# グローバル状態 / 設定値
# ============================================================
should_exit = False
suppress_until = 0.0
is_talking = False
_reply_lock = threading.Lock()

# 初期設定値(対話形式で上書き)
RX_DURATION_MIN_SEC = 0.5
RX_DURATION_MAX_SEC = 3.9
ANNOUNCE_FREQ = 2

# ⭐ V1.60: ナイトモード設定(対話形式で上書き)
NIGHT_MODE_ENABLED = True   # デフォルト: 有効
NIGHT_START_HOUR = 22       # N1: この時刻の時報まで送出してナイトモードへ
NIGHT_END_HOUR = 5          # N2: この時刻台は送出なし、N2+1時の時報から再開

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
# ロガー(整形済みフォーマット:タグ + アクション + ターゲット + 付加情報)
# ============================================================
logger = logging.getLogger("dvswitch_bot")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
# [INFO] を外し、時刻のみのシンプルなフォーマットに
_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
logger.addHandler(_handler)


def _fmt(tag, action, target="", extra=""):
    """ログ行を整形する

    フォーマット: [TAG]  ACTION(12字幅)  TARGET(10字幅)  EXTRA(自由)
    タグ種別:
      [RX]  受信検知系(Kerchunk / Normal QSO / Too short / Suppressed)
      [TX]  送信系  (Generate / Sending / Complete / TimeSignal / Scheduled)
      [--]  状態変化 (Suppress 開始など)
      [..]  ライフサイクル(Bot ready / Bot stopped など)
      [!!]  エラー
    """
    # アクション 12 文字幅左寄せ
    action_str = f"{action:<12}"
    if extra:
        # extra がある場合のみ target を 10 字幅に揃える(列を縦に整列)
        target_str = f"{target:<10}" if target else " " * 10
        return f"[{tag}]  {action_str} {target_str}  {extra}".rstrip()
    else:
        # extra が無い場合は行末空白を残さない
        return f"[{tag}]  {action_str} {target}".rstrip()


def _handle_signal(signum, frame):
    """SIGTERM / SIGINT を受けて Graceful shutdown を開始"""
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

        # ⭐ 絶対時刻同期方式(time.monotonic ベース)
        next_send_time = time.monotonic()

        # PRE パディング(1.5秒の無音)
        for _ in range(PRE_POST_PADDING_PACKETS):
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

        # 音声本体
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

        # POST パディング(1.5秒の無音)
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
            # PTT OFF 信号を送信
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 0, 0, 0, 0, 0)
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            sock.close()
        if wf:
            wf.close()


# ============================================================
# ⭐ V1.60: ナイトモード判定
# ============================================================
def _is_night_suppressed(hour):
    """この時刻がナイトモード抑制範囲かどうかを返す

    ルール:
      - ナイトモード OFF なら常に False
      - N1時の時報は送出する(N1時は抑制しない)
      - N1+1時 〜 N2時は抑制
      - N2+1時以降は送出再開
      例) N1=22, N2=5 の場合:
          22時 → 送出
          23時〜翌5時 → 抑制
          6時 → 再開
    """
    if not NIGHT_MODE_ENABLED:
        return False

    # 抑制範囲: N1+1 〜 N2(両端含む)
    suppress_start = (NIGHT_START_HOUR + 1) % 24
    suppress_end   = NIGHT_END_HOUR

    if suppress_start <= suppress_end:
        # 日をまたがない場合(例: 2時〜5時 → 2,3,4,5時を抑制)
        return suppress_start <= hour <= suppress_end
    else:
        # 日をまたぐ場合(例: 23時〜5時 → 23,0,1,2,3,4,5時を抑制)
        return hour >= suppress_start or hour <= suppress_end


# ============================================================
# スケジューラー(時報と放送の分離)
# ============================================================
TIME_SIGNAL_LEAD_SEC = 7  # 時報は正時の N 秒前に発火させて、ジャストに音声が始まるように調整


def _get_trigger_minutes():
    """放送回数に応じた発火分のリストを返す"""
    if ANNOUNCE_FREQ == 1:
        return [30]
    elif ANNOUNCE_FREQ == 2:
        return [20, 40]
    elif ANNOUNCE_FREQ == 3:
        return [15, 30, 45]
    return []


def _announcement_scheduler():
    """毎正時の時報と、定時メッセージのスケジューリング

    時報は「正時 HH:00:00 ぴったりに受信側で音声が始まる」ようにしたいので、
    実際の発火タイミングは HH-1:59:(60-LEAD) 秒に前倒しする。
    LEAD = TIME_SIGNAL_LEAD_SEC(デフォルト 7 秒)

    ⭐ V1.60: ナイトモード対応
      - 抑制範囲の時刻は時報・定時メッセージともに発火させない
      - カーチャンク応答はこのスケジューラを通らないため影響なし
    """
    fired_time_signal_for = None    # 直近に発火した時報の「正時の hour」
    fired_message_minute = None     # 直近に発火した定時メッセージの分
    msg_index = 0                   # 001 と 002 のローテーション用

    logger.info(_fmt("..", "Scheduler", "started"))

    while not should_exit:
        now = datetime.now()

        # === 時報の発火判定(LEAD 秒前) ===
        # 例:LEAD=7 のとき、HH-1:59:53 〜 HH-1:59:59 の間に発火
        # 「次の正時」の hour を計算
        next_hour_dt = (now.replace(minute=0, second=0, microsecond=0)
                        + timedelta(hours=1))
        seconds_until_next_hour = (next_hour_dt - now).total_seconds()

        # LEAD 秒以内になったら発火(同じ正時で二度発火しないようガード)
        if 0 < seconds_until_next_hour <= TIME_SIGNAL_LEAD_SEC:
            target_hour = next_hour_dt.hour
            if fired_time_signal_for != target_hour:
                fired_time_signal_for = target_hour
                # ⭐ V1.60: ナイトモード判定
                if _is_night_suppressed(target_hour):
                    logger.info(_fmt("..", "NightSkip", f"{target_hour:02d}:00",
                                     "time_signal suppressed (night mode)"))
                else:
                    logger.info(_fmt("..", "Trigger", f"{target_hour:02d}:00",
                                     f"time_signal (lead {TIME_SIGNAL_LEAD_SEC}s)"))
                    _start_worker("time_signal", target_hour)

        # === 定時メッセージの発火判定(従来通り、その分のジャスト) ===
        m = now.minute
        if m != 0 and m in _get_trigger_minutes():
            # この分でまだ発火していなければ発火
            current_minute_key = (now.hour, m)
            if fired_message_minute != current_minute_key:
                fired_message_minute = current_minute_key
                # ⭐ V1.60: ナイトモード判定
                if _is_night_suppressed(now.hour):
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

        # 1 秒粒度でチェック(LEAD 秒前を捉えるため、10 秒は粗すぎる)
        time.sleep(1)

    logger.info(_fmt("..", "Scheduler", "stopped"))


def _start_worker(mode, val, extra=None):
    """応答処理を別スレッドで起動(重複起動防止付き)

    extra: モード別の追加情報(kerchunk なら検知された PTT 時間[秒])
    """
    global is_talking
    with _reply_lock:
        if is_talking:
            logger.info(_fmt("..", "Skipped", str(val), f"already talking ({mode})"))
            return
        is_talking = True
    threading.Thread(target=_reply_executor, args=(mode, val, extra), daemon=True).start()


# ============================================================
# ⭐ V1.60: ナイトモード開始アナウンス
# ============================================================
NIGHT_ANN_GAP_SEC = 1.0   # 時報送出完了後、アナウンスまでの待機時間


def _send_night_mode_announcement():
    """N1時の時報直後に流すナイトモード開始アナウンスを生成・送出

    文面: 「ただいまより、このデジピーターは、明朝{N2+1}時まで、ナイトモードに入ります。」

    流れ:
      時報送出完了 → NIGHT_ANN_GAP_SEC 待機 → イントロ + 動的合成を送出

    イントロは fixed_intro.wav(カーチャンク応答と共用)を流用する。
    PRE/POST パディング(各1.5秒)は send_usrp_wav_with_padding() が付与する。
    """
    started_at = time.monotonic()
    resume_hour = (NIGHT_END_HOUR + 1) % 24
    middle_text = f"ただいまより、このデジピーターは、明朝{resume_hour}時まで、ナイトモードに入ります。"
    label = f"N1={NIGHT_START_HOUR:02d}"

    # 時報直後の短い間を空ける
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
    """応答処理の本体(モード別に分岐)"""
    global is_talking, suppress_until
    started_at = time.monotonic()
    try:
        if mode == "kerchunk":
            cs_kana = "".join([CHAR_TO_KANA.get(ch, ch) for ch in val.upper()])
            middle = f"{cs_kana}局からの、"
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
            # ⭐ V1.58:アウトロ WAV を廃止し、「時です」まで動的合成に含める
            middle = f"{val}時です"
            target_str = f"{val:02d}:00"
            logger.info(_fmt("TX", "Generate", target_str, "time_signal"))
            if _generate_hybrid(TIME_INTRO_WAV, middle, None):
                logger.info(_fmt("TX", "Sending", target_str, "time_signal"))
                send_usrp_wav_with_padding(TEMP_FINAL)
                elapsed = time.monotonic() - started_at
                logger.info(_fmt("TX", "TimeSignal", target_str, f"{elapsed:.1f}s"))

                # ⭐ V1.60: N1時の時報直後にナイトモード開始アナウンス
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
        # 一時ファイルを掃除(残っていれば)
        for tmp in (TEMP_FINAL, TEMP_48K, TEMP_8K, TEMP_INTRO_PADDED):
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError as e:
                    logger.error(_fmt("!!", "Tmp rm err", os.path.basename(tmp), str(e)))
        with _reply_lock:
            is_talking = False


def _generate_hybrid(intro, middle_text, outro):
    """イントロ + 動的音声 (+ アウトロ) を結合した WAV を生成

    音声構成:
      [intro] + [GAP_AFTER_INTRO_SEC の無音] + [中間音声] (+ [outro])
                ↑ イントロとコールサインの間に明確な「間」を作る

    引数:
      intro      : 必須。イントロ WAV のパス
      middle_text: 必須。Open JTalk で動的合成する中間テキスト
      outro      : Optional。None を渡すとイントロ+中間のみで結合する
                   (V1.58:時報モードで「時です」まで合成に含めるため追加)

    ⭐ 課題3修正:例外を握りつぶさず logger.error() で記録する
    """
    try:
        # 1. Open JTalk で中間テキストを音声化(48kHz)
        p = subprocess.Popen(
            ["open_jtalk", "-x", DICT_PATH, "-m", VOICE_PATH, "-ow", TEMP_48K],
            stdin=subprocess.PIPE,
        )
        p.communicate(middle_text.encode("utf-8"))
        if p.returncode != 0:
            logger.error(_fmt("!!", "open_jtalk", "", f"rc={p.returncode}"))
            return False

        # 2. SoX で 8kHz/mono/16bit に変換
        subprocess.run(
            ["sox", TEMP_48K, "-r", "8000", "-c", "1", "-b", "16", TEMP_8K],
            check=True,
        )

        # 3. イントロの末尾に GAP_AFTER_INTRO_SEC の無音を追加
        #    (pad の引数:先頭無音秒数 末尾無音秒数)
        subprocess.run(
            ["sox", intro, TEMP_INTRO_PADDED, "pad", "0", f"{GAP_AFTER_INTRO_SEC}"],
            check=True,
        )

        # 4. SoX で「パディング済みイントロ + 中間 (+ アウトロ)」を結合
        #    ⭐ V1.58:outro が None の場合はイントロ+中間音声のみを結合
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
# 対話設定
# ============================================================
def _interactive_setup():
    """起動時に最小/最大受信時間と放送回数を対話で設定"""
    global RX_DURATION_MIN_SEC, RX_DURATION_MAX_SEC, ANNOUNCE_FREQ
    global NIGHT_MODE_ENABLED, NIGHT_START_HOUR, NIGHT_END_HOUR

    print("\n[DVSwitch Bot V1.60 Setup]")
    try:
        val = input(f"最小受信時間を入力 (秒) [現在: {RX_DURATION_MIN_SEC}]: ").strip()
        if val:
            RX_DURATION_MIN_SEC = float(val)

        val = input(f"最大受信時間(カーチャンク)を入力 (秒) [現在: {RX_DURATION_MAX_SEC}]: ").strip()
        if val:
            RX_DURATION_MAX_SEC = float(val)

        val = input(f"1時間あたりの放送回数を選択 (1, 2, 3) ※正時除く [現在: {ANNOUNCE_FREQ}]: ").strip()
        if val:
            ANNOUNCE_FREQ = int(val)
    except ValueError:
        print("入力エラー: デフォルト値を適用します。")

    # ⭐ V1.60: ナイトモード設定
    print("\n--- ナイトモード設定 ---")
    print("  ナイトモード中は時報・定時メッセージを抑制します")
    print("  (カーチャンク応答は24時間動作します)")
    try:
        default_yn = "y" if NIGHT_MODE_ENABLED else "n"
        val = input(f"ナイトモードを有効にしますか？ (y/n) [現在: {default_yn}]: ").strip().lower()
        if val in ("y", "n"):
            NIGHT_MODE_ENABLED = (val == "y")

        if NIGHT_MODE_ENABLED:
            val = input(f"ナイトモード開始時刻 N1 (0〜23) [現在: {NIGHT_START_HOUR}]: ").strip()
            if val:
                n1 = int(val)
                if 0 <= n1 <= 23:
                    NIGHT_START_HOUR = n1
                else:
                    print(f"  範囲外のためデフォルト値 {NIGHT_START_HOUR} を維持します")

            val = input(f"ナイトモード終了時刻 N2 (0〜23) [現在: {NIGHT_END_HOUR}]: ").strip()
            if val:
                n2 = int(val)
                if 0 <= n2 <= 23:
                    NIGHT_END_HOUR = n2
                else:
                    print(f"  範囲外のためデフォルト値 {NIGHT_END_HOUR} を維持します")
    except ValueError:
        print("入力エラー: ナイトモードはデフォルト値を適用します。")

    print(f"\n[INFO] 最小: {RX_DURATION_MIN_SEC}s / 最大: {RX_DURATION_MAX_SEC}s / 放送: {ANNOUNCE_FREQ}回(正時外)")
    if NIGHT_MODE_ENABLED:
        resume_hour = (NIGHT_END_HOUR + 1) % 24
        print(f"[INFO] ナイトモード: ON  ({NIGHT_START_HOUR}時の時報まで送出 → "
              f"{(NIGHT_START_HOUR + 1) % 24}〜{NIGHT_END_HOUR}時は抑制 → "
              f"{resume_hour}時の時報から再開)")
    else:
        print("[INFO] ナイトモード: OFF (24時間送出)")
    print("-" * 40)


# ============================================================
# 設定値ダンプ
# ============================================================
def _log_startup_info():
    """起動時の設定値・環境情報をログ出力"""
    logger.info("=" * 70)
    logger.info(f"DVSwitch Bot V1.60 starting up (PID: {_PID})")
    logger.info(f"  My callsign       : {MY_CALLSIGN}")
    logger.info(f"  Target            : {UDP_IP}:{UDP_PORT}")
    logger.info(f"  Log dir           : {LOG_DIR}")
    logger.info(f"  Bot dir           : {BOT_DIR}")
    logger.info(f"  RX duration       : min={RX_DURATION_MIN_SEC}s / max={RX_DURATION_MAX_SEC}s")
    logger.info(f"  Suppress duration : {SUPPRESS_DURATION_SEC}s")
    logger.info(f"  Gap after intro   : {GAP_AFTER_INTRO_SEC}s")
    logger.info(f"  Announce freq     : {ANNOUNCE_FREQ}/h (at minutes {_get_trigger_minutes()})")
    logger.info(f"  Time signal       : every hour at :00 (lead {TIME_SIGNAL_LEAD_SEC}s)")
    # ⭐ V1.60: ナイトモード状態をダンプ
    if NIGHT_MODE_ENABLED:
        resume_hour = (NIGHT_END_HOUR + 1) % 24
        suppress_start = (NIGHT_START_HOUR + 1) % 24
        logger.info(f"  Night mode        : ON  (N1={NIGHT_START_HOUR:02d} N2={NIGHT_END_HOUR:02d} "
                    f"/ suppress {suppress_start:02d}-{NIGHT_END_HOUR:02d} "
                    f"/ resume {resume_hour:02d}:00)")
    else:
        logger.info(f"  Night mode        : OFF (24時間送出)")
    logger.info("-" * 70)

    # 必須ファイルの存在確認(⭐ V1.58:time_outro は不要になったので確認対象外)
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
        basename = os.path.basename(msg)
        if os.path.exists(msg):
            logger.info(f"  OK   Message     : {msg}")
        else:
            logger.error(f"  MISS Message     : {msg}  (NOT FOUND)")

    logger.info("=" * 70)


# ============================================================
# ⭐ 課題4修正:ログファイル管理(ローテーション対応)
# ============================================================
def _find_latest_log():
    """最新の MMDVM_Bridge ログファイルパスを返す"""
    logs = glob.glob(os.path.join(LOG_DIR, LOG_PATTERN))
    standard_log = os.path.join(LOG_DIR, "MMDVM_Bridge.log")
    if os.path.exists(standard_log):
        logs.append(standard_log)
    if not logs:
        return None
    return max(logs, key=os.path.getctime)


def _open_log_file(path):
    """ログファイルを開き、末尾にシークして (file_obj, inode) を返す"""
    f = open(path, "r", encoding="utf-8", errors="ignore")
    f.seek(0, 2)  # ファイルの末尾に移動
    ino = os.stat(path).st_ino
    return f, ino


# ============================================================
# メイン
# ============================================================
def monitor_and_reply():
    """ログを監視し、通話終了を検知して応答アクションを起こす"""
    global should_exit, suppress_until

    # 対話設定とスケジューラ起動
    _interactive_setup()
    _log_startup_info()

    scheduler_thread = threading.Thread(target=_announcement_scheduler, daemon=True)
    scheduler_thread.start()

    # 正規表現パターン
    start_pattern = re.compile(r"received network voice header from ([A-Z0-9/\-]+)")
    end_pattern = re.compile(r"received network end of voice transmission")
    ts_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")

    # 最新のログファイルを探す
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

    # ⭐ 課題1修正:_last_cs と _last_start_dt を関数スコープで明示的に初期化
    last_cs = None
    last_start_dt = None

    # ⭐ 課題4修正:ログローテーション検出用の時刻
    last_rotation_check = time.monotonic()

    try:
        while not should_exit:
            line = f.readline()

            if not line:
                time.sleep(0.1)

                # ⭐ 課題4修正:ログローテーションのチェック
                now_mono = time.monotonic()
                if now_mono - last_rotation_check >= ROTATION_CHECK_INTERVAL:
                    last_rotation_check = now_mono
                    latest_path = _find_latest_log()

                    if latest_path and latest_path != current_path:
                        # 別のファイルが最新になった(日付変わりなど)
                        try:
                            logger.info(f"Log rotation detected: {current_path} -> {latest_path}")
                            f.close()
                            current_path = latest_path
                            f, current_ino = _open_log_file(current_path)
                        except OSError as e:
                            logger.error(f"Log rotation switch failed: {e}")
                    elif latest_path == current_path:
                        # 同名でも inode が変わった(置換された)場合に対応
                        try:
                            new_ino = os.stat(current_path).st_ino
                            if new_ino != current_ino:
                                logger.info(f"Log file replaced (inode changed): {current_path}")
                                f.close()
                                f, current_ino = _open_log_file(current_path)
                        except OSError as e:
                            logger.error(f"Inode check failed: {e}")

                continue

            # 受信開始の検知
            m_s = start_pattern.search(line)
            if m_s:
                cs = m_s.group(1)
                if cs != MY_CALLSIGN:
                    m_t = ts_pattern.search(line)
                    if m_t:
                        last_cs = cs
                        last_start_dt = datetime.strptime(m_t.group(1), "%Y-%m-%d %H:%M:%S.%f")
                continue

            # 受信終了の検知
            if end_pattern.search(line) and last_cs is not None and last_start_dt is not None:
                m_t = ts_pattern.search(line)
                if m_t:
                    end_dt = datetime.strptime(m_t.group(1), "%Y-%m-%d %H:%M:%S.%f")
                    dur = (end_dt - last_start_dt).total_seconds()
                    now = time.monotonic()

                    # カーチャンク判定(最小〜最大の範囲内なら応答)
                    # ⭐ V1.60: カーチャンク応答はナイトモード対象外 → 24時間動作
                    if RX_DURATION_MIN_SEC <= dur < RX_DURATION_MAX_SEC:
                        if suppress_until - now <= 0:
                            logger.info(f"receive:Kerchunk detected: {last_cs} ({dur:.1f}s) trigger")
                            _start_worker("kerchunk", last_cs, extra=dur)
                        else:
                            remain = suppress_until - now
                            logger.info(f"receive:suppressed: {last_cs} ({dur:.1f}s, remaining {remain:.1f}s)")
                    elif dur >= RX_DURATION_MAX_SEC:
                        # 通常交信は応答せず、抑制時間だけ設定
                        suppress_until = now + SUPPRESS_DURATION_SEC
                        logger.info(f"receive:Normal QSO detected: {last_cs} ({dur:.1f}s)")
                        logger.info(f"process:suppress start ({SUPPRESS_DURATION_SEC:.1f}s)　{last_cs}")
                    else:
                        logger.info(f"receive:Too short, ignored: {last_cs} ({dur:.1f}s, min={RX_DURATION_MIN_SEC}s)")

                # 状態リセット
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
