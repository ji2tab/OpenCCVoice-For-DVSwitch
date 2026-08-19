#!/bin/bash

# ==============================================================================
# DVSwitch bot 固定WAVファイル 対話式作成スクリプト
#   Version: V1.21 （🔴 chown_owner の引数順バグ修正。V1.1 の「chown 汎用化」は
#            引数順が逆で chown が常に失敗しており、生成物が root 所有のまま
#            だった。V1.2 の --regen・V1.0 の記録/プリフィルを含む）
#   配置: /opt/dvswitch_bot/bin/create_wav.sh
#   出力: /opt/dvswitch_bot/ 直下（fixed_intro/outro, time_intro, 001, 002 ほか）
#
#   変更履歴:
#     V1.0  初版。入力内容の wav_source.json 記録＋次回起動時プリフィル。
#     V1.1  生成物の chown を ocv:ocv 決め打ちから汎用化。$SUDO_USER →
#           UID 1000 の順で実ユーザーを特定し、その既定グループへ揃える
#           （chown_owner ヘルパに集約）。複数ユーザー非想定・www-data 等の
#           システムユーザー（UID<1000）は対象外、という構成前提に基づく。
#     V1.2  🔵 --regen（非対話再生成）モードを追加。ダッシュボード（app.py）が
#           wav_source.json を更新した後に `sudo create_wav.sh --regen` を呼び、
#           記録済みの texts を Open JTalk で全固定WAVへ再合成する。対話・確認は
#           一切しない。合成パイプライン（open_jtalk → sox、無音トリムの有無）は
#           対話モードとファイル単位で厳密に同一。texts は不変とし generated_at
#           のみ更新する（VV版 create_wav.sh V1.3 の do_regen と同方針。jtalk は
#           話者が1つのため voice は扱わない点だけが差）。
#     V1.21 🔴 chown_owner の引数順バグ修正（機能追加なし）。
#           V1.1 で導入した chown_owner は `chown "$@" "${OWNER_USER}:"` と
#           対象パスを先に渡していたため、chown がそれをユーザー名と解釈して
#           常に `invalid user` で失敗していた。`2>/dev/null || true` が
#           エラーを完全に握りつぶすため、V1.1 以降ずっと「汎用化したつもりで
#           実際には一度も所有者が変わっていない」状態だった（生成した WAV と
#           wav_source.json は root 所有のまま）。引数順を正し、失敗時は
#           WARN を出すようにした。dvs_config.sh V1.1 と同一方式。
#
#   使い方:
#     sudo ./create_wav.sh        対話で固定WAVを作成（上書き前に自動バックアップ）
#     sudo ./create_wav.sh -r     バックアップから復元（日付フォルダを選択）
#     sudo ./create_wav.sh -d     /opt/dvswitch_bot/bak/wav/ 配下の WAV バックアップを全削除
#     sudo ./create_wav.sh -h     ヘルプ
#
#   バックアップ:
#     上書き直前に、既存の *.wav を /opt/dvswitch_bot/bak/wav/YYMMDDHHMMSS/ へ自動退避する。
#     （dvs_config.sh と同じ /opt/dvswitch_bot/bak/ 配下にまとめる）
#
# ------------------------------------------------------------------------------
#   🔵 改修（2026-06-24）: 入力内容（読み上げソーステキスト）の記録と再利用
# ------------------------------------------------------------------------------
#   従来このスクリプトは、入力した文字列をどこにも保存せず WAV だけを出力して
#   いたため、「このWAVが何を喋っているのか」「次に作り直すとき同じ内容を再入力
#   する」のが手間だった。本改修で次の2点を追加した。
#
#   (1) 生成時に入力内容を JSON へ保存
#       生成のたびに、入力原文・確認後の読み仮名・実際に合成した最終テキストを
#       /opt/dvswitch_bot/wav_source.json に書き出す。後から内容を完全に復元できる。
#       ※ bot_config.json には追記しない。bot_config.json は dvswitch_bot.py /
#         bot_setup.py / app.py が共有し、後者2つは「知っているキーだけ」で保存し
#         直すため、無関係なキーを足すと消える。WAV のソースは性質が別物なので
#         専用ファイル(wav_source.json)に分離している。
#
#   (2) 次回起動時に前回値をプリフィル
#       wav_source.json があれば、各 read プロンプトの初期値(-i)に前回の入力を
#       流し込む。そのまま Enter で前回と同じ内容を再生成できる。コールサイン等を
#       変えなければ、手で直した読み仮名もそのまま再利用される。
#
#   JSON の読み書きは、日本語・記号のエスケープを安全に扱うため python3 を用いる
#   （bot が python3 前提の環境なので追加依存はない）。
# ==============================================================================

