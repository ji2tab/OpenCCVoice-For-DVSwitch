#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 OpenCCVoice for DVSwitch Web Dashboard
 app.py  V2.66

 変更履歴:
   V2.0  初版リリース
   V2.1  タイトル変更、ポート8081、ログディレクトリ修正、変更ログ機能追加
   V2.2  V2.1実機ソースのクリーンアップ
   V2.3  ログ表示機能を削除（音声化け対策）
         DVSwitch設定保存後に analog_bridge / mmdvm_bridge を自動再起動
   V2.4  UIスタイルをDVSwitch Dashboard風に変更
   V2.5  配色をDVSwitch Dashboard実ソースに合わせて変更
   V2.51 フォント11pt統一、iniバックアップ一覧を非表示、ヘッダにバージョン表示
   V2.52 MMDVM_Bridge [Info] セクション編集機能を追加
   V2.53 Bot設定/DVSwitch設定/MMDVM Info を3カラム横並びに変更
   V2.54 受信時間フィルタを縦並びに変更
   V2.55 メッセージをURLパラメータから内部保持に変更（URL 2バイト文字除去）
   V2.56 配置コメントを実態（/opt/dvswitch_bot/web）に修正
   V2.57 3カードを一括保存に統合、保存ボタンをサービス制御行へ、変更ログ非表示、
         保存時に dvswitch-bot/analog_bridge/mmdvm_bridge を一括再起動
   V2.58 メッセージ頭切れ修正（main上余白追加）、status-pillのCSS typo修正
   V2.59 .btn/.section-title のCSS typo修正（ボタン肥大化）、ボタンを大きく、
         section-titleを通常フォント化（半角括弧を細く表示）
   V2.60 サービス制御の5ボタンを同じ幅・高さに統一
   V2.61 ボタンに固定height/box-sizing追加で完全同一サイズ化
   V2.62 ボタンサイズ縮小（幅120→84px、高さ42→34px）
   V2.63 通常/変更モード追加（通常は閲覧専用＋変更ボタンのみ、変更で編集＋操作ボタン表示）
   V2.64 サービス状態を●(緑)active / ●(赤)inactive の丸印表現に変更
   V2.65 操作ボタンをPi-star風テキストボタン（オレンジ統一・| 区切り）に変更
   V2.66 操作ボタンを右寄せ、アイコン削除（テキストのみ）

 配置:
   /opt/dvswitch_bot/web/app.py

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

# リダイレクト後に1回だけ表示するメッセージ（URLに乗せない）
_flash = {"msg": "", "err": ""}

def set_flash(msg="", err=""):
    _flash["msg"] = msg
    _flash["err"] = err

def pop_flash():
    m, e = _flash["msg"], _flash["err"]
    _flash["msg"] = ""
    _flash["err"] = ""
    return m, e

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
    _msg, _err = pop_flash()
    status = get_service_status()
    bot_cfg = read_json(BOT_CONFIG)
    change_log = read_json(CHANGE_LOG) if os.path.exists(CHANGE_LOG) else []
    if not isinstance(change_log, list):
        change_log = []
    return render_template_string(TEMPLATE,
        status=status,
        bot_cfg=bot_cfg,
        dvs=get_dvs_values(),
        info=get_info_values(),
        backups=list_backups(),
        change_log=change_log,
        msg=_msg,
        err=_err,
    )

def get_dvs_values():
    return {
        "callsign": get_ini_value(MMDVM_INI, "Callsign"),
        "mmdvm_id": get_ini_value(MMDVM_INI, "Id"),
        "password": get_ini_value(MMDVM_INI, "Password"),
        "txtg":     get_ini_value(ANALOG_INI, "txTg"),
    }

def get_info_values():
    return {
        "rxfreq":    get_ini_value(MMDVM_INI, "RXFrequency", "[Info]"),
        "txfreq":    get_ini_value(MMDVM_INI, "TXFrequency", "[Info]"),
        "power":     get_ini_value(MMDVM_INI, "Power", "[Info]"),
        "lat":       get_ini_value(MMDVM_INI, "Latitude", "[Info]"),
        "lon":       get_ini_value(MMDVM_INI, "Longitude", "[Info]"),
        "height":    get_ini_value(MMDVM_INI, "Height", "[Info]"),
        "location":  get_ini_value(MMDVM_INI, "Location", "[Info]"),
        "desc":      get_ini_value(MMDVM_INI, "Description", "[Info]"),
        "url":       get_ini_value(MMDVM_INI, "URL", "[Info]"),
    }

@app.route("/api/status")
def api_status():
    return jsonify({"status": get_service_status()})


