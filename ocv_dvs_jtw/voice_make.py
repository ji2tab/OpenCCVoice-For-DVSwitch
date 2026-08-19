#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 voice_make.py (vmp) — OpenCCVoice for DVSwitch 定時音声 事前生成ツール
 — JJ2YYK デジピーター自動応答システム  JTW版 —

 dvswitch_bot.py（V2.03jtw 以降）から「発火の約2分前」にワンショット起動され、
 その発火に対応する音声（本来のアナウンス＋当地の天気）を1本の WAV として
 事前生成し、所定のスロットファイルへ書き出す。生成が終わると即座に終了する
 （常駐しない）。発火時、bot はこのスロットWAVを再生するだけでよい。

 【設計思想（bot との役割分担）】
  - スケジュール判定（何分に何を鳴らすか・ナイト抑制・001/002 交互・カスタム
    使用の有無）はすべて bot 側が持つ「唯一の真実の源」。vmp はスケジュールを
    一切知らない。bot が号令の引数として「何を作るか」を渡し、vmp は言われた
    ものを作るだけ。これによりスケジュール知識の二重化を避ける。
  - vmp はワンショット（丙方式）。常駐しないため「vmp が死んでいる」状態が
    存在しない。bot が必要なときだけ subprocess で起動する。
  - スロット競合は構造的に起きない: 定時発火は最短でも15分間隔で排他的、かつ
    合成は数秒オーダー。生成が次発火に食い込むことは設計上ありえないため、
    スロットは種別ごとの固定名で足りる（ロック不要）。カーチャンク応答は
    bot 側が別系統で生成するため、vmp と生成が競合することもない。

 【時報の正確さを守る仕組み】
  正時ちょうどに open_jtalk 合成を始めたのでは Raspberry Pi では間に合わない
  （合成1.5秒〜、天気込み長文ではさらに）。そこで2分前に「本来音声＋天気」を
  完成 WAV として焼いておき、発火時は再生のみ（合成ゼロ＝遅延ゼロ）にする。

 【内部フォールバック（時報を絶対に落とさない）】
  天気の取得・合成に失敗しても、vmp は「本来音声だけ」をスロットに必ず書く。
  → 回線断や Open-Meteo 障害でも、時報そのものは定刻に流れる（天気だけ欠ける）。
  天気なし指定・機能OFF時も同様に、本来音声だけのスロットを作る。
  本来音声の合成自体が失敗したときのみスロットは作られない（＝bot は割り切りで
  鳴らさない）。

 【地名】
  天気文の地名（「〇〇の天気は…」の〇〇）は wav_source.json の location を
  読む（create_wav.sh がイントロ WAV に焼き込むのと同じ源）。これにより地名は
  1箇所（location）で管理され、イントロと天気で必ず一致する。location が無い/
  空なら「当地」にフォールバック。読みは location 側で調整可能なため vmp では
  読み仮名処理をしない。

 【配置】
  /opt/dvswitch_bot/bin/voice_make.py

 【呼び出し（bot が subprocess で起動）】
  python3 voice_make.py --kind time_signal   --hour 12 --slot /dev/shm/ocv_slot_XX00.wav [--weather]
  python3 voice_make.py --kind half_hour     --hour 12 --slot /dev/shm/ocv_slot_XX30.wav [--weather]
  python3 voice_make.py --kind message --base /opt/dvswitch_bot/001.wav \
                                       --slot /dev/shm/ocv_slot_XX15.wav [--weather]

 【スロットWAV】
  bot と vmp で取り決めた固定パス（/dev/shm 上）。原子的差し替え（.building →
  os.replace）で書くため、書きかけを bot が再生することはない。

 Document Version: V1.02vmp（JTW版・本体と天気の間に WEATHER_GAP_SEC のワンテンポを追加）
 　（V1.02vmp: スロット先頭に LEAD_BEFORE_INTRO_SEC=0.5s の無音を追加し
 　 時報/定時の頭欠けを解消。実測 2026-08-19・両ノード）
 　（V1.00vmp: JTW版・初版）
 Last Updated: 2026-08-05
