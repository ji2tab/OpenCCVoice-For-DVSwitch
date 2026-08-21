#!/bin/bash

# ==============================================================================
# DVSwitch bot 固定WAVファイル 対話式作成スクリプト
#   Version: V1.4vv （🔴 VVW V2.08vvw 対応。素材WAVに「語頭前の助走」を焼き込む
#            apply_leads を新設。V1.32vv の chown 引数順修正等を含む。詳細は変更履歴参照）
#   V1.31vv の要点 （🔴 対話モードの話者反映バグ修正 + 再起動の対話確認を追加。
#            (1) 合成時に選択話者を vv_say.py へ明示引数で渡す。V1.3avv までは
#            vv_say.py が保存前の古い wav_source.json から voice を読むため、話者を
#            変更しても固定WAVが旧話者のまま生成された—「テキストは新しいのに声だけ
#            古い」実機症状 2026-07-14。
#            (2) 対話モード末尾で、話者が変わった場合のみ dvswitch-bot の再起動を
#            y/N で確認して実行（dvs_config.sh の restart_services と同方式）。bot は
#            voice を起動時にのみ読むため、再起動忘れ＝固定/動的の話者混在を防ぐ。
#            --regen は app.py が JSON 更新→regen→voice_changed 判定で自動再起動する
#            経路のため影響なし・無変更）
#   ※ 版番号の "vv" は VOICEVOX 系ノード用ファイルであることを示す命名規約
#     （Open JTalk 系 Pi ノード用の同名ファイルと区別する。2026-07-14 導入）。
#   配置: /opt/dvswitch_bot/bin/create_wav.sh
#   出力: /opt/dvswitch_bot/ 直下（fixed_intro/outro, time_intro, 001, 002 ほか）
#
#   変更履歴:
#     V1.0  初版。入力内容の wav_source.json 記録＋次回起動時プリフィル。
#     V1.1  生成物の chown を ocv:ocv 決め打ちから汎用化。$SUDO_USER →
#           UID 1000 の順で実ユーザーを特定し、その既定グループへ揃える
#           （chown_owner ヘルパに集約）。複数ユーザー非想定・www-data 等の
#           システムユーザー（UID<1000）は対象外、という構成前提に基づく。
#     V1.2  🔵 音声キャラクター（話者）の対話式選択を追加。
#           入力セッションの最前段で、環境の VOICEVOX 全話者（models/vvms/*.vvm）
#           をスキャンして一覧表示し、番号で選ばせる。選択結果（style_id / vvm /
#           label）を wav_source.json の "voice" オブジェクトへ保存する。次回起動時
#           は前回の話者を既定選択としてプリフィルする。VOICEVOX の読み込み・スキャン
#           に失敗した場合は選択をスキップし、既定話者（No.7 アナウンス / style_id 30
#           / 6.vvm）で続行する（WAV 生成自体は止めない）。
#     V1.3  🔵 --regen（非対話再生成）モードを追加。
#           wav_source.json に記録済みの texts（最終合成テキスト）と voice（話者）を
#           そのまま使い、プロンプト一切なしで全WAVを再生成する。Web ダッシュボード
#           （app.py）から「話者だけ変えて作り直す」ために叩く入口。
#           手順: app.py が wav_source.json の voice を書き換え → 本モードを実行。
#           vv_say.py は wav_source.json の voice を自分で読むため、本モードは
#           テキストを渡すだけで新話者の音声になる。生成成功後に generated_at のみ
#           更新する（texts / voice には触れない）。既存WAVのバックアップは対話時と
#           同様に自動実行。texts が無い（旧形式・未生成）場合はエラー終了(exit 1)。
#     V1.3a 🔵 文言修正のみ（機能変更なし）。V1.2 時代の「合成は No.7 のまま（次回
#           改修）」という注意書きが、vv_say.py 改修版・bot V1.96 配置後は事実と
#           異なるため、確認画面・ヘルプ・完了メッセージから撤去。代わりに
#           「固定WAVは選択話者で生成される／bot 動的合成への反映は bot 再起動が
#           必要」という正確な案内に差し替えた。
#           ※ V1.2 の「選択と保存まで（合成は No.7 のまま）」という制限は、
#             vv_say.py（wav_source.json の voice 参照版）と dvswitch_bot.py V1.96
#             の配置により解消済み。V1.3 以降、選択した話者で実際に合成される。
#     V1.31vv 🔴 対話モードの話者反映バグ修正 + 話者変更時の bot 再起動確認を追加。
#           合成時に選択話者を vv_say.py へ明示引数で渡す（従来は保存前の古い
#           wav_source.json を読むため旧話者のまま生成された）。詳細は冒頭参照。
#     V1.32vv 🔴 chown_owner の引数順バグ修正（機能追加なし）。
#           V1.1 で導入した chown_owner は `chown "$@" "${OWNER_USER}:"` と
#           対象パスを先に渡していたため、chown がそれをユーザー名と解釈して
#           常に `invalid user` で失敗していた。`2>/dev/null || true` が
#           エラーを完全に握りつぶすため、V1.1 以降ずっと「汎用化したつもりで
#           実際には一度も所有者が変わっていない」状態だった（生成した WAV と
#           wav_source.json は root 所有のまま）。引数順を正し、失敗時は
#           WARN を出すようにした。dvs_config.sh V1.1 と同一方式。
#     V1.4vv  🔴 VVW V2.08vvw 対応。生成した素材WAVの「語頭の前」に無音の助走を焼き込む
#           （apply_leads）。V2.08vvw で bot 側の前パディングを 1.7s→0.5s に縮めたため、
#           頭欠け防止の無音は素材WAV側が持つ設計に変わった。これが無いと時報・定時・
#           カーチャンク応答の語頭が欠ける（JTW ocv-uhf で確定・VVW は要 RF 確認）。
#             fixed_intro : pad 1.78（自然な頭と合わせ語頭まで ≈2.0s）
#             time_intro/001/002 : fade 20ms ＋ pad 0.5（語頭まで ≈0.52s。フェードインは
#               録音WAVのノイズフロア段差による境目音を消す）
#           JTW版 create_wav.sh V1.3 の apply_leads と同一処理。
#
#   使い方:
#     sudo ./create_wav.sh          対話で固定WAVを作成（上書き前に自動バックアップ）
#     sudo ./create_wav.sh --regen  記録済みの内容(texts)と話者(voice)で全WAVを非対話再生成
#     sudo ./create_wav.sh -r       バックアップから復元（日付フォルダを選択）
#     sudo ./create_wav.sh -d       /opt/dvswitch_bot/bak/wav/ 配下の WAV バックアップを全削除
#     sudo ./create_wav.sh -h       ヘルプ
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
#         🔵 V1.2: 話者選択(voice)も同じ理由で wav_source.json 側に持たせる
#         （bot_config.json には足さない）。ファイルを増やさず1ファイルで管理する。
#
#   (2) 次回起動時に前回値をプリフィル
#       wav_source.json があれば、各 read プロンプトの初期値(-i)に前回の入力を
#       流し込む。そのまま Enter で前回と同じ内容を再生成できる。コールサイン等を
#       変えなければ、手で直した読み仮名もそのまま再利用される。
#       🔵 V1.2: 話者選択も前回値を既定選択としてプリフィルする。
#
#   JSON の読み書きは、日本語・記号のエスケープを安全に扱うため python3 を用いる
#   （bot が python3 前提の環境なので追加依存はない）。
# ==============================================================================

