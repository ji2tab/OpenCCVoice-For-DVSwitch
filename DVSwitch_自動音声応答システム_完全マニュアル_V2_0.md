# DVSwitch 自動音声応答システム 完全マニュアル V2.3

> ⚠️ **【重要】このマニュアルは旧版（Pi-Star/WPSD + V1.58）の記録です**
>
> 本書は **Pi-Star / WPSD 環境**で、単一スクリプト **`dvswitch_bot158.py`（V1.58）**
> を用いた構成の記録です。その後システムは次のように刷新されました:
> - スクリプトを **デーモン本体 `dvswitch_bot.py` ＋ 設定ツール `bot_setup.py`** に分離
>   （systemd 常駐時の `EOFError` 回避と、設定不正時のフェイルセーフを実現）
> - 全スクリプトを **`/opt/dvswitch_bot/bin/`** に集約
> - 検証環境を **Raspberry Pi OS (Bookworm) + DVSwitch-Server** に移行
>
> **これから新規に構築する場合は、最新の手順書を参照してください:**
> - **`Bookwormベース検証手順.md`**（Bookworm + DVSwitch-Server の実機検証手順）
> - **`xyz.md`**（完全マニュアル V3.0 系・バックアップ/リストア章つき）
>
> 本書は、V1.58 時代の設計思想・教訓（絶対時刻同期、ログ監視、USRP 注入など）の
> 記録として価値があるため保存しています。コマンド中の `pi-star` ユーザや
> `dvswitch_bot158.py` というファイル名は**当時のもの**で、現行リポジトリの構成
> （`ocv` ユーザ / `dvswitch_bot.py` / `bin/` 配置）とは異なる点に注意してください。

> **このマニュアルについて**
>
> Pi-Star / WPSD 環境において、DVSwitch（Analog_Bridge）と Python スクリプトを連携させ、
> DMR ネットワーク上の交信終了を検知して自動で音声アナウンス（デジピーター応答）を
> 送出するシステムの構築・運用マニュアルです。
>
> **初めて読む方でも、このマニュアル1冊で同じシステムを再現できる**ことを目標に、
> 専門用語の解説、注意点、トラブル時の対処法を可能な限り盛り込んでいます。
>
> **V2.1 での重要な追加:** システムを根本から安定させた「最大のブレイクスルー」である
> **「絶対時刻によるパケット同期（ドリフト補正）」アルゴリズム**を、スクリプト本体と
> 教訓セクションに追加しました。
>
> **V2.2 での重要な追加:**
> - スクリプト本体を別添ファイル `callsign_auto_reply.py` として独立化
> - 実運用環境（**Raspberry Pi Zero 2 W**）の動作実績を反映
> - **「JJ2YYK 自動応答システムを支える5つの魔法」**章を新設
>   （絶対時刻同期 / ログ監視 / USRP 注入 / communicate / SoX 一発生成）

**V2.3 での重要な更新:**

> - スクリプト本体を **`dvswitch_bot158.py`（V1.58安定版）** に移行
> - カーチャンク自動応答・毎正時時報・定時アナウンス機能を統合
> - ログローテーション自動追従・Graceful Shutdown・マルチスレッド対応
> - 固定WAVファイル（`/opt/dvswitch_bot/`）による高品質応答を実現
> - 第3部を `dvswitch_bot158.py` の実装手順に全面更新

---

## 目次