# 🔵 機械可読バージョン（固定行）。版を上げるときはヘッダーの Version 表記と一致させる。
SCRIPT_VERSION="V1.21"

# 定数定義 (Open JTalkの設定)
DIC_DIR="/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_MODEL="/usr/share/hts-voice/mei/mei_normal.htsvoice"
OUT_DIR="/opt/dvswitch_bot"
TMP_DIR="/tmp"
BAK_ROOT="/opt/dvswitch_bot/bak/wav"

# 🔵 改修: 入力内容（読み上げソーステキスト）の保存先
SRC_JSON="/opt/dvswitch_bot/wav_source.json"

# ------------------------------------------------------------------------------
# 🔵 V1.1: 生成物の所有者を汎用的に決定する（ocv 決め打ちを廃止）
# ------------------------------------------------------------------------------
# 本スクリプトは sudo（root）で動くため、何もしないと生成物が root 所有になり、
# bot やダッシュボード（dvswitch-web）など非root プロセスから読めなくなる。
# そこで生成物の所有者を「実ユーザー」に戻す。
#
# 前提（システム構成の制約）: root 以外の実ユーザーは1人だけ（raspberry/pi-star/
# ocv 構成）。www-data 等のサービス用アカウントは UID < 1000 に割り当てられるため、
# UID 1000（人間が最初に作る一般ユーザー）を見れば実ユーザーを一意に特定できる。
#
# 決定順:
#   1) $SUDO_USER  … sudo した本人（通常はこれで確定。最も自然）
#   2) UID 1000    … root 直実行などで $SUDO_USER が空のときの保険
# どちらも取れない場合は空のままとし、所有者変更はスキップする（chown は
# 末尾の "|| true" で握りつぶすため、スクリプトは止まらない）。
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  OWNER_USER="$SUDO_USER"
else
  OWNER_USER="$(id -nu 1000 2>/dev/null)"
fi

# 所有者を OWNER_USER（の既定グループ）へ揃えるヘルパ。
# グループは "ユーザー名:" とコロン止めで「そのユーザーの既定グループ」に任せる
# （ocv:ocv のようにグループ名まで決め打ちすると、グループ名が異なる環境で外す）。
# OWNER_USER が空のときは何もしない。
#
# 🔴 引数順に注意: chown は「所有者 → 対象」の順で渡す。V1.1〜V1.2 は
#    `chown "$@" "${OWNER_USER}:"` と対象を先に書いていたため、chown が対象パスを
#    ユーザー名と解釈して常に `invalid user` で失敗していた（2>/dev/null || true が
#    エラーを握りつぶすため気づけなかった）。結果、生成物は root 所有のままだった。
#    失敗を黙らせず WARN として出す（スクリプト自体は止めない）。
chown_owner() {
  [ -n "$OWNER_USER" ] || return 0
  chown "${OWNER_USER}:" "$@" || echo "   [WARN] 所有者を ${OWNER_USER} に変更できませんでした: $*" >&2
}

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
  echo "create_wav.sh ${SCRIPT_VERSION}"
  echo ""
  cat <<'EOF'
DVSwitch bot 固定WAV 作成ツール create_wav.sh

使い方:
  sudo ./create_wav.sh        対話で固定WAVを作成（上書き前に自動バックアップ）
  sudo ./create_wav.sh -r     バックアップから復元（日付フォルダを選択）
  sudo ./create_wav.sh -d     /opt/dvswitch_bot/bak/wav/ 配下の WAV バックアップを全削除
  sudo ./create_wav.sh --regen 記録済み内容(texts)で全固定WAVを非対話再生成（ダッシュボード用）
  sudo ./create_wav.sh -h     このヘルプを表示

生成されるWAV（/opt/dvswitch_bot/ 直下に上書き）:
  fixed_intro.wav  … カーチャンク応答イントロ
  fixed_outro.wav  … カーチャンク応答アウトロ
  time_intro.wav   … 時報イントロ
  001.wav / 002.wav … 定時メッセージ
  ※ time_outro.wav は現行 bot では未使用（生成はするが無害）

