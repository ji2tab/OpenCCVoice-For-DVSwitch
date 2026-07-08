#!/usr/bin/env python3
"""VOICEVOXでテキストを音声合成し、48kHz WAVとして保存する。
Usage: vv_say.py "<text>" <output_wav_path> [style_id]
"""
import sys
from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

DIST_DIR = "/opt/voicevox/dist"

def main():
    text = sys.argv[1]
    out_path = sys.argv[2]
    style_id = int(sys.argv[3]) if len(sys.argv) > 3 else 30  # No.7（アナウンス）既定

    onnx = Onnxruntime.load_once(
        filename=f"{DIST_DIR}/onnxruntime/lib/libvoicevox_onnxruntime.so.1.17.3"
    )
    openjtalk = OpenJtalk(f"{DIST_DIR}/dict/open_jtalk_dic_utf_8-1.11")
    synth = Synthesizer(onnx, openjtalk)

    with VoiceModelFile.open(f"{DIST_DIR}/models/vvms/6.vvm") as model:
        synth.load_voice_model(model)

    query = synth.create_audio_query(text, style_id=style_id)
    query.output_sampling_rate = 48000
    wav = synth.synthesis(query, style_id=style_id)

    with open(out_path, "wb") as f:
        f.write(wav)

if __name__ == "__main__":
    main()
