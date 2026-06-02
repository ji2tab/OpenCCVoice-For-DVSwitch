#!/bin/bash

# ==============================================================================
# DVSwitch bot V1.58 固定WAVファイル 対話式作成スクリプト
# ==============================================================================

# 定数定義 (Open JTalkの設定)
DIC_DIR="/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_MODEL="/usr/share/hts-voice/mei/mei_normal.htsvoice"
OUT_DIR="/opt/dvswitch_bot"
TMP_DIR="/tmp"

# ------------------------------------------------------------------------------
# 0. 初期セットアップ (権限・ディレクトリチェック)
# ------------------------------------------------------------------------------

# root権限チェック（一般ユーザーで実行された場合は自動的にsudoで再実行）
if [ "$EUID" -ne 0 ]; then
  echo "root権限が必要です。sudoを使用してスクリプトを再実行します..."
  sudo "$0" "$@"
  exit $?
fi

# 出力先ディレクトリの確認・作成
if [ ! -d "$OUT_DIR" ]; then
  echo "[INFO] 出力先ディレクトリ ${OUT_DIR} が存在しないため、新規作成します。"
  mkdir -p "$OUT_DIR"
fi

echo "=========================================================="
echo " DVSwitch bot WAVファイル対話式ジェネレーター"
echo "=========================================================="
echo ""

# ------------------------------------------------------------------------------
# 1. 英数字の自動カナ変換関数
# ------------------------------------------------------------------------------

# 【コールサイン用】数字を英語読み(ワン、ツー、スリー...)に変換
function callsign_to_kana() {
    local input="$1"
    local kana=""
    local char=""
    for (( i=0; i<${#input}; i++ )); do
        char="${input:$i:1}"
        case "${char^^}" in
            A) kana+="エー" ;; B) kana+="ビー" ;; C) kana+="シー" ;; D) kana+="ディー" ;;
            E) kana+="イー" ;; F) kana+="エフ" ;; G) kana+="ジー" ;; H) kana+="エイチ" ;;
            I) kana+="アイ" ;; J) kana+="ジェイ" ;; K) kana+="ケー" ;; L) kana+="エル" ;;
            M) kana+="エム" ;; N) kana+="エヌ" ;; O) kana+="オー" ;; P) kana+="ピー" ;;
            Q) kana+="キュー" ;; R) kana+="アール" ;; S) kana+="エス" ;; T) kana+="ティー" ;;
            U) kana+="ユー" ;; V) kana+="ブイ" ;; W) kana+="ダブリュー" ;; X) kana+="エックス" ;;
            Y) kana+="ワイ" ;; Z) kana+="ゼット" ;;
            0) kana+="ゼロ" ;; 1) kana+="ワン" ;; 2) kana+="ツー" ;; 3) kana+="スリー" ;;
            4) kana+="フォー" ;; 5) kana+="ファイブ" ;; 6) kana+="シックス" ;;
            7) kana+="セブン" ;; 8) kana+="エイト" ;; 9) kana+="ナイン" ;;
            *) kana+="$char" ;;
        esac
    done
    echo "$kana"
}

# 【メッセージ用】数字を日本語読み(イチ、ニー、サン...)に変換
function msg_alphanum_to_kana() {
    local input="$1"
    local kana=""
    local char=""
    for (( i=0; i<${#input}; i++ )); do
        char="${input:$i:1}"
        case "${char^^}" in
            A) kana+="エー" ;; B) kana+="ビー" ;; C) kana+="シー" ;; D) kana+="ディー" ;;
            E) kana+="イー" ;; F) kana+="エフ" ;; G) kana+="ジー" ;; H) kana+="エイチ" ;;
            I) kana+="アイ" ;; J) kana+="ジェイ" ;; K) kana+="ケー" ;; L) kana+="エル" ;;
            M) kana+="エム" ;; N) kana+="エヌ" ;; O) kana+="オー" ;; P) kana+="ピー" ;;
            Q) kana+="キュー" ;; R) kana+="アール" ;; S) kana+="エス" ;; T) kana+="ティー" ;;
            U) kana+="ユー" ;; V) kana+="ブイ" ;; W) kana+="ダブリュー" ;; X) kana+="エックス" ;;
            Y) kana+="ワイ" ;; Z) kana+="ゼット" ;;
            0) kana+="ゼロ" ;; 1) kana+="イチ" ;; 2) kana+="ニー" ;; 3) kana+="サン" ;;
            4) kana+="ヨン" ;; 5) kana+="ゴー" ;; 6) kana+="ロク" ;; 7) kana+="ナナ" ;;
            8) kana+="ハチ" ;; 9) kana+="キュー" ;;
            *) kana+="$char" ;;
        esac
    done
    echo "$kana"
}

