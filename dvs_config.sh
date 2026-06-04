#!/bin/bash
# ==============================================================================
# DVSwitch 設定対話ツール  dvs_config.sh
#   配置: /opt/dvswitch_bot/bin/dvs_config.sh
#   TGIF 接続を前提に、ユーザ毎の可変項目を対話入力し、3つの ini を更新する。
#   編集前に /opt/bak/YYMMDDHHMMSS/ へ 3ファイルをまとめてバックアップする。
#
#   使い方（bin ディレクトリに cd して実行、または絶対パスで実行）:
#     cd /opt/dvswitch_bot/bin && sudo ./dvs_config.sh   対話編集（編集前に自動バックアップ）
#     sudo /opt/dvswitch_bot/bin/dvs_config.sh           （絶対パスでも可）
#     sudo ./dvs_config.sh -r     バックアップから復元（日付フォルダを選択）
#     sudo ./dvs_config.sh -d     /opt/bak/ 配下のバックアップを全削除
#     sudo ./dvs_config.sh -h     ヘルプ
#
#   対象ファイル:
#     /opt/MMDVM_Bridge/MMDVM_Bridge.ini
#     /opt/MMDVM_Bridge/DVSwitch.ini      （バックアップ対象。本ツールでは値変更なし）
#     /opt/Analog_Bridge/Analog_Bridge.ini
#
#   対話で入力する可変項目:
#     callsign       -> MMDVM Callsign
#     dmrid (7桁)    -> MMDVM Id(先頭7桁), Analog gatewayDmrId, Analog repeaterID(先頭7桁)
#     essid (2桁)    -> MMDVM Id(末尾2桁), Analog repeaterID(末尾2桁)
#     tgifpassword   -> MMDVM Password
#     txtgif         -> Analog txTg
#
#   スクリプトが固定値でセットする項目:
#     MMDVM [DMR] Enable = 1
#     MMDVM [DMR Network] Enable = 1
#     MMDVM [DMR Network] Address = tgif.network
#     Analog [USRP] txPort = 51001
#     Analog [USRP] rxPort = 51000
#     Analog [USRP] usrpAudio = AUDIO_USE_GAIN
#     Analog [USRP] tlvAudio = AUDIO_USE_GAIN
# ==============================================================================

set -u

MMDVM_INI="/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
DVSWITCH_INI="/opt/MMDVM_Bridge/DVSwitch.ini"
ANALOG_INI="/opt/Analog_Bridge/Analog_Bridge.ini"
TARGET_FILES=("$MMDVM_INI" "$DVSWITCH_INI" "$ANALOG_INI")

BAK_ROOT="/opt/bak"

FIX_ADDRESS="tgif.network"
FIX_USRP_TXPORT="51001"
FIX_USRP_RXPORT="51000"
FIX_USRP_AUDIO="AUDIO_USE_GAIN"
FIX_TLV_AUDIO="AUDIO_USE_GAIN"

if [ "$EUID" -ne 0 ]; then
  echo "root 権限が必要です。sudo で再実行します..."
  exec sudo "$0" "$@"
fi

# サービス再起動（y/N 確認つき）。do_edit / do_restore から呼ぶ。
restart_services() {
  echo ""
  read -ep "analog_bridge と mmdvm_bridge を今すぐ再起動しますか？ (y/N): " RST
  if [[ "${RST,,}" == "y" ]]; then
    echo "[INFO] サービスを再起動します..."
    systemctl restart analog_bridge mmdvm_bridge
    sleep 3
    echo "[INFO] 状態:"
    systemctl is-active analog_bridge mmdvm_bridge
    echo "[完了] 再起動しました。"
  else
    echo "再起動はスキップしました。手動で有効化してください:"
    echo "   sudo systemctl restart analog_bridge mmdvm_bridge"
  fi
}

show_help() {
  cat <<'EOF'
DVSwitch 設定対話ツール dvs_config.sh （TGIF 接続前提）

使い方:
  sudo ./dvs_config.sh        対話形式で ini を編集（編集前に自動バックアップ）
  sudo ./dvs_config.sh -r     バックアップから復元（日付フォルダを選択して一括リストア）
  sudo ./dvs_config.sh -d     /opt/bak/ 配下のバックアップをすべて削除
  sudo ./dvs_config.sh -h     このヘルプを表示

対話入力する項目:
  callsign / dmrid(7桁) / essid(2桁) / tgifpassword / txtgif

自動でセットされる固定値:
  MMDVM [DMR]Enable=1, [DMR Network]Enable=1, Address=tgif.network
  Analog [USRP] txPort=51001 / rxPort=51000 / usrpAudio=AUDIO_USE_GAIN / tlvAudio=AUDIO_USE_GAIN

バックアップ先:
  /opt/bak/YYMMDDHHMMSS/ に 3つの ini をまとめて保存します。

編集／復元の最後に、サービス再起動を y/N で確認します。

既知の制約（注意）:
  - 値の置換は「既存のキー行」が対象です。コメントアウト行は対象外。
  - Enable / Address / USRP 系はセクションを限定して置換します。
  - 行末コメントは保持されません（キー=値 のみ書き換え）。
  - DVSwitch.ini はバックアップ対象ですが、本ツールでは値を変更しません。
EOF
}