# 🔵 機械可読バージョン（固定行）。版を上げるときはヘッダーの Version 表記と一致させる。
SCRIPT_VERSION="V1.4vv"

# 定数定義 (Open JTalkの設定)
DIC_DIR="/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_MODEL="/usr/share/hts-voice/mei/mei_normal.htsvoice"
OUT_DIR="/opt/dvswitch_bot"
TMP_DIR="/tmp"
BAK_ROOT="/opt/dvswitch_bot/bak/wav"

# 🔵 改修: 入力内容（読み上げソーステキスト）の保存先
SRC_JSON="/opt/dvswitch_bot/wav_source.json"

# ------------------------------------------------------------------------------
# 🔵 V1.2: 話者（VOICEVOX）選択まわりの定数
# ------------------------------------------------------------------------------
# VOICEVOX の配置と、話者スキャンに使う venv 側 python3（voicevox_core を持つ）。
# vv_say.py を叩くのと同じ python を使う。
VOICEVOX_DIST_DIR="/opt/voicevox/dist"
VENV_PY="/opt/dvswitch_bot/venv/bin/python3"

# 既定話者（スキャン失敗時・初回で前回値が無いときのフォールバック）。
# 現行 vv_say.py と揃えて No.7（アナウンス） / style_id 30 / 6.vvm とする。
DEFAULT_VOICE_STYLE_ID="30"
DEFAULT_VOICE_VVM="6.vvm"
DEFAULT_VOICE_LABEL="No.7（アナウンス）"

