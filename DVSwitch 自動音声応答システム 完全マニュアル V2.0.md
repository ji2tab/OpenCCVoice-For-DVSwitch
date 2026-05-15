# DVSwitch 自動音声応答システム 完全マニュアル V2.0

> **このマニュアルについて**
>
> Pi-Star / WPSD 環境において、DVSwitch（Analog_Bridge）と Python スクリプトを連携させ、
> DMR ネットワーク上の交信終了を検知して自動で音声アナウンス（デジピーター応答）を
> 送出するシステムの構築・運用マニュアルです。
>
> **初めて読む方でも、このマニュアル1冊で同じシステムを再現できる**ことを目標に、
> 専門用語の解説、注意点、トラブル時の対処法を可能な限り盛り込んでいます。

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

---

# はじめに

## このシステムで何ができるのか

このシステムを構築すると、以下のことが自動で行えます。

1. DMR ネットワーク上で誰かが交信を行う
2. 交信が終わると、システムが自動で検知
3. 15 秒待機（交信の衝突回避）
4. 「**JA1XXX、こちらは JJ2YYK、尾張旭、DMR デジピーターです**」のように
   相手のコールサインを呼びかけて応答する

これは**ハム無線界における「電子的な応答機」**であり、デジピーター（自動中継局）
としての存在証明にもなります。

## 必要なもの一覧

### ハードウェア
- **Raspberry Pi 3B+ 以上**（4 / 5 推奨、CPU負荷が高いため）
- **microSD カード**（16GB 以上、Class 10 推奨）
- **電源アダプタ**（公式の 5V 3A 推奨）
- **MMDVM ホットスポット基板**（DVMEGA、ZUMspot、JumboSPOT 等）
- **インターネット接続**（有線 LAN または Wi-Fi）

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
│ (callsign_auto_reply)│
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
2. **SoX**: Open JTalk が作った高品質な音声（48000Hz）を、DMR の規格（8000Hz）に
   劣化なく、かつ一瞬で正確に変換するために必須のツールです。

> **初心者向け解説:** 「外部 API を使わない」のは、インターネット遅延や障害の影響を
> 受けないため、そして個人情報を外部に送らないためです。**完全にローカル完結**します。

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
wget https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip

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

**これは最重要の注意点です。** 特定バージョンの Analog_Bridge では、設定ファイルに以下の
パラメータが残っていると起動時にクラッシュ（Fatal Parse Error）します。
**必ず先頭に `;` を付けてコメントアウト**してください。

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

自動応答システムの音声は `Analog_Bridge`（51000 番ポート）へ直接投げるため、
ここのポート番号は変更しなくても大丈夫です。

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

- **原因:** Raspberry Pi の CPU リソース不足、または SoX の変換エラー
- **対策:**
  1. `top` や `htop` コマンドで CPU 使用率を確認。重いプロセスがあれば停止
  2. Python スクリプト側の `time.sleep(0.02)`（20ms のウェイト）が正しく機能しているか確認
     （一気にデータを流し込むと Analog_Bridge がパンクする）
  3. Pi-Star のダッシュボード自動更新を一時的に切る（ブラウザを閉じる）と改善する場合あり

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

# 第3部：ソフトウェア編 — OpenCCVoice for DVSwitch

DVSwitch のログをリアルタイム監視し、受信したコールサインを正確に読み上げて自動応答する
システム「**OpenCCVoice for DVSwitch**」の実装手順です。

## 3-1. システムの動作概要

```
1. ログファイルを開いて末尾で待機
   ↓
2. "received network voice header from XXXXX" を検知
   → コールサイン XXXXX を記憶
   ↓
3. "received network end of voice transmission" を検知
   → 受信終了を確認
   ↓
4. 15秒待機（交信の衝突回避）
   ↓
5. 「XXXXX。こちらは、JJ2YYK、尾張旭、DMR、デジピーターです。」を生成
   ↓
6. Open JTalk でテキストを WAV 化（48000Hz）
   ↓
7. SoX で 8000Hz / モノラル / 16bit に変換
   ↓
8. USRP プロトコル（UDP 51000）で Analog_Bridge に送信
   ↓
9. 記憶をリセットして 1 に戻る
```

## 3-2. スクリプトの配置

```bash
# ホームディレクトリに作成
cd ~
nano callsign_auto_reply.py
```

