# OpenCCVoice for DVSwitch VV版（VOICEVOX）構築手順書

**Document Version: V1.0（2026-07-15）**

本書は、DMR デジピーター自動音声応答システム **OpenCCVoice for DVSwitch の VV版（VOICEVOX 音声合成版）** を、x86_64 Linux 上にゼロから構築する手順書です。実機（Incus コンテナ `ocv-voicevox`、Debian 12、コールサイン JJ2YYK、TGIF TG44833）で 2026年7月に検証済みの手順を再構成したものです。

> 凡例: ✅ 実機検証済み ／ ⚠️ 注意点 ／ 🔴 省略・誤りが致命傷になる箇所

---

## 0. 本書の位置づけとシステム構成

### 0.1 位置づけ

- VV版の動作要件は **x86_64 の Linux（Debian 12 / Ubuntu 24.04 系で検証）** です。ベアメタル・VM・コンテナのいずれでも構築できます。
- **Incus コンテナで環境を用意する場合**は、先に別冊『Incus コンテナ/incus構築マニュアル.md』を実施し、SSH でログインできる状態にしてから本書の第2章へ合流してください。
- JT版（Open JTalk / Raspberry Pi 用、リポジトリ直下）とはスクリプトが別系統です。VV版のファイルは `dvs_ocv_vv/` 配下、版番号は **`vv` サフィックス**（例: V1.96vv）で区別されます。
- Web ダッシュボードは JT版・VV版で**共用**です（`dashboard/app.py`、V3.11 以降）。

### 0.2 システム構成

```
[DMRハンディ機]
    │  RF (430MHz等)
    ▼
[ホットスポット / Pi-Star]
    │  TGIFネットワーク (TG44833) / Homebrew (62031)
    ▼
━━━ x86_64 Linux（本書の構築対象）━━━━━━━━━━━━━━━━━━━

  MMDVM_Bridge（amd64ネイティブ）
    │  TLV
    ▼
  Analog_Bridge（amd64ネイティブ）
    │
    ├─ AMBE ─▶ md380-emu（ARMバイナリ + qemu-arm-static）
    │
    │  USRP/UDP (rx:51000 / tx:51001)
    ▼
  dvswitch_bot.py V1.96vv（venv内Python・常駐デーモン）
    │      カーチャンク検出 → 応答合成 → USRP送出
    └─ 起動時に1回ロード ─▶ VOICEVOX CORE 0.16.x（同一プロセス内ライブラリ）

  create_wav.sh + vv_say.py（固定WAV生成）
      └───（合成に VOICEVOX CORE を利用）

  dashboard/app.py（Flask, :8081, dvswitch-web）※JT版・VV版で共用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

音声合成は2系統あります。**①固定WAV**（イントロ等。`create_wav.sh`→`vv_say.py` が生成、送出のたびに読み直し）と **②動的合成**（時報の時刻・コールサイン読み等。bot が起動時にロードした VOICEVOX で合成）。話者は両系統とも `wav_source.json` の `voice` を参照して揃います。

### 0.3 検証済み環境

| 項目 | 値 |
|---|---|
| ホスト | ocv-pc（Intel Core i5-7200U, Ubuntu 24.04, 192.168.1.67） |
| コンテナ | ocv-voicevox（Incus, Debian 12 amd64, macvlan, 192.168.1.170） |
| ユーザー | ocv（sudo 権限） |
| Python | 3.11.2（要件: 3.10 以上） |
| VOICEVOX CORE | 0.16.4（構築時点。最新版で読み替え可） |
| DMR | JJ2YYK / DMR ID 4402396 / ESSID 88 / TGIF TG44833 |

---

## 1. 前提条件

- x86_64 の Debian 12 または Ubuntu 24.04 系に SSH ログインでき、sudo が使えること
- インターネット接続（dvswitch.org / GitHub / VOICEVOX リリースへ到達できること）
- 自局の DMR ID（RadioID 登録済み）と TGIF のアカウント（Hotspot Security パスワード）
- ディスク空き 3GB 以上（VOICEVOX のモデル・ONNX Runtime が約 1.5GB）

---

## 2. OS 基本設定

**【対象マシンで実行】**

```bash
sudo apt update && sudo apt -y upgrade

# タイムゾーン（時報・ログの基準）
sudo timedatectl set-timezone Asia/Tokyo

