#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 DVSwitch ログ監視・自動音声応答システム（デーモン版 / config-driven）
 — JJ2YYK デジピーター自動応答システム  V1.94 —

 本ファイルは常駐デーモンとして、カーチャンク自動応答・毎正時の時報・定時アナウンス・
 ナイトモードを提供する。判定・法令対応（無線局運用規則第30条）・watchdog 擬似終端・
 応答音声キャッシュ・頭無音・終端多重化・SET_INFO メタデータ送出など、主要な設計は
 すべてこのファイル内で完結している。
 
 バージョンごとの詳細な変更履歴（V1.60〜V1.93）は本ファイルには含めず、リポジトリ直下の
 Changelog.md に分離した（V1.92 でこの整理を実施）。改修時は Changelog.md を参照のこと。
 
 【設定項目（bot_config.json）】
  RX_DURATION_MIN_SEC : 最小受信時間（秒, 0 < MIN < MAX）
  RX_DURATION_MAX_SEC : 最大受信時間（秒, カーチャンク上限）
  ANNOUNCE_FREQ       : 1時間あたりの放送回数（TIME_SIGNAL_MODE 依存）
  TIME_SIGNAL_MODE    : 時刻案内モード（0/1/2, 任意キー。未設定なら 1）
  NIGHT_MODE_ENABLED  : ナイトモード有効（true / false）
  NIGHT_START_HOUR    : ナイトモード開始 N1（0〜23）
  NIGHT_END_HOUR      : ナイトモード終了 N2（0〜23）
  USE_CSTM_INTRO      : intro にカスタム音声を使う（true/false, 任意キー。既定 false）
  USE_CSTM_001        : 001 にカスタム音声を使う（true/false, 任意キー。既定 false）
  USE_CSTM_002        : 002 にカスタム音声を使う（true/false, 任意キー。既定 false）

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

 Document Version: V1.94 (daemon, V1.93 + 自局コールサイン/DMR ID の ini 自動取得)
 　（V1.93: V1.92 + 第30条セッションのギャップ判定バグ修正・
                          QSO_SESSION_GAP_SEC を独立定数化し 60 秒へ変更)
 Last Updated: 2026-07-07
================================================================================
"""

# ============================================================
# 🔵 機械可読バージョン（固定行 / ダッシュボード app.py が最優先で参照）
# ============================================================
# この行はファイル冒頭付近に固定で置く。docstring（人間向けの "Document Version:"）
# が長くなっても、ダッシュボードはこの __version__ を確実に拾える。
# 版を上げるときは下の文字列も必ず更新すること（docstring と一致させる）。
__version__ = "V1.94"

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

# ============================================================
# 🔵 V1.94: 自局コールサイン / DMR ID を ini から自動取得
# ============================================================
# V1.83〜V1.93 は MY_CALLSIGN / MY_DMR_ID をソースに直書きしており、
# (1) 他局が導入するとエディタでの手修正が必須、(2) 一括アップデートの
# たびに配布デフォルト（JJ2YYK / 4402396）へ巻き戻る、(3) ダッシュボード
# から変更できない、という不具合があった（JS1YTZ 局の報告で顕在化）。
# 正しい値は dvs_config.sh / ダッシュボードが管理する ini に既に存在する
# ため、起動時にそこから読む方式に変更し、真実の源を一本化した:
#   MY_CALLSIGN ← MMDVM_Bridge.ini の Callsign
#   MY_DMR_ID   ← Analog_Bridge.ini の gatewayDmrId
# ini が読めない・キーが無い場合のみ従来の既定値へフォールバックし、
# 起動ログに WARN を出す（後方互換。ただし自局判定 cs != MY_CALLSIGN が
# 誤るとループの恐れがあるため、WARN を見たら ini を確認すること）。
# 値の反映タイミングは bot 起動時（変更後は bot 再起動）。
_MMDVM_INI_PATH = "/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
_ANALOG_INI_PATH = "/opt/Analog_Bridge/Analog_Bridge.ini"


def _read_ini_value(path, key):
    """ini から最初に現れる `key = value` の値を返す（無ければ None）。
    dvs_config.sh / app.py の get_ini と同じ流儀: コメント行は対象外、
    行末の `;` コメントは除去。configparser は DVSwitch ini の重複キーで
    例外になり得るため使わない。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s.startswith((";", "#", "[")):
                    continue
                m = re.match(rf"^{re.escape(key)}\s*=\s*(.*)$", s)
                if m:
                    val = m.group(1).split(";")[0].strip()
                    return val or None
    except OSError:
        pass
    return None


def _resolve_my_station():
    """(callsign, dmr_id) を ini から解決する。失敗分のみ既定値で補う。"""
    fallback_cs, fallback_id = "JJ2YYK", 4402396  # 旧 V1.83 直書き値（互換用）
    cs = _read_ini_value(_MMDVM_INI_PATH, "Callsign")
    raw_id = _read_ini_value(_ANALOG_INI_PATH, "gatewayDmrId")
    dmr_id = None
    if raw_id and raw_id.isdigit():
        dmr_id = int(raw_id)
    warn = []
    if not cs:
        cs = fallback_cs
        warn.append(f"Callsign を {_MMDVM_INI_PATH} から取得できず既定値 {fallback_cs} を使用")
    if dmr_id is None:
        dmr_id = fallback_id
        warn.append(f"gatewayDmrId を {_ANALOG_INI_PATH} から取得できず既定値 {fallback_id} を使用")
    return cs, dmr_id, warn


MY_CALLSIGN, MY_DMR_ID, _MY_STATION_WARNINGS = _resolve_my_station()
# 🔴 V1.83: 送信前に SET_INFO メタデータを送るか。DVSwitch 公式クライアント
# (pyUC) と同じ振る舞いにして、Analog_Bridge に正規経路でコールサイン/ID を
# 通知する。False で V1.82 と同一（メタデータなし）。
TX_METADATA_ENABLED = True
DICT_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"

# 固定 WAV ファイルのパス
BOT_DIR = "/opt/dvswitch_bot"
FIXED_INTRO_WAV = f"{BOT_DIR}/fixed_intro.wav"
FIXED_OUTRO_WAV = f"{BOT_DIR}/fixed_outro.wav"
TIME_INTRO_WAV  = f"{BOT_DIR}/time_intro.wav"
TIME_OUTRO_WAV  = f"{BOT_DIR}/time_outro.wav"
MSG_FILES = [f"{BOT_DIR}/001.wav", f"{BOT_DIR}/002.wav"]

