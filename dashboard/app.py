#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 OpenCCVoice for DVSwitch Web Dashboard
 app.py  V3.2

 ■ 位置づけ
   V2 系（V2.0〜V2.87bvv）の機能を統合したメジャーバージョン。
   Open JTalk 系（Pi ノード）と VOICEVOX 系ノードの「共用」ダッシュボード。
   VOICEVOX 未導入ノードでは話者変更・読み上げ内容編集の UI を自動的に隠す
   （voicevox_available() 判定）ため、jtalk ノードに置いても従来どおり動作する。
   ※ 共用ファイルのため、版番号に "vv" サフィックスは付けない
     （vv 規約は VOICEVOX 系ノード固有のファイルにのみ適用する）。

 ■ 変更履歴
   V2 系の詳細な変更履歴（V2.0〜V2.87bvv）は本ファイルには含めず、リポジトリの
   Changelog（ダッシュボードセクション）へ分離した（dvswitch_bot.py V1.92 と
   同じ整理方針）。改修時はそちらを参照のこと。

 【V3.11 の要点（V3.1 からの変更）】
  1. 🔵 「保存して再生成」ボタンを保存行の右端へ移動（CSS のみ・row-reverse）。
     7項目テーブル直下の左端では見落とされやすく、一括保存と取り違えて
     /save_all を押してしまう実運用フィードバックへの対応。

 【V3.1 の要点（V3.0 からの変更）】
  1. 🔵 読み上げテキスト編集を Open JTalk（Pi）ノードでも可能にした（共用対応の拡張）。
     従来は読み上げ内容カードの入力UI全体を voicevox_available() で隠していたが、
     テキスト7項目（コールサイン/読み・地名・メッセージ1,2/読み）の編集は jtalk でも
     出すようにした（話者選択のみ従来どおり VOICEVOX ノード限定）。
  2. 🔵 /wav_source_config を jtalk / VOICEVOX で分岐。jtalk では話者(voice)を検証・
     記録せず、bot 再起動もしない（固定WAVは bot が送出のたび読み直すため）。VOICEVOX
     ノードの挙動（話者記録＋話者変更時のみ再起動）は V3.0 と不変。
     ※ jtalk 側は create_wav.sh V1.2 以降（--regen 対応）が必要。
  3. 🔵 保存ヒットの文言と保存後メッセージを jtalk / VOICEVOX で出し分け。

 【V3.2 の要点（V3.11 からの変更）】
  1. 🔵 天気読み上げ（JTW版）の設定に対応。Bot設定カードの下に「天気読み上げ」
     カードを新設し、次を編集できるようにした。
       WEATHER_ENABLED         天気読み上げの親スイッチ
       WEATHER_ON_TIME_SIGNAL  時報（:00）・30分案内（:30）に付ける
       WEATHER_ON_MESSAGE      定時メッセージ（001/002）に付ける
       WEATHER_LATITUDE / WEATHER_LONGITUDE  取得座標
     付与先を系統ごとに選べるのは dvswitch_bot.py V2.04jtw / bot_setup.py V2.04jtw
     から。検証条件（付与先が1つも無ければ不可・座標必須・範囲）は三者で同一。
  2. 🔵 JTW ノード以外では天気カードを丸ごとグレーアウトし、注記のみ表示する
     （共有ダッシュボードの流儀。VOICEVOX 話者変更 UI と同じ考え方）。
     判定は jtw_available(): bin/voice_make.py が存在する、または bot の版文字列に
     "jtw" を含む。片方が取得できなくても拾えるよう OR で判定する。
  3. 🔴 未知キー保護を追加（V3.11 以前の欠陥の修正）。従来の保存ルートは
     bot_config.json を「ダッシュボードが知っているキーだけ」で作り直していたため、
     JTW ノードで保存すると WEATHER_* が黙って消えていた（JTW版 README の警告は
     この挙動を指す）。V3.2 では既存ファイルを土台にして差分更新するため、
     ダッシュボードが知らないキーは保存しても失われない。将来 bot 側にキーが
     増えても、ダッシュボードを更新するまでの間に設定を壊さない。
  4. 🔵 bot_config.json の組み立て・検証を build_bot_cfg() / validate_bot_cfg() に
     集約し、/bot_config と /save_all の重複（従来2箇所に同じ dict と assert が
     並んでいた）を解消した。検証条件の追加漏れが起きない構造にする。

 【V3.0 の要点（V2.87bvv からの変更）】
  1. 🔵 V2 系機能の統合・整理。機能セットは V2.87bvv と同一
     （3カード一括保存 / 順序再起動 / 時刻案内モード / TX_GAIN / カスタム音声 /
      読み上げ内容の表示・統合編集 / 話者変更＋--regen 再生成 / 外部リンク）。
     長大な変更履歴を Changelog へ分離し、版表記を機械可読の __version__ に
     一元化した。テンプレートは context_processor 経由の {{ app_version }} で
     参照するため、版更新箇所は docstring と __version__ の2箇所のみ。
  2. 🔵 テスト送信機能を追加。サービス制御カード（変更モード）から、固定WAV
     （fixed_intro / fixed_outro / time_intro / 001 / 002。実在すれば cstm_*.wav
      も選択可）を選んで単発送信できる（POST /test_send → bin/test_send.py 実行）。
     設計判断: bot は停止しない。停止→再開すると起動アナウンス（「起動しました。」）
     が送出されてしまうため。bot の送信はカーチャンク応答・時報・定時メッセージの
     発火時のみなので、発火時刻直前を避ければ実用上衝突しない（confirm で注意喚起）。
  3. 🔵 label の CSS typo 修正（display:blockcolor → display:block;color）。
     V2.58 / V2.59 の typo 修正と同系統。入力ラベルが本来意図の淡色表示になる。

 【対応バージョン】
   dvswitch_bot.py : V2.04jtw 以降（JTW 系。天気の付与先を系統ごとに指定するため。
                     V2.03jtw 以前でも保存は壊れないが、付与先の指定は無視され
                     全定時音声へ一様付与になる）
                   : V1.96vv 以降（VOICEVOX 系）/ V1.93 以降（Open JTalk 系。
                     読み上げ内容編集のための bot 改修は不要 — 固定WAVを送出時に
                     読み直し、キャッシュも mtime で自動無効化するため）
   create_wav.sh   : --regen 対応版が必要（VOICEVOX 系: V1.3avv 以降 /
                     Open JTalk 系: V1.2 以降）。読み上げ内容編集・話者変更に必要
   vv_say.py       : V2.0vv 以降（VOICEVOX 系のみ）
   test_send.py    : リポジトリ版（テスト送信機能が bin/test_send.py を実行する）

 配置:
   /opt/dvswitch_bot/web/app.py

 アクセス:
   http://<RPi-IP>:8081/
