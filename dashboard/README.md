# OpenCCVoice for DVSwitch Web Dashboard

DVSwitch Bot の設定・監視・サービス制御を行う軽量 Web ダッシュボードです。  
Raspberry Pi 上の Flask アプリとして動作します。

## バージョン

**V3.21**

JT版 / JTW版（Open JTalk 系）・VV版 / VVW版（VOICEVOX 系）の全ノードで共用する Web ダッシュボードです。

## 機能

| 機能 | 説明 |
|---|---|
| サービス制御 | dvswitch-bot の Start / Stop / Restart。保存時は依存順＋待機つきの順序再起動 |
| Bot設定 | `bot_config.json` の全項目を Web フォームで編集（受信時間フィルタ・放送回数・ナイトモード等） |
| DVSwitch設定 | `MMDVM_Bridge.ini` / `Analog_Bridge.ini` / MMDVM `[Info]` を Web フォームで編集 |
| 3カード一括保存 | Bot設定・DVSwitch設定・MMDVM Info を1操作でまとめて保存し、関連サービスを再起動 |
| 送出音量（TX_GAIN） | 送出ゲインを Bot設定から調整（dvswitch_bot.py V1.68 以降） |
| 時刻案内モード | 時報・定時アナウンスの案内モードを設定 |
| 読み上げ内容の統合編集 | コールサイン読み・地名・定時メッセージ等のテキストを編集。VV版は話者変更、JT版は `--regen` で固定WAVを再生成。V3.1 で JT版ノードでもテキスト編集が可能に |
| 保存して再生成 | 読み上げ内容を保存し固定WAVを再生成（VV版は話者変更込み） |
| カスタム音声 | 標準音声（intro／001／002）を自前の音声ファイルに差し替え |
| テスト送信 | ダッシュボードから単発のテスト送信を実行 |
| 天気読み上げ | JTW版ノードでのみ有効。天気の親スイッチ・付与先（時報系／定時メッセージ系）・取得座標を編集（V3.2〜）。非 JTW ノードではカードをグレーアウト |
| 未知キー保護 | ダッシュボードが知らない設定キーも保存で失われない（既存ファイルを土台に差分更新。V3.2〜） |
| 外部リンク | 関連サービス（Dashboard 等）への外部リンクを表示 |
| 自動バックアップ | DVSwitch設定保存時に `/opt/dvswitch_bot/bak/ini/` へ自動バックアップ |
| ログ表示 | MMDVM_Bridge ログ末尾5行を表示・30秒自動更新 |
| バックアップ一覧 | ini バックアップのタイムスタンプ一覧（最新10件） |
| 変更ログ | Bot設定の変更履歴（項目・変更前後の値・日時）を記録・表示 |

## ファイル構成

```
dashboard/
├── app.py                     # Flask アプリ本体
├── dvswitch-web.service       # systemd サービスファイル
├── install.sh                 # インストールスクリプト
├── uninstall.sh               # アンインストールスクリプト
├── how to install uninstall.md # 導入・削除の手順メモ
├── 操作マニュアル.md            # 画面ごとの操作説明
├── Changelog_dashboard.md     # 版ごとの変更履歴（app.py / usrp_web.py）
├── usrp_web.py                # 受信音声の Web モニタ V0.16（別プロセス・別ポート／手動導入）
├── dvswitch-usrpweb.service   # usrp_web.py 用 systemd ユニットのテンプレート
└── README.md                  # このファイル
```

> `usrp_web.py` は **app.py とは独立した別プログラム**です（Flask ではなく aiohttp、
> ポートも 8081 ではなく 8443/HTTPS）。`install.sh` では配置されず、`app.py` からも参照されません。
> 導入は下の「受信音声 Web モニタ（usrp_web.py）」の手順で手動で行います。

## 前提条件

- Raspberry Pi (Raspbian / Raspberry Pi OS)
- Python 3 + python3-flask
- DVSwitch (MMDVM_Bridge + Analog_Bridge) インストール済み
- dvswitch-bot サービス設定済み

## パス設定（app.py 冒頭）

```python
BOT_CONFIG   = "/opt/dvswitch_bot/bot_config.json"
CHANGE_LOG   = "/opt/dvswitch_bot/bot_change_log.json"
MMDVM_INI    = "/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
DVSWITCH_INI = "/opt/MMDVM_Bridge/DVSwitch.ini"
ANALOG_INI   = "/opt/Analog_Bridge/Analog_Bridge.ini"
LOG_DIR      = "/var/log/mmdvm"
BAK_ROOT     = "/opt/dvswitch_bot/bak/ini"
SERVICE_NAME = "dvswitch-bot"
```

