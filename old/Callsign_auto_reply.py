#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 OpenCCVoice for DVSwitch V1.0
 — JJ2YYK デジピーター自動応答システム —

 DMR ログを監視し、コールサインを読み上げて自動応答するシステム

 【動作概要】
   1. MMDVM_Bridge のログをリアルタイム監視
   2. "received network voice header from XXXXX" を検知 → コールサインを記憶
   3. "received network end of voice transmission" を検知 → 受信終了
   4. RESPONSE_DELAY 秒待機（交信の衝突回避）
   5. Open JTalk で応答メッセージを音声合成
   6. SoX で 8000Hz / モノラル / 16bit に変換
   7. USRP プロトコル（UDP 51000）で Analog_Bridge に送信

 【⭐ 核心技術】
   UDP パケット送信は「絶対時刻同期方式（ドリフト補正）」を採用。
   単純な time.sleep(0.02) では処理時間（1～2ms）が蓄積し、音切れが発生する。
   本実装では送信開始時刻からの経過時間を毎回逆算することで、
   20ms 間隔を厳密に維持している。
   詳細は完全マニュアル V2.1 の「教訓 8」を参照。

 【依存パッケージ】
   - open-jtalk
   - open-jtalk-mecab-naist-jdic
   - sox
   - メイの音声モデル（/usr/share/hts-voice/mei/mei_normal.htsvoice）

 【使い方】
   python3 callsign_auto_reply.py

 Document Version: V1.0
 Last Updated: May 2026
