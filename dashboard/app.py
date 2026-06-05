#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 OpenCCVoice for DVSwitch Web Dashboard
 app.py  V2.2

 変更履歴:
   V2.0  初版リリース
   V2.1  タイトル変更、ポート8081、ログディレクトリ修正、変更ログ機能追加
   V2.2  V2.1実機ソースのクリーンアップ
         - CHANGE_LOG 二重定義を修正
         - append_change_log 二重定義を修正
         - コメントの文字化け修正

 配置:
   /opt/openccvoice/web/app.py   ← 推奨
   /opt/dvswitch_bot/web/app.py  ← 既存環境

 アクセス:
   http://<RPi-IP>:8081/
================================================================================
"""

import os, json, re, subprocess, glob
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

# ─── パス設定 ─────────────────────────────────────────────
BOT_CONFIG   = "/opt/dvswitch_bot/bot_config.json"
CHANGE_LOG   = "/opt/dvswitch_bot/bot_change_log.json"
MMDVM_INI    = "/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
DVSWITCH_INI = "/opt/MMDVM_Bridge/DVSwitch.ini"
ANALOG_INI   = "/opt/Analog_Bridge/Analog_Bridge.ini"
LOG_DIR      = "/var/log/mmdvm"
BAK_ROOT     = "/opt/dvswitch_bot/bak/ini"
SERVICE_NAME = "dvswitch-bot"

app = Flask(__name__)

# ─── ユーティリティ ──────────────────────────────────────

def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)

def append_change_log(label, old_cfg, new_cfg):
    import time
    entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "changes": {}}
    for k in new_cfg:
        o = old_cfg.get(k)
        n = new_cfg[k]
        if str(o) != str(n):
            entry["changes"][k] = {"from": o, "to": n}
    if not entry["changes"]:
        return
    try:
        logs = read_json(CHANGE_LOG) if os.path.exists(CHANGE_LOG) else []
        if not isinstance(logs, list):
            logs = []
        logs.insert(0, entry)
        write_json(CHANGE_LOG, logs[:50])
    except Exception:
        pass

def get_ini_value(path, key, section=None):
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return ""
    in_section = (section is None)
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            cur = stripped
            in_section = (section is None) or (cur == section)
        if in_section and re.match(rf"^\s*{re.escape(key)}\s*=", line):
            val = line.split("=", 1)[1].strip()
            val = re.sub(r"\s*;.*$", "", val).strip()
            return val
    return ""

def set_ini_value(path, key, value, section=None):
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False
    in_section = (section is None)
    done = False
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            cur = stripped
            in_section = (section is None) or (cur == section)
        if in_section and not done and re.match(rf"^\s*{re.escape(key)}\s*=", line):
            indent = re.match(r"^\s*", line).group()
            out.append(f"{indent}{key}={value}\n")
            done = True
        else:
            out.append(line)
    if done:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out)
    return done

def backup_ini():
    ts = datetime.now().strftime("%y%m%d%H%M%S")
    dst = os.path.join(BAK_ROOT, ts)
    os.makedirs(dst, exist_ok=True)
    for src in [MMDVM_INI, DVSWITCH_INI, ANALOG_INI]:
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, dst)
    return ts

def get_service_status():
    try:
        r = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"

def service_action(action):
    try:
        r = subprocess.run(
            ["sudo", "systemctl", action, SERVICE_NAME],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0, r.stderr.strip()
    except Exception as e:
        return False, str(e)


def list_backups():
    try:
        dirs = sorted(
            [d for d in glob.glob(os.path.join(BAK_ROOT, "*")) if os.path.isdir(d)],
            reverse=True
        )
        return [os.path.basename(d) for d in dirs]
    except Exception:
        return []

# ─── ルート ──────────────────────────────────────────────

@app.route("/")
def index():
    status = get_service_status()
    bot_cfg = read_json(BOT_CONFIG)
    change_log = read_json(CHANGE_LOG) if os.path.exists(CHANGE_LOG) else []
    if not isinstance(change_log, list):
        change_log = []
    return render_template_string(TEMPLATE,
        status=status,
        bot_cfg=bot_cfg,
        dvs=get_dvs_values(),
        backups=list_backups(),
        change_log=change_log,
        msg=request.args.get("msg", ""),
        err=request.args.get("err", ""),
    )

def get_dvs_values():
    return {
        "callsign": get_ini_value(MMDVM_INI, "Callsign"),
        "mmdvm_id": get_ini_value(MMDVM_INI, "Id"),
        "password": get_ini_value(MMDVM_INI, "Password"),
        "txtg":     get_ini_value(ANALOG_INI, "txTg"),
    }

@app.route("/api/status")
def api_status():
    return jsonify({"status": get_service_status()})


@app.route("/service/<action>", methods=["POST"])
def service_ctrl(action):
    if action not in ("start", "stop", "restart"):
        return redirect(url_for("index", err="不正なアクション"))
    ok, msg = service_action(action)
    if ok:
        return redirect(url_for("index", msg=f"サービスを {action} しました"))
    else:
        return redirect(url_for("index", err=f"{action} 失敗: {msg}"))

@app.route("/bot_config", methods=["POST"])
def bot_config_save():
    try:
        cfg = {
            "RX_DURATION_MIN_SEC": float(request.form["rx_min"]),
            "RX_DURATION_MAX_SEC": float(request.form["rx_max"]),
            "ANNOUNCE_FREQ":       int(request.form["freq"]),
            "NIGHT_MODE_ENABLED":  request.form.get("night_enabled") == "on",
            "NIGHT_START_HOUR":    int(request.form["night_start"]),
            "NIGHT_END_HOUR":      int(request.form["night_end"]),
        }
        assert cfg["RX_DURATION_MIN_SEC"] > 0, "最小受信時間は0より大"
        assert cfg["RX_DURATION_MIN_SEC"] < cfg["RX_DURATION_MAX_SEC"], "MIN < MAX であること"
        assert cfg["ANNOUNCE_FREQ"] in (1, 2, 3), "放送回数は1/2/3"
        assert 0 <= cfg["NIGHT_START_HOUR"] <= 23
        assert 0 <= cfg["NIGHT_END_HOUR"] <= 23
        old_cfg = read_json(BOT_CONFIG)
        write_json(BOT_CONFIG, cfg)
        append_change_log("Bot設定", old_cfg, cfg)
        return redirect(url_for("index", msg="Bot設定を保存しました。サービスを再起動してください。"))
    except (AssertionError, ValueError) as e:
        return redirect(url_for("index", err=f"入力エラー: {e}"))

@app.route("/dvs_config", methods=["POST"])
def dvs_config_save():
    try:
        callsign = request.form["callsign"].strip().upper()
        dmrid    = request.form["dmrid"].strip()
        essid    = request.form["essid"].strip()
        password = request.form["password"].strip()
        txtg     = request.form["txtg"].strip()

        assert re.match(r"^[0-9]{7}$", dmrid), "DMRID は7桁数字"
        assert re.match(r"^[0-9]{2}$", essid), "ESSID は2桁数字"
        assert callsign, "コールサインを入力"

        full_id  = dmrid + essid
        repeater = dmrid + essid
        ts = backup_ini()

        set_ini_value(MMDVM_INI, "Callsign", callsign)
        set_ini_value(MMDVM_INI, "Id", full_id)
        set_ini_value(MMDVM_INI, "Password", password)
        set_ini_value(MMDVM_INI, "Enable", "1", "[DMR]")
        set_ini_value(MMDVM_INI, "Enable", "1", "[DMR Network]")
        set_ini_value(MMDVM_INI, "Address", "tgif.network", "[DMR Network]")

        set_ini_value(ANALOG_INI, "gatewayDmrId", dmrid)
        set_ini_value(ANALOG_INI, "repeaterID", repeater)
        set_ini_value(ANALOG_INI, "txTg", txtg)
        set_ini_value(ANALOG_INI, "txPort", "51001", "[USRP]")
        set_ini_value(ANALOG_INI, "rxPort", "51000", "[USRP]")
        set_ini_value(ANALOG_INI, "usrpAudio", "AUDIO_USE_GAIN", "[USRP]")
        set_ini_value(ANALOG_INI, "tlvAudio",  "AUDIO_USE_GAIN", "[USRP]")

        # analog_bridge / mmdvm_bridge を自動再起動
        subprocess.run(["sudo", "systemctl", "restart", "analog_bridge", "mmdvm_bridge"],
                       capture_output=True, timeout=15)
        return redirect(url_for("index",
            msg=f"DVSwitch設定を保存し、サービスを再起動しました（バックアップ: {ts}）"))
    except (AssertionError, ValueError) as e:
        return redirect(url_for("index", err=f"入力エラー: {e}"))

# ─── HTML テンプレート ────────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenCCVoice for DVSwitch Web Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Zen+Kaku+Gothic+New:wght@400;700&display=swap');

  :root {
    --bg:      #0d1117;
    --panel:   #161b22;
    --border:  #30363d;
    --accent:  #58a6ff;
    --green:   #3fb950;
    --red:     #f85149;
    --amber:   #e3b341;
    --text:    #c9d1d9;
    --muted:   #8b949e;
    --mono:    'Share Tech Mono', monospace;
    --sans:    'Zen Kaku Gothic New', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    padding: 0 0 60px;
  }

  header {
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    padding: 14px 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    position: sticky; top: 0; z-index: 100;
  }
  .logo {
    font-family: var(--mono);
    font-size: 1.15rem;
    color: var(--accent);
    letter-spacing: .08em;
  }
  .logo span { color: var(--green); }
  .tagline { font-size: .78rem; color: var(--muted); }

  .status-pill {
    margin-left: auto;
    display: flex; align-items: center; gap: 8px;
    font-family: var(--mono);
    font-size: .82rem;
  }
  .dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--muted);
    box-shadow: 0 0 6px currentColor;
    transition: background .4s;
  }
  .dot.active   { background: var(--green); }
  .dot.failed   { background: var(--red); }
  .dot.inactive { background: var(--amber); }

  main { max-width: 1100px; margin: 0 auto; padding: 28px 20px 0; display: grid; gap: 24px; }

  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  @media(max-width:760px) { .grid2 { grid-template-columns: 1fr; } }

  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .card-head {
    padding: 12px 18px;
    border-bottom: 1px solid var(--border);
    font-size: .82rem;
    font-family: var(--mono);
    color: var(--accent);
    letter-spacing: .06em;
    display: flex; align-items: center; gap: 8px;
  }
  .card-head .icon { font-size: 1rem; }
  .card-body { padding: 18px; }

  .field { margin-bottom: 14px; }
  label { display: block; font-size: .78rem; color: var(--muted); margin-bottom: 5px; }
  input[type=text], input[type=number], input[type=password], select {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-family: var(--mono);
    font-size: .88rem;
    padding: 7px 10px;
    outline: none;
    transition: border-color .2s;
  }
  input:focus, select:focus { border-color: var(--accent); }

  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

  .toggle-row {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 14px;
  }
  .toggle-label { font-size: .82rem; color: var(--text); }
  input[type=checkbox] { width: 16px; height: 16px; accent-color: var(--accent); }

  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 18px;
    border-radius: 6px;
    border: none;
    font-family: var(--mono);
    font-size: .84rem;
    cursor: pointer;
    transition: opacity .15s, transform .1s;
    text-decoration: none;
  }
  .btn:active { transform: scale(.97); }
  .btn-primary { background: var(--accent); color: #0d1117; font-weight: 700; }
  .btn-green   { background: var(--green); color: #0d1117; font-weight: 700; }
  .btn-red     { background: var(--red); color: #fff; }
  .btn-amber   { background: var(--amber); color: #0d1117; }
  .btn-ghost   { background: transparent; border: 1px solid var(--border); color: var(--text); }
  .btn:hover   { opacity: .85; }

  .btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 6px; }

  .svc-row {
    display: flex; align-items: center; gap: 14px;
    flex-wrap: wrap;
  }
  .svc-name { font-family: var(--mono); font-size: .9rem; color: var(--accent); }
  .svc-status { font-family: var(--mono); font-size: .82rem; padding: 3px 10px;
    border-radius: 20px; background: var(--bg); border: 1px solid var(--border); }
  .svc-status.active   { color: var(--green); border-color: var(--green); }
  .svc-status.failed   { color: var(--red);   border-color: var(--red); }
  .svc-status.inactive { color: var(--amber); border-color: var(--amber); }


  .msg, .err {
    border-radius: 6px;
    padding: 10px 16px;
    font-size: .84rem;
    margin-bottom: 4px;
    font-family: var(--mono);
  }
  .msg { background: #1c2b1c; border: 1px solid var(--green); color: var(--green); }
  .err { background: #2b1c1c; border: 1px solid var(--red);   color: var(--red); }

  .bak-list { list-style: none; }
  .bak-list li {
    font-family: var(--mono);
    font-size: .78rem;
    color: var(--muted);
    padding: 3px 0;
    border-bottom: 1px solid #1e242c;
  }
  .bak-list li:last-child { border-bottom: none; }

  .chg-list { list-style: none; }
  .chg-list li {
    font-family: var(--mono);
    font-size: .78rem;
    color: var(--text);
    padding: 6px 0;
    border-bottom: 1px solid #1e242c;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: baseline;
  }
  .chg-list li:last-child { border-bottom: none; }
  .chg-time  { color: var(--muted); min-width: 140px; }
  .chg-key   { color: var(--accent); }
  .chg-arrow { color: var(--amber); }
  .chg-new   { color: var(--green); }

  .section-title {
    font-size: .7rem;
    font-family: var(--mono);
    color: var(--muted);
    letter-spacing: .15em;
    text-transform: uppercase;
    margin-bottom: 16px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }
  hr { border: none; border-top: 1px solid var(--border); margin: 6px 0 14px; }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">OpenCCVoice for DVSwitch Web Dashboard</div>
    <div class="tagline">JJ2YYK / TGIF TG168 管理パネル</div>
  </div>
  <div class="status-pill">
    <div class="dot {% if status == 'active' %}active{% elif status == 'failed' %}failed{% else %}inactive{% endif %}" id="dot"></div>
    <span id="svc-status-label">{{ status }}</span>
  </div>
</header>

<main>

{% if msg %}
<div class="msg">✔ {{ msg }}</div>
{% endif %}
{% if err %}
<div class="err">✖ {{ err }}</div>
{% endif %}

<!-- サービス制御 -->
<div class="card">
  <div class="card-head"><span class="icon">⚙</span> サービス制御 — {{ service_name }}</div>
  <div class="card-body">
    <div class="svc-row">
      <span class="svc-name">dvswitch-bot</span>
      <span class="svc-status {{ status }}" id="svc-status">{{ status }}</span>
      <div class="btn-row">
        <form method="post" action="/service/start">
          <button class="btn btn-green">▶ Start</button>
        </form>
        <form method="post" action="/service/stop">
          <button class="btn btn-red">■ Stop</button>
        </form>
        <form method="post" action="/service/restart">
          <button class="btn btn-amber">↺ Restart</button>
        </form>
        <button class="btn btn-ghost" onclick="refreshStatus()">⟳ 更新</button>
      </div>
    </div>
  </div>
</div>

<!-- 2カラム: Bot設定 / DVSwitch設定 -->
<div class="grid2">

  <!-- Bot設定 -->
  <div class="card">
    <div class="card-head"><span class="icon">🤖</span> Bot 設定 — bot_config.json</div>
    <div class="card-body">
      <form method="post" action="/bot_config">
        <div class="section-title">受信時間フィルタ</div>
        <div class="row2">
          <div class="field">
            <label>最小受信時間 (秒)</label>
            <input type="number" name="rx_min" step="0.1" min="0.1" max="10"
              value="{{ bot_cfg.get('RX_DURATION_MIN_SEC', 0.5) }}" required>
          </div>
          <div class="field">
            <label>最大受信時間 / カーチャンク (秒)</label>
            <input type="number" name="rx_max" step="0.1" min="0.2" max="30"
              value="{{ bot_cfg.get('RX_DURATION_MAX_SEC', 3.9) }}" required>
          </div>
        </div>

        <div class="section-title">定時アナウンス</div>
        <div class="field">
          <label>1時間あたりの放送回数</label>
          <select name="freq">
            {% for v in [1,2,3] %}
            <option value="{{ v }}" {% if bot_cfg.get('ANNOUNCE_FREQ',2)==v %}selected{% endif %}>{{ v }} 回/h</option>
            {% endfor %}
          </select>
        </div>

        <div class="section-title">ナイトモード</div>
        <div class="toggle-row">
          <input type="checkbox" name="night_enabled" id="night_chk"
            {% if bot_cfg.get('NIGHT_MODE_ENABLED', True) %}checked{% endif %}
            onchange="toggleNight(this.checked)">
          <label class="toggle-label" for="night_chk">ナイトモード有効（定時アナウンスを抑制）</label>
        </div>
        <div id="night-fields" class="row2" {% if not bot_cfg.get('NIGHT_MODE_ENABLED', True) %}style="display:none"{% endif %}>
          <div class="field">
            <label>開始 N1 (0〜23)</label>
            <input type="number" name="night_start" min="0" max="23"
              value="{{ bot_cfg.get('NIGHT_START_HOUR', 22) }}">
          </div>
          <div class="field">
            <label>終了 N2 (0〜23)</label>
            <input type="number" name="night_end" min="0" max="23"
              value="{{ bot_cfg.get('NIGHT_END_HOUR', 5) }}">
          </div>
        </div>

        <div class="btn-row" style="margin-top:18px">
          <button class="btn btn-primary" type="submit">💾 保存</button>
        </div>
      </form>
    </div>
  </div>

  <!-- DVSwitch設定 -->
  <div class="card">
    <div class="card-head"><span class="icon">📡</span> DVSwitch 設定 — ini ファイル</div>
    <div class="card-body">
      <form method="post" action="/dvs_config">
        <div class="section-title">局識別情報 (MMDVM_Bridge.ini)</div>
        <div class="field">
          <label>Callsign</label>
          <input type="text" name="callsign"
            value="{{ dvs.callsign }}" placeholder="JJ2YYK" required>
        </div>
        <div class="row2">
          <div class="field">
            <label>DMR ID（7桁）</label>
            <input type="text" name="dmrid" maxlength="7" pattern="[0-9]{7}"
              value="{{ dvs.mmdvm_id[:7] if dvs.mmdvm_id|length >= 7 else dvs.mmdvm_id }}"
              placeholder="4402518" required>
          </div>
          <div class="field">
            <label>ESSID（2桁）</label>
            <input type="text" name="essid" maxlength="2" pattern="[0-9]{2}"
              value="{{ dvs.mmdvm_id[7:9] if dvs.mmdvm_id|length >= 9 else '00' }}"
              placeholder="01" required>
          </div>
        </div>
        <div class="field">
          <label>TGIF Password</label>
          <input type="password" name="password" value="{{ dvs.password }}">
        </div>

        <div class="section-title">ルーティング (Analog_Bridge.ini)</div>
        <div class="field">
          <label>送信 TG（txTg）</label>
          <input type="text" name="txtg" value="{{ dvs.txtg }}" placeholder="168" required>
        </div>

        <div style="font-size:.75rem; color:var(--muted); margin-bottom:14px">
          保存前に自動バックアップを作成します。<br>
          固定値: Address=tgif.network / txPort=51001 / rxPort=51000
        </div>

        <div class="btn-row">
          <button class="btn btn-primary" type="submit">💾 保存＆バックアップ</button>
        </div>
      </form>
    </div>
  </div>

</div><!-- .grid2 -->

<!-- バックアップ一覧 -->
<div class="card">
  <div class="card-head"><span class="icon">🗄</span> ini バックアップ一覧</div>
  <div class="card-body">
    {% if backups %}
    <ul class="bak-list">
      {% for b in backups[:10] %}
      <li>{{ b[:2] }}/{{ b[2:4] }}/{{ b[4:6] }} {{ b[6:8] }}:{{ b[8:10] }}:{{ b[10:12] }}  →  {{ b }}</li>
      {% endfor %}
    </ul>
    {% if backups|length > 10 %}
    <div style="font-size:.75rem;color:var(--muted);margin-top:6px">（最新10件を表示）</div>
    {% endif %}
    {% else %}
    <div style="font-size:.82rem;color:var(--muted)">バックアップはまだありません。</div>
    {% endif %}
  </div>
</div>

<!-- Bot設定 変更ログ -->
<div class="card">
  <div class="card-head"><span class="icon">📝</span> Bot設定 変更ログ</div>
  <div class="card-body">
    {% if change_log %}
    <ul class="chg-list">
      {% for e in change_log[:20] %}
      <li>
        <span class="chg-time">{{ e.time }}</span>
        {% for k, v in e.changes.items() %}
        <span class="chg-key">{{ k }}</span>
        <span style="color:var(--muted)">{{ v.from }}</span>
        <span class="chg-arrow">→</span>
        <span class="chg-new">{{ v.to }}</span>
        {% endfor %}
      </li>
      {% endfor %}
    </ul>
    {% else %}
    <div style="font-size:.82rem;color:var(--muted)">変更履歴はまだありません。</div>
    {% endif %}
  </div>
</div>

</main>

<script>
function dotClass(s) {
  if (s === "active") return "active";
  if (s === "failed") return "failed";
  return "inactive";
}

function refreshStatus() {
  fetch("/api/status").then(r=>r.json()).then(d => {
    const s = d.status;
    const dot = document.getElementById("dot");
    const lbl = document.getElementById("svc-status-label");
    const pill = document.getElementById("svc-status");
    dot.className = "dot " + dotClass(s);
    lbl.textContent = s;
    if (pill) { pill.textContent = s; pill.className = "svc-status " + dotClass(s); }
  });
}


setInterval(refreshStatus, 20000);


function toggleNight(on) {
  document.getElementById("night-fields").style.display = on ? "" : "none";
}
</script>

</body>
</html>
"""

@app.context_processor
def inject_service_name():
    return {"service_name": SERVICE_NAME}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False, threaded=True)