## インストール手順

### 新規インストール

```bash
# RPiへ転送
scp -r dashboard/ pi@<RPi-IP>:~/

# RPi上で実行
cd ~/dashboard
sudo bash install.sh
```

### 既存環境への上書き更新

```bash
sudo cp app.py /opt/dvswitch_bot/web/app.py
sudo systemctl restart dvswitch-web
```

## アクセス

```
http://<Raspberry-Pi-IP>:8081/
```

> **⚠️ セキュリティ上の注意**
> ダッシュボードは認証なしで `0.0.0.0:8081` で待ち受けます。
> 信頼できる LAN / VPN（Tailscale 等）内でのみ使用してください。インターネットへ直接公開しないこと。

## サービス管理

```bash
sudo systemctl status dvswitch-web
sudo systemctl start dvswitch-web
sudo systemctl stop dvswitch-web
sudo systemctl restart dvswitch-web
journalctl -u dvswitch-web -n 50
```

## アンインストール

```bash
sudo systemctl stop dvswitch-web
sudo systemctl disable dvswitch-web
sudo rm /etc/systemd/system/dvswitch-web.service
sudo rm -rf /opt/dvswitch_bot/web
sudo systemctl daemon-reload
```

## 受信音声 Web モニタ（usrp_web.py）

**V0.16 ／ 手動導入（systemd ユニットのテンプレートあり）**

Analog_Bridge が復号した受信音声（USRP 音声パケット）と、bot の応答音声ミラーを受け取り、
HTTPS + WebSocket でブラウザへ流して PC のスピーカーで鳴らす受信モニタです。
現状はフェーズ1で **受信（RX）専用**、送信は行いません。`app.py`（Flask・8081）とは
**別プロセス・別ポート**（aiohttp・8443/HTTPS）で動き、`dvswitch_bot.py` には触れません。

| 項目 | 値 |
|---|---|
| 版 | `usrp_web.py` **V0.16**（版情報パネル: monitor / bot / voice_make / dashboard の版を表示） |
| 待受 | `https://<node-ip>:8443/` |
| 受信ポート | `--usrp-port`（Analog_Bridge の復号 RX。`Analog_Bridge.ini` `[USRP]` の `txPort`） |
| ミラーポート | `--mirror-port`（bot 応答のミラー。`dvswitch_bot.py` V2.06jtw 以降の `WEB_MIRROR_*`。0 で無効） |
| 依存 | `aiohttp`（`app.py` の Flask とは別。bot を動かす python から見える場所へ入れる） |
| 配置先 | `/opt/dvswitch_bot/web/usrp_web.py` ／ 証明書 `/opt/dvswitch_bot/web/certs/` |

### 1. 依存パッケージ

```bash
# VOICEVOX 系ノード（venv 運用。dvswitch-usrpweb.service の既定もこちら）
sudo /opt/dvswitch_bot/venv/bin/pip3 install aiohttp

# JT系ノード（Raspberry Pi / システム python）
sudo pip3 install aiohttp
```

### 2. ファイル配置

```bash
sudo cp usrp_web.py /opt/dvswitch_bot/web/usrp_web.py
```

### 3. 自己署名証明書（SAN に IP を入れる）

ブラウザは CN だけの証明書を受け付けないため、**`subjectAltName` に接続先 IP** を入れます。

```bash
NODE_IP=192.168.1.50            # ← 実機の IP に置き換える
sudo mkdir -p /opt/dvswitch_bot/web/certs
sudo openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
  -keyout /opt/dvswitch_bot/web/certs/usrp_web.key \
  -out    /opt/dvswitch_bot/web/certs/usrp_web.crt \
  -subj   "/CN=${NODE_IP}" \
  -addext "subjectAltName=IP:${NODE_IP}"
sudo chmod 600 /opt/dvswitch_bot/web/certs/usrp_web.key
```

> 自己署名のため、初回アクセス時はブラウザの警告を承認する必要があります。

### 4. systemd ユニットの登録

本ディレクトリの [`dvswitch-usrpweb.service`](dvswitch-usrpweb.service) をテンプレートとして使います。
ポート番号・証明書パスは実機に合わせて編集してください。
**JT系ノードでは `ExecStart` の python を `/usr/bin/python3` に読み替えます**（ユニット内にも注記あり）。

