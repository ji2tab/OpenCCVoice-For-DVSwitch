#!/bin/bash
# ==============================================================================
# weather_diag.sh — 時刻＋天気の「1本もの」音声を今その場で生成して検証する
#   タイミングを狙う必要なし。いつ実行してもよい。
#   bot 本体と同じ結合手順（open_jtalk → sox 8kHz → intro結合 → vol）を再現し、
#   出来た1本ものの長さ・無音区間を表示し、そのまま送出テストできる。
#
#   使い方:
#     sudo bash weather_diag.sh            生成して長さを表示（送出はしない・安全）
#     sudo bash weather_diag.sh --send     生成して長さ表示のうえ、実際に電波に送出
#                                          （bot を一時停止して送り、終わったら再開）
# ==============================================================================
set -u

D=/opt/dvswitch_bot
DICT=/var/lib/mecab/dic/open-jtalk/naist-jdic
VOICE=/usr/share/hts-voice/mei/mei_normal.htsvoice
OUT=/tmp/weather_diag_full.wav

# bot_config.json から TX_GAIN を読む（無ければ 1.0）
GAIN=$(python3 -c "import json;print(json.load(open('$D/bot_config.json')).get('TX_GAIN',1.0))" 2>/dev/null || echo 1.0)

# 読み上げ文（実際の bot と同じ組み立て。天気は固定のサンプル文）
HOUR=$(date +%-H)
TEXT="${HOUR}時です。続いて当地の天気は、快晴、気温は33度です"

echo "=================================================================="
echo " 時刻＋天気 音声診断"
echo "   文面 : こちらは、〜（time_intro）。${TEXT}"
echo "   TX_GAIN : ${GAIN}（bot_config.json より）"
echo "=================================================================="

# --- bot と同じ4ステップで1本に結合 ---
echo "[1/4] open_jtalk で合成中..."
open_jtalk -x "$DICT" -m "$VOICE" -ow /tmp/wd_mid48.wav <<< "$TEXT" || { echo "❌ open_jtalk 失敗"; exit 1; }
echo "[2/4] 8kHz/mono/16bit へ変換..."
sox /tmp/wd_mid48.wav -r 8000 -c 1 -b 16 /tmp/wd_mid8.wav || { echo "❌ sox 変換失敗"; exit 1; }
echo "[3/4] time_intro.wav を結合（間に 0.5 秒）..."
sox "$D/time_intro.wav" /tmp/wd_ti_pad.wav pad 0 0.5 || { echo "❌ intro パディング失敗"; exit 1; }
echo "[4/4] 全体を結合し音量調整..."
if [ "$GAIN" = "1.0" ]; then
  sox /tmp/wd_ti_pad.wav /tmp/wd_mid8.wav "$OUT" || { echo "❌ 結合失敗"; exit 1; }
else
  sox /tmp/wd_ti_pad.wav /tmp/wd_mid8.wav "$OUT" vol "$GAIN" || { echo "❌ 結合失敗"; exit 1; }
fi

echo ""
echo "=================================================================="
echo " ✅ 1本ものが完成しました: $OUT"
echo "------------------------------------------------------------------"
# 長さ・形式
DUR=$(soxi -D "$OUT" 2>/dev/null)
echo " 長さ（秒）    : ${DUR}"
echo " 形式          : $(soxi -r "$OUT")Hz / $(soxi -c "$OUT")ch / $(soxi -b "$OUT")bit"
echo "------------------------------------------------------------------"
# ファイルの途中に電波が切れるような「完全無音の区間」があるか
echo " ファイル内の無音区間（1本の途中で電波が切れる原因になり得る箇所）:"
SIL=$(sox "$OUT" /tmp/wd_sil.wav silence 1 0.1 0.1% 1 0.3 0.1% 2>&1; soxi -D /tmp/wd_sil.wav 2>/dev/null)
# 0.3 秒以上の無音を検出して位置を出す
sox "$OUT" -n stat -freq 2>/dev/null >/dev/null
python3 - "$OUT" <<'PY'
import sys, wave, audioop
w = wave.open(sys.argv[1], 'rb')
fr = w.getframerate(); n = w.getnframes()
data = w.readframes(n); w.close()
win = int(fr*0.05)  # 50ms 窓
sil_runs = []; cur = None
for i in range(0, len(data)-win*2, win*2):
    chunk = data[i:i+win*2]
    rms = audioop.rms(chunk, 2)
    t = i/2/fr
    if rms < 30:  # ほぼ無音
        if cur is None: cur = t
    else:
        if cur is not None:
            if t-cur >= 0.3: sil_runs.append((cur,t))
            cur = None
if cur is not None and (n/fr)-cur >= 0.3: sil_runs.append((cur, n/fr))
if sil_runs:
    for a,b in sil_runs:
        print(f"    {a:5.2f}s 〜 {b:5.2f}s  （{b-a:.2f}秒の無音）")
    print("    ※ この無音が長いと、TGIF が電波を切って分割送信のように聞こえ得ます")
else:
    print("    途中に目立つ無音区間なし（全体がつながった1本）")
PY
echo "=================================================================="

if [ "${1:-}" = "--send" ]; then
  echo ""
  echo " 送出テストします（bot を一時停止 → 送出 → 再開）"
  read -p " よろしいですか？ (y/N): " YN
  if [ "${YN,,}" = "y" ]; then
    echo " bot を停止..."
    systemctl stop dvswitch-bot
    sleep 1
    echo " 送出中..."
    python3 "$D/bin/test_send.py" "$OUT"
    echo " bot を再開..."
    systemctl start dvswitch-bot
    echo " 完了。無線機で『${HOUR}時です。続いて当地の天気は…』が"
    echo " 電波断なく1回で最後まで聞こえたか確認してください。"
  else
    echo " 送出はキャンセルしました。"
  fi
else
  echo ""
  echo " このファイルを実際に電波で送って確かめるには:"
  echo "   sudo bash weather_diag.sh --send"
fi
