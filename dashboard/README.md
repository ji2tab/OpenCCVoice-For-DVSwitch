# OpenCCVoice for DVSwitch Web Dashboard

DVSwitch Bot の設定・監視・サービス制御を行う軽量 Web ダッシュボードです。  
Raspberry Pi 上の Flask アプリとして動作します。

## バージョン

**V3.11**

JT版（Open JTalk）・VV版（VOICEVOX）両ノードで共用する Web ダッシュボードです。

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
| 外部リンク | 関連サービス（Dashboard 等）への外部リンクを表示 |
| 自動バックアップ | DVSwitch設定保存時に `/opt/dvswitch_bot/bak/ini/` へ自動バックアップ |
| ログ表示 | MMDVM_Bridge ログ末尾5行を表示・30秒自動更新 |
| バックアップ一覧 | ini バックアップのタイムスタンプ一覧（最新10件） |
| 変更ログ | Bot設定の変更履歴（項目・変更前後の値・日時）を記録・表示 |

## ファイル構成

```
dashboard/
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

## 変更履歴

> 詳細な版ごとの履歴は [`Changelog_dashboard.md`](Changelog_dashboard.md) を参照。

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