================================================================================
"""

import os
import time
import glob
import re
import socket
import struct
import wave
import subprocess

# ==============================================================================
# システム設定（環境に合わせて変更）
# ==============================================================================
LOG_DIR = "/var/log/mmdvm"           # MMDVM のログディレクトリ
LOG_PATTERN = "MMDVM_Bridge-*.log"   # 監視対象のログファイル名
UDP_IP = "127.0.0.1"                 # Analog_Bridge の IP
UDP_PORT = 51000                     # Analog_Bridge の rxPort

# Open JTalk のパス設定
DICT_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"
TEMP_WAV_48K = "/tmp/reply_48k.wav"
TEMP_WAV_8K = "/tmp/reply_8k.wav"

# 自局コールサイン(無限ループ防止のため、自分の応答は無視する)
MY_CALLSIGN = "JJ2YYK"

# 応答待機時間(秒) — 交信の衝突回避のため
RESPONSE_DELAY = 15.0

# パケット送信間隔(秒) — DMR は 20ms = 50pps が規格
PACKET_INTERVAL = 0.02

# 📖 読み替え辞書(コールサインを正しく英語読みさせるための設定)
USER_DICT = {
    "JJ2YYK": "ジェイ、ジェイ、ツー、ワイ、ワイ、ケー",
    "JI2TAB": "ジェイ、アイ、ツー、ティー、エー、ビー",
    "JR2DHR": "ジェイ、アール、ツー、ディー、エイチ、アール",
    # ↓ 新しいコールサインはここに追加
}


def get_latest_log():
    """最新のログファイルを見つけて返す"""
    files = glob.glob(os.path.join(LOG_DIR, LOG_PATTERN))
    if not files:
        standard_log = os.path.join(LOG_DIR, "MMDVM_Bridge.log")
        return standard_log if os.path.exists(standard_log) else None
    return max(files, key=os.path.getctime)


def talk(raw_text):
    """テキストを音声に変換し、USRP プロトコルで DVSwitch に送信する

    ⭐ 重要: パケット送信は「絶対時刻同期方式」を採用しています。
    単純な time.sleep(0.02) では処理時間によるドリフトが蓄積し、
    Analog_Bridge のバッファが空になって音切れ(プツプツ・ケロケロ)が発生します。
    本実装では送信開始時刻からの経過時間を毎回逆算することで、
    20ms 間隔を厳密に維持しています。
    """
    text = raw_text
    # 辞書の適用(コールサインをカナ読みに置換)
    for key, value in USER_DICT.items():
        text = text.replace(key, value)

    print(f"🎙️  発話準備: {text}")

    # 1. Open JTalk で音声生成(communicate 方式で標準入力から確実に渡す)
    cmd_jtalk = [
        "open_jtalk",
        "-x", DICT_PATH,
        "-m", VOICE_PATH,
        "-p", "1.1",     # ピッチ(声の高さ)
        "-r", "1.0",     # スピード
        "-ow", TEMP_WAV_48K,
    ]
    process = subprocess.Popen(cmd_jtalk, stdin=subprocess.PIPE)
    process.communicate(text.encode("utf-8"))

    # 2. SoX で 8000Hz モノラル 16bit に変換(DMR の規格に合わせる)
    subprocess.run([
        "sox", TEMP_WAV_48K,
        "-r", "8000", "-c", "1", "-b", "16",
        TEMP_WAV_8K,
    ])

    # 3. UDP ソケット通信で送信(⭐ 絶対時刻同期方式)
    if not os.path.exists(TEMP_WAV_8K):
        print("❌ 音声ファイルの生成に失敗しました")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    wf = wave.open(TEMP_WAV_8K, "rb")
    seq = 0

    # ⭐ 送信開始の「絶対時刻」を記録(これが同期の基準点)
    start_time = time.time()

    try:
        while True:
            data = wf.readframes(160)  # 20ms 分のサンプル数(8000Hz × 0.02s)
            if len(data) == 0:
                break
            if len(data) < 320:
                data += b"\x00" * (320 - len(data))  # パディング(16bit × 160 = 320 bytes)

            # USRP ヘッダー(PTT ON: 1)を付与して送信
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + data, (UDP_IP, UDP_PORT))
            seq += 1

            # ⭐ ドリフト補正:次のパケットを送るべき絶対時刻を計算
            # 「開始から seq * 20ms 経過した時刻」が次の目標時刻
            target_time = start_time + (seq * PACKET_INTERVAL)
            sleep_duration = target_time - time.time()

            # 処理が早ければ待つ、遅れていれば待たない(追いつく)
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            # else: すでに遅延している → 即座に次のパケットへ(追いつき動作)
    finally:
        # USRP ヘッダー(PTT OFF: 0)を送信して通信終了
        header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 0, 0, 0, 0, 0)
        sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
        wf.close()
        sock.close()

        # 使用した一時ファイルの削除
        if os.path.exists(TEMP_WAV_48K):
            os.remove(TEMP_WAV_48K)
        if os.path.exists(TEMP_WAV_8K):
            os.remove(TEMP_WAV_8K)
    print(f"✅ 送信完了({seq} パケット, {seq * PACKET_INTERVAL:.2f}秒)")


def monitor_and_reply():
    """ログを監視し、通話終了を検知して応答アクションを起こす"""
    current_file = get_latest_log()
    if not current_file:
        print("❌ ログが見つかりません")
        return

    print(f"👀 OpenCCVoice for DVSwitch V1.0 待機中: {current_file}")
    print(f"📡 自局: {MY_CALLSIGN} | 応答待機時間: {RESPONSE_DELAY}秒")

    # 監視するログの文字列パターン
    start_pattern = re.compile(r"received network voice header from ([A-Z0-9\-]+)")
    end_pattern = re.compile(r"received network end of voice transmission")

    last_detected_callsign = None

    try:
        with open(current_file, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)  # ファイルの末尾に移動(過去のログは無視)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                # ① 受信開始の検知(コールサインを記憶)
                start_match = start_pattern.search(line)
                if start_match:
                    callsign = start_match.group(1)
                    # 自局の応答は無視(無限ループ防止)
                    if callsign == MY_CALLSIGN:
                        print(f"⏭️  自局の送信を無視: {callsign}")
                        continue
                    last_detected_callsign = callsign
                    print(f"▶️  受信中: {last_detected_callsign}")

                # ② 受信終了の検知
                if end_pattern.search(line):
                    if last_detected_callsign:
                        print(f"⏹️  受信終了 -> {RESPONSE_DELAY}秒後に "
                              f"{last_detected_callsign} へ返信します")

                        # 交信の衝突を避けるための待機
                        time.sleep(RESPONSE_DELAY)

                        # 応答メッセージの生成と送信
                        msg = (f"{last_detected_callsign}。こちらは、{MY_CALLSIGN}、"
                               f"尾張旭、DMR、デジピーターです。")
                        talk(msg)

                        # 応答が完了したら記憶をリセット
                        last_detected_callsign = None

    except KeyboardInterrupt:
        print("\n🛑 システムを終了します")


if __name__ == "__main__":
    monitor_and_reply()