@app.route("/service/<action>", methods=["POST"])
def service_ctrl(action):
    if action not in ("start", "stop", "restart"):
        set_flash(err="不正なアクション"); return redirect("/")
    ok, msg = service_action(action)
    if ok:
        set_flash(msg=f"サービスを {action} しました"); return redirect("/")
    else:
        set_flash(err=f"{action} 失敗: {msg}"); return redirect("/")

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
        set_flash(msg="Bot設定を保存しました。サービスを再起動してください。"); return redirect("/")
    except (AssertionError, ValueError) as e:
        set_flash(err=f"入力エラー: {e}"); return redirect("/")

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
        set_flash(msg=f"DVSwitch設定を保存し、サービスを再起動しました（バックアップ: {ts}）"); return redirect("/")
    except (AssertionError, ValueError) as e:
        set_flash(err=f"入力エラー: {e}"); return redirect("/")


@app.route("/info_config", methods=["POST"])
def info_config_save():
    try:
        backup_ini()
        set_ini_value(MMDVM_INI, "RXFrequency", request.form["rxfreq"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "TXFrequency", request.form["txfreq"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Power",       request.form["power"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Latitude",    request.form["lat"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Longitude",   request.form["lon"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Height",      request.form["height"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Location",    request.form["location"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Description", request.form["desc"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "URL",         request.form["url"].strip(), "[Info]")
        subprocess.run(["sudo", "systemctl", "restart", "mmdvm_bridge"],
                       capture_output=True, timeout=15)
        set_flash(msg="MMDVM Info を保存し、mmdvm_bridge を再起動しました"); return redirect("/")
    except (KeyError, ValueError) as e:
        set_flash(err=f"入力エラー: {e}"); return redirect("/")


@app.route("/save_all", methods=["POST"])
def save_all():
    try:
        backup_ini()

        # --- Bot設定 (bot_config.json) ---
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

        # --- DVSwitch設定 (ini) ---
        callsign = request.form["callsign"].strip().upper()
        dmrid    = request.form["dmrid"].strip()
        essid    = request.form["essid"].strip()
        password = request.form["password"].strip()
        txtg     = request.form["txtg"].strip()
        assert re.match(r"^[0-9]{7}$", dmrid), "DMRID は7桁数字"
        assert re.match(r"^[0-9]{2}$", essid), "ESSID は2桁数字"
        assert callsign, "コールサインを入力"
        full_id  = dmrid + essid
        set_ini_value(MMDVM_INI, "Callsign", callsign)
        set_ini_value(MMDVM_INI, "Id", full_id)
        set_ini_value(MMDVM_INI, "Password", password)
        set_ini_value(MMDVM_INI, "Enable", "1", "[DMR]")
        set_ini_value(MMDVM_INI, "Enable", "1", "[DMR Network]")
        set_ini_value(MMDVM_INI, "Address", "tgif.network", "[DMR Network]")
        set_ini_value(ANALOG_INI, "gatewayDmrId", dmrid)
        set_ini_value(ANALOG_INI, "repeaterID", full_id)
        set_ini_value(ANALOG_INI, "txTg", txtg)
        set_ini_value(ANALOG_INI, "txPort", "51001", "[USRP]")
        set_ini_value(ANALOG_INI, "rxPort", "51000", "[USRP]")
        set_ini_value(ANALOG_INI, "usrpAudio", "AUDIO_USE_GAIN", "[USRP]")
        set_ini_value(ANALOG_INI, "tlvAudio",  "AUDIO_USE_GAIN", "[USRP]")

        # --- MMDVM Info ([Info]) ---
        set_ini_value(MMDVM_INI, "RXFrequency", request.form["rxfreq"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "TXFrequency", request.form["txfreq"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Power",       request.form["power"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Latitude",    request.form["lat"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Longitude",   request.form["lon"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Height",      request.form["height"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Location",    request.form["location"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "Description", request.form["desc"].strip(), "[Info]")
        set_ini_value(MMDVM_INI, "URL",         request.form["url"].strip(), "[Info]")

        # --- 3サービス一括再起動 ---
        subprocess.run(
            ["sudo", "systemctl", "restart", "dvswitch-bot", "analog_bridge", "mmdvm_bridge"],
            capture_output=True, timeout=30
        )
        set_flash(msg="全設定を保存し、dvswitch-bot / analog_bridge / mmdvm_bridge を再起動しました")
        return redirect("/")
    except (AssertionError, ValueError, KeyError) as e:
        set_flash(err=f"入力エラー: {e}")
        return redirect("/")

# ─── HTML テンプレート ────────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenCCVoice for DVSwitch Web Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
  :root {
    --bg:      #fafafa;
    --bg2:     #e8e8e8;
    --bg3:     #f9f9f9;
    --border:  #ccc;
    --border2: #ddd;
    --orange:  #b44010;
    --orange2: #b5651d;
    --orange3: #ef7215;
    --green:   #12AD2A;
    --green2:  #1d1;
    --green3:  #0b0;
    --text:    #333;
    --muted:   #666;
    --th-bg:   #d0d0d0;
    --mono:    'Share Tech Mono', monospace;
    --red:     #c0392b;
    --amber:   #e67e22;
    --blue:    #2563eb;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#f8f8f8;color:var(--text);font-family:arial,sans-serif;font-size:11pt;min-height:100vh;padding-bottom:40px}

  /* ヘッダ */
  header{
    background:var(--bg);
    border-bottom:2px solid var(--orange);
    padding:10px 20px;
    display:flex;align-items:center;justify-content:space-between;
    position:sticky;top:0;z-index:100;
    box-shadow:0 0 6px #999;
  }
  .logo{font-weight:bold;color:var(--orange);font-family:var(--mono);letter-spacing:.06em}
  .tagline{color:var(--muted);margin-top:2px}
  .status-pill{display:flex;align-items:center;gap:6px;color:var(--muted)}
  .dot{width:10px;height:10px;border-radius:50%;background:#ccc}
  .dot.active{background:var(--green3);box-shadow:0 0 4px var(--green3)}
  .dot.failed{background:var(--red)}
  .dot.inactive{background:var(--amber)}

  main{max-width:1100px;margin:0 auto;padding:20px 16px;display:grid;gap:12px}

  /* カード */
  .card{
    background:var(--bg);
    border-radius:10px;
    box-shadow:0 0 8px #999;
    overflow:hidden;
  }
  .card-head{
    background:var(--bg2);
    padding:6px 14px;
    border-bottom:1px solid var(--border);
font-weight:bold;
    color:var(--orange2);
    display:flex;align-items:center;gap:6px;
    border-radius:10px 10px 0 0;
  }
  .card-body{padding:14px}

  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  @media(max-width:760px){.grid2{grid-template-columns:1fr}}
  .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;align-items:start}
  @media(max-width:900px){.grid3{grid-template-columns:1fr}}

  /* フォーム */
  .field{margin-bottom:10px}
  label{display:blockcolor:var(--muted);margin-bottom:3px}
  input[type=text],input[type=number],input[type=password],select{
    width:100%;
    background:var(--bg3);
    border:1px solid var(--border);
    border-radius:4px;
    color:var(--text);
    font-family:var(--mono);

    padding:5px 8px;
    outline:none;
  }
  input:focus,select:focus{border-color:var(--orange2)}
  .row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .toggle-row{display:flex;align-items:center;gap:8px;margin-bottom:10px}
  .toggle-label{color:var(--text)}
  input[type=checkbox]{width:14px;height:14px;accent-color:var(--orange2)}

  /* ボタン */
  .btn{
    display:inline-flex;align-items:center;justify-content:center;gap:6px;
    box-sizing:border-box;
    width:84px;height:34px;
    padding:0 8px;border-radius:6px;
    font-family:arial,sans-serif;font-weight:bold;font-size:12px;line-height:1;
    cursor:pointer;transition:opacity .15s;border:1px solid #999;
    background:var(--bg2);color:var(--text);
    vertical-align:middle;
  }
  .btn:hover{opacity:.8}
  .btn:active{transform:scale(.97)}
  .btn-primary{background:var(--orange2);border-color:var(--orange);color:#fff}
  .btn-green{background:#1a6b1a;border-color:#0a4a0a;color:#fff}
  .btn-red{background:#a02020;border-color:#701010;color:#fff}
  .btn-amber{background:#b07010;border-color:#806000;color:#fff}
  .btn-ghost{background:var(--bg2);border-color:#999;color:var(--muted)}
  .btn-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}

  /* サービス */
  .svc-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
  .svc-name{font-weight:bold;color:var(--orange2);font-family:var(--mono)}
  .svc-badge{
    display:inline-flex;align-items:center;gap:6px;
    font-weight:bold;font-family:arial,sans-serif;font-size:13px;
  }
  .svc-badge::before{
    content:"";width:11px;height:11px;border-radius:50%;
    display:inline-block;background:#999;
  }
  .svc-badge.active{color:#1a6b1a}
  .svc-badge.active::before{background:#12AD2A;box-shadow:0 0 4px #12AD2A}
  .svc-badge.inactive{color:#a02020}
  .svc-badge.inactive::before{background:#e02020}
  .svc-badge.failed{color:#a02020}
  .svc-badge.failed::before{background:#e02020}

  /* メッセージ */
  .msg,.err{
    border-radius:6px;padding:8px 14px;
margin-bottom:6px;border-left:4px solid;
  }
  .msg{background:#e8f5e9;border-color:var(--green);color:#1a6b1a}
  .err{background:#fdecea;border-color:var(--red);color:#a02020}

  /* テーブル共通 */
  table{width:100%;border-collapse:collapse}
  th{background:var(--th-bg);padding:4px 8px;text-align:left;border:1px solid var(--border)}
  td{padding:3px 8px;border-bottom:1px solid var(--border2)}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:#f0f0e8}

  /* バックアップ・変更ログ */
  .bak-list{list-style:none}
  .bak-list li{color:var(--muted);padding:3px 0;border-bottom:1px solid var(--border2);font-family:var(--mono)}
  .bak-list li:last-child{border-bottom:none}
  .chg-list{list-style:none}
  .chg-list li{padding:5px 0;border-bottom:1px solid var(--border2);display:flex;flex-wrap:wrap;gap:6px;align-items:baseline;font-family:var(--mono)}
  .chg-list li:last-child{border-bottom:none}
  .chg-time{color:var(--muted);min-width:135px}
  .chg-key{color:var(--orange2);font-weight:bold}
  .chg-arrow{color:var(--muted)}
  .chg-new{color:#1a6b1a;font-weight:bold}


  /* Pi-star風テキストボタン */
  .tbtn-row{display:inline-flex;align-items:center;flex-wrap:wrap}
  .tbtn{
    background:none;border:none;color:var(--orange2);
    font-family:arial,sans-serif;font-size:14px;font-weight:bold;
    cursor:pointer;padding:2px 12px;white-space:nowrap;
  }
  .tbtn:hover{text-decoration:underline;color:var(--orange)}
  .tbtn-sep{color:#ccc;font-size:14px;user-select:none}
  .tbtn-form{display:inline;margin:0}

  /* モード切替リンク風ボタン */
  .mode-link{
    background:none;border:none;color:var(--orange2);
    font-family:arial,sans-serif;font-size:13px;font-weight:bold;
    cursor:pointer;padding:4px 8px;letter-spacing:.05em;
  }
  .mode-link:hover{text-decoration:underline}
  /* 閲覧専用時の入力欄 */
  .view-mode input,.view-mode select{
    background:transparent;border:1px solid transparent;
    color:var(--text);pointer-events:none;padding-left:0;
  }
  .view-mode input[type=checkbox]{opacity:.6}
  .view-mode .edit-only{display:none}

  .section-title{
    color:var(--muted);
    font-family:arial,sans-serif;
    letter-spacing:.05em;
    margin-bottom:10px;padding-bottom:4px;
    border-bottom:1px solid var(--border2);
  }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">OpenCCVoice for DVSwitch Web Dashboard</div>
    <div class="tagline">JJ2YYK / TGIF TG168 管理パネル&nbsp;&nbsp;&nbsp;V2.66</div>
  </div>
  <div class="status-pill">
    <div class="dot {% if status == 'active' %}active{% elif status == 'failed' %}failed{% else %}inactive{% endif %}" id="dot"></div>
    <span id="svc-status-label">{{ status }}</span>
  </div>
</header>

<main class="view-mode" id="main">

{% if msg %}
<div class="msg">✔ {{ msg }}</div>
{% endif %}
{% if err %}
<div class="err">✖ {{ err }}</div>
{% endif %}

<div class="card">
  <div class="card-head">⚙ サービス制御 — {{ service_name }}</div>
  <div class="card-body">
    <div class="svc-row">
      <span class="svc-name">dvswitch-bot</span>
      <span class="svc-badge {{ status }}" id="svc-status">{{ status }}</span>
      <div class="btn-row" style="align-items:center;margin-left:auto">
        <!-- 通常モード: 変更ボタンのみ -->
        <button class="mode-link" id="btn-edit" onclick="enterEdit()">✎ 変更</button>
        <!-- 変更モード: 操作ボタン群（初期非表示） -->
        <div id="edit-buttons" class="tbtn-row" style="display:none">
          <form method="post" action="/service/start" class="tbtn-form">
            <button class="tbtn">Start</button>
          </form>
          <span class="tbtn-sep">|</span>
          <form method="post" action="/service/stop" class="tbtn-form">
            <button class="tbtn">Stop</button>
          </form>
          <span class="tbtn-sep">|</span>
          <form method="post" action="/service/restart" class="tbtn-form">
            <button class="tbtn">Restart</button>
          </form>
          <span class="tbtn-sep">|</span>
          <button class="tbtn" type="button" onclick="refreshStatus()">更新</button>
          <span class="tbtn-sep">|</span>
          <button class="tbtn" type="submit" form="save-form">保存</button>
          <span class="tbtn-sep">|</span>
          <button class="tbtn" type="button" onclick="cancelEdit()">取消</button>
        </div>
      </div>
    </div>
  </div>
</div>

<form id="save-form" method="post" action="/save_all">
<div class="grid3">

  <div class="card">
    <div class="card-head">🤖 Bot 設定 — bot_config.json</div>
    <div class="card-body">
        <div class="section-title">受信時間フィルタ</div>
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
      </div>
  </div>

  <div class="card">
    <div class="card-head">📡 DVSwitch 設定 — ini ファイル</div>
    <div class="card-body">
        <div class="section-title">局識別情報 (MMDVM_Bridge.ini)</div>
        <div class="field">
          <label>Callsign</label>
          <input type="text" name="callsign" value="{{ dvs.callsign }}" placeholder="JJ2YYK" required>
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
        <div style="font-size:10px;color:var(--muted);margin-bottom:12px">
          保存前に自動バックアップを作成します。<br>
          固定値: Address=tgif.network / txPort=51001 / rxPort=51000
        </div>
      </div>
  </div>

  <!-- MMDVM Info -->
  <div class="card">
    <div class="card-head">📍 MMDVM Info — MMDVM_Bridge.ini [Info]</div>
    <div class="card-body">
          <div class="section-title">周波数</div>
        <div class="row2">
          <div class="field">
            <label>RX Frequency (Hz)</label>
            <input type="text" name="rxfreq" value="{{ info.rxfreq }}" placeholder="222340000">
          </div>
          <div class="field">
            <label>TX Frequency (Hz)</label>
            <input type="text" name="txfreq" value="{{ info.txfreq }}" placeholder="224940000">
          </div>
        </div>
        <div class="section-title">位置情報</div>
        <div class="row2">
          <div class="field">
            <label>Latitude（緯度）</label>
            <input type="text" name="lat" value="{{ info.lat }}" placeholder="35.21">
          </div>
          <div class="field">
            <label>Longitude（経度）</label>
            <input type="text" name="lon" value="{{ info.lon }}" placeholder="137.03">
          </div>
        </div>
        <div class="row2">
          <div class="field">
            <label>Height（高さ m）</label>
            <input type="text" name="height" value="{{ info.height }}" placeholder="0">
          </div>
          <div class="field">
            <label>Power（W）</label>
            <input type="text" name="power" value="{{ info.power }}" placeholder="1">
          </div>
        </div>
        <div class="field">
          <label>Location（設置場所）</label>
          <input type="text" name="location" value="{{ info.location }}" placeholder="Owariasahi, Aichi">
        </div>
        <div class="section-title">その他</div>
        <div class="field">
          <label>Description</label>
          <input type="text" name="desc" value="{{ info.desc }}" placeholder="MMDVM_Bridge">
        </div>
        <div class="field">
          <label>URL</label>
          <input type="text" name="url" value="{{ info.url }}" placeholder="https://...">
        </div>
    </div>
  </div>

</div>



<div style="text-align:center;font-size:9px;color:var(--muted);margin-top:4px">
  OpenCCVoice for DVSwitch Web Dashboard V2.5
</div>
</form>

</main>

<script>
function dotClass(s){
  if(s==="active") return "active";
  if(s==="failed") return "failed";
  return "inactive";
}
function refreshStatus(){
  fetch("/api/status").then(r=>r.json()).then(d=>{
    const s=d.status;
    document.getElementById("dot").className="dot "+dotClass(s);
    document.getElementById("svc-status-label").textContent=s;
    const p=document.getElementById("svc-status");
    if(p){p.textContent=s;p.className="svc-badge "+dotClass(s);}
  });
}
setInterval(refreshStatus,20000);
function toggleNight(on){
  document.getElementById("night-fields").style.display=on?"":"none";
}
function enterEdit(){
  document.getElementById("main").classList.remove("view-mode");
  document.getElementById("btn-edit").style.display="none";
  document.getElementById("edit-buttons").style.display="inline-flex";
}
function cancelEdit(){
  // 変更を破棄して通常モードへ（再読み込みで元の値に戻す）
  location.href="/";
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
