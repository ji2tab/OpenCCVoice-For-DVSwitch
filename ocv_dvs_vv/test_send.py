#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 USRP テスト送信ツール
 — 指定した WAV ファイルを Analog_Bridge へ単発送信する —

【配置】
  /opt/dvswitch_bot/bin/test_send.py

【使い方】
  python3 /opt/dvswitch_bot/bin/test_send.py /opt/dvswitch_bot/002.wav
  python3 /opt/dvswitch_bot/bin/test_send.py /opt/dvswitch_bot/001.wav

【注意】
  bot 本体が動いている場合は、同じ UDP ポートに二重送信になるので、
  bot を一旦止めてから実行してください。
    sudo systemctl stop dvswitch-bot     # systemd の場合（サービス名はハイフン）
    または bot を起動しているターミナルで Ctrl+C
================================================================================
"""

import os
import sys
import time
import socket
import struct
import wave

UDP_IP = "127.0.0.1"
UDP_PORT = 51000
PACKET_INTERVAL = 0.02          # 20ms
PRE_POST_PADDING_PACKETS = 75   # 前後 1.5 秒の無音


def send_usrp_wav(wav_path):
    """WAV を USRP プロトコルで送信(前後 1.5 秒のパディング付き)"""
    if not os.path.exists(wav_path):
        print(f"❌ ファイルが見つかりません: {wav_path}")
        return

    print(f"📂 送信ファイル: {wav_path}")
    print(f"📡 送信先     : {UDP_IP}:{UDP_PORT}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    wf = wave.open(wav_path, "rb")

    # フォーマット確認
    print(f"   - Sample rate: {wf.getframerate()} Hz")
    print(f"   - Channels   : {wf.getnchannels()}")
    print(f"   - Bits       : {wf.getsampwidth() * 8} bit")
    if wf.getframerate() != 8000 or wf.getnchannels() != 1 or wf.getsampwidth() != 2:
        print("⚠️  注意: 8kHz / mono / 16bit ではありません。音が崩れる可能性があります。")

    seq = 0
    next_send_time = time.monotonic()

    try:
        # PRE パディング
        print("▶️  PRE パディング(1.5秒)...")
        for _ in range(PRE_POST_PADDING_PACKETS):
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

        # 音声本体
        print("▶️  音声送信中...")
        while True:
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

        # POST パディング
        print("▶️  POST パディング(1.5秒)...")
        for _ in range(PRE_POST_PADDING_PACKETS):
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

    finally:
        # PTT OFF
        header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 0, 0, 0, 0, 0)
        sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
        sock.close()
        wf.close()

    print(f"✅ 送信完了 ({seq} パケット, 約 {seq * PACKET_INTERVAL:.1f}秒)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python3 test_send.py <WAVファイルパス>")
        print("例   : python3 /opt/dvswitch_bot/bin/test_send.py /opt/dvswitch_bot/002.wav")
        sys.exit(1)
    send_usrp_wav(sys.argv[1])
