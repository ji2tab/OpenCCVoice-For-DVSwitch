#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 OpenCCVoice for DVSwitch  —  Web USRP クライアント
 usrp_web_tx.py  V0.3tx  （実験版: RX + TX〔AudioWorklet送信/PTT状態機械/WD〕/ HTTPS / catch-up）

 目的:
   Analog_Bridge が復号した受信音声（USRP 音声パケット）を UDP で受け、
   ブラウザ（Web 起動PC）へ WebSocket でストリーミングして
   PC のスピーカーで鳴らす「受信モニタ」。

 このフェーズ1は「聞くだけ」。送信(TX)は行わない。したがって:
   - dvswitch_bot.py には一切触れない（排他ロックもまだ不要）。
   - Analog_Bridge が RX 音声を出すポート(USRP txPort)を bind して受けるだけ。
     bot はカーチャンク検出をログ監視で行い、USRP は「送出専用」で使っている想定
     なので、この RX 出力ポートは通常空いている。もし bind に失敗する場合は
     他プロセスが掴んでいる（＝ポート番号が違う）ので下記ポートを実機に合わせる。

 【要確認: 実機の USRP ポート】
   下記 USRP_RX_PORT は DVSwitch の一般的な既定値 34001 を入れてある。
   実機の値を必ず確認して合わせること:
       grep -nA6 '^\[USRP\]' /opt/Analog_Bridge/Analog_Bridge.ini
   Analog_Bridge は「address:txPort」へ復号RX音声を送る。よって Web 側は
   その txPort を bind する（＝ USRP_RX_PORT に txPort を入れる）。

 USRP 音声パケット仕様（本コードが解釈する範囲）:
   先頭32バイト固定ヘッダ:
     [0:4]   'USRP'（マジック）
     [4:8]   seq      (uint32 BE)
     [8:12]  memory   (uint32 BE)
     [12:16] keyup/PTT(uint32 BE)   1=送信中, 0=PTT断
     [16:20] talkgroup(uint32 BE)
     [20:24] type     (uint32 BE)   0=音声(USRP_TYPE_VOICE)
     [24:28] mpxid    (uint32 BE)
     [28:32] reserved (uint32 BE)
   type==0 のとき、ヘッダ直後に 160 サンプル(=320バイト)の
   16bit 符号付きリトルエンディアン PCM, 8kHz, モノラル が続く。
   本コードは type==0 の音声ペイロードのみブラウザへ転送する。

 依存:
   pip3 install aiohttp
   （標準の同期 Flask では連続ストリーミング＋WS＋TLS が扱いにくいため、
    このサービスは app.py とは別プロセス・別ポートで独立させる。
    ダッシュボード app.py 側にはリンクを1つ足すだけで済む＝最小改修。）

 起動例:
   python3 usrp_web.py \
       --cert /opt/dvswitch_bot/web/certs/usrpweb.crt \
       --key  /opt/dvswitch_bot/web/certs/usrpweb.key
   ブラウザで  https://<node-ip>:8443/  を開き「接続」を押す。

 変更履歴:
   V0.1  初版（フェーズ1: RX モニタのみ / HTTPS / WebSocket ブロードキャスト）
   V0.2  🔴 受信ゼロ不具合を修正。web.run_app() が自前の新規イベントループを回す
         ため、main() 内で run_until_complete により先に生成した UDP エンドポイントが
         別ループに取り残され datagram_received が発火しなかった（カーネル側の
         Recv-Q には溜まるがアプリの packets が 0 のまま）。UDP 生成を aiohttp の
         on_startup（＝実際にサービスを回すループ）へ移動して解消。
         あわせて --verbose を追加（WS 接続/切断と受信パケットをコンソールに出力）。
   V0.3  🔵 応答音声ミラー対応。Analog_Bridge の復号RX(51001)には bot 自身の
         応答音声が現れない（bot の音は 51000→送信の一方向で、この構成では
         ループバックしない実測結果）。そこで bot 側(dvswitch_bot.py V2.06jtw〜)が
         応答 USRP パケットを複製送信するミラーポート(既定 51002)を追加受信できる
         ように、--mirror-port を新設。51001 と 51002 の両方を listen し、同一ハブへ
         流して同じブラウザで混ぜて鳴らす。--mirror-port 0（既定）でミラー無効。
   V0.4  🔵 案A（ミックスせず優先1本化）。V0.3 は 51001 と 51002 を単純合流して
         いたため、送受信の輻輳で両系統が同時に来ると1本のWSへ倍レートで流れ込み、
         ブラウザの再生キューが伸びて「再生が半速化」する不具合があった。
         51002(priority=bot応答) を最優先とし、priority 受信中はホールド期間
         (PRIORITY_HOLD_SEC) だけ 51001(rx=他局受信) を捨てて合流させない。
         これで常に1系統ぶんのレートになり半速化しない。あわせて priority
         セッション先頭の PRIORITY_LEAD_SKIP パケットを再生スキップし、bot が
         RF 対策で入れる先頭 100Hz 微小トーンがミラーで「ブブッ」と鳴るのを抑制
         （RF側の対策は無改修のまま／bot・ブラウザ側も無改修、本ファイルのみで完結）。
   V0.5  🔵 常時「プツプツ」を解消（再生側のみ・サーバ/bot 無改修）。V0.4 までは
         20ms ごとの 8kHz 小バッファを個別に AudioBuffer 化して並べていたため、
         ブラウザが各バッファを独立に出力レートへリサンプルし、境界で波形が不連続に
         なってクリック（プツプツ）が出ていた。届いた PCM をリングバッファに貯め、
         1本の連続再生ノードから線形補間で「連続」リサンプルして読み出す方式へ変更。
         境界クリックが消え、プリバッファも 120→240ms に深くして到着ジッタを吸収する。
   V0.6  🔵 「プツプツ」が V0.5 でも残るため、再生を AudioWorklet（音声専用スレッド）へ
         変更。V0.5 の createScriptProcessor はメインスレッド動作で、GC や UI 負荷で
         コールバックが遅延すると途切れが出た。worklet はメインスレッドから独立して
         動くため途切れにくい。リング/線形補間の連続リサンプルは踏襲。AudioWorklet
         非対応環境のみ ScriptProcessor へ自動フォールバック（サーバ/bot は無改修）。
   V0.7  🔵 語頭（無音→発話）でのプツッを解消。V0.6 まではアンダーラン時に
         readPos を writeCount へジャンプさせており、その位置不連続が語頭で段差
         （クリック）になっていた（他局受信・bot応答の両方で発生）。V0.7 では
         アンダーラン時に位置ジャンプせず読み位置を据え置き、直前サンプルを保持
         しつつ約5msのエンベロープで無音へフェード／復帰時フェードインして段差を
         丸める。枯渇後の再プリバッファは 80ms と浅めにして語頭遅延を抑える。
         worklet・ScriptProcessor 両経路に適用（サーバ/bot は無改修）。
   V0.8  🔵 セッションの立ち上がり（プリバッファ枯渇→受信再開）で出る「bububu」を抑制。
         V0.7 はフェードイン/アウトが共通5msで、立ち上がりが急すぎて再開時に
         ガサつきが出ていた。フェードインを 40ms に緩め（アウトは 5ms 据え置きで
         終端の切れは保持）、再プリバッファを 80→120ms に深くして、立ち上がり直後に
         浅すぎて即アンダーラン→再立ち上がりを繰り返す bububu を防ぐ。
         worklet・ScriptProcessor 両経路に適用（サーバ/bot は無改修）。
   V0.9  🔵 案X。rx↔priority の切り替わりで出ていた bububu を根治。実測ログで
         rx(他局受信) と priority(bot応答) はほぼ重ならず順次に来ることが判明した
         ため、V0.4 の「優先ホールドで一方を捨てる」方式を撤去し、両ポートを1本の
         ストリームとして順に合流させる。切り替わりでバッファがリセット→再立ち上がり
         する（bububu の原因）が無くなる。ミラー先頭トーンのスキップは維持。
         再生側の連続化・フェード（V0.5〜V0.8）はそのまま（サーバ/bot は無改修）。
   V0.10 🔵 受信開始（rx=51001 の新セッション先頭）で Web でのみ出る bububu を抑制。
         無線機では出ず Web だけで出ることから、送信立ち上がり（PTTオン→同期→音声が
         乗るまで）のガサつきが再生の初回立ち上がりと重なって耳につくと判断。先頭
         スキップを role ごとに一般化し、rx に 3（=60ms）を追加（priority は従来 8）。
         DMR 実音声の頭は残るため頭欠けしにくく、フェードイン(40ms)と併用で丸める。
         スキップ数は LEAD_SKIP で調整可（サーバ受信ロジックのみ／bot は無改修）。
   V0.11 🔵 診断モード --diag を追加（既定動作は不変）。bot応答(51002)は正常なのに
         他局受信(51001)だけ受信開始で bububu が残るため、51001 に実際に届く先頭
         パケットの中身（長さ/type/keyup/振幅peak/先頭サンプル）を可視化して、
         壊れフレーム・巨大段差・長さ乱れのいずれかを数値で特定できるようにする。
         --diag 指定時は各セッション先頭 DIAG_LEAD 個の素性を [diag:role] 行で出力。
   V0.12 🔴 bububu/バリバリの根治。--diag の実測により、壊れたセッションでは
         Analog_Bridge が「同一の大振幅フレーム」（例 head=[554,-27129,-13090,...]
         peak=27129）を延々リピート送出していることが判明した（正常音声は毎フレーム
         波形が異なり peak も小さい）。この壊れリピートがブラウザで bububu/バリバリ/
         ブーンとして鳴っていた。対策: 直前フレームとバイト完全一致するフレームを
         壊れリピートとして破棄する（連続重複フレーム除去）。完全ゼロ(無音)は正常な
         無音送出があり得るため例外として通す。正常音声が完全一致することは実質なく
         誤検出しない。破棄数は [dup:role] 行で確認できる（bot は無改修）。
   V0.13 🔴 V0.12 の取りこぼし修正。実測ログで、壊れフレームは「先頭の大振幅
         パターン [554,-27129,-13090,140,...] は毎回同一だが末尾数サンプルだけ
         揺れる」ことが判明し、バイト完全一致判定では x1 しか落ちず bububu が
         残った。判定を「フレーム先頭 DUP_HEAD_BYTES(16B=8サンプル) の一致」に
         変更し、末尾が揺れる壊れフレームも全て破棄する。正常音声は毎フレーム
         波形が異なり先頭8サンプルまで連続一致しないため誤検出しない。
         先頭が無音(全ゼロ)のフレームは正常として除外（bot は無改修）。
   V0.14 🔴 V0.13 の取りこぼし修正（実測第2弾）。壊れフレームの固定部は先頭
         4サンプル [554,-27129,-13090,140] のみで、5サンプル目以降は既に揺れて
         おり、16B=8サンプル一致では大半が素通りしていた（12連発中 x1 のみ破棄）。
         比較長を 8B=4サンプルへ短縮し、あわせて誤検出防止のため「先頭に大振幅
         サンプル(>DUP_MIN_PEAK=5000)を含む」を AND 条件に追加。壊れフレーム
         (peak≈27000)は確実に落ち、正常音声の静音部は偶然一致しても通る。
         （bot は無改修）
   V0.15 🔵 語頭切れ修正＋こもり軽減（再生JSのみ／サーバ・bot 無改修）。
         (1) 語頭切れ:「ジェイ・ジェイ」の2音目が半分欠ける症状は、語間の短い
         無音でバッファが枯れるたびに再プリバッファ(120ms)を貯め直し、その間に
         次の語頭を消費していたのが原因。再プリバッファを廃止し、枯れても読み
         位置据え置きのままデータ到着で即フェードイン復帰する方式へ変更（プリ
         バッファは初回接続時の1回のみ）。フェードインも 40ms→10ms に短縮
         （初回 bububu は V0.14 の壊れフレーム破棄で根治済みのため不要）。
         (2) こもり軽減: 1次ハイシェルフ相当の高域ブースト（差分加算, HF_BOOST=0.8,
         カットオフ約1.2kHz）を追加。8kHz 音源の帯域は増やせないが、体感の明瞭度を
         改善する。HF_BOOST=0 で原音に戻せる。worklet/フォールバック両対応。
 V0.16: 版情報パネルを追加。ページ冒頭に本モニタ・bot・voice_make・dashboard の
         現在版を表示する（/status の "versions" と、ページ読込時の1回取得で描画）。
         版はノード上の実ファイル（bin/dvswitch_bot.py 等）から起動時＋60秒TTLで
         読み直すため、bot を更新すればリロードで新版が映る。音声経路は不変更。