do_backup() {
  local ts dir
  ts="$(date +%y%m%d%H%M%S)"
  dir="${BAK_ROOT}/${ts}"
  mkdir -p "$dir"
  echo "[INFO] バックアップ作成: $dir"
  local f
  for f in "${TARGET_FILES[@]}"; do
    if [ -f "$f" ]; then
      cp -p "$f" "$dir/"
      echo "       - $(basename "$f")"
    else
      echo "       ! 見つからないためスキップ: $f"
    fi
  done
  echo ""
}

set_ini() {
  local file="$1" key="$2" val="$3"
  if grep -Eq "^[[:space:]]*${key}[[:space:]]*=" "$file"; then
    sed -i -E "s|^([[:space:]]*${key}[[:space:]]*=).*|\1${val}|" "$file"
    echo "   [set] $(basename "$file"): ${key} = ${val}"
  else
    echo "   [WARN] $(basename "$file"): キー ${key} が見つからず変更できません"
  fi
}

set_section_key() {
  local file="$1" section="$2" key="$3" val="$4"
  awk -v sec="$section" -v key="$key" -v val="$val" '
    BEGIN { insec=0; done=0 }
    /^\[.*\]/ {
      if ($0 == sec) { insec=1 } else { insec=0 }
      print; next
    }
    {
      if (insec && !done && $0 ~ ("^[[:space:]]*" key "[[:space:]]*=")) {
        match($0, /^[[:space:]]*/)
        indent = substr($0, 1, RLENGTH)
        print indent key "=" val
        done=1
        next
      }
      print
    }
  ' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
  echo "   [set] $(basename "$file") ${section} ${key} = ${val}"
}

is_ndigits() { [[ "$1" =~ ^[0-9]+$ ]] && [ "${#1}" -eq "$2" ]; }

ask_plain() {
  local p="$1" cur="$2" a
  read -ep "${p} [現在: ${cur}]: " -i "$cur" a
  REPLY_VAL="$a"
}

ask_ndigits() {
  local p="$1" cur="$2" n="$3" a
  while true; do
    read -ep "${p}（${n}桁数字）[現在: ${cur}]: " -i "$cur" a
    if is_ndigits "$a" "$n"; then REPLY_VAL="$a"; return 0; fi
    echo "   → ${n}桁の数字で入力してください。"
  done
}

get_ini() {
  local file="$1" key="$2" line val
  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$file" | head -n1)"
  val="${line#*=}"
  val="$(echo "$val" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+;.*$//; s/[[:space:]]+$//')"
  echo "$val"
}

guess_dmrid() { local v="$1"; [[ "$v" =~ ^[0-9]{9}$ ]] && echo "${v:0:7}" || echo ""; }
guess_essid() { local v="$1"; [[ "$v" =~ ^[0-9]{9}$ ]] && echo "${v:7:2}" || echo ""; }

