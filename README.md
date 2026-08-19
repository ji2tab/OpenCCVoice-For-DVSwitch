# OpenCCVoice for DVSwitch

**DVSwitch / DMR 環境向け 自動音声応答（デジピーター）システム**

[日本語](#概要) ｜ [English](#english)

MMDVM_Bridge のログをリアルタイム監視し、カーチャンク（短い PTT）を検知して合成音声で
自動応答する、Raspberry Pi 向けの自動音声応答システムです。毎正時の時報・定時アナウンス・
ナイトモードにも対応し、24 時間無人で動作します。

---

## 概要

OpenCCVoice は、JA2CCV 局の設計考案を基礎に、複数局の協力により発展してきたプロジェクトです。
DVSwitch / DMR / Analog_Bridge 環境における自動音声応答・時報・案内放送技術を、オープンに
共有・改善し、継続的に発展させていくことを目的としています。

> **理念：ブラックボックスにしない、共有の精神**
> 「誰でも自由に使え、誰でも改良でき、そしてその成果をオープンに共有できる」
> 特定の人だけが技術を抱え込む「ブラックボックス化」を避け、多くの局が改善に参加することで
> 技術の相互発展を促します。

## 主な機能

- **カーチャンク自動応答** — 短い PTT を検知し、自局名を合成音声で自動応答
- **毎正時の時報** — 「こちらは〇〇、〇〇時です」を自動送出
- **定時アナウンス** — 1 時間に 時刻案内モード依存で最大4 回、定時メッセージを交互送出
- **ナイトモード** — 夜間は時報・定時を抑制（カーチャンク応答は 24 時間動作）
- **ログローテーション自動追従** — 日付が変わっても監視を継続
- **完全ローカル動作** — 外部 API に依存しない（Open JTalk によるローカル音声合成）
  ※天気読み上げを搭載した JTW版・VVW版のみ、天気の取得に Open-Meteo API を利用します

## システム構成

```
dvswitch_bot.py → Analog_Bridge → md380-emu → MMDVM_Bridge → DMR ネットワーク（TGIF 等）
     (USRP/UDP 51000)   (AMBE/UDP 2470)              (DMR/UDP 62031)
```

| 構成要素 | 役割 |
|---|---|
| `dvswitch_bot.py` | ログ監視・カーチャンク検知・WAV 送信（デーモン本体） |
| Analog_Bridge | 音声プロトコル変換ゲートウェイ |
| md380-emu | PCM ⇔ AMBE ソフトウェアコーデック |
| MMDVM_Bridge | DMR ネットワーク接続 |

## 動作環境

- Raspberry Pi Zero 2 W（実運用実績）
- Raspberry Pi OS (Bookworm) 32-bit ＋ DVSwitch-Server
- Open JTalk + SoX（音声合成・変換）
- Python 3（標準ライブラリのみ。サードパーティ非依存）

---

## クイックスタート

詳細は [構築導入設定 完全マニュアル](ocv_dvs_jt/OpenCCVoice_構築導入設定_完全マニュアル.md) を参照してください。
以下は導入済み環境での要点のみです。

```bash
# 1. スクリプト一式を /opt/dvswitch_bot/bin/ に取得
sudo mkdir -p /opt/dvswitch_bot/bin && sudo chown -R ocv:ocv /opt/dvswitch_bot
cd /opt/dvswitch_bot/bin
BASE=https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/ocv_dvs_jt
for f in dvs_config.sh create_wav.sh test_send.py dvswitch_bot.py bot_setup.py; do
  curl -fsSL "$BASE/$f" -o "$f"
done
chmod +x *.sh *.py

# 2. DVSwitch 設定（TGIF）
sudo ./dvs_config.sh

# 3. 固定 WAV を生成
sudo ./create_wav.sh

# 4. Bot の設定を作成
sudo python3 bot_setup.py

# 5. 送信テスト → 常駐化
python3 test_send.py /opt/dvswitch_bot/001.wav
sudo systemctl enable --now dvswitch-bot
```

---

## リポジトリ構成

### エディションとディレクトリ

本リポジトリには、音声合成エンジン（Open JTalk / VOICEVOX）× 天気読み上げの有無で
4 つのエディションと、共用の Web ダッシュボードが含まれます。

| ディレクトリ | エディション | 音声合成 | 天気読み上げ | 想定ノード |
|---|---|---|---|---|
| [`ocv_dvs_jt/`](ocv_dvs_jt/) | **Open JTalk 版（JT版）** | Open JTalk + SoX | — | Raspberry Pi ノード |
| [`ocv_dvs_jtw/`](ocv_dvs_jtw/) | **JTW版**（JT版＋天気） | Open JTalk + SoX | ✓ Open-Meteo | Raspberry Pi / x86_64 |
| [`ocv_dvs_vv/`](ocv_dvs_vv/) | **VOICEVOX 版（VV版）** | VOICEVOX | — | x86_64 Linux（ベアメタル/VM/コンテナ可、Incus 手順は別冊） |
| [`ocv_dvs_vvw/`](ocv_dvs_vvw/) | **VVW版**（VV版＋天気） | VOICEVOX | ✓ Open-Meteo | x86_64 Linux |
| [`dashboard/`](dashboard/) | **共用 Web ダッシュボード** | — | — | 全エディション共通 |
| [`Incus コンテナ/`](Incus%20コンテナ/) | Incus 構築リソース | — | — | ini サンプルと構築マニュアルのみ（スクリプトは `ocv_dvs_vv/` へ移設済み） |

JT版・VV版は天気なしの安定版、JTW版・VVW版はそれぞれの発展版です。天気系の改修は
`w` 付きの系譜で行い、安定版はそのまま維持されます。

Web ダッシュボードは 4 エディションのいずれでも共用です（[`dashboard/app.py`](dashboard/app.py)）。

### 版数

| ファイル | JT版（`ocv_dvs_jt/`） | JTW版（`ocv_dvs_jtw/`） | VV版（`ocv_dvs_vv/`） | VVW版（`ocv_dvs_vvw/`） |
|---|---|---|---|---|
| `dvswitch_bot.py` | V1.95 | V2.07jtw | V1.99vv | V2.02vvw |
| `create_wav.sh` | V1.21 | V1.21 | V1.32vv | V1.32vv |
| `dvs_config.sh` | V1.1 | V1.1 | V1.1 | V1.1 |
| `bot_setup.py` | JT版と共通 | V2.04jtw（天気対応） | JT版と共通 | JT版と共通 |
| `test_send.py` | 4エディションすべて共通（同一内容） | | | |
| `vv_say.py` | — | — | V2.0vv | V2.0vv |
| `voice_make.py` | — | V1.01vmp | — | — |

`create_wav.sh` / `dvs_config.sh` / `test_send.py` は JT版とJTW版、VV版とVVW版でそれぞれ同一内容です。

共用 Web ダッシュボード `dashboard/app.py` は **V3.21**。
## パス変更のお知らせ（2026-07）

JT版（Open JTalk 版）のソース5本とマニュアル5冊を、まずリポジトリ直下から `dvs_ocv_JT/` へ移設し、その後ディレクトリ名を全小文字の [`ocv_dvs_jt/`](ocv_dvs_jt/) へ改名しました（VV版も `dvs_ocv_vv/` → [`ocv_dvs_vv/`](ocv_dvs_vv/) へ改名）。VV版と同列の構成です。
旧 `.../main/` 直下および旧 `.../main/dvs_ocv_JT/...` の raw 取得 URL は **404** になります。取得スクリプトは `.../main/ocv_dvs_jt/...` へパスを更新してください。


### スクリプト（JT版・`/opt/dvswitch_bot/bin/` に配置）

| ファイル | 役割 |
|---|---|
| [`dvswitch_bot.py`](ocv_dvs_jt/dvswitch_bot.py) | 自動応答デーモン本体（JSON 設定を読むだけ。常駐向け） |
| [`bot_setup.py`](ocv_dvs_jt/bot_setup.py) | Bot 設定ツール（`bot_config.json` を対話作成） |
| [`dvs_config.sh`](ocv_dvs_jt/dvs_config.sh) | DVSwitch ini を TGIF 用に一括設定（自動バックアップ付き） |
| [`create_wav.sh`](ocv_dvs_jt/create_wav.sh) | 固定 WAV を対話生成（自動バックアップ付き） |
| [`test_send.py`](ocv_dvs_jt/test_send.py) | USRP 単発送信テスト |

### ドキュメント

| ドキュメント | 内容 |
|---|---|
| [構築導入設定 完全マニュアル](ocv_dvs_jt/OpenCCVoice_構築導入設定_完全マニュアル.md) | OS インストールから運用まで、新規構築を通しで再現できる実務マニュアル |
| [VV版（VOICEVOX）構築手順書](ocv_dvs_vv/OpenCCVoice%20for%20DVSwitch%20VV%E7%89%88%EF%BC%88VOICEVOX%EF%BC%89%E6%A7%8B%E7%AF%89%E6%89%8B%E9%A0%86%E6%9B%B8.md) | VV版（VOICEVOX / x86_64 Linux）をゼロから構築する手順書。Incus で環境を用意する場合は『Incus コンテナ/incus構築マニュアル.md』を先に実施 |
| [操作マニュアル](ocv_dvs_jt/OpenCCVoice_操作マニュアル.md) | 日常運用の逆引き（起動停止・設定変更・音声差し替え・トラブル対応） |
| [カスタム音声マニュアル](ocv_dvs_jt/カスタム音声.md) | 標準音声（intro／001／002）を自前の音声ファイルに差し替える手順（cstm 機能） |
| [README_PROJECT](README_PROJECT.md) | プロジェクトの理念・背景・詳細説明 |

### ソフトウェア仕様書（[`specification/`](specification/)）

スクリプト内部の技術仕様（定数・関数・処理フロー・パケット構造など）。

| 仕様書 | 対象 |
|---|---|
| [システム仕様書](specification/OpenCCVoice_システム仕様書.md) | システム全体の構成・データフロー・ポート・配置 |
| [dvswitch_bot 仕様書](specification/dvswitch_bot_ソフトウェア仕様書.md) | デーモン本体の内部仕様 |
| [bot_setup 仕様書](specification/bot_setup_ソフトウェア仕様書.md) | 設定ツールの内部仕様 |
| [dvs_config 仕様書](specification/dvs_config_ソフトウェア仕様書.md) | DVSwitch ini 設定ツールの内部仕様 |
| [create_wav 仕様書](specification/create_wav_ソフトウェア仕様書.md) | 固定 WAV 生成ツールの内部仕様 |
| [test_send 仕様書](specification/test_send_ソフトウェア仕様書.md) | 送信テストツールの内部仕様 |
| [vv_say 仕様書](specification/vv_say_ソフトウェア仕様書.md) | VOICEVOX 音声合成ヘルパの内部仕様（VV版・VVW版のみ） |

---

## ファイル配置（実機）

```
/opt/dvswitch_bot/
├── bin/                スクリプト（dvswitch_bot.py, bot_setup.py, dvs_config.sh,
│                       create_wav.sh, test_send.py。JTW版は voice_make.py も）
├── web/                共用 Web ダッシュボード（app.py。導入した場合のみ）
├── venv/               VV版・VVW版のみ（voicevox_core を持つ Python 仮想環境）
├── *.wav               固定 WAV（fixed_intro/outro, time_intro, 001, 002）
├── bot_config.json     Bot 設定
├── wav_source.json     読み上げソーステキストと話者の記録
└── bak/
    ├── ini/            dvs_config.sh のバックアップ
    └── wav/            create_wav.sh のバックアップ
```

---

## ライセンス

[LICENSE](LICENSE) を参照してください。

## クレジット

JA2CCV 局の設計考案を基礎に、JI2TAB / JJ2YYK ほか複数局の協力により発展してきた
オープンプロジェクトです。

---

## English

**OpenCCVoice for DVSwitch** is an automatic voice-response (digipeater) system for
DVSwitch / DMR environments on the Raspberry Pi. It monitors MMDVM_Bridge logs in real
time, detects "kerchunk" (short PTT) transmissions, and responds automatically with
synthesized voice. It also provides hourly time signals, scheduled announcements, and a
night mode, running unattended 24/7.

Built on the design concept of JA2CCV and developed through the cooperation of multiple
stations, OpenCCVoice aims to keep this technology open — free to use, free to improve,
and openly shared rather than kept as a black box.

**Stack:** Raspberry Pi OS (Bookworm) + DVSwitch-Server, Open JTalk + SoX, Python 3
(standard library only).

This repository ships four editions — an **Open JTalk edition** (`ocv_dvs_jt/`, for Raspberry Pi nodes), a **VOICEVOX edition** (`ocv_dvs_vv/`), and weather-enabled variants of each (`ocv_dvs_jtw/`, `ocv_dvs_vvw/`, which read out local weather via the Open-Meteo API) — plus a **shared web dashboard** (`dashboard/`, `app.py` V3.21) used by all of them.

See the [complete setup manual](ocv_dvs_jt/OpenCCVoice_構築導入設定_完全マニュアル.md) (Japanese)
to build the system from scratch, and [`specification/`](specification/) for per-script
technical specifications.