## 3-3. スクリプト本体

以下の内容を貼り付けて保存してください。**コメント部分も含めて、すべてコピーしても問題ありません。**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenCCVoice for DVSwitch V1.0
DMR ログを監視し、コールサインを読み上げて自動応答するシステム
"""

import os
import time
import glob
import re
import socket
import struct
import wave
import subprocess

# ==========================================
# システム設定（環境に合わせて変更）
# ==========================================
LOG_DIR = "/var/log/mmdvm"           # MMDVM のログディレクトリ
LOG_PATTERN = "MMDVM_Bridge-*.log"   # 監視対象のログファイル名
UDP_IP = "127.0.0.1"                 # Analog_Bridge の IP
UDP_PORT = 51000                     # Analog_Bridge の rxPort

# Open JTalk のパス設定
DICT_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"
TEMP_WAV_48K = "/tmp/reply_48k.wav"
TEMP_WAV_8K = "/tmp/reply_8k.wav"

# 自局コールサイン（無限ループ防止のため、自分の応答は無視する）
MY_CALLSIGN = "JJ2YYK"

# 応答待機時間（秒）— 交信の衝突回避のため
RESPONSE_DELAY = 15.0

# 📖 読み替え辞書（コールサインを正しく英語読みさせるための設定）
USER_DICT = {
    "JJ2YYK": "ジェイ、ジェイ、ツー、ワイ、ワイ、ケー",
    "JI2TAB": "ジェイ、アイ、ツー、ティー、エー、ビー",
    "JR2DHR": "ジェイ、アール、ツー、ディー、エイチ、アール",
    # ↓ 新しいコールサインはここに追加
}


def get_latest_log():
    """最新のログファイルを見つけて返す"""
    files = glob.glob(os.path.join(LOG_DIR, LOG_PATTERN))
    if not files:
        standard_log = os.path.join(LOG_DIR, "MMDVM_Bridge.log")
        return standard_log if os.path.exists(standard_log) else None
    return max(files, key=os.path.getctime)


def talk(raw_text):
    """テキストを音声に変換し、USRP プロトコルで DVSwitch に送信する"""
    text = raw_text
    # 辞書の適用（コールサインをカナ読みに置換）
    for key, value in USER_DICT.items():
        text = text.replace(key, value)

    print(f"🎙️  発話準備: {text}")

    # 1. Open JTalk で音声生成（communicate 方式で標準入力から確実に渡す）
    cmd_jtalk = [
        "open_jtalk",
        "-x", DICT_PATH,
        "-m", VOICE_PATH,
        "-p", "1.1",     # ピッチ（声の高さ）
        "-r", "1.0",     # スピード
        "-ow", TEMP_WAV_48K,
    ]
    process = subprocess.Popen(cmd_jtalk, stdin=subprocess.PIPE)
    process.communicate(text.encode("utf-8"))

    # 2. SoX で 8000Hz モノラル 16bit に変換（DMR の規格に合わせる）
    subprocess.run([
        "sox", TEMP_WAV_48K,
        "-r", "8000", "-c", "1", "-b", "16",
        TEMP_WAV_8K,
    ])

    # 3. UDP ソケット通信で送信
    if not os.path.exists(TEMP_WAV_8K):
        print("❌ 音声ファイルの生成に失敗しました")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    wf = wave.open(TEMP_WAV_8K, "rb")
    seq = 0
    try:
        while True:
            data = wf.readframes(160)  # 20ms ごとの細切れデータ
            if len(data) == 0:
                break
            if len(data) < 320:
                data += b"\x00" * (320 - len(data))  # パディング

            # USRP ヘッダー（PTT ON: 1）を付与して送信
            header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 1, 0, 0, 0, 0)
            sock.sendto(header + data, (UDP_IP, UDP_PORT))
            seq += 1
            time.sleep(0.02)  # 20ms 待機（重要）
    finally:
        # USRP ヘッダー（PTT OFF: 0）を送信して通信終了
        header = struct.pack("!4sIIIIIII", b"USRP", seq, 0, 0, 0, 0, 0, 0)
        sock.sendto(header + b"\x00" * 320, (UDP_IP, UDP_PORT))
        wf.close()
        sock.close()

        # 使用した一時ファイルの削除
        if os.path.exists(TEMP_WAV_48K):
            os.remove(TEMP_WAV_48K)
        if os.path.exists(TEMP_WAV_8K):
            os.remove(TEMP_WAV_8K)
    print("✅ 送信完了")


def monitor_and_reply():
    """ログを監視し、通話終了を検知して応答アクションを起こす"""
    current_file = get_latest_log()
    if not current_file:
        print("❌ ログが見つかりません")
        return

    print(f"👀 OpenCCVoice for DVSwitch V1.0 待機中: {current_file}")
    print(f"📡 自局: {MY_CALLSIGN} | 応答待機時間: {RESPONSE_DELAY}秒")

    # 監視するログの文字列パターン
    start_pattern = re.compile(r"received network voice header from ([A-Z0-9\-]+)")
    end_pattern = re.compile(r"received network end of voice transmission")

    last_detected_callsign = None

    try:
        with open(current_file, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)  # ファイルの末尾に移動（過去のログは無視）
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                # ① 受信開始の検知（コールサインを記憶）
                start_match = start_pattern.search(line)
                if start_match:
                    callsign = start_match.group(1)
                    # 自局の応答は無視（無限ループ防止）
                    if callsign == MY_CALLSIGN:
                        print(f"⏭️  自局の送信を無視: {callsign}")
                        continue
                    last_detected_callsign = callsign
                    print(f"▶️  受信中: {last_detected_callsign}")

                # ② 受信終了の検知
                if end_pattern.search(line):
                    if last_detected_callsign:
                        print(f"⏹️  受信終了 -> {RESPONSE_DELAY}秒後に "
                              f"{last_detected_callsign} へ返信します")

                        # 交信の衝突を避けるための待機
                        time.sleep(RESPONSE_DELAY)

                        # 応答メッセージの生成と送信
                        msg = (f"{last_detected_callsign}。こちらは、{MY_CALLSIGN}、"
                               f"尾張旭、DMR、デジピーターです。")
                        talk(msg)

                        # 応答が完了したら記憶をリセット
                        last_detected_callsign = None

    except KeyboardInterrupt:
        print("\n🛑 システムを終了します")


if __name__ == "__main__":
    monitor_and_reply()
```

## 3-4. カスタマイズポイント

### ① 読み替え辞書（USER_DICT）の追加

新しいコールサインを正しく読ませるには、`USER_DICT` に追加します。

```python
USER_DICT = {
    "JJ2YYK": "ジェイ、ジェイ、ツー、ワイ、ワイ、ケー",
    "JI2TAB": "ジェイ、アイ、ツー、ティー、エー、ビー",
    "JR2DHR": "ジェイ、アール、ツー、ディー、エイチ、アール",
    "JA1XXX": "ジェイ、エー、ワン、エックス、エックス、エックス",  # 追加例
}
```

> **コツ:** 読点（、）を間に入れることで、音声合成エンジンが「区切って」読んでくれます。
> 区切らないと「ジジツーワイワイケー」と早口になってしまいます。

### ② 応答メッセージのカスタマイズ

`monitor_and_reply()` 関数内の以下の行を編集します。

```python
msg = (f"{last_detected_callsign}。こちらは、{MY_CALLSIGN}、"
       f"尾張旭、DMR、デジピーターです。")
```

例:
```python
# よりフォーマルに
msg = (f"{last_detected_callsign}局、応答ありがとうございます。"
       f"こちらは{MY_CALLSIGN}、尾張旭の自動応答機です。")

# 時刻を入れる
import datetime
now = datetime.datetime.now().strftime("%H時%M分")
msg = (f"{last_detected_callsign}。こちらは{MY_CALLSIGN}、"
       f"現在の時刻は{now}です。")
```

### ③ 応答待機時間の調整

```python
RESPONSE_DELAY = 15.0  # 必要に応じて 10.0 ～ 20.0 で調整
```

| 待機時間 | 用途 |
|---|---|
| 5 ～ 10 秒 | 即応性重視（衝突リスクあり） |
| 15 秒 | バランス型（推奨） |
| 20 ～ 30 秒 | 衝突回避優先 |

### ④ 音声パラメータの調整

`talk()` 関数内の Open JTalk コマンドで調整可能です。

| パラメータ | 意味 | 推奨範囲 | 例 |
|---|---|---|---|
| `-p 1.1` | ピッチ（声の高さ） | 0.8 ～ 1.3 | `-p 1.2` で少し高め |
| `-r 1.0` | スピード | 0.85 ～ 1.2 | `-r 0.9` でゆっくり |
| `-fm 0` | 抑揚 | -1.0 ～ 1.5 | `-fm 1.5` で抑揚強め |
| `-jf 1.0` | 音量倍率 | 0.5 ～ 2.0 | `-jf 1.5` で大きめ |

## 3-5. 実行方法

### 手動起動（テスト用）

```bash
python3 ~/callsign_auto_reply.py
```

画面にログが表示されます。無線機で実際に交信を行ってテストできます。

### 終了方法

```
Ctrl + C
```

### 常駐起動（systemd 化）

長期運用する場合は、systemd サービスとして登録します。これにより:

- ラズパイ起動時に自動で開始
- エラー時に自動再起動
- バックグラウンドで動作

```bash
sudo nano /etc/systemd/system/callsign-bot.service
```

以下の内容を貼り付け。

```ini
[Unit]
Description=DVSwitch Callsign Auto Reply Bot (OpenCCVoice)
After=network.target Analog_Bridge.service MMDVM_Bridge.service md380-emu.service
Wants=Analog_Bridge.service MMDVM_Bridge.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/pi-star/callsign_auto_reply.py
Restart=on-failure
RestartSec=10
User=pi-star
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> **注意:** `User=pi-star` と `ExecStart=` のパス（`/home/pi-star/...`）は、
> 実際のユーザー名に合わせて変更してください。WPSD では `WPSD` 等の場合があります。

有効化と起動:

```bash
# systemd に変更を読み込ませる
sudo systemctl daemon-reload

# 自動起動を有効化（起動時に開始する）
sudo systemctl enable callsign-bot

# 今すぐ起動
sudo systemctl start callsign-bot

# 状態確認
sudo systemctl status callsign-bot

# ログを見る
sudo journalctl -u callsign-bot -f
```

## 3-6. 開発中の教訓（重要・必読）

### 教訓 1：Open JTalk への文字列の渡し方

- **症状:** 音声が出ない（送信時間 0.0 秒になる）
- **原因:** `subprocess.run(input=...)` でテキストを渡そうとした際、処理がすっぽ抜けて
  「空のテキスト」が渡り、0 バイトの WAV ファイルが作られた
- **解決策:** `subprocess.Popen` と `communicate()` を使い、標準入力ストリームとして
  直接テキストを確実に流し込む方式（本スクリプトの方式）を厳守すること

```python
# ❌ 動かないパターン
subprocess.run(["open_jtalk", ...], input=text.encode("utf-8"))

# ✅ 動くパターン（本スクリプトの方式）
process = subprocess.Popen(["open_jtalk", ...], stdin=subprocess.PIPE)
process.communicate(text.encode("utf-8"))
```

### 教訓 2：SoX による変換は段階的に行う

- **症状:** ファイルフォーマットが破損する
- **原因:** 変換と無音追加を同時に 1 行のコマンドで行おうとした
- **教訓:** システムを安定稼働させるためには、スクリプトの処理は極力シンプルにする
  （純粋な音声化とフォーマット変換のみ行う）のが鉄則

### 教訓 3：UDP 送信は 20ms ごとにペーシングする

- **症状:** 音声がケロケロしたりブツ切れになる
- **原因:** 一気にデータを流し込むと Analog_Bridge がパンクする
- **解決策:** `time.sleep(0.02)` で 1 パケット 20ms のペースを厳守する

### 教訓 4：自局のループ送信に注意

- **症状:** 一度応答すると、無限に応答し続ける
- **原因:** 自分の応答音声が DMR ネットワークを経由して再び自分のログに記録され、
  それを「新しい交信」として再応答してしまう
- **解決策:** `MY_CALLSIGN` 定数を設定し、自局からの送信は無視する処理を入れる
  （本スクリプトに実装済み）

### 教訓 5：ログファイルのローテーション

- **症状:** 数日後に動かなくなる
- **原因:** MMDVM_Bridge のログは日付ごとに別ファイルになる（例:
  `MMDVM_Bridge-2026-05-15.log`）。古いファイルを監視し続けると更新されない
- **解決策:** `get_latest_log()` で最新ファイルを毎回取得する設計にする
  （本スクリプトに実装済み）。ただし、**起動中に日付が変わった場合**は再起動が必要。
  対策として `cron` で毎日深夜にサービスを再起動するのも有効。

### 教訓 6：CPU 負荷の管理

- **症状:** 音声が遅延する、ケロケロする
- **原因:** md380-emu と Pi-Star の MMDVM 処理が同時に動くと CPU が逼迫する
- **解決策:**
  - Raspberry Pi 4 以上を使う（Pi 3B+ では限界がある）
  - 冷却を強化する（CPU 温度が 70℃ を超えると性能低下）
  - 不要なプロセスを停止する

### 教訓 7：ファイルパスのハードコーディング

- **症状:** 別のラズパイに移したら動かない
- **原因:** ユーザー名（pi-star / WPSD）やパスが環境によって異なる
- **解決策:** スクリプト上部の設定セクションで一元管理し、移植時はそこだけ変更すれば
  済むようにする（本スクリプトもそのように設計）

---

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
python3 ~/callsign_auto_reply.py
```

画面に `👀 OpenCCVoice for DVSwitch V1.0 待機中` と出れば起動成功。

別の DMR 局が交信を終了すると:
1. `▶️ 受信中: XXXXX`
2. `⏹️ 受信終了 -> 15秒後に XXXXX へ返信します`
3. （15 秒経過）
4. `🎙️ 発話準備: ...`
5. `✅ 送信完了`

の順で表示され、Pi-Star ダッシュボードに「TX」が表示されます。

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
cp ~/callsign_auto_reply.py ./

# systemd サービス定義のコピー
sudo cp /etc/systemd/system/callsign-bot.service ./ 2>/dev/null || true

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

# イメージ化（数十分かかる）
sudo dd if=/dev/sdb of=~/pistar_backup_$(date +%Y%m%d).img bs=4M status=progress

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
cp ~/dvswitch_backup/callsign_auto_reply.py ~/
sudo cp ~/dvswitch_backup/callsign-bot.service /etc/systemd/system/

# サービス再起動
sudo systemctl daemon-reload
sudo systemctl restart Analog_Bridge MMDVM_Bridge md380-emu
sudo systemctl enable callsign-bot
sudo systemctl start callsign-bot
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
0 3 * * 0 tar czf /home/pi-star/dvswitch_backup_$(date +\%Y\%m\%d).tar.gz /opt/Analog_Bridge/Analog_Bridge.ini /opt/MMDVM_Bridge/MMDVM_Bridge.ini /home/pi-star/callsign_auto_reply.py
```

---

# 付録：クイックリファレンス

## ポート番号一覧

| ポート | 用途 | プロトコル |
|---|---|---|
| 51000 | Python → Analog_Bridge（USRP 受信） | UDP |
| 51001 | Analog_Bridge → Python（USRP 送信） | UDP |
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
| `~/callsign_auto_reply.py` | 自動応答スクリプト本体 |
| `/etc/systemd/system/callsign-bot.service` | systemd サービス定義 |

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
sudo systemctl restart callsign-bot
sudo systemctl status callsign-bot

# 全部まとめて再起動
sudo systemctl restart Analog_Bridge md380-emu MMDVM_Bridge callsign-bot
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
sudo journalctl -u callsign-bot -f

# 直近 100 行
sudo journalctl -u callsign-bot -n 100
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
sudo systemctl status Analog_Bridge MMDVM_Bridge md380-emu callsign-bot

# 2. 全部再起動
sudo systemctl restart Analog_Bridge MMDVM_Bridge md380-emu

# 3. ログを目で見る
sudo journalctl -u Analog_Bridge -n 50

# 4. ポートが開いているか
sudo netstat -ulnp | grep -E "51000|2470|62031"
```

---

## おわりに

このマニュアルは、あなたの長年の悲願であるシステムを、**未来のあなた（または誰か）が
同じものをもう一度作れるように**書き起こしたものです。

技術は記録されなければ失われます。あなたが積み重ねた試行錯誤と教訓が、このドキュメントに
凝縮されています。

もし将来、SD カードが壊れたり、ラズパイを買い替えたりしても、このマニュアルがあれば
必ず再構築できます。**「悲願」がもう失われることはありません。**

73、そして良き運用を。

---

*Document Created: May 2026*  
*DVSwitch Auto Reply System V2.0 — Complete Manual*  
*OpenCCVoice for DVSwitch*