do_edit() {
  local f missing=0
  for f in "$MMDVM_INI" "$ANALOG_INI"; do
    [ -f "$f" ] || { echo "[ERROR] 見つかりません: $f"; missing=1; }
  done
  [ "$missing" -eq 1 ] && { echo "対象ファイルが不足しています。中止します。"; exit 1; }

  echo "=========================================================="
  echo " DVSwitch 設定 対話編集（TGIF 接続前提）"
  echo " Enter で現状維持、値を打ち替えると変更されます"
  echo "=========================================================="
  echo ""

  local cur_call cur_id cur_pass cur_txtg cur_dmrid cur_essid
  cur_call="$(get_ini "$MMDVM_INI" Callsign)"
  cur_id="$(get_ini "$MMDVM_INI" Id)"
  cur_pass="$(get_ini "$MMDVM_INI" Password)"
  cur_txtg="$(get_ini "$ANALOG_INI" txTg)"
  cur_dmrid="$(guess_dmrid "$cur_id")"
  cur_essid="$(guess_essid "$cur_id")"
  [ -z "$cur_dmrid" ] && cur_dmrid="$(get_ini "$ANALOG_INI" gatewayDmrId)"

  ask_plain   "1. Callsign（自局コールサイン）" "$cur_call";  V_CALL="$REPLY_VAL"
  ask_ndigits "2. DMR ID"                        "$cur_dmrid" 7; V_DMRID="$REPLY_VAL"
  ask_ndigits "3. ESSID"                         "${cur_essid:-00}" 2; V_ESSID="$REPLY_VAL"
  ask_plain   "4. TGIF Password"                 "$cur_pass";  V_PASS="$REPLY_VAL"
  ask_plain   "5. 送信 TG（txTg）"               "$cur_txtg";  V_TXTG="$REPLY_VAL"

  local V_ID_COMBINED="${V_DMRID}${V_ESSID}"
  local V_REPEATER="${V_DMRID}${V_ESSID}"

  echo ""
  echo "=========================================================="
  echo " 以下の内容で更新します"
  echo "----------------------------------------------------------"
  echo " [MMDVM_Bridge.ini]"
  echo "   Callsign              = $V_CALL"
  echo "   Id                    = $V_ID_COMBINED   (dmrid ${V_DMRID} + essid ${V_ESSID})"
  echo "   [DMR] Enable          = 1            (固定)"
  echo "   [DMR Network] Enable  = 1            (固定)"
  echo "   [DMR Network] Address = ${FIX_ADDRESS}  (固定)"
  echo "   [DMR Network] Password= $V_PASS"
  echo " [Analog_Bridge.ini]"
  echo "   gatewayDmrId          = $V_DMRID"
  echo "   repeaterID            = $V_REPEATER   (dmrid + essid)"
  echo "   txTg                  = $V_TXTG"
  echo "   [USRP] txPort         = ${FIX_USRP_TXPORT}   (固定)"
  echo "   [USRP] rxPort         = ${FIX_USRP_RXPORT}   (固定)"
  echo "   [USRP] usrpAudio      = ${FIX_USRP_AUDIO}  (固定)"
  echo "   [USRP] tlvAudio       = ${FIX_TLV_AUDIO}  (固定)"
  echo " [DVSwitch.ini] 変更なし（バックアップのみ）"
  echo "----------------------------------------------------------"
  read -ep "この内容で保存しますか？ (y/N): " CONFIRM
  if [[ "${CONFIRM,,}" != "y" ]]; then
    echo "中止しました。ファイルは変更していません。"
    exit 0
  fi

  echo ""
  do_backup

  echo "[INFO] 書き込み中..."
  set_ini "$MMDVM_INI" Callsign "$V_CALL"
  set_ini "$MMDVM_INI" Id       "$V_ID_COMBINED"
  set_ini "$MMDVM_INI" Password "$V_PASS"
  set_section_key "$MMDVM_INI" "[DMR]"          "Enable"  "1"
  set_section_key "$MMDVM_INI" "[DMR Network]"  "Enable"  "1"
  set_section_key "$MMDVM_INI" "[DMR Network]"  "Address" "$FIX_ADDRESS"

  set_ini "$ANALOG_INI" gatewayDmrId "$V_DMRID"
  set_ini "$ANALOG_INI" repeaterID   "$V_REPEATER"
  set_ini "$ANALOG_INI" txTg         "$V_TXTG"
  set_section_key "$ANALOG_INI" "[USRP]" "txPort"    "$FIX_USRP_TXPORT"
  set_section_key "$ANALOG_INI" "[USRP]" "rxPort"    "$FIX_USRP_RXPORT"
  set_section_key "$ANALOG_INI" "[USRP]" "usrpAudio" "$FIX_USRP_AUDIO"
  set_section_key "$ANALOG_INI" "[USRP]" "tlvAudio"  "$FIX_TLV_AUDIO"

  echo ""
  echo "[完了] 反映しました。"
  restart_services
}

do_restore() {
  if [ ! -d "$BAK_ROOT" ]; then
    echo "[ERROR] バックアップディレクトリがありません: $BAK_ROOT"
    exit 1
  fi
  mapfile -t DIRS < <(find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r)
  if [ "${#DIRS[@]}" -eq 0 ]; then
    echo "[INFO] 復元できるバックアップがありません。"
    exit 0
  fi

  echo "=========================================================="
  echo " 復元するバックアップ（日付フォルダ）を選択してください"
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

  local pick="${DIRS[$((SEL-1))]}" src
  src="${BAK_ROOT}/${pick}"
  echo ""
  echo "[INFO] 選択: $src"

  echo "[INFO] 復元前の現状を保険バックアップします。"
  do_backup

  local b dst
  for b in "$(basename "$MMDVM_INI")" "$(basename "$DVSWITCH_INI")" "$(basename "$ANALOG_INI")"; do
    if [ -f "${src}/${b}" ]; then
      case "$b" in
        MMDVM_Bridge.ini)  dst="$MMDVM_INI" ;;
        DVSwitch.ini)      dst="$DVSWITCH_INI" ;;
        Analog_Bridge.ini) dst="$ANALOG_INI" ;;
        *) continue ;;
      esac
      cp -p "${src}/${b}" "$dst"
      echo "       - ${b} -> ${dst}"
    else
      echo "       ! ${b} が選択フォルダに無いためスキップ"
    fi
  done

  echo ""
  echo "[完了] 復元しました。"
  restart_services
}

do_delete() {
  if [ ! -d "$BAK_ROOT" ]; then
    echo "[INFO] $BAK_ROOT は存在しません。削除対象なし。"
    exit 0
  fi
  echo "[WARN] $BAK_ROOT 配下のバックアップをすべて削除します。"
  read -ep "本当に削除しますか？ (y/N): " CONFIRM
  if [[ "${CONFIRM,,}" == "y" ]]; then
    rm -rf "${BAK_ROOT:?}/"*
    echo "[完了] 削除しました。"
  else
    echo "キャンセルしました。"
  fi
}

case "${1:-}" in
  -h|--help) show_help ;;
  -r)        do_restore ;;
  -d)        do_delete ;;
  "")        do_edit ;;
  *)         echo "不明なオプション: $1"; echo ""; show_help; exit 1 ;;
esac