# 選択結果（select_voice で確定する）
VOICE_STYLE_ID=""
VOICE_VVM=""
VOICE_LABEL=""

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
# 🔴 引数順に注意: chown は「所有者 → 対象」の順で渡す。V1.1〜V1.31vv は
#    `chown "$@" "${OWNER_USER}:"` と対象を先に書いていたため、chown が対象パスを
#    ユーザー名と解釈して常に `invalid user` で失敗していた（2>/dev/null || true が
#    エラーを握りつぶすため気づけなかった）。結果、生成物は root 所有のままだった。
#    失敗を黙らせず WARN として出す（スクリプト自体は止めない）。
chown_owner() {
  [ -n "$OWNER_USER" ] || return 0
  chown "${OWNER_USER}:" "$@" || echo "   [WARN] 所有者を ${OWNER_USER} に変更できませんでした: $*" >&2
}

# ------------------------------------------------------------------------------
# 🔴 V1.4vv: 生成済み素材WAVに「語頭前の助走」を焼き込む（VVW V2.08vvw 頭欠け対策）
# ------------------------------------------------------------------------------
# 対話生成・--regen の両方で、全WAV生成の最後に呼ぶ。合成エンジン（VOICEVOX）に依存
# しない sox 後処理のため、JTW版 create_wav.sh V1.3 と同一。pad は加算されるため
# WAV生成の直後に1回だけ呼ぶこと（冪等ではない）。
apply_leads() {
  local t="${TMP_DIR}/_lead_tmp.wav" f
  if [ -f "${OUT_DIR}/fixed_intro.wav" ]; then
    if sox "${OUT_DIR}/fixed_intro.wav" "$t" pad "${LEAD_FIXED_INTRO_PAD_SEC}" 0; then
      mv "$t" "${OUT_DIR}/fixed_intro.wav"; chown_owner "${OUT_DIR}/fixed_intro.wav"
      echo " [OK] fixed_intro.wav ← 助走 pad ${LEAD_FIXED_INTRO_PAD_SEC}s"
    else
      echo " [WARN] fixed_intro.wav の助走付与に失敗（元のまま）" >&2
    fi
  fi
  for f in time_intro 001 002; do
    if [ -f "${OUT_DIR}/${f}.wav" ]; then
      if sox "${OUT_DIR}/${f}.wav" "$t" fade t "${LEAD_SLOT_FADE_SEC}" 0 pad "${LEAD_SLOT_PAD_SEC}" 0; then
        mv "$t" "${OUT_DIR}/${f}.wav"; chown_owner "${OUT_DIR}/${f}.wav"
        echo " [OK] ${f}.wav ← fade ${LEAD_SLOT_FADE_SEC}s ＋ 助走 pad ${LEAD_SLOT_PAD_SEC}s"
      else
        echo " [WARN] ${f}.wav の助走付与に失敗（元のまま）" >&2
      fi
    fi
  done
}

# 🔴 V1.4vv: 素材WAVに焼き込む「語頭前の助走」（秒）。VVW V2.08vvw の頭欠け対策。
# bot 側の前パディング縮小（1.7s→0.5s）に伴い、語頭を守る無音は素材WAVが持つ。JTW V1.3 と同値。
LEAD_FIXED_INTRO_PAD_SEC="1.78"   # fixed_intro に前置する無音（fadeなし）→ 語頭 ≈2.0s
LEAD_SLOT_PAD_SEC="0.5"           # time_intro/001/002 に前置する無音 → 語頭 ≈0.52s
LEAD_SLOT_FADE_SEC="0.02"         # 上記3つの先頭フェードイン（ノイズフロア段差対策）

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
  sudo ./create_wav.sh          対話で固定WAVを作成（上書き前に自動バックアップ）
  sudo ./create_wav.sh --regen  記録済み内容で全WAVを非対話再生成（下記参照）
  sudo ./create_wav.sh -r       バックアップから復元（日付フォルダを選択）
  sudo ./create_wav.sh -d       /opt/dvswitch_bot/bak/wav/ 配下の WAV バックアップを全削除
  sudo ./create_wav.sh -h       このヘルプを表示

非対話再生成（--regen）:
  wav_source.json に記録済みの texts（最終合成テキスト）と voice（話者）をそのまま
  使い、プロンプトなしで全WAVを作り直します。話者だけ変えて作り直す用途
  （Web ダッシュボードからの話者変更）の入口です。テキストを変えたい場合は
  通常の対話モードを使ってください。texts の記録が無い場合はエラー終了します。