# 日本語ロケール（create_wav.sh の対話表示・WAV内テキストで使用）
sudo apt install -y locales
sudo sed -i 's/^# *ja_JP.UTF-8/ja_JP.UTF-8/' /etc/locale.gen
sudo locale-gen
sudo update-locale LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8 LANGUAGE=ja_JP:ja

# 必須パッケージ
sudo apt install -y wget curl sox python3-venv python3-pip nano
```

> ⚠️ `update-locale` は設定ファイルを書き換えるだけで**現在の SSH セッションには反映されません**。一度ログアウト→再ログインし、`locale` で `ja_JP.UTF-8` を確認してください。✅（実機で確認済みの挙動）

---

## 3. DVSwitch のインストール

### 3.1 リポジトリ登録

```bash
cd /tmp
wget http://dvswitch.org/bookworm
chmod +x bookworm
sudo ./bookworm
```

`Verified: Valid DVSwitch Keyring (72147EC1E788D4C3)` と `Finished DVSwitch repository install` が出れば成功です。✅ Ubuntu 24.04（noble）でも bookworm スクリプトで問題ありません。

### 3.2 本体インストール

```bash
sudo apt install -y dvswitch-server
```

`analog-bridge`（amd64 ネイティブ）・`mmdvm-bridge`（amd64 ネイティブ）・`md380-emu`（armhf）がまとめて入ります。

> ⚠️ インストール中に `YSFHosts.txt` / `TGList_TGIF.txt` のダウンロード失敗や Apache の `Could not execute systemctl` 警告が出ることがありますが、bot の動作には影響しません（実機で確認済み）。

### 3.3 md380-emu の実行権限付与

🔴 パッケージの既知の問題で実行権限が付かないことがあります。必ず確認・付与してください。

```bash
sudo chmod +x /opt/md380-emu/md380-emu
ls -la /opt/md380-emu/md380-emu   # -rwxr-xr-x であること
```

### 3.4 qemu の確認（x86_64 ではダウングレード不要）

md380-emu は 32bit ARM バイナリのため `qemu-arm-static` 経由で動きます。

```bash
dpkg -l | grep qemu-user-static
/usr/bin/qemu-arm-static /opt/md380-emu/md380-emu
# → Usage メッセージが出て SEGV しなければ OK
```

> ✅ **x86_64 環境では Debian 12 / Ubuntu 24.04 標準の qemu（7.2〜8.2系）で SEGV は発生しません**（ocv-pc・ocv-voicevox の両方で実証）。Raspberry Pi（ARM ホスト）の Bookworm で必須だった「qemu 5.2 へのダウングレード＋apt-mark hold」は、**x86_64 では不要**です。SEGV が出た場合のみ JT版手順書の該当章を参照してください。

### 3.5 サービス有効化

```bash
sudo systemctl enable --now md380-emu analog_bridge mmdvm_bridge
systemctl is-active md380-emu analog_bridge mmdvm_bridge
```

---

## 4. DVSwitch の設定（TGIF 接続）

### 4.0 dvs 初期設定（ini 生成）と TGIF 切替

DVSwitch-Server の各 ini（DVSwitch.ini / Analog_Bridge.ini / MMDVM_Bridge.ini）は、初回の `dvs` 対話設定で生成されます。次章以降で使う `dvs_config.sh` は既存のキー行を置換する方式のため、この初期化で ini が生成されていることが前提です（未生成のまま `dvs_config.sh` を実行しても置換対象が無く TGIF 設定が入りません）。まずここで ini を作ってから 4.1 へ進んでください。

```bash
sudo /usr/local/dvs/dvs
```

⚠️ `dvs` コマンドは PATH に登録されていないため、上記のようにフルパス（`/usr/local/dvs/dvs`）で実行します。

1. **「01 初期設定」を完走** します。
2. 案内に従って **再起動** します。
3. 再起動後、再び `sudo /usr/local/dvs/dvs` を起動し、`02 詳細設定` → `24 その他のDMRネットワーク` → `1 デフォルトのDMRサーバー変更` → `2 TGIF` を選び、**接続先を TGIF に切り替え** ます。

ここまでで ini 一式が生成され、デフォルト DMR サーバーが TGIF になります。細かな値（Callsign / DMR ID / ESSID / TGIF Password / 送信TG 等）は次の 4.1 の `dvs_config.sh` で確定します。

### 4.1 dvs_config.sh で TGIF 用の値を確定

対話式設定ツール `dvs_config.sh` を使います（3つの ini を自動バックアップ付きで更新）。

```bash
sudo mkdir -p /opt/dvswitch_bot/bin
sudo chown -R "$USER": /opt/dvswitch_bot
curl -fsSL "https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_ocv_vv/dvs_config.sh" \
  | sudo tee /opt/dvswitch_bot/bin/dvs_config.sh >/dev/null
