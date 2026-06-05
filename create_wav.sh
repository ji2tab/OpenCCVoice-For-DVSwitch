#!/bin/bash

# ==============================================================================
# DVSwitch bot 固定WAVファイル 対話式作成スクリプト
#   配置: /opt/dvswitch_bot/bin/create_wav.sh
#   出力: /opt/dvswitch_bot/ 直下（fixed_intro/outro, time_intro, 001, 002 ほか）
#
#   使い方:
#     sudo ./create_wav.sh        対話で固定WAVを作成（上書き前に自動バックアップ）
#     sudo ./create_wav.sh -r     バックアップから復元（日付フォルダを選択）
#     sudo ./create_wav.sh -d     /opt/bak/ 配下の WAV バックアップを全削除
#     sudo ./create_wav.sh -h     ヘルプ
#
#   バックアップ:
#     上書き直前に、既存の *.wav を /opt/bak/wav_YYMMDDHHMMSS/ へ自動退避する。
#     （dvs_config.sh と同じ /opt/bak/ 配下にまとめる）
# ==============================================================================

# 定数定義 (Open JTalkの設定)
DIC_DIR="/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_MODEL="/usr/share/hts-voice/mei/mei_normal.htsvoice"
OUT_DIR="/opt/dvswitch_bot"
TMP_DIR="/tmp"
BAK_ROOT="/opt/bak"

# 管理対象の WAV（バックアップ／復元の対象。time_outro は未使用だが拾う）
WAV_FILES=(fixed_intro.wav fixed_outro.wav time_intro.wav 001.wav 002.wav time_outro.wav)

# ------------------------------------------------------------------------------
# 0. 初期セットアップ (権限チェック)
# ------------------------------------------------------------------------------

# root権限チェック（一般ユーザーで実行された場合は自動的にsudoで再実行）
if [ "$EUID" -ne 0 ]; then
  echo "root権限が必要です。sudoを使用してスクリプトを再実行します..."
  sudo "$0" "$@"
  exit $?
fi

# ------------------------------------------------------------------------------
# ヘルプ
# ------------------------------------------------------------------------------
show_help() {
  cat <<'EOF'
DVSwitch bot 固定WAV 作成ツール create_wav.sh

使い方:
  sudo ./create_wav.sh        対話で固定WAVを作成（上書き前に自動バックアップ）
  sudo ./create_wav.sh -r     バックアップから復元（日付フォルダを選択）
  sudo ./create_wav.sh -d     /opt/bak/ 配下の WAV バックアップを全削除
  sudo ./create_wav.sh -h     このヘルプを表示

生成されるWAV（/opt/dvswitch_bot/ 直下に上書き）:
  fixed_intro.wav  … カーチャンク応答イントロ
  fixed_outro.wav  … カーチャンク応答アウトロ
  time_intro.wav   … 時報イントロ
  001.wav / 002.wav … 定時メッセージ
  ※ time_outro.wav は現行 bot では未使用（生成はするが無害）

バックアップ:
  作成（上書き）の直前に、既存の *.wav を /opt/bak/wav_YYMMDDHHMMSS/ へ自動退避します。
  運用中に作り直して失敗しても、 -r で元のWAVセットに戻せます。

備考:
  bot は送出のたびにWAVを読み直すため、上書きすれば再起動なしで次の送出から反映されます。
EOF
}

# ------------------------------------------------------------------------------
# バックアップ（既存 *.wav を /opt/bak/wav_YYMMDDHHMMSS/ へ退避）
# ------------------------------------------------------------------------------
backup_wavs() {
  local ts dir f found=0
  ts="$(date +%y%m%d%H%M%S)"
  dir="${BAK_ROOT}/wav_${ts}"

  # 退避対象が1つでもあるか確認
  for f in "${WAV_FILES[@]}"; do
    [ -f "${OUT_DIR}/${f}" ] && found=1
  done
  if [ "$found" -eq 0 ]; then
    echo "[INFO] 既存のWAVが無いため、バックアップはスキップします（初回作成）。"
    return 0
  fi

  mkdir -p "$dir"
  echo "[INFO] 既存WAVをバックアップ: $dir"
  for f in "${WAV_FILES[@]}"; do
    if [ -f "${OUT_DIR}/${f}" ]; then
      cp -p "${OUT_DIR}/${f}" "$dir/"
      echo "       - ${f}"
    fi
  done
  echo ""
}

