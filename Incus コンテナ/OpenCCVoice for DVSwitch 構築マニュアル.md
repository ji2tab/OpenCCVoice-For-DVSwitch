# OpenCCVoice for DVSwitch 構築マニュアル
**Incus コンテナ（Debian 12 / amd64）版**

---

> **このマニュアルの位置づけ**
>
> 原本『OpenCCVoice for DVSwitch 構築・導入・設定 完全マニュアル』（Raspberry Pi OS Bookworm / armhf 実機版）を、
> **Incus コンテナ上の Debian 12 Bookworm（amd64）環境**で再現するための差分・実務マニュアルです。
>
> 原本と手順が同一の章は簡潔に触れるにとどめ、**コンテナ環境特有の作業・詰まりどころ**を重点的に記載します。
> 実機（ホスト名 ocv、Ubuntu 24.04 上の Incus）で検証済みの手順に基づきます。
>
> **対象構成:**
> - ホスト: Ubuntu 24.04 LTS（amd64）+ Incus 6.0.0
> - コンテナ: Debian 12 Bookworm（amd64、`images:debian/12` で作成）
> - ユーザー: `ocv`
> - ネットワーク: macvlan（物理LAN直結）+ 固定IP
> - Bot: `dvswitch_bot.py`（デーモン本体）＋ `bot_setup.py`（設定ツール）

**凡例:** ✅ 検証済み ／ ⚠️ 要注意（実機の値が正） ／ 🔴 重大（外すと成立しない） ／ 🆕 原本にないコンテナ固有の手順

---

## 目次

