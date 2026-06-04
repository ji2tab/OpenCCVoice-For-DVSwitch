# OpenCCVoice Project

[日本語 (Japanese)](#openccvoice-について) | [English](#about-openccvoice)

---

# OpenCCVoice について

OpenCCVoice は、JA2CCV 局の設計考案を基礎に、複数局の協力により発展してきたプロジェクトです。
本プロジェクトは、DVSwitch / DMR / Analog_Bridge 環境における自動音声応答・時報・案内放送技術を、オープンに共有し、改善し合い、継続的に発展させていくことを目的としています。

現在のシステムでは、Python によるログ監視、Open JTalk 音声合成、USRP 音声送信、スケジューリング機能などを組み合わせ、柔軟な自動応答システムを実現しています。

---

## 理念：ブラックボックスにしない、共有の精神

OpenCCVoice は、アマチュア無線の精神に基づき、以下の理念を掲げています。

> **「誰でも自由に使え、誰でも改良でき、そしてその成果をオープンに共有できる」**

特定の人だけが技術を抱え込む「ブラックボックス化」を避け、多くの局が改善に参加することで、技術の相互発展を促します。

この理念を象徴するものとして、**「OpenCCVoice」** という名称が付けられています。

---

# OpenCCVoice DVSwitch Bot

## 概要

DVSwitch Bot は、DVSwitch / Analog_Bridge / MMDVM_Bridge 環境向けに設計された、自動音声応答・時報・定時案内システムです。

> **現行構成（デーモン分離版）:** 設定ツール `bot_setup.py` と デーモン本体
> `dvswitch_bot.py` に分離し、`/opt/dvswitch_bot/bin/` に配置する。systemd 常駐時の
> `EOFError` 回避と、設定不正時のフェイルセーフを備える。以下に挙げる機能は、
> 時報の一体合成（「〇〇時です」）を導入した V1.58 系を踏襲している。

MMDVM_Bridge のログをリアルタイム監視し、受信状況に応じて以下の処理を自動実行します。

* カーチャンク検知による自動応答
* 毎正時の時報送信
* 定時アナウンス送信
* 重複応答抑制
* Open JTalk による動的音声合成
* USRP プロトコルによる Analog_Bridge 送信
* ログローテーション追従
* Graceful Shutdown 対応
* マルチスレッド動作

---

# 主な特徴

## 1. カーチャンク自動応答

短時間のPTT操作（カーチャンク）を検知し、自動応答を返します。

例：

> 「JJ2YYK局からの、アクセスを確認しました」

通常交信と誤認しないよう、最小受信時間・最大受信時間による判定を行います。

---

## 2. 毎正時の時報送信

毎正時に自動時報を送信します。

V1.58 では、従来の固定アウトロ音声を廃止し、

> 「21時です」

までを Open JTalk で一体合成する方式へ変更しました。

これにより、

* 「時」
* 「です」

の接続が滑らかになり、自然な抑揚で再生されます。

---

## 3. 定時アナウンス

指定回数（1時間あたり1〜3回）の定時メッセージ送信に対応しています。

対応ファイル：

* `001.wav`
* `002.wav`

毎正時との重複を避けながら、自動ローテーション送信されます。

---

## 4. 絶対時刻同期方式（ドリフト補正）

本システムの中核技術として、USRP 音声送信には、

> **time.monotonic() ベースの絶対時刻同期方式**

を採用しています。

20ms ごとの送信タイミングを絶対時刻基準で制御することで、

* ジッタ低減
* 音切れ防止
* Analog_Bridge への安定供給

を実現しています。

---

## 5. SDカード保護設計

一時音声ファイルは `/dev/shm`（RAMディスク）へ生成されます。

これにより、

* SDカード書き込み回数削減
* Raspberry Pi の寿命延長
* 高速な一時処理

を実現しています。

---

## 6. ログローテーション対応

MMDVM_Bridge のログローテーションを自動検出し、監視対象を自動切替します。

以下のケースへ対応：

* 日付変更による新規ログ生成
* inode 変更
* ログファイル置換

---

# 必要環境

## 対応環境

* Raspberry Pi OS
* DVSwitch
* Analog_Bridge
* MMDVM_Bridge

---

## 必須パッケージ

* open-jtalk
* open-jtalk-mecab-naist-jdic
* sox

---

## 音声モデル

使用音声：

* mei_normal.htsvoice

標準パス：

```bash
/usr/share/hts-voice/mei/mei_normal.htsvoice
```

---

# 必須音声ファイル

以下の WAV ファイルを事前配置してください。

| ファイル            | 用途           |
| --------------- | ------------ |
| fixed_intro.wav | カーチャンク応答イントロ |
| fixed_outro.wav | カーチャンク応答アウトロ |
| time_intro.wav  | 時報イントロ       |
| 001.wav         | 定時メッセージ1     |
| 002.wav         | 定時メッセージ2     |

配置先：

```bash
/opt/dvswitch_bot/
```

---

# 起動方法

スクリプトは **`/opt/dvswitch_bot/bin/`** に配置し、設定は専用ツール
`bot_setup.py` で作成する。デーモン本体 `dvswitch_bot.py` は起動時に
その設定ファイル（`/opt/dvswitch_bot/bot_config.json`）を読むだけで、
対話は行わない（systemd 常駐に適した構成）。

```bash
# 1) 先に設定ファイルを作成（対話）
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py

# 2) デーモン本体を起動（手動起動の例。常駐は systemd 推奨）
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
```

`bot_setup.py` で設定できる項目:

* 最小受信時間 / 最大受信時間（カーチャンク判定）
* 1時間あたりの定時放送回数（1〜3）
* ナイトモード（夜間の時報・定時メッセージ抑制）と開始/終了時刻

> 設定ファイルが無い・壊れている・値が不正な場合、デーモン本体は誤動作を避けるため
> **起動を拒否する（フェイルセーフ）**。必ず先に `bot_setup.py` を実行すること。

常駐化（systemd）や各スクリプトの取得を含む詳しい構築手順は、リポジトリの
**`Bookwormベース検証手順.md`** を参照。

---

# ライセンスと権利について

公開されるソースコード、回路図、関連ドキュメントの著作権は、各著作者および OpenCCVoice Project に帰属します。

OpenCCVoice は、技術共有と相互発展を目的としたオープンプロジェクトであり、公開物は GPL v3 の理念に基づいて取り扱われます。

---

## 1. 利用と改変について

* 誰でも自由に利用できます
* 改変・機能追加・組み込みが可能です

---

## 2. 再配布・派生物公開の条件

改変版や派生物を公開・配布する場合は、以下を遵守してください。

1. 原著作者を明示すること
2. 改変内容を明記すること
3. 派生物もオープンに公開すること

ブラックボックス化は禁止されます。

ソースコード・回路図・関連資料を公開してください。

---

## 3. ライセンス

本プロジェクトは、

> GNU General Public License v3 (GPL v3)

の理念に準拠しています。

正式 LICENSE 文書は公開時に同梱されます。

---

# 免責事項 (Disclaimer)

## 1. 無保証

本成果物は「現状のまま（AS IS）」提供されます。

製作者および OpenCCVoice Project は、

* 動作保証
* 特定用途適合性
* 不具合不存在

を保証しません。

---

## 2. 損害に対する非責任

本成果物の利用により発生した、

* 無線機故障
* Raspberry Pi 故障
* SDカード破損
* データ消失
* その他損害

について、製作者および関係者は責任を負いません。

---

## 3. 法令遵守

利用者は各国の電波法・関連法規を遵守してください。

特に以下は利用者責任で確認してください。

* 送信内容
* 送信間隔
* 変調レベル
* 電波占有時間
* 自動送信に関する規定

---

## 4. 自己責任運用

自作機器の接続・送信動作にはリスクがあります。

利用者自身の責任で、

* 配線確認
* レベル調整
* 送信試験
* 法令確認

を行ってください。

---

# About OpenCCVoice

The OpenCCVoice project is based on concepts originally designed by JA2CCV and developed collaboratively by multiple amateur radio operators.

The project focuses on open development of automatic voice response systems for DVSwitch / DMR environments using technologies such as:

* Python-based log monitoring
* Open JTalk speech synthesis
* USRP audio transmission
* Automatic time announcements
* Scheduled broadcasts
* Analog_Bridge integration

---

## Philosophy: No Black Box

> **"Free to use, free to improve, and results are shared openly."**

OpenCCVoice promotes open technical collaboration and avoids proprietary black-box development.

Users are encouraged to:

* study
* modify
* improve
* redistribute

the project openly.

---

# License

This project follows the philosophy of:

> GNU General Public License v3 (GPL v3)

Derivative works must remain open and properly credited.

---

# Disclaimer

This project is provided:

> **AS IS**

without warranty of any kind.

Users assume full responsibility for:

* radio operation
* legal compliance
* hardware safety
* transmission configuration

The authors are not liable for any damage or legal issues arising from use of this project.

---

**Project Contributors:**
JA2CCV / JI2TAB / JJ2YYK / OpenCCVoice Contributors
