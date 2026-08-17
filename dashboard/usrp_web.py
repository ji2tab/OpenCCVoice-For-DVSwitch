#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 OpenCCVoice for DVSwitch  —  Web USRP クライアント
 usrp_web.py  V0.1   （フェーズ1: RX モニタのみ / bot 非干渉 / HTTPS）

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
================================================================================
"""

__version__ = "V0.1"

import argparse
import asyncio
import ssl
import struct
import sys
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

# USRP 音声パケット定数
USRP_MAGIC     = b"USRP"
USRP_HDR_LEN   = 32
USRP_TYPE_VOICE = 0
# 1クライアントあたりの音声キュー上限（超過分は捨ててレイテンシ肥大を防ぐ）
CLIENT_QUEUE_MAX = 50

# ----------------------------------------------------------------------------
# 受信音声を全 WebSocket クライアントへ配るハブ
# ----------------------------------------------------------------------------
class AudioHub:
    def __init__(self):
        # 各クライアント = asyncio.Queue（音声 bytes を積む）
        self.clients = set()
        self.pkt_count = 0
        self.last_keyup = 0

    def register(self):
        q = asyncio.Queue(maxsize=CLIENT_QUEUE_MAX)
        self.clients.add(q)
        return q

    def unregister(self, q):
        self.clients.discard(q)

    def broadcast(self, audio: bytes):
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
    def __init__(self, hub: AudioHub):
        self.hub = hub

    def datagram_received(self, data: bytes, addr):
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
        self.hub.pkt_count += 1
        self.hub.last_keyup = keyup
        self.hub.broadcast(audio)

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
    try:
        async def pump():
            while True:
                audio = await q.get()
                if ws.closed:
                    break
                await ws.send_bytes(audio)

        pump_task = asyncio.ensure_future(pump())
        # クライアントからのメッセージ（現状は close 検知のみ）
        async for msg in ws:
            if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
        pump_task.cancel()
    finally:
        hub.unregister(q)
    return ws


async def status_handler(request: web.Request):
    hub: AudioHub = request.app["hub"]
    return web.json_response({
        "version": __version__,
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
    受信パケット: 0 ／ ジッタバッファ: 120ms<br>
    <span style="color:#999;">※ 初回は「接続」ボタン押下（ブラウザの自動再生制限のため）</span>
  </div>
</div>

<script>
const SR = 8000;                 // USRP 音声は 8kHz モノラル
const TARGET_LATENCY = 0.12;     // ジッタバッファ 120ms
let ac=null, ws=null, gain=null, nextTime=0, running=false, pkts=0;

const btn   = document.getElementById('btn');
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

async function connect(){
  ac = new (window.AudioContext||window.webkitAudioContext)();
  await ac.resume();
  gain = ac.createGain();
  gain.gain.value = vol.value/100;
  gain.connect(ac.destination);
  nextTime = 0;

  const proto = location.protocol==='https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto+'://'+location.host+'/ws');
  ws.binaryType = 'arraybuffer';
  ws.onopen  = ()=>{ running=true; btn.textContent='切断'; btn.className=''; setState('接続中','live'); };
  ws.onclose = ()=>{ if(running){ setState('切断','busy'); } };
  ws.onerror = ()=>{ setState('エラー','busy'); };
  ws.onmessage = ev=>{ pkts++; playChunk(ev.data); updateStat(); };
}

function disconnect(){
  running=false;
  if(ws){ ws.close(); ws=null; }
  if(ac){ ac.close(); ac=null; }
  btn.textContent='接続'; btn.className='off';
  setState('未接続','');
}

function playChunk(arrbuf){
  const i16 = new Int16Array(arrbuf);
  const f32 = new Float32Array(i16.length);
  for(let i=0;i<i16.length;i++){ f32[i]=i16[i]/32768; }
  const buf = ac.createBuffer(1, f32.length, SR);   // 8kHz で作成→出力レートへ自動リサンプル
  buf.copyToChannel(f32, 0);
  const src = ac.createBufferSource();
  src.buffer = buf;
  src.connect(gain);
  const now = ac.currentTime;
  // アンダーラン時はバッファを積み直す
  if(nextTime < now + 0.02){ nextTime = now + TARGET_LATENCY; }
  src.start(nextTime);
  nextTime += buf.duration;
}

function updateStat(){
  stat.innerHTML = '受信パケット: '+pkts+' ／ ジッタバッファ: 120ms';
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


async def start_udp(hub: AudioHub, addr, port):
    loop = asyncio.get_event_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: USRPReceiver(hub),
        local_addr=(addr, port),
    )
    return transport


def main():
    global USRP_RX_ADDR, USRP_RX_PORT, WEB_HOST, WEB_PORT

    ap = argparse.ArgumentParser(description="OpenCCVoice USRP Web (phase1 RX)")
    ap.add_argument("--usrp-addr", default=USRP_RX_ADDR)
    ap.add_argument("--usrp-port", type=int, default=USRP_RX_PORT)
    ap.add_argument("--web-host", default=WEB_HOST)
    ap.add_argument("--web-port", type=int, default=WEB_PORT)
    ap.add_argument("--cert", required=True, help="TLS 証明書 (PEM)")
    ap.add_argument("--key", required=True, help="TLS 秘密鍵 (PEM)")
    args = ap.parse_args()

    USRP_RX_ADDR, USRP_RX_PORT = args.usrp_addr, args.usrp_port
    WEB_HOST, WEB_PORT = args.web_host, args.web_port

    hub = AudioHub()

    app = web.Application()
    app["hub"] = hub
    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/status", status_handler)

    loop = asyncio.get_event_loop()
    udp_transport = loop.run_until_complete(start_udp(hub, USRP_RX_ADDR, USRP_RX_PORT))
    sys.stderr.write(
        f"usrp_web.py {__version__}\n"
        f"  USRP RX listen : {USRP_RX_ADDR}:{USRP_RX_PORT} (Analog_Bridge txPort)\n"
        f"  Web HTTPS      : https://{WEB_HOST}:{WEB_PORT}/\n"
    )

    ssl_ctx = build_ssl(args.cert, args.key)
    try:
        web.run_app(app, host=WEB_HOST, port=WEB_PORT, ssl_context=ssl_ctx, print=None)
    finally:
        udp_transport.close()


if __name__ == "__main__":
    main()
