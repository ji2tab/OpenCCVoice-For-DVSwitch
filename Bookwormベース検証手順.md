# DVSwitch + OpenCCVoice 自動音声応答システム 構築手順書（検証済み版）

**対象機:** Raspberry Pi Zero 2W
**OS:** Raspberry Pi OS (Legacy, 32-bit) Lite — Debian Bookworm ベース
**ホスト名:** OCV / **ユーザー:** ocv
**コールサイン:** JJ2YYK（DMR ID 440239652）
**接続先:** TGIF Network TG 44833
**検証日:** 2026-06-02

---

## このドキュメントの位置づけ

本書は実機 OCV 上で**実際に最後まで通した作業ログ**に基づく。各手順には次の印を付けた。

- ✅ **検証済み** — このセッションで実行し、想定どおり動作した
- ⚠️ **要注意** — 公開ドキュメントの記載と実機が食い違っていた箇所（実機の値が正）
- 🔴 **重大** — ここを外すとシステムが成立しない決定的ポイント

ユーザー名は、配布ドキュメントでは `pi-star` だが、本機は `ocv` である。以下すべて `ocv` で記載する。別ユーザーで構築する場合は読み替えること。

---

## 第0部：今回の構築で判明した「決定的な3点」

後続の手順で詳述するが、再現時に必ず意識すべき急所を先に挙げる。

1. 🔴 **md380-emu は qemu 7.2 (Bookworm標準) では SEGV で起動できない。**
   qemu-user-static を **5.2 (Bullseye版) にダウングロードし、`apt-mark hold` で固定**する必要がある。これが今回最大のハマりどころだった。

2. ⚠️ **USRP ポートは 51000 / 51001。**
   配布ドキュメントには 51000/51001 と書かれた版と 31001 単一の版が混在していたが、実際に動作した値は `rxPort = 51000` / `txPort = 51001`（Analog_Bridge 側）。ボットの送信先は **51000**。

3. ⚠️ **Open JTalk の辞書パスは `/var/lib/mecab/dic/open-jtalk/naist-jdic`。**
   配布ドキュメントの `/var/lib/mecab/dic/naist-jdic` では辞書が開けずエラーになる。

---

## 第1部：OS 準備

### 1-1. OS 書き込み・初回起動 ✅

Raspberry Pi OS (Legacy, 32-bit) Lite を書き込み、起動。SSH 等で接続する。

```bash
uname -a
# Linux OCV 6.12.x+rpt-rpi-v7 ... armv7l を確認
```

### 1-2. システム更新 ✅

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

再起動後、カーネルが更新版（本検証では 6.12.87）で立ち上がることを確認する。

---

## 第2部：DVSwitch-Server インストール

### 2-1. リポジトリ登録 ✅

```bash
cd /tmp
wget http://dvswitch.org/bookworm
cat bookworm          # 中身を確認してから実行する（GPGキー取得とリポジトリ追加のみ）
chmod +x bookworm
sudo ./bookworm
```

`Verified: Valid DVSwitch Keyring (72147EC1E788D4C3)` と
`Finished DVSwitch repository install` が出れば成功。

### 2-2. 本体インストール ✅

```bash
sudo apt install dvswitch-server -y
```

- インストール中に `Error, YSFHosts.txt file does not seem to be valid` が出るが**無害**（YSF未使用時）。
- chroot 起因の `Could not execute systemctl` も**実機起動後は問題なし**。

### 2-3. 初期設定メニュー ✅

メニューの実体は `dvswitch-menu` ではなく **`/usr/local/dvs/dvs`**。

```bash
sudo /usr/local/dvs/dvs
```

メニューに従って初期設定後、再起動する。

---

## 第3部：サービスの起動確認と修正

### 3-1. サービス一覧の確認 ✅

```bash
sudo systemctl list-units --all | grep -E "analog|mmdvm|md380|bridge|dvswitch|webproxy"
```

`dvswitch-server` という単体ユニットは**存在しない**（メタパッケージのため）。実体は `analog_bridge` / `mmdvm_bridge` / `md380-emu` / `webproxy` などのユニット群。

### 3-2. 🔴🔴 md380-emu の SEGV と qemu ダウングレード ✅

**症状:** TGIF 等から実際に信号が入り AMBE デコードが走った瞬間、
`md380-emu.service: Main process exited, code=killed, status=11/SEGV` を吐いて
auto-restart を無限に繰り返す。