# 🔵 V1.73: カスタム WAV のパス（利用者が自己責任で用意する差し替え音声）。
# 設定 USE_CSTM_* が True かつ実ファイルが存在する場合のみ、標準の代わりに使う。
# 無ければ標準へフォールバックする（_resolve_wav 参照）。
CSTM_INTRO_WAV = f"{BOT_DIR}/cstm_intro.wav"
CSTM_MSG_FILES = [f"{BOT_DIR}/cstm_001.wav", f"{BOT_DIR}/cstm_002.wav"]

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
# 🔴 V1.82: 送信終端（USRP keyup=0）の送出回数。従来は1発のみで、取りこぼすと
# Analog_Bridge がストリームを閉じられず、DMR 終端フレームの生成が遅延・不整に
# なり得た（受信側無線機が受信状態のままスタックする一因）。複数回送って確実化。
USRP_EOT_REPEAT = 1
# 🔴 V1.84: 無音のノイズ充填（TGIF 先頭無音スキップ対策）。
# パケットキャプチャ解析により、TGIF は先頭のデジタル完全無音（全ゼロ PCM →
# AMBE 無音固定パターン）を転送せず、音が始まった所から配送を開始することが
# 判明（送信275/281フレームに対し配送224/230、差は2回とも51フレーム=3.06s
# ＝前パディング1.5s＋頭無音1.5sに一致）。ヘッダは無音区間の前にあるため
# 一緒に捨てられ、受信側はヘッダ無しストリームの途中参加を強いられる
# （MD-619 の受信スタックの直接原因）。
# 対策: 送出する PCM の「完全ゼロ」ブロックを、聞こえないほど微小なノイズ
# （振幅±NOISE_FILL_AMP、約-47dBFS）に置き換える。人の声のノイズフロアと
# 同様に AMBE が非無音として符号化するため、TGIF は先頭から転送する。
NOISE_FILL_ENABLED = True
# 🔴 V1.89: リード音をホワイトノイズ→100Hz微小トーン（ハム）に変更。
# AMBE は音声用ボコーダのため、ノイズは「ゲロゲロ」（うがい声様の歪み）に、
# 無音判定境界の振幅では「プツプツ」（無音/非無音フレームの交互）に化ける。
# 周期信号（トーン）なら綺麗に静かなハムとして符号化される。100Hz は 20ms
# ブロックにちょうど2周期＝ブロック連結で位相が完全連続。末尾5ブロックは
# フェードアウトして無音への遷移ポップも防ぐ。
NOISE_FILL_AMP = 150   # トーン振幅（150/32768 ≈ -47dBFS。AMBE 非無音判定の実証値）
# 🔴 V1.88: ノイズは前パディングの先頭 NOISE_LEAD_PACKETS 個だけに短縮。
# TGIF ゲート床（実測≈1.0〜1.3s）を跨ぐ最小限とし、残りはゼロ（無音）にして
# ゲート開放後に聞こえるノイズの尻尾を削る。頭シャーが残る場合はここを増やし、
# 逆に頭欠け/ハング症状が出る場合は 75（全区間ノイズ）に戻す。
NOISE_LEAD_PACKETS = 65   # 65×20ms=1.3s
# 🔴 V1.85: ゲート開放バースト。実測（V1.84: -47dBFS ノイズでスキップが
# 3.06s→1.32s に短縮）から、TGIF のゲートはエネルギー積算型と判断。
# 音量が大きいほど早く開く。そこでストリーム先頭の短時間だけ強めのノイズを
# 置き、最初のフレームでゲートを開かせてヘッダを保全する（JJ2ZAR 等の実局は
# マイク音声が即座にゲートを開くためヘッダが通る、と同じ状態を作る）。
# バーストはキーアップ直後の 300ms・-22dBFS の柔らかいヒスで、実用上目立たない。
GATE_BURST_PACKETS = 0    # 先頭のバーストパケット数（15×20ms=300ms）。0で無効
GATE_BURST_AMP = 2500      # バースト振幅（2500/32768 ≈ -22dBFS）
ROTATION_CHECK_INTERVAL = 5.0
GAP_AFTER_INTRO_SEC = 0.5

# 🔴 起動アナウンス遅延（秒）。起動後この秒数だけ待ってから送出する。
STARTUP_ANNOUNCE_DELAY_SEC = 5.0

# ============================================================
# 🔵 V1.75: コールサイン応答音声のキャッシュ設定（即応答化）
# ============================================================
# 同一コールサインの合成結果を再利用し、生成待ち（約2秒）を2回目以降で消す。
# ヘッダ受信時に先行生成し、終端/watchdog 判定が来た時にはキャッシュ完成済みに
# しておくことで即送出する。ソース定数（bot_config.json には置かない）。
# WATCHDOG_RX_MAX_SEC 等と同じ方針で、変更頻度が低くダッシュボードから触る必要の
# ない値のため三位一体（bot/setup/dashboard）の対象外とする。
REPLY_CACHE_ENABLED = True     # False で V1.74 と同一挙動（毎回 TEMP_FINAL に生成）
PREWARM_ON_HEADER   = True     # ヘッダ受信時に背景で先行生成してキャッシュを温める
CACHE_DIR    = f"/dev/shm/ocv_reply_cache_{_PID}"  # RAM 上・毎起動クリア（SD 保護）
CACHE_SCHEMA = "v1"            # 読み/結合仕様の版。仕様変更時に上げると全キャッシュ再生成

# 🔴 V1.77: キャッシュ命中時の送出前ガード（RF ターンアラウンド保護）。
# V1.74 まで合成に約2秒かかっており、その2秒が結果的に「相手が送信を終えてから
# SFR 中継の RX→TX 折り返し／経路が空くまでの待ち」を兼ねていた。キャッシュ即応答で
# その2秒が消えると、経路が空く前に応答がキーアップしてイントロ頭（「こちらは…」）が
# 食われる。そこで命中時のみ送出前にこの秒数だけ待ち、経路が空くのを待ってから
# キーアップする（前パディング 1.5s と合わせた総リードで頭欠けを防ぐ）。
# ミス時は合成に約2秒かかりガードを兼ねるため待たない（従来どおり）。
# 現場のターンアラウンドに合わせて調整可（頭が戻るなら下げて最短を探る）。0 で無効。
REPLY_TX_LEAD_DELAY_SEC = 1.0