入力内容の記録（wav_source.json）:
  生成時に、入力原文・読み仮名・合成テキストを /opt/dvswitch_bot/wav_source.json
  へ保存します。次回起動時はこの内容を各入力欄の初期値として読み込むため、
  そのまま Enter で前回と同じWAVを再生成できます。
  （bot_config.json には一切追記しません。WAV のソースは別ファイルで管理します。）

バックアップ:
  作成（上書き）の直前に、既存の *.wav と wav_source.json を
  /opt/dvswitch_bot/bak/wav/YYMMDDHHMMSS/ へ自動退避します。
  運用中に作り直して失敗しても、 -r で元のWAVセット（と入力記録）に戻せます。

備考:
  bot は送出のたびにWAVを読み直すため、上書きすれば再起動なしで次の送出から反映されます。
EOF
}

# ------------------------------------------------------------------------------
# 🔵 改修: wav_source.json から前回の入力値を読み込む
#   出力: 配列 PRIOR に 7 要素を格納（順序固定）
#     [0]callsign [1]callsign_kana [2]location [3]msg1 [4]msg1_kana [5]msg2 [6]msg2_kana
#   ファイルが無い／壊れている場合は全要素を空にする（プリフィル無しと同等）。
#   フィールド区切りに US(0x1f)を用い、テキスト中の改行・記号で壊れないようにする。
# ------------------------------------------------------------------------------
PRIOR=()
load_prior() {
  PRIOR=("" "" "" "" "" "" "")
  [ -f "$SRC_JSON" ] || return 0
  mapfile -t -d $'\x1f' PRIOR < <(python3 - "$SRC_JSON" <<'PYEOF'
import json, sys
keys = ["callsign", "callsign_kana", "location", "msg1", "msg1_kana", "msg2", "msg2_kana"]
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        d = {}
except Exception:
    d = {}
sys.stdout.write("\x1f".join(str(d.get(k, "")) for k in keys))
PYEOF
)
  # 要素数が欠けた場合に備えて 7 要素へ正規化
  while [ "${#PRIOR[@]}" -lt 7 ]; do PRIOR+=(""); done
}

# ------------------------------------------------------------------------------
# 🔵 改修: 入力内容を wav_source.json へ保存する
#   値は環境変数経由で python3 に渡す（クォート事故を避けるため）。
#   入力原文・読み仮名に加え、実際に合成した最終テキスト(texts)も残し、
#   後から「何を喋っているWAVなのか」を完全に復元できるようにする。
# ------------------------------------------------------------------------------
save_source_json() {
  GEN_AT="$(date '+%Y-%m-%d %H:%M:%S')" \
  J_CALLSIGN="$CALLSIGN" \
  J_CALLSIGN_KANA="$CALLSIGN_KANA" \
  J_LOCATION="$LOCATION" \
  J_MSG1="$MSG1" \
  J_MSG1_KANA="$MSG1_KANA" \
  J_MSG2="$MSG2" \
  J_MSG2_KANA="$MSG2_KANA" \
  J_FIXED_INTRO="$BASE_INTRO_TEXT" \
  J_FIXED_OUTRO="カーチャンクです。" \
  J_TIME_INTRO="こちらは、${CALLSIGN_KANA}、" \
  J_TEXT_001="$TEXT_001" \
  J_TEXT_002="$TEXT_002" \
  J_TIME_OUTRO="です。" \
  python3 - "$SRC_JSON" <<'PYEOF'
import json, os, sys
d = {
    "generated_at":  os.environ.get("GEN_AT", ""),
    "callsign":      os.environ.get("J_CALLSIGN", ""),
    "callsign_kana": os.environ.get("J_CALLSIGN_KANA", ""),
    "location":      os.environ.get("J_LOCATION", ""),
    "msg1":          os.environ.get("J_MSG1", ""),
    "msg1_kana":     os.environ.get("J_MSG1_KANA", ""),
    "msg2":          os.environ.get("J_MSG2", ""),
    "msg2_kana":     os.environ.get("J_MSG2_KANA", ""),
    # 実際に Open JTalk へ渡した最終テキスト（合成内容の記録）
    "texts": {
        "fixed_intro": os.environ.get("J_FIXED_INTRO", ""),
        "fixed_outro": os.environ.get("J_FIXED_OUTRO", ""),
        "time_intro":  os.environ.get("J_TIME_INTRO", ""),
        "001":         os.environ.get("J_TEXT_001", ""),
        "002":         os.environ.get("J_TEXT_002", ""),
        "time_outro":  os.environ.get("J_TIME_OUTRO", ""),
    },
}
path = sys.argv[1]
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
    f.write("\n")
os.replace(tmp, path)
PYEOF
  # 所有者を実ユーザー（の既定グループ）に揃える（sudo 実行で root 化するのを防ぐ）
  chown_owner "$SRC_JSON"
}