音声キャラクター（話者）の選択:
  作成の最初に、VOICEVOX の全話者（models/vvms/*.vvm）を一覧表示し、番号で選べます。
  選んだ話者（style_id / vvm / 表示名）は wav_source.json の "voice" に保存され、
  次回起動時は前回の話者が既定選択になります。
  固定WAVは選択した話者で生成されます（🔴 V1.31vv: 合成時に vv_say.py へ明示引数で渡す）。
  bot の動的合成（時報の時刻部分等）へ反映するには bot の再起動が必要です。

生成されるWAV（/opt/dvswitch_bot/ 直下に上書き）:
  fixed_intro.wav  … カーチャンク応答イントロ
  fixed_outro.wav  … カーチャンク応答アウトロ
  time_intro.wav   … 時報イントロ
  001.wav / 002.wav … 定時メッセージ
  ※ time_outro.wav は現行 bot では未使用（生成はするが無害）

入力内容の記録（wav_source.json）:
  生成時に、入力原文・読み仮名・合成テキスト・選択した話者を
  /opt/dvswitch_bot/wav_source.json へ保存します。次回起動時はこの内容を各入力欄・
  話者選択の既定値として読み込むため、そのまま Enter で前回と同じWAVを再生成できます。
  （bot_config.json には一切追記しません。WAV のソースと話者は別ファイルで管理します。）

バックアップ:
  作成（上書き）の直前に、既存の *.wav と wav_source.json を
  /opt/dvswitch_bot/bak/wav/YYMMDDHHMMSS/ へ自動退避します。
  運用中に作り直して失敗しても、 -r で元のWAVセット（と入力記録・話者）に戻せます。

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
# 🔵 V1.2: wav_source.json から前回の話者選択を読み込む
#   出力: PRIOR_VOICE_STYLE_ID / PRIOR_VOICE_VVM / PRIOR_VOICE_LABEL
#   "voice" が無い／壊れている場合は全て空（＝既定話者にフォールバック）。
# ------------------------------------------------------------------------------
PRIOR_VOICE_STYLE_ID=""
PRIOR_VOICE_VVM=""
PRIOR_VOICE_LABEL=""
load_prior_voice() {
  PRIOR_VOICE_STYLE_ID=""
  PRIOR_VOICE_VVM=""
  PRIOR_VOICE_LABEL=""
  [ -f "$SRC_JSON" ] || return 0
  local _v
  mapfile -t -d $'\x1f' _v < <(python3 - "$SRC_JSON" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
    v = d.get("voice", {}) if isinstance(d, dict) else {}
    if not isinstance(v, dict):
        v = {}
except Exception:
    v = {}
sys.stdout.write("\x1f".join([
    str(v.get("style_id", "")),
    str(v.get("vvm", "")),
    str(v.get("label", "")),
]))
PYEOF
)
  PRIOR_VOICE_STYLE_ID="${_v[0]:-}"
  PRIOR_VOICE_VVM="${_v[1]:-}"
  PRIOR_VOICE_LABEL="${_v[2]:-}"
}

# ------------------------------------------------------------------------------
# 🔵 V1.2: 話者（VOICEVOX）を対話式で選択する
#   - venv python3 で models/vvms/*.vvm をスキャンし、style_id 昇順で一覧表示
#   - 前回選択（無ければ既定 No.7）を初期選択としてプリフィル
#   - 選択結果を VOICE_STYLE_ID / VOICE_VVM / VOICE_LABEL に確定
#   - スキャン失敗・無効入力時は既定（前回 or No.7）で続行（生成は止めない）
#   レコード形式: "style_id\x1fvvm\x1fキャラ名\x1fスタイル名"（1行1レコード）
# ------------------------------------------------------------------------------
select_voice() {
  echo "=========================================================="
  echo " 音声キャラクター（話者）の選択"
  echo "----------------------------------------------------------"

  # 既定（前回値 → 無ければ No.7）
  local def_sid def_vvm def_label
  if [ -n "$PRIOR_VOICE_STYLE_ID" ] && [ -n "$PRIOR_VOICE_VVM" ]; then
    def_sid="$PRIOR_VOICE_STYLE_ID"
    def_vvm="$PRIOR_VOICE_VVM"
    def_label="${PRIOR_VOICE_LABEL:-style_id ${PRIOR_VOICE_STYLE_ID} / ${PRIOR_VOICE_VVM}}"
  else
    def_sid="$DEFAULT_VOICE_STYLE_ID"
    def_vvm="$DEFAULT_VOICE_VVM"
    def_label="$DEFAULT_VOICE_LABEL"
  fi

  # 全話者スキャン（venv python3 / voicevox_core）
  local scan=""
  if [ -x "$VENV_PY" ]; then
    scan="$("$VENV_PY" - <<'PYEOF' 2>/dev/null
import glob, sys
try:
    from voicevox_core.blocking import VoiceModelFile
except Exception:
    sys.exit(0)  # 出力なし → bash 側で既定にフォールバック

DIST_DIR = "/opt/voicevox/dist"
recs = []
for vvm_path in sorted(glob.glob(DIST_DIR + "/models/vvms/*.vvm")):
    vvm = vvm_path.rsplit("/", 1)[-1]
    try:
        with VoiceModelFile.open(vvm_path) as model:
            metas = model.metas
    except Exception:
        continue
    for ch in metas:
        for st in ch.styles:
            recs.append((st.id, vvm, ch.name, st.name))

recs.sort(key=lambda r: r[0])
for sid, vvm, cname, sname in recs:
    sys.stdout.write("%d\x1f%s\x1f%s\x1f%s\n" % (sid, vvm, cname, sname))
PYEOF
)"
  fi

  # スキャン不可 → 既定で続行
  if [ -z "$scan" ]; then
    echo "[WARN] 話者一覧を取得できませんでした（VOICEVOX 読み込み失敗、または venv 不在）。"
    echo "       既定の話者で続行します: ${def_label}  (style_id=${def_sid} / ${def_vvm})"
    VOICE_STYLE_ID="$def_sid"
    VOICE_VVM="$def_vvm"
    VOICE_LABEL="$def_label"
    echo ""
    return 0
  fi

  # レコードを配列へ
  local RECS=()
  mapfile -t RECS <<< "$scan"

  # 一覧表示（既定に一致する行へマーカー）
  local i sid vvm cname sname def_idx=""
  echo " 番号   style_id  vvm       キャラクター（スタイル）"
  echo "----------------------------------------------------------"
  for i in "${!RECS[@]}"; do
    IFS=$'\x1f' read -r sid vvm cname sname <<< "${RECS[$i]}"
    if [ "$sid" = "$def_sid" ] && [ "$vvm" = "$def_vvm" ]; then
      def_idx="$((i+1))"
      printf "  %3d)  %-8s  %-8s  %s（%s）  ← 前回/既定\n" "$((i+1))" "$sid" "$vvm" "$cname" "$sname"
    else
      printf "  %3d)  %-8s  %-8s  %s（%s）\n" "$((i+1))" "$sid" "$vvm" "$cname" "$sname"
    fi
  done
  echo "----------------------------------------------------------"

  # 既定に一致する行が無ければ 1 を初期値に
  local prompt_def="${def_idx:-1}"

  # 選択入力（Enter で既定）
  local SEL=""
  read -ep "話者番号を選択してください (Enter で既定): " -i "$prompt_def" SEL

  # 検証。無効なら既定で続行
  if ! [[ "$SEL" =~ ^[0-9]+$ ]] || [ "$SEL" -lt 1 ] || [ "$SEL" -gt "${#RECS[@]}" ]; then
    echo "[WARN] 無効な選択です。既定の話者で続行します: ${def_label}  (style_id=${def_sid} / ${def_vvm})"
    VOICE_STYLE_ID="$def_sid"
    VOICE_VVM="$def_vvm"
    VOICE_LABEL="$def_label"
    echo ""
    return 0
  fi

  IFS=$'\x1f' read -r sid vvm cname sname <<< "${RECS[$((SEL-1))]}"
  VOICE_STYLE_ID="$sid"
  VOICE_VVM="$vvm"
  VOICE_LABEL="${cname}（${sname}）"

  echo ""
  echo "[選択] ${VOICE_LABEL}  (style_id=${VOICE_STYLE_ID} / ${VOICE_VVM})"
  echo ""
}

# ------------------------------------------------------------------------------
# 🔵 改修: 入力内容を wav_source.json へ保存する
#   値は環境変数経由で python3 に渡す（クォート事故を避けるため）。
#   入力原文・読み仮名に加え、実際に合成した最終テキスト(texts)も残し、
#   後から「何を喋っているWAVなのか」を完全に復元できるようにする。
#   🔵 V1.2: 選択した話者(voice)も同じファイルへ保存する。
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
  J_VOICE_STYLE_ID="$VOICE_STYLE_ID" \
  J_VOICE_VVM="$VOICE_VVM" \
  J_VOICE_LABEL="$VOICE_LABEL" \
  python3 - "$SRC_JSON" <<'PYEOF'
import json, os, sys

def _style_id(raw):
    # 数値なら int で、そうでなければ文字列のまま保存する
    raw = (raw or "").strip()
    if raw.isdigit():
        return int(raw)
    return raw

d = {
    "generated_at":  os.environ.get("GEN_AT", ""),
    "callsign":      os.environ.get("J_CALLSIGN", ""),
    "callsign_kana": os.environ.get("J_CALLSIGN_KANA", ""),
    "location":      os.environ.get("J_LOCATION", ""),
    "msg1":          os.environ.get("J_MSG1", ""),
    "msg1_kana":     os.environ.get("J_MSG1_KANA", ""),
    "msg2":          os.environ.get("J_MSG2", ""),
    "msg2_kana":     os.environ.get("J_MSG2_KANA", ""),
    # 🔵 V1.2: 選択した話者（vv_say.py / dvswitch_bot.py V1.96 が参照する）
    "voice": {
        "style_id": _style_id(os.environ.get("J_VOICE_STYLE_ID", "")),
        "vvm":      os.environ.get("J_VOICE_VVM", ""),
        "label":    os.environ.get("J_VOICE_LABEL", ""),
    },
    # 実際に Open JTalk / VOICEVOX へ渡した最終テキスト（合成内容の記録）
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
# 🔵 V1.3: 非対話再生成（--regen）
#   wav_source.json の texts（最終合成テキスト）と voice（話者）をそのまま使い、
#   プロンプトなしで全WAVを再生成する。Web ダッシュボード（app.py）が話者変更後に
#   叩く入口。vv_say.py は wav_source.json の voice を自分で読むため、ここでは
#   テキストを渡すだけで選択中の話者の音声になる。
#   成功後に generated_at のみ更新する（texts / voice には触れない）。
# ------------------------------------------------------------------------------
do_regen() {
  echo "=========================================================="
  echo " 非対話再生成（--regen）  ${SCRIPT_VERSION}"
  echo "=========================================================="

  if [ ! -f "$SRC_JSON" ]; then
    echo "[ERROR] ${SRC_JSON} がありません。先に対話モードで一度WAVを作成してください。"
    exit 1
  fi

  # texts と voice を US(0x1f) 区切りで取り出す（順序固定）。
  # [0]fixed_intro [1]fixed_outro [2]time_intro [3]001 [4]002 [5]time_outro
  # [6]voice.label [7]voice.style_id [8]voice.vvm
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
v = d.get("voice", {}) if isinstance(d, dict) else {}
if not isinstance(v, dict):
    v = {}
keys = ["fixed_intro", "fixed_outro", "time_intro", "001", "002", "time_outro"]
out = [str(t.get(k, "")) for k in keys]
out += [str(v.get("label", "")), str(v.get("style_id", "")), str(v.get("vvm", ""))]
sys.stdout.write("\x1f".join(out))
PYEOF
)
  while [ "${#FIELDS[@]}" -lt 9 ]; do FIELDS+=(""); done

  local T_INTRO="${FIELDS[0]}" T_OUTRO="${FIELDS[1]}" T_TIME="${FIELDS[2]}"
  local T_001="${FIELDS[3]}"   T_002="${FIELDS[4]}"   T_TOUT="${FIELDS[5]}"
  local V_LABEL="${FIELDS[6]}" V_SID="${FIELDS[7]}"   V_VVM="${FIELDS[8]}"

  # texts が空（旧形式の wav_source.json など）は再生成不能
  if [ -z "$T_INTRO" ] || [ -z "$T_001" ] || [ -z "$T_002" ]; then
    echo "[ERROR] wav_source.json に texts の記録がありません（旧形式の可能性）。"
    echo "        対話モード（引数なし）で一度作成し直すと記録されます。"
    exit 1
  fi

  if [ -n "$V_LABEL" ]; then
    echo "[INFO] 話者: ${V_LABEL} (style_id=${V_SID} / ${V_VVM})"
  else
    echo "[INFO] 話者: 記録なし → vv_say.py の既定（No.7）で生成します。"
  fi
  echo "[INFO] 記録済みテキストで全WAVを再生成します。"
  echo ""

  # 上書き直前の自動バックアップ（対話時と同一）
  backup_wavs

  echo "WAVファイルを生成中..."

  /opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$T_INTRO" "${TMP_DIR}/temp_intro.wav" \
    && sox "${TMP_DIR}/temp_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_intro.wav" \
    && echo " [OK] fixed_intro.wav" || { echo " [NG] fixed_intro.wav"; exit 1; }

  /opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$T_OUTRO" "${TMP_DIR}/temp_outro.wav" \
    && sox "${TMP_DIR}/temp_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_outro.wav" \
    && echo " [OK] fixed_outro.wav" || { echo " [NG] fixed_outro.wav"; exit 1; }

  /opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$T_TIME" "${TMP_DIR}/time_intro.wav" \
    && sox "${TMP_DIR}/time_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_intro.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse \
    && echo " [OK] time_intro.wav" || { echo " [NG] time_intro.wav"; exit 1; }

  /opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$T_001" "${TMP_DIR}/001_raw.wav" \
    && sox "${TMP_DIR}/001_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/001.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse \
    && echo " [OK] 001.wav" || { echo " [NG] 001.wav"; exit 1; }

  /opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$T_002" "${TMP_DIR}/002_raw.wav" \
    && sox "${TMP_DIR}/002_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/002.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse \
    && echo " [OK] 002.wav" || { echo " [NG] 002.wav"; exit 1; }

  /opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$T_TOUT" "${TMP_DIR}/time_outro.wav" \
    && sox "${TMP_DIR}/time_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_outro.wav" \
    && echo " [OK] time_outro.wav" || { echo " [NG] time_outro.wav"; exit 1; }

  # 🔴 V1.4vv: 素材WAVに語頭前の助走を焼き込む（VVW V2.08vvw 頭欠け対策）
  apply_leads

  # generated_at のみ更新（texts / voice は不変）
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

  rm -f "${TMP_DIR}/temp_intro.wav" "${TMP_DIR}/temp_outro.wav" "${TMP_DIR}/time_intro.wav" \
        "${TMP_DIR}/001_raw.wav" "${TMP_DIR}/002_raw.wav" "${TMP_DIR}/time_outro.wav"

  echo ""
  echo "[完了] 再生成しました。bot の動的合成（時報等）へ話者を反映するには bot の再起動が必要です。"
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
# 🔵 V1.2: 前回の話者選択も読み込む（話者選択の既定に使う）
load_prior_voice
if [ -f "$SRC_JSON" ]; then
  echo "[INFO] 前回の入力内容を読み込みました（${SRC_JSON}）。"
  echo "       各項目は前回値を初期表示します。変更なければそのまま Enter。"
  echo ""
fi

# 🔵 V1.2: 最前段で音声キャラクター（話者）を選択する
select_voice

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
echo "以下の内容でWAVファイルを生成します:"
echo "----------------------------------------------------------"
echo " [話者]            : ${VOICE_LABEL}  (style_id=${VOICE_STYLE_ID} / ${VOICE_VVM})"
echo " [fixed_intro.wav] : $BASE_INTRO_TEXT"
echo " [fixed_outro.wav] : カーチャンクです。"
echo " [time_intro.wav]  : こちらは、${CALLSIGN_KANA}、"
echo " [001.wav]         : ${BASE_INTRO_TEXT}${MSG1_KANA}"
echo " [002.wav]         : ${BASE_INTRO_TEXT}${MSG2_KANA}"
echo " [time_outro.wav]  : です。"
echo "----------------------------------------------------------"
echo " ※ 固定WAVは選択した話者で生成されます（合成時に話者を明示指定）。"
echo "    bot の動的合成（時報の時刻部分・コールサイン読み等）へ"
echo "    話者を反映するには、生成後に bot の再起動が必要です。"
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
# 🔴 V1.31vv: 選択話者を明示引数で渡す（引数は vv_say.py の最優先。保存前の古い
# wav_source.json の voice を読んでしまう V1.3avv までのバグを根治）。以下6呼び出し全て同様。
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$BASE_INTRO_TEXT" "${TMP_DIR}/temp_intro.wav" "$VOICE_STYLE_ID" "$VOICE_VVM"
sox "${TMP_DIR}/temp_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_intro.wav"
echo " [OK] fixed_intro.wav"

# --- fixed_outro.wav ---
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "カーチャンクです。" "${TMP_DIR}/temp_outro.wav" "$VOICE_STYLE_ID" "$VOICE_VVM"
sox "${TMP_DIR}/temp_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/fixed_outro.wav"
echo " [OK] fixed_outro.wav"

# --- time_intro.wav ---
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "こちらは、${CALLSIGN_KANA}、" "${TMP_DIR}/time_intro.wav" "$VOICE_STYLE_ID" "$VOICE_VVM"
sox "${TMP_DIR}/time_intro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_intro.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse
echo " [OK] time_intro.wav"

# --- 001.wav ---
TEXT_001="${BASE_INTRO_TEXT}${MSG1_KANA}"
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$TEXT_001" "${TMP_DIR}/001_raw.wav" "$VOICE_STYLE_ID" "$VOICE_VVM"
sox "${TMP_DIR}/001_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/001.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse
echo " [OK] 001.wav"

# --- 002.wav ---
TEXT_002="${BASE_INTRO_TEXT}${MSG2_KANA}"
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "$TEXT_002" "${TMP_DIR}/002_raw.wav" "$VOICE_STYLE_ID" "$VOICE_VVM"
sox "${TMP_DIR}/002_raw.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/002.wav" silence 1 0.1 1% reverse silence 1 0.1 1% reverse
echo " [OK] 002.wav"

# --- time_outro.wav ---
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py "です。" "${TMP_DIR}/time_outro.wav" "$VOICE_STYLE_ID" "$VOICE_VVM"
sox "${TMP_DIR}/time_outro.wav" -r 8000 -c 1 -b 16 "${OUT_DIR}/time_outro.wav"
echo " [OK] time_outro.wav"

# 🔴 V1.4vv: 素材WAVに語頭前の助走を焼き込む（VVW V2.08vvw 頭欠け対策）
apply_leads

# ------------------------------------------------------------------------------
# 🔵 改修: 入力内容を wav_source.json へ保存（次回起動時のプリフィル元になる）
# ------------------------------------------------------------------------------
save_source_json
echo " [OK] wav_source.json （入力内容＋話者を記録）"

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
echo " 選択話者: ${VOICE_LABEL}  (style_id=${VOICE_STYLE_ID} / ${VOICE_VVM})"
echo "----------------------------------------------------------"
echo " bot は送出のたびにWAVを読み直すため、固定WAV（応答・定時メッセージ等）は"
echo " 再起動なしで次の送出から新しい音声になります。"
echo " 次回このスクリプトを起動すると、今回の入力・話者が初期値として表示されます。"
echo " 元に戻したいときは:  sudo ./create_wav.sh -r"
echo "=========================================================="

# ------------------------------------------------------------------------------
# 🔴 V1.31vv: 話者が変わった場合のみ、bot 再起動を対話で確認する。
#   bot（dvswitch_bot.py V1.96vv）は wav_source.json の voice を起動時に一度だけ
#   読むため、動的合成（時報の時刻・コールサイン読み「◯◯局の、」等）へ新話者を
#   反映するには再起動が必要（固定WAVは送出のたび読み直すため不要）。
#   従来は末尾の案内文で手動実行を促すだけで、忘れると固定＝新話者／動的＝旧話者の
#   混在になった（2026-07-14 実機で発生）。dvs_config.sh の restart_services と同じ
#   y/N 確認方式で、その場で再起動できるようにする。
#   比較元: 実行前の wav_source.json の voice（PRIOR_VOICE_*）。無ければ bot の
#   フォールバック既定（No.7 アナウンス）と比較する（bot の実効話者と揃える）。
_prev_sid="${PRIOR_VOICE_STYLE_ID:-$DEFAULT_VOICE_STYLE_ID}"
_prev_vvm="${PRIOR_VOICE_VVM:-$DEFAULT_VOICE_VVM}"
if [ "$VOICE_STYLE_ID" != "$_prev_sid" ] || [ "$VOICE_VVM" != "$_prev_vvm" ]; then
  echo ""
  echo "[INFO] 話者が変更されました（style_id=${_prev_sid}/${_prev_vvm} → ${VOICE_STYLE_ID}/${VOICE_VVM}）。"
  echo "       bot の動的合成（時報の時刻・コールサイン読み等）へ反映するには再起動が必要です。"
  read -ep "dvswitch-bot を今すぐ再起動しますか？ (y/N): " RST
  if [[ "${RST,,}" == "y" ]]; then
    echo "[INFO] dvswitch-bot を再起動します..."
    systemctl restart dvswitch-bot
    sleep 3
    echo "[INFO] 状態: $(systemctl is-active dvswitch-bot)"
    echo "[完了] 再起動しました。応答キャッシュもクリアされ、次の送出から全パートが新話者になります。"
  else
    echo "再起動はスキップしました。動的合成部分は旧話者のままです。手動で再起動してください:"
    echo "   sudo systemctl restart dvswitch-bot"
  fi
else
  echo ""
  echo "[INFO] 話者は前回と同じため、bot の再起動は不要です（固定WAVは次の送出から反映）。"
fi