================================================================================
"""

__version__ = "V0.3tx"

import argparse
import array
import asyncio
import ssl
import re
import socket
import struct
import sys
import time
from collections import deque

try:
    from aiohttp import web, WSMsgType
except Exception as e:  # noqa: BLE001
    sys.stderr.write(
        "ERROR: aiohttp が見つかりません。'pip3 install aiohttp' を実行してください。\n"
        f"詳細: {e}\n"
    )
    sys.exit(1)

# ----------------------------------------------------------------------------
# 設定（必要に応じて起動引数で上書き可）
# ----------------------------------------------------------------------------
USRP_RX_ADDR = "0.0.0.0"     # bind するローカルアドレス（通常このまま）
USRP_RX_PORT = 34001         # ★実機の Analog_Bridge.ini [USRP] txPort に合わせる
WEB_HOST     = "0.0.0.0"     # ダッシュボードを LAN 全体へ出す
WEB_PORT     = 8443          # HTTPS ポート（app.py の 8081 とは別）

# 🔵 V0.16: 版情報パネル用 — ノード上の関連ファイルから版を読む
BOT_PY = "/opt/dvswitch_bot/bin/dvswitch_bot.py"
VMP_PY = "/opt/dvswitch_bot/bin/voice_make.py"
APP_PY = "/opt/dvswitch_bot/web/app.py"
_VERS_TTL_SEC = 60.0
_vers_cache = {"at": 0.0, "data": {}}


def _read_version_line(path, patterns):
    """path の先頭 20KB から patterns（正規表現リスト）の最初の一致を返す。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head = f.read(20000)
        for pat in patterns:
            m = re.search(pat, head, re.M)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "—"