================================================================================
"""

__version__ = "V1.02vmp"

import os
import sys
import json
import wave
import argparse
import subprocess
import urllib.request
import urllib.error

# ============================================================
# 基本設定（bot と揃える。合成パイプラインは create_wav.sh / bot と同一手順）
# ============================================================
BOT_DIR = "/opt/dvswitch_bot"
DICT_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"
TIME_INTRO_WAV = f"{BOT_DIR}/time_intro.wav"
CONFIG_PATH = f"{BOT_DIR}/bot_config.json"
WAV_SOURCE_JSON = f"{BOT_DIR}/wav_source.json"

# intro と合成音の間の無音（bot の GAP_AFTER_INTRO_SEC と揃える）
GAP_AFTER_INTRO_SEC = 0.5
# 🔵 実測(2026-08-19): スロット再生の頭欠け対策。時報/定時スロットは
# time_intro.wav の生の先頭から始まるため、TGIF のストリーム確立中に語頭
# （「こちらは」の「こ」）が食われて半文字〜1/4文字欠ける症状があった。
# カーチャンク応答が平気なのは先頭の無音マージンが大きいため。スロット先頭に
# この無音リードを足して語頭を保護する（両ノード実測で 0.5 秒に確定）。
LEAD_BEFORE_INTRO_SEC = 0.5
# 🔵 V1.01vmp: 本体（時報/001 等）と天気の間に置くワンテンポの無音（秒）。
# 「12時です」→（間）→「尾張旭の天気は…」のように、本体と天気の切れ目に
# 一拍おいて聞きやすくする。intro↔本文の間隔とは目的が別なので独立定数にする。
WEATHER_GAP_SEC = 0.5

# 天気取得
WEATHER_FETCH_TIMEOUT_SEC = 5
DEFAULT_PLACE = "当地"   # location が無い/空のときのフォールバック

# WMO weather code → 読み上げ語。Open-Meteo の current.weather_code 準拠。
# 表に無いコードは「天気」を省略し気温のみ読む（_weather_sentence 参照）。
_WMO_TEXT = {
    0: "快晴", 1: "晴れ", 2: "晴れ、ときどき曇り", 3: "曇り",
    45: "霧", 48: "霧",
    51: "霧雨", 53: "霧雨", 55: "霧雨",
    56: "冷たい霧雨", 57: "冷たい霧雨",
    61: "弱い雨", 63: "雨", 65: "強い雨",
    66: "冷たい雨", 67: "冷たい雨",
    71: "弱い雪", 73: "雪", 75: "強い雪", 77: "細かい雪",
    80: "にわか雨", 81: "にわか雨", 82: "強いにわか雨",
    85: "にわか雪", 86: "強いにわか雪",
    95: "雷雨", 96: "ひょうを伴う雷雨", 99: "ひょうを伴う雷雨",
}


def _log(msg):
    """bot のログと混ざっても判別できるよう vmp 印をつけて stderr へ出す。
    bot は subprocess の stderr を journal に流せる。"""
    print(f"[vmp] {msg}", file=sys.stderr, flush=True)


# ============================================================
# 設定・地名の読み取り
# ============================================================
def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _read_location():
    """wav_source.json の location を返す。無い/空なら DEFAULT_PLACE。
    create_wav.sh がイントロに焼き込むのと同じ源。読みは location 側で
    調整済みの前提のため、ここでは加工しない。"""
    loc = _read_json(WAV_SOURCE_JSON).get("location", "")
    loc = (loc or "").strip()
    return loc if loc else DEFAULT_PLACE


def _read_weather_coords():
    """bot_config.json から緯度経度を返す（(lat, lon) or None）。
    bot と同じ設定ファイルを見るので、真実の源は一本のまま。"""
    cfg = _read_json(CONFIG_PATH)
    try:
        lat = float(cfg["WEATHER_LATITUDE"])
        lon = float(cfg["WEATHER_LONGITUDE"])
    except (KeyError, ValueError, TypeError):
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return None
    return lat, lon


# ============================================================
# 天気の取得・文生成
# ============================================================
def _weather_fetch(lat, lon):
    """Open-Meteo の current から (weather_code, temperature_2m) を取る。
    失敗時は例外を上げる（呼び出し側でログして天気なしにフォールバック）。"""
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           "&current=weather_code,temperature_2m&timezone=Asia%2FTokyo")
    with urllib.request.urlopen(url, timeout=WEATHER_FETCH_TIMEOUT_SEC) as r:
        d = json.load(r)
    cur = d["current"]
    return int(cur["weather_code"]), float(cur["temperature_2m"])


def _weather_sentence(code, temp, place):
    """読み上げ文を組む。氷点下対応。未知コードは天気を省略し気温のみ。
    地名は location（place）を差し込む。"""
    t = int(round(temp))
    temp_part = f"気温は氷点下{-t}度です" if t < 0 else f"気温は{t}度です"
    wx = _WMO_TEXT.get(code)
    if wx:
        return f"{place}の天気は、{wx}、{temp_part}"
    return f"{place}の{temp_part}"


# ============================================================
# 音声合成（bot / create_wav.sh と同一パイプライン）
# ============================================================
def _synth_middle(text, out48):
    """open_jtalk で text を合成し 48k WAV を out48 に書く。成功で True。"""
    try:
        p = subprocess.Popen(
            ["open_jtalk", "-x", DICT_PATH, "-m", VOICE_PATH, "-ow", out48],
            stdin=subprocess.PIPE,
        )
        p.communicate(text.encode("utf-8"))
        return p.returncode == 0
    except FileNotFoundError as e:
        _log(f"open_jtalk 見つからず: {e}")
        return False


def _sox(args):
    """sox をエラー時 False で返す薄いラッパ。"""
    try:
        subprocess.run(["sox"] + args, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        _log(f"sox 失敗: {e}")
        return False


def _build_slot(base_kind, base_text, base_wav, weather_text, slot_path):
    """スロットWAVを1本ものとして生成し、原子的に slot_path へ書く。

    base_kind : "synth"（時報系: base_text を合成して本体にする）
                "file" （メッセージ系: base_wav を本体にする）
    base_text : 時報系の読み上げ本文（例「12時です」）
    base_wav  : メッセージ系の本体WAV（001.wav / cstm_001.wav の実パス）
    weather_text : 接ぐ天気文（None なら天気なし＝本体だけ）
    slot_path : 出力スロット（/dev/shm/...wav）

    構成:
      時報系   : time_intro.wav ＋（間 GAP）＋ 本文合成 ［＋（間）＋ 天気合成］
      メッセージ系: base_wav        ［＋（間）＋ 天気合成］
      （メッセージ系はイントロを base_wav が内包する前提のため time_intro は付けない）
    戻り値: True で成功（slot_path に有効なWAVがある）。
    """
    pid = os.getpid()
    tmp48 = f"/dev/shm/vmp_mid48_{pid}.wav"
    tmp8 = f"/dev/shm/vmp_mid8_{pid}.wav"
    tmp_wx48 = f"/dev/shm/vmp_wx48_{pid}.wav"
    tmp_wx8 = f"/dev/shm/vmp_wx8_{pid}.wav"
    tmp_intro = f"/dev/shm/vmp_intro_{pid}.wav"
    building = f"{slot_path[:-4]}.building.wav" if slot_path.endswith(".wav") else f"{slot_path}.building.wav"
    cleanup = [tmp48, tmp8, tmp_wx48, tmp_wx8, tmp_intro]

    try:
        parts = []   # 結合するパーツ（8k WAV のパス）を順に並べる

        # --- 本体 ---
        if base_kind == "synth":
            if not base_text:
                _log("synth 指定だが base_text が空")
                return False
            if not _synth_middle(base_text, tmp48):
                _log("本文合成に失敗")
                return False
            if not _sox([tmp48, "-r", "8000", "-c", "1", "-b", "16", tmp8]):
                return False
            # time_intro を先頭に（末尾に GAP の無音）
            if not _sox([TIME_INTRO_WAV, tmp_intro, "pad", f"{LEAD_BEFORE_INTRO_SEC}", f"{GAP_AFTER_INTRO_SEC}"]):
                return False
            parts.append(tmp_intro)
            parts.append(tmp8)
        elif base_kind == "file":
            if not base_wav or not os.path.exists(base_wav):
                _log(f"file 指定だが base_wav が無い: {base_wav}")
                return False
            parts.append(base_wav)
        else:
            _log(f"不明な base_kind: {base_kind}")
            return False

        # --- 天気（あれば本体の後ろに接ぐ）---
        if weather_text:
            if _synth_middle(weather_text, tmp_wx48) and \
               _sox([tmp_wx48, "-r", "8000", "-c", "1", "-b", "16", tmp_wx8]):
                # 🔵 V1.01vmp: 本体と天気の間にワンテンポ（WEATHER_GAP_SEC）の
                # 無音を置くため、天気側の先頭に無音を pad する。
                tmp_wx8_padded = f"/dev/shm/vmp_wx8pad_{pid}.wav"
                cleanup.append(tmp_wx8_padded)
                if _sox([tmp_wx8, tmp_wx8_padded, "pad", f"{WEATHER_GAP_SEC}", "0"]):
                    parts.append(tmp_wx8_padded)
                else:
                    parts.append(tmp_wx8)   # pad 失敗時は間なしで接ぐ（天気は落とさない）
            else:
                _log("天気合成に失敗 → 天気なしで本体のみ生成（時報は死守）")

        # --- 結合して building へ、成功したら原子的に slot へ ---
        if len(parts) == 1:
            # パーツ1つ（メッセージ系・天気なし）は sox でコピー（形式正規化も兼ねる）
            if not _sox([parts[0], building]):
                return False
        else:
            if not _sox(parts + [building]):
                return False

        os.replace(building, slot_path)
        return True

    finally:
        for f in cleanup + [building]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except OSError:
                pass


# ============================================================
# 本文テキスト（時報系）
# ============================================================
def _time_signal_text(hour):
    return f"{hour}時です"


def _half_hour_text(hour):
    return f"{hour}時30分です"


# ============================================================
# メイン
# ============================================================
def main():
    ap = argparse.ArgumentParser(description="OpenCCVoice 定時音声 事前生成 (vmp)")
    ap.add_argument("--kind", required=True,
                    choices=["time_signal", "half_hour", "message"],
                    help="生成する音声の種別")
    ap.add_argument("--slot", required=True, help="出力スロットWAVのパス（/dev/shm/...）")
    ap.add_argument("--hour", type=int, help="時（time_signal/half_hour で使用）")
    ap.add_argument("--base", help="本体WAVのパス（message で使用: 001.wav / cstm_001.wav）")
    ap.add_argument("--weather", action="store_true",
                    help="指定時のみ本体の後ろに当地の天気を接ぐ")
    args = ap.parse_args()

    # --- 天気文の用意（--weather のときだけ）---
    weather_text = None
    if args.weather:
        coords = _read_weather_coords()
        if coords is None:
            _log("天気座標が未設定/不正 → 天気なしで生成")
        else:
            try:
                code, temp = _weather_fetch(*coords)
                place = _read_location()
                weather_text = _weather_sentence(code, temp, place)
                _log(f"天気取得OK code={code} temp={temp:.1f} place={place} → 「{weather_text}」")
            except Exception as e:
                _log(f"天気取得失敗 → 天気なしで生成（本体は死守）: {e}")

    # --- 本体の種別ごとに生成 ---
    if args.kind == "time_signal":
        if args.hour is None:
            _log("time_signal に --hour が必要"); sys.exit(2)
        ok = _build_slot("synth", _time_signal_text(args.hour), None, weather_text, args.slot)
    elif args.kind == "half_hour":
        if args.hour is None:
            _log("half_hour に --hour が必要"); sys.exit(2)
        ok = _build_slot("synth", _half_hour_text(args.hour), None, weather_text, args.slot)
    elif args.kind == "message":
        if not args.base:
            _log("message に --base が必要"); sys.exit(2)
        ok = _build_slot("file", None, args.base, weather_text, args.slot)
    else:
        _log(f"不明な kind: {args.kind}"); sys.exit(2)

    if ok:
        _log(f"スロット生成OK: {args.slot} (kind={args.kind}, weather={'yes' if weather_text else 'no'})")
        sys.exit(0)
    else:
        _log(f"スロット生成失敗: {args.slot} (kind={args.kind})")
        sys.exit(1)


if __name__ == "__main__":
    main()
