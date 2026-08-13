#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 bot_setup.py — DVSwitch Bot 設定ツール（JTW版 / V2.04jtw）
   dvswitch_bot.py（デーモン版）が読む設定ファイル
   /opt/dvswitch_bot/bot_config.json を対話で作成・更新する。

 dvswitch_bot.py 本体は対話を持たず、この設定ファイルを読むだけ。
 設定が無い / 不正だと本体は安全のため起動を拒否する（フェイルセーフ）。
 そのため、常駐させる前に必ず本ツールで設定を作成すること。

【対話で設定する項目】
   RX_DURATION_MIN_SEC : 最小受信時間（秒, 0 < MIN < MAX）
   RX_DURATION_MAX_SEC : 最大受信時間（秒, カーチャンク上限）
   TIME_SIGNAL_MODE    : 時刻案内モード（0=なし / 1=毎正時 / 2=毎正時+毎30分）
   ANNOUNCE_FREQ       : 定時メッセージ（001/002交互）の頻度
                         ※選択肢は TIME_SIGNAL_MODE に依存
                           mode0: 0/1/2/3/4  mode1: 0/1/2/3  mode2: 0/2
   NIGHT_MODE_ENABLED  : ナイトモード（true / false）
   NIGHT_START_HOUR    : ナイトモード開始 N1（0〜23）
   NIGHT_END_HOUR      : ナイトモード終了 N2（0〜23）
   TX_GAIN             : 送出音量の倍率（1.0=等倍, 0.0超〜5.0以下。下げる方向が主用途）
   USE_CSTM_INTRO      : intro にカスタム音声 cstm_intro.wav を使う（true/false）
   USE_CSTM_001        : 001 にカスタム音声 cstm_001.wav を使う（true/false）
   USE_CSTM_002        : 002 にカスタム音声 cstm_002.wav を使う（true/false）
                         ※カスタム選択時にファイルが無ければ本体が標準へ自動フォールバック
                         ※カスタムファイルは利用者が /opt/dvswitch_bot/ 直下に用意する
   WEATHER_ENABLED     : 天気読み上げの親スイッチ
                         （true/false, JTW版 V2.03jtw〜。取得・合成は voice_make.py）
   WEATHER_ON_TIME_SIGNAL : 時報（:00）・30分案内（:30）に天気を付ける
                         （true/false, 任意キー。既定 true。JTW版 V2.04jtw〜）
   WEATHER_ON_MESSAGE  : 定時メッセージ（001/002）に天気を付ける
                         （true/false, 任意キー。既定 true。JTW版 V2.04jtw〜）
   WEATHER_LATITUDE    : 天気取得の緯度（有効時のみ。例 35.2167）
   WEATHER_LONGITUDE   : 天気取得の経度（有効時のみ。例 137.0333）
                         ※WEATHER_ENABLED=true でも、付与先（時報系/メッセージ系）が
                           1つも無い設定は不可（本体が起動拒否）

【配置】
   /opt/dvswitch_bot/bin/bot_setup.py

【使い方】
   sudo python3 /opt/dvswitch_bot/bin/bot_setup.py        対話で作成・更新（既存値があれば初期表示）
   sudo python3 /opt/dvswitch_bot/bin/bot_setup.py -s     現在の設定を表示するだけ
   sudo python3 /opt/dvswitch_bot/bin/bot_setup.py -h     ヘルプ

 ※ /opt/dvswitch_bot/ への書き込みのため sudo 推奨。

 【版履歴（本ツール）】
   V2.04jtw : 天気の付与先を「時報系（:00/:30）」と「定時メッセージ系（001/002）」で
              個別に選べるようにした（WEATHER_ON_TIME_SIGNAL / WEATHER_ON_MESSAGE）。
              どちらも任意キーで既定 true のため、キーの無い既存設定は V2.03jtw と
              完全に同一の動作（全定時音声へ一様付与）になる。付与先が存在しない系統
              （時刻案内 OFF / 定時メッセージ 0 回）は対話で問わず OFF 固定にする。
              検証は「付与先が1つも無ければエラー」に一般化（V2.03jtw の
              「mode0 かつ freq0 は不可」を包含する）。
              ※本体 dvswitch_bot.py V2.04jtw / ダッシュボード app.py V3.2 と対で運用する。
   V2.03jtw : 定時音声の生成が voice_make.py（vmp）へ分離されたことに追随。
              WEATHER_HOURS（時刻絞り）を廃止（全定時音声へ一様付与）。天気の
              併用不可条件を「時報も定時メッセージも無い（mode0 かつ freq0）」に修正。
   V2.02jtw : 天気の座標初期値を MMDVM_Bridge.ini [Info] から補完（Enter で採用）。
              機械可読 __version__ 行を新設（以後ダッシュボード等から版を追える）。
   V2.00jtw : 天気読み上げ（WEATHER_*）の対話設定・既存キー引き継ぎに対応。
   （本体 dvswitch_bot.py の版とは独立。本体は V2.01jtw 以降と組み合わせる。）