# ------------------------------------------------------------------------------
# 復元（-r）: 日付フォルダを選んで *.wav を戻す
# ------------------------------------------------------------------------------
do_restore() {
  if [ ! -d "$BAK_ROOT" ]; then
    echo "[ERROR] バックアップディレクトリがありません: $BAK_ROOT"
    exit 1
  fi
  mapfile -t DIRS < <(find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'wav_*' -printf '%f\n' | sort -r)
  if [ "${#DIRS[@]}" -eq 0 ]; then
    echo "[INFO] 復元できる WAV バックアップがありません（wav_* フォルダなし）。"
    exit 0
  fi

  echo "=========================================================="
  echo " 復元する WAV バックアップ（日付フォルダ）を選択してください"
  echo "----------------------------------------------------------"
  local i
  for i in "${!DIRS[@]}"; do
    printf "  %2d) %s\n" "$((i+1))" "${DIRS[$i]}"
  done
  echo "   0) キャンセル"
  echo "----------------------------------------------------------"
  read -ep "番号: " SEL

  [[ "$SEL" =~ ^[0-9]+$ ]] || { echo "数値を入力してください。中止。"; exit 1; }
  [ "$SEL" -eq 0 ] && { echo "キャンセルしました。"; exit 0; }
  [ "$SEL" -ge 1 ] && [ "$SEL" -le "${#DIRS[@]}" ] || { echo "範囲外です。中止。"; exit 1; }

  local pick="${DIRS[$((SEL-1))]}" src f
  src="${BAK_ROOT}/${pick}"
  echo ""
  echo "[INFO] 選択: $src"

  # 復元前に、現在のWAVを保険バックアップ
  echo "[INFO] 復元前の現状を保険バックアップします。"
  backup_wavs

  echo "[INFO] 復元中..."
  for f in "${WAV_FILES[@]}"; do
    if [ -f "${src}/${f}" ]; then
      cp -p "${src}/${f}" "${OUT_DIR}/"
      echo "       - ${f} を復元"
    fi
  done
  echo ""
  echo "[完了] 復元しました。bot は次の送出から復元後のWAVを読みます（再起動不要）。"
  exit 0
}

# ------------------------------------------------------------------------------
# 削除（-d）: WAV バックアップを全削除
# ------------------------------------------------------------------------------
do_delete() {
  if [ ! -d "$BAK_ROOT" ]; then
    echo "[INFO] $BAK_ROOT は存在しません。削除対象なし。"
    exit 0
  fi
  local cnt
  cnt="$(find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'wav_*' | wc -l)"
  if [ "$cnt" -eq 0 ]; then
    echo "[INFO] wav_* バックアップはありません。"
    exit 0
  fi
  echo "[WARN] $BAK_ROOT 配下の WAV バックアップ（wav_* フォルダ ${cnt}個）を削除します。"
  read -ep "本当に削除しますか？ (y/N): " CONFIRM
  if [[ "${CONFIRM,,}" == "y" ]]; then
    find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'wav_*' -exec rm -rf {} +
    echo "[完了] 削除しました。"
  else
    echo "キャンセルしました。"
  fi
  exit 0
}

# ------------------------------------------------------------------------------
# 引数処理
# ------------------------------------------------------------------------------
case "${1:-}" in
  -h|--help) show_help; exit 0 ;;
  -r)        do_restore ;;
  -d)        do_delete ;;
  "")        : ;;  # 引数なし → 通常の作成処理へ
  *)         echo "不明なオプション: $1"; echo ""; show_help; exit 1 ;;
esac

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
# 上書きの直前に、既存のWAVを /opt/bak/wav_YYMMDDHHMMSS/ へ自動退避
backup_wavs

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
echo "----------------------------------------------------------"
echo " bot は送出のたびにWAVを読み直すため、再起動は不要です。"
echo " 次のカーチャンク応答・時報・定時メッセージから新しい音声になります。"
echo " 元に戻したいときは:  sudo ./create_wav.sh -r"
echo "=========================================================="