# ============================================================
# ============================================================
# 🔵 V1.80: 検出即送出化（GPIO 依存排除）
# ============================================================
# ケロ検出直後に即座に送出し、実音声前の無音パッドで頭欠けを防ぐ。
# GPIO ファイルの存在・権限に依存せず、純粋なソフト制御。
PRE_AUDIO_SILENCE_SEC = 1.5           # 実音声前の無音パッド（受信側の途中参加同期の助走）。V1.87で復活

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
# 🔴 V1.74: 無線局運用規則 第30条対応（長時間通信時の識別信号強制送信）の設定
# ============================================================
# 無線局運用規則 第30条: 「無線局は、長時間継続して通報を送信するときは、
# 三十分（アマチュア局にあつては十分）ごとを標準として適当に「ＤＥ」及び
# 自局の呼出符号を送信しなければならない。」への対応。
#
# Normal QSO（長時間送信）判定が連続して発生している「セッション」の経過時間が
# この秒数の倍数を超えるたびに、通話と通話の間（＝送信終了直後のタイミング）で
# FIXED_INTRO_WAV を強制送信し、自局を識別する。セッションが続く限り繰り返す。
QSO_ID_INTERVAL_SEC = 600.0   # 10分（アマチュア局の標準）

# セッション継続とみなす無通信ギャップの上限（秒）。前回の Normal QSO 送信の
# 「終了」から今回の送信の「開始」までの純粋な無音がこの秒数を超えたら、
# セッションが途切れたとみなして積算をリセットし、次回はタイマーを 0 から
# 再スタートする。
# 🔴 V1.93: SUPPRESS_DURATION_SEC（15秒）のエイリアスをやめ独立定数化し、
# 値を 60.0 に変更。既存 TGIFChanger の自TG復帰判定（無音60秒）と運用上の
# 一貫性を優先し、本ソフト内での第30条運用定義として 60 秒を採用する。
QSO_SESSION_GAP_SEC = 60.0

# ============================================================
# グローバル状態 / 設定値
# ============================================================
should_exit = False
suppress_until = 0.0
is_talking = False
_reply_lock = threading.Lock()
# 🔵 V1.75: 合成パイプライン（共有一時ファイル使用）を直列化するロックと、
# コールサイン単位のビルド用ロック群（プリキャッシュと応答の競合を防ぐ）。
_gen_lock = threading.Lock()
# 🔴 V1.91: 送信フロー全体（生成→送出）を直列化するロック。
# 起動アナウンス・ケロ応答・時報・ナイト・10分ID が同時に走ることによる
# 二重送信／共有 TEMP_FINAL の上書き競合／UDPストリーム混線を防ぐ。
# ロック順序は常に _tx_lock（外）→ _gen_lock（内）。プリキャッシュは
# _gen_lock のみ取得（送信ではないため _tx_lock は取らない）。デッドロックなし。
_tx_lock = threading.Lock()
_cache_build_locks = {}
_cache_locks_guard = threading.Lock()

# 🔴 V1.74: 長時間通信セッションの追跡状態（すべて time.monotonic() 基準）
qso_session_start = None      # このセッションが始まった時刻（None=セッション無し）
qso_session_last_end = None   # 直近の Normal QSO 送信が終わった時刻
qso_session_id_count = 0      # このセッション内で既に送信した識別信号の回数

# 設定値（_load_config() が JSON から設定する。初期値はあくまでプレースホルダ）
RX_DURATION_MIN_SEC = None
RX_DURATION_MAX_SEC = None
ANNOUNCE_FREQ = None
TIME_SIGNAL_MODE = None
TX_GAIN = None
NIGHT_MODE_ENABLED = None
NIGHT_START_HOUR = None
NIGHT_END_HOUR = None
# 🔵 V1.73: カスタム音声を使うか（intro / 001 / 002 を個別指定）。任意キー・既定 False。
USE_CSTM_INTRO = None
USE_CSTM_001 = None
USE_CSTM_002 = None

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
    global USE_CSTM_INTRO, USE_CSTM_001, USE_CSTM_002

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

    # 🔵 V1.73: カスタム音声フラグ（任意キー / 既定 False）。
    # intro / 001 / 002 を個別に「カスタムを使う(True) / 標準(False)」で指定する。
    # bool 以外（未設定含む不正値）は安全側に False（標準）として扱い、起動は止めない。
    def _as_bool(key):
        v = cfg.get(key, False)
        if isinstance(v, bool):
            return v
        logger.warning(_fmt("!!", key, str(v),
                            "bool でないため False（標準音声）として扱う"))
        return False
    use_cstm_intro = _as_bool("USE_CSTM_INTRO")
    use_cstm_001   = _as_bool("USE_CSTM_001")
    use_cstm_002   = _as_bool("USE_CSTM_002")

    # 5) 反映
    RX_DURATION_MIN_SEC = rx_min
    RX_DURATION_MAX_SEC = rx_max
    ANNOUNCE_FREQ = freq
    TIME_SIGNAL_MODE = ts_mode
    TX_GAIN = tx_gain
    NIGHT_MODE_ENABLED = night_enabled
    NIGHT_START_HOUR = n1
    NIGHT_END_HOUR = n2
    USE_CSTM_INTRO = use_cstm_intro
    USE_CSTM_001 = use_cstm_001
    USE_CSTM_002 = use_cstm_002

    logger.info(_fmt("..", "Config", "loaded", CONFIG_PATH))


# 🔵 V1.73: カスタム/標準の WAV パス解決（欠落時フォールバック付き）
def _resolve_wav(use_cstm, cstm_path, fixed_path, label=""):
    """カスタム使用フラグと実ファイルの有無から、実際に再生するパスを返す。

    - use_cstm が True かつ cstm_path が存在 → cstm_path（カスタムを使う）
    - use_cstm が True だが cstm_path が無い → fixed_path（標準へフォールバック＋警告）
    - use_cstm が False → fixed_path（標準）

    こうして「カスタム指定したのにファイルが無い」事故でも送出を止めず、
    標準音声で鳴らし続ける。判定は送出のたびに行う（後から cstm を置けば
    再起動なしで次回から反映される）。
    """
    if use_cstm:
        if os.path.exists(cstm_path):
            return cstm_path
        logger.warning(_fmt("!!", "CSTM missing", label or os.path.basename(cstm_path),
                            f"{os.path.basename(cstm_path)} が無いため標準にフォールバック"))
    return fixed_path


def _handle_signal(signum, frame):
    global should_exit
    sig_name = signal.Signals(signum).name
    logger.info(_fmt("..", "Signal", sig_name, "shutting down"))
    should_exit = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ============================================================