**原因:** Bookworm 標準の **qemu-user-static 7.2.x** が md380-emu の ARM バイナリと非互換。
Bullseye の **qemu 5.2.x** では正常動作する（同一 Zero 2W の Bullseye 実機で実績あり）。

**対処:** Bullseye 版 qemu パッケージを公式アーカイブから取得してダウングレードする。

```bash
# 公式アーカイブから取得（他機からのコピーは不可、必ず公式から）
wget http://archive.raspbian.org/raspbian/pool/main/q/qemu/qemu-user-static_5.2+dfsg-11+deb11u5_armhf.deb -O /tmp/qemu52.deb

sudo systemctl stop md380-emu
sudo dpkg -i /tmp/qemu52.deb
# "warning: downgrading ..." は想定どおりの警告でエラーではない

# apt upgrade で 7.2 に戻らないよう固定する
sudo apt-mark hold qemu-user-static

# 念のためバイナリの実行権限を確認（立っていなければ付与）
ls -la /opt/md380-emu/md380-emu
sudo chmod +x /opt/md380-emu/md380-emu

sudo systemctl restart md380-emu
sudo systemctl status md380-emu --no-pager   # active (running) を確認

qemu-arm-static --version    # qemu-arm version 5.2.x になっていること
```

> ⚠️ **この段階での running 表示は「起動できた」ことの確認に過ぎない。**
> SEGV は実際に AMBE デコードが走ったときに発生するため、`status=11/SEGV`
> が**出ないことの最終確認は、経路が開通する第8部の送信テスト後に行う**
> （本手順書の実作業でも、SEGV が発覚したのは TGIF 接続後だった）。

> **【手順外・ドツボ記録】md380-emu の実行ビット欠落について**
> 本検証では、qemu の問題に気づく前段階で、インストール直後の
> `md380-emu` バイナリに実行ビットが立っておらず `Permission denied` で
> 起動失敗する事象に遭遇した（パッケージ側の不備と思われる）。
> ただし上記ダウングレード手順内で `chmod +x` を実施するため、
> 独立した手順としては不要。`Permission denied` が出た場合の
> 切り分け情報として記録に残す。

---

## 第4部：Web ダッシュボード

### 4-1. ⚠️ DocumentRoot の変更 ✅

初期状態では `http://<IP>/` が Apache のデフォルトページを表示する。
DVSwitch ダッシュボードの実体は **`/usr/share/dvswitch`**。

```bash
sudo sed -i 's|DocumentRoot /var/www/html|DocumentRoot /usr/share/dvswitch|' \
  /etc/apache2/sites-enabled/000-default.conf
sudo systemctl restart apache2
```

`http://<IP>/` で「DVSwitch Dashboard」が表示されれば成功。
Monit 監視画面は `http://<IP>:2812/`。

> **補足:** Zero 2W + SDカードでは初回表示が重い。`top` で `wa`(I/O待ち) が高い場合は SD のランダムアクセス遅延が主因。サービスを止めるより、まず全サービスを正常稼働させてから判断する。

---

## 第5部：音声合成環境（Open JTalk + SoX）

### 5-1. パッケージ導入 ✅

```bash
sudo apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic \
  hts-voice-nitech-jp-atr503-m001 sox
```

### 5-2. 高品質音声「メイ」導入 ✅

```bash
cd ~
wget -L --content-disposition \
  https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip

# ↓ファイル名にクエリ文字列が付くことがあるので展開時は実ファイル名を確認
ls *.zip*
unzip 'MMDAgent_Example-1.8.zip'*      # 実ファイル名に合わせる

sudo mkdir -p /usr/share/hts-voice/mei
sudo cp MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice /usr/share/hts-voice/mei/
rm -rf MMDAgent_Example-1.8 'MMDAgent_Example-1.8.zip'*
```

### 5-3. 🔴 動作確認（辞書パスに注意） ✅

⚠️ 辞書パスは **`/var/lib/mecab/dic/open-jtalk/naist-jdic`**（`open-jtalk/` を含む）。

```bash
echo "テスト、動作確認。" | open_jtalk \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -ow /tmp/test.wav && \
sox /tmp/test.wav -r 8000 -c 1 -b 16 /tmp/test_8k.wav && echo OK
```

`OK` が出れば成功。`Cannot open ... naist-jdic` が出る場合はパスが誤り。

