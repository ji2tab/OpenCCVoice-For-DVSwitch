#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 bot_setup.py — DVSwitch Bot 設定ツール
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

【配置】
   /opt/dvswitch_bot/bin/bot_setup.py

【使い方】
   sudo python3 /opt/dvswitch_bot/bin/bot_setup.py        対話で作成・更新（既存値があれば初期表示）
   sudo python3 /opt/dvswitch_bot/bin/bot_setup.py -s     現在の設定を表示するだけ
   sudo python3 /opt/dvswitch_bot/bin/bot_setup.py -h     ヘルプ

 ※ /opt/dvswitch_bot/ への書き込みのため sudo 推奨。
================================================================================
"""

import os
import sys
import json

BOT_DIR = "/opt/dvswitch_bot"
CONFIG_PATH = f"{BOT_DIR}/bot_config.json"

# デフォルト値（V1.60 のコード初期値に準拠）
DEFAULTS = {
    "RX_DURATION_MIN_SEC": 0.5,
    "RX_DURATION_MAX_SEC": 3.9,
    "TIME_SIGNAL_MODE": 1,
    "ANNOUNCE_FREQ": 2,
    "NIGHT_MODE_ENABLED": True,
    "NIGHT_START_HOUR": 22,
    "NIGHT_END_HOUR": 5,
}

REQUIRED_KEYS = list(DEFAULTS.keys())


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


# ------------------------------------------------------------
# 対話本体
# ------------------------------------------------------------
def do_edit():
    existing = load_existing()
    base = dict(DEFAULTS)
    if existing:
        # 既存の有効な値だけ初期値に取り込む
        for k in REQUIRED_KEYS:
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