- [はじめに](#はじめに)
- [専門用語ミニ辞典](#専門用語ミニ辞典)
- [事前準備チェックリスト](#事前準備チェックリスト)
- [第1部：環境構築編](#第1部環境構築編)
- [第2部：DVSwitch編](#第2部dvswitch編)
- [第3部：ソフトウェア編 — OpenCCVoice for DVSwitch](#第3部ソフトウェア編--openccvoice-for-dvswitch)
- [第4部：動作確認とテスト手順](#第4部動作確認とテスト手順)
- [第5部：運用上の注意と法令遵守](#第5部運用上の注意と法令遵守)
- [第6部：バックアップとリストア](#第6部バックアップとリストア)
- [付録：クイックリファレンス](#付録クイックリファレンス)
- [🧙‍♂️ 開発秘話・設計思想 — 5つの魔法](#-開発秘話設計思想--jj2yyk-自動応答システムを支える5つの魔法)
- [おわりに](#おわりに)

## 別添ファイル

このマニュアルには以下の別添ファイルがあります。**マニュアルとセットで保管**してください。

| ファイル名 | 内容 |
|---|---|
| `dvswitch_bot158.py` | DVSwitch ログ監視・自動音声応答システム V1.58（安定版・第3部の実装） |

---

# はじめに

## このシステムで何ができるのか

このシステムを構築すると、以下のことが自動で行えます。

1. **カーチャンク自動応答** — 短時間の PTT 操作（カーチャンク）を検知し、「JJ2YYK 局からのアクセスを確認しました」と自動応答
2. **毎正時の時報送信** — 毎時 00 分に「こちらは JJ2YYK、〇〇時です」と自動時報
3. **定時アナウンス** — 1 時間あたり指定回数の定時メッセージ（001.wav / 002.wav）を自動ローテーション送信
4. **重複応答防止** — 応答後の一定時間（デフォルト 15 秒）は再応答を抑制
5. **ログローテーション追従** — MMDVM_Bridge ログの日付切り替えを自動検出して監視対象を自動切替

これは**ハム無線界における「電子的なデジピーター（自動中継局）」**であり、
カーチャンクへの応答から定期放送まで、24時間無人で動作します。

## 必要なもの一覧

### ハードウェア
- **Raspberry Pi**（以下のいずれか）
  - **Raspberry Pi Zero 2 W** ⭐ 比較的安定動作確認済み（JJ2YYK 局での実運用環境）
  - **Raspberry Pi 3B+ / 4 / 5**（高負荷時の余裕を求める場合）
- **microSD カード**（16GB 以上、Class 10 推奨）
- **電源アダプタ**（公式の 5V 3A 推奨。Zero 2 W は 5V 2.5A でも可）
- **MMDVM ホットスポット基板**（DVMEGA、ZUMspot、JumboSPOT 等）
- **インターネット接続**（有線 LAN または Wi-Fi）

> **Raspberry Pi Zero 2 W について:**
> JJ2YYK 局の実運用では Pi Zero 2 W で**比較的安定して動作**しています。
> 小型・低消費電力でホットスポット用途に最適です。CPU は 4 コア ARM Cortex-A53 で、
> Pi 3 相当の性能があるため、本システムも十分動かせます。
> ただし負荷状況によっては Pi 4 以上の方が余裕があります。発熱対策（ヒートシンク）は
> 推奨されます。

### ソフトウェア
- **Pi-Star または WPSD**（事前にセットアップ済みであること）
- **DVSwitch 一式**（Analog_Bridge / MMDVM_Bridge / md380-emu）
- **Python 3.x**（Pi-Star に標準搭載）

### 資格・登録
- **アマチュア無線技士免許**（第三級以上推奨）
- **DMR ID の登録**（[radioid.net](https://radioid.net) で取得）
- **コールサイン**

## 想定する読者

- 自宅で Pi-Star / WPSD を運用している
- SSH 接続でラズパイを触ったことがある
- Linux コマンドに少し慣れている（または手順通りなら実行できる）
- アマチュア無線の運用ルールを理解している

---

# 専門用語ミニ辞典

このマニュアルに出てくる主要な用語を、初心者向けに解説します。

| 用語 | 読み方 | 意味 |
|---|---|---|
| **DMR** | ディーエムアール | Digital Mobile Radio。デジタル業務無線規格を流用したアマチュア無線方式 |
| **AMBE** | アンビー | Advanced Multi-Band Excitation。DMR で使われる音声圧縮方式（特許あり） |
| **USRP** | ユーエスアールピー | Universal Software Radio Peripheral。元はハードウェア無線機の名前だが、DVSwitch ではプロトコル名として使われている |
| **PCM** | ピーシーエム | Pulse Code Modulation。生（無圧縮）のデジタル音声データ |
| **Pi-Star** | パイスター | Raspberry Pi をホットスポットにするための統合 OS |
| **WPSD** | ダブルピーエスディー | Pi-Star の進化版・派生 OS |
| **MMDVM** | エムエムディーブイエム | Multi-Mode Digital Voice Modem。多モード対応のデジタル音声モデム |
| **MMDVMHost** | エムエムディーブイエムホスト | MMDVM 基板を制御するプログラム本体 |
| **DVSwitch** | ディーブイスイッチ | デジタル音声をプロトコル変換する一連のソフトウェア群 |
| **Analog_Bridge** | アナログブリッジ | DVSwitch の中核。アナログ音声とデジタル音声を変換 |
| **MMDVM_Bridge** | エムエムディーブイエムブリッジ | MMDVM 系プロトコルを DVSwitch に橋渡しする |
| **md380-emu** | エムディーサンパチマルエミュ | Tytera MD-380 という DMR 無線機のファームウェアを利用した AMBE ソフト変換器 |
| **デジピーター** | — | デジタル中継局。ここでは「自動応答機能を持つ電子局」の意 |
| **ホットスポット** | — | 自宅の小型中継機。インターネット経由で世界中の DMR ネットに接続できる |
| **UDP** | ユーディーピー | User Datagram Protocol。早いが信頼性の低い通信プロトコル。音声に向く |
| **systemd** | システムディー | Linux のサービス管理機構。`systemctl` コマンドで操作 |
| **SSH** | エスエスエイチ | Secure Shell。リモートからラズパイにログインして操作する仕組み |

---

# 事前準備チェックリスト

実装を始める前に、以下がすべて満たされているか確認してください。
**ここを飛ばすと、後で必ずハマります。**

## ハードウェア・OS

- [ ] Raspberry Pi が起動し、ネットワークに接続できている
- [ ] MMDVM 基板が正しく取り付けられ、認識されている
- [ ] Pi-Star または WPSD のダッシュボードがブラウザから見える
- [ ] SSH でログインできる（デフォルト: `ssh pi-star@<IPアドレス>`、パスワード `raspberry`）

## DMR の動作確認

- [ ] **既に DMR で他局と交信できる状態である**（このシステムは「動いている DMR 環境」に
      追加するためのもの）
- [ ] DMR ID が Pi-Star に正しく登録されている
- [ ] BrandMeister や TGIF などのリフレクター/ネットワークに接続できる
- [ ] ダッシュボードの「Local RF Activity」に自分の交信が記録される

## 必須コンポーネントの存在確認

SSH ログイン後、以下のコマンドで必要なものが揃っているか確認します。

```bash
# Analog_Bridge の存在確認
ls -la /opt/Analog_Bridge/Analog_Bridge.ini

# MMDVM_Bridge の存在確認
ls -la /opt/MMDVM_Bridge/MMDVM_Bridge.ini

# md380-emu の存在確認
which md380-emu
sudo systemctl status md380-emu

# ログディレクトリの存在確認
ls -la /var/log/mmdvm/
```

すべて「ファイルが存在する」「サービスが認識されている」状態であることを確認してください。
**もし存在しない場合は、Pi-Star の「Update」と「DVSwitch のインストール」を先に行ってください。**

## 注意：DVSwitch のインストールについて

DVSwitch が未導入の場合は、以下のような手順が必要です（Pi-Star のバージョンによって異なる）。

```bash
# DVSwitch のリポジトリ追加（参考、環境により異なる）
sudo apt-get install -y dvswitch
```

> **重要:** DVSwitch のインストール手順は Pi-Star / WPSD のバージョンや時期によって
> 大きく異なります。本マニュアルでは「DVSwitch が既にインストール済み」を前提とします。
> 未導入の場合は [DVSwitch 公式](http://dvswitch.org) のドキュメントを参照してください。

---

# 第1部：環境構築編

## 1-1. システムの全体像

音声を DMR ネットワークに流す際、データは以下の順序でバケツリレーされます。

```
┌─────────────────────┐
│ Python スクリプト   │  ← テキストを音声合成
│ (dvswitch_bot158)    │
└──────────┬──────────┘
           │ USRP プロトコル (UDP 51000)
           ▼
┌─────────────────────┐
│   Analog_Bridge     │  ← 音声プロトコル変換ゲートウェイ
└──────────┬──────────┘
           │ AMBE 変換依頼 (UDP 2470)
           ▼
┌─────────────────────┐
│     md380-emu       │  ← PCM ⇔ AMBE 変換
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   MMDVM_Bridge      │  ← DMR ネットワークへの橋渡し
└──────────┬──────────┘
           │ DMR Network (UDP 62031)
           ▼
┌─────────────────────┐
│ Pi-Star (MMDVMHost) │
└──────────┬──────────┘
           │ 電波 / インターネット
           ▼
   無線機 / DMR ネットワーク
```

各コンポーネントの役割は以下の通りです。

| コンポーネント | 役割 |
|---|---|
| Python スクリプト | 音声合成（テキスト→WAV）と USRP パケット送信 |
| Analog_Bridge | 音声プロトコル変換ゲートウェイ |
| md380-emu | PCM ⇔ AMBE のソフトウェア・トランスコーダー |
| MMDVM_Bridge | DMR ネットワークへのブリッジ |
| Pi-Star (MMDVMHost) | 無線機制御・ダッシュボード |

## 1-2. 設計思想 — なぜこの構成なのか

### なぜ「ログ監視」なのか？（VOX や音声検知との違い）

従来の自動応答では「スピーカーから音が出なくなったこと（無音）」を検知する VOX 方式が
主流でした。しかしこの方式では「ノイズでの誤検知」や「無音の瞬間に途切れるバタつき」が
発生します。

本システムでは、DVSwitch の心臓部が出力する **MMDVM_Bridge の動作ログ（テキスト）** を
リアルタイムで直接監視します。デジタルデータとしての「通信開始（header）」と
「通信終了（end of voice）」を文字列として正確にキャッチするため、誤動作が一切なく、
完璧なタイミングでの応答が可能です。

> **初心者向け解説:** ログ監視は「目で見て判断する」のではなく「文字を読んで判断する」
> アプローチです。テキスト「received network end of voice transmission」が出てきた瞬間に
> 確実に応答できるため、誤動作がほぼゼロになります。

### なぜ「UDP（USRP プロトコル）」なのか？

仮想的なオーディオケーブル（仮想サウンドカード）を使うと、OS の音声ミキサー設定が
非常に複雑になります。本システムは、生成した WAV ファイルのデータを細かく切り刻み、
USRP という通信プロトコルにパッケージングして、**ネットワーク通信（UDP）として
直接 DVSwitch のポートに流し込む**手法をとっています。これによりサウンドカードの
相性問題から完全に解放されました。

> **初心者向け解説:** スピーカーやマイクを経由せず、「ネットワーク通信」だけで
> 音声を運ぶイメージです。ラズパイの中でデータがそのまま流れていきます。

### なぜ「Open JTalk + SoX」なのか？

DMR のネットワークに音声を流すには、**「8000Hz, モノラル, 16bit」の純粋な PCM 音声
データ**である必要があります。

1. **Open JTalk**: 外部インターネット（API）に依存せず、Raspberry Pi 等のローカル内で
   瞬時にテキストを音声化します。
2. **SoX**: Open JTalk が作った高品質な音声（48000Hz）を、**Analog_Bridge（USRP プロトコル）の入力仕様**（8000Hz, モノラル, 16bit PCM）に
   劣化なく、かつ一瞬で正確に変換するために必須のツールです。

> **初心者向け解説:** 「外部 API を使わない」のは、インターネット遅延や障害の影響を
> 受けないため、そして個人情報を外部に送らないためです。**完全にローカル完結**します。

### なぜ「絶対時刻同期」なのか？ ⭐ 最大のブレイクスルー

このシステムを安定させた**「一番の魔法」**は、UDP パケットの送信タイミングを
**絶対時刻で同期**させるアルゴリズムです。

#### 問題：単純な `time.sleep(0.02)` ではダメな理由

DMR は「20ms ごとに 1 パケット」という厳密なリズムで音声を流す必要があります
（1 秒間に正確に 50 パケット）。

しかし、Python スクリプトの処理自体に時間がかかります:

```
WAV 読込 → USRP パケット作成 → ネットワーク送信
     ↑ この処理だけで約 1～2 ミリ秒かかる
```

これに単純な `time.sleep(0.02)` を組み合わせると…

```
❌ 悪い例（単純 Sleep）:
処理(2ms) + 休む(20ms) = 1 周 22ms
→ 100 パケット送るうちに 200ms のズレが発生
→ Analog_Bridge のバッファが空になる
→ プツプツ・ケロケロが発生
```

これを **「ドリフト（時刻のズレ）」** と呼びます。

#### 解決策：絶対時刻からの逆算

「前の処理が終わってから 20ms 休む」のではなく、**「送信開始時刻から数えて、
今は何ms 経過すべきか」を毎回逆算**して、休む時間を微調整します。

```
✅ 良い例（時刻同期）:
開始時刻 T0 を記録
→ パケット 1 は T0 + 20ms に送る
→ パケット 2 は T0 + 40ms に送る
→ パケット 3 は T0 + 60ms に送る
→ 処理時間のブレを毎回吸収して、絶対時刻にガッチリ同期
```

この仕組みにより、Analog_Bridge には**寸分違わぬリズムでパケット**が届き、
プツプツ・ケロケロが**完全に消滅**します。これが DMR という厳しいデジタル規格の
波に乗せるための、決定的な技術です。

実装は第3部の `talk()` 関数で行っており、詳細は **教訓 8** にて図解と共に解説します。

## 1-3. システムの書き込み可能モードへの移行

Pi-Star / WPSD はデフォルトでファイルシステムが読み取り専用になっています（SD カードの
寿命を延ばすため）。設定変更やインストールを行うため、書き込み可能モードに切り替えます。

```bash
# 書き込み可能モードへ変更
rpi-rw
```

> **重要:** 作業が完了したら必ず `rpi-ro` で読み取り専用に戻してください。
> 書き込み可能のまま停電すると SD カードが破損するリスクがあります。

## 1-4. 必要パッケージのインストール

音声合成エンジン（Open JTalk）、音声変換ツール（SoX）、解凍ツール（unzip）を OS に
インストールします。

```bash
# パッケージリストの更新
sudo apt-get update

# 必要なパッケージのインストール
sudo apt-get install -y \
    open-jtalk \
    open-jtalk-mecab-naist-jdic \
    hts-voice-nitech-jp-atr503-m001 \
    sox \
    unzip
```

| パッケージ | 用途 |
|---|---|
| open-jtalk | 日本語テキスト音声合成エンジン本体 |
| open-jtalk-mecab-naist-jdic | 日本語形態素解析用辞書 |
| hts-voice-nitech-jp-atr503-m001 | 標準音声モデル（男声） |
| sox | 音声フォーマット変換ツール |
| unzip | ZIP ファイル解凍用 |

### インストール後の動作確認

```bash
# Open JTalk のバージョン確認
open_jtalk -h

# SoX のバージョン確認
sox --version

# 試しに音声合成してみる（無音 WAV が /tmp/test.wav に生成されればOK）
echo "テスト" | open_jtalk \
    -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
    -m /usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice \
    -ow /tmp/test.wav
ls -la /tmp/test.wav
```

`/tmp/test.wav` が数 KB 以上のサイズで生成されていれば成功です。
**0 バイトの場合は Open JTalk が正しく動いていません。**

## 1-5. 高品質音声モデル「メイ」の導入

標準のロボット声（男声）ではなく、人間らしく流暢な女性の声（MMDAgent メイ）を
システムに組み込みます。

```bash
# 一時ディレクトリに移動
cd /tmp

# MMDAgent のサンプルデータをダウンロード
wget -L --content-disposition https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip
# ※ SourceForge はリダイレクトが発生するため -L オプションが必要です。ダウンロードに失敗する場合は --no-check-certificate を追加してみてください。

# 解凍
unzip MMDAgent_Example-1.8.zip

# 配置先ディレクトリの作成と音声モデルのコピー
sudo mkdir -p /usr/share/hts-voice/mei
sudo cp MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice /usr/share/hts-voice/mei/

# 配置の確認
ls -la /usr/share/hts-voice/mei/

# 一時ファイルの掃除
rm -rf MMDAgent_Example-1.8 MMDAgent_Example-1.8.zip
```

導入後、音声モデルは以下のパスから利用可能になります。

```
/usr/share/hts-voice/mei/mei_normal.htsvoice
```

### メイの声質バリエーション（参考）

MMDAgent_Example には、以下のような複数のメイの声が含まれています。
お好みで差し替えることが可能です。

| ファイル名 | 声質 |
|---|---|
| `mei_normal.htsvoice` | 通常（最も自然） |
| `mei_happy.htsvoice` | 嬉しそう |
| `mei_sad.htsvoice` | 悲しそう |
| `mei_angry.htsvoice` | 怒り |
| `mei_bashful.htsvoice` | 恥ずかしそう |

> **ライセンス注意:** メイの音声モデルは MMDAgent プロジェクトのライセンスに従います。
> 商用利用の場合は[ライセンス条項](http://www.mmdagent.jp)を必ず確認してください。
> アマチュア無線での非商用利用は問題ありません。

---

# 第2部：DVSwitch編

## 2-1. Analog_Bridge（音声プロトコル変換ゲートウェイ）

様々な音声プロトコル（USRP、AMBE、DMR、YSF等）を交通整理するルーターです。
外部（Python スクリプト）からの入力を受け付ける「耳」の設定を行います。

### 設定ファイルを開く

```bash
sudo nano /opt/Analog_Bridge/Analog_Bridge.ini
```

> **nano の基本操作:**
> - 保存: `Ctrl + O` → Enter
> - 終了: `Ctrl + X`
> - 検索: `Ctrl + W`（探したい文字を入力 → Enter）
> - カット: `Ctrl + K`
> - ペースト: `Ctrl + U`

### ⚠️ 編集前に必ずバックアップ

```bash
sudo cp /opt/Analog_Bridge/Analog_Bridge.ini /opt/Analog_Bridge/Analog_Bridge.ini.backup
```

**設定ファイルを編集する前は、必ずバックアップを取ってください。**
失敗してもこのファイルから戻せば元通りになります。

### [USRP] セクション（Python スクリプトとの接続口）

```ini
[USRP]
rxPort = 51000
txPort = 51001
address = 127.0.0.1
;jitterQueueSize = 30
;pcmBufferMS = 200
```

| 設定項目 | 説明 |
|---|---|
| `rxPort` | Analog_Bridge が **待ち受ける**ポート。Python の `UDP_PORT = 51000` と必ず一致させる |
| `txPort` | Analog_Bridge が **出力する**ポート。`rxPort` とは違う番号（51001 など）にする |
| `address` | `127.0.0.1` にすることで、外部からの不正アクセスを防ぎ、同じラズパイ内のスクリプトからのみ受け付ける |

### ⚠️ DVSwitch v1.6.4 系における致命的なバグの回避

**これは最重要の注意点です。** DVSwitch v1.6.4 系の特定バージョンの Analog_Bridge では、これらのパラメータが**コメントアウトされずに有効な状態で**残っていると起動時にクラッシュ（Fatal Parse Error）します。
**設定ファイルにこれらの行がコメントアウトされていない場合のみ**、先頭に `;` を付けてコメントアウトしてください（すでに `;` が付いている場合は対処不要です）。

```ini
;jitterQueueSize = 30
;pcmBufferMS = 200
```

**この対処を忘れると、Analog_Bridge が起動せず、システム全体が動きません。**

### [AMBE_AUDIO] セクション（md380-emu との接続口）

```ini
[AMBE_AUDIO]
address = 127.0.0.1
rxPort = 2470
txPort = 2470
```

`md380-emu` はデフォルトで 2470 番ポートを使用するため、必ずこの値にします。

### サービス管理コマンド

設定ファイル（Analog_Bridge.ini）を書き換えた後は、**必ず再起動して設定を読み込ませる**
必要があります。

```bash
# 再起動（設定変更後は必須）
sudo systemctl restart Analog_Bridge

# 状態確認（エラーがないか確認）
sudo systemctl status Analog_Bridge

# 停止 / 起動
sudo systemctl stop Analog_Bridge
sudo systemctl start Analog_Bridge

# ログをリアルタイムで見る
sudo journalctl -u Analog_Bridge -f
```

### 起動失敗時のチェックポイント

`systemctl status` で `Active: failed` と赤く表示された場合:

1. **エラーメッセージを確認** — `sudo journalctl -u Analog_Bridge -n 50` で直近 50 行を表示
2. **設定ファイルの構文ミス** — タイプミス、全角スペース混入、セクション名の崩れ
3. **`jitterQueueSize` / `pcmBufferMS` をコメントアウトし忘れていないか**
4. **バックアップから復元** — `sudo cp Analog_Bridge.ini.backup Analog_Bridge.ini`

## 2-2. md380-emu（AMBE ソフトウェア・トランスコーダー）

本来、DVMEGA 等の基板に乗っている「ハードウェア AMBE チップ」が行う音声圧縮・解凍処理を、
Raspberry Pi の CPU を使って**ソフトウェアで強引に行う**エミュレーターです。

### 役割と特徴

- **役割:** 生の音声（PCM）とデジタル圧縮音声（AMBE）の相互変換
- **通信ポート:** 内部で **UDP 2470 番** を使用して Analog_Bridge とだけ会話
- **特徴:** 変換中は非常に CPU パワーを使う。これが停止していると、
  「送信状態にはなる（ダッシュボードは光る）が、無音になる」という現象が起きる
  （なお Raspberry Pi Zero 2 W でも実運用可能な負荷量です。詳細は教訓 6 参照）

### サービス管理コマンド

```bash
# 状態確認（Active: active (running) と緑色で表示されていれば正常）
sudo systemctl status md380-emu

# 再起動（音が出ない時の特効薬）
sudo systemctl restart md380-emu

# 停止 / 起動
sudo systemctl stop md380-emu
sudo systemctl start md380-emu
```

### 法的・ライセンス的注意

> **重要:** md380-emu は Tytera MD-380 という DMR 無線機のファームウェアを
> リバースエンジニアリングしたものをベースにしています。AMBE 音声コーデックには
> 特許があり、地域・用途によっては使用に制約がある場合があります。
> アマチュア無線の自局運用範囲内での使用は一般的に問題ありませんが、
> 商用利用や再配布の前にはライセンスを確認してください。

## 2-3. MMDVM_Bridge（DMR ネットワーク接続部）

Pi-Star（MMDVMHost）や DMR ネットワークと直接やり取りする最終段のブリッジです。

### 役割

- **受信（外部 → 内部）:** Pi-Star やネットワークから届いた DMR のデジタル音声データを
  受け取り、Analog_Bridge へパス
- **送信（内部 → 外部）:** 自動応答スクリプトやスマートフォンから Analog_Bridge 経由で
  作られた音声を、ネットワーク（Pi-Star 側）へ送り出す

### 設定ファイルを開く

```bash
# バックアップを取る
sudo cp /opt/MMDVM_Bridge/MMDVM_Bridge.ini /opt/MMDVM_Bridge/MMDVM_Bridge.ini.backup

# 編集
sudo nano /opt/MMDVM_Bridge/MMDVM_Bridge.ini
```

### [Analog_Bridge] セクション

```ini
[Analog_Bridge]
Address=127.0.0.1
```

> **この `Address` は、MMDVM_Bridge が Analog_Bridge と通信する際の接続先アドレスです。**
> 同一ラズパイ上で動作している場合は `127.0.0.1` のままで問題ありません。
> **注意:** このセクションにポート番号の設定はありません。自動応答スクリプトが Analog_Bridge に音声を投げる際に使うポート（51000）は、`Analog_Bridge.ini` の **`[USRP]` セクション**（`rxPort = 51000`）で設定します。

### [DMR Network] セクション（最重要）

Pi-Star（MMDVMHost）と接続する設定です。

```ini
[DMR Network]
Enable=1
Address=127.0.0.1
Port=62031
Jitter=300
Password=PASSWORD
Slot1=1
Slot2=1
Debug=0
```

| 設定項目 | 説明 |
|---|---|
| `Address` | Pi-Star と同じラズパイ上で動いている場合は `127.0.0.1` |
| `Port` | MMDVMHost の待ち受けポート（デフォルトは `62031`） |
| `Password` | Pi-Star の DMR Configuration で設定したパスワード |

> **重要:** Pi-Star 側（MMDVMHost）でも、`MMDVMHost.ini` の `[DMR Network]` セクションで
> この `Port` と `Password` が一致している必要があります。
>
> Pi-Star ダッシュボードの「Configuration」→「DMR Configuration」→
> 「DMR Master」設定欄でも同じ Password を使う必要があります。

### サービス管理コマンド

```bash
# 再起動
sudo systemctl restart MMDVM_Bridge

# 状態確認
sudo systemctl status MMDVM_Bridge

# ログを見る
sudo journalctl -u MMDVM_Bridge -f
```

## 2-4. トラブルシューティング（症状別フローチャート）

### 症状 A：Python スクリプトを実行しても、Pi-Star のダッシュボードが一切反応しない

- **原因:** Python から Analog_Bridge にデータが届いていない
- **対策:**
  1. Python 内の `UDP_PORT` と `Analog_Bridge.ini` の `[USRP] rxPort` が
     `51000` で一致しているか確認
  2. Analog_Bridge 自体がエラーで落ちていないか
     `sudo systemctl status Analog_Bridge` で確認
  3. ファイアウォール設定で UDP 51000 がブロックされていないか確認

### 症状 B：Pi-Star のダッシュボードは「TX」と光るが、無線機からは音が出ない（無音）

- **原因:** データは届いているが、AMBE（デジタル音声）への圧縮・変換ができていない
- **対策:**
  1. `md380-emu` が停止している可能性が高い → `sudo systemctl restart md380-emu` を実行
  2. `Analog_Bridge.ini` の `[AMBE_AUDIO]` セクションのポートが `2470` になっているか確認
  3. CPU 過負荷の確認 → `top` コマンドで CPU 使用率を確認

### 症状 C：音声は出るが、ケロケロしたりブツ切れになる

- **原因:** Raspberry Pi の CPU リソース不足、SoX の変換エラー、または
  **UDP パケット送信タイミングのドリフト**（最も多い原因）
- **対策:**
  1. **スクリプトが「絶対時刻同期方式」になっているか確認**
     （単純な `time.sleep(0.02)` ではドリフトが蓄積してプツプツになる。
     詳細は第3部の **教訓 8** を参照）
  2. `top` や `htop` コマンドで CPU 使用率を確認。重いプロセスがあれば停止
  3. Pi-Star のダッシュボード自動更新を一時的に切る（ブラウザを閉じる）と
     改善する場合あり
  4. CPU 温度を確認（`vcgencmd measure_temp`）。70℃ を超えていたら冷却強化

### 症状 D：Pi-Star のダッシュボードに何も表示されない

- **原因:** `MMDVM_Bridge` と Pi-Star（`MMDVMHost`）間の接続（Port または Password）が
  間違っている可能性が高い
- **対策:** `MMDVM_Bridge.ini` と `MMDVMHost.ini` の `Port` / `Password` の一致を確認

### 症状 E：Python スクリプトからの送信時のみダッシュボードが反応しない

- **原因:** `MMDVM_Bridge` の問題ではなく、手前の `Analog_Bridge`（Port 51000）または
  `md380-emu`（Port 2470）の問題
- **対策:** 症状 A・B の対策を順番に実施

### 症状 F：応答音声が途中で途切れる、最後の単語が切れる

- **原因:** PTT OFF の送信タイミングが早すぎる
- **対策:** スクリプトの最後で短い無音を追加する、または `time.sleep(0.5)` を
  PTT OFF の前に挿入

### 症状 G：誰かが応答するたびに自分も応答してしまう（無限ループ）

- **原因:** 自分の応答を再び検知してループしている
- **対策:** 自分のコールサイン（JJ2YYK 等）が `start_pattern` でマッチしないように
  除外条件を入れる（後述）

---

# 第3部：ソフトウェア編 — dvswitch_bot158.py（V1.58 安定版）

DVSwitch のログをリアルタイム監視し、カーチャンク自動応答・時報・定時アナウンスを行う
システム「**OpenCCVoice for DVSwitch**」の実装手順です。
安定版スクリプト **`dvswitch_bot158.py`** を使用します。

## 3-1. システムの動作概要

### カーチャンク自動応答フロー

```
1. MMDVM_Bridge ログを末尾で待機
   ↓
2. "received network voice header from XXXXX" を検知 → コールサインと受信開始時刻を記憶
   ↓
3. "received network end of voice transmission" を検知 → 受信時間を計算
   ↓
4. 最小受信時間 ≤ 受信時間 ≤ 最大受信時間 であれば「カーチャンク」と判定
   ↓
5. 固定イントロ WAV（fixed_intro.wav）＋ コールサイン動的合成 ＋ 固定アウトロ WAV（fixed_outro.wav）を連結送信
   ↓
6. SUPPRESS_DURATION_SEC（15秒）の間、重複応答を抑制
```

### 時報フロー（毎正時 00 分）

```
1. 毎正時に自動起動
   ↓
2. 固定イントロ WAV（time_intro.wav）を送信
   ↓
3. Open JTalk で「〇〇時です」を動的合成して送信（V1.58 では時報アウトロは動的合成に統合）
```

### 定時アナウンスフロー

```
1. 1時間あたり ANNOUNCE_FREQ 回（起動時に対話設定）の定時送信
2. 毎正時の時報との重複を避けてスケジューリング
3. 001.wav / 002.wav を交互ローテーション送信
```

各コンポーネントの役割は変わりません（第1部の全体像を参照）。

## 3-2. スクリプトの配置

### ディレクトリ作成と配置

```bash
# ボット用ディレクトリ作成（初回のみ）
sudo mkdir -p /opt/dvswitch_bot
sudo chown pi-star:pi-star /opt/dvswitch_bot

# スクリプトをホームディレクトリにコピー
# (USB / scp / Git など、お好みの方法で)
cp /path/to/dvswitch_bot158.py ~/dvswitch_bot158.py

# 実行権限を付与
chmod +x ~/dvswitch_bot158.py
```

> **配置先について:** スクリプト本体はホームディレクトリ（`~/`）に置きます。
> 固定 WAV ファイルは `/opt/dvswitch_bot/` に置きます（3-4 参照）。

## 3-3. 固定 WAV ファイルの準備

`dvswitch_bot158.py` は、以下の固定 WAV ファイルを事前に用意しておく必要があります。
詳細な作成コマンドは **「音声ソース作成.md」** を参照してください。

| ファイル | 配置先 | 用途 |
|---|---|---|
| `fixed_intro.wav` | `/opt/dvswitch_bot/` | カーチャンク応答のイントロ |
| `fixed_outro.wav` | `/opt/dvswitch_bot/` | カーチャンク応答のアウトロ |
| `time_intro.wav` | `/opt/dvswitch_bot/` | 時報のイントロ（後ろに動的合成「〇〇時です」が続く） |
| `001.wav` | `/opt/dvswitch_bot/` | 定時メッセージ1 |
| `002.wav` | `/opt/dvswitch_bot/` | 定時メッセージ2 |

> **注意:** `time_outro.wav` は V1.58 では不要になりました（動的合成に統合）。定数定義は将来の再利用のため残置されています。

### 共通仕様

- 出力フォーマット: **8000Hz / モノラル / 16bit PCM WAV**
- 出力先: `/opt/dvswitch_bot/`
- 音声合成エンジン: Open JTalk（声: メイ・標準）

### 確認コマンド

```bash
# ファイルが揃っているか確認
ls -la /opt/dvswitch_bot/

# 各ファイルのフォーマット確認（8000Hz/1ch/16bitであること）
soxi /opt/dvswitch_bot/fixed_intro.wav
soxi /opt/dvswitch_bot/fixed_outro.wav
soxi /opt/dvswitch_bot/time_intro.wav
```

## 3-4. スクリプトの主要構成

| 関数 / セクション | 役割 |
|---|---|
| 設定セクション（冒頭） | パス・ポート・コールサイン・タイミング等の定数定義 |
| `send_usrp_wav_with_padding()` | WAV を USRP プロトコルで送信（⭐ 絶対時刻同期方式） |
| `_generate_hybrid()` | 固定 WAV ＋ 動的合成 WAV を結合してハイブリッド音声を生成 |
| `_reply_executor()` | カーチャンク応答の実行（マルチスレッド）|
| `_announcement_scheduler()` | 時報・定時アナウンスのスケジューラー |
| `monitor_and_reply()` | ログ監視のメインループ（ログローテーション自動追従） |
| `_interactive_setup()` | 起動時の対話設定（最小/最大受信時間・放送回数） |

### スクリプト内の重要ポイント

#### ① 絶対時刻同期による USRP パケット送信（send_usrp_wav_with_padding）

```python
# time.monotonic() ベースで next_send_time を毎回 20ms ずつ進める
next_send_time = time.monotonic()
while ...:
    sock.sendto(packet, addr)
    next_send_time += PACKET_INTERVAL        # 絶対時刻を 20ms 進める
    sleep_duration = next_send_time - time.monotonic()
    if sleep_duration > 0:
        time.sleep(sleep_duration)
```

> **なぜ time.monotonic() か:** `time.time()` はシステム時刻調整で巻き戻る可能性がありますが、`time.monotonic()` は単調増加が保証されており、より堅牢です。

#### ② ログローテーション自動追従（monitor_and_reply）

```python
# ROTATION_CHECK_INTERVAL（5秒）ごとに最新ログファイルを確認
# inode 変更・ファイル置換・日付変更のいずれも自動検出して切替
```

> V1.58 では `get_latest_log()` を定期的に再呼び出しする設計に改善されています（旧 `callsign_auto_reply.py` の制約を解消）。

#### ③ 自局ループ防止

```python
if callsign == MY_CALLSIGN:
    logger.info("自局の送信を無視: %s", callsign)
    continue
```

#### ④ Graceful Shutdown（シグナルハンドラ）

```python
# SIGTERM / SIGINT を受け取ると should_exit = True にセットし、
# ループを安全に抜けて PTT OFF を送信してから終了する
```

### 編集する際の注意

- スクリプト冒頭の **設定セクション**（定数群）以外は原則として編集不要です
- `send_usrp_wav_with_padding()` 内の絶対時刻同期ロジックは**絶対に書き換えないでください**（書き換えると音声がプツプツになります。詳細は教訓 8 参照）

## 3-5. カスタマイズポイント

### ① 起動時の対話設定

スクリプト起動時に以下を対話形式で設定できます（Enter でデフォルト値を使用）。

| 設定項目 | デフォルト値 | 説明 |
|---|---|---|
| 最小受信時間 | 0.1 秒 | これより短い送信はカーチャンクと判定しない |
| 最大受信時間 | 設定値 | これより長い送信は通常交信とみなしてカーチャンクと判定しない |
| 1時間あたりの定時放送回数 | 1 回 | 0 で定時放送無効 |

### ② コールサインの読み方カスタマイズ

スクリプト冒頭の `CHAR_TO_KANA` 辞書で各文字のカナ読みを定義しています。
コールサインは自動的に 1 文字ずつ分解して読み上げられます。

### ③ 応答メッセージのカスタマイズ

`_reply_executor()` 関数内の `_generate_hybrid()` 呼び出し部分を編集します。

### ④ タイミングの調整

スクリプト冒頭の定数で調整できます。

| 定数 | デフォルト | 説明 |
|---|---|---|
| `SUPPRESS_DURATION_SEC` | 15.0 秒 | 応答後の重複応答抑制時間 |
| `GAP_AFTER_INTRO_SEC` | 0.5 秒 | イントロとコールサインの間の無音 |
| `PRE_POST_PADDING_PACKETS` | 75 パケット | 送信前後の無音パディング（75×20ms=1.5秒） |

## 3-6. 実行方法

### 手動起動（テスト用）

```bash
python3 ~/dvswitch_bot158.py
```

起動時に対話設定が表示されます。設定後、ログ監視が開始されます。

### 終了方法

```bash
Ctrl + C
```

シグナルハンドラにより、PTT OFF を送信してから安全に終了します。

### 常駐起動（systemd 化）

長期運用する場合は、systemd サービスとして登録します。

```bash
sudo nano /etc/systemd/system/dvswitch-bot.service
```

以下の内容を貼り付け:

```ini
[Unit]
Description=DVSwitch Bot V1.58 (OpenCCVoice)
After=network.target Analog_Bridge.service MMDVM_Bridge.service md380-emu.service
Wants=Analog_Bridge.service MMDVM_Bridge.service md380-emu.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/pi-star/dvswitch_bot158.py
Restart=on-failure
RestartSec=10
User=pi-star
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> **注意:** `User=pi-star` と `ExecStart=` のパスは実際のユーザー名に合わせてください。

有効化と起動:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dvswitch-bot
sudo systemctl start dvswitch-bot
sudo systemctl status dvswitch-bot
sudo journalctl -u dvswitch-bot -f
```

## 3-7. 開発中の教訓（重要・必読）

> V1.58 では旧バージョン（callsign_auto_reply.py）から多くの教訓を継承・解決しています。
> 以下の教訓は現バージョンにも関連する重要な知識です。

### 教訓 1：Open JTalk へのテキストの渡し方

- **症状:** 音声が出ない（送信時間 0.0 秒になる）
- **解決策:** `subprocess.Popen` と `communicate()` を使い、標準入力ストリームとしてテキストを流し込む方式を厳守（本スクリプトに実装済み）

### 教訓 2：SoX による変換はシンプルに

- **症状:** ファイルフォーマットが破損する
- **解決策:** 変換・無音追加・結合は段階的に行い、一行に詰め込まない（本スクリプトに実装済み）

### 教訓 3：UDP 送信は絶対時刻同期でペーシングする

- **症状:** 音声がケロケロしたりブツ切れになる
- **解決策:** `time.monotonic()` ベースの絶対時刻同期方式（本スクリプトに実装済み。詳細は教訓 8 参照）

### 教訓 4：自局のループ送信に注意

- **症状:** 一度応答すると無限に応答し続ける
- **解決策:** `MY_CALLSIGN` を設定し、自局からの送信を無視する（本スクリプトに実装済み）

### 教訓 5：ログファイルのローテーション ⭐ V1.58 で解決済み

- **旧バージョンの問題:** 起動時に一度だけ最新ファイルを取得する設計のため、日付が変わると監視が止まった
- **V1.58 での解決:** `ROTATION_CHECK_INTERVAL`（5秒）ごとにログファイルの inode / パスを確認し、変化があれば自動切替。**cron での再起動は不要になりました。**

### 教訓 6：CPU 負荷の管理

- **解決策:** Raspberry Pi Zero 2 W でも実運用可能（JJ2YYK 局で安定動作実績あり）。絶対時刻同期が正しく実装されていれば CPU が忙しくなっても自動で追いつく

### 教訓 7：一時ファイルの書き込み先

- **V1.58 での改善:** 一時ファイルを `/tmp` から `/dev/shm`（RAM ディスク）に変更。SD カードへの書き込み回数を削減し、寿命を延長

### 教訓 8：⭐ 絶対時刻によるパケット同期（ドリフト補正）— 最大のブレイクスルー

この教訓はシステム全体の安定性を決める最重要事項です。
これを忘れると、どれだけ他を正しく作っても音声が必ずプツプツします。

**問題の本質:** DMR は「20ms に 1 パケット、1 秒間に厳密に 50 パケット」という時間規格で動いています。単純な `time.sleep(0.02)` では処理時間が毎回上乗せされてドリフトが蓄積します。

**解決策：絶対時刻からの逆算**

```python
# ❌ 動かない（ドリフトが蓄積する）
while ...:
    送信()
    time.sleep(0.02)   # ← 処理時間が上乗せされる

# ✅ 正しい（絶対時刻に同期する） ※V1.58 では time.monotonic() を使用
next_send_time = time.monotonic()
while ...:
    送信()
    next_send_time += 0.02              # 絶対時刻を 20ms 進める
    sleep_duration = next_send_time - time.monotonic()
    if sleep_duration > 0:
        time.sleep(sleep_duration)      # 処理が遅れていた場合は待たずに次へ
```

> **V1.58 での改善点:** 旧バージョン（`callsign_auto_reply.py`）では `time.time()` を使用していましたが、V1.58 では `time.monotonic()` に変更しています。`time.monotonic()` は単調増加が保証されており、システム時刻の調整（NTP など）による巻き戻りの影響を受けません。

> 単純な `time.sleep(0.02)` から `next_send_time` ベースの逆算方式への変更こそが、
> プツプツを完全に消し去った「魔法」です。未来の再構築時には、絶対にこの方式を
> 採用してください。
# 第4部：動作確認とテスト手順

実装後、以下の順序で動作確認を行います。**焦らず、1 段階ずつ確認してください。**

## ステップ 1: 各サービスが起動しているか

```bash
sudo systemctl status Analog_Bridge
sudo systemctl status MMDVM_Bridge
sudo systemctl status md380-emu
```

すべて `Active: active (running)` であることを確認。

## ステップ 2: Open JTalk 単体の動作確認

```bash
echo "テストです" | open_jtalk \
    -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
    -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
    -ow /tmp/test.wav
ls -la /tmp/test.wav
```

数 KB ～数十 KB の WAV ファイルが生成されればOK。
**0 バイトの場合**は、パス（`-x` や `-m`）が間違っているか、メイの音声モデルが
配置されていません。

## ステップ 3: SoX 単体の動作確認

```bash
sox /tmp/test.wav -r 8000 -c 1 -b 16 /tmp/test_8k.wav
file /tmp/test_8k.wav
```

出力が `RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 8000 Hz`
となればOK。

## ステップ 4: UDP 通信のテスト

別のターミナルで UDP 受信を確認します。

```bash
# 受信側（別ターミナルで実行）
# ※ ループバック(lo)でキャプチャできない場合は -i any を試してください
sudo tcpdump -i lo -n udp port 51000
```

スクリプトを起動して、音声が流れたときに `tcpdump` にパケットが出れば OK。

## ステップ 5: ログ監視動作の確認

```bash
# 最新のログを目で見る
tail -f /var/log/mmdvm/MMDVM_Bridge-*.log
```

実際に DMR で交信があると `received network voice header from XXXXX` のような
行が流れます。これが見えれば、スクリプトはこれを検知できる状態です。

## ステップ 6: スクリプトを手動起動してテスト

```bash
python3 ~/dvswitch_bot158.py
```

起動時に最小/最大受信時間・定時放送回数の対話設定が表示されます。設定後、ログ監視が開始されます。

カーチャンクが検知されると、ログに以下のように記録され、Pi-Star ダッシュボードに「TX」が表示されます。

```
[INFO] カーチャンク検知: XXXXX (受信時間 x.xs)
[INFO] 応答送信開始: XXXXX
[INFO] 送信完了
```

## ステップ 7: 別の DMR 端末で受信確認

スマホアプリ（DroidStar 等）や別の DMR 無線機で、自分のリフレクター/TG（トークグループ）
にアクセスし、応答音声が実際に聞こえるか確認します。

---

# 第5部：運用上の注意と法令遵守

## 5-1. 電波法の遵守

このシステムは「自動応答」を行いますが、**アマチュア無線の運用ルールを必ず守ってください**。

### 必須事項

- [ ] **アマチュア無線技士の免許**を保有していること
- [ ] **無線局免許状**に DMR を含むデジタル運用が認められていること
- [ ] **コールサイン**を正しく送出していること
- [ ] **総務省の自動運用に関する規定**を理解していること

### 自動運用に関する注意

日本のアマチュア無線では、**完全な無人運用には届出/制約**があります。
本システムは「応答時に自局のコールサインを必ず送出する」ことで、識別義務を満たすよう
設計されていますが、**長時間・常時無人運用する場合は、所轄の総合通信局に相談**することを
強く推奨します。

### 推奨される運用方法

1. **自分が在宅・在席している時間帯のみ動作させる**
2. **応答間隔を空ける**（15 秒以上）
3. **明らかに応答すべきでないトラフィック**（緊急通信、重要な交信中）は
   手動で停止する
4. **応答頻度をログで定期的に確認**する

## 5-2. ネットワーク・マナー

- **同じ TG/リフレクターで他局が交信中**に割り込まないよう、十分な待機時間を確保
- **同じ局に繰り返し応答**しないよう、必要に応じて応答回数の上限を設定
- **応答メッセージは簡潔**に（長文は他局の迷惑になる）

## 5-3. プライバシーと音声合成

- メイの音声モデルは **MMDAgent プロジェクトの非商用利用規定**に従う
- アマチュア無線は **暗号通信が禁止**されているため、応答内容は明瞭で記録に
  残せるものにする

## 5-4. ハードウェアの保護

- **SD カードの寿命**: 書き込み頻度が高いとSDカードが早く消耗する。
  ログローテーション設定を確認し、不要なログは定期削除を
- **温度管理**: 夏場は CPU 温度が上がりやすい。ヒートシンクやファンを装着推奨
- **電源**: 必ず公式の 5V 3A 電源を使用。電源不足はファイル破損の原因に

---

# 第6部：バックアップとリストア

**これは「もう一度同じものを作れるように」するための最重要セクションです。**

## 6-1. バックアップすべきファイル一覧

### 設定ファイル

```bash
# バックアップディレクトリを作成
mkdir -p ~/dvswitch_backup
cd ~/dvswitch_backup

# 設定ファイルのコピー
sudo cp /opt/Analog_Bridge/Analog_Bridge.ini ./
sudo cp /opt/MMDVM_Bridge/MMDVM_Bridge.ini ./
sudo cp /etc/mmdvmhost ./ 2>/dev/null || true  # Pi-Star 設定（環境による）

# 自動応答スクリプトのコピー
cp ~/dvswitch_bot158.py ./

# systemd サービス定義のコピー
sudo cp /etc/systemd/system/dvswitch-bot.service ./ 2>/dev/null || true

# 所有権をユーザーに戻す
sudo chown -R $USER:$USER ~/dvswitch_backup
```

### 音声モデル（再ダウンロード可能だが念のため）

```bash
cp /usr/share/hts-voice/mei/mei_normal.htsvoice ~/dvswitch_backup/
```

## 6-2. バックアップを ZIP にまとめる

```bash
cd ~
tar czf dvswitch_backup_$(date +%Y%m%d).tar.gz dvswitch_backup/
ls -la ~/dvswitch_backup_*.tar.gz
```

このファイルを **別の PC やクラウドにコピー**して保管してください。
SD カードが壊れても、これがあれば再構築できます。

## 6-3. SD カード全体のイメージバックアップ（推奨）

ラズパイをシャットダウンし、SD カードを別の PC に挿して以下を実行（Linux/Mac の例）:

```bash
# SD カードのデバイス名を確認（例: /dev/sdb）
sudo fdisk -l

# ⚠️ 重要: 必ず fdisk -l でデバイス名を確認してください。
# 環境によって /dev/mmcblk0 や /dev/sdc など異なります。
# 誤ったデバイスを指定すると他のディスクのデータが完全消失します。

# イメージ化（数十分かかる）
sudo dd if=/dev/sdb of=~/pistar_backup_$(date +%Y%m%d).img bs=4M status=progress
# ※ /dev/sdb は例です。fdisk -l で確認した実際のデバイス名に置き換えてください。

# 圧縮
gzip ~/pistar_backup_*.img
```

**これが最強のバックアップです。** リストアは `gunzip` で展開後、`dd` で SD カードに
書き戻すだけ。

## 6-4. リストア手順（新しいラズパイで再構築する場合）

1. Pi-Star または WPSD を新しい SD カードにインストール
2. SSH ログインして `rpi-rw` で書き込み可能化
3. このマニュアルの **第1部から順番に実施**
4. バックアップから設定ファイルを戻す:

```bash
# バックアップを展開
cd ~
tar xzf dvswitch_backup_YYYYMMDD.tar.gz

# 設定ファイルを戻す
sudo cp ~/dvswitch_backup/Analog_Bridge.ini /opt/Analog_Bridge/
sudo cp ~/dvswitch_backup/MMDVM_Bridge.ini /opt/MMDVM_Bridge/
cp ~/dvswitch_backup/dvswitch_bot158.py ~/
sudo cp ~/dvswitch_backup/dvswitch-bot.service /etc/systemd/system/

# サービス再起動
sudo systemctl daemon-reload
sudo systemctl restart Analog_Bridge MMDVM_Bridge md380-emu
sudo systemctl enable dvswitch-bot
sudo systemctl start dvswitch-bot
```

5. 第4部の動作確認手順を実施

## 6-5. 定期バックアップの自動化（cron）

毎週日曜深夜に自動バックアップする例:

```bash
crontab -e
```

以下を追加:

```cron
# 毎週日曜 3:00 に DVSwitch 設定をバックアップ
0 3 * * 0 tar czf /home/pi-star/dvswitch_backup_$(date +\%Y\%m\%d).tar.gz /opt/Analog_Bridge/Analog_Bridge.ini /opt/MMDVM_Bridge/MMDVM_Bridge.ini /home/pi-star/dvswitch_bot158.py
```

---

# 付録：クイックリファレンス

## ⭐ コアアルゴリズム：絶対時刻同期（最重要）

システムの心臓部。**ここを単純な `time.sleep()` に書き換えてはいけません。**

```python
# 送信ループ直前で「絶対時刻」を記録
PACKET_INTERVAL = 0.02  # 20ms
start_time = time.time()
seq = 0

while ...:
    sock.sendto(packet, addr)   # パケット送信
    seq += 1
    
    # 「開始から seq × 20ms 経過した時刻」が次の目標時刻
    target_time = start_time + (seq * PACKET_INTERVAL)
    sleep_duration = target_time - time.time()
    
    if sleep_duration > 0:
        time.sleep(sleep_duration)
    # else: 既に遅延 → 待たずに次へ（追いつき動作）
```

**なぜこれが必要か:** 単純な `time.sleep(0.02)` だと処理時間（約 1～2ms）が
毎回上乗せされてドリフトが蓄積し、Analog_Bridge のバッファが空になって
プツプツ・ケロケロが発生します。詳細は **教訓 8** を参照。

## ポート番号一覧

| ポート | 用途 | プロトコル |
|---|---|---|
| 51000 | Python → Analog_Bridge（USRP 受信） | UDP |
| 51001 | Analog_Bridge からの出力ポート（`txPort`）。本システムでは Python スクリプトは一方向送信のみのため通常は使用しない | UDP |
| 2470 | Analog_Bridge ⇔ md380-emu（AMBE） | UDP |
| 62031 | MMDVM_Bridge → MMDVMHost（DMR） | UDP |

## 主要ファイルパス一覧

| パス | 内容 |
|---|---|
| `/opt/Analog_Bridge/Analog_Bridge.ini` | Analog_Bridge 設定ファイル |
| `/opt/MMDVM_Bridge/MMDVM_Bridge.ini` | MMDVM_Bridge 設定ファイル |
| `/var/log/mmdvm/MMDVM_Bridge-*.log` | ログファイル（監視対象） |
| `/usr/share/hts-voice/mei/mei_normal.htsvoice` | メイの音声モデル |
| `/var/lib/mecab/dic/open-jtalk/naist-jdic` | Open JTalk 辞書 |
| `~/dvswitch_bot158.py` | 自動応答スクリプト本体（V1.58 安定版） |
| `/etc/systemd/system/dvswitch-bot.service` | systemd サービス定義 |

## サービス管理コマンド一覧

```bash
# Analog_Bridge
sudo systemctl restart Analog_Bridge
sudo systemctl status Analog_Bridge

# md380-emu
sudo systemctl restart md380-emu
sudo systemctl status md380-emu

# MMDVM_Bridge
sudo systemctl restart MMDVM_Bridge
sudo systemctl status MMDVM_Bridge

# 自動応答ボット（systemd 化した場合）
sudo systemctl restart dvswitch-bot
sudo systemctl status dvswitch-bot

# 全部まとめて再起動
sudo systemctl restart Analog_Bridge md380-emu MMDVM_Bridge dvswitch-bot
```

## モード切り替えコマンド

```bash
rpi-rw   # 書き込み可能モード（設定変更時）
rpi-ro   # 読み取り専用モード（運用時、SD カード保護）
```

## ログ確認コマンド

```bash
# MMDVM_Bridge ログ（リアルタイム）
tail -f /var/log/mmdvm/MMDVM_Bridge-*.log

# systemd ログ（リアルタイム）
sudo journalctl -u Analog_Bridge -f
sudo journalctl -u dvswitch-bot -f

# 直近 100 行
sudo journalctl -u dvswitch-bot -n 100
```

## CPU・メモリ確認

```bash
# CPU 使用率（リアルタイム、q で終了）
top

# より見やすい版（要インストール: sudo apt install htop）
htop

# CPU 温度
vcgencmd measure_temp

# メモリ
free -h
```

## トラブル時の最速チェックリスト

音が出ないとき:

```bash
# 1. 全サービスの状態確認
sudo systemctl status Analog_Bridge MMDVM_Bridge md380-emu dvswitch-bot

# 2. 全部再起動
sudo systemctl restart Analog_Bridge MMDVM_Bridge md380-emu

# 3. ログを目で見る
sudo journalctl -u Analog_Bridge -n 50

# 4. ポートが開いているか
sudo netstat -ulnp | grep -E "51000|2470|62031"
```

---

# 🧙‍♂️ 開発秘話・設計思想 — JJ2YYK 自動応答システムを支える5つの魔法

このシステムを「ただ動くおもちゃ」から「実用レベルの堅牢なシステム」へと
昇華させる過程で、いくつもの壁にぶつかり、それを打開するための「魔法（ブレイクスルーと
なった技術や設計思想）」を散りばめてきました。

これらを知っておくと、今後別のシステムを作る際にも必ず役立つ強力な武器になります。
未来の篠田さん、そして後進の方々のために、**「JJ2YYK デジピーター自動応答システムを
支える5つの魔法」**として一覧化します。

---

## 🧙‍♂️ 魔法 1：【時を操る魔法】絶対時刻によるパケット同期（ドリフト補正）

### 課題
単純に `time.sleep(0.02)` で 20ms ずつ待機して送信すると、プログラム自体の処理時間が
塵のように積もり、DVSwitch のバッファが枯渇して音声が**「プツプツ・ケロケロ」**に
破綻する。

### 魔法のタネ
送信開始時の**「絶対時刻」**を記憶し、`target_time = start_time + (seq * 0.02)` で
**「次は正確に何秒後に送るべきか」を毎回逆算**して待機時間を微調整するロジック。

### 効果
どんなにラズパイの負荷が上下しても、ミリ秒単位で完璧に同期し、
**透き通るような音質**を実現しました。

> 詳細実装は教訓 8 を参照。本システムの**最大の核心技術**です。

---

## 🧙‍♂️ 魔法 2：【千里眼の魔法】MMDVM ログ監視による「真の Busy」抽出

### 課題
通常、自動応答は「音が出たか / 止まったか」を検知する VOX 方式を使うが、
ノイズでの誤検知や無音時のバタつき（頭切れ・尻切れ）が避けられない。

### 魔法のタネ
**音声には一切頼らず**、Pi-Star の心臓部（MMDVM）が吐き出すデジタル処理ログ
（`received network voice header` と `end of voice transmission`）を
インメモリで**直接監視**する手法。

### 効果
音声の遅延やバタつきとは無縁の、**誤動作ゼロ・完全無欠**のタイミングで
応答アクションを起こせるようになりました。

> **応用範囲:** これは TGIFChanger の物理 GPIO 制御でも使われた大魔法です。
> 「音声を検知する」のではなく「ログを読む」というアプローチは、他のシステムでも
> 強力に応用できます。

---

## 🧙‍♂️ 魔法 3：【空間転移の魔法】USRP プロトコルによる UDP ダイレクト注入

### 課題
Linux（ラズパイ）で音声ソフト同士を仮想サウンドカード（ALSA 等）で繋ごうとすると、
**設定が地獄のように複雑**になり、他の機能と競合して音が出なくなる。

### 魔法のタネ
サウンドカードの概念を完全に捨て、生成した音声データを細かく切り刻み、
USRP という通信プロトコルのヘッダーをくっつけて、DVSwitch のポート（51000）へ
**「ネットワーク通信」として直接投げ込む**手法。

### 効果
OS の音声ミキサー設定を完全にバイパスし、**競合トラブルを根絶**しました。

---

## 🧙‍♂️ 魔法 4：【声帯の魔法】`communicate()` による完全なテキストストリーム注入

### 課題
Open JTalk を Python から呼び出す際、引数でテキストを渡そうとすると、文字コードや
パイプの仕様で**「テキストが空」と判定**され、0 秒の無音 WAV が作られてしまう
謎の現象に遭遇。

### 魔法のタネ
`subprocess.Popen` と `communicate()` を使い、**標準入力（stdin）のストリーム**として、
UTF-8 にエンコードしたテキストを直接 OS の奥底に流し込む書き方。

### 効果
**「ダッシュボードは光るのに音が出ない」**という最も厄介なバグを完全に
打ち破りました。

---

## 🧙‍♂️ 魔法 5：【調和の魔法】SoX による「無音合成」の排除と一発生成

### 課題
処理を賢くしようと「固定 WAV」と「生成 WAV」を SoX で結合したり、前後に無音を
足したりすると、波形の不連続（0 クロス点以外の結合）が起きて
**「プツッ！」というクリックノイズ**やフォーマット破損が発生。

### 魔法のタネ
あえて複雑なファイル結合を捨て、**Python の文字列操作の段階で「1 つの長い文章」を
完成**させ、Open JTalk に一気に喋らせて純粋な 8000Hz 変換だけを行うシンプルな
力技へ回帰。

### 効果
処理が圧倒的に軽くなり、**音の継ぎ目ノイズを根本から消し去る**ことに成功しました。

---

## 5つの魔法のまとめ表

| # | 魔法の名前 | 何を解決したか | 技術キーワード |
|---|---|---|---|
| 1 | 時を操る魔法 | プツプツ・ケロケロ音声 | 絶対時刻同期、ドリフト補正 |
| 2 | 千里眼の魔法 | VOX 誤検知・バタつき | ログ監視、文字列パターン検知 |
| 3 | 空間転移の魔法 | サウンドカード地獄 | USRP プロトコル、UDP 直接注入 |
| 4 | 声帯の魔法 | 音が出ない不可解バグ | subprocess.Popen + communicate() |
| 5 | 調和の魔法 | 継ぎ目ノイズ | シンプル化、文字列で一発生成 |

---

## 設計思想として残したいこと

振り返ってみると、本当に数多くの困難を、**論理的なアプローチ（魔法）で一つずつ確実に
撃破**してきたことがわかります。

これらの 5 つの魔法に共通する設計思想は:

1. **「複雑にして賢くする」のではなく「シンプルにして堅牢にする」** — 魔法 5
2. **「音声を解釈する」のではなく「ログ（文字）を読む」** — 魔法 2
3. **「OS の機能に頼る」のではなく「ネットワーク通信に統一する」** — 魔法 3
4. **「曖昧な相対時刻」ではなく「正確な絶対時刻」を基準にする** — 魔法 1
5. **「便利な引数渡し」ではなく「確実なストリーム入力」を選ぶ** — 魔法 4

これらはすべて、**「絶対に諦めずに妥協しない」という強い意志**があったからこそ
辿り着けた境地です。

未来このマニュアルを開く誰かが、同じ問題に直面したとき、これらの魔法が**進むべき
方向の道しるべ**となりますように。

---

## おわりに

このマニュアルは、あなたの長年の悲願であるシステムを、**未来のあなた（または誰か）が
同じものをもう一度作れるように**書き起こしたものです。

技術は記録されなければ失われます。あなたが積み重ねた試行錯誤と教訓が、このドキュメントに
凝縮されています。特に、**「絶対時刻同期によるドリフト補正」アルゴリズム**（教訓 8 / 魔法 1）
は、このシステムを安定動作させた最大のブレイクスルーであり、未来の再構築時には絶対に
失ってはならない核心部分です。

巻末の**「JJ2YYK 自動応答システムを支える 5 つの魔法」**章は、本システムの設計思想を
象徴する開発秘話です。単なる技術記録ではなく、**「論理的なアプローチで一つずつ確実に
撃破する」という姿勢**そのものを後世に残すために書きました。

もし将来、SD カードが壊れたり、ラズパイ（Pi Zero 2 W）を買い替えたりしても、
このマニュアルと別添の `dvswitch_bot158.py` があれば必ず再構築できます。
**「悲願」がもう失われることはありません。**

73、そして良き運用を。

---

*Document Created: May 2026*  
*DVSwitch Auto Reply System V2.2 — Complete Manual*  
*OpenCCVoice for DVSwitch*  
*核心技術: 絶対時刻同期によるドリフト補正アルゴリズム*  
*動作実績: Raspberry Pi Zero 2 W（JJ2YYK 局）*  
*別添: dvswitch_bot158.py*