```bash
sudo cp dvswitch-usrpweb.service /etc/systemd/system/dvswitch-usrpweb.service
sudo systemctl daemon-reload
sudo systemctl enable --now dvswitch-usrpweb
systemctl status dvswitch-usrpweb
journalctl -u dvswitch-usrpweb -n 50
```

### 5. アクセス

```
https://<node-ip>:8443/
```

ページ冒頭の版情報パネルに monitor / bot / voice_make / dashboard の版が出れば正常です
（`voice_make.py` を持たない JT版・VV版ノードでは voice_make は `—` 表示）。

> **⚠️ セキュリティ上の注意**
> `app.py` と同様に認証はありません。HTTPS ですが、信頼できる LAN / VPN 内でのみ使用してください。

### 手動起動（サービス化せず試す場合）

```bash
sudo /opt/dvswitch_bot/venv/bin/python3 /opt/dvswitch_bot/web/usrp_web.py \
  --usrp-port 51001 --mirror-port 51002 \
  --cert /opt/dvswitch_bot/web/certs/usrp_web.crt \
  --key  /opt/dvswitch_bot/web/certs/usrp_web.key --verbose
```

### アンインストール

```bash
sudo systemctl disable --now dvswitch-usrpweb
sudo rm /etc/systemd/system/dvswitch-usrpweb.service
sudo systemctl daemon-reload
sudo rm -f /opt/dvswitch_bot/web/usrp_web.py
```

---

## 変更履歴

> 詳細な版ごとの履歴は [`Changelog_dashboard.md`](Changelog_dashboard.md) を参照。

### V3.21
- 天気読み上げカードのレイアウト変更（機能は V3.2 と同一）。左セルの縦積みから全幅カードへ移し、
  内部を「天気を付ける対象｜取得座標」の2カラム横並びにした。

### V3.2
- 「天気読み上げ — JTW版」カードを新設（`WEATHER_ENABLED` / `WEATHER_ON_TIME_SIGNAL` /
  `WEATHER_ON_MESSAGE` / `WEATHER_LATITUDE` / `WEATHER_LONGITUDE`）。非 JTW ノードではグレーアウト。
- 🔴 未知キー保護を追加（V3.11 以前の欠陥修正）。従来はダッシュボードが知っているキーだけで
  `bot_config.json` を作り直していたため、JTW ノードで保存すると `WEATHER_*` が黙って消えていた。
- `bot_config.json` の組み立て・検証を `build_bot_cfg()` / `validate_bot_cfg()` に集約。

### V3.11
- 「保存して再生成」ボタンを右寄せに調整。

### V3.1
- 読み上げテキストの編集を Open JTalk（JT版）ノードでも可能に（共用対応の拡張）。
  話者が1つの JT版でもテキスト7項目を編集でき、`--regen` で固定WAVを再生成する。

### V3.0
- V2 系（V2.0〜V2.87bvv）を統合し、JT版（Open JTalk）／VV版（VOICEVOX）両ノード共用の
  ダッシュボードに再編。変更履歴を `Changelog_dashboard.md` へ分離。

### V2.3〜V2.87（主な追加）
- 3カード（Bot設定 / DVSwitch設定 / MMDVM Info）の一括保存。
- サービスの依存順＋待機つき順序再起動（同時 restart から変更）。
- 送出音量（TX_GAIN）の調整（dvswitch_bot.py V1.68 以降）。
- 時刻案内モードの設定。
- カスタム音声（intro／001／002 の差し替え）。
- 読み上げ内容カードの追加と「話者＋テキストの統合編集」への拡張。
- 話者変更＋`--regen` による固定WAV再生成、テスト送信、外部リンク。

### V2.2
- `CHANGE_LOG` 二重定義を修正
- `append_change_log` 二重定義を修正（`str()` 比較の正しい版を採用）
- 変更ログの表示スタイル改善（項目・変更前後を色分け表示）
- 不要な `import configparser, io` を削除
- コメント表記を統一

### V2.1
- タイトル変更: `DVSwitch Web Dashboard` → `OpenCCVoice for DVSwitch Web Dashboard`
- ポート変更: 8080 → 8081
- ログディレクトリ修正: `/opt/MMDVM_Bridge` → `/var/log/mmdvm`
- ログファイルパターン: 日付付きファイルを優先選択
- ログ表示行数: 40行 → 5行 / ログ枠高さ: 320px → 160px
- Bot設定 変更ログ機能追加

### V2.0
- 初版リリース