sudo chmod +x /opt/dvswitch_bot/bin/dvs_config.sh
sudo /opt/dvswitch_bot/bin/dvs_config.sh
```

対話で入力する項目: **Callsign / DMR ID（7桁） / ESSID（2桁） / TGIF Password / 送信TG（txTg）**。
固定値（Address=tgif.network、USRP tx:51001 / rx:51000、AUDIO_USE_GAIN 等）はスクリプトが自動設定します。

設定後の TGIF ログイン確認:

```bash
sudo journalctl -u mmdvm_bridge -n 30 --no-pager | grep -iE "login|master"
```

> 🔴 **サービスを複数同時に restart しない**でください。順序なしの同時再起動は Analog_Bridge が無音の半死状態になる既知事象があります。再起動は必ずこの順で3秒ずつ空けます:
> ```bash
> sudo systemctl restart md380-emu && sleep 3 && \
> sudo systemctl restart analog_bridge && sleep 3 && \
> sudo systemctl restart mmdvm_bridge
> ```

---

## 5. VOICEVOX CORE 環境構築

JT版の Open JTalk 章に相当する部分を、丸ごと VOICEVOX CORE（Python バインディング / 同一プロセス内ライブラリ）に置き換えます。Docker は使いません（入れ子コンテナ問題を回避し、amd64 ネイティブで完結）。✅

### 5.1 ダウンローダーで一括取得

```bash
sudo mkdir -p /opt/voicevox
sudo chown -R "$USER": /opt/voicevox
cd /opt/voicevox

binary=download-linux-x64
curl -sSfL "https://github.com/VOICEVOX/voicevox_core/releases/latest/download/${binary}" -o download
chmod +x download