# ------------------------------------------------------------------------------
# バックアップ（既存 *.wav と wav_source.json を /opt/dvswitch_bot/bak/wav/YYMMDDHHMMSS/ へ退避）
# ------------------------------------------------------------------------------
backup_wavs() {
  local ts dir f found=0
  ts="$(date +%y%m%d%H%M%S)"
  dir="${BAK_ROOT}/${ts}"

  # 退避対象が1つでもあるか確認（WAV または ソースJSON）
  for f in "${WAV_FILES[@]}"; do
    [ -f "${OUT_DIR}/${f}" ] && found=1
  done
  [ -f "$SRC_JSON" ] && found=1

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
  # 🔵 改修: 入力記録(wav_source.json)も WAV と同じ世代でバックアップする。
  # 古いWAVセットへ復元したときに、対応する入力記録（＝プリフィル元）も一緒に
  # 戻るようにし、WAV と記録がズレないようにする。
  if [ -f "$SRC_JSON" ]; then
    cp -p "$SRC_JSON" "$dir/"
    echo "       - $(basename "$SRC_JSON")"
  fi
  # 所有者を実ユーザー（の既定グループ）に揃える（sudo 実行で root 化するのを防ぐ）
  chown_owner -R /opt/dvswitch_bot/bak
  echo ""
}

# ------------------------------------------------------------------------------
# 復元（-r）: 日付フォルダを選んで *.wav と wav_source.json を戻す
# ------------------------------------------------------------------------------
do_restore() {
  if [ ! -d "$BAK_ROOT" ]; then
    echo "[ERROR] バックアップディレクトリがありません: $BAK_ROOT"
    exit 1
  fi
  mapfile -t DIRS < <(find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r)
  if [ "${#DIRS[@]}" -eq 0 ]; then
    echo "[INFO] 復元できる WAV バックアップがありません。"
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
  # 🔵 改修: 入力記録(wav_source.json)も対になっていれば一緒に復元する。
  if [ -f "${src}/$(basename "$SRC_JSON")" ]; then
    cp -p "${src}/$(basename "$SRC_JSON")" "$SRC_JSON"
    chown_owner "$SRC_JSON"
    echo "       - $(basename "$SRC_JSON") を復元"
  fi
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
  cnt="$(find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d | wc -l)"
  if [ "$cnt" -eq 0 ]; then
    echo "[INFO] WAV バックアップはありません。"
    exit 0
  fi
  echo "[WARN] $BAK_ROOT 配下の WAV バックアップ（${cnt}個）を削除します。"
  read -ep "本当に削除しますか？ (y/N): " CONFIRM
  if [[ "${CONFIRM,,}" == "y" ]]; then
    find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
    echo "[完了] 削除しました。"
  else
    echo "キャンセルしました。"
  fi
  exit 0
}