# ============================================================
# 送信・生成
# ============================================================
# 🔴 V1.84/V1.89: リード音ブロック（20ms/160サンプル/320バイト）を事前生成。
# 完全ゼロの先頭を非無音にして TGIF の先頭無音スキップを回避する。
# V1.89: 内容はホワイトノイズではなく 100Hz 微小トーン（AMBE で綺麗に載る）。
import math as _math
_TONE_BLOCK = b""
_TONE_FADES = []          # 末尾フェード用（振幅を段階的に絞ったブロック）
_FADE_STEPS = (0.75, 0.55, 0.35, 0.20, 0.08)

def _init_noise_blocks():
    global _TONE_BLOCK, _TONE_FADES
    base = [ _math.sin(2 * _math.pi * 100.0 * i / 8000.0) for i in range(160) ]  # 100Hz=2周期/20ms
    _TONE_BLOCK = struct.pack("<160h", *[int(NOISE_FILL_AMP * s) for s in base])
    _TONE_FADES = [struct.pack("<160h", *[int(NOISE_FILL_AMP * f * s) for s in base])
                   for f in _FADE_STEPS]

def _lead_block(i: int, lead_total: int) -> bytes:
    """前パディング i 番目のリード音ブロック。末尾 len(_FADE_STEPS) 個はフェード。"""
    if not _TONE_BLOCK:
        _init_noise_blocks()
    fade_start = lead_total - len(_FADE_STEPS)
    if i >= fade_start:
        return _TONE_FADES[min(i - fade_start, len(_TONE_FADES) - 1)]
    return _TONE_BLOCK

def _noise_block() -> bytes:
    """互換用: リード音の基本ブロックを返す。無効時はゼロ。"""
    if not NOISE_FILL_ENABLED:
        return b"\x00" * 320
    if not _TONE_BLOCK:
        _init_noise_blocks()
    return _TONE_BLOCK

_ZERO_320 = b"\x00" * 320

def _fill_if_silent(data: bytes) -> bytes:
    """PCM ブロックが完全ゼロなら微小ノイズに置き換える（それ以外はそのまま）。"""
    if NOISE_FILL_ENABLED and data == _ZERO_320:
        return _noise_block()
    return data


def _usrp_set_info_payload(callsign: str, dmr_id: int) -> bytes:
    """🔴 V1.83: DVSwitch 公式クライアント pyUC の sendMetadata() と同一の
    TLV_TAG_SET_INFO(8) ペイロードを組む。
      [tag(1)][len(1)][dmrID(3)][repeaterID(4)=0][tg(3)=0][ts(1)=0][cc(1)=0][callsign][NUL]
    tg/ts/cc は 0（pyUC と同じ）。実際の TG/TS/CC は Analog_Bridge.ini の
    txTg/txTs/colorCode が使われる。"""
    call = callsign.encode("ascii") + b"\x00"
    tlv_len = 3 + 4 + 3 + 1 + 1 + len(callsign) + 1
    head = bytes([
        8, tlv_len,                                   # TLV_TAG_SET_INFO, length
        (dmr_id >> 16) & 0xFF, (dmr_id >> 8) & 0xFF, dmr_id & 0xFF,  # DMR ID (3B)
        0, 0, 0, 0,                                   # repeater ID (4B)
        0, 0, 0,                                      # TG (3B) = 0
        0,                                            # TS = 0
        0,                                            # CC = 0
    ])
    return head + call


def _send_usrp_metadata(sock, seq: int) -> int:
    """🔴 V1.83: 音声送出の前に SET_INFO メタデータを送る（pyUC と同じ振る舞い）。
    ヘッダは pyUC の sendUSRPCommand() と同一: keyup=0, type ワードに
    (USRP_TYPE_TEXT=2) << 24 を格納する（公式クライアントのバイト列を踏襲）。
    戻り値は次に使う seq。"""
    payload = _usrp_set_info_payload(MY_CALLSIGN, MY_DMR_ID)
    header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 0, 0, (2 << 24), 0, 0)
    sock.sendto(header + payload, (UDP_IP, UDP_PORT))
    return seq + 1


def send_usrp_wav_with_padding(wav_path):
    """WAV を USRP プロトコルで送信(前後 1.5 秒のパディング付き、絶対時刻同期)"""
    sock = None
    wf = None
    seq = 0
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        wf = wave.open(wav_path, "rb")

        next_send_time = time.monotonic()

        # 🔴 V1.83: 送信前に SET_INFO メタデータ（コールサイン/DMR ID）を送る。
        # 正規 USRP クライアント（pyUC/DVSwitch Mobile）と同じ振る舞いにして、
        # Analog_Bridge が正規経路でメタデータを組み立てられるようにする。
        if TX_METADATA_ENABLED:
            seq = _send_usrp_metadata(sock, seq)
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

        for _i in range(PRE_POST_PADDING_PACKETS):
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            # 🔴 V1.88/V1.89: 前パディングの先頭 NOISE_LEAD_PACKETS 個のみ
            # 100Hz 微小トーン（末尾フェード付き）。残りはゼロ。
            if NOISE_FILL_ENABLED and _i < NOISE_LEAD_PACKETS:
                payload = _lead_block(_i, NOISE_LEAD_PACKETS)
            else:
                payload = b"\x00" * 320
            sock.sendto(header + payload, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

        while not should_exit:
            data = wf.readframes(160)
            if not data:
                break
            if len(data) < 320:
                data += b"\x00" * (320 - len(data))
            # 🔵 V1.86: WAV 内の無音は置換しない（ゲート開放後の無音は正常に転送される
            # ことが実測で確認済み。真の無音のままにして耳障りなノイズを排除）
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + data, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

        for _ in range(PRE_POST_PADDING_PACKETS):
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            # 🔵 V1.86: 後パディングはゼロ（真の無音）に戻す。ゲートは既に開いており
            # 無音でも転送されるため、終端側のノイズ音を排除できる。
            sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
            seq += 1
            next_send_time += PACKET_INTERVAL
            time.sleep(max(0, next_send_time - time.monotonic()))

    except Exception as e:
        logger.error(_fmt("!!", "Send error", "", str(e)))
    finally:
        if sock:
            # 🔴 V1.82: 送信終端の確実化。
            # 従来は keyup=0 を1発だけ・直前パケットと間隔ゼロで送って即クローズ
            # していた。この1発を Analog_Bridge が取りこぼすとストリームが閉じず、
            # DMR 終端フレームが正しく出ない（受信機が受信状態で固まる一因）。
            # 対策: keyup=0 を USRP_EOT_REPEAT 回、正規のパケット間隔（20ms）で
            # 送る（送信ループのペーシングが直前の間隔を確保済み）。
            # Analog_Bridge は最初の keyup=0 でストリームを閉じ、残りは無害。
            try:
                for _ in range(max(1, USRP_EOT_REPEAT)):
                    header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 0, 0, 0, 0, 0)
                    sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
                    seq += 1
                    time.sleep(PACKET_INTERVAL)
            except OSError:
                pass
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
                    # 🔵 V1.73: 001/002 を個別に cstm 解決（欠落時は標準へフォールバック）。
                    _idx = msg_index % len(MSG_FILES)
                    _use_cstm = USE_CSTM_001 if _idx == 0 else USE_CSTM_002
                    target = _resolve_wav(
                        _use_cstm, CSTM_MSG_FILES[_idx], MSG_FILES[_idx],
                        os.path.basename(MSG_FILES[_idx]))
                    logger.info(_fmt("..", "Trigger",
                                     os.path.basename(target),
                                     "scheduled_message"))
                    _start_worker("fixed_file", target)
                    msg_index += 1

        time.sleep(1)

    logger.info(_fmt("..", "Scheduler", "stopped"))


