#!/usr/bin/env python3
"""VOICEVOX でテキストを音声合成し、WAV として保存する。

Version: V2.0vv

Usage:
    vv_say.py "<text>" <output_wav_path> [style_id] [vvm]
    vv_say.py --version

話者の決まり方（優先順）:
    1. コマンドライン引数 style_id / vvm（両方 or どちらかを明示指定）
    2. wav_source.json の "voice"（create_wav.sh が保存した選択）
    3. 既定の No.7（アナウンス） style_id=30 / 6.vvm

変更履歴:
    V1.0  初版。6.vvm 固定・style_id 既定 30・出力 48kHz 固定。
          onnxruntime の .so はバージョン付きパス（.so.1.17.3）を直書き。
    V2.0vv 🔵 話者の可変化（"vv"=VOICEVOX系ノード用を示すサフィックス）（OpenCCVoice 話者選択機能の一部）。
          - 6.vvm 固定を撤廃し、wav_source.json の "voice" を参照。
            style_id と vvm を必ずセットで解決する（不一致による合成失敗を防ぐ）。
          - query.output_sampling_rate=48000 のハードコードを撤去（deprecation 対応。
            VOICEVOX のネイティブ出力に任せ、8kHz への変換は呼び出し側 sox が担う）。
          - onnxruntime の .so をバージョン非依存の glob で解決。
          - 機械可読の版表記（__version__ 固定行）と --version オプションを追加。
          ※ 対応セット: create_wav.sh V1.2+（voice 記録）/ dvswitch_bot.py V1.96+
"""
import glob
import json
import os
import sys

# 機械可読バージョン（固定行）。版を上げるときはヘッダーの Version 表記と一致させる。
__version__ = "V2.0vv"

from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

DIST_DIR = "/opt/voicevox/dist"
VVM_DIR = f"{DIST_DIR}/models/vvms"
SRC_JSON = "/opt/dvswitch_bot/wav_source.json"

# 既定話者（wav_source.json に voice が無い・壊れている場合のフォールバック）。
# create_wav.sh / dvswitch_bot.py と揃えて No.7（アナウンス）とする。
DEFAULT_STYLE_ID = 30
DEFAULT_VVM = "6.vvm"


def _resolve_onnxruntime_so():
    """onnxruntime の .so をバージョン非依存で解決する。"""
    cands = sorted(glob.glob(f"{DIST_DIR}/onnxruntime/lib/libvoicevox_onnxruntime.so*"))
    if not cands:
        raise FileNotFoundError(
            f"onnxruntime の .so が見つかりません: {DIST_DIR}/onnxruntime/lib/"
        )
    return cands[0]


def _load_voice_from_json():
    """wav_source.json の "voice" から (style_id, vvm) を取り出す。
    取得できなければ (None, None) を返す（呼び出し側で既定にフォールバック）。"""
    try:
        with open(SRC_JSON, encoding="utf-8") as f:
            d = json.load(f)
        v = d.get("voice", {}) if isinstance(d, dict) else {}
        if not isinstance(v, dict):
            return None, None
        sid = v.get("style_id", None)
        vvm = v.get("vvm", None)
        # style_id は int 化できるときだけ採用
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            sid = None
        if not vvm:
            vvm = None
        return sid, vvm
    except Exception:
        return None, None


def _vvm_to_path(vvm):
    """"6.vvm" のようなファイル名をフルパスへ。既にパスならそのまま使う。"""
    if not vvm:
        return None
    if os.path.isabs(vvm) or "/" in vvm:
        return vvm
    return f"{VVM_DIR}/{vvm}"


def _resolve_voice(argv):
    """引数 → wav_source.json → 既定 の順で (style_id, vvm_path) を確定する。
    style_id と vvm は必ずセットで扱い、不一致による合成失敗を避ける。"""
    arg_style = None
    arg_vvm = None
    if len(argv) > 3 and argv[3] != "":
        try:
            arg_style = int(argv[3])
        except ValueError:
            arg_style = None
    if len(argv) > 4 and argv[4] != "":
        arg_vvm = argv[4]

    # 1) 引数で両方そろっていれば最優先
    if arg_style is not None and arg_vvm:
        return arg_style, _vvm_to_path(arg_vvm)

    # 2) wav_source.json の voice
    json_style, json_vvm = _load_voice_from_json()

    # style_id の決定: 引数 → JSON → 既定
    style_id = arg_style if arg_style is not None else (
        json_style if json_style is not None else DEFAULT_STYLE_ID
    )
    # vvm の決定: 引数 → JSON → 既定
    vvm = arg_vvm or json_vvm or DEFAULT_VVM

    # style_id と vvm の出所が食い違い、片方だけ引数指定のような場合でも、
    # ここで組として確定させる（上の優先順で一貫した組になる）。
    return style_id, _vvm_to_path(vvm)


def main():
    # 版の確認用（配置ミスの切り分けに使う）:
    #   /opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py --version
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        print(f"vv_say.py {__version__}")
        sys.exit(0)

    if len(sys.argv) < 3:
        sys.stderr.write(
            'Usage: vv_say.py "<text>" <output_wav_path> [style_id] [vvm]\n'
            '       vv_say.py --version\n'
        )
        sys.exit(1)

    text = sys.argv[1]
    out_path = sys.argv[2]
    style_id, vvm_path = _resolve_voice(sys.argv)

    if not os.path.exists(vvm_path):
        sys.stderr.write(f"vvm が見つかりません: {vvm_path}\n")
        sys.exit(1)

    onnx = Onnxruntime.load_once(filename=_resolve_onnxruntime_so())
    openjtalk = OpenJtalk(f"{DIST_DIR}/dict/open_jtalk_dic_utf_8-1.11")
    synth = Synthesizer(onnx, openjtalk)

    with VoiceModelFile.open(vvm_path) as model:
        synth.load_voice_model(model)

    # 出力サンプリングレートはハードコードしない（VOICEVOX のネイティブ出力に任せる）。
    # 8kHz への変換は呼び出し側（create_wav.sh の sox）が行う。
    query = synth.create_audio_query(text, style_id=style_id)
    wav = synth.synthesis(query, style_id=style_id)

    with open(out_path, "wb") as f:
        f.write(wav)


if __name__ == "__main__":
    main()