def _collect_versions():
    """monitor / bot / voice_make / dashboard の版を dict で返す（60秒キャッシュ）。"""
    now = time.monotonic()
    if now - _vers_cache["at"] < _VERS_TTL_SEC and _vers_cache["data"]:
        return _vers_cache["data"]
    data = {
        "monitor": __version__,
        "bot": _read_version_line(BOT_PY, [r'^__version__ = "(V[^"]+)"']),
        "voice_make": _read_version_line(VMP_PY, [r'^__version__ = "(V[^"]+)"']),
        "dashboard": _read_version_line(APP_PY, [r'app\.py\s+(V[\d.]+[a-z]*)',
                                                 r'^__version__ = "(V[^"]+)"']),
    }
    _vers_cache.update(at=now, data=data)
    return data


# USRP 音声パケット定数
USRP_MAGIC     = b"USRP"
USRP_HDR_LEN   = 32
USRP_TYPE_VOICE = 0

# 🔵 V0.1tx: 送信（TX）— ブラウザのマイク音声を USRP パケットにして
# Analog_Bridge の rxPort へ送る。pyUC が喋るのと同じ層（bot のログ監視とは別系統）。
# 免許人＝アマチュア無線技士が操作する性善説の前提。カーチャンク自動応答が
# 返るのは想定内の正常動作。
TX_DEST_ADDR = "127.0.0.1"
TX_DEST_PORT = 51000          # ★Analog_Bridge.ini [USRP] rxPort（送信の宛先）
TX_SAMPLES   = 160            # 20ms @ 8kHz（受信と同じ粒度）
TX_WATCHDOG_SEC = 2.0         # この秒数マイク音声が途絶えたら自動終端（送信しっぱなし防止）


class UsrpTx:
    """WS から届く 8kHz/16bit/mono PCM を USRP 音声パケット化して送出する。
    PTT ON で keyup=1 の音声パケットを連続送出、PTT OFF で keyup=0 の
    終端パケットを1つ送る。ストリーム識別の seq はセッション毎に単調増加。"""
    def __init__(self, addr=TX_DEST_ADDR, port=TX_DEST_PORT):
        self.addr, self.port = addr, port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = 0
        self.active = False
        self._last_audio = 0.0

    def _packet(self, pcm160: bytes, keyup: int) -> bytes:
        # ヘッダ: 'USRP' + seq + memory(0) + keyup + talkgroup(0) + type + mpxid(0) + reserved(0)
        hdr = struct.pack("!4sIIIIIII", USRP_MAGIC, self.seq, 0, keyup, 0, USRP_TYPE_VOICE, 0, 0)
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        return hdr + pcm160

    def _watchdog_check(self):
        """最後の音声から TX_WATCHDOG_SEC 以上途絶えたら自動で終端（送信しっぱなし防止）。"""
        import time as _t
        if self.active and (_t.monotonic() - self._last_audio) > TX_WATCHDOG_SEC:
            self.end_tx()
            return True
        return False

    def send_audio(self, pcm160: bytes):
        import time as _t
        self._last_audio = _t.monotonic()
        # 160サンプル(320バイト)に満たない/超える場合はパディング/切り詰め
        if len(pcm160) < TX_SAMPLES * 2:
            pcm160 = pcm160 + b"\x00" * (TX_SAMPLES * 2 - len(pcm160))
        elif len(pcm160) > TX_SAMPLES * 2:
            pcm160 = pcm160[:TX_SAMPLES * 2]
        self.active = True
        self.sock.sendto(self._packet(pcm160, 1), (self.addr, self.port))

    def end_tx(self):
        # 終端（keyup=0）。無音1パケットを送って PTT オフを通知。
        self.sock.sendto(self._packet(b"\x00" * (TX_SAMPLES * 2), 0), (self.addr, self.port))
        self.active = False
# 1クライアントあたりの音声キュー上限（超過分は捨ててレイテンシ肥大を防ぐ）
CLIENT_QUEUE_MAX = 50

# 🔵 V0.9: 案X（rx/priority を区別せず1本のストリームとして順に流す）。
# 実測ログで rx(他局受信) と priority(bot応答) はほぼ重ならず順次に来ることが
# 分かったため、V0.4 の「優先ホールドで一方を捨てる」方式をやめて単純合流に戻す。
# これにより rx↔priority の切り替わりでバッファがリセットされ再立ち上がりする
# （＝bububu の原因）が無くなる。再生側の連続化・フェード（V0.5〜V0.8）は維持。
#
# 🔵 V0.10: 受信開始（新セッション先頭）の数パケットを role ごとにスキップする。
# priority(51002/bot応答): 先頭 100Hz 対策トーンを消すため 8（=トーン5＋余裕）。
# rx(51001/他局受信): 送信立ち上がり（PTTオン→同期→音声が乗るまで）のガサつき
#   （Web 再生でのみ耳につく bububu）を抑えるため 3（=60ms）と控えめに。DMR の
#   実音声の頭は残るためこの程度なら頭欠けしにくい。フェードイン(40ms)と併用する。
SESSION_GAP_SEC = 0.5        # この秒数途切れたら「新しいセッション」とみなし先頭スキップを再セット
LEAD_SKIP = {"rx": 3, "priority": 8}   # role ごとの先頭スキップ数（パケット, 1個=20ms）

# 🔵 V0.12〜V0.14: 壊れリピート除去の判定用定数。
# 実測の壊れフレームは先頭4サンプル [554,-27129,-13090,140] が固定で、5サンプル目
# 以降はすでに揺れている（V0.13 の 16B=8サンプル一致では取りこぼした）。
# 判定は「先頭 DUP_HEAD_BYTES(8B=4サンプル) が直前フレームと一致」かつ
# 「フレームの先頭に大振幅サンプル(絶対値 > DUP_MIN_PEAK)を含む」の AND とする。
# 大振幅条件により、正常音声の静音部で先頭が偶然一致しても誤破棄しない
# （壊れフレームは peak≈27000 と巨大なので確実に引っかかる）。
DUP_HEAD_BYTES = 8
DUP_MIN_PEAK   = 5000
_SILENCE_HEAD = b"\x00" * DUP_HEAD_BYTES   # 先頭が無音のフレームは正常として通す

# --verbose 時のコンソール出力
VERBOSE = False
# 🔵 V0.11: --diag。各セッション先頭の数パケットの中身（長さ/type/keyup/振幅/先頭サンプル）を
# 出して、51001(rx) の受信開始で出る bububu の正体（壊れフレーム/巨大段差/長さ乱れ）を特定する。
DIAG = False
DIAG_LEAD = 12   # 各セッション先頭で診断出力するパケット数

def vlog(msg: str):
    if VERBOSE:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