> **なぜ `open-jtalk/` を挟むのか（エラーの原因）**
> Debian/Raspbian の `open-jtalk-mecab-naist-jdic` パッケージ（本検証では 1.11-3）は、
> 辞書を **`/var/lib/mecab/dic/open-jtalk/naist-jdic/`** に配置する（`sys.dic` 等がここにある）。
> 配布ドキュメントの `/var/lib/mecab/dic/naist-jdic`（`open-jtalk/` なし）は、
> ソースからの自前ビルドや別系統の配置を前提にした記述で、本パッケージの実配置とは
> 一階層ずれている。このため当該パスでは辞書が見つからず `Cannot open ...` となる。
> パッケージで導入する限りパスは `open-jtalk/` 入りで固定なので、実体が不明なときは
> `find /var/lib/mecab -name "sys.dic"` で確認するのが確実。

---

## 第6部：ボット本体と固定 WAV

### 6-1. ボット用ディレクトリ ✅

```bash
sudo mkdir -p /opt/dvswitch_bot
sudo chown ocv:ocv /opt/dvswitch_bot
```

### 6-2. スクリプト取得 ✅

```bash
cd ~
wget https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvswitch_bot158.py
chmod +x dvswitch_bot158.py
```

### 6-3. ⚠️ スクリプト内パラメータの確認 ✅

```bash
grep -n "UDP_IP\|UDP_PORT\|DICT_PATH" dvswitch_bot158.py
```

期待値（本検証時点の V1.58 では既定で正しかった）:

| 変数 | 正しい値 |
|---|---|
| `UDP_IP` | `127.0.0.1` |
| `UDP_PORT` | `51000` |
| `DICT_PATH` | `/var/lib/mecab/dic/open-jtalk/naist-jdic` |

`UDP_PORT` が 31001 等になっていたら 51000 に直す:

```bash
sed -i 's/UDP_PORT = 31001/UDP_PORT = 51000/' dvswitch_bot158.py
```

### 6-4. 固定 WAV 作成（対話式スクリプト） ✅

固定 WAV は GitHub の対話式スクリプトで生成する。コールサイン・地名・
定時メッセージを対話入力すると、英数字を自動でカナ変換し、5本＋
`time_outro.wav`（V1.58 未使用・無害）を一括生成する。辞書パス・音声モデル・
SoX の使い分け（単純変換／前後トリム）はスクリプト内に正しく実装されている。

```bash
cd ~
# ※リポジトリ上のファイル名が "reate_wav.sh" のため URL に注意（先頭 c 欠落の表記）
wget https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/reate_wav.sh -O create_wav.sh
chmod +x create_wav.sh
sudo ./create_wav.sh
```

対話入力の流れ:

1. コールサイン（例 `JJ2YYK`）→ 自動カナ変換結果を確認・修正（`ジェイジェイツーワイワイケー`）
2. 設置場所の地名（例 `おわりあさひ`。漢字を入れると Open JTalk の読みに依存するため、確実に読ませたい場合はひらがな推奨）
3. 定時メッセージ1 → カナ確認・修正
4. 定時メッセージ2 → カナ確認・修正
5. 確認プロンプトで `Y`

> **生成される文面について（検証範囲の注記）**
> このセッションで TGIF 送信成功まで確認したのは、後述の「個別コマンド版」で
> 作った WAV である。スクリプト版は 001/002 が
> `こちらは、(コールサイン)、(地名) ディーエムアール デジピーターです。(メッセージ)`
> という固定構造で組み立てられ、読点やカナが個別コマンド版と完全一致はしない。
> 音声フォーマット（8kHz/mono/16bit）と経路は同一なので動作に支障はないが、
> 読み上げの「文面」は入力値で変わる点に留意する。
> 「TGIF44833」のような英数字は自動変換で読点が入らないため、確認プロンプトの
> `read -i` 編集で読点（例: `ヨンヨンハチサンサン`）を整えるとよい。

確認:

```bash
ls -la /opt/dvswitch_bot/
soxi /opt/dvswitch_bot/*.wav    # 全ファイル 8000Hz / 1ch / 16-bit を確認
```

> **SoX 2パターンの使い分け（スクリプト内の実装）**
> - **単純変換**（`fixed_intro` / `fixed_outro` / `time_outro`）: 他音声と連結されるため末尾無音は許容。ボット側で 0.5 秒の無音を別途付加する。
> - **前後トリム**（`time_intro` / `001` / `002`）: `silence 1 0.1 1% reverse` を 2 回適用し前後無音を除去。単独再生・動的合成連結時の「間」を一定にする。