# ------------------------------------------------------------------------------
# 2. ユーザー入力セッション
# ------------------------------------------------------------------------------

# コールサインの入力
read -ep "1. コールサインを入力してください (例: JJ2YYK): " CALLSIGN
AUTO_KANA=$(callsign_to_kana "$CALLSIGN")
# -i オプションで変換後のテキストを初期値としてセット。そのままEnterでOK、矢印キーで修正も可能。
read -ep "   -> 読み仮名を確認・修正してください: " -i "$AUTO_KANA" CALLSIGN_KANA

# 地名の入力
read -ep "2. 設置場所の地名を入力してください (漢字・ひらがな等 例: 尾張旭): " LOCATION

# メッセージの入力
echo ""
read -ep "3. 定時メッセージ1を入力してください: " MSG1
AUTO_MSG1=$(msg_alphanum_to_kana "$MSG1")
read -ep "   -> 読みを確認・修正してください: " -i "$AUTO_MSG1" MSG1_KANA

echo ""
read -ep "4. 定時メッセージ2を入力してください: " MSG2
AUTO_MSG2=$(msg_alphanum_to_kana "$MSG2")
read -ep "   -> 読みを確認・修正してください: " -i "$AUTO_MSG2" MSG2_KANA

# 読み上げベーステキストの組み立て
BASE_INTRO_TEXT="こちらは、${CALLSIGN_KANA}、${LOCATION} ディーエムアール デジピーターです。"

echo ""
echo "以下の読み上げ内容でWAVファイルを生成します:"
echo "----------------------------------------------------------"
echo " [fixed_intro.wav] : $BASE_INTRO_TEXT"
echo " [fixed_outro.wav] : カーチャンクです。"
echo " [time_intro.wav]  : こちらは、${CALLSIGN_KANA}、"
echo " [001.wav]         : ${BASE_INTRO_TEXT}${MSG1_KANA}"
echo " [002.wav]         : ${BASE_INTRO_TEXT}${MSG2_KANA}"
echo " [time_outro.wav]  : です。"
echo "----------------------------------------------------------"
read -ep "よろしいですか？ (Y/n): " CONFIRM
if [[ "${CONFIRM^^}" == "N" ]]; then
    echo "処理を中止しました。"
    exit 1
fi

echo ""
echo "WAVファイルを生成中..."

# ------------------------------------------------------------------------------
# 3. 音声合成とSoX処理
# ------------------------------------------------------------------------------

# --- fixed_intro.wav ---
echo "$BASE_INTRO_TEXT" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/temp_intro.wav"
sox "${TMP_DIR}/temp_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_intro.wav"
echo " [OK] fixed_intro.wav"

# --- fixed_outro.wav ---
echo "カーチャンクです。" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/temp_outro.wav"
sox "${TMP_DIR}/temp_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_outro.wav"
echo " [OK] fixed_outro.wav"

# --- time_intro.wav ---
echo "こちらは、${CALLSIGN_KANA}、" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/time_intro.wav"
sox "${TMP_DIR}/time_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_intro.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse
echo " [OK] time_intro.wav"

# --- 001.wav ---
TEXT_001="${BASE_INTRO_TEXT}${MSG1_KANA}"
echo "$TEXT_001" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/001_raw.wav"
sox "${TMP_DIR}/001_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/001.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse
echo " [OK] 001.wav"

# --- 002.wav ---
TEXT_002="${BASE_INTRO_TEXT}${MSG2_KANA}"
echo "$TEXT_002" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/002_raw.wav"
sox "${TMP_DIR}/002_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/002.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse
echo " [OK] 002.wav"

# --- time_outro.wav ---
echo "です。" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/time_outro.wav"
sox "${TMP_DIR}/time_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_outro.wav"
echo " [OK] time_outro.wav"

# ------------------------------------------------------------------------------
# 4. 後処理・確認
# ------------------------------------------------------------------------------

# 一時ファイルの削除
rm -f "${TMP_DIR}/temp_intro.wav" "${TMP_DIR}/temp_outro.wav" "${TMP_DIR}/time_intro.wav" "${TMP_DIR}/001_raw.wav" "${TMP_DIR}/002_raw.wav" "${TMP_DIR}/time_outro.wav"

echo ""
echo "=========================================================="
echo " すべての処理が完了しました！"
echo " 出力先: $OUT_DIR"
echo "=========================================================="