### 第1章：前提・原本との違い
- [1. アーキテクチャ上の重要な前提](#1-アーキテクチャ上の重要な前提)
- [2. 原本マニュアルとの対比表](#2-原本マニュアルとの対比表)

### 第2章：コンテナ作成とネットワーク
- [3. Incusコンテナの作成](#3-incusコンテナの作成)
- [4. 🆕 ネットワーク（macvlan固定IP）](#4-ネットワークmacvlan固定ip)
- [5. 🆕 SSHアクセスの設定](#5-sshアクセスの設定)

### 第3章：DVSwitch-Server
- [6. DVSwitch-Serverインストール](#6-dvswitch-serverインストール)
- [7. dvs初期設定（ini生成）とTGIF切替](#7-dvs初期設定ini生成とtgif切替)
- [8. スクリプト一式の取得](#8-スクリプト一式の取得)
- [9. dvs_config.shでTGIF用の値を確定](#9-dvs_configshでtgif用の値を確定)

### 第4章：🆕 md380-emu（コンテナ環境での急所）
- [10. md380-emuのアーキテクチャ確認](#10-md380-emuのアーキテクチャ確認)
- [11. qemu-arm-staticの扱い（原本と結論が異なる）](#11-qemu-arm-staticの扱い原本と結論が異なる)

### 第5章：音声とBot
- [12. 音声合成環境（Open JTalk + SoX）](#12-音声合成環境open-jtalk-sox)
- [13. 固定WAVの作成](#13-固定wavの作成)
- [14. 送信テスト](#14-送信テスト)
- [15. Bot本体と設定ツールの導入](#15-bot本体と設定ツールの導入)
- [16. 常駐化（systemd）](#16-常駐化systemd)

### 第6章：🆕 複数コンテナ運用（UHF/VHF分離など）
- [17. コンテナの複製と個体分離](#17-コンテナの複製と個体分離)
- [18. DMR IDの分離運用について](#18-dmr-idの分離運用について)

### 付録
- [付録A：トラブルシューティング早見表（コンテナ固有）](#付録aトラブルシューティング早見表コンテナ固有)
- [付録B：実体ファイルとストレージの仕組み](#付録bストレージの仕組み)

> **最短ルート:** 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 12 → 13 → 14 → 15 → 16。
> 11章は「作業したが不要だった」の記録として読む。17〜18は複数機運用時のみ。

---

# 第1章：前提・原本との違い

## 1. アーキテクチャ上の重要な前提

原本マニュアルは **Raspberry Pi OS（armhf、ARM32ネイティブ）** を前提に書かれています。
本書の環境は **Incus コンテナ上の Debian 12（amd64、x86_64ネイティブ）** です。

DVSwitchスタックの構成要素のうち、実行バイナリのアーキテクチャに依存するのは
**md380-emu（ARM32静的リンクバイナリ）ただ1つ**です。他のコンポーネント
（analog_bridge, mmdvm_bridge, dvswitch_bot.py, Open JTalk 等）はすべて
amd64ネイティブで動作し、原本の手順がそのまま適用できます。

```
┌─────────────────────┐
│  dvswitch_bot.py    │  ← amd64ネイティブ（Python）
└──────────┬──────────┘
           │ USRP (UDP 51000)
           ▼
┌─────────────────────┐
│   Analog_Bridge     │  ← amd64ネイティブ
└──────────┬──────────┘
           │ AMBE (UDP 2470)
           ▼
┌─────────────────────┐
│     md380-emu       │  ← 🔴 ARM32バイナリ（qemu-arm-static経由で実行）
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│   MMDVM_Bridge      │  ← amd64ネイティブ
└──────────┬──────────┘
           │ DMR (UDP 62031)
           ▼
        TGIF Network
```

> 🔴 **重要な発見（原本と結論が異なる点）:**
> 原本の第11章は「qemu-user-staticを5.2（Bullseye版）にダウングレードしないとSEGVする」
> ことを必須操作としていますが、**amd64版のDVSwitch-Serverパッケージは
> `/opt/md380-emu/qemu-arm-static` として単体で5.2.0系バイナリを最初から同梱しています。**
> システム全体のqemu-user-staticダウングレードは、検証の結果**不要**でした。
> 詳細は第11章を参照。

## 2. 原本マニュアルとの対比表

| 章 | 原本（RPi armhf実機） | 本書（Incusコンテナ amd64） |
|---|---|---|
| OS準備 | Raspberry Pi Imagerで書き込み | `incus launch images:debian/12 <name>` |
| ネットワーク固定IP | `nmtui`（NetworkManager） | Incus macvlanデバイス + systemd-networkd |
| DVSwitchリポジトリ | `bookworm`スクリプト（armhf向け） | 同じ`bookworm`スクリプト（**amd64向けに自動対応**） |
| md380-emu実行基盤 | ARM32ネイティブOS上でそのまま実行 | ホストのbinfmt_misc + qemu-arm-static経由でエミュレーション実行 |
| qemuダウングレード | 🔴必須（システム全体） | **不要**（パッケージ同梱バイナリが最初から5.2系） |
| SSHアクセス | 標準で有効なことが多い | 🆕 openssh-serverを別途導入 |

---

# 第2章：コンテナ作成とネットワーク

## 3. Incusコンテナの作成

Incusホスト（Ubuntu 24.04、Incus導入済み）で、Debian 12（amd64）のシステムコンテナを作成します。

```bash
incus init images:debian/12 ocv
incus start ocv
incus list
incus exec ocv -- uname -a
```

> ⚠️ **armhfコンテナを直接作ろうとしない。** `incus launch images:debian/11/armhf ...`
> は `Error: Failed instance creation: ... Requested architecture isn't supported by
> this host` で失敗します。Incusのアーキテクチャ検証はイメージのメタデータのみを見ており、
> qemu-user-static/binfmt_misc の登録状況を考慮しないためです。md380-emu以外は
> amd64依存が無いため、**素直にamd64コンテナを使うのが正解**です。

## 4. 🆕 ネットワーク（macvlan固定IP）

デフォルトの `incusbr0`（NAT）では物理LANのIPが取れないため、macvlanデバイスに
差し替えます。

```bash
# eth0をmacvlan方式にオーバーライド
incus config device add ocv eth0 nic nictype=macvlan parent=<物理NIC名>

incus restart ocv
incus exec ocv -- ip addr show eth0
```

物理NIC名は `incus network list` で確認できます（例: `enp2s0`）。

### 固定IP化（systemd-networkd）

Debian 12コンテナは既定で `systemd-networkd` + `DHCP=true` の
`/etc/systemd/network/eth0.network` を持っています。これを静的設定に書き換えます。

```bash
incus exec ocv -- bash -c 'cat > /etc/systemd/network/eth0.network << "EOF"
[Match]
Name=eth0

[Network]
Address=192.168.1.XXX/24
Gateway=192.168.1.1
DNS=192.168.1.1
EOF'

incus restart ocv
incus exec ocv -- ip addr show eth0
incus exec ocv -- ping -c 3 192.168.1.1
```

> ⚠️ 原本の `nmtui` 手順はDebian 12標準コンテナには存在しません
> （NetworkManagerが入っていないため）。systemd-networkdの `.network` ファイルを
> 直接編集するのが最も確実です。

## 5. 🆕 SSHアクセスの設定

Debian 12の最小コンテナイメージにはSSHサーバーが入っていないため、別途導入します。

```bash
incus exec ocv -- bash -c "apt update && apt install -y openssh-server sudo"
incus exec ocv -- systemctl enable --now ssh

# ユーザー作成
incus exec ocv -- useradd -m -s /bin/bash -G sudo ocv
incus exec ocv -- bash -c "echo 'ocv:<パスワード>' | chpasswd"

# パスワード認証を許可する場合
incus exec ocv -- sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
incus exec ocv -- systemctl restart ssh
```

以降の作業はSSH接続（`ssh ocv@192.168.1.XXX`）で行います。

### 🆕 タイムゾーン・ロケール設定

原本には無い項目ですが、コンテナは既定でUTC・Cロケールのため、必ず設定してください。
bot の時報機能（正時判定）に直接影響します。

```bash
sudo timedatectl set-timezone Asia/Tokyo
sudo apt install -y locales
sudo sed -i 's/^# *ja_JP.UTF-8 UTF-8/ja_JP.UTF-8 UTF-8/' /etc/locale.gen
sudo locale-gen
sudo update-locale LANG=ja_JP.UTF-8 LANGUAGE=ja_JP:ja LC_ALL=ja_JP.UTF-8
```

設定後、ログの日時がJSTになっているか必ず確認してください。

---

# 第3章：DVSwitch-Server

ここからは原本の第7〜10章とほぼ同一です。差分のみ記載します。

## 6. DVSwitch-Serverインストール

```bash
sudo apt install -y wget
cd /tmp
wget http://dvswitch.org/bookworm
chmod +x bookworm
sudo ./bookworm
```

`Verified: Valid DVSwitch Keyring` と `Finished DVSwitch repository install` が
出れば成功。リポジトリの `apt-cache policy` 出力に `b=amd64` と表示されることを
確認してください（原本のarmhf版と混同していないかのチェック）。

```bash
sudo apt install dvswitch-server -y
```

## 7. dvs初期設定（ini生成）とTGIF切替

原本第8章と完全に同一です。

```bash
sudo /usr/local/dvs/dvs
```

`01 初期設定` を完走 → 再起動 → `02 詳細設定 → 24 その他のDMRネットワーク →
1 デフォルトのDMRサーバー変更 → 2 TGIF` でTGIFへ切替。

## 8. スクリプト一式の取得

原本第9章と同一です。

```bash
sudo mkdir -p /opt/dvswitch_bot/bin
sudo chown -R ocv:ocv /opt/dvswitch_bot
cd /opt/dvswitch_bot/bin
BASE=https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main
for f in dvs_config.sh create_wav.sh test_send.py dvswitch_bot.py bot_setup.py; do
  curl -fsSL "$BASE/$f" -o "$f"
done
chmod +x *.sh *.py
```

## 9. dvs_config.shでTGIF用の値を確定

原本第10章と同一です。

```bash
sudo mkdir -p /opt/dvswitch_bot/bak/ini /opt/dvswitch_bot/bak/wav
sudo chown -R ocv:ocv /opt/dvswitch_bot/bak
cd /opt/dvswitch_bot/bin
sudo ./dvs_config.sh
```

反映確認:

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
sudo tail -40 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

`DMR, Logged into the master successfully: tgif.network:62031` が出れば成功。

---

# 第4章：🆕 md380-emu（コンテナ環境での急所）

原本第11章は「qemu 5.2ダウングレードが必須」としていますが、**コンテナ環境（amd64）
では検証の結果、この作業は不要でした。** 本章で実際の確認手順と結論を示します。

## 10. md380-emuのアーキテクチャ確認

```bash
file /opt/md380-emu/md380-emu
```

結果例:
```
/opt/md380-emu/md380-emu: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV),
statically linked, for GNU/Linux 2.6.32, ..., not stripped
```

**ARM32・静的リンク**であることが分かります。amd64ホスト上でこれを実行するには、
ホスト側のbinfmt_misc登録（qemu-arm-static）が必要です。事前準備として
以下がホスト側で完了している前提です。

```bash
# ホスト側（コンテナの外、Incusホスト自体）で実行
sudo apt install -y qemu-user-static binfmt-support
cat /proc/sys/fs/binfmt_misc/qemu-arm   # flags: に F が含まれること（fix binary）
```

`F`フラグ（fix binary、interpreterのfdを登録時に固定）が付いていれば、
コンテナ内に `qemu-arm-static` バイナリ自体を配置しなくても、カーネルが
自動的にARM32バイナリの実行をqemuにディスパッチします。

## 11. qemu-arm-staticの扱い（原本と結論が異なる）

### 11-1. 同梱バイナリの確認 🆕

```bash
/opt/md380-emu/qemu-arm-static --version
file /opt/md380-emu/qemu-arm-static
```

結果例:
```
qemu-arm version 5.2.0 (Debian 1:5.2+dfsg-11+deb11u3)
/opt/md380-emu/qemu-arm-static: ELF 64-bit LSB executable, x86-64, statically linked
```

**amd64版のdvswitch-serverパッケージは、md380-emu実行専用のqemu-arm-static
（5.2.0、x86-64バイナリ）をあらかじめ `/opt/md380-emu/` 配下に同梱しています。**
`md380-emu.service` はシステム全体の `/usr/bin/qemu-arm-static` ではなく、
この同梱バイナリを使って起動します。

```bash
sudo systemctl status md380-emu --no-pager
# CGroup: .../qemu-arm-static /opt/md380-emu/md380-emu -S ...
# のように /opt/md380-emu/qemu-arm-static が使われていることを確認
```

### 11-2. 実行権限の付与（原本と同じく必要）

```bash
sudo chmod +x /opt/md380-emu/md380-emu
sudo systemctl restart md380-emu
sleep 3
sudo systemctl status md380-emu --no-pager
```

### 11-3. 結論

| 操作 | 原本（RPi） | 本書（Incusコンテナ amd64） |
|---|---|---|
| md380-emuに`chmod +x` | 🔴必須 | 🔴必須（同じ） |
| システム全体のqemu-user-staticを5.2へダウングレード | 🔴必須（SEGV回避） | **不要**（同梱バイナリが最初から5.2.0） |

送信テスト（第14章）後、以下でSEGVが出ていないことを最終確認してください。

```bash
sudo journalctl -u md380-emu -n 20 --no-pager
sudo systemctl status md380-emu --no-pager
```

`status=11/SEGV` が出ておらず `active (running)` を維持していれば、
このコンテナ環境ではqemu関連の追加対応は不要と判断できます。

> 💡 **参考: どうしてもホスト全体のダウングレードが必要になった場合**
> amd64版qemu-user-static 5.2系は `deb.debian.org` の通常リポジトリには
> 既に存在しないため（bullseyeがoldoldstableへ移行済み）、`archive.debian.org`
> から取得します。ただし同ディレクトリには**最終セキュリティ更新版のみ**が
> 残っている点に注意してください（例: `deb11u2`は無く`deb11u3`のみ、等）。
> 実在するファイル名は以下で確認できます。
> ```bash
> wget -q -O - http://archive.debian.org/debian/pool/main/q/qemu/ | \
>   grep -oE 'qemu-user-static[^"]*amd64\.deb' | sort -u
> ```

---

# 第5章：音声とBot

原本第14〜18章とほぼ同一です。差分のみ記載します。

## 12. 音声合成環境（Open JTalk + SoX）

原本と同一手順。

```bash
sudo apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic \
  hts-voice-nitech-jp-atr503-m001 sox unzip

cd ~
wget -L --content-disposition \
  https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip
unzip 'MMDAgent_Example-1.8.zip'*
sudo mkdir -p /usr/share/hts-voice/mei
sudo cp MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice /usr/share/hts-voice/mei/
rm -rf MMDAgent_Example-1.8 'MMDAgent_Example-1.8.zip'*

# 動作確認（辞書パスに open-jtalk/ を含む点に注意）
echo "テスト、動作確認。" | open_jtalk \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -ow /tmp/test.wav && \
sox /tmp/test.wav -r 8000 -c 1 -b 16 /tmp/test_8k.wav && echo OK
```

## 13. 固定WAVの作成

原本と同一手順。

```bash
cd /opt/dvswitch_bot/bin
sudo ./create_wav.sh
```

> ⚠️ **カナ確認は毎回丁寧に。** コールサインの読み（例:「ツー」/「ニー」）が
> 名乗り部分と定時メッセージ部分で揺れやすいので、確認画面に出る全項目の
> カナ表記を必ず見比べてから `y` を押してください。不一致に気づいた場合は
> 再実行で修正できます（既存WAVは自動バックアップされます）。

## 14. 送信テスト

原本と同一手順。**このステップがmd380-emu SEGVの最終確認を兼ねます。**

```bash
python3 /opt/dvswitch_bot/bin/test_send.py /opt/dvswitch_bot/001.wav

sudo journalctl -u md380-emu -n 20 --no-pager
sudo systemctl status md380-emu --no-pager
```

## 15. Bot本体と設定ツールの導入

原本と同一手順。

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py    # 手動起動で動作確認
```

`Config loaded` → `Bot ready — monitoring DMR traffic` が出れば成功。
カーチャンクを送って応答を確認後、`Ctrl+C` で停止。

## 16. 常駐化（systemd）

原本第18章と同一です。

```bash
sudo tee /etc/systemd/system/dvswitch-bot.service > /dev/null << 'EOF'
[Unit]
Description=DVSwitch Bot (OpenCCVoice, daemon)
After=network.target analog_bridge.service mmdvm_bridge.service md380-emu.service
Wants=analog_bridge.service mmdvm_bridge.service md380-emu.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
Restart=on-failure
RestartSec=10
User=ocv
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now dvswitch-bot
sudo systemctl status dvswitch-bot --no-pager
```

`active (running)` で、ログに `Config loaded` と `Bot ready` が出ていれば成功。

---

# 第6章：🆕 複数コンテナ運用（UHF/VHF分離など）

原本には無い、Incusコンテナならではの利点です。1台のホスト上に複数の独立した
OpenCCVoice環境（例: UHF機・VHF機）を並行稼働させられます。

## 17. コンテナの複製と個体分離

```bash
# 元コンテナを一旦停止してからコピー（一貫性のため）
incus stop ocv
incus copy ocv ocv-vhf
incus start ocv
```

複製後、**起動前に**個体差別化が必要な項目:

```bash
# ① machine-idの再生成（必須。同一のままだとsystemd journal/D-Busが混乱する）
incus start ocv-vhf
incus exec ocv-vhf -- rm -f /etc/machine-id
incus exec ocv-vhf -- systemd-machine-id-setup

# ② IPアドレスの変更
incus exec ocv-vhf -- bash -c 'cat > /etc/systemd/network/eth0.network << "EOF"
[Match]
Name=eth0

[Network]
Address=192.168.1.YYY/24
Gateway=192.168.1.1
DNS=192.168.1.1
EOF'

# ③ hostnameの変更
incus exec ocv-vhf -- hostnamectl set-hostname ocv-vhf

incus restart ocv-vhf
incus list
```

コンテナ名の変更（リネーム）は以下で行います（停止が必要）。

```bash
incus stop ocv
incus rename ocv ocv-uhf
incus start ocv-uhf
incus exec ocv-uhf -- hostnamectl set-hostname ocv-uhf
```

## 18. DMR IDの分離運用について

🔴 **重要:** 複製したコンテナをTGIFに**同時ログインさせる場合**、
DMR ID（コールサイン7桁 + ESSID 2桁）が完全一致していると、TGIFサーバー側が
重複ログインとみなして**約1〜2分周期でタイムアウト・再接続を繰り返す**
不安定な挙動になります。

```bash
# ログに以下が周期的に出る場合はID重複が濃厚
# E: ... DMR, Connection to the master has timed out, retrying connection
```

運用パターンは2通りです。

| パターン | 対応 |
|---|---|
| **並行稼働させる**（例: UHF機とVHF機を両方常時運用） | `dvs_config.sh` でESSIDおよび送信TGを個体ごとに変える（例: ESSID 68→UHF、84→VHF） |
| **片方は予備機・停止運用**（複製は保険/待機用） | ESSID共通のままで問題ない。ただし稼働させる方は常に1台だけになるよう、不要な側のサービスを確実に停止しておく（`systemctl disable`推奨） |

いずれの場合も、設定変更後は必ずログでTGIFログインの安定性
（タイムアウトが再発しないか）を数分程度確認してください。

```bash
grep -E "^Id=|^Callsign=" /opt/MMDVM_Bridge/MMDVM_Bridge.ini
grep -E "repeaterID|gatewayDmrId|txTg" /opt/Analog_Bridge/Analog_Bridge.ini
sudo tail -f /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

---

# 付録

## 付録A：トラブルシューティング早見表（コンテナ固有）

| 症状 | 原因 | 対処 |
|---|---|---|
| `incus launch images:debian/11/armhf ...` が `architecture isn't supported` で失敗 | Incusのアーキ検証はイメージメタデータのみ参照、qemu登録は無関係 | amd64コンテナ（`images:debian/12`）を使う（第3章） |
| コンテナのIPv4欄が`incus list`で空欄 | macvlan未設定 or 静的IP未反映直後 | `incus config device add ... nictype=macvlan`、数秒待って再確認（第4章） |
| SSH接続できない | openssh-server未導入 | 第5章の手順でインストール・有効化 |
| ログのタイムスタンプがUTC | タイムゾーン未設定 | `timedatectl set-timezone Asia/Tokyo`（第5章） |
| `qemu-user-static_..._armhf.deb`をdpkg -iしようとして失敗 | ホスト(amd64)とパッケージ(armhf)のアーキ不一致 | amd64版のqemu-user-staticを使う。ただしmd380-emu自体は同梱版で足りるため通常不要（第11章） |
| md380-emuがSEGVするか心配 | 原本はRPi前提でqemu 5.2化必須と記載 | まず `/opt/md380-emu/qemu-arm-static --version` を確認。5.2系が同梱されていれば追加対応不要 |
| 複製後のコンテナでTGIF接続が数十秒〜数分周期でタイムアウト | DMR ID（ESSID）が複製元と重複 | `dvs_config.sh` でESSID/送信TGを分離、または片方を確実に停止（第18章） |
| `incus rename` が失敗する | コンテナが起動中 | `incus stop` してから実行 |

## 付録B：ストレージの仕組み

Incusのデフォルトストレージプールは、環境によって `btrfs` ドライバ +
ループバックイメージファイル（例: `/var/lib/incus/disks/default.img`）
という構成になっていることがあります。

```bash
incus storage list
incus storage show default
df -h
```

btrfsはCoW（Copy-on-Write）に対応しているため、`incus copy` によるコンテナ複製や
`incus snapshot create` によるスナップショットは、実データを丸ごと複製せず
差分のみを消費する形で高速・省容量に行われます。

DVSwitch/OpenCCVoiceのワークロード（UDPベースの音声転送が主体、ディスクI/Oは
ログ書き込みとWAV読み込み程度）は非常に軽量なため、ループバックデバイス経由の
オーバーヘッドは実務上ほぼ無視できます。

ストレージプール容量が逼迫してきた場合は以下で拡張できます。

```bash
incus storage set default size=30GiB
```

---

*OpenCCVoice for DVSwitch 構築マニュアル（Incusコンテナ / Debian 12 / amd64 版）*
*原本: OpenCCVoice for DVSwitch 構築・導入・設定 完全マニュアル（Raspberry Pi OS Bookworm 32-bit版）*
*本書は原本との差分検証（Incus 6.0.0 on Ubuntu 24.04 実機）に基づき作成*