================================================================================
"""

# ============================================================
# 🔵 機械可読バージョン（固定行 / ダッシュボード等が参照可能）
# ============================================================
# 本体 dvswitch_bot.py の __version__ と同じ流儀。bot_setup.py 側の変更で
# 版を上げるときはこの文字列と上の docstring 版履歴を一致させること。
__version__ = "V2.04jtw"

import os
import sys
import json

BOT_DIR = "/opt/dvswitch_bot"
CONFIG_PATH = f"{BOT_DIR}/bot_config.json"

# デフォルト値（V1.60 のコード初期値に準拠 / TX_GAIN は V1.68 / USE_CSTM_* は V1.73）
DEFAULTS = {
    "RX_DURATION_MIN_SEC": 0.5,
    "RX_DURATION_MAX_SEC": 3.9,
    "TIME_SIGNAL_MODE": 1,
    "ANNOUNCE_FREQ": 2,
    "NIGHT_MODE_ENABLED": True,
    "NIGHT_START_HOUR": 22,
    "NIGHT_END_HOUR": 5,
    "TX_GAIN": 1.0,
    "USE_CSTM_INTRO": False,
    "USE_CSTM_001": False,
    "USE_CSTM_002": False,
    "WEATHER_ENABLED": False,
    # 🔵 V2.04jtw: 天気の付与先。既定 true（＝キーが無い既存設定は V2.03jtw と
    # 同じ「全定時音声へ一様付与」になる）。WEATHER_ENABLED=false のときは効かない。
    "WEATHER_ON_TIME_SIGNAL": True,
    "WEATHER_ON_MESSAGE": True,
}

# 🔵 V2.00jtw: 天気読み上げの座標・対象時刻。DEFAULTS に置かない（土地の既定値を
# 持たせると、第三者局が Enter 連打で他所の天気を放送する事故になるため）。
# 既存 config に在れば do_edit が base に引き継ぎ、OFF に切り替えても値は保存し
# 続ける（再度 ON にしたとき前回の座標が初期表示される）。
_WEATHER_EXTRA_KEYS = ("WEATHER_LATITUDE", "WEATHER_LONGITUDE")

# 🔵 V2.00jtw: 座標の初期値ソース。bot_config.json に無い場合は
# MMDVM_Bridge.ini の [Info] Latitude/Longitude から引く（V1.94 の
# コールサイン ini 自動取得と同じ「真実の源の一本化」）。ただし DVSwitch
# 配布 ini の既定値（41.7333, -50.3999 = 北大西洋のプレースホルダ）と
# (0, 0) は「未設定」とみなして採用しない。
_MMDVM_INI_PATH = "/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
_INI_PLACEHOLDER_COORDS = ((41.7333, -50.3999), (0.0, 0.0))


def _read_ini_value(path, key):
    """ini から最初に現れる `key = value` の値を返す（無ければ None）。
    dvswitch_bot.py の _read_ini_value と同じ流儀。"""
    import re as _re
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s.startswith((";", "#", "[")):
                    continue
                m = _re.match(rf"^{_re.escape(key)}\s*=\s*(.*)$", s)
                if m:
                    val = m.group(1).split(";")[0].strip()
                    return val or None
    except OSError:
        pass
    return None


def _ini_coords():
    """MMDVM_Bridge.ini [Info] の座標を (lat, lon) で返す。
    読めない・プレースホルダ・範囲外なら None。"""
    lat_s = _read_ini_value(_MMDVM_INI_PATH, "Latitude")
    lon_s = _read_ini_value(_MMDVM_INI_PATH, "Longitude")
    try:
        lat, lon = float(lat_s), float(lon_s)
    except (TypeError, ValueError):
        return None
    if (lat, lon) in _INI_PLACEHOLDER_COORDS:
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return None
    return lat, lon

REQUIRED_KEYS = list(DEFAULTS.keys())

# 送出音量ゲイン TX_GAIN の有効範囲（dvswitch_bot.py V1.68 と同一基準）。
# 1.0=等倍。0 以下は無効、>5.0 はクリップの恐れがあるため不可。
TX_GAIN_MIN = 0.0   # これより大きいこと
TX_GAIN_MAX = 5.0   # これ以下

# 任意キー（既定あり）。本体 dvswitch_bot.py と同様に「必須」とはしないため、
# 既存ファイルの欠落チェック対象から外す（旧 config を不正と誤判定しない）。
# DEFAULTS には残すので、新規作成・保存時は常にこれらを含めて書き出す。
#   TX_GAIN        : V1.68 で追加
#   USE_CSTM_*     : V1.73 で追加（intro/001/002 のカスタム音声選択）
#   WEATHER_*      : V2.00jtw で追加（時報への当地天気読み上げ / JTW版）
#   WEATHER_ON_*   : V2.04jtw で追加（天気の付与先の個別指定）
_OPTIONAL_KEYS = ("TX_GAIN", "USE_CSTM_INTRO", "USE_CSTM_001", "USE_CSTM_002",
                  "WEATHER_ENABLED", "WEATHER_ON_TIME_SIGNAL", "WEATHER_ON_MESSAGE")
REQUIRED_KEYS = [k for k in DEFAULTS if k not in _OPTIONAL_KEYS]


# ------------------------------------------------------------
# 検証（dvswitch_bot.py の _load_config と同じ基準）
# ------------------------------------------------------------
def validate(cfg):
    """設定 dict を検証。問題があればエラーメッセージのリストを返す（空なら正常）。"""
    errors = []

    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        errors.append(f"必須キー不足: {', '.join(missing)}")
        return errors  # これ以上は検証できない

    try:
        rx_min = float(cfg["RX_DURATION_MIN_SEC"])
        rx_max = float(cfg["RX_DURATION_MAX_SEC"])
        ts_mode = int(cfg["TIME_SIGNAL_MODE"])
        freq = int(cfg["ANNOUNCE_FREQ"])
        n1 = int(cfg["NIGHT_START_HOUR"])
        n2 = int(cfg["NIGHT_END_HOUR"])
    except (ValueError, TypeError) as e:
        errors.append(f"値の型が不正: {e}")
        return errors

    if not isinstance(cfg["NIGHT_MODE_ENABLED"], bool):
        errors.append("NIGHT_MODE_ENABLED は true / false")

    if not (rx_min > 0):
        errors.append(f"RX_DURATION_MIN_SEC は 0 より大きい必要（現在 {rx_min}）")
    if not (rx_min < rx_max):
        errors.append(f"MIN < MAX である必要（現在 {rx_min} / {rx_max}）")
    if ts_mode not in (0, 1, 2):
        errors.append(f"TIME_SIGNAL_MODE は 0/1/2（現在 {ts_mode}）")
    else:
        valid_freq = {0: (0, 1, 2, 3, 4), 1: (0, 1, 2, 3), 2: (0, 2)}[ts_mode]
        if freq not in valid_freq:
            errors.append(
                f"ANNOUNCE_FREQ は TIME_SIGNAL_MODE={ts_mode} のとき "
                f"{'/'.join(map(str, valid_freq))}（現在 {freq}）")
    if not (0 <= n1 <= 23):
        errors.append(f"NIGHT_START_HOUR は 0〜23（現在 {n1}）")
    if not (0 <= n2 <= 23):
        errors.append(f"NIGHT_END_HOUR は 0〜23（現在 {n2}）")

    # TX_GAIN は任意キー。在る場合のみ厳格に範囲チェックする（書き出しツール側は
    # 入口で弾く方針。本体側は不正でも 1.0 にフォールバックする最後の砦を持つ）。
    if "TX_GAIN" in cfg:
        try:
            g = float(cfg["TX_GAIN"])
        except (ValueError, TypeError):
            errors.append(f"TX_GAIN は数値（現在 {cfg['TX_GAIN']!r}）")
        else:
            if not (TX_GAIN_MIN < g <= TX_GAIN_MAX):
                errors.append(
                    f"TX_GAIN は {TX_GAIN_MIN} 超 〜 {TX_GAIN_MAX} 以下（現在 {g}）")

    # USE_CSTM_* は任意キー。在る場合のみ bool かを確認する（本体側は不正なら
    # False にフォールバックする最後の砦を持つが、書き出しツールは入口で弾く）。
    for k in ("USE_CSTM_INTRO", "USE_CSTM_001", "USE_CSTM_002"):
        if k in cfg and not isinstance(cfg[k], bool):
            errors.append(f"{k} は true / false（現在 {cfg[k]!r}）")

    # 🔵 V2.00jtw / V2.04jtw: 天気読み上げ（dvswitch_bot.py V2.04jtw の _load_config と同一基準）。
    # WEATHER_ENABLED は任意キー。true のときのみ座標を厳格に検証する。
    # 🔵 V2.04jtw: 付与先（WEATHER_ON_*）を導入したため、併用不可の判定を
    # 「実際に天気を付ける先が1つも無いか」へ一般化した。付与先の有無は
    #     時報系   : WEATHER_ON_TIME_SIGNAL かつ TIME_SIGNAL_MODE >= 1
    #     メッセージ系: WEATHER_ON_MESSAGE     かつ ANNOUNCE_FREQ > 0
    # で判定する。両方 false なら、V2.03jtw の「mode0 かつ freq0」と同じくエラー。
    if "WEATHER_ENABLED" in cfg and not isinstance(cfg["WEATHER_ENABLED"], bool):
        errors.append(f"WEATHER_ENABLED は true / false（現在 {cfg['WEATHER_ENABLED']!r}）")
    for k in ("WEATHER_ON_TIME_SIGNAL", "WEATHER_ON_MESSAGE"):
        if k in cfg and not isinstance(cfg[k], bool):
            errors.append(f"{k} は true / false（現在 {cfg[k]!r}）")
    if cfg.get("WEATHER_ENABLED") is True:
        # 任意キーのため既定 true（＝キーが無ければ V2.03jtw と同じ一様付与）
        _on_ts = cfg.get("WEATHER_ON_TIME_SIGNAL", True) is not False
        _on_msg = cfg.get("WEATHER_ON_MESSAGE", True) is not False
        _tgt_ts = _on_ts and ts_mode >= 1
        _tgt_msg = _on_msg and int(cfg.get("ANNOUNCE_FREQ", 0)) > 0
        if not (_tgt_ts or _tgt_msg):
            errors.append("WEATHER_ENABLED=true ですが、天気を付ける音声が1つもありません"
                          f"（時報系: 付与={_on_ts}/mode={ts_mode}, "
                          f"メッセージ系: 付与={_on_msg}/freq={cfg.get('ANNOUNCE_FREQ', 0)}）")
        try:
            w_lat = float(cfg["WEATHER_LATITUDE"])
            w_lon = float(cfg["WEATHER_LONGITUDE"])
        except (KeyError, ValueError, TypeError):
            errors.append("WEATHER_ENABLED=true のとき WEATHER_LATITUDE / WEATHER_LONGITUDE "
                          "を数値で指定（例 35.2167 / 137.0333）")
        else:
            if not (-90.0 <= w_lat <= 90.0) or not (-180.0 <= w_lon <= 180.0):
                errors.append(f"WEATHER_LATITUDE / WEATHER_LONGITUDE が範囲外（現在 {w_lat} / {w_lon}）")

    return errors


# ------------------------------------------------------------
# 読み書き
# ------------------------------------------------------------
def load_existing():
    """既存設定を読む。無い/壊れていれば None。"""
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
            cfg = json.load(fp)
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    return None


def save_config(cfg):
    os.makedirs(BOT_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    os.replace(tmp, CONFIG_PATH)


def show_config():
    cfg = load_existing()
    if cfg is None:
        print(f"[INFO] 設定ファイルがありません（または壊れています）: {CONFIG_PATH}")
        print("       'sudo python3 /opt/dvswitch_bot/bin/bot_setup.py' で作成してください。")
        return
    print(f"[INFO] 現在の設定: {CONFIG_PATH}")
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    errs = validate(cfg)
    if errs:
        print("\n[WARN] この設定には問題があります:")
        for e in errs:
            print(f"   - {e}")
        print("   このままでは dvswitch_bot.py は起動を拒否します。")
    else:
        print("\n[OK] 設定は有効です。dvswitch_bot.py が起動できます。")


# ------------------------------------------------------------
# 入力ヘルパ
# ------------------------------------------------------------
def ask_float(prompt, cur):
    while True:
        s = input(f"{prompt} [現在: {cur}]: ").strip()
        if s == "":
            return cur
        try:
            return float(s)
        except ValueError:
            print("   → 数値で入力してください。")


def ask_int(prompt, cur, choices=None, lo=None, hi=None):
    while True:
        s = input(f"{prompt} [現在: {cur}]: ").strip()
        if s == "":
            return cur
        try:
            v = int(s)
        except ValueError:
            print("   → 整数で入力してください。")
            continue
        if choices is not None and v not in choices:
            print(f"   → {choices} のいずれかで入力してください。")
            continue
        if lo is not None and hi is not None and not (lo <= v <= hi):
            print(f"   → {lo}〜{hi} で入力してください。")
            continue
        return v


def ask_bool(prompt, cur):
    default_yn = "y" if cur else "n"
    while True:
        s = input(f"{prompt} (y/n) [現在: {default_yn}]: ").strip().lower()
        if s == "":
            return cur
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        print("   → y または n で入力してください。")


def ask_gain(prompt, cur):
    """送出音量ゲイン（倍率）の入力。範囲外は厳格に弾いて再入力させる。"""
    while True:
        s = input(f"{prompt} [現在: {cur}]: ").strip()
        if s == "":
            v = cur
        else:
            try:
                v = float(s)
            except ValueError:
                print("   → 数値（例 0.8）で入力してください。")
                continue
        if not (TX_GAIN_MIN < v <= TX_GAIN_MAX):
            print(f"   → {TX_GAIN_MIN} より大きく {TX_GAIN_MAX} 以下で入力してください。")
            continue
        if v > 1.0:
            print("   ※ 1.0 超は増幅です。クリップ（音割れ）に注意してください。")
        return v


def ask_latlon(prompt, cur, lo, hi):
    """🔵 V2.00jtw: 緯度/経度の入力。既定値が無い（cur=None）場合は Enter 連打を
    許さず必ず入力させる（他所の座標既定値で誤った土地の天気を放送する事故防止）。"""
    while True:
        cur_disp = cur if cur is not None else "未設定・入力必須"
        s = input(f"{prompt} [現在: {cur_disp}]: ").strip()
        if s == "":
            if cur is not None:
                return cur
            print("   → 未設定のため入力が必要です（例 35.2167）。")
            continue
        try:
            v = float(s)
        except ValueError:
            print("   → 数値で入力してください（例 35.2167）。")
            continue
        if not (lo <= v <= hi):
            print(f"   → {lo}〜{hi} の範囲で入力してください。")
            continue
        return v


# ------------------------------------------------------------
# 対話本体
# ------------------------------------------------------------
def do_edit():
    existing = load_existing()
    base = dict(DEFAULTS)
    if existing:
        # 既存の有効な値だけ初期値に取り込む（任意キー TX_GAIN も含めて拾う）
        for k in DEFAULTS:
            if k in existing:
                base[k] = existing[k]
        # 🔵 V2.00jtw: DEFAULTS 外の天気キー（座標・対象時刻）も引き継ぐ。
        # ここで拾わないと、本ツールの再実行で手書きした天気設定が黙って消える。
        for k in _WEATHER_EXTRA_KEYS:
            if k in existing:
                base[k] = existing[k]
        print(f"[INFO] 既存設定を読み込みました: {CONFIG_PATH}")
    else:
        print("[INFO] 新規作成します（デフォルト値を初期表示）")

    print("\n==========================================================")
    print(" DVSwitch Bot 設定ツール（Enter で現在値を維持）")
    print("==========================================================\n")

    cfg = {}
    cfg["RX_DURATION_MIN_SEC"] = ask_float("最小受信時間 (秒)", base["RX_DURATION_MIN_SEC"])
    cfg["RX_DURATION_MAX_SEC"] = ask_float("最大受信時間/カーチャンク (秒)", base["RX_DURATION_MAX_SEC"])

    # --- 時刻案内モード ---
    print("\n--- 時刻案内（時報）モード ---")
    print("  0 : 時刻案内しない")
    print("  1 : 毎正時のみ「○○時です」")
    print("  2 : 毎正時「○○時です」＋毎30分「○○時30分です」")
    ts_base = base.get("TIME_SIGNAL_MODE", 1)
    cfg["TIME_SIGNAL_MODE"] = ask_int("時刻案内モード (0/1/2)", ts_base, choices=(0, 1, 2))

    # --- 定時メッセージ（001/002 交互）---
    # 選択肢は時刻案内モードに依存する。時刻案内が占有する分は除外。
    ts = cfg["TIME_SIGNAL_MODE"]
    print("\n--- 定時メッセージ（001/002 を交互再生）---")
    if ts == 0:
        print("  0 : なし")
        print("  1 : 正時（:00）")
        print("  2 : 正時 + 30分（:00, :30）")
        print("  3 : 20分・40分（:20, :40）")
        print("  4 : 15分・30分・45分（:15, :30, :45）")
        freq_choices = (0, 1, 2, 3, 4)
    elif ts == 1:
        print("  ※ 正時（:00）は時刻案内が占有します")
        print("  0 : なし")
        print("  1 : 30分（:30）")
        print("  2 : 20分・40分（:20, :40）")
        print("  3 : 15分・30分・45分（:15, :30, :45）")
        freq_choices = (0, 1, 2, 3)
    else:  # ts == 2
        print("  ※ 正時（:00）と30分（:30）は時刻案内が占有します")
        print("  0 : なし")
        print("  2 : 15分・45分（:15, :45）")
        freq_choices = (0, 2)
    # 既存値が今回の選択肢に無ければデフォルトに丸める
    freq_base = base.get("ANNOUNCE_FREQ", 2)
    if freq_base not in freq_choices:
        freq_base = freq_choices[0]
    cfg["ANNOUNCE_FREQ"] = ask_int(f"定時メッセージ {freq_choices}", freq_base, choices=freq_choices)

    print("\n--- ナイトモード設定 ---")
    print("  ナイトモード中は時報・定時メッセージを抑制します")
    print("  (カーチャンク応答は24時間動作します)")
    cfg["NIGHT_MODE_ENABLED"] = ask_bool("ナイトモードを有効にしますか？",
                                         base["NIGHT_MODE_ENABLED"])
    if cfg["NIGHT_MODE_ENABLED"]:
        cfg["NIGHT_START_HOUR"] = ask_int("ナイトモード開始 N1 (0〜23)",
                                          base["NIGHT_START_HOUR"], lo=0, hi=23)
        cfg["NIGHT_END_HOUR"] = ask_int("ナイトモード終了 N2 (0〜23)",
                                        base["NIGHT_END_HOUR"], lo=0, hi=23)
    else:
        # OFF の場合も値は保持（本体検証のため範囲内の値を入れておく）
        cfg["NIGHT_START_HOUR"] = base["NIGHT_START_HOUR"]
        cfg["NIGHT_END_HOUR"] = base["NIGHT_END_HOUR"]

    # --- 送出音量ゲイン（V1.68）---
    print("\n--- 送出音量（ゲイン倍率）---")
    print("  bot が出す音すべて（ID/時報/30分案内/起動・ナイト案内/001・002）に効きます。")
    print("  1.0 = 等倍（変更なし）。下げる方向が主用途。")
    print("  目安: 0.8 控えめ / 0.7 はっきり小さく / 0.5 かなり小さく")
    cfg["TX_GAIN"] = ask_gain("送出音量 (倍率 0.0超〜5.0以下)", base.get("TX_GAIN", 1.0))

    # --- カスタム音声の選択（V1.73）---
    # intro / 001 / 002 を個別に「カスタム(cstm)を使う / 標準(fixed)」で選ぶ。
    # カスタムを選んでも実ファイル（cstm_intro.wav 等）が無ければ、本体側が
    # 標準にフォールバックして送出を続ける（誤設定で止まらない）。
    # カスタムファイルは利用者が自己責任で /opt/dvswitch_bot/ 直下に用意する。
    print("\n--- カスタム音声（差し替え）---")
    print("  intro / 001 / 002 を個別に、標準 or カスタムに切り替えできます。")
    print("  カスタム選択時に対応ファイルが無ければ標準で鳴ります（自動フォールバック）。")
    print("  カスタムファイル: cstm_intro.wav / cstm_001.wav / cstm_002.wav")
    print("    intro …… カーチャンク応答・起動・ナイトの名乗りに共通で効きます")
    cfg["USE_CSTM_INTRO"] = ask_bool("intro にカスタム音声(cstm_intro.wav)を使う？",
                                     base.get("USE_CSTM_INTRO", False))
    cfg["USE_CSTM_001"] = ask_bool("001 にカスタム音声(cstm_001.wav)を使う？",
                                   base.get("USE_CSTM_001", False))
    cfg["USE_CSTM_002"] = ask_bool("002 にカスタム音声(cstm_002.wav)を使う？",
                                   base.get("USE_CSTM_002", False))

    # --- 天気読み上げ（V2.00jtw / JTW版）---
    # 定時音声（時報/30分/001/002）に続けて Open-Meteo の当地天気（天気＋気温）を
    # 付ける。voice_make.py が発火2分前に取得・事前生成し、発火時は再生のみ。
    # 地名は wav_source.json の location（create_wav.sh で設定）を使う。
    print("\n--- 天気読み上げ（JTW版）---")
    # 🔵 V2.04jtw: 付与先の系統ごとに「そもそも鳴る音声があるか」を先に見る。
    # 無い系統は対話で問わず OFF 固定にする（選ばせても意味がないため）。
    _has_ts = (cfg["TIME_SIGNAL_MODE"] >= 1)            # 時報 :00 / 30分案内 :30
    _has_msg = (int(cfg.get("ANNOUNCE_FREQ", 0)) > 0)   # 定時メッセージ 001/002
    # 付与先の既定は base（既存設定 → 無ければ DEFAULTS の true）
    cfg["WEATHER_ON_TIME_SIGNAL"] = base.get("WEATHER_ON_TIME_SIGNAL", True)
    cfg["WEATHER_ON_MESSAGE"] = base.get("WEATHER_ON_MESSAGE", True)
    if not (_has_ts or _has_msg):
        print("  時報も定時メッセージも無いため、天気は設定できません（OFF固定）。")
        cfg["WEATHER_ENABLED"] = False
        for k in _WEATHER_EXTRA_KEYS:
            if k in base:
                cfg[k] = base[k]   # 値は保存し続ける（音声を有効に戻したとき再利用）
    else:
        print("  定時音声の後ろに「○○の天気は、晴れ、気温は25度です」を付けます。")
        print("  （○○は create_wav.sh で設定した地名。座標は Google マップで確認できます）")
        cfg["WEATHER_ENABLED"] = ask_bool("天気読み上げを有効にしますか？",
                                          base.get("WEATHER_ENABLED", False))
        if cfg["WEATHER_ENABLED"]:
            # --- 付与先の選択（V2.04jtw）---
            # 鳴る音声が無い系統は問わずに OFF 固定（理由を明示する）。
            print("\n  天気を付ける対象を選びます（両方 ON も可）。")
            if _has_ts:
                cfg["WEATHER_ON_TIME_SIGNAL"] = ask_bool(
                    "  時報（:00 / :30）に天気を付ける？",
                    base.get("WEATHER_ON_TIME_SIGNAL", True))
            else:
                cfg["WEATHER_ON_TIME_SIGNAL"] = False
                print("  ※ 時刻案内が無効（mode 0）のため、時報への付与は OFF 固定です。")
            if _has_msg:
                cfg["WEATHER_ON_MESSAGE"] = ask_bool(
                    "  定時メッセージ（001/002）に天気を付ける？",
                    base.get("WEATHER_ON_MESSAGE", True))
            else:
                cfg["WEATHER_ON_MESSAGE"] = False
                print("  ※ 定時メッセージが 0 回のため、そちらへの付与は OFF 固定です。")
            # 付与先が両方 OFF なら天気自体を OFF に倒す（保存時の検証エラーを未然に回避）
            if not (cfg["WEATHER_ON_TIME_SIGNAL"] or cfg["WEATHER_ON_MESSAGE"]):
                print("  ※ 付与先が両方 OFF のため、天気読み上げ自体を OFF にしました。")
                cfg["WEATHER_ENABLED"] = False
        if cfg["WEATHER_ENABLED"]:
            # 🔵 初期値の補完: bot_config.json に無ければ MMDVM_Bridge.ini の
            # [Info] Latitude/Longitude を初期表示する（Enter で採用可）。
            _cur_lat = base.get("WEATHER_LATITUDE")
            _cur_lon = base.get("WEATHER_LONGITUDE")
            if _cur_lat is None or _cur_lon is None:
                _ll = _ini_coords()
                if _ll:
                    if _cur_lat is None:
                        _cur_lat = _ll[0]
                    if _cur_lon is None:
                        _cur_lon = _ll[1]
                    print(f"  ※ 座標の初期値を MMDVM_Bridge.ini の [Info] から取得しました"
                          f"（{_ll[0]}, {_ll[1]} / Enter で採用）。")
            cfg["WEATHER_LATITUDE"] = ask_latlon("緯度（例 35.2167）", _cur_lat, -90.0, 90.0)
            cfg["WEATHER_LONGITUDE"] = ask_latlon("経度（例 137.0333）", _cur_lon, -180.0, 180.0)
            # V2.03jtw: 天気は全定時音声へ一様付与（時刻絞り WEATHER_HOURS は廃止）。
        else:
            for k in _WEATHER_EXTRA_KEYS:
                if k in base:
                    cfg[k] = base[k]   # OFF でも座標は保存し続ける

    # 確認表示
    ts = cfg["TIME_SIGNAL_MODE"]
    ts_label = {0: "なし", 1: "毎正時 :00", 2: "毎正時 :00 + 毎30分 :30"}[ts]
    # 定時メッセージの実トリガー分（dvswitch_bot.py の _get_trigger_minutes と同一表）
    _msg_table = {
        0: {0: [], 1: [0], 2: [0, 30], 3: [20, 40], 4: [15, 30, 45]},
        1: {0: [], 1: [30], 2: [20, 40], 3: [15, 30, 45]},
        2: {0: [], 2: [15, 45]},
    }
    msg_minutes = _msg_table[ts].get(cfg["ANNOUNCE_FREQ"], [])
    msg_str = "なし" if not msg_minutes else "・".join(f":{m:02d}" for m in msg_minutes)

    print("\n----------------------------------------------------------")
    print(" 以下の内容で保存します")
    print("----------------------------------------------------------")
    print(f"   最小受信時間   : {cfg['RX_DURATION_MIN_SEC']} 秒")
    print(f"   最大受信時間   : {cfg['RX_DURATION_MAX_SEC']} 秒")
    print(f"   時刻案内       : mode {ts}（{ts_label}）")
    print(f"   定時メッセージ : {cfg['ANNOUNCE_FREQ']}（{msg_str}）001/002交互")
    if cfg["NIGHT_MODE_ENABLED"]:
        resume = (cfg["NIGHT_END_HOUR"] + 1) % 24
        sup_start = (cfg["NIGHT_START_HOUR"] + 1) % 24
        print(f"   ナイトモード   : ON  N1={cfg['NIGHT_START_HOUR']:02d} N2={cfg['NIGHT_END_HOUR']:02d} "
              f"(抑制 {sup_start:02d}〜{cfg['NIGHT_END_HOUR']:02d} / 再開 {resume:02d}:00)")
    else:
        print("   ナイトモード   : OFF（24時間送出）")
    _g = cfg["TX_GAIN"]
    _g_note = "等倍/変更なし" if _g == 1.0 else ("減衰" if _g < 1.0 else "増幅(クリップ注意)")
    print(f"   送出音量       : {_g}（{_g_note}）")
    _cstm = lambda b: "カスタム" if b else "標準"
    print(f"   カスタム音声   : intro={_cstm(cfg['USE_CSTM_INTRO'])} "
          f"001={_cstm(cfg['USE_CSTM_001'])} 002={_cstm(cfg['USE_CSTM_002'])}")
    if cfg.get("WEATHER_ENABLED"):
        # 🔵 V2.04jtw: 付与先を明示する（両方 ON なら従来どおり「全定時音声」）
        _wt = []
        if cfg.get("WEATHER_ON_TIME_SIGNAL", True):
            _wt.append("時報:00" + ("・:30" if ts == 2 else ""))
        if cfg.get("WEATHER_ON_MESSAGE", True):
            _wt.append(f"定時メッセージ（{msg_str}）")
        print(f"   天気読み上げ   : ON  ({cfg['WEATHER_LATITUDE']}, {cfg['WEATHER_LONGITUDE']}) "
              f"付与先: {' / '.join(_wt) if _wt else 'なし'}")
    else:
        print("   天気読み上げ   : OFF")
    print("----------------------------------------------------------")

    # 検証
    errs = validate(cfg)
    if errs:
        print("\n[ERROR] 入力に問題があります。保存を中止します:")
        for e in errs:
            print(f"   - {e}")
        sys.exit(1)

    ans = input("\nこの内容で保存しますか？ (y/N): ").strip().lower()
    if ans != "y":
        print("中止しました。ファイルは変更していません。")
        return

    try:
        save_config(cfg)
    except PermissionError:
        print(f"\n[ERROR] 書き込み権限がありません: {CONFIG_PATH}")
        print("        sudo を付けて再実行してください: sudo python3 /opt/dvswitch_bot/bin/bot_setup.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 保存に失敗しました: {e}")
        sys.exit(1)

    print(f"\n[完了] 保存しました: {CONFIG_PATH}")
    print("       デーモンを再起動して反映してください:")
    print("       sudo systemctl restart dvswitch-bot")


def show_help():
    print(__doc__)


# ------------------------------------------------------------
def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg in ("-h", "--help"):
        show_help()
    elif arg in ("-s", "--show"):
        show_config()
    elif arg == "":
        do_edit()
    else:
        print(f"不明なオプション: {arg}\n")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