# core / ONNX Runtime / Open JTalk 辞書 / 音声モデル(.vvm) を一括取得（約1.5GB）
./download -o /opt/voicevox/dist
```

取得後の主なパス（以降のスクリプトが前提とする配置）:

| 内容 | パス |
|---|---|
| ONNX Runtime | `/opt/voicevox/dist/onnxruntime/lib/libvoicevox_onnxruntime.so.*` |
| 辞書 | `/opt/voicevox/dist/dict/open_jtalk_dic_utf_8-1.11` |
| 音声モデル | `/opt/voicevox/dist/models/vvms/*.vvm` |

> ⚠️ GPU は不要です（CPU 版で動作）。GitHub のレート制限（HTTP 429/403）でダウンロードが弾かれた場合は、時間をおいて再試行してください。

### 5.2 venv 作成と Python バインディング導入

```bash
cd /opt/dvswitch_bot
python3 -m venv venv --system-site-packages
source venv/bin/activate

# 最新版は https://github.com/VOICEVOX/voicevox_core/releases で whl 名を確認
pip install "https://github.com/VOICEVOX/voicevox_core/releases/download/0.16.4/voicevox_core-0.16.4-cp310-abi3-manylinux_2_34_x86_64.whl"
```

✅ 構築時実績: `voicevox-core 0.16.4`（`cp310-abi3-manylinux_2_34_x86_64`）。Python 3.10 以上なら abi3 whl がそのまま入ります。

> 🔴 **bot は必ずこの venv の Python で動かします**。第8章の systemd ユニットの `ExecStart` は `/usr/bin/python3` ではなく `/opt/dvswitch_bot/venv/bin/python3` です。ここを間違えると `ModuleNotFoundError: voicevox_core` で即死します。

### 5.3 単体合成テスト

```bash
cd /opt/voicevox/dist
python3 - << 'EOF'
import glob
from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

so = sorted(glob.glob("onnxruntime/lib/libvoicevox_onnxruntime.so*"))[0]
onnx = Onnxruntime.load_once(filename=so)
openjtalk = OpenJtalk("dict/open_jtalk_dic_utf_8-1.11")
synth = Synthesizer(onnx, openjtalk)

with VoiceModelFile.open("models/vvms/0.vvm") as model:
    synth.load_voice_model(model)

query = synth.create_audio_query("じぇいじぇいつーわいわいけー", style_id=3)  # ずんだもん(ノーマル)
wav = synth.synthesis(query, style_id=3)
open("/tmp/vv_test.wav", "wb").write(wav)
print("OK:", len(wav), "bytes")
EOF
aplay /tmp/vv_test.wav   # スピーカーがあれば再生確認（無ければファイル生成だけでOK）
```

> ⚠️ `.so` のバージョン番号（`.so.1.17.3` 等）はリリースにより変わるため、上記のように **glob で解決**します（固定パスは将来壊れます）。また `query.output_sampling_rate = 48000` の指定は**不要**です（deprecation 対象。ネイティブ 24kHz 出力に任せ、8kHz 変換は sox が行う設計）。

---

## 6. OpenCCVoice VV版ファイルの配置

`dvs_ocv_vv/` 配下から取得します。デプロイは `curl -fsSL … | sudo tee` パターン（`-f` により 404 なら書き込み前に停止）。

```bash
RAW="https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_ocv_vv"

# bot 本体（VV版 V1.96vv 以降）
curl -fsSL "$RAW/dvswitch_bot.py" | sudo tee /opt/dvswitch_bot/bin/dvswitch_bot.py >/dev/null

# 設定ツール
curl -fsSL "$RAW/bot_setup.py" | sudo tee /opt/dvswitch_bot/bin/bot_setup.py >/dev/null

# 固定WAV生成（VV版 V1.31vv 以降。話者選択・--regen 対応）
curl -fsSL "$RAW/create_wav.sh" | sudo tee /opt/dvswitch_bot/bin/create_wav.sh >/dev/null
sudo chmod +x /opt/dvswitch_bot/bin/create_wav.sh

# VOICEVOX 合成ヘルパ（V2.0vv 以降）
curl -fsSL "$RAW/vv_say.py" | sudo tee /opt/voicevox/vv_say.py >/dev/null

# 送信テストツール
curl -fsSL "$RAW/test_send.py" | sudo tee /opt/dvswitch_bot/bin/test_send.py >/dev/null

# 構文・版確認
python3 -c "import ast; ast.parse(open('/opt/dvswitch_bot/bin/dvswitch_bot.py',encoding='utf-8').read()); print('bot syntax OK')"
grep -m1 "^__version__" /opt/dvswitch_bot/bin/dvswitch_bot.py
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py --version
```

期待値（2026-07-15 時点）: bot `V1.96vv` / vv_say `V2.0vv` / create_wav `V1.31vv`。

### 6.1 bot 初期設定

```bash
sudo /opt/dvswitch_bot/venv/bin/python3 /opt/dvswitch_bot/bin/bot_setup.py
```

対話に従って `bot_config.json`（応答頻度・時報モード・夜間モード・受信時間窓・TX_GAIN 等）を作成します。

---

## 7. 固定 WAV の作成（話者選択）

```bash
sudo /opt/dvswitch_bot/bin/create_wav.sh
```

対話の流れ（✅ 実機で全127スタイルのスキャンを確認済み）:

1. **話者選択** — 環境の `models/vvms/*.vvm` を全スキャンした一覧（style_id 昇順）から番号で選択。前回選択（初回は No.7 アナウンス = style_id 30 / 6.vvm）が既定。
2. コールサイン → 読み仮名（自動生成・修正可）
3. 設置場所の地名
4. 定時メッセージ1・2 → 読み（自動生成・修正可）
5. 確認 → 既存WAVの自動バックアップ（`/opt/dvswitch_bot/bak/wav/日時/`）→ 6ファイル生成

生成物: `fixed_intro.wav` / `fixed_outro.wav` / `time_intro.wav` / `001.wav` / `002.wav` / `time_outro.wav`（`/opt/dvswitch_bot/` 直下）。入力内容と選択話者は `wav_source.json` に記録され、次回のプリフィルと `--regen`（非対話再生成）に使われます。

参考: 話者と vvm の対応例 — 春日部つむぎ=8/0.vvm、ずんだもん(ノーマル)=3/0.vvm、波音リツ=9/3.vvm、玄野武宏=11/4.vvm、No.7(アナウンス)=30/6.vvm。🔴 style_id と vvm は**必ずセット**（不一致は合成失敗）。スクリプト経由で選べば自動で揃います。

---

## 8. bot の systemd ユニット作成

🔴 VV版はユニットを**手動で作成**します（インストーラはありません）。ExecStart が venv であることが最重要です。

```bash
sudo tee /etc/systemd/system/dvswitch-bot.service >/dev/null << 'EOF'
[Unit]
Description=OpenCCVoice DVSwitch bot (VV / dvswitch_bot.py)
After=network.target md380-emu.service analog_bridge.service mmdvm_bridge.service
Wants=analog_bridge.service mmdvm_bridge.service

[Service]
Type=simple
ExecStart=/opt/dvswitch_bot/venv/bin/python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
WorkingDirectory=/opt/dvswitch_bot
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now dvswitch-bot
systemctl is-active dvswitch-bot
sudo journalctl -u dvswitch-bot -n 20 --no-pager
```

起動ログに選択話者（例: `style_id=3` / `0.vvm`）のロードが出ていれば、`wav_source.json` の voice を正しく読んでいます。

> ⚠️ 話者を変更したとき: **①固定WAVは再生成した次の送出から**反映（bot は送出のたびに WAV を読み直すため再起動不要）、**②動的合成（時報の時刻等）は bot 再起動で**反映（起動時に1回ロードする設計）。

---

## 9. Web ダッシュボード（共用 dashboard/app.py）

JT/VV 共用のダッシュボードを導入します。`install.sh` が `web/` 作成 → `app.py` 配置 → `dvswitch-web.service` 登録・起動まで行います。

```bash
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/install.sh | sudo bash

systemctl is-active dvswitch-web
grep -m1 'app.py  V' /opt/dvswitch_bot/web/app.py   # V3.11 以降
```

ブラウザで `http://<このマシンのIP>:8081/` を開きます。VV ノードでは「読み上げ内容」カードで以下が使えます（V3.x）:

- **話者（音声キャラクター）のプルダウン変更**（全話者を自動スキャン）
- **入力値と読み仮名の編集**（CLI と同じ7項目、「自動生成」ボタン付き）
- 保存で `wav_source.json` 更新 → `create_wav.sh --regen`（非対話再生成）→ 話者が変わった場合のみ bot 自動再起動

> ⚠️ ダッシュボード実行ユーザーの sudo 許可が systemctl のみの場合、`/opt/dvswitch_bot/bin/create_wav.sh` の NOPASSWD 追加が必要です（root で動かしている場合は不要）。
> ⚠️ ポート 8081 は認証なしです。LAN 外へ公開しないでください（Pi-Star 系ではファイアウォールが既定で 8081 を遮断します）。

---

## 10. 動作確認

```bash
# (1) 送信テスト（固定WAVをそのまま TG へ送出）
python3 /opt/dvswitch_bot/bin/test_send.py

# (2) 全サービス確認
systemctl is-active md380-emu analog_bridge mmdvm_bridge dvswitch-bot dvswitch-web
```

- (1) で TGIF ダッシュボード（tgif.network）に自局の送信が見え、受信機で音声が聞こえれば音声経路は完成です。
- ハンディ機で TG へ**カーチャンク**（1秒弱の短い送信）→ 選択した話者で「こちらは、〜」の応答が返れば bot 動作 OK。
- 時報設定を有効にしていれば、毎時の時報が同じ話者で流れます（イントロ=固定WAV、時刻=動的合成の組み合わせ）。

---

## 11. 運用メモ

**話者の変更（2経路）**
- CLI: `sudo /opt/dvswitch_bot/bin/create_wav.sh` → 話者を選び直して再生成 → `sudo systemctl restart dvswitch-bot`
- Web: ダッシュボードの「読み上げ内容」カードで選択 → 保存して再生成（bot 再起動まで自動）

**テキストだけの変更**は bot 再起動不要（WAV は送出ごとに読み直し）。

**非対話再生成**: `sudo /opt/dvswitch_bot/bin/create_wav.sh --regen`（記録済みの texts と voice で全WAVを作り直し。vv_say.py 差し替え後の作り直し等に便利）。

**版の確認（vv サフィックスが VV版の証）**:
```bash
grep -m1 "^__version__" /opt/dvswitch_bot/bin/dvswitch_bot.py
/opt/dvswitch_bot/venv/bin/python3 /opt/voicevox/vv_say.py --version
grep -m1 "SCRIPT_VERSION=" /opt/dvswitch_bot/bin/create_wav.sh
```

**バックアップ/復元**: WAVセットは `create_wav.sh -r`、DVSwitch の ini は `dvs_config.sh -r` でいつでも世代復元できます。

**更新（デプロイ）**: 第6章と同じ `curl -fsSL <raw URL> | sudo tee <配置先>` パターンで上書き → 構文チェック → 該当サービス再起動。`systemctl cat dvswitch-bot` で ExecStart のパスを確認してから配置するのが安全です。

---

## 付録A トラブルシューティング（実例ベース）

**A-1. イントロだけ古い話者、コールサイン読みは新しい話者**
①固定WAVが旧 `vv_say.py`（6.vvm 固定の V1.0 相当）で生成されています。`vv_say.py --version` で `V2.0vv` 以降か確認 → 旧版なら差し替えて `create_wav.sh --regen`。bot（②動的合成）側は正常なので再起動不要。✅ 実際に発生・解決した事例。

**A-2. `systemctl status dvswitch-bot` が inactive なのに応答が返る**
bot が端末からフォアグラウンド起動されています（`ps aux | grep dvswitch_bot` に pts 付きプロセス）。そのまま service start すると**二重起動**で UDP 51000 の bind 競合や二重応答が起きます。手動プロセスを `kill` してから `systemctl start`。✅ 実例。

**A-3. `Unit dvswitch-bot.service not found`**
ユニット未作成です。第8章のユニットを作成 → `daemon-reload` → `enable --now`。✅ 実例（ocv-voicevox は当初手動起動運用だった）。

**A-4. bot 起動直後に落ちる（ImportError: voicevox_core）**
ExecStart が `/usr/bin/python3` になっています。venv の python3 に修正（第8章）。

**A-5. `.so.1.17.3 が見つからない`**
ONNX Runtime の版が変わっています。現行スクリプト（V2.0vv/V1.96vv 以降）は glob で自動解決するため発生しません。旧スクリプトなら更新してください。

**A-6. 起動時に `output_sampling_rate should be DEFAULT_SAMPLING_RATE` 警告**
旧版の 48kHz ハードコードです。V1.95b/V2.0vv 以降で撤去済み。更新してください。

**A-7. 相手局の受信機が応答冒頭でフリーズする／頭切れ（途中参加）**
TGIF が先頭の無音 DMR フレームを黙って落とし VoiceLCHeader が失われる既知事象。現行 bot は先頭を位相連続 100Hz マイクロトーン（約 -47dBFS）に置換して対策済み。旧版なら bot を更新。

**A-8. 同時 restart 後に無音**
Analog_Bridge の半死状態。第4章の順序再起動（md380 → analog → mmdvm → bot、3秒間隔）で復旧。

**A-9. GitHub からの取得が 403/429**
レート制限です。時間をおいて再試行。`curl -f` を付けているため、失敗時にファイルが壊れることはありません。

**A-10. ダッシュボード 8081 に繋がらない**
`systemctl is-active dvswitch-web` を確認。Pi-Star 系ではファイアウォールが 8081 を遮断します（`sudo iptables -I INPUT -p tcp --dport 8081 -j ACCEPT` で一時開放、再起動で消える点とセキュリティ判断に注意）。

---

## 付録B ファイル・版一覧（2026-07-15 時点）

| ファイル | 配置先 | 版 | 取得元（リポジトリ内） |
|---|---|---|---|
| dvswitch_bot.py | /opt/dvswitch_bot/bin/ | V1.96vv | dvs_ocv_vv/ |
| bot_setup.py | /opt/dvswitch_bot/bin/ | （JT版と共通） | dvs_ocv_vv/ |
| create_wav.sh | /opt/dvswitch_bot/bin/ | V1.31vv | dvs_ocv_vv/ |
| vv_say.py | /opt/voicevox/ | V2.0vv | dvs_ocv_vv/ |
| test_send.py | /opt/dvswitch_bot/bin/ | （共通） | dvs_ocv_vv/ |
| dvs_config.sh | /opt/dvswitch_bot/bin/ | （共通） | dvs_ocv_vv/ |
| app.py（共用） | /opt/dvswitch_bot/web/ | V3.11以降 | dashboard/ |
| bot_config.json | /opt/dvswitch_bot/ | — | bot_setup.py が生成 |
| wav_source.json | /opt/dvswitch_bot/ | — | create_wav.sh が生成 |

サービス: `md380-emu` / `analog_bridge` / `mmdvm_bridge` / `dvswitch-bot` / `dvswitch-web`

---

*本書は 2026年7月の実構築セッション（ocv-voicevox）の記録を基に再構成しました。リポジトリ: `ji2tab/OpenCCVoice-For-DVSwitch`（main）*