# ----------------------------------------------------------------------------
# 受信音声を全 WebSocket クライアントへ配るハブ
# ----------------------------------------------------------------------------
class AudioHub:
    def __init__(self):
        # 各クライアント = asyncio.Queue（音声 bytes を積む）
        self.clients = set()
        self.pkt_count = 0
        self.last_keyup = 0
        # 🔵 V0.10: role ごとの先頭スキップ状態（rx / priority 個別）
        self._last_ts = {"rx": 0.0, "priority": 0.0}   # role ごとの直近受信時刻
        self._skip = {"rx": 0, "priority": 0}          # role ごとの残りスキップ数
        # 🔵 V0.12/V0.13: 壊れリピート除去（Analog_Bridge が先頭に固定の壊れ
        # パターンを持つフレームを連発する事象への対策）の状態
        self._last_audio = {"rx": None, "priority": None}  # role ごとの直前フレーム先頭(DUP_HEAD_BYTES)
        self._dup_count = {"rx": 0, "priority": 0}         # 連続重複の観測数（ログ用）

    def register(self):
        q = asyncio.Queue(maxsize=CLIENT_QUEUE_MAX)
        self.clients.add(q)
        return q

    def unregister(self, q):
        self.clients.discard(q)

    def feed(self, role: str, audio: bytes, keyup: int):
        """🔵 V0.10 案X: rx(51001)/priority(51002) を1本のストリームとして順に流す。
        各 role の新セッション先頭を LEAD_SKIP[role] 個だけスキップして、受信開始の
        ガサつき（rx）と 100Hz 対策トーン（priority）を抑える。頭欠けを避けるため
        rx のスキップは控えめ。戻り値: 実際にブラウザへ流したら True。

        🔵 V0.12: 連続重複フレーム除去。--diag の実測で、Analog_Bridge が壊れた
        セッションでは「同一の大振幅フレーム」を延々リピート送出することが判明
        （bububu/バリバリの正体）。正常音声は毎フレーム波形が異なるため、直前と
        バイト完全一致するフレームは壊れリピートとして破棄する。完全ゼロ(無音)は
        正常な無音送出があり得るため除外して通す。"""
        now = time.monotonic()
        # 新しいセッションの立ち上がり検出 → 先頭スキップと重複状態を再セット
        if now - self._last_ts.get(role, 0.0) > SESSION_GAP_SEC:
            self._skip[role] = LEAD_SKIP.get(role, 0)
            if self._dup_count.get(role, 0) > 0:
                vlog(f"[dup:{role}] previous session dropped {self._dup_count[role]} duplicated frames")
            self._last_audio[role] = None
            self._dup_count[role] = 0
        self._last_ts[role] = now

        # 🔵 V0.14: 壊れリピート判定＝「先頭 DUP_HEAD_BYTES 一致」かつ「先頭に
        # 大振幅サンプルを含む」。先頭4サンプルの固定壊れパターンを狙い撃ちしつつ、
        # 大振幅条件で正常音声の静音部での偶然一致を除外する。
        head = audio[:DUP_HEAD_BYTES]
        if head == self._last_audio.get(role) and head != _SILENCE_HEAD:
            hs = array.array("h")
            hs.frombytes(head)
            if sys.byteorder == "big":
                hs.byteswap()
            if hs and max(abs(x) for x in hs) > DUP_MIN_PEAK:
                self._dup_count[role] = self._dup_count.get(role, 0) + 1
                if self._dup_count[role] in (1, 50, 250, 1000):   # 抑制ぎみにログ
                    vlog(f"[dup:{role}] duplicated frame dropped (x{self._dup_count[role]})")
                return False
        self._last_audio[role] = head

        if self._skip.get(role, 0) > 0:
            self._skip[role] -= 1
            return False  # 先頭の数パケットは流さない
        self._broadcast(audio, keyup)
        return True

    def _broadcast(self, audio: bytes, keyup: int):
        self.last_keyup = keyup
        for q in self.clients:
            if q.full():
                # 詰まっているクライアントは古いフレームを1つ捨てて最新を優先
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(audio)
            except asyncio.QueueFull:
                pass