> 個別コマンドで手動生成する方法（このセッションで TGIF 送信まで検証した文面）は **付録C** に掲載。

---

## 第7部：DVSwitch 側の経路・TG 設定

音声の流れ:
**ボット → (USRP 51000) → Analog_Bridge → (TLV) → MMDVM_Bridge → TGIF**

### 7-1. ⚠️ Analog_Bridge.ini（USRP / 送信 TG） ✅

`/opt/Analog_Bridge/Analog_Bridge.ini`

```ini
[USRP]
address = 127.0.0.1
txPort = 51001        ; Analog_Bridge → 外部（USRP送信）
rxPort = 51000        ; 外部 → Analog_Bridge（ボットはここへ送る）
```

🔴 `[AMBE_AUDIO]` セクションの送信 TG:

```ini
[AMBE_AUDIO]
txTg = 44833          ; ★ボット音声が乗る DMR TG（最重要）
txTs = 2
colorCode = 1
```

> **補足（未反映・要検討）:** `gatewayDmrId` / `repeaterID` がデフォルト値
> （4401378 / 440137811）のままだった。JJ2YYK 運用に厳密に合わせるなら
> 4402396 / 440239652 への変更を検討する。本検証では変更せず送信成功している。

### 7-2. DVSwitch.ini（DMR exportTG） ✅

`/opt/MMDVM_Bridge/DVSwitch.ini` の `[DMR]`:

```ini
[DMR]
address = 127.0.0.1
exportTG = 44833      ; ★エクスポート TG を 44833 に
```

### 7-3. 設定反映 ✅

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
```

> **TGIF が 4000 に戻る件:** TGIF Network 側のダッシュボードで TG を指定しても、
> Static 設定がないと一定時間でデフォルト（4000）へ戻る。
> 送信側（ローカル）の TG は `txTg` / `exportTG` = 44833 で決まる。
> 受信を継続したい場合は TGIF ダッシュボードで 44833 を Static 登録すること。

---

## 第8部：送信テスト

### 8-1. テスト送信ツール取得 ✅

`test_send.py` を GitHub から取得する。USRP プロトコルで前後 1.5 秒パディングを
付けて WAV を単発送信するツール。

```bash
cd ~
wget https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/test_send.py
```

主要パラメータ（取得後に確認。本検証時点では既定で正しかった）:

```python
UDP_IP = "127.0.0.1"
UDP_PORT = 51000
PACKET_INTERVAL = 0.02            # 20ms
PRE_POST_PADDING_PACKETS = 75     # 前後 1.5 秒の無音
```

### 8-2. 実行 ✅

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
sleep 3
python3 ~/test_send.py /opt/dvswitch_bot/001.wav
```

TGIF TG 44833 で音声が出れば**経路開通**。本検証ではここまで成功を確認した。

> bot 本体が常駐している場合は二重送信になるため、テスト時は bot を停止する。

### 8-3. 🔴 md380-emu SEGV の最終確認 ✅

第3-3部でダウングレードした qemu の効果を、ここで**実際のデコードを走らせて確定**する。
この送信テスト（および TGIF から実信号を受けたとき）に
`md380-emu.service: ... status=11/SEGV` が**出ないこと**を確認する。

```bash
sudo journalctl -u md380-emu -n 20 --no-pager   # SEGV が出ていないこと
sudo systemctl status md380-emu --no-pager       # active (running) のまま
```

SEGV が再発する場合は qemu が 7.2 に戻っていないか確認する
（`qemu-arm-static --version` が 5.2.x、`apt-mark` で hold 済みか）。

---

## 第9部：常駐化（systemd）※未実行

本検証ではここまで未着手。手順のみ記載する。

```bash
sudo nano /etc/systemd/system/dvswitch-bot.service
```

```ini
[Unit]
Description=DVSwitch Bot V1.58 (OpenCCVoice)
After=network.target analog_bridge.service mmdvm_bridge.service md380-emu.service
Wants=analog_bridge.service mmdvm_bridge.service md380-emu.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/ocv/dvswitch_bot158.py
Restart=on-failure
RestartSec=10
User=ocv
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable dvswitch-bot
sudo systemctl start dvswitch-bot
sudo systemctl status dvswitch-bot
```