# ------------------------------------------------------------------------------
# 🔵 V1.2: 非対話再生成（--regen）
#   ダッシュボード（app.py の /wav_source_config）が wav_source.json を更新した
#   直後に `sudo create_wav.sh --regen` として呼ぶ。記録済みの texts を Open JTalk
#   で全固定WAVへ再合成する。対話・確認は一切しない。
#   合成パイプライン（open_jtalk → sox、無音トリムの有無）は対話モードの生成部と
#   ファイル単位で厳密に同一であること（変更時は両方を必ず揃える）。
#   texts は書き換えず generated_at のみ更新する（VV版 do_regen と同方針。jtalk は
#   話者が1つのため voice フィールドは扱わない）。
# ------------------------------------------------------------------------------
do_regen() {
  echo "=========================================================="
  echo " 非対話再生成（--regen）  ${SCRIPT_VERSION}"
  echo "=========================================================="

  if [ ! -f "$SRC_JSON" ]; then
    echo "[ERROR] ${SRC_JSON} がありません。先に対話モードで一度WAVを作成してください。"
    exit 1
  fi

  # texts を US(0x1f) 区切りで取り出す（順序固定）。
  # [0]fixed_intro [1]fixed_outro [2]time_intro [3]001 [4]002 [5]time_outro
  local FIELDS=()
  mapfile -t -d $'\x1f' FIELDS < <(python3 - "$SRC_JSON" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
except Exception:
    d = {}
t = d.get("texts", {}) if isinstance(d, dict) else {}
if not isinstance(t, dict):
    t = {}
keys = ["fixed_intro", "fixed_outro", "time_intro", "001", "002", "time_outro"]
out = [str(t.get(k, "")) for k in keys]
sys.stdout.write("\x1f".join(out))
PYEOF
)
  while [ "${#FIELDS[@]}" -lt 6 ]; do FIELDS+=(""); done

  local T_INTRO="${FIELDS[0]}" T_OUTRO="${FIELDS[1]}" T_TIME="${FIELDS[2]}"
  local T_001="${FIELDS[3]}"   T_002="${FIELDS[4]}"   T_TOUT="${FIELDS[5]}"

  # texts が空（旧形式の wav_source.json など）は再生成不能
  if [ -z "$T_INTRO" ] || [ -z "$T_001" ] || [ -z "$T_002" ]; then
    echo "[ERROR] wav_source.json に texts の記録がありません（旧形式の可能性）。"
    echo "        対話モード（引数なし）で一度作成し直すと記録されます。"
    exit 1
  fi

  echo "[INFO] 記録済みテキストで全固定WAVを再生成します（Open JTalk / mei_normal）。"
  echo ""

  # 上書き直前の自動バックアップ（対話モードと同一）
  backup_wavs

  echo "WAVファイルを生成中..."

  # --- fixed_intro.wav（無音トリムなし：対話モードと同一）---
  echo "$T_INTRO" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/temp_intro.wav" \
    && sox "${TMP_DIR}/temp_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_intro.wav" \
    && echo " [OK] fixed_intro.wav" || { echo " [NG] fixed_intro.wav"; exit 1; }

  # --- fixed_outro.wav（無音トリムなし）---
  echo "$T_OUTRO" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/temp_outro.wav" \
    && sox "${TMP_DIR}/temp_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_outro.wav" \
    && echo " [OK] fixed_outro.wav" || { echo " [NG] fixed_outro.wav"; exit 1; }

  # --- time_intro.wav（前後の無音トリムあり：対話モードと同一）---
  echo "$T_TIME" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/time_intro.wav" \
    && sox "${TMP_DIR}/time_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_intro.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse \
    && echo " [OK] time_intro.wav" || { echo " [NG] time_intro.wav"; exit 1; }

  # --- 001.wav（前後の無音トリムあり）---
  echo "$T_001" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/001_raw.wav" \
    && sox "${TMP_DIR}/001_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/001.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse \
    && echo " [OK] 001.wav" || { echo " [NG] 001.wav"; exit 1; }

  # --- 002.wav（前後の無音トリムあり）---
  echo "$T_002" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/002_raw.wav" \
    && sox "${TMP_DIR}/002_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/002.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse \
    && echo " [OK] 002.wav" || { echo " [NG] 002.wav"; exit 1; }

  # --- time_outro.wav（無音トリムなし）---
  echo "$T_TOUT" | open_jtalk -x "$DIC_DIR" -m "$VOICE_MODEL" -ow "${TMP_DIR}/time_outro.wav" \
    && sox "${TMP_DIR}/time_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_outro.wav" \
    && echo " [OK] time_outro.wav" || { echo " [NG] time_outro.wav"; exit 1; }

  # generated_at のみ更新（texts は不変）
  python3 - "$SRC_JSON" <<'PYEOF'
import json, os, sys
from datetime import datetime
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    d = json.load(f)
d["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
    f.write("\n")
os.replace(tmp, path)
PYEOF
  chown_owner "$SRC_JSON"
  echo " [OK] wav_source.json （generated_at を更新）"

  # 一時ファイルの削除（対話モードと同一）
  rm -f "${TMP_DIR}/temp_intro.wav" "${TMP_DIR}/temp_outro.wav" "${TMP_DIR}/time_intro.wav" \
        "${TMP_DIR}/001_raw.wav" "${TMP_DIR}/002_raw.wav" "${TMP_DIR}/time_outro.wav"

  echo ""
  echo "[完了] 固定WAVを再生成しました。"
  echo "       bot は送出のたびに固定WAVを読み直すため、再起動は不要です。"
  exit 0
}

# ------------------------------------------------------------------------------
# 引数処理
# ------------------------------------------------------------------------------
case "${1:-}" in
  -h|--help) show_help; exit 0 ;;
  -r)        do_restore ;;
  -d)        do_delete ;;
  --regen)   do_regen ;;
  "")        : ;;  # 引数なし → 通常の作成処理へ
  *)         echo "不明なオプション: $1"; echo ""; show_help; exit 1 ;;