def _start_worker(mode, val, extra=None):
    """返り値: 実際にワーカースレッドを起動できたら True、is_talking 中で
    スキップした場合は False。🔴 V1.74: 識別信号の強制送信で、送信できたか
    どうかを呼び出し側が判定して再試行させるために戻り値を追加した
    （既存の呼び出し元は戻り値を無視しており挙動に影響しない）。"""
    global is_talking
    with _reply_lock:
        if is_talking:
            logger.info(_fmt("..", "Skipped", str(val), f"already talking ({mode})"))
            return False
        is_talking = True
    threading.Thread(target=_reply_executor, args=(mode, val, extra), daemon=True).start()
    return True


# ============================================================
# 🔴 V1.67: 受信時間に基づくカーチャンク判定/抑制（共通ロジック / V1.65 から移植）
# ============================================================
def _assert_identity():
    """🔴 V1.90: 自局アイデンティティ(SET_INFO)を Analog_Bridge に再主張する。
    AB は「最後に聞いた局」のコールサインをメタデータとして保持し、次の送信の
    Talker Alias に埋め込むため、他局の受信が終わるたびにここで JJ2YYK/自局 ID
    に上書きする（受信終端のたび＋起動時＋送信直前の三重主張）。"""
    if not TX_METADATA_ENABLED:
        return
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _send_usrp_metadata(s, 0)
        s.close()
    except OSError:
        pass


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

    # 🔴 V1.90: 他局の受信が終わった直後に自局アイデンティティを再主張。
    # AB の「最後に聞いた局」状態（JJ2ZAR 等）を JJ2YYK に上書きし、
    # 応答の Talker Alias がケロした局のコールサインを引きずるのを防ぐ。
    if cs != MY_CALLSIGN:
        _assert_identity()

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
        # 🔴 V1.74: 無線局運用規則 第30条対応。カーチャンクではなく Normal QSO
        # （長時間送信）のみをセッション判定・10分カウントの対象とする。
        # 🔴 V1.93: 今回の送信時間 dur を渡し、ギャップ判定を純粋な無音時間で行う。
        _handle_qso_session(now, dur)
    else:
        logger.info(f"receive:Too short, ignored{tag}: {cs} ({dur:.1f}s, min={RX_DURATION_MIN_SEC}s)")