> 常駐化の前に、まず `python3 ~/dvswitch_bot158.py` を手動起動して
> カーチャンク検知・定時放送の動作を対話設定込みで確認することを推奨する。

---

## 付録A：今回の修正点まとめ（配布ドキュメント vs 実機）

| 項目 | 配布ドキュメント | 実機（正） | 印 |
|---|---|---|---|
| ユーザー名 | pi-star | ocv | ⚠️ |
| メニューコマンド | dvswitch-menu | /usr/local/dvs/dvs | ⚠️ |
| USRP rxPort | 51000 / 31001 混在 | 51000 | ⚠️ |
| USRP txPort | 51001 / 31001 混在 | 51001 | ⚠️ |
| ボット UDP_PORT | 51000 | 51000 | ✅ |
| Open JTalk 辞書 | /var/lib/mecab/dic/naist-jdic | /var/lib/mecab/dic/open-jtalk/naist-jdic | ⚠️ |
| md380-emu 実行権限 | （記載なし） | chmod +x（ダウングレード手順に統合） | ⚠️ |
| qemu-user-static | （記載なし） | 5.2 へダウングレード＋hold | 🔴 |
| Apache DocumentRoot | （記載なし） | /usr/share/dvswitch | ⚠️ |
| 送信 TG | （環境依存） | txTg / exportTG = 44833 | 🔴 |

## 付録B：トラブルシューティング早見表

| 症状 | 原因 | 対処 |
|---|---|---|
| md380-emu が `Permission denied` | 実行ビット無し | `sudo chmod +x /opt/md380-emu/md380-emu` |
| md380-emu が `status=11/SEGV` を繰り返す | qemu 7.2 非互換 | qemu 5.2 へダウングレード＋`apt-mark hold` |
| Open JTalk が `Cannot open ... naist-jdic` | 辞書パス誤り | `/var/lib/mecab/dic/open-jtalk/naist-jdic` を使う |
| `http://<IP>/` が Apache 既定ページ | DocumentRoot 未変更 | `/usr/share/dvswitch` に変更 |
| 音声は出るが TG が 4000 に戻る | TGIF 側 Static 未設定 | TGIF ダッシュボードで 44833 を Static 登録 |
| ボット音声が無音 | md380-emu 停止 or Analog_Bridge 設定 | md380-emu 稼働確認、USRP ポート確認 |

## 付録C：固定 WAV の個別コマンド生成（検証済み文面）

第6-4部は対話式スクリプト（`create_wav.sh`）での生成を本手順とした。
ここでは、スクリプトを使わず手動で作る場合、または**このセッションで
TGIF 送信まで検証した文面**をそのまま再現したい場合のコマンドを掲載する。

辞書パス・音声モデルは第5部と同じ。各ファイルは 8kHz / mono / 16bit PCM。
`fixed_*` は単純変換、`time_intro` / `001` / `002` は前後トリム付き。

```bash
# fixed_intro.wav（カーチャンク応答イントロ）
echo "こちらは、ジェイジェイツーワイワイケー、おわりあさひ ディーエムアール デジピーターです。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/temp_intro.wav && sudo sox /tmp/temp_intro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/fixed_intro.wav

# fixed_outro.wav（カーチャンク応答アウトロ）
echo "カーチャンクです。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/temp_outro.wav && sudo sox /tmp/temp_outro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/fixed_outro.wav

# time_intro.wav（時報イントロ・前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/time_intro.wav && sox /tmp/time_intro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/time_intro.wav silence 1 0.1 1% reverse silence 1 0.1 1% reverse

# 001.wav（定時メッセージ1・前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。オープン、シーシーヴォイス、フォー、ディーブイスイッチからの音声です。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/001_raw.wav && sox /tmp/001_raw.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/001.wav silence 1 0.1 1% reverse silence 1 0.1 1% reverse

# 002.wav（定時メッセージ2・前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。ティージーアイエフ、ヨンヨンハチサンサンと、インターネット接続しています。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/002_raw.wav && sox /tmp/002_raw.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/002.wav silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

確認:

```bash
ls -la /opt/dvswitch_bot/
soxi /opt/dvswitch_bot/*.wav    # 全ファイル 8000Hz / 1ch / 16-bit を確認
```

---

*作成: 2026-06-02 / 対応 bot: dvswitch_bot158.py V1.58 / 実機: OCV (Zero 2W, Bookworm 32-bit)*