# ----------------------------------------------------------------------------
# Analog_Bridge からの USRP UDP を受ける asyncio プロトコル
# ----------------------------------------------------------------------------
class USRPReceiver(asyncio.DatagramProtocol):
    def __init__(self, hub: AudioHub, role: str = "rx"):
        self.hub = hub
        self.role = role            # "rx"(51001) / "priority"(51002)
        self._first_logged = False
        self._diag_last_ts = 0.0    # 🔵 V0.11: 診断用セッション判定
        self._diag_remaining = 0
        self._diag_seq = 0

    def datagram_received(self, data: bytes, addr):
        # 🔵 V0.11: 診断は type フィルタより前に全パケットを見る（非音声も可視化）
        if DIAG:
            now = time.monotonic()
            if now - self._diag_last_ts > SESSION_GAP_SEC:
                self._diag_remaining = DIAG_LEAD
                self._diag_seq = 0
                vlog(f"[diag:{self.role}] --- new session ---")
            self._diag_last_ts = now
            if self._diag_remaining > 0:
                self._diag_remaining -= 1
                self._diag_seq += 1
                self._diag_dump(data, addr, self._diag_seq)

        if len(data) < USRP_HDR_LEN + 2:
            return
        if data[:4] != USRP_MAGIC:
            return
        ptype = struct.unpack(">I", data[20:24])[0]
        if ptype != USRP_TYPE_VOICE:
            return
        keyup = struct.unpack(">I", data[12:16])[0]
        audio = data[USRP_HDR_LEN:]
        if not audio:
            return
        if not self._first_logged:
            self._first_logged = True
            vlog(f"[rx:{self.role}] first voice packet from {addr[0]}:{addr[1]} "
                 f"({len(audio)} bytes, keyup={keyup})")
        self.hub.pkt_count += 1
        played = self.hub.feed(self.role, audio, keyup)
        if VERBOSE and self.hub.pkt_count % 50 == 0:
            vlog(f"[rx:{self.role}] packets={self.hub.pkt_count} keyup={keyup} "
                 f"played={played} clients={len(self.hub.clients)}")

    def _diag_dump(self, data: bytes, addr, k: int):
        """1パケットの素性を数値化して出す（先頭数個のみ）。"""
        n = len(data)
        magic = data[:4] == USRP_MAGIC
        ptype = keyup = -1
        if n >= USRP_HDR_LEN:
            ptype = struct.unpack(">I", data[20:24])[0]
            keyup = struct.unpack(">I", data[12:16])[0]
        audio = data[USRP_HDR_LEN:] if n >= USRP_HDR_LEN else b""
        alen = len(audio)
        peak = 0
        head = []
        if alen >= 2:
            samp = array.array("h")
            samp.frombytes(audio[:(alen // 2) * 2])
            if sys.byteorder == "big":
                samp.byteswap()  # USRP 音声は 16bit LE
            if samp:
                peak = max(abs(x) for x in samp)
                head = list(samp[:6])
        vlog(f"[diag:{self.role}] #{k:2d} src={addr[1]} len={n} audio={alen} "
             f"magic={int(magic)} type={ptype} keyup={keyup} peak={peak} head={head}")

    def error_received(self, exc):
        sys.stderr.write(f"[usrp] UDP error: {exc}\n")


# ----------------------------------------------------------------------------
# WebSocket ハンドラ（サーバ→ブラウザへ音声 bytes を送り続ける）
# ----------------------------------------------------------------------------
async def ws_handler(request: web.Request):
    hub: AudioHub = request.app["hub"]
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    q = hub.register()
    vlog(f"[ws] client connected  (clients={len(hub.clients)})")
    try:
        async def pump():
            while True:
                audio = await q.get()
                if ws.closed:
                    break
                await ws.send_bytes(audio)

        pump_task = asyncio.ensure_future(pump())

        async def tx_watchdog():
            # 🔵 V0.3tx: 200ms 毎に「音声が途絶えたのに送信中」を検出して自動終端。
            _tx = request.app.get("tx")
            if _tx is None:
                return
            while True:
                await asyncio.sleep(0.2)
                if _tx._watchdog_check():
                    vlog("[tx] ウォッチドッグ: 音声途絶により自動終端")
        wd_task = asyncio.ensure_future(tx_watchdog())
        # クライアントからのメッセージ: バイナリ=マイクPCM(TX)、テキスト=PTT制御
        tx: UsrpTx = request.app.get("tx")
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                # ブラウザで 8kHz/16bit/mono にリサンプル済みの PCM。160サンプル単位。
                if tx is not None:
                    for off in range(0, len(msg.data), TX_SAMPLES * 2):
                        tx.send_audio(msg.data[off:off + TX_SAMPLES * 2])
            elif msg.type == WSMsgType.TEXT:
                if msg.data == "ptt:off" and tx is not None:
                    tx.end_tx()
                    vlog("[tx] PTT off (end of transmission)")
                elif msg.data == "ptt:on":
                    vlog("[tx] PTT on")
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
        # 🔵 V0.3tx: WS が閉じたら送信中でも必ず終端を出す（送信しっぱなし防止）
        if tx is not None and tx.active:
            tx.end_tx()
            vlog("[tx] WS 切断により強制終端")
        pump_task.cancel()
        wd_task.cancel()
    finally:
        hub.unregister(q)
        vlog(f"[ws] client disconnected (clients={len(hub.clients)})")
    return ws


async def status_handler(request: web.Request):
    hub: AudioHub = request.app["hub"]
    return web.json_response({
        "version": __version__,
        "versions": _collect_versions(),
        "tx_enabled": request.app.get("tx") is not None,
        "tx_dest": f"{TX_DEST_ADDR}:{TX_DEST_PORT}" if request.app.get("tx") else None,
        "clients": len(hub.clients),
        "packets": hub.pkt_count,
        "last_keyup": hub.last_keyup,
        "usrp_port": USRP_RX_PORT,
    })


# ----------------------------------------------------------------------------
# ブラウザ側ページ（Web Audio API で 8kHz PCM を再生）
#   ※ app.py のダッシュボード配色（bg #fafafa / accent #b44010）に合わせてある
# ----------------------------------------------------------------------------
INDEX_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenCCVoice USRP Web — RX モニタ</title>
<style>
  body{font-family:Arial,"Noto Sans JP",sans-serif;background:#fafafa;color:#222;
       margin:0;padding:20px;}
  .card{max-width:520px;margin:0 auto;background:#f8f8f8;border-radius:10px;
        box-shadow:0 0 8px #999;padding:18px 20px;}
  h1{font-size:16px;margin:0 0 4px;color:#b44010;}
  .sub{font-size:11px;color:#777;margin:0 0 14px;}
  .row{display:flex;align-items:center;gap:12px;margin:10px 0;}
  button{font-family:inherit;font-size:13px;padding:8px 18px;border:1px solid #b44010;
         background:#b44010;color:#fff;border-radius:6px;cursor:pointer;}
  button.off{background:#fff;color:#b44010;}
  button:disabled{opacity:.5;cursor:default;}
  .pill{font-size:12px;padding:3px 10px;border-radius:12px;background:#ddd;color:#333;}
  .pill.live{background:#12AD2A;color:#fff;}
  .pill.busy{background:#b44010;color:#fff;}
  label{font-size:12px;color:#444;}
  input[type=range]{vertical-align:middle;}
  .stat{font-size:11px;color:#666;margin-top:12px;line-height:1.6;}
  code{background:#eee;padding:1px 4px;border-radius:3px;}
</style>
</head>
<body>
<div class="card">
  <h1>USRP Web — 受信モニタ</h1>
  <p class="sub">Analog_Bridge の復号RX音声をブラウザで再生（フェーズ1: 受信のみ）</p>
  <p class="sub" id="vers" style="color:#888;">versions: 取得中…</p>

  <div class="row">
    <button id="btn" class="off">接続</button>
    <span id="state" class="pill">未接続</span>
  </div>

  <div class="row">
    <label for="vol">音量</label>
    <input id="vol" type="range" min="0" max="200" value="100">
    <span id="volval" style="font-size:12px;color:#444;width:40px;">100%</span>
  </div>

  <div class="stat" id="stat">
    受信パケット: 0 ／ ジッタバッファ: 240ms<br>
    <span style="color:#999;">※ 初回は「接続」ボタン押下（ブラウザの自動再生制限のため）</span>
  </p>
  <div id="txpanel" style="display:none; margin-top:14px; padding-top:12px; border-top:1px solid #eee;">
    <p class="sub" style="margin:0 0 8px;">送信（TX）— マイク音声を rxPort へ / 免許人操作前提・応答が返るのは正常</p>
    <button id="pttBtn" class="off" style="min-width:150px;">🎤 PTT（押している間）</button>
    <label style="margin-left:14px;"><input type="checkbox" id="pttToggle"> トグル送信</label>
    <span id="txstate" class="pill">送信待機</span>
  </p>
  <p>
  </div>
</div>

<script>
// ============================================================
// 🔵 V0.6: AudioWorklet による連続再生（音声専用スレッド）
// ------------------------------------------------------------
// V0.5 は createScriptProcessor（メインスレッド動作・非推奨）を使っており、
// GC や UI 負荷でコールバックが遅延すると音が途切れ「プツプツ」が残った。
// V0.6 では音声専用スレッドで動く AudioWorklet に切り替える。届いた PCM を
// worklet 内リングに貯め、process() が出力レートで線形補間の連続リサンプルを
// して読み出す。メインスレッドの負荷から独立するため途切れにくい。
// AudioWorklet 非対応環境のみ、従来の ScriptProcessor へフォールバックする。
// ============================================================
const SR = 8000;                 // USRP 音声は 8kHz モノラル
const PREBUFFER_SEC = 0.24;      // ジッタバッファ 240ms
const RING_CAP = SR * 8;         // リング容量 8 秒ぶん（フォールバック用）
// 🔵 V0.15: 高域ブースト量（こもり軽減）。0=無効(原音), 0.8=既定。
// 効きすぎ（シャリつく）なら 0.5、物足りなければ 1.2 程度まで。
const HF_BOOST = 0.8;

let ac=null, ws=null, gain=null, node=null, running=false, pkts=0;
// フォールバック(ScriptProcessor)用の状態
let ring=null, writeCount=0, readPos=0, primed=false;

const btn   = document.getElementById('btn');
// ===== 🔵 V0.1tx: 送信(TX) =====
// ===== 🔵 V0.3tx: 送信(TX) 全面刷新 =====
// 設計: AudioContext とマイクは「初回に1回だけ」確保して使い回す。PTT は
// 送信フラグ txSending を切り替えるだけ（context を毎回 close しない＝再ONで
// 失敗しない）。マイク PCM の取り出しは AudioWorklet（音声専用スレッド）で
// 確実に行い、8kHz へ間引いて 160 サンプル単位で WS 送信する。
let txCtx=null, txStream=null, txWorklet=null, txReady=false, txSending=false;
const TX_SR = 8000;
function setTxState(t){ const e=document.getElementById('txstate'); if(e) e.textContent=t; }

// tx 有効ならパネル表示
fetch('/status').then(r=>r.json()).then(s=>{
  if(s.tx_enabled){ const p=document.getElementById('txpanel'); if(p) p.style.display='block'; }
});

// マイク送信用 AudioWorklet（マイク入力→8k間引き→160サンプルを main へ postMessage）
const TX_WORKLET_SRC = `
class TxCapture extends AudioWorkletProcessor {
  constructor(){
    super();
    this.sending = false;
    this.acc = 0;
    this.ratio = sampleRate / ${TX_SR};   // 例 48000/8000 = 6
    this.buf = [];
    this.port.onmessage = (e)=>{ if(e.data && 'sending' in e.data){ this.sending = e.data.sending; if(!this.sending) this.buf.length=0; } };
  }
  process(inputs){
    const ch = inputs[0][0];
    if(this.sending && ch){
      for(let i=0;i<ch.length;i++){
        this.acc++;
        if(this.acc >= this.ratio){ this.acc -= this.ratio;
          let v = Math.max(-1, Math.min(1, ch[i]));
          this.buf.push(v < 0 ? v*32768 : v*32767);
        }
      }
      while(this.buf.length >= 160){
        const chunk = this.buf.splice(0,160);
        const pcm = new Int16Array(chunk);
        this.port.postMessage(pcm.buffer, [pcm.buffer]);
      }
    }
    return true;
  }
}
registerProcessor('tx-capture', TxCapture);
`;

// 初回だけ: マイク許可 → AudioContext → Worklet を用意（以後使い回す）
async function txEnsureReady(){
  if(txReady) return true;
  if(!ws || ws.readyState!==1){ setTxState('先に「接続」を'); return false; }
  try{
    txStream = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
  }catch(e){ setTxState('マイク不可（許可/証明書を確認）'); return false; }
  try{
    txCtx = new (window.AudioContext||window.webkitAudioContext)();
    if(txCtx.state==='suspended'){ await txCtx.resume(); }
    const blob = new Blob([TX_WORKLET_SRC], {type:'application/javascript'});
    const url = URL.createObjectURL(blob);
    await txCtx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const srcNode = txCtx.createMediaStreamSource(txStream);
    txWorklet = new AudioWorkletNode(txCtx, 'tx-capture', {numberOfInputs:1, numberOfOutputs:0});
    txWorklet.port.onmessage = (ev)=>{ if(txSending && ws && ws.readyState===1) ws.send(ev.data); };
    srcNode.connect(txWorklet);   // 出力には繋がない（サイドトーン無し）
    txReady = true;
    return true;
  }catch(err){
    setTxState('初期化失敗: '+err.message);
    return false;
  }
}

async function txStart(){
  if(txSending) return;
  if(!(await txEnsureReady())) return;
  if(txCtx.state==='suspended'){ try{ await txCtx.resume(); }catch(e){} }
  txSending = true;
  txWorklet.port.postMessage({sending:true});
  if(ws && ws.readyState===1) ws.send('ptt:on');
  setTxState('🔴 送信中');
  const b=document.getElementById('pttBtn'); if(b) b.className='';
  // 送信中は受信再生をミュート（回り込み防止）
  if(typeof gain!=='undefined' && gain){ try{ gain.gain.value=0; }catch(e){} }
}

function txStop(){
  if(!txSending) return;
  txSending = false;
  if(txWorklet){ try{ txWorklet.port.postMessage({sending:false}); }catch(e){} }
  if(ws && ws.readyState===1) ws.send('ptt:off');
  setTxState('送信待機');
  const b=document.getElementById('pttBtn'); if(b) b.className='off';
  // 受信ミュート解除（マイク・context は閉じない＝再ONで即使える）
  if(typeof gain!=='undefined' && gain){ try{ gain.gain.value=(document.getElementById('vol')?document.getElementById('vol').value/100:1); }catch(e){} }
}

window.addEventListener('DOMContentLoaded',()=>{
  const pttBtn=document.getElementById('pttBtn');
  const pttToggle=document.getElementById('pttToggle');
  if(!pttBtn) return;
  // 押している間だけ（トグルOFF時）
  pttBtn.addEventListener('mousedown',()=>{ if(!pttToggle.checked) txStart(); });
  pttBtn.addEventListener('mouseup',  ()=>{ if(!pttToggle.checked) txStop(); });
  pttBtn.addEventListener('mouseleave',()=>{ if(!pttToggle.checked && txSending) txStop(); });
  pttBtn.addEventListener('touchstart',(e)=>{ e.preventDefault(); if(!pttToggle.checked) txStart(); });
  pttBtn.addEventListener('touchend',  (e)=>{ e.preventDefault(); if(!pttToggle.checked) txStop(); });
  // トグル時: クリックで ON/OFF
  pttBtn.addEventListener('click',()=>{ if(pttToggle.checked){ txSending?txStop():txStart(); } });
});
// 🔵 V0.16: 版情報パネル（読込時に1回取得。失敗しても音声機能に影響なし）
fetch('/status').then(r=>r.json()).then(s=>{
  const v = s.versions || {};
  document.getElementById('vers').textContent =
    `monitor ${v.monitor||'—'} ／ bot ${v.bot||'—'} ／ voice_make ${v.voice_make||'—'} ／ dashboard ${v.dashboard||'—'}`;
}).catch(()=>{ document.getElementById('vers').textContent = 'versions: 取得失敗'; });
const state = document.getElementById('state');
const stat  = document.getElementById('stat');
const vol   = document.getElementById('vol');
const volval= document.getElementById('volval');

function setState(txt, cls){ state.textContent=txt; state.className='pill'+(cls?(' '+cls):''); }

vol.addEventListener('input', ()=>{
  volval.textContent = vol.value+'%';
  if(gain) gain.gain.value = vol.value/100;
});

btn.addEventListener('click', async ()=>{
  if(!running){ await connect(); } else { disconnect(); }
});

// ---- AudioWorklet プロセッサのソース（Blob 経由で addModule する）----
const WORKLET_SRC = `
class USRPPlayer extends AudioWorkletProcessor {
  constructor(options){
    super();
    const o = (options && options.processorOptions) || {};
    this.SR = o.sr || 8000;
    this.prebuf = (o.prebufSec || 0.24) * this.SR;  // 初回接続時のみのプリバッファ
    this.cap = this.SR * 8;
    // 🔵 V0.17: 輻輳時の遅延累積対策（catch-up）。到着が束で遅れるとリングに
    // 音が溜まり、律儀に全部再生して遅延が最大8秒まで積み上がっていた。
    // 滞留(avail)が MAX_LAG を超えたら、読み位置を最新から TARGET_LAG の
    // 位置へジャンプさせて実時間に追いつく（古い音を捨てる）。モニタは
    // 実時間追従が正義なので、多少の欠けより遅延ゼロを優先する。
    this.maxLagSamp    = (o.maxLagSec    || 0.6) * this.SR;  // これ超で追いつき発動
    this.targetLagSamp = (o.targetLagSec || 0.24) * this.SR; // 追いつき後の残し量
    this.catchupCount = 0;
    this.ring = new Float32Array(this.cap);
    this.writeCount = 0;
    this.readPos = 0;
    this.primed = false;
    this.env = 0;          // 出力エンベロープ 0..1（段差を丸めるフェード）
    this.lastRaw = 0;      // 直前の補間サンプル（アンダーラン中の保持値）
    // 🔵 V0.15: フェードインを 10ms へ短縮。復帰待ち(再プリバッファ)を廃止した
    // ため、語間の短い枯れから即復帰する。40ms のままだと復帰のたびに語頭が
    // 薄くなるので短くする（初回立ち上がりの bububu は壊れフレーム破棄=V0.14 で
    // 根治済みのため、もう長いフェードに頼らない）。
    this.fadeInInc  = 1 / (0.010 * sampleRate);
    this.fadeOutInc = 1 / (0.005 * sampleRate);
    this.step = this.SR / sampleRate;          // sampleRate は worklet グローバル
    // 🔵 V0.15: 高域ブースト（1次ハイシェルフ相当）。8kHz 音源のこもり感を
    // 軽減する。y[n] = x[n] + HF_BOOST*(x[n]-lp[n]) で高域成分を足す。
    // lp は 1次ローパス（約1.2kHz）。HF_BOOST=0 で無効（原音）。
    this.hfBoost = (typeof o.hfBoost === 'number') ? o.hfBoost : 0.8;
    const fc = 1200;
    this.lpA = Math.exp(-2 * Math.PI * fc / sampleRate);
    this.lpState = 0;
    this.port.onmessage = (e)=>{
      // 🔵 V0.17: 制御メッセージ（{cmd:'flush'}）で読み書き位置を同期リセット。
      // 送信終了(keyup=0)時に呼ばれ、次の送信開始までに溜まった残渣を捨てる。
      if(e.data && e.data.cmd === 'flush'){
        this.readPos = this.writeCount;   // 追いつき（残さず捨てる）
        this.primed = false;              // 次の音は再プリバッファから
        return;
      }
      const i16 = new Int16Array(e.data);
      let w = this.writeCount;
      for(let i=0;i<i16.length;i++){ this.ring[w % this.cap] = i16[i] / 32768; w++; }
      this.writeCount = w;
    };
  }
  process(inputs, outputs){
    const out = outputs[0][0];
    if(!out) return true;
    // 🔵 V0.15: プリバッファは「初回接続時の1回だけ」。以降は枯れても貯め直さず、
    // データが来た瞬間にフェードインで即復帰する。従来は枯れるたびに 120ms
    // 貯め直しており、その間に語頭（「ジェイ・ジェイ」の2音目など）が食われて
    // 半分欠ける症状が出ていた。
    if(!this.primed){
      if((this.writeCount - this.readPos) >= this.prebuf){ this.primed = true; }
      else { out.fill(0); return true; }
    }
    // 🔵 V0.17: このブロックの処理を始める前に滞留を点検し、溜まりすぎていたら
    // 読み位置を最新-targetLag へ飛ばす（1ブロックに1回で十分）。
    {
      const lag = this.writeCount - this.readPos;
      if(lag > this.maxLagSamp){
        this.readPos = this.writeCount - this.targetLagSamp;
        this.catchupCount++;
        // 飛ばした直後の段差はエンベロープのフェードで吸収される
      }
    }
    for(let i=0;i<out.length;i++){
      const avail = this.writeCount - this.readPos;
      let raw;
      if(avail >= 2){
        const idx = Math.floor(this.readPos);
        const frac = this.readPos - idx;
        const s0 = this.ring[idx % this.cap];
        const s1 = this.ring[(idx+1) % this.cap];
        raw = s0 + (s1 - s0) * frac;
        this.lastRaw = raw;
        this.readPos += this.step;
        if(this.env < 1){ this.env = Math.min(1, this.env + this.fadeInInc); }   // 即時フェードイン復帰
      } else {
        // アンダーラン: 読み位置は据え置き・再プリバッファもしない。
        // 直前サンプルを保持しつつ 5ms で無音へフェードし、データが来たら
        // 上の分岐で即フェードイン再開する（語頭を食わない）。
        if(this.env > 0){ this.env = Math.max(0, this.env - this.fadeOutInc); }
        raw = this.lastRaw;
      }
      // 🔵 V0.15: 高域ブースト（こもり軽減）。エンベロープ適用前の raw に対して
      // 1次ローパスとの差分（高域）を足す。
      this.lpState = this.lpState * this.lpA + raw * (1 - this.lpA);
      const bright = raw + this.hfBoost * (raw - this.lpState);
      out[i] = bright * this.env;
    }
    return true;
  }
}
registerProcessor('usrp-player', USRPPlayer);
`;

async function connect(){
  ac = new (window.AudioContext||window.webkitAudioContext)();
  await ac.resume();
  gain = ac.createGain();
  gain.gain.value = vol.value/100;
  gain.connect(ac.destination);

  let useWorklet = !!(ac.audioWorklet);
  if(useWorklet){
    try{
      const blob = new Blob([WORKLET_SRC], {type:'application/javascript'});
      const url = URL.createObjectURL(blob);
      await ac.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      node = new AudioWorkletNode(ac, 'usrp-player', {
        numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [1],
        processorOptions: { sr: SR, prebufSec: PREBUFFER_SEC, hfBoost: HF_BOOST, maxLagSec: 0.6, targetLagSec: 0.24 }
      });
      node.connect(gain);
    }catch(err){
      console.warn('AudioWorklet 初期化失敗、ScriptProcessor へフォールバック:', err);
      useWorklet = false;
    }
  }
  if(!useWorklet){
    // ---- フォールバック: ScriptProcessor（worklet と同じフェード方式）----
    ring = new Float32Array(RING_CAP); writeCount=0; readPos=0; primed=false;
    let env=0, lastRaw=0, lpState=0;
    node = ac.createScriptProcessor(2048, 0, 1);
    const step = SR / ac.sampleRate;
    const fadeInInc  = 1 / (0.010 * ac.sampleRate);
    const fadeOutInc = 1 / (0.005 * ac.sampleRate);
    const prebufSamples = PREBUFFER_SEC * SR;
    const HF_BOOST = 0.8;
    // 🔵 V0.17: フォールバック側にも追いつき（worklet と同一方針）
    const maxLagSamp = 0.6 * SR, targetLagSamp = 0.24 * SR;
    const lpA = Math.exp(-2 * Math.PI * 1200 / ac.sampleRate);
    node.onaudioprocess = (e)=>{
      const out = e.outputBuffer.getChannelData(0);
      if(!primed){
        if((writeCount - readPos) >= prebufSamples){ primed = true; }
        else { out.fill(0); return; }
      }
      // 🔵 V0.17: 滞留しすぎたら読み位置を最新-targetへ飛ばす
      if((writeCount - readPos) > maxLagSamp){ readPos = writeCount - targetLagSamp; }
      for(let i=0;i<out.length;i++){
        const avail = writeCount - readPos;
        let raw;
        if(avail >= 2){
          const idx = Math.floor(readPos);
          const frac = readPos - idx;
          const s0 = ring[idx % RING_CAP];
          const s1 = ring[(idx+1) % RING_CAP];
          raw = s0 + (s1 - s0) * frac;
          lastRaw = raw;
          readPos += step;
          if(env < 1){ env = Math.min(1, env + fadeInInc); }
        } else {
          if(env > 0){ env = Math.max(0, env - fadeOutInc); }
          raw = lastRaw;
        }
        lpState = lpState * lpA + raw * (1 - lpA);
        out[i] = (raw + HF_BOOST * (raw - lpState)) * env;
      }
    };
    node.connect(gain);
  }

  const proto = location.protocol==='https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto+'://'+location.host+'/ws');
  ws.binaryType = 'arraybuffer';
  ws.onopen  = ()=>{ running=true; btn.textContent='切断'; btn.className=''; setState('接続中','live'); };
  ws.onclose = ()=>{ if(running){ setState('切断','busy'); } };
  ws.onerror = ()=>{ setState('エラー','busy'); };
  ws.onmessage = ev=>{
    pkts++;
    if(node && node.port){
      // Worklet: ArrayBuffer を転送（コピーなし）
      node.port.postMessage(ev.data, [ev.data]);
    } else {
      // フォールバック: メインスレッドのリングへ書く
      enqueue(ev.data);
    }
    updateStat();
  };
}

function disconnect(){
  running=false;
  if(ws){ ws.close(); ws=null; }
  if(node){ try{ node.disconnect(); }catch(e){} node=null; }
  if(ac){ ac.close(); ac=null; }
  ring=null; primed=false;
  btn.textContent='接続'; btn.className='off';
  setState('未接続','');
}

// フォールバック時のみ使用: 届いた 16bit PCM をメインスレッドのリングへ
function enqueue(arrbuf){
  const i16 = new Int16Array(arrbuf);
  for(let i=0;i<i16.length;i++){ ring[writeCount % RING_CAP] = i16[i] / 32768; writeCount++; }
}

function updateStat(){
  stat.innerHTML = '受信パケット: '+pkts+' ／ ジッタバッファ: 240ms';
}
</script>
</body>
</html>
"""


async def index_handler(request: web.Request):
    return web.Response(text=INDEX_HTML, content_type="text/html")


# ----------------------------------------------------------------------------
# 起動
# ----------------------------------------------------------------------------
def build_ssl(cert, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    return ctx


async def _on_startup(app: web.Application):
    # 🔴 V0.2: web.run_app() が回すループ上で UDP を生成する。
    # ここで作らないと datagram_received が発火しない（別ループ取り残し）。
    # 🔵 V0.3: RX(51001) に加え、ミラーポート(51002 等)も同じハブへ受ける。
    loop = asyncio.get_event_loop()
    app["udp_transports"] = []
    for label, port in app["listen_ports"]:
        role = "priority" if label == "mirror" else "rx"
        transport, _ = await loop.create_datagram_endpoint(
            lambda r=role: USRPReceiver(app["hub"], role=r),
            local_addr=(app["usrp_addr"], port),
        )
        app["udp_transports"].append(transport)
        vlog(f"[udp] endpoint ready on {app['usrp_addr']}:{port} ({label}/{role})")


async def _on_cleanup(app: web.Application):
    for t in app.get("udp_transports", []):
        t.close()


def main():
    global USRP_RX_ADDR, USRP_RX_PORT, WEB_HOST, WEB_PORT, VERBOSE, DIAG

    ap = argparse.ArgumentParser(description="OpenCCVoice USRP Web (phase1 RX)")
    ap.add_argument("--usrp-addr", default=USRP_RX_ADDR)
    ap.add_argument("--usrp-port", type=int, default=USRP_RX_PORT)
    ap.add_argument("--mirror-port", type=int, default=0,
                    help="bot 応答音声のミラー受信ポート（既定0=無効。例 51002）")
    ap.add_argument("--web-host", default=WEB_HOST)
    ap.add_argument("--web-port", type=int, default=WEB_PORT)
    ap.add_argument("--cert", required=True, help="TLS 証明書 (PEM)")
    ap.add_argument("--key", required=True, help="TLS 秘密鍵 (PEM)")
    ap.add_argument("--verbose", action="store_true",
                    help="WS 接続/切断と受信パケットをコンソールに出力")
    ap.add_argument("--tx", action="store_true",
                    help="送信(TX)機能を有効化。ブラウザのマイクを rxPort へ送出")
    ap.add_argument("--tx-port", type=int, default=TX_DEST_PORT,
                    help=f"送信の宛先ポート = Analog_Bridge [USRP] rxPort（既定 {TX_DEST_PORT}）")
    ap.add_argument("--tx-addr", default=TX_DEST_ADDR)
    ap.add_argument("--diag", action="store_true",
                    help="各セッション先頭パケットの中身(長さ/type/keyup/振幅/先頭サンプル)を出力")
    args = ap.parse_args()

    USRP_RX_ADDR, USRP_RX_PORT = args.usrp_addr, args.usrp_port
    WEB_HOST, WEB_PORT = args.web_host, args.web_port
    VERBOSE = args.verbose
    DIAG = args.diag
    if DIAG:
        VERBOSE = True   # 診断出力は vlog を使うため verbose を自動で有効化

    # listen するポート群（RX 本流＋任意でミラー）
    listen_ports = [("RX", USRP_RX_PORT)]
    if args.mirror_port and args.mirror_port != USRP_RX_PORT:
        listen_ports.append(("mirror", args.mirror_port))

    hub = AudioHub()

    app = web.Application()
    app["hub"] = hub
    # 🔵 V0.1tx: 送信器（--tx 指定時のみ）
    if args.tx:
        app["tx"] = UsrpTx(args.tx_addr, args.tx_port)
    else:
        app["tx"] = None
    app["usrp_addr"] = USRP_RX_ADDR
    app["usrp_port"] = USRP_RX_PORT
    app["listen_ports"] = listen_ports
    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/status", status_handler)
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    mirror_disp = str(args.mirror_port) if (args.mirror_port and args.mirror_port != USRP_RX_PORT) else "OFF"
    sys.stderr.write(
        f"usrp_web_tx.py {__version__}\n"
        f"  USRP RX listen : {USRP_RX_ADDR}:{USRP_RX_PORT} (Analog_Bridge txPort)\n"
        f"  mirror listen  : {mirror_disp} (bot 応答音声)\n"
        f"  Web HTTPS      : https://{WEB_HOST}:{WEB_PORT}/\n"
        f"  TX (送信)      : {('ON → ' + args.tx_addr + ':' + str(args.tx_port) + ' (rxPort)') if args.tx else 'OFF'}\n"
        f"  verbose        : {'ON' if VERBOSE else 'OFF'}\n"
    )

    ssl_ctx = build_ssl(args.cert, args.key)
    web.run_app(app, host=WEB_HOST, port=WEB_PORT, ssl_context=ssl_ctx, print=None)


if __name__ == "__main__":
    main()
