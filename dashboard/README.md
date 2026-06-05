# OpenCCVoice for DVSwitch Web Dashboard

DVSwitch Bot の設定・監視・サービス制御を行う軽量 Web ダッシュボードです。  
Raspberry Pi 上の Flask アプリとして動作します。

## バージョン

**V2.2**

## 機能

| 機能 | 説明 |
|---|---|
| サービス制御 | dvswitch-bot の Start / Stop / Restart |
| Bot設定 | `bot_config.json` の全項目をWebフォームで編集 |
| DVSwitch設定 | `MMDVM_Bridge.ini` / `Analog_Bridge.ini` をWebフォームで編集 |
| 自動バックアップ | DVSwitch設定保存時に `/opt/dvswitch_bot/bak/ini/` へ自動バックアップ |
| ログ表示 | MMDVM_Bridge ログ末尾5行を表示・30秒自動更新 |
| バックアップ一覧 | ini バックアップのタイムスタンプ一覧（最新10件） |
| 変更ログ | Bot設定の変更履歴（項目・変更前後の値・日時）を記録・表示 |

## ファイル構成

```
openccvoice_v22/
├── app.py                  # Flask アプリ本体
├── dvswitch-web.service    # systemd サービスファイル
├── install.sh              # インストールスクリプト
└── README.md               # このファイル
```

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
scp -r openccvoice_v22/ pi@<RPi-IP>:~/

# RPi上で実行
cd ~/openccvoice_v22
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

## 変更履歴

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