# ============================================================
# 🔴 V1.74: 無線局運用規則 第30条対応（長時間通信セッション管理 + 識別信号強制送信）
# ============================================================
def _handle_qso_session(now, dur=0.0):
    """Normal QSO（長時間送信）が検知されるたびに呼ばれる。

    前回の Normal QSO 送信の「終了」から今回の送信の「開始」までの純粋な
    無通信ギャップが QSO_SESSION_GAP_SEC（60秒）以内で連続している間は
    同一の「長時間通信セッション」とみなし、セッション開始からの経過時間を
    積算する。経過時間が QSO_ID_INTERVAL_SEC（10分）の倍数を新たに跨ぐたびに、
    このタイミング（＝直前の送信が終わった、通話と通話の「間」）で
    FIXED_INTRO_WAV を強制送信して自局を識別する。セッションが続く限り
    10分おきに繰り返す（無線局運用規則 第30条）。

    🔴 V1.93: ギャップ判定バグ修正。now は今回送信の「終了」時刻なので、
    従来の (now - qso_session_last_end) は「無音＋今回の通話時間」となり、
    無音が短くても通話が長いだけで誤ってセッションがリセットされていた。
    今回の送信時間 dur を受け取り、tx_start = now - dur（今回送信の開始時刻の
    近似）を求め、(tx_start - qso_session_last_end) で純粋な無音時間を評価する。
    セッション開始時刻も tx_start に合わせ、最初の送信の通話時間も経過時間に
    含める（経過時間の起点をギャップ判定の起点と一致させる）。

    識別信号の内容を法的に保証するため、USE_CSTM_INTRO の設定に関わらず
    必ず正規の FIXED_INTRO_WAV を送信する（カスタム音声には差し替えない）。

    他の送出と衝突して送信できなかった場合（is_talking 中）は
    qso_session_id_count を更新しない。これにより次回の Normal QSO 検知時に
    再び「due_count > qso_session_id_count」となり自動的に再試行される
    （取りこぼし防止）。
    """
    global qso_session_start, qso_session_last_end, qso_session_id_count

    # 🔴 V1.93: 今回送信の開始時刻の近似（now は終了時刻）。
    tx_start = now - dur

    if qso_session_last_end is None or (tx_start - qso_session_last_end) > QSO_SESSION_GAP_SEC:
        # 前回の Normal QSO の終了から今回の送信開始までの純粋な無音が
        # QSO_SESSION_GAP_SEC 超（無通信で区切りがついた）、または今回が初回 →
        # 新しいセッションとして 0 から開始。セッション開始は今回送信の開始時刻に
        # 合わせ、最初の送信の通話時間も経過時間に含める。
        qso_session_start = tx_start
        qso_session_id_count = 0
        logger.info(_fmt("..", "QSO session", "start",
                         f"long-transmission session began (10-min ID every {QSO_ID_INTERVAL_SEC/60:.0f}min)"))

    qso_session_last_end = now

    elapsed = now - qso_session_start
    due_count = int(elapsed // QSO_ID_INTERVAL_SEC)

    if due_count > qso_session_id_count:
        started = _start_worker("regulatory_id", FIXED_INTRO_WAV)
        if started:
            logger.info(_fmt("TX", "Regulatory ID", "",
                             f"session {elapsed/60:.1f}min elapsed -> forcing fixed_intro.wav "
                             f"(#{due_count}, rule 30)"))
            qso_session_id_count = due_count
        else:
            # is_talking 中でスキップされた。カウンタは更新せず、次回の
            # Normal QSO 検知時に再試行させる（法令上、取りこぼしは避けたい）。
            logger.warning(_fmt("!!", "Regulatory ID", "deferred",
                                f"busy (other TX in progress) - will retry at next "
                                f"Normal QSO detection (elapsed {elapsed/60:.1f}min)"))


# ============================================================
# 🔴 起動アナウンス（V1.62）
# ============================================================
def _send_startup_announcement():
    """起動アナウンス。起動後 STARTUP_ANNOUNCE_DELAY_SEC 秒遅延して
    「起動しました。」を 1 回だけ送出する。
    🔴 V1.91: _tx_lock で他の送信（起動直後の他局受信への応答等）と直列化。
    従来は無ロックで、起動直後に他局を受信すると応答と二重送信になり
    ストリームが壊れることがあった。TEMP の実行中削除も廃止（競合の元凶）。"""
    if should_exit:
        return
    with _tx_lock:
        started_at = time.monotonic()
        middle_text = "起動しました。"
        logger.info(_fmt("TX", "Generate", "startup", "startup_announce"))
        _intro = _resolve_wav(USE_CSTM_INTRO, CSTM_INTRO_WAV, FIXED_INTRO_WAV, "intro")
        if _generate_hybrid(_intro, middle_text, None):
            logger.info(_fmt("TX", "Sending", "startup", "startup_announce"))
            send_usrp_wav_with_padding(TEMP_FINAL)
            elapsed = time.monotonic() - started_at
            logger.info(_fmt("TX", "Startup", "startup", f"{elapsed:.1f}s"))
        else:
            logger.error(_fmt("!!", "Gen failed", "startup", "startup_announce"))


# ============================================================
# ナイトモード開始アナウンス
# ============================================================
NIGHT_ANN_GAP_SEC = 1.0


def _send_night_mode_announcement():
    started_at = time.monotonic()
    resume_hour = (NIGHT_END_HOUR + 1) % 24
    middle_text = f"ただいまより、このデジピーターは、みょうちょう{resume_hour}時まで、ナイトモードに入ります。"
    label = f"N1={NIGHT_START_HOUR:02d}"

    time.sleep(NIGHT_ANN_GAP_SEC)

    logger.info(_fmt("TX", "Generate", label, "night_announce"))
    _intro = _resolve_wav(USE_CSTM_INTRO, CSTM_INTRO_WAV, FIXED_INTRO_WAV, "intro")
    if _generate_hybrid(_intro, middle_text, None):
        logger.info(_fmt("TX", "Sending", label, "night_announce"))
        send_usrp_wav_with_padding(TEMP_FINAL)
        elapsed = time.monotonic() - started_at
        logger.info(_fmt("TX", "NightAnn", label, f"{elapsed:.1f}s"))
    else:
        logger.error(_fmt("!!", "Gen failed", label, "night_announce"))


# ============================================================
# 🔵 V1.75: コールサイン応答音声のキャッシュ（即応答化）
# ============================================================
# 置き場所は /dev/shm（RAM）。プロセス再起動で自動クリアされ、設定は起動時のみ
# 読むため、キャッシュは常に現在の設定と整合する。さらに intro（cstm 差し替え
# 含む）/ outro / GAP / TX_GAIN / 音声モデル / スキーマ版のシグネチャを .sig に
# 併存させ、変化したら自動再生成する（cstm 音声の無再起動差し替えにも追従）。

def _safe_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _cache_path(cs):
    safe = cs.upper().replace("/", "_")
    return f"{CACHE_DIR}/{safe}.wav"


def _mtime(path):
    try:
        return f"{os.path.getmtime(path):.3f}"
    except OSError:
        return "0"


def _reply_signature():
    """キャッシュ整合性の署名。cs 非依存（intro/outro/ゲイン等のみに依存）。
    解決後 intro の実体（cstm 差し替え含む）・各 WAV の mtime・GAP・TX_GAIN・
    頭無音・音声モデル・スキーマ版が変われば署名が変わり、再生成が走る。"""
    intro = _resolve_wav(USE_CSTM_INTRO, CSTM_INTRO_WAV, FIXED_INTRO_WAV, "intro")
    return "|".join([
        CACHE_SCHEMA,
        intro, _mtime(intro),
        FIXED_OUTRO_WAV, _mtime(FIXED_OUTRO_WAV),
        f"{GAP_AFTER_INTRO_SEC}",
        f"{PRE_AUDIO_SILENCE_SEC}",
        f"{TX_GAIN}",
        VOICE_PATH,
    ])


def _cs_build_lock(cs):
    with _cache_locks_guard:
        lk = _cache_build_locks.get(cs)
        if lk is None:
            lk = threading.Lock()
            _cache_build_locks[cs] = lk
        return lk


def _cache_valid(path, sig_path, sig_now):
    try:
        return os.path.exists(path) and _read_text(sig_path) == sig_now
    except OSError:
        return False


def _ensure_cached(cs):
    """cs の応答 WAV を返す。無ければ生成して /dev/shm に格納する。
    返り値: (path, was_hit)。was_hit=True はキャッシュ命中（合成スキップ）。
    生成失敗時は (None, False)。"""
    # キャッシュ無効時は V1.74 と同一挙動（毎回 TEMP_FINAL に生成）。
    if not REPLY_CACHE_ENABLED:
        cs_kana = "".join([CHAR_TO_KANA.get(ch, ch) for ch in cs.upper()])
        middle = f"{cs_kana}局の、"
        intro = _resolve_wav(USE_CSTM_INTRO, CSTM_INTRO_WAV, FIXED_INTRO_WAV, "intro")
        ok = _generate_hybrid(intro, middle, FIXED_OUTRO_WAV, out_path=TEMP_FINAL,
                              head_silence=PRE_AUDIO_SILENCE_SEC)
        return (TEMP_FINAL, False) if ok else (None, False)

    path = _cache_path(cs)
    sig_path = f"{path}.sig"
    sig_now = _reply_signature()

    # ロック外の高速ヒット判定（プリキャッシュ完了済みなら即ここで返る）
    if _cache_valid(path, sig_path, sig_now):
        return path, True

    with _cs_build_lock(cs):
        # 待機中に他スレッド（プリキャッシュ等）が生成済みかを再確認
        if _cache_valid(path, sig_path, sig_now):
            return path, True

        cs_kana = "".join([CHAR_TO_KANA.get(ch, ch) for ch in cs.upper()])
        middle = f"{cs_kana}局の、"
        intro = _resolve_wav(USE_CSTM_INTRO, CSTM_INTRO_WAV, FIXED_INTRO_WAV, "intro")
        # 🔴 V1.76: 一時ファイルも必ず .wav 拡張子にする。SoX は出力の拡張子で
        # フォーマットを判別するため、.part など未知の拡張子だと
        # "no handler for file extension" で失敗する（V1.75 の実機不具合）。
        # path は _cache_path により必ず .wav 終わりなので、それを基に .wav の
        # 一時名を作り、完成後に os.replace で原子的に本名へ差し替える。
        # 🔴 V1.80: 頭無音（PRE_AUDIO_SILENCE_SEC）もここで焼き込む（送出時の再パッド不要）。
        tmp = f"{path[:-4]}.building.wav" if path.endswith(".wav") else f"{path}.building.wav"
        if _generate_hybrid(intro, middle, FIXED_OUTRO_WAV, out_path=tmp,
                            head_silence=PRE_AUDIO_SILENCE_SEC):
            try:
                os.replace(tmp, path)   # 半端な書きかけを読ませないため原子的に差し替え
                with open(sig_path, "w", encoding="utf-8") as sf:
                    sf.write(sig_now)
                return path, False
            except OSError as e:
                logger.error(_fmt("!!", "Cache write", cs, str(e)))
                _safe_remove(tmp)
                return None, False
        _safe_remove(tmp)
        return None, False


def _prewarm_reply(cs):
    """🔵 V1.75: ヘッダ受信時に呼ぶ。未キャッシュなら背景で先行生成する。
    既にキャッシュがあれば何もしない（2回目以降は作らない）。送信状態
    (is_talking) には触れないので、応答・時報等とは独立に走る。"""
    if not (REPLY_CACHE_ENABLED and PREWARM_ON_HEADER):
        return
    path = _cache_path(cs)
    if _cache_valid(path, f"{path}.sig", _reply_signature()):
        return  # 既にキャッシュあり → 生成しない

    def _worker():
        # 🔴 V1.76: 生成失敗時に "ready" と誤記していたのを修正。
        # path が None（生成失敗）なら failed、成功時のみ ready を出す。
        path, was_hit = _ensure_cached(cs)
        if path is None:
            logger.error(_fmt("!!", "Precache", cs, "failed"))
        elif not was_hit:
            logger.info(_fmt("..", "Precache", cs, "ready"))

    threading.Thread(target=_worker, daemon=True).start()


def _init_reply_cache():
    """起動時にキャッシュ用ディレクトリを作り直す（RAM 上・毎起動クリア）。
    設定は起動時のみ読むため、クリアによりキャッシュは常に現行設定と整合する。"""
    if not REPLY_CACHE_ENABLED:
        return
    try:
        if os.path.isdir(CACHE_DIR):
            for name in os.listdir(CACHE_DIR):
                _safe_remove(os.path.join(CACHE_DIR, name))
        else:
            os.makedirs(CACHE_DIR, exist_ok=True)
    except OSError as e:
        logger.error(_fmt("!!", "Cache init", CACHE_DIR, str(e)))


def _reply_executor(mode, val, extra=None):
    global is_talking, suppress_until
    started_at = time.monotonic()
    # 🔴 V1.91: 送信フロー全体を直列化（二重送信・ストリーム破壊の防止）。
    # 起動アナウンス・ケロ応答・時報・ナイト等が同時に走ると、UDP ストリームが
    # 混ざる／共有 TEMP_FINAL を上書きし合う。ここで一本化する。
    if not _tx_lock.acquire(blocking=False):
        logger.info(_fmt("..", "TX queue", str(val), "waiting for current TX"))
        _tx_lock.acquire()
    try:
        if mode == "kerchunk":
            # 🔵 V1.75: 応答はキャッシュ優先。ヘッダ受信時のプリ生成が間に合って
            # いればここは即ヒットし、合成をスキップして即送出する。ミス時は
            # ここで生成してキャッシュに格納する（そのコールサインの初回のみ）。
            # ログの Cached=命中（合成なし）/ Generate=生成 で高速経路が判別できる。
            path, was_hit = _ensure_cached(val)
            if path:
                logger.info(_fmt("TX", "Cached" if was_hit else "Generate", val))
                # 🔴 V1.86: SFR 折り返し保護を V1.77 実証方式（送出前の実時間待ち）に回帰。
                # ストリーム内の無音（焼き込み頭無音）は TGIF に食われる／ノイズ充填は
                # 耳障り、と実測で判明したため、音に一切影響しない wall-clock 待ちで
                # 折り返しを保護する。命中時のみ待つ（ミス時は合成約2秒がガードを兼ねる）。
                if was_hit and REPLY_TX_LEAD_DELAY_SEC > 0:
                    logger.info(_fmt("..", "TX lead", val, f"{REPLY_TX_LEAD_DELAY_SEC:.1f}s"))
                    time.sleep(REPLY_TX_LEAD_DELAY_SEC)
                logger.info(_fmt("TX", "Sending", val))
                send_usrp_wav_with_padding(path)
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

        elif mode == "regulatory_id":
            # 🔴 V1.74: 無線局運用規則 第30条対応の識別信号強制送信。
            # val は常に FIXED_INTRO_WAV（呼び出し元 _handle_qso_session が固定で
            # 渡す）。法令上の識別内容を保証するため、USE_CSTM_INTRO の設定や
            # _resolve_wav は経由せず、常に正規の固定ファイルを送信する。
            basename = os.path.basename(val)
            if os.path.exists(val):
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
                logger.info(_fmt("TX", "Sending", basename, "regulatory_id (rule 30)"))
                send_usrp_wav_with_padding(play_path)
                elapsed = time.monotonic() - started_at
                logger.info(_fmt("TX", "RegID", basename, f"{elapsed:.1f}s"))
            else:
                logger.error(_fmt("!!", "File missing", basename, val))

        else:
            logger.error(_fmt("!!", "Unknown mode", str(mode)))

    except Exception as e:
        logger.error(_fmt("!!", "Executor err", str(mode), str(e)))
    finally:
        # 🔴 V1.91: 実行中の共有 TEMP_* 削除を廃止（Race Condition の元凶）。
        # 従来はここで TEMP_48K 等を削除していたが、プリキャッシュ・スレッドが
        # _generate_hybrid で同じファイルを生成している最中に横から消してしまい
        # 「sox FAIL」を誘発していた。共有 TEMP は /dev/shm 上の小ファイルで、
        # 各生成が上書きするため実行中の削除は不要。掃除は起動時のみ行う。
        _tx_lock.release()
        with _reply_lock:
            is_talking = False


def _generate_hybrid(intro, middle_text, outro, out_path=TEMP_FINAL, head_silence=0.0):
    # 🔵 V1.75: 合成パイプラインは共有一時ファイル(TEMP_48K/8K/INTRO_PADDED)を
    # 使うため、プリキャッシュ・スレッドと応答スレッドが同時に走っても壊れないよう
    # _gen_lock で直列化する（Pi では合成が CPU 律速で並列化の利得も薄い）。
    # out_path を追加し、キャッシュ用に任意の出力先へ結合できるようにした
    # （既定 TEMP_FINAL のため、時報など既存呼び出しは挙動不変）。
    with _gen_lock:
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

            # 🔴 V1.80: イントロ整形。pad "先頭無音" "末尾無音"。
            #   先頭 = head_silence（kerchunk 応答のみ SFR 折り返し対策で無音を焼き込む。
            #          時報・起動等は 0 なので従来どおりズレない）
            #   末尾 = GAP_AFTER_INTRO_SEC（イントロと合成音の間）
            subprocess.run(
                ["sox", intro, TEMP_INTRO_PADDED, "pad", f"{head_silence}", f"{GAP_AFTER_INTRO_SEC}"],
                check=True,
            )

            concat_cmd = ["sox", TEMP_INTRO_PADDED, TEMP_8K]
            if outro is not None:
                concat_cmd.append(outro)
            concat_cmd.append(out_path)
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
        finally:
            # 🔴 V1.92: 中間ファイルの掃除は「生成の責任」として _gen_lock 保持の
            # ままここで行う（レビュー指摘の採用）。ロック内なので他スレッドの
            # 生成と競合せず、作業ファイルの寿命が明確になる。
            # 注意: out_path（TEMP_FINAL/キャッシュ）は呼び出し元が送信で読むため
            # ここでは削除しない。
            for _t in (TEMP_48K, TEMP_8K, TEMP_INTRO_PADDED):
                _safe_remove(_t)


# ============================================================
# 設定値ダンプ
# ============================================================
def _log_startup_info():
    logger.info("=" * 70)
    logger.info(f"DVSwitch Bot V1.93 (daemon, V1.92 + 第30条ギャップ判定修正) starting up (PID: {_PID})")
    logger.info(f"  My callsign       : {MY_CALLSIGN}")
    # 🔵 V1.94: DMR ID と取得元も表示。ini から読めなかった項目は WARN を出す。
    logger.info(f"  My DMR ID         : {MY_DMR_ID}  (source: ini 自動取得)")
    for _w in _MY_STATION_WARNINGS:
        logger.warning(f"  [station] {_w} — ini を確認してください（自局判定の誤りはループの恐れ）")
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
    # 🔴 V1.74/V1.93: 無線局運用規則 第30条対応（識別信号強制送信）の状態を表示
    logger.info(f"  Regulatory ID     : ON  (rule 30 / interval={QSO_ID_INTERVAL_SEC/60:.0f}min, "
                f"session gap={QSO_SESSION_GAP_SEC:.0f}s, always uses {os.path.basename(FIXED_INTRO_WAV)})")
    # 🔵 V1.75: コールサイン応答音声キャッシュ（即応答化）の状態を表示
    if REPLY_CACHE_ENABLED:
        logger.info(f"  Reply cache       : ON  (RAM {CACHE_DIR} / "
                    f"prewarm={'ON' if PREWARM_ON_HEADER else 'OFF'} / schema={CACHE_SCHEMA} / "
                    f"hit lead={REPLY_TX_LEAD_DELAY_SEC:.1f}s)")
    else:
        logger.info(f"  Reply cache       : OFF (V1.74 と同一 / 毎回生成)")
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

    # 🔵 V1.73: カスタム音声の選択状態と、実際に再生されるファイル（解決後）を表示。
    # 「カスタム指定だが実ファイルが無い → 標準にフォールバック」も一目で分かる。
    logger.info("-" * 70)
    _cstm_items = [
        ("intro", USE_CSTM_INTRO, CSTM_INTRO_WAV, FIXED_INTRO_WAV),
        ("001",   USE_CSTM_001,   CSTM_MSG_FILES[0], MSG_FILES[0]),
        ("002",   USE_CSTM_002,   CSTM_MSG_FILES[1], MSG_FILES[1]),
    ]
    for name, use_cstm, cstm_path, fixed_path in _cstm_items:
        if not use_cstm:
            logger.info(f"  Voice {name:<5}     : 標準 ({os.path.basename(fixed_path)})")
        elif os.path.exists(cstm_path):
            logger.info(f"  Voice {name:<5}     : カスタム ({os.path.basename(cstm_path)})")
        else:
            logger.warning(f"  Voice {name:<5}     : カスタム指定だが {os.path.basename(cstm_path)} が無い "
                           f"→ 標準 ({os.path.basename(fixed_path)}) にフォールバック")

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
    # 🔵 V1.75: 応答音声キャッシュを初期化（RAM 上・毎起動クリア）。設定は起動時
    # のみ読むため、ここでクリアすればキャッシュは常に現行設定と整合する。
    _init_reply_cache()
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
    # 🔴 V1.91: 前回異常終了で残った共有 TEMP を起動時に一括掃除
    # （実行中の削除は廃止したため、掃除はここでのみ行う）
    for _tmp in (TEMP_FINAL, TEMP_48K, TEMP_8K, TEMP_INTRO_PADDED):
        _safe_remove(_tmp)
    logger.info("Bot ready — monitoring DMR traffic")
    # 🔴 V1.90: 起動時にも自局アイデンティティを主張しておく
    _assert_identity()

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
                    # 🔵 V1.75: 受信即・先行生成。未キャッシュなら背景で合成を始め、
                    # 終端/watchdog 判定が来る頃には完成させておく（即応答化）。
                    # 既にキャッシュがあれば何もしない（2回目以降は作らない）。
                    _prewarm_reply(cs)
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