esac

# 出力先ディレクトリの確認・作成
if [ ! -d "$OUT_DIR" ]; then
  echo "[INFO] 出力先ディレクトリ ${OUT_DIR} が存在しないため、新規作成します。"
  mkdir -p "$OUT_DIR"
fi

echo "=========================================================="
echo " DVSwitch bot WAVファイル対話式ジェネレーター  ${SCRIPT_VERSION}"
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

# 🔵 改修: 前回の入力値を読み込む（あれば各入力欄の初期値に使う）
load_prior
if [ -f "$SRC_JSON" ]; then
  echo "[INFO] 前回の入力内容を読み込みました（${SRC_JSON}）。"
  echo "       各項目は前回値を初期表示します。変更なければそのまま Enter。"
  echo ""
fi

# コールサインの入力（前回値があれば初期表示）
read -ep "1. コールサインを入力してください (例: JJ2YYK): " -i "${PRIOR[0]}" CALLSIGN
# 読み仮名の初期値: コールサインが前回と同一なら、手で直した前回の読み仮名を再利用。
# 変わっていれば自動生成し直す。
if [ -n "${PRIOR[1]}" ] && [ "$CALLSIGN" == "${PRIOR[0]}" ]; then
  CALLSIGN_KANA_DEFAULT="${PRIOR[1]}"
else
  CALLSIGN_KANA_DEFAULT="$(callsign_to_kana "$CALLSIGN")"
fi
read -ep "   -> 読み仮名を確認・修正してください: " -i "$CALLSIGN_KANA_DEFAULT" CALLSIGN_KANA

# 地名の入力（前回値があれば初期表示）
read -ep "2. 設置場所の地名を入力してください (漢字・ひらがな等 例: 尾張旭): " -i "${PRIOR[2]}" LOCATION

# メッセージの入力
echo ""
read -ep "3. 定時メッセージ1を入力してください: " -i "${PRIOR[3]}" MSG1
if [ -n "${PRIOR[4]}" ] && [ "$MSG1" == "${PRIOR[3]}" ]; then
  MSG1_KANA_DEFAULT="${PRIOR[4]}"
else
  MSG1_KANA_DEFAULT="$(msg_alphanum_to_kana "$MSG1")"
fi
read -ep "   -> 読みを確認・修正してください: " -i "$MSG1_KANA_DEFAULT" MSG1_KANA

echo ""
read -ep "4. 定時メッセージ2を入力してください: " -i "${PRIOR[5]}" MSG2
if [ -n "${PRIOR[6]}" ] && [ "$MSG2" == "${PRIOR[5]}" ]; then
  MSG2_KANA_DEFAULT="${PRIOR[6]}"
else
  MSG2_KANA_DEFAULT="$(msg_alphanum_to_kana "$MSG2")"
fi
read -ep "   -> 読みを確認・修正してください: " -i "$MSG2_KANA_DEFAULT" MSG2_KANA

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
# 上書きの直前に、既存のWAVを /opt/dvswitch_bot/bak/wav/YYMMDDHHMMSS/ へ自動退避
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
# 🔵 改修: 入力内容を wav_source.json へ保存（次回起動時のプリフィル元になる）
# ------------------------------------------------------------------------------
save_source_json
echo " [OK] wav_source.json （入力内容を記録）"

# ------------------------------------------------------------------------------
# 4. 後処理・確認
# ------------------------------------------------------------------------------

# 一時ファイルの削除
rm -f "${TMP_DIR}/temp_intro.wav" "${TMP_DIR}/temp_outro.wav" "${TMP_DIR}/time_intro.wav" "${TMP_DIR}/001_raw.wav" "${TMP_DIR}/002_raw.wav" "${TMP_DIR}/time_outro.wav"

echo ""
echo "=========================================================="
echo " すべての処理が完了しました！"
echo " 出力先: $OUT_DIR"
echo " 入力記録: $SRC_JSON"
echo "----------------------------------------------------------"
echo " bot は送出のたびにWAVを読み直すため、再起動は不要です。"
echo " 次のカーチャンク応答・時報・定時メッセージから新しい音声になります。"
echo " 次回このスクリプトを起動すると、今回の入力が初期値として表示されます。"
echo " 元に戻したいときは:  sudo ./create_wav.sh -r"
echo "=========================================================="