================================================================================
"""

# ============================================================
# 🔵 機械可読バージョン（固定行 / V3.0 で導入）
# ============================================================
# 版を上げるときは docstring の表記と必ず一致させること。
# テンプレートのヘッダ/フッタは context_processor 経由（{{ app_version }}）で
# この値を参照するため、テンプレート内に版のベタ書きはない。
__version__ = "V3.2"

import os, json, re, subprocess, glob, time, wave, contextlib
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

# qqq パス設定 qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq
BOT_CONFIG   = "/opt/dvswitch_bot/bot_config.json"
CHANGE_LOG   = "/opt/dvswitch_bot/bot_change_log.json"
WAV_SOURCE   = "/opt/dvswitch_bot/wav_source.json"
MMDVM_INI    = "/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
DVSWITCH_INI = "/opt/MMDVM_Bridge/DVSwitch.ini"
ANALOG_INI   = "/opt/Analog_Bridge/Analog_Bridge.ini"
LOG_DIR      = "/var/log/mmdvm"
BAK_ROOT     = "/opt/dvswitch_bot/bak/ini"
SERVICE_NAME = "dvswitch-bot"

# 🔵 V2.73: bot 本体スクリプトのフォールバックパス（ExecStart 取得失敗時に使用）
BOT_SCRIPT   = "/opt/dvswitch_bot/bin/dvswitch_bot.py"

# 🔵 V3.0: テスト送信（bin/test_send.py の Web 入口）関連。
# 送信対象に選べる WAV のホワイトリスト。実在するものだけ UI に出す
# （cstm_* はカスタム音声。無いノードでは選択肢に出ない）。
TEST_SEND_PY  = "/opt/dvswitch_bot/bin/test_send.py"
TEST_WAV_DIR  = "/opt/dvswitch_bot"
TEST_WAV_CHOICES = [
    "fixed_intro.wav", "fixed_outro.wav", "time_intro.wav",
    "001.wav", "002.wav",
    "cstm_intro.wav", "cstm_001.wav", "cstm_002.wav",
]
TEST_SEND_TIMEOUT_MARGIN_SEC = 15  # タイムアウト = WAV長 + パディング3s + この余裕

# 🔴 再起動の依存順と待機（V2.68）
# Analog_Bridge は起動時に md380-emu(AMBE) へ接続し、MMDVM_Bridge と TLV 経路を張る。
# 同時 restart だと相手未準備で経路確立に失敗するため、下から順に間隔を空けて起動する。
RESTART_ORDER   = ["md380-emu", "analog_bridge", "mmdvm_bridge"]  # bot は include_bot で末尾追加
RESTART_GAP_SEC = 3.0   # 各サービス再起動の間隔（経路確立を待つ）

# 🔴 V2.70: 時刻案内モード別の定時メッセージ(ANNOUNCE_FREQ)の有効値。
# dvswitch_bot.py V1.64 の _get_trigger_minutes() / 検証と同一の表。
#   mode0: 0/1/2/3/4   mode1: 0/1/2/3   mode2: 0/2
VALID_FREQ_BY_MODE = {0: (0, 1, 2, 3, 4), 1: (0, 1, 2, 3), 2: (0, 2)}

# 🔴 V2.74: 送出音量ゲイン TX_GAIN の有効範囲（dvswitch_bot.py V1.68 と同一基準）。
# 1.0=等倍の線形倍率。0 以下は無効、>5.0 はクリップの恐れがあるため不可。
TX_GAIN_MIN = 0.0   # これより大きいこと
TX_GAIN_MAX = 5.0   # これ以下

# 🔵 V2.86: VOICEVOX 話者変更まわり。
# 本ダッシュボードは VOICEVOX ノード（ocv-voicevox 等）と Open JTalk の Pi ノードで
# 共有する。VOICEVOX が導入されていないノードでは話者変更 UI を自動的に無効化する
# （表示は「未対応」注記のみ。他の機能はすべて従来どおり動く）。
VOICEVOX_VVM_DIR = "/opt/voicevox/dist/models/vvms"     # 話者モデル置き場
VENV_PY          = "/opt/dvswitch_bot/venv/bin/python3"  # voicevox_core を持つ venv
CREATE_WAV_SH    = "/opt/dvswitch_bot/bin/create_wav.sh" # --regen で叩く
REGEN_TIMEOUT_SEC = 300  # 再生成の上限。vv_say.py は1ファイルごとに onnx を
                         # ロードし直すため6ファイルで数十秒〜かかる余裕を見る。

def voicevox_available():
    """このノードで VOICEVOX 話者変更が使えるか（共有ダッシュボード対応）。"""
    return os.path.isdir(VOICEVOX_VVM_DIR) and os.path.exists(VENV_PY)


# 🔵 V3.2: 天気読み上げ（JTW版）まわり。
# 本ダッシュボードは JT / VV / JTW の各ノードで共有する。天気は JTW版だけの機能
# なので、非 JTW ノードでは天気カードをグレーアウトし、保存ルートでも天気キーに
# 一切触れない（VOICEVOX 話者変更 UI と同じ流儀）。
VMP_PATH = "/opt/dvswitch_bot/bin/voice_make.py"   # JTW版の天気音声生成ツール
WEATHER_LAT_MIN, WEATHER_LAT_MAX = -90.0, 90.0
WEATHER_LON_MIN, WEATHER_LON_MAX = -180.0, 180.0


def jtw_available():
    """このノードが JTW版（天気読み上げ対応）かどうか。

    判定は次の OR:
      1) /opt/dvswitch_bot/bin/voice_make.py が存在する（実体ベース・確実）
      2) bot の版文字列に "jtw" を含む（例 V2.04jtw）
    どちらか一方が取得できない状況（vmp を別パスに置いた / ExecStart から版を
    拾えない）でも拾えるよう OR にしている。ファイル存在の方が安いため先に見る。
    """
    if os.path.exists(VMP_PATH):
        return True
    return "jtw" in (get_bot_version() or "").lower()

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

# qqq ユーティリティ qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq

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
    import time as _time
    entry = {"time": _time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "changes": {}}
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


# 🔵 V2.73: 起動中の dvswitch_bot 本体のバージョン取得
def get_bot_script_path():
    """systemctl cat dvswitch-bot の ExecStart から、実際に起動している bot
    スクリプトのパスを取得する。取得できなければ BOT_SCRIPT にフォールバック。

    こうすることで /opt/dvswitch_bot/bin/dvswitch_bot.py と /opt/dvswitch_bot/
    dvswitch_bot.py のような重複ファイルがあっても、systemd が実際に起動して
    いる方の版を確実に指せる（systemctl cat は read-only なので sudo 不要）。"""
    try:
        r = subprocess.run(
            ["systemctl", "cat", SERVICE_NAME],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.splitlines():
            s = line.strip()
            if s.startswith("ExecStart="):
                # 例) ExecStart=/usr/bin/python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
                m = re.search(r"(\S+dvswitch_bot\.py)", s)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return BOT_SCRIPT

def get_bot_version():
    """bot スクリプトからバージョン（例: V1.68）を抽出する。見つからなければ空文字。
    閲覧用途のみで設定には一切影響しない。

    抽出は次の優先順で行う:
      1) __version__ = "Vx.yy"   ← bot 冒頭付近の機械可読固定行（最優先・最も堅牢）
      2) Document Version: Vx.yy ← docstring 内の人間向け表記
      3) DVSwitch Bot Vx.yy      ← 起動バナー行
    まず先頭 20000 バイトで探し、見つからなければファイル全体を読んで再探索する
    （docstring が長くなって版の行が後方へ押し出されても取りこぼさないため）。
    """
    path = get_bot_script_path()

    def _find(text):
        for pat in (
            # 行頭の代入行のみ。コメント中の「__version__ = "Vx.yy"」のような
            # 例示文字列（先頭が空白や記号で始まる）を誤検出しないよう ^ で固定する。
            r"(?m)^__version__\s*=\s*[\"'](V[\d.]+[a-z]*)[\"']",
            r"Document Version:\s*(V[\d.]+[a-z]*)",
            r"DVSwitch Bot (V[\d.]+[a-z]*)",
        ):
            m = re.search(pat, text)
            if m:
                return m.group(1)
        return ""

    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            head = f.read(20000)
    except Exception:
        return ""
    ver = _find(head)
    if ver:
        return ver
    # フォールバック: 先頭で見つからなければ全体を読んで再探索（長さ非依存）
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            full = f.read()
    except Exception:
        return ""
    return _find(full)


# 🔴 安全な順序再起動（V2.68）
def safe_restart_services(include_bot=True):
    """依存順に間隔を空けてサービスを再起動する。
       md380-emu → analog_bridge → mmdvm_bridge → (dvswitch-bot)

    同時 restart だと Analog_Bridge 起動時に相手（md380-emu / MMDVM_Bridge）が
    未準備で、TLV/AMBE 経路の確立に失敗し「音が出ない・ケロる」状態になる。
    これを防ぐため、各サービスの restart 間に RESTART_GAP_SEC の待機を挟む。

    戻り値: (ok, detail)
      ok     : 全サービスが returncode 0 なら True
      detail : 失敗したサービスとエラーの説明（OK の場合は空文字）
    """
    seq = list(RESTART_ORDER)
    if include_bot and SERVICE_NAME not in seq:
        seq.append(SERVICE_NAME)

    errors = []
    for i, svc in enumerate(seq):
        try:
            r = subprocess.run(
                ["sudo", "systemctl", "restart", svc],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                errors.append(f"{svc}: {r.stderr.strip()}")
        except Exception as e:
            errors.append(f"{svc}: {e}")
        # 最後のサービスの後は待たない
        if i < len(seq) - 1:
            time.sleep(RESTART_GAP_SEC)

    ok = (len(errors) == 0)
    return ok, "; ".join(errors)


def list_backups():
    try:
        dirs = sorted(
            [d for d in glob.glob(os.path.join(BAK_ROOT, "*")) if os.path.isdir(d)],
            reverse=True
        )
        return [os.path.basename(d) for d in dirs]
    except Exception:
        return []

# qqq ルート qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq

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
        bot_version=get_bot_version(),
        dvs=get_dvs_values(),
        info=get_info_values(),
        wav_source=get_wav_source(),
        voices=get_voice_list(),
        voicevox_ok=voicevox_available(),
        jtw_ok=jtw_available(),
        test_wavs=get_test_wavs(),
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

# 🔵 V2.78: wav_source.json（create_wav.sh が記録する読み上げソース）を読み、
# 各WAVが実際に喋る内容を表示用に整形して返す。閲覧専用。
# create_wav.sh だけが書き込み、ダッシュボードは読むだけ（bot_config.json には無関係）。
# 🔵 V2.86: 話者(voice)の表示・変更に対応（変更ルートは /voice_config）。

# 🔵 V2.86: VOICEVOX の全話者一覧を venv 側 python でスキャンして返す。
# create_wav.sh の select_voice と同じ方法（VoiceModelFile.metas のみ使用。
# Synthesizer/onnxruntime はロードしないため軽量）。結果は vvms ディレクトリの
# mtime でキャッシュし、モデル追加時は自動で再スキャンする。
_voice_cache = {"mtime": None, "list": []}

def get_voice_list():
    """[{'style_id':int,'vvm':'6.vvm','label':'No.7（アナウンス）'}, ...] を
    style_id 昇順で返す。スキャン不可（VOICEVOX 不在等）は空リスト。"""
    if not voicevox_available():
        return []
    try:
        mtime = os.path.getmtime(VOICEVOX_VVM_DIR)
    except OSError:
        return []
    if _voice_cache["mtime"] == mtime and _voice_cache["list"]:
        return _voice_cache["list"]
    script = (
        "import glob,sys\n"
        "from voicevox_core.blocking import VoiceModelFile\n"
        "recs=[]\n"
        "for p in sorted(glob.glob('" + VOICEVOX_VVM_DIR + "/*.vvm')):\n"
        "    vvm=p.rsplit('/',1)[-1]\n"
        "    try:\n"
        "        with VoiceModelFile.open(p) as m: metas=m.metas\n"
        "    except Exception: continue\n"
        "    for ch in metas:\n"
        "        for st in ch.styles:\n"
        "            recs.append((st.id,vvm,ch.name,st.name))\n"
        "recs.sort(key=lambda r:r[0])\n"
        "for sid,vvm,cn,sn in recs:\n"
        "    sys.stdout.write('%d\\x1f%s\\x1f%s（%s）\\n'%(sid,vvm,cn,sn))\n"
    )
    try:
        r = subprocess.run([VENV_PY, "-c", script],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return []
        out = []
        for line in r.stdout.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3 and parts[0].isdigit():
                out.append({"style_id": int(parts[0]), "vvm": parts[1], "label": parts[2]})
        _voice_cache["mtime"] = mtime
        _voice_cache["list"] = out
        return out
    except Exception:
        return []

# 🔵 V2.87: 英数字→カナ変換（create_wav.sh の bash 関数の Python 移植）。
# 「読み自動生成」の空欄フォールバック（サーバ側）に使う。クライアント側 JS にも
# 同じ表を移植しており、両者は必ず同一の変換結果になるよう表を揃えること。
_KANA_ALPHA = {
    "A": "エー", "B": "ビー", "C": "シー", "D": "ディー", "E": "イー", "F": "エフ",
    "G": "ジー", "H": "エイチ", "I": "アイ", "J": "ジェイ", "K": "ケー", "L": "エル",
    "M": "エム", "N": "エヌ", "O": "オー", "P": "ピー", "Q": "キュー", "R": "アール",
    "S": "エス", "T": "ティー", "U": "ユー", "V": "ブイ", "W": "ダブリュー",
    "X": "エックス", "Y": "ワイ", "Z": "ゼット",
}
# コールサイン用: 数字は英語読み（ワン、ツー…）
_KANA_DIGIT_CALLSIGN = {
    "0": "ゼロ", "1": "ワン", "2": "ツー", "3": "スリー", "4": "フォー",
    "5": "ファイブ", "6": "シックス", "7": "セブン", "8": "エイト", "9": "ナイン",
}
# メッセージ用: 数字は日本語読み（イチ、ニー…）
_KANA_DIGIT_MSG = {
    "0": "ゼロ", "1": "イチ", "2": "ニー", "3": "サン", "4": "ヨン",
    "5": "ゴー", "6": "ロク", "7": "ナナ", "8": "ハチ", "9": "キュー",
}

def callsign_to_kana(s):
    """コールサインの英数字をカナ読みへ（create_wav.sh callsign_to_kana と同一）。"""
    out = []
    for ch in s:
        u = ch.upper()
        out.append(_KANA_ALPHA.get(u) or _KANA_DIGIT_CALLSIGN.get(u) or ch)
    return "".join(out)

def msg_alphanum_to_kana(s):
    """メッセージ中の英数字をカナ読みへ（create_wav.sh msg_alphanum_to_kana と同一）。"""
    out = []
    for ch in s:
        u = ch.upper()
        out.append(_KANA_ALPHA.get(u) or _KANA_DIGIT_MSG.get(u) or ch)
    return "".join(out)

# 🔵 V2.87: 入力値から6つの読み上げテキスト(texts)を組み立てる。
# create_wav.sh の対話モードの組み立てと厳密に同一であること（三位一体と同様、
# 変更時は create_wav.sh 側と必ずセットで揃える）。
def build_wav_texts(callsign_kana, location, msg1_kana, msg2_kana):
    base = f"こちらは、{callsign_kana}、{location} ディーエムアール デジピーターです。"
    return {
        "fixed_intro": base,
        "fixed_outro": "カーチャンクです。",
        "time_intro":  f"こちらは、{callsign_kana}、",
        "001":         base + msg1_kana,
        "002":         base + msg2_kana,
        "time_outro":  "です。",
    }

# 🔵 V2.86: 読み上げテキストを「固定部分」と「入力で変えられる可変部分」に分割する。
# 可変部分＝ wav_source.json のトップレベルに記録された入力値
# （callsign_kana / location / msg1_kana / msg2_kana）。テンプレート側で可変部分だけ
# <b> 表示する（Jinja2 の自動エスケープを活かすため、HTML はここでは作らない）。
def _split_variable_segments(text, variables):
    """text を [{'t': 断片, 'v': 可変ならTrue}, ...] に分割して返す。
    variables は可変値のリスト。長い値から優先マッチ（部分文字列の誤分割を防ぐ）。"""
    vars_ = sorted({v for v in variables if v}, key=len, reverse=True)
    if not text:
        return []
    if not vars_:
        return [{"t": text, "v": False}]
    pat = re.compile("|".join(re.escape(v) for v in vars_))
    segs, pos = [], 0
    for m in pat.finditer(text):
        if m.start() > pos:
            segs.append({"t": text[pos:m.start()], "v": False})
        segs.append({"t": m.group(0), "v": True})
        pos = m.end()
    if pos < len(text):
        segs.append({"t": text[pos:], "v": False})
    return segs

def get_wav_source():
    """wav_source.json を読み、各WAVの読み上げテキストと生成時刻を返す。
    ファイルが無い/壊れている場合は空表示用の辞書を返す（存在フラグ exists=False）。
    🔵 V2.86: 話者(voice)と、可変部分を太字表示するための segments を追加。"""
    data = read_json(WAV_SOURCE)
    if not isinstance(data, dict) or not data:
        return {"exists": False, "generated_at": "", "entries": [],
                "voice_label": "", "voice_style_id": "", "voice_vvm": ""}
    texts = data.get("texts", {})
    if not isinstance(texts, dict):
        texts = {}
    # 🔵 V2.86: 可変部分（create_wav.sh の入力で変わる値）。太字表示の対象。
    variables = [
        str(data.get("callsign_kana", "") or ""),
        str(data.get("location", "") or ""),
        str(data.get("msg1_kana", "") or ""),
        str(data.get("msg2_kana", "") or ""),
    ]
    # WAVファイル名と読み上げ内容の対応（表示順を固定）。
    # 🔵 V2.81: 全6項目を表示する（V2.80 で絞った3件を再表示）。
    # time_outro は現行 bot では未使用だが、記録として併せて表示する。
    order = [
        ("fixed_intro.wav", "fixed_intro", "カーチャンク応答イントロ"),
        ("fixed_outro.wav", "fixed_outro", "カーチャンク応答アウトロ"),
        ("time_intro.wav",  "time_intro",  "時報イントロ"),
        ("001.wav",         "001",         "定時メッセージ1"),
        ("002.wav",         "002",         "定時メッセージ2"),
        ("time_outro.wav",  "time_outro",  "時報アウトロ（現行 bot 未使用）"),
    ]
    entries = []
    for fname, key, role in order:
        text = texts.get(key, "")
        entries.append({
            "file": fname,
            "role": role,
            "text": text,
            # 🔵 V2.86: 固定/可変の断片リスト。テンプレートで可変のみ <b> にする。
            "segments": _split_variable_segments(text, variables),
        })
    # 🔵 V2.86: 話者（create_wav.sh V1.2+ が voice に記録。無ければ空表示）
    voice = data.get("voice", {})
    if not isinstance(voice, dict):
        voice = {}
    return {
        "exists": True,
        "generated_at": data.get("generated_at", ""),
        "entries": entries,
        "voice_label": str(voice.get("label", "") or ""),
        "voice_style_id": str(voice.get("style_id", "") or ""),
        "voice_vvm": str(voice.get("vvm", "") or ""),
        # 🔵 V2.87: 入力値と読み仮名（Web からの編集用。CLI と同じ7項目）
        "callsign":      str(data.get("callsign", "") or ""),
        "callsign_kana": str(data.get("callsign_kana", "") or ""),
        "location":      str(data.get("location", "") or ""),
        "msg1":          str(data.get("msg1", "") or ""),
        "msg1_kana":     str(data.get("msg1_kana", "") or ""),
        "msg2":          str(data.get("msg2", "") or ""),
        "msg2_kana":     str(data.get("msg2_kana", "") or ""),
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
    return jsonify({"status": get_service_status(), "bot_version": get_bot_version()})


# 🔵 V2.87: 読み上げ内容（話者＋入力テキスト）の統合変更ルート。
# V2.86 の /voice_config（話者のみ）を置き換え。CLI（create_wav.sh 対話モード）と
# 同じ7項目の入力値＋話者を Web から一括変更し、1回の再生成にまとめる。
# 流れ: (1) 話者の選択値をスキャン結果と照合して検証（クライアント値を信用しない）
#       (2) 入力値の検証。読み仮名が空欄なら CLI と同じ変換で自動生成
#       (3) texts（6つの読み上げテキスト）を再計算（build_wav_texts。
#           create_wav.sh の組み立てと厳密に同一）
#       (4) wav_source.json を更新（入力7項目・texts・voice）
#       (5) create_wav.sh --regen で固定WAVを非対話再生成
#       (6) 話者が変わった場合のみ dvswitch-bot を再起動（bot V1.96 は起動時に
#           voice を読む）。テキストのみの変更は再起動不要（bot は送出のたびに
#           WAV を読み直す）。bridges/md380 は無関係のため常に触らない。
# 失敗時は各段階のエラーを flash 表示。--regen 失敗時も json は更新済みのため、
# もう一度保存すれば再試行できる。
@app.route("/wav_source_config", methods=["POST"])
def wav_source_config_save():
    # 🔵 V3.1: jtalk / VOICEVOX 両ノード対応。
    #   - VOICEVOX ノード: 従来どおり話者(voice)を検証・記録し、話者が変わったら
    #     bot を再起動する（動的合成が起動時に話者を読むため）。
    #   - Open JTalk（Pi）ノード: 話者は1つ（mei_normal）のため voice は扱わない。
    #     読み上げテキスト7項目のみ編集→固定WAVを --regen で作り直す。固定WAVは bot が
    #     送出のたびに読み直す（キャッシュも mtime で自動無効化）ため bot 再起動は不要。
    vv = voicevox_available()

    # (1) 話者（VOICEVOX ノードのみ検証。jtalk では voice=None のまま）
    voice = None
    if vv:
        sel = request.form.get("voice_sel", "")
        m = re.match(r"^(\d+):([\w.\-]+\.vvm)$", sel)
        if m:
            sid, vvm = int(m.group(1)), m.group(2)
            for v in get_voice_list():
                if v["style_id"] == sid and v["vvm"] == vvm:
                    voice = v
                    break
        if voice is None:
            set_flash(err="話者の選択値が不正です（一覧から選び直してください）")
            return redirect("/")

    # (2) 入力値。読み仮名の空欄は CLI と同じ規則で自動生成
    callsign = request.form.get("callsign", "").strip().upper()
    if not callsign:
        set_flash(err="コールサインを入力してください")
        return redirect("/")
    callsign_kana = request.form.get("callsign_kana", "").strip() or callsign_to_kana(callsign)
    location      = request.form.get("location", "").strip()
    if not location:
        set_flash(err="設置場所の地名を入力してください")
        return redirect("/")
    msg1      = request.form.get("msg1", "").strip()
    msg1_kana = request.form.get("msg1_kana", "").strip() or msg_alphanum_to_kana(msg1)
    msg2      = request.form.get("msg2", "").strip()
    msg2_kana = request.form.get("msg2_kana", "").strip() or msg_alphanum_to_kana(msg2)

    # (3)(4) texts 再計算と wav_source.json 更新
    data = read_json(WAV_SOURCE)
    if not isinstance(data, dict) or not isinstance(data.get("texts"), dict):
        set_flash(err="wav_source.json に texts の記録がありません。"
                      "先に create_wav.sh（対話モード）で一度WAVを作成してください")
        return redirect("/")
    # 話者変更の有無は VOICEVOX ノードのみ意味を持つ（jtalk は常に False＝再起動不要）
    voice_changed = False
    if vv:
        old_voice = data.get("voice", {}) if isinstance(data.get("voice"), dict) else {}
        voice_changed = (old_voice.get("style_id") != voice["style_id"]
                         or old_voice.get("vvm") != voice["vvm"])
    data.update({
        "callsign": callsign, "callsign_kana": callsign_kana, "location": location,
        "msg1": msg1, "msg1_kana": msg1_kana, "msg2": msg2, "msg2_kana": msg2_kana,
        "texts": build_wav_texts(callsign_kana, location, msg1_kana, msg2_kana),
    })
    # voice は VOICEVOX ノードのみ記録する（jtalk では既存キーに触れず、無ければ書かない）
    if vv:
        data["voice"] = {"style_id": voice["style_id"], "vvm": voice["vvm"],
                         "label": voice["label"]}
    write_json(WAV_SOURCE, data)

    # (5) 固定WAVを非対話再生成（create_wav.sh --regen / jtalk:V1.2+ VOICEVOX:V1.3+）
    try:
        r = subprocess.run(["sudo", CREATE_WAV_SH, "--regen"],
                           capture_output=True, text=True,
                           timeout=REGEN_TIMEOUT_SEC)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().splitlines()
            detail = tail[-1] if tail else "詳細不明"
            set_flash(err=f"WAV再生成に失敗: {detail}（入力内容は保存済み。再度保存で再試行）")
            return redirect("/")
    except subprocess.TimeoutExpired:
        set_flash(err="WAV再生成がタイムアウトしました（入力内容は保存済み）")
        return redirect("/")
    except Exception as e:
        set_flash(err=f"WAV再生成の実行に失敗: {e}")
        return redirect("/")

    # (6) 話者が変わった場合のみ bot 再起動
    if voice_changed:
        try:
            r = subprocess.run(["sudo", "systemctl", "restart", SERVICE_NAME],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                set_flash(err=f"WAVは再生成済みですが bot 再起動に失敗: {r.stderr.strip()}")
                return redirect("/")
        except Exception as e:
            set_flash(err=f"WAVは再生成済みですが bot 再起動に失敗: {e}")
            return redirect("/")
        set_flash(msg=f"読み上げ内容を保存し、話者「{voice['label']}」でWAV再生成と bot 再起動を完了しました")
    elif vv:
        set_flash(msg="読み上げ内容を保存し、WAVを再生成しました（話者変更なしのため bot 再起動は省略）")
    else:
        set_flash(msg="読み上げ内容を保存し、固定WAVを再生成しました（bot は送出時に読み直すため再起動不要）")
    return redirect("/")


@app.route("/service/<action>", methods=["POST"])
def service_ctrl(action):
    if action not in ("start", "stop", "restart"):
        set_flash(err="不正なアクション"); return redirect("/")
    ok, msg = service_action(action)
    if ok:
        set_flash(msg=f"サービスを {action} しました"); return redirect("/")
    else:
        set_flash(err=f"{action} 失敗: {msg}"); return redirect("/")

# 🔵 V3.0: テスト送信（bin/test_send.py の Web 入口）
# サービス制御カード（変更モード）から固定WAVを選んで単発送信する。
# 設計判断: bot は停止しない。停止→再開すると起動アナウンス（「起動しました。」）
# が送出されてしまうため。bot が送信するのはカーチャンク応答・時報・定時
# メッセージの発火時のみなので、発火時刻直前を避ければ実用上衝突しない
# （テンプレート側の confirm でも注意喚起する）。
def get_test_wavs():
    """テスト送信できる WAV の一覧（TEST_WAV_CHOICES のうち実在するもの）。"""
    return [f for f in TEST_WAV_CHOICES
            if os.path.exists(os.path.join(TEST_WAV_DIR, f))]


def _wav_duration_sec(path):
    """WAV の長さ（秒）。読めなければ 0.0（タイムアウトのマージンで吸収）。"""
    try:
        with contextlib.closing(wave.open(path, "rb")) as wf:
            fr = wf.getframerate()
            return (wf.getnframes() / float(fr)) if fr else 0.0
    except Exception:
        return 0.0


@app.route("/test_send", methods=["POST"])
def test_send():
    fname = request.form.get("test_wav", "")
    # 選択値はホワイトリストと照合する（クライアント値を信用しない）
    if fname not in TEST_WAV_CHOICES:
        set_flash(err="テスト送信: WAV の選択値が不正です")
        return redirect("/")
    path = os.path.join(TEST_WAV_DIR, fname)
    if not os.path.exists(path):
        set_flash(err=f"テスト送信: {fname} が見つかりません")
        return redirect("/")
    if not os.path.exists(TEST_SEND_PY):
        set_flash(err=f"テスト送信: {TEST_SEND_PY} がありません")
        return redirect("/")
    # タイムアウト = WAV長 + 前後パディング(1.5s×2) + マージン
    timeout = _wav_duration_sec(path) + 3.0 + TEST_SEND_TIMEOUT_MARGIN_SEC
    try:
        r = subprocess.run(
            ["python3", TEST_SEND_PY, path],
            capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().splitlines()
            set_flash(err=f"テスト送信に失敗: {tail[-1] if tail else '詳細不明'}")
        else:
            set_flash(msg=f"テスト送信を完了しました: {fname}")
    except subprocess.TimeoutExpired:
        set_flash(err="テスト送信がタイムアウトしました")
    except Exception as e:
        set_flash(err=f"テスト送信の実行に失敗: {e}")
    return redirect("/")


# 🔵 V3.2: bot_config.json の組み立てと検証を1箇所に集約する。
# 従来は /bot_config と /save_all に同じ dict と assert が並んでおり、条件を足す
# たびに二重メンテが必要だった（三位一体の原則を1ファイル内でも守る）。
def build_bot_cfg(form, old_cfg):
    """フォームから bot_config.json の内容を組み立てて返す。

    🔴 V3.2 未知キー保護: 既存ファイル(old_cfg)を土台にして差分更新する。
    従来は毎回まっさらな dict を作っていたため、ダッシュボードが知らないキー
    （JTW版の WEATHER_* など）が保存のたびに消えていた。土台にすることで、
    bot 側にキーが増えてもダッシュボードを更新するまで設定を壊さない。

    天気キーは JTW ノードのときだけフォームの値で上書きする。非 JTW ノードでは
    触れないため、他系統の設定ファイルを持ち込んでも値は保持される。
    """
    cfg = dict(old_cfg) if isinstance(old_cfg, dict) else {}
    cfg.update({
        "RX_DURATION_MIN_SEC": float(form["rx_min"]),
        "RX_DURATION_MAX_SEC": float(form["rx_max"]),
        "TIME_SIGNAL_MODE":    int(form.get("time_signal_mode", 1)),
        "ANNOUNCE_FREQ":       int(form["freq"]),
        "NIGHT_MODE_ENABLED":  form.get("night_enabled") == "on",
        "NIGHT_START_HOUR":    int(form["night_start"]),
        "NIGHT_END_HOUR":      int(form["night_end"]),
        "TX_GAIN":             float(form.get("tx_gain", 1.0)),
        "USE_CSTM_INTRO":      form.get("use_cstm_intro") == "on",
        "USE_CSTM_001":        form.get("use_cstm_001") == "on",
        "USE_CSTM_002":        form.get("use_cstm_002") == "on",
    })
    if jtw_available():
        cfg.update(_weather_from_form(form))
    return cfg


def _weather_from_form(form):
    """天気キーをフォームから組み立てる（JTW ノードでのみ呼ばれる）。

    座標は空欄なら辞書に入れない＝既存値を維持する（build_bot_cfg が old_cfg を
    土台にしているため）。天気 OFF のまま座標欄を空で保存しても、以前入力した
    座標は消えない（bot_setup.py が OFF でも座標を保存し続けるのと同じ思想）。
    """
    d = {
        "WEATHER_ENABLED":        form.get("weather_enabled") == "on",
        "WEATHER_ON_TIME_SIGNAL": form.get("weather_on_time_signal") == "on",
        "WEATHER_ON_MESSAGE":     form.get("weather_on_message") == "on",
    }
    lat = (form.get("weather_lat") or "").strip()
    lon = (form.get("weather_lon") or "").strip()
    if lat != "":
        d["WEATHER_LATITUDE"] = float(lat)
    if lon != "":
        d["WEATHER_LONGITUDE"] = float(lon)
    return d


def validate_bot_cfg(cfg):
    """bot_config.json の検証。問題があれば AssertionError を送出する。
    条件は dvswitch_bot.py / bot_setup.py と同一基準に揃えること（三位一体）。"""
    assert cfg["RX_DURATION_MIN_SEC"] > 0, "最小受信時間は0より大"
    assert cfg["RX_DURATION_MIN_SEC"] < cfg["RX_DURATION_MAX_SEC"], "MIN < MAX であること"
    assert cfg["TIME_SIGNAL_MODE"] in (0, 1, 2), "時刻案内モードは0/1/2"
    _vf = VALID_FREQ_BY_MODE[cfg["TIME_SIGNAL_MODE"]]
    assert cfg["ANNOUNCE_FREQ"] in _vf, f"定時メッセージは{'/'.join(map(str, _vf))}"
    assert 0 <= cfg["NIGHT_START_HOUR"] <= 23
    assert 0 <= cfg["NIGHT_END_HOUR"] <= 23
    assert TX_GAIN_MIN < cfg["TX_GAIN"] <= TX_GAIN_MAX, f"送出音量は{TX_GAIN_MIN}超〜{TX_GAIN_MAX}以下"
    _validate_weather(cfg)


def _validate_weather(cfg):
    """🔵 V3.2: 天気（JTW版）の検証。bot_setup.py V2.04jtw の validate と同一基準。

    - WEATHER_ENABLED が false／キー無しなら何も見ない（従来ノードは素通り）
    - true のときは「実際に天気を付ける先」が1つ以上あること
        時報系   : WEATHER_ON_TIME_SIGNAL かつ TIME_SIGNAL_MODE >= 1
        メッセージ系: WEATHER_ON_MESSAGE     かつ ANNOUNCE_FREQ > 0
      （V2.03jtw の「mode0 かつ freq0 は不可」を包含する一般化）
    - 座標は必須かつ範囲内
    付与先キーの既定は true（キーが無い既存設定は一様付与＝V2.03jtw と同じ）。
    """
    if not cfg.get("WEATHER_ENABLED"):
        return
    on_ts = cfg.get("WEATHER_ON_TIME_SIGNAL", True) is not False
    on_msg = cfg.get("WEATHER_ON_MESSAGE", True) is not False
    tgt_ts = on_ts and int(cfg.get("TIME_SIGNAL_MODE", 1)) >= 1
    tgt_msg = on_msg and int(cfg.get("ANNOUNCE_FREQ", 0)) > 0
    assert tgt_ts or tgt_msg, (
        "天気を付ける音声がありません"
        "（時報に付けるなら時刻案内モードを1以上に、"
        "定時メッセージに付けるなら送出する分を1つ以上にしてください）")
    try:
        lat = float(cfg["WEATHER_LATITUDE"])
        lon = float(cfg["WEATHER_LONGITUDE"])
    except (KeyError, ValueError, TypeError):
        raise AssertionError("天気を有効にするには緯度・経度が必要です（例 35.2167 / 137.0333）")
    assert WEATHER_LAT_MIN <= lat <= WEATHER_LAT_MAX, \
        f"緯度は{WEATHER_LAT_MIN}〜{WEATHER_LAT_MAX}（現在 {lat}）"
    assert WEATHER_LON_MIN <= lon <= WEATHER_LON_MAX, \
        f"経度は{WEATHER_LON_MIN}〜{WEATHER_LON_MAX}（現在 {lon}）"


@app.route("/bot_config", methods=["POST"])
def bot_config_save():
    try:
        # 🔵 V3.2: 組み立て・検証は build_bot_cfg / validate_bot_cfg に集約。
        # old_cfg は未知キー保護の土台と、変更ログの比較元を兼ねる。
        old_cfg = read_json(BOT_CONFIG)
        cfg = build_bot_cfg(request.form, old_cfg)
        validate_bot_cfg(cfg)
        write_json(BOT_CONFIG, cfg)
        append_change_log("Bot設定", old_cfg, cfg)
        set_flash(msg="Bot設定を保存しました。サービスを再起動してください。"); return redirect("/")
    except (AssertionError, ValueError, KeyError) as e:
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

        # 🔴 V2.68: 依存順＋待機つきで再起動（bot は設定変更なしなので含めない）
        ok, detail = safe_restart_services(include_bot=False)
        if ok:
            set_flash(msg=f"DVSwitch設定を保存し、サービスを順序再起動しました（バックアップ: {ts}）")
        else:
            set_flash(err=f"DVSwitch設定は保存しましたが、再起動に一部失敗: {detail}")
        return redirect("/")
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
        # 🔴 V2.68: Info 変更は MMDVM_Bridge のみで足りるが、Analog_Bridge↔MMDVM_Bridge の
        # TLV 経路を確実に張り直すため、依存順の順序再起動に統一する（bot は含めない）。
        ok, detail = safe_restart_services(include_bot=False)
        if ok:
            set_flash(msg="MMDVM Info を保存し、サービスを順序再起動しました")
        else:
            set_flash(err=f"MMDVM Info は保存しましたが、再起動に一部失敗: {detail}")
        return redirect("/")
    except (KeyError, ValueError) as e:
        set_flash(err=f"入力エラー: {e}"); return redirect("/")


@app.route("/save_all", methods=["POST"])
def save_all():
    try:
        backup_ini()

        # --- Bot設定 (bot_config.json) ---
        # 🔵 V3.2: 組み立て・検証は build_bot_cfg / validate_bot_cfg に集約
        # （/bot_config と同一処理。未知キー保護つき）。
        old_cfg = read_json(BOT_CONFIG)
        cfg = build_bot_cfg(request.form, old_cfg)
        validate_bot_cfg(cfg)
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

        # --- 🔴 V2.68: 依存順＋待機つきで全サービスを再起動（bot 含む） ---
        # 旧: systemctl restart dvswitch-bot analog_bridge mmdvm_bridge（同時）
        # 新: md380-emu → analog_bridge → mmdvm_bridge → dvswitch-bot（順序＋待機）
        ok, detail = safe_restart_services(include_bot=True)
        if ok:
            set_flash(msg="全設定を保存し、md380-emu / analog_bridge / mmdvm_bridge / dvswitch-bot を順序再起動しました")
        else:
            set_flash(err=f"全設定は保存しましたが、再起動に一部失敗: {detail}")
        return redirect("/")
    except (AssertionError, ValueError, KeyError) as e:
        set_flash(err=f"入力エラー: {e}")
        return redirect("/")

# qqq HTML テンプレート qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq

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
  /* 🔵 V3.0: typo 修正（display:blockcolor → display:block;color）。
     V2.58/V2.59 の typo 修正と同系。ラベルが本来意図の淡色・ブロック表示になる。 */
  label{display:block;color:var(--muted);margin-bottom:3px}
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
  /* 🔵 V3.2: 非対応ノードでカードごと無効化する（天気カード用）。
     view-mode の入力欄グレーアウトと同じ見え方に揃え、操作を受け付けない。 */
  .card-na .card-body{opacity:.55}
  .card-na input,.card-na select{pointer-events:none;background:#e8e8e8;color:#888}
  .wx-sub{margin-left:22px}
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
  /* モード切替で高さが変わらないよう、操作領域の高さを確保（変更モード基準で統一） */
  .svc-ctrl{display:flex;align-items:center;justify-content:flex-end;min-height:34px}
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
  /* 🔵 V2.73: bot 本体バージョン（active の右側に小さく表示） */
  .svc-ver{
    font-family:var(--mono);font-size:12px;color:var(--muted);
    margin-left:4px;letter-spacing:.03em;
  }
  /* 🔵 V3.0: テスト送信行（サービス制御カード内・変更モードのみ表示） */
  .test-send-row{display:flex;align-items:center;gap:8px;margin-top:10px;flex-wrap:wrap}

  /* 🔵 V2.85: 外部サービス（DVSwitch Dashboard / Monit）へのリンク */
  .ext-links{
    display:inline-flex;align-items:center;gap:8px;
    margin-left:16px;font-size:13px;
  }
  .ext-links a{
    color:var(--orange2);text-decoration:none;font-weight:bold;
    font-family:arial,sans-serif;
  }
  .ext-links a:hover{text-decoration:underline;color:var(--orange)}
  .ext-links .sep{color:#ccc;user-select:none}

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
  /* 閲覧専用時の入力欄：枠あり・グレーアウト */
  .view-mode input,.view-mode select{
    background:#e8e8e8;border:1px solid var(--border);
    color:#888;pointer-events:none;
  }
  .view-mode input[type=checkbox]{opacity:.5}
  .view-mode .edit-only{display:none}

  .section-title{
    color:var(--muted);
    font-family:arial,sans-serif;
    letter-spacing:.05em;
    margin-bottom:10px;padding-bottom:1px;
    border-bottom:1px solid var(--border2);
  }

  /* 🔵 V2.78: 読み上げ内容（wav_source.json）の表示専用ブロック。
     入力欄ではなく表示テキストなので、編集モードでも常にグレー系のまま。
     3カラム(grid3)の下に幅いっぱいで置く。保存・送信の対象ではない。 */
  .wav-src-table{width:100%;border-collapse:collapse;font-size:11pt}
  .wav-src-table th,.wav-src-table td{
    padding:6px 10px;border-bottom:1px solid var(--border2);text-align:left;
    vertical-align:top;
  }
  .wav-src-table th{
    background:#ededed;color:var(--muted);font-weight:bold;white-space:nowrap;
  }
  .wav-src-table tr:last-child td{border-bottom:none}
  .wav-src-file{
    font-family:var(--mono);color:var(--orange2);white-space:nowrap;
  }
  .wav-src-role{color:var(--muted);white-space:nowrap}
  /* 読み上げテキスト本体：グレーアウト表示（編集不可であることを視覚化） */
  .wav-src-text{
    font-family:var(--mono);color:#888;
    background:#e8e8e8;border:1px solid var(--border);border-radius:4px;
    padding:4px 8px;word-break:break-all;
  }
  .wav-src-empty{color:#aaa;font-style:italic}
  .wav-src-meta{color:var(--muted);font-size:10px;margin-top:8px}
  /* 🔵 V2.86: 話者行（現在の話者表示＋変更UI）と、可変部分の太字。
     読み上げテキストは編集不可を示すグレー(#888)のため、可変部分の <b> は
     濃色(#444)にして「入力で変わる場所」がひと目で分かるようにする。 */
  .voice-row{
    display:flex;align-items:center;gap:14px;flex-wrap:wrap;
    margin-bottom:10px;padding:6px 10px;
    background:#f3f3f3;border:1px solid var(--border2);border-radius:4px;
  }
  .voice-cur b{color:var(--orange2)}
  .voice-detail{color:var(--muted);font-size:10pt}
  .voice-form{display:inline-flex;align-items:center;gap:8px}
  .voice-sel{font-size:10pt;padding:2px 4px;max-width:340px}
  .wav-src-text b{color:#444;font-weight:bold}
  .wav-src-table th b{color:#444}
  /* 🔵 V2.87: 入力値と読み仮名の編集テーブル（CLI の対話7項目）。
     input は他カードと同じく view-mode の共通CSSでグレー化される。 */
  .wav-input-table{width:100%;border-collapse:collapse;font-size:11pt;margin-bottom:10px}
  .wav-input-table td{padding:4px 10px;vertical-align:middle}
  .wav-in-label{white-space:nowrap;color:var(--muted);width:210px}
  .wav-in-sub{padding-left:26px}
  /* 🔵 V2.87b: 入力枠は列幅いっぱいに伸ばし、右端を全行で揃える
     （下の読み上げ内容プレビュー表と同じ幅感）。通常/変更モード共通。 */
  .wav-input-table input{font-size:11pt;padding:3px 6px;width:100%;box-sizing:border-box}
  .wav-input-table input.wav-in-wide{width:100%}
  /* 🔵 V3.11: 保存ボタンを行の右端へ（row-reverse で DOM 先頭のボタンが右端、
     説明文がその左に並ぶ）。7項目テーブル直下の左端では見落とされやすい、
     という実運用フィードバック 2026-07-14 による配置変更。 */
  .wav-save-row{display:flex;flex-direction:row-reverse;justify-content:flex-start;align-items:center;gap:12px;margin:4px 0 12px}
  .tbtn-strong{font-weight:bold}
  /* 🔵 V2.79: 上のグリッド(grid3)との間隔を確保。カードは box-shadow(周囲8px)を
     持つため、間隔ゼロだと影同士が重なってめり込んで見える。grid3 内の gap(12px)
     より広めの 16px を空けて、影が重ならないようにする。 */
  .card-below-grid{margin-top:16px}
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">OpenCCVoice for DVSwitch Web Dashboard</div>
    <div class="tagline">{{ dvs.callsign }} / TGIF TG{{ dvs.txtg }} 管理パネル&nbsp;&nbsp;&nbsp;{{ app_version }}</div>
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
      <span class="svc-ver" id="svc-ver">{% if bot_version %}{{ bot_version }}{% endif %}</span>
      <!-- 🔵 V2.85: 外部サービスへのリンク（ホスト名は JS で補完）-->
      <span class="ext-links">
        <a id="link-dvs" href="#" target="_blank" rel="noopener">DVSwitch Dashboard</a>
        <span class="sep">|</span>
        <a id="link-monit" href="#" target="_blank" rel="noopener">Monit</a>
      </span>
      <div class="svc-ctrl" style="margin-left:auto">
        <!-- 通常モード: 変更ボタンのみ -->
        <button class="mode-link" id="btn-edit" onclick="enterEdit()">変更モード</button>
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

    <!-- 🔵 V3.0: テスト送信（変更モードのみ表示）。bin/test_send.py を実行して
         選択した固定WAVを単発送信する。bot は停止しない（停止→再開だと起動
         アナウンスが送出されるため）。時報・定時メッセージの発火時刻直前の
         実行は二重送信になり得るため避けること（confirm でも注意喚起）。 -->
    {% if test_wavs %}
    <div class="edit-only test-send-row">
      <span class="voice-detail">テスト送信:</span>
      <select name="test_wav" class="voice-sel" style="max-width:220px" form="testsend-form">
        {% for w in test_wavs %}
        <option value="{{ w }}">{{ w }}</option>
        {% endfor %}
      </select>
      <button class="tbtn" type="submit" form="testsend-form">送信</button>
      <span class="voice-detail">選択したWAVを単発送信します（完了まで画面は待機）</span>
    </div>
    {% endif %}
  </div>
</div>

<form id="save-form" method="post" action="/save_all">
<div class="grid3">

  <!-- 🔵 V3.2: 左セル＝Bot設定 + 天気読み上げ の2カード縦積み
       （中央セルの DVSwitch設定 + カスタム音声 と同じ構成にした） -->
  <div style="display:grid;gap:12px;align-content:start">
  <div class="card">
    <div class="card-head">Bot 設定 — bot_config.json</div>
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
        <div class="section-title">時刻案内（時報）</div>
        <div class="field">
          <label>時刻案内モード</label>
          <select name="time_signal_mode" id="ts_mode" onchange="rebuildFreq()">
            <option value="0" {% if bot_cfg.get('TIME_SIGNAL_MODE',1)==0 %}selected{% endif %}>0: 時刻案内しない</option>
            <option value="1" {% if bot_cfg.get('TIME_SIGNAL_MODE',1)==1 %}selected{% endif %}>1: 毎正時のみ「○○時です」</option>
            <option value="2" {% if bot_cfg.get('TIME_SIGNAL_MODE',1)==2 %}selected{% endif %}>2: 毎正時＋毎30分「○○時30分です」</option>
          </select>
        </div>
        <div class="section-title">定時メッセージ（001/002 交互）</div>
        <div class="field">
          <label>送出する分</label>
          <select name="freq" id="freq_sel"><!-- JS が時刻案内モードに応じて構築 --></select>
        </div>
        <div class="section-title">送出音量</div>
        <div class="field">
          <label>音量倍率（1.0=等倍 / 0.0超〜5.0以下）</label>
          <input type="number" name="tx_gain" step="0.05" min="0.05" max="5.0"
            value="{{ bot_cfg.get('TX_GAIN', 1.0) }}" required>
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

  <!-- 🔵 V3.2: 天気読み上げカード（Bot設定の下・左セル内）。
       JTW版（voice_make.py を持つノード）でのみ操作可能。非 JTW ノードでは
       card-na でカードごとグレーアウトし、注記だけを出す（共有ダッシュボード）。
       非 JTW ノードでは保存ルートも天気キーに触れないため、フォームに値が
       出ていても設定は書き換わらない。 -->
  <div class="card {% if not jtw_ok %}card-na{% endif %}">
    <div class="card-head">天気読み上げ — JTW版</div>
    <div class="card-body">
        {% if jtw_ok %}
        <div style="font-size:10px;color:var(--muted);margin-bottom:10px">
          定時音声の後ろに「○○の天気は、晴れ、気温は25度です」を付けます。
          地名（○○）は下の「読み上げ内容」の地名と共通です。取得は Open-Meteo。
        </div>
        {% else %}
        <div style="font-size:10px;color:var(--muted);margin-bottom:10px">
          このノードは JTW版（天気読み上げ対応）ではないため設定できません。
          表示のみで、保存しても bot_config.json の天気設定は変更されません。
        </div>
        {% endif %}
        <div class="toggle-row">
          <input type="checkbox" name="weather_enabled" id="wx_chk"
            {% if bot_cfg.get('WEATHER_ENABLED', False) %}checked{% endif %}
            {% if not jtw_ok %}disabled{% endif %}
            onchange="toggleWeather(this.checked)">
          <label class="toggle-label" for="wx_chk">天気読み上げを有効にする</label>
        </div>
        <div id="wx-fields" {% if not bot_cfg.get('WEATHER_ENABLED', False) %}style="display:none"{% endif %}>
          <div class="section-title">天気を付ける対象</div>
          <div class="toggle-row wx-sub">
            <input type="checkbox" name="weather_on_time_signal" id="wx_ts_chk"
              {% if bot_cfg.get('WEATHER_ON_TIME_SIGNAL', True) %}checked{% endif %}
              {% if not jtw_ok %}disabled{% endif %}>
            <label class="toggle-label" for="wx_ts_chk">時報（:00）・30分案内（:30）</label>
          </div>
          <div class="toggle-row wx-sub">
            <input type="checkbox" name="weather_on_message" id="wx_msg_chk"
              {% if bot_cfg.get('WEATHER_ON_MESSAGE', True) %}checked{% endif %}
              {% if not jtw_ok %}disabled{% endif %}>
            <label class="toggle-label" for="wx_msg_chk">定時メッセージ（001/002）</label>
          </div>
          <div class="section-title">取得座標</div>
          <div class="row2">
            <div class="field">
              <label>緯度（-90〜90）</label>
              <input type="text" name="weather_lat" placeholder="{{ info.lat or '35.2167' }}"
                value="{{ bot_cfg.get('WEATHER_LATITUDE', '') }}"
                {% if not jtw_ok %}disabled{% endif %}>
            </div>
            <div class="field">
              <label>経度（-180〜180）</label>
              <input type="text" name="weather_lon" placeholder="{{ info.lon or '137.0333' }}"
                value="{{ bot_cfg.get('WEATHER_LONGITUDE', '') }}"
                {% if not jtw_ok %}disabled{% endif %}>
            </div>
          </div>
          <div style="font-size:10px;color:var(--muted)">
            空欄で保存すると、以前の座標をそのまま維持します。
            未設定のまま有効にはできません（MMDVM Info の緯度経度を目安に入力）。
          </div>
        </div>
    </div>
  </div>

  </div>
  <!-- /左セル -->

  <!-- 🔵 V2.83: 中央セル＝DVSwitch設定 + カスタム音声 の2カード縦積み -->
  <div style="display:grid;gap:12px;align-content:start">
  <div class="card">
    <div class="card-head">DVSwitch 設定 — ini ファイル</div>
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

  <!-- 🔵 V2.83: カスタム音声カード（DVSwitch設定の下・中央セル内） -->
  <div class="card">
    <div class="card-head">カスタム音声 — 差し替え</div>
    <div class="card-body">
        <div style="font-size:10px;color:var(--muted);margin-bottom:10px">
          ON にすると標準の代わりに cstm_*.wav を再生します。ファイルが無ければ
          自動的に標準音声で鳴ります（要: 利用者がファイルを用意）。
        </div>
        <div class="toggle-row">
          <input type="checkbox" name="use_cstm_intro" id="cstm_intro_chk"
            {% if bot_cfg.get('USE_CSTM_INTRO', False) %}checked{% endif %}>
          <label class="toggle-label" for="cstm_intro_chk">intro（名乗り）に cstm_intro.wav を使う</label>
        </div>
        <div class="toggle-row">
          <input type="checkbox" name="use_cstm_001" id="cstm_001_chk"
            {% if bot_cfg.get('USE_CSTM_001', False) %}checked{% endif %}>
          <label class="toggle-label" for="cstm_001_chk">001 に cstm_001.wav を使う</label>
        </div>
        <div class="toggle-row">
          <input type="checkbox" name="use_cstm_002" id="cstm_002_chk"
            {% if bot_cfg.get('USE_CSTM_002', False) %}checked{% endif %}>
          <label class="toggle-label" for="cstm_002_chk">002 に cstm_002.wav を使う</label>
        </div>
    </div>
  </div>

  </div>
  <!-- /中央セル -->

  <!-- MMDVM Info -->
  <div class="card">
    <div class="card-head">MMDVM Info — MMDVM_Bridge.ini [Info]</div>
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

<!-- 🔵 V2.78: 読み上げ内容（wav_source.json）— 3カラムの下に幅いっぱいで表示。
     create_wav.sh が記録した各WAVの実際の読み上げ内容。閲覧専用（編集不可）。
     🔵 V2.79: 上グリッドとの間隔確保のため card-below-grid（margin-top:16px）を付与。 -->
<div class="card card-below-grid">
  <div class="card-head">読み上げ内容 — wav_source.json</div>
  <div class="card-body">
    {% if wav_source.exists %}
    <!-- 🔵 V2.86: 話者（音声キャラクター）の表示と変更。
         🔵 V2.87: 話者に加え、入力値7項目（コールサイン/読み・地名・メッセージ1,2/読み）
         の編集を統合。保存は1ボタン（保存して再生成）→ /wav_source_config へ POST し、
         wav_source.json 更新 → create_wav.sh --regen →（話者変更時のみ）bot 再起動。
         表示は常時、編集UIは変更モードのみ（edit-only）。VOICEVOX 未導入ノード
         （Open JTalk の Pi ノード等）では編集UIを出さず注記のみ（共有ダッシュボード対応）。
         save-form（一括保存）とは独立のため、フォーム入れ子を避けて HTML5 の form
         属性で外部の wavsrc-form（save-form 閉じタグ直後に定義）へ関連付ける。 -->
    <div class="voice-row">
      <span class="voice-cur">現在の話者:
        {% if wav_source.voice_label %}
          <b>{{ wav_source.voice_label }}</b>
          <span class="voice-detail">(style_id={{ wav_source.voice_style_id }} / {{ wav_source.voice_vvm }})</span>
        {% else %}
          <span class="voice-detail">記録なし（既定 No.7〔アナウンス〕で生成されています）</span>
        {% endif %}
      </span>
      {% if voicevox_ok and voices %}
      <span class="edit-only voice-form">
        <select name="voice_sel" class="voice-sel" form="wavsrc-form">
          {% for v in voices %}
          <option value="{{ v.style_id }}:{{ v.vvm }}"
            {% if wav_source.voice_style_id == v.style_id|string and wav_source.voice_vvm == v.vvm %}selected{% endif %}>
            {{ v.label }}（{{ v.style_id }} / {{ v.vvm }}）
          </option>
          {% endfor %}
        </select>
      </span>
      {% elif not voicevox_ok %}
      <span class="voice-detail">（このノードは VOICEVOX 未導入のため変更は不可）</span>
      {% endif %}
    </div>
    {# 🔵 V3.1: 読み上げテキストの編集は jtalk / VOICEVOX 両ノードで可能にする
       （voicevox_ok に依存しない）。話者選択のみ上の voice-row で voicevox_ok に
       応じて出し分ける。VOICEVOX 未導入ノードでは voice を書かず、bot 再起動もしない
       （/wav_source_config 側で分岐）。 #}
    <!-- 🔵 V2.87: 入力値と読み仮名（CLI の対話項目と同じ7項目）。
         通常モードでは view-mode の共通CSSでグレー表示（他カードの入力欄と同じ挙動）。
         「読み自動生成」は CLI のプリフィルと同じ変換を JS で行う（表はサーバ側と同一）。
         読み欄を空で保存した場合もサーバ側で同じ変換により自動生成される。 -->
    <table class="wav-input-table">
      <tbody>
        <tr>
          <td class="wav-in-label">1. コールサイン</td>
          <td><input type="text" name="callsign" id="ws-callsign" form="wavsrc-form"
                     value="{{ wav_source.callsign }}"></td>
        </tr>
        <tr>
          <td class="wav-in-label wav-in-sub">→ 読み仮名
              <button type="button" class="tbtn edit-only" onclick="autoKana('callsign')">自動生成</button></td>
          <td><input type="text" name="callsign_kana" id="ws-callsign-kana" form="wavsrc-form"
                     class="wav-in-wide" value="{{ wav_source.callsign_kana }}"></td>
        </tr>
        <tr>
          <td class="wav-in-label">2. 設置場所の地名</td>
          <td><input type="text" name="location" id="ws-location" form="wavsrc-form"
                     value="{{ wav_source.location }}"></td>
        </tr>
        <tr>
          <td class="wav-in-label">3. 定時メッセージ1</td>
          <td><input type="text" name="msg1" id="ws-msg1" form="wavsrc-form"
                     class="wav-in-wide" value="{{ wav_source.msg1 }}"></td>
        </tr>
        <tr>
          <td class="wav-in-label wav-in-sub">→ 読み
              <button type="button" class="tbtn edit-only" onclick="autoKana('msg1')">自動生成</button></td>
          <td><input type="text" name="msg1_kana" id="ws-msg1-kana" form="wavsrc-form"
                     class="wav-in-wide" value="{{ wav_source.msg1_kana }}"></td>
        </tr>
        <tr>
          <td class="wav-in-label">4. 定時メッセージ2</td>
          <td><input type="text" name="msg2" id="ws-msg2" form="wavsrc-form"
                     class="wav-in-wide" value="{{ wav_source.msg2 }}"></td>
        </tr>
        <tr>
          <td class="wav-in-label wav-in-sub">→ 読み
              <button type="button" class="tbtn edit-only" onclick="autoKana('msg2')">自動生成</button></td>
          <td><input type="text" name="msg2_kana" id="ws-msg2-kana" form="wavsrc-form"
                     class="wav-in-wide" value="{{ wav_source.msg2_kana }}"></td>
        </tr>
      </tbody>
    </table>
    <div class="edit-only wav-save-row">
      <button class="tbtn tbtn-strong" type="submit" form="wavsrc-form">保存して再生成（WAV作り直し）</button>
      <span class="voice-detail">再生成には数十秒かかります。{% if voicevox_ok %}話者を変えた場合は bot も自動再起動します。{% else %}固定WAVの入れ替えのみのため bot の再起動は不要です。{% endif %}</span>
    </div>
    <table class="wav-src-table">
      <thead>
        <tr>
          <th>WAVファイル</th>
          <th>用途</th>
          <th>読み上げ内容（<b>太字</b>＝入力で変えられる可変部分）</th>
        </tr>
      </thead>
      <tbody>
        {% for it in wav_source.entries %}
        <tr>
          <td class="wav-src-file">{{ it.file }}</td>
          <td class="wav-src-role">{{ it.role }}</td>
          <td>
            {% if it.text %}
            <!-- 🔵 V2.86: 固定部分は従来表示、可変部分（コールサイン読み・地名・
                 メッセージ読み）のみ <b> で強調。segments はサーバ側で分割済み。 -->
            <div class="wav-src-text">{% for s in it.segments %}{% if s.v %}<b>{{ s.t }}</b>{% else %}{{ s.t }}{% endif %}{% endfor %}</div>
            {% else %}
            <span class="wav-src-empty">（記録なし）</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% if wav_source.generated_at %}
    <div class="wav-src-meta">生成日時: {{ wav_source.generated_at }}　/　create_wav.sh で作成・記録</div>
    {% endif %}
    {% else %}
    <div class="wav-src-empty">
      wav_source.json がまだありません。create_wav.sh でWAVを作成すると、
      ここに各WAVの読み上げ内容が表示されます。
    </div>
    {% endif %}
  </div>
</div>



<div style="text-align:center;font-size:9px;color:var(--muted);margin-top:4px">
  OpenCCVoice for DVSwitch Web Dashboard {{ app_version }}
</div>
</form>

<!-- 🔵 V2.87: 読み上げ内容（話者＋テキスト）保存フォーム本体。save-form の外に置き、
     カード内の select/input/button から form="wavsrc-form" 属性で関連付ける（入れ子回避）。 -->
<form id="wavsrc-form" method="post" action="/wav_source_config"
      onsubmit="return confirm('読み上げ内容を保存し、固定WAVの再生成を行います。\n（話者を変えた場合は bot も再起動します）\n再生成には数十秒かかることがあります。よろしいですか？');"></form>

<!-- 🔵 V3.0: テスト送信フォーム本体（コントロールはサービス制御カード内。
     form 属性で関連付け。フォーム入れ子を避ける方式は wavsrc-form と同じ） -->
<form id="testsend-form" method="post" action="/test_send"
      onsubmit="return confirm('選択したWAVをテスト送信します。\n時報・定時メッセージの発火時刻直前は避けてください。\nよろしいですか？');"></form>

</main>

<script>
// 🔵 V2.85: 外部サービスのリンクを、今開いているホスト名で組み立てる。
// LAN でも Tailscale でも、アクセス中の経路に応じた正しいリンクになる。
// DVSwitch Dashboard = ポート80（番号なし） / Monit = ポート2812。
(function(){
  var host = window.location.hostname;  // 例 192.168.1.66 / 100.x / ホスト名
  var dvs = document.getElementById("link-dvs");
  var monit = document.getElementById("link-monit");
  if(dvs)   dvs.href   = "http://" + host + "/";
  if(monit) monit.href = "http://" + host + ":2812/";
})();
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
    const v=document.getElementById("svc-ver");
    if(v && d.bot_version!==undefined){v.textContent=d.bot_version||"";}
  });
}
setInterval(refreshStatus,20000);
function toggleNight(on){
  document.getElementById("night-fields").style.display=on?"":"none";
}
// 🔵 V3.2: 天気読み上げの詳細（付与先・座標）を親スイッチに連動して開閉する
// （ナイトモードの toggleNight と同じ流儀）。
function toggleWeather(on){
  var el=document.getElementById("wx-fields");
  if(el) el.style.display=on?"":"none";
}

// 🔴 V2.70: 定時メッセージの選択肢を時刻案内モードに連動させる
// （dvswitch_bot.py V1.64 の _get_trigger_minutes と同一の対応表）
var INIT_FREQ = {{ bot_cfg.get('ANNOUNCE_FREQ', 2) }};
var FREQ_OPTS = {
  0: [[0,"0: なし"],[1,"1: :00"],[2,"2: :00 :30"],[3,"3: :00 :20 :40"],[4,"4: :00 :15 :30 :45"]],
  1: [[0,"0: なし"],[1,"1: :30"],[2,"2: :20 :40"],[3,"3: :15 :30 :45"]],
  2: [[0,"0: なし"],[2,"2: :15 :45"]]
};
function rebuildFreq(){
  var mode = parseInt(document.getElementById("ts_mode").value,10);
  var sel  = document.getElementById("freq_sel");
  // 既に選択がある場合はそれを、初回(空)は保存値を引き継ぐ
  var prev = (sel.value!=="") ? parseInt(sel.value,10) : INIT_FREQ;
  var opts = FREQ_OPTS[mode] || [];
  sel.innerHTML="";
  var matched=false;
  opts.forEach(function(o){
    var op=document.createElement("option");
    op.value=o[0]; op.textContent=o[1];
    if(o[0]===prev){op.selected=true;matched=true;}
    sel.appendChild(op);
  });
  // 旧モードの値が新モードに無ければ先頭(0=なし)へ丸める
  if(!matched && sel.options.length>0){sel.options[0].selected=true;}
}
rebuildFreq();
function enterEdit(){
  document.getElementById("main").classList.remove("view-mode");
  document.getElementById("btn-edit").style.display="none";
  document.getElementById("edit-buttons").style.display="inline-flex";
}
function cancelEdit(){
  // 変更を破棄して通常モードへ（再読み込みで元の値に戻す）
  location.href="/";
}

// 🔵 V2.87: 英数字→カナ変換（create_wav.sh / app.py サーバ側と同一の表）。
// 「読み自動生成」ボタンで CLI のプリフィルと同じ体験を提供する。
var KANA_ALPHA = {A:"エー",B:"ビー",C:"シー",D:"ディー",E:"イー",F:"エフ",
  G:"ジー",H:"エイチ",I:"アイ",J:"ジェイ",K:"ケー",L:"エル",M:"エム",N:"エヌ",
  O:"オー",P:"ピー",Q:"キュー",R:"アール",S:"エス",T:"ティー",U:"ユー",V:"ブイ",
  W:"ダブリュー",X:"エックス",Y:"ワイ",Z:"ゼット"};
var KANA_DIGIT_CS  = {"0":"ゼロ","1":"ワン","2":"ツー","3":"スリー","4":"フォー",
  "5":"ファイブ","6":"シックス","7":"セブン","8":"エイト","9":"ナイン"};
var KANA_DIGIT_MSG = {"0":"ゼロ","1":"イチ","2":"ニー","3":"サン","4":"ヨン",
  "5":"ゴー","6":"ロク","7":"ナナ","8":"ハチ","9":"キュー"};
function toKana(s, digitMap){
  var out = "";
  for (var i = 0; i < s.length; i++){
    var u = s[i].toUpperCase();
    out += KANA_ALPHA[u] || digitMap[u] || s[i];
  }
  return out;
}
// which: 'callsign'（数字は英語読み） / 'msg1' / 'msg2'（数字は日本語読み）
function autoKana(which){
  var srcId  = "ws-" + which;
  var dstId  = "ws-" + which + "-kana";
  var src = document.getElementById(srcId);
  var dst = document.getElementById(dstId);
  if(!src || !dst) return;
  var map = (which === "callsign") ? KANA_DIGIT_CS : KANA_DIGIT_MSG;
  dst.value = toKana(src.value, map);
}
</script>
</body>
</html>
"""

@app.context_processor
def inject_globals():
    # 🔵 V3.0: 版表記の一元化。テンプレートは {{ app_version }} でこの値を参照する。
    return {"service_name": SERVICE_NAME, "app_version": __version__}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False, threaded=True)
