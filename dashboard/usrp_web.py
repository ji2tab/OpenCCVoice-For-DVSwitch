#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 OpenCCVoice for DVSwitch  —  Web USRP クライアント
 usrp_web.py  V0.5   （フェーズ1: RX モニタのみ / bot 非干渉 / HTTPS）

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
================================================================================
"""

__version__ = "V0.5"

import argparse
import asyncio
import ssl
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

# USRP 音声パケット定数
USRP_MAGIC     = b"USRP"
USRP_HDR_LEN   = 32
USRP_TYPE_VOICE = 0
# 1クライアントあたりの音声キュー上限（超過分は捨ててレイテンシ肥大を防ぐ）
CLIENT_QUEUE_MAX = 50

# 🔵 V0.4: 案A（ミックスせず優先1本化）。51002(priority=bot応答)を最優先とし、
# priority 受信中は 51001(RX=他局受信) を捨てて合流させない。これにより
# 同時受信時に2系統が1本のWSへ倍レートで流れ込み「再生が半速化」する問題を防ぐ。
PRIORITY_HOLD_SEC    = 0.2   # priority を1発受けたら、この秒数 RX を抑制（20ms間隔に対し十分な保持）
PRIORITY_SESSION_GAP = 0.5   # priority がこの秒数途切れたら「新しいbot応答」とみなす
# 各 priority セッション先頭のスキップ数。bot は RF 対策で先頭に 100Hz 微小トーン
# （NOISE_LEAD_PACKETS=5）を入れており、それがミラーでは「ブブッ」という雑音として
# 鳴る。RF側の対策は残したまま、Webでは先頭数パケットを再生しないことで抑制する。
# 5(トーン)＋余裕。トーンの後は無音パディングなので多めに捨てても実害はない。
PRIORITY_LEAD_SKIP   = 8

# --verbose 時のコンソール出力
VERBOSE = False

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
        # 🔵 V0.4: 優先(priority=51002)制御の状態
        self.priority_hold_until = 0.0   # この時刻まで RX を抑制する
        self.priority_last_ts = 0.0      # 直近に priority を受けた時刻（セッション判定用）
        self.priority_skip_remaining = 0 # 現セッションで残りスキップするパケット数

    def register(self):
        q = asyncio.Queue(maxsize=CLIENT_QUEUE_MAX)
        self.clients.add(q)
        return q

    def unregister(self, q):
        self.clients.discard(q)

    def feed(self, role: str, audio: bytes, keyup: int):
        """role='priority'(51002/bot応答) と role='rx'(51001/他局受信) を
        ミックスせず1本化する（案A）。priority を最優先し、priority 受信中は
        ホールド期間 rx を捨てる。priority セッション先頭はトーン抑制でスキップ。
        戻り値: 実際にブラウザへ流したら True（verbose ログ判定用）。"""
        now = time.monotonic()
        if role == "priority":
            # 新しい bot 応答の立ち上がり検出 → 先頭スキップをセット
            if now - self.priority_last_ts > PRIORITY_SESSION_GAP:
                self.priority_skip_remaining = PRIORITY_LEAD_SKIP
            self.priority_last_ts = now
            self.priority_hold_until = now + PRIORITY_HOLD_SEC
            # 先頭トーン区間はブラウザへ流さない（ホールドは上で確定済み）
            if self.priority_skip_remaining > 0:
                self.priority_skip_remaining -= 1
                return False
            self._broadcast(audio, keyup)
            return True
        else:  # rx
            # bot 応答中（ホールド中）は他局受信を捨てて合流させない
            if now < self.priority_hold_until:
                return False
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
        self.role = role            # 🔵 V0.4: "rx"(51001) / "priority"(51002)
        self._first_logged = False

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
        if not self._first_logged:
            self._first_logged = True
            vlog(f"[rx:{self.role}] first voice packet from {addr[0]}:{addr[1]} "
                 f"({len(audio)} bytes, keyup={keyup})")
        self.hub.pkt_count += 1
        played = self.hub.feed(self.role, audio, keyup)
        if VERBOSE and self.hub.pkt_count % 50 == 0:
            vlog(f"[rx:{self.role}] packets={self.hub.pkt_count} keyup={keyup} "
                 f"played={played} clients={len(self.hub.clients)}")

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
        # クライアントからのメッセージ（現状は close 検知のみ）
        async for msg in ws:
            if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
        pump_task.cancel()
    finally:
        hub.unregister(q)
        vlog(f"[ws] client disconnected (clients={len(hub.clients)})")
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
    受信パケット: 0 ／ ジッタバッファ: 240ms<br>
    <span style="color:#999;">※ 初回は「接続」ボタン押下（ブラウザの自動再生制限のため）</span>
  </div>
</div>

<script>
// ============================================================
// 🔵 V0.5: リングバッファ + 連続再生（継ぎ目クリック除去）
// ------------------------------------------------------------
// V0.4 までは 20ms ごとの 8kHz 小バッファを個別に AudioBuffer 化して
// 並べていた。ブラウザは各バッファを独立に出力レート(48kHz等)へリサンプル
// するため、バッファ境界で波形が不連続になり「常時プツプツ」が出ていた。
// V0.5 では届いた PCM をリングバッファに貯め、1本の連続再生ノードから
// 途切れなく読み出して「連続」リサンプル（線形補間）する。境界クリックが
// 消え、深めのプリバッファ(240ms)で到着ジッタも吸収する。
// ============================================================
const SR = 8000;                 // USRP 音声は 8kHz モノラル
const PREBUFFER_SEC = 0.24;      // ジッタバッファ 240ms（貯めてから再生開始）
const RING_CAP = SR * 8;         // リング容量 8 秒ぶん

let ac=null, ws=null, gain=null, node=null, running=false, pkts=0;
let ring=null, writeCount=0, readPos=0, primed=false;

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

  // リング初期化
  ring = new Float32Array(RING_CAP);
  writeCount = 0; readPos = 0; primed = false;

  // 連続再生ノード（出力レートで onaudioprocess が回り、8kHz リングから
  // 線形補間で読み出す。境界をまたいで連続に補間するためクリックが出ない）
  const bufSize = 2048;
  node = ac.createScriptProcessor(bufSize, 0, 1);
  const step = SR / ac.sampleRate;   // 例 8000/48000 = 0.1667（1出力サンプルあたりの読み進み）
  node.onaudioprocess = (e)=>{
    const out = e.outputBuffer.getChannelData(0);
    const prebufSamples = PREBUFFER_SEC * SR;
    // プリバッファが溜まるまで（または枯れて再プライム中は）無音
    if(!primed){
      if((writeCount - readPos) >= prebufSamples){ primed = true; }
      else { out.fill(0); return; }
    }
    for(let i=0;i<out.length;i++){
      const avail = writeCount - readPos;
      if(avail < 2){
        // アンダーラン: 無音を出し、読み位置を書き込み位置へ合わせて再プライムへ
        out[i] = 0;
        readPos = writeCount;
        primed = false;
        continue;
      }
      const idx = Math.floor(readPos);
      const frac = readPos - idx;
      const s0 = ring[idx % RING_CAP];
      const s1 = ring[(idx+1) % RING_CAP];
      out[i] = s0 + (s1 - s0) * frac;
      readPos += step;
    }
  };
  node.connect(gain);

  const proto = location.protocol==='https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto+'://'+location.host+'/ws');
  ws.binaryType = 'arraybuffer';
  ws.onopen  = ()=>{ running=true; btn.textContent='切断'; btn.className=''; setState('接続中','live'); };
  ws.onclose = ()=>{ if(running){ setState('切断','busy'); } };
  ws.onerror = ()=>{ setState('エラー','busy'); };
  ws.onmessage = ev=>{ pkts++; enqueue(ev.data); updateStat(); };
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

// 届いた 16bit PCM をリングへ書き込む（Float32 に正規化）
function enqueue(arrbuf){
  const i16 = new Int16Array(arrbuf);
  for(let i=0;i<i16.length;i++){
    ring[writeCount % RING_CAP] = i16[i] / 32768;
    writeCount++;
  }
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
    global USRP_RX_ADDR, USRP_RX_PORT, WEB_HOST, WEB_PORT, VERBOSE

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
    args = ap.parse_args()

    USRP_RX_ADDR, USRP_RX_PORT = args.usrp_addr, args.usrp_port
    WEB_HOST, WEB_PORT = args.web_host, args.web_port
    VERBOSE = args.verbose

    # listen するポート群（RX 本流＋任意でミラー）
    listen_ports = [("RX", USRP_RX_PORT)]
    if args.mirror_port and args.mirror_port != USRP_RX_PORT:
        listen_ports.append(("mirror", args.mirror_port))

    hub = AudioHub()

    app = web.Application()
    app["hub"] = hub
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
        f"usrp_web.py {__version__}\n"
        f"  USRP RX listen : {USRP_RX_ADDR}:{USRP_RX_PORT} (Analog_Bridge txPort)\n"
        f"  mirror listen  : {mirror_disp} (bot 応答音声)\n"
        f"  Web HTTPS      : https://{WEB_HOST}:{WEB_PORT}/\n"
        f"  verbose        : {'ON' if VERBOSE else 'OFF'}\n"
    )

    ssl_ctx = build_ssl(args.cert, args.key)
    web.run_app(app, host=WEB_HOST, port=WEB_PORT, ssl_context=ssl_ctx, print=None)


if __name__ == "__main__":
    main()
