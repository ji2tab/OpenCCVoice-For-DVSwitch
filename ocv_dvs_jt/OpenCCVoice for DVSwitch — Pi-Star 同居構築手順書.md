# OpenCCVoice for DVSwitch — Pi-Star 同居構築手順書

**対象機材：** Raspberry Pi Zero 2 W / Pi-Star v4.3.7 / Bookworm  
**コールサイン：** JJ2ZAR  
**DMR ID：** 440251966（ESSID: 66）  
**接続先：** TGIF Network TG44833  
**Pi-Star IP：** 192.168.X.X  
**作成日：** 2026年6月8日  

---

## 凡例

本手順書では、各操作・ファイル・パッケージが「どこから来たもの」かを以下のマークで明示します。

| マーク | 意味 |
|---|---|
| 🔵 **[Pi-Star 既存]** | Pi-Star に最初から含まれているパッケージ・ファイル・設定 |
| 🟢 **[新規導入]** | 本手順で新たにインストール・作成するもの |
| 🟡 **[Pi-Star 設定変更]** | Pi-Star 既存のファイル・設定を本手順で変更するもの |
| 🔴 **[重要]** | 省略すると動作しない必須手順 |
| ⚠️ **[注意]** | 誤ると問題が起きる可能性がある手順 |
| ✅ **[確認]** | 正常であることを示す出力例 |

---

## 目次

1. [はじめに](#1-はじめに)
2. [Pi-Star の事前確認](#2-pi-star-の事前確認)
3. [不要サービスの停止](#3-不要サービスの停止)
4. [DVSwitch のインストール](#4-dvswitch-のインストール)
5. [qemu のダウングレードとピン留め](#5-qemu-のダウングレードとピン留め)
6. [INI ファイルの設定](#6-ini-ファイルの設定)
7. [systemd サービスの設定](#7-systemd-サービスの設定)
8. [スワップメモリの設定](#8-スワップメモリの設定)
9. [音声合成環境の導入](#9-音声合成環境の導入)
10. [bot スクリプトの導入](#10-bot-スクリプトの導入)
11. [常駐化と動作確認](#11-常駐化と動作確認)
12. [設定値一覧](#12-設定値一覧)
- [付録A：ポート 62031/62032 の競合問題](#付録aポート-6203162032-の競合問題)
- [付録B：DVSwitch リポジトリ URL 変更](#付録bdvswitch-リポジトリ-url-変更)
- [付録C：qemu ダウングレード URL の 404 エラー](#付録cqemu-ダウングレード-url-の-404-エラー)
- [付録D：/var/log/mmdvm/ が再起動で消える問題](#付録dvarlogmmdvm-が再起動で消える問題)
- [付録E：pistar-nextiontext.service の循環依存エラー](#付録epistar-nextiontextservice-の循環依存エラー)
- [付録F：NextionDriver が再起動後に復活する問題](#付録fnextiondriver-が再起動後に復活する問題)
- [付録G：dphys-swapfile が見つからない問題](#付録gdphys-swapfile-が見つからない問題)
- [付録H：MMDAgent ZIP のファイル名問題](#付録hmmdagent-zip-のファイル名問題)
- [付録I：Port=62031 誤判断の経緯と正しい設定](#付録iport62031-誤判断の経緯と正しい設定)

---

## 1. はじめに

### 1.1 このマニュアルの目的

Pi-Star（アマチュア無線デジタル中継システム）が稼働している Raspberry Pi Zero 2 W に、OpenCCVoice for DVSwitch（自動音声応答システム）を同居インストールするための手順書です。

Pi-Star を停止・置き換えることなく、同一機材の上で両システムを並行稼働させます。

### 1.2 システム構成図

```
【Pi-Star 側】🔵 Pi-Star 既存
  MMDVMHost → RF（無線モデム） → TGIF/BM（JJ2ZAR のコールサイン）

【OpenCCVoice 側】🟢 新規導入
  dvswitch_bot.py
       ↓ USRP (UDP 51000)
  Analog_Bridge
       ↓ AMBE (UDP 2470)
  md380-emu
       ↓ TLV (UDP 31100/31103)
  MMDVM_Bridge
       ↓ DMR (UDP 62031)
  TGIF Network TG44833
```

Pi-Star と OpenCCVoice は完全に独立したネットワークスタックで動作します。共有するリソースはハードウェア（CPU・メモリ・ネットワーク）のみです。

### 1.3 パッケージ・ファイル全体像

| 種別 | パッケージ／ファイル | 由来 |
|---|---|---|
| MMDVMHost | /usr/local/bin/MMDVMHost | 🔵 Pi-Star 既存 |
| DMRGateway | /usr/local/bin/DMRGateway | 🔵 Pi-Star 既存 |
| NextionDriver | /usr/local/bin/NextionDriver | 🔵 Pi-Star 既存 |
| qemu-user-static | /usr/bin/qemu-arm-static | 🔵 Pi-Star 既存（→ 🟡 バージョン変更） |
| mmdvmhost.service | /lib/systemd/system/ | 🔵 Pi-Star 既存 |
| /etc/mmdvmhost | Pi-Star の MMDVMHost 設定 | 🔵 Pi-Star 既存（変更なし） |
| analog-bridge | /opt/Analog_Bridge/ | 🟢 新規導入（DVSwitch リポジトリ） |
| mmdvm-bridge | /opt/MMDVM_Bridge/ | 🟢 新規導入（DVSwitch リポジトリ） |
| md380-emu | /opt/md380-emu/ | 🟢 新規導入（DVSwitch リポジトリ） |
| MMDVM_Bridge.ini | /opt/MMDVM_Bridge/ | 🟢 新規導入後に設定 |
| Analog_Bridge.ini | /opt/Analog_Bridge/ | 🟢 新規導入後に設定 |
| mmdvm_bridge.service | /lib/systemd/system/ | 🟡 Pi-Star 既存ファイルを修正 |
| open-jtalk / sox | /usr/bin/ | 🟢 新規導入（Raspbian リポジトリ） |
| mei_normal.htsvoice | /usr/share/hts-voice/mei/ | 🟢 新規導入（MMDAgent より） |
| dvswitch_bot.py 他 | /opt/dvswitch_bot/bin/ | 🟢 新規導入（GitHub） |
| dvswitch-bot.service | /etc/systemd/system/ | 🟢 新規作成 |
| /var/swapfile | スワップファイル | 🟢 新規作成 |
| /etc/rc.local | 起動スクリプト | 🟢 新規作成 |

### 1.4 前提条件

| 項目 | 内容 |
|---|---|
| 対象機材 | Raspberry Pi Zero 2 W |
| Pi-Star バージョン | v4.3.7（Bookworm 64bit カーネル / armhf ユーザーランド） |
| カーネル | Linux 6.12.75+rpt-rpi-v8 aarch64 |
| IP アドレス | 192.168.X.X（固定） |
| 必要な知識 | SSH 接続・sudo コマンドの基本操作 |
| TGIF アカウント | 事前に取得済みであること |

### 1.5 作業の概要

| ステップ | 内容 | 種別 |
|---|---|---|
| 1 | 不要サービスの停止とメモリ確保 | 🔵 Pi-Star 既存サービスを操作 |
| 2 | DVSwitch リポジトリの追加 | 🟢 新規 |
| 3 | DVSwitch パッケージのインストール | 🟢 新規 |
| 4 | qemu のダウングレードとピン留め | 🟡 Pi-Star 既存パッケージを変更 |
| 5 | INI ファイルの設定 | 🟢 新規インストール後に設定 |
| 6 | systemd サービスファイルの修正 | 🟡 Pi-Star 既存ファイルを修正 |
| 7 | スワップメモリの設定 | 🟢 新規 |
| 8 | 音声合成環境（Open JTalk）の導入 | 🟢 新規 |
| 9 | bot スクリプトの取得と設定 | 🟢 新規 |
| 10 | 動作確認 | — |

---

## 2. Pi-Star の事前確認

### 2.1 SSH 接続と読み書きモードへの切り替え

🔵 **[Pi-Star 既存]** Pi-Star のファイルシステムは起動時に読み取り専用（read-only）になっています。設定を変更するには読み書きモードに切り替える必要があります。`rpi-rw` は Pi-Star に付属のコマンドです。

```bash
rpi-rw
```

> プロンプトが `(ro)` から `(rw)` に変わることを確認してください。再起動すると自動的に `(ro)` に戻ります。

### 2.2 ポートの競合確認

DVSwitch を追加する前に、Pi-Star が使用しているポートを確認します。

```bash
sudo ss -tulnp | grep -E '62031|62032|51000|51001|2470|31100|31103'
```

Pi-Star 標準構成では以下のポートが使用されています。

| ポート | 使用プロセス | 由来 | 対処 |
|---|---|---|---|
| 62031（UDP） | 🔵 DMRGateway（127.0.0.1 のみ） | Pi-Star 既存 | 変更不要 |
| 62032（UDP） | 🔵 MMDVMHost | Pi-Star 既存 | MMDVM_Bridge の Local= を 63032 に変更 |

> ⚠️ MMDVM_Bridge の `Local=` ポートに 62032 を使用すると Pi-Star の MMDVMHost と競合します。本手順では **63032 に変更**して回避します。

### 2.3 メモリの確認

```bash
free -m
```

Pi-Star 起動直後のメモリ使用量の目安（すべて 🔵 Pi-Star 既存プロセス）：

| プロセス | 消費メモリ目安 | 由来 |
|---|---|---|
| MMDVMHost | 約 72MB | 🔵 Pi-Star 既存 |
| NextionDriver | 約 43MB | 🔵 Pi-Star 既存 |
| php-fpm | 約 43MB | 🔵 Pi-Star 既存 |
| DMRGateway / その他 | 約 132MB | 🔵 Pi-Star 既存 |
| **合計（目安）** | **約 290MB / 463MB** | |

---

## 3. 不要サービスの停止

🔵 **[Pi-Star 既存サービスを操作]** メモリを確保するために Pi-Star の不要サービスを停止します。

> ⚠️ NextionDriver は Pi-Star の起動スクリプト（`RequiredBy=mmdvmhost.service`）により再起動後に復活します。OLED/Nextion LCD が必要な現場では停止せず、後述の **スワップメモリ（第8章）** で対処してください。

### 3.1 サービス名の確認

```bash
systemctl list-units --all | grep -iE 'nextion|smbd|nmbd|php|samba'
```

以下はすべて 🔵 Pi-Star 既存のサービスです。

| サービス名 | 役割 | 停止可否 |
|---|---|---|
| nextiondriver.service | Nextion/OLED LCD 表示 | LCD 不要なら停止可 |
| pistar-nextiontext.service | LCD テキスト更新 | LCD 不要なら停止可 |
| php8.2-fpm.service | Pi-Star ダッシュボード（PHP） | ダッシュボード不要なら停止可 |
| smbd.service / nmbd.service | Samba ファイル共有 | SSH で管理するなら停止可 |

### 3.2 サービスの停止と無効化

```bash
sudo systemctl stop nextiondriver.service pistar-nextiontext.service \
  phpsessionclean.timer phpsessionclean.service
sudo systemctl disable nextiondriver.service pistar-nextiontext.service \
  phpsessionclean.timer phpsessionclean.service
```

### 3.3 停止後のメモリ確認

```bash
free -m
```

available が 170MB 以上になることを確認してください。

---

## 4. DVSwitch のインストール

🟢 **[新規導入]** DVSwitch パッケージは Pi-Star には含まれていません。専用リポジトリから追加します。

### 4.1 リポジトリスクリプトの取得

🟢 **[新規]** DVSwitch の公式リポジトリを登録するスクリプトを取得します。

```bash
cd /tmp
wget http://dvswitch.org/bookworm -O dvswitch_bookworm.sh
head -5 dvswitch_bookworm.sh   # 内容確認（シェルスクリプトであることを確認）
```

> ℹ️ このスクリプトは N4IRS 氏により 2026年2月に更新されており、Bookworm 対応・GPG キー検証付きです。

### 4.2 リポジトリの登録

🟢 **[新規]** `/etc/apt/sources.list.d/dvswitch.list` が新規作成されます。

```bash
sudo bash /tmp/dvswitch_bookworm.sh
```

以下のメッセージが出れば成功です。

```
Verified: Valid DVSwitch Keyring (72147EC1E788D4C3)
Finished DVSwitch repository install
```

### 4.3 パッケージの確認

```bash
apt-cache show analog-bridge mmdvm-bridge md380-emu | \
  grep -E 'Package|Version|Architecture'
```

以下の armhf 版パッケージが表示されることを確認してください。

| パッケージ | バージョン（目安） | インストール先 |
|---|---|---|
| analog-bridge | 1.6.4-20210517-62 armhf | /opt/Analog_Bridge/ |
| mmdvm-bridge | 1.6.8-20230108-97 armhf | /opt/MMDVM_Bridge/ |
| md380-emu | 20201009-13 armhf | /opt/md380-emu/ |

### 4.4 パッケージのインストール

🟢 **[新規]** 以下の3つが新たにインストールされます。Pi-Star の既存パッケージには触れません。

```bash
sudo apt install -y analog-bridge mmdvm-bridge md380-emu
```

インストール後の配置：

| ファイル | 由来 |
|---|---|
| /opt/Analog_Bridge/Analog_Bridge | 🟢 新規（analog-bridge パッケージ） |
| /opt/Analog_Bridge/Analog_Bridge.ini | 🟢 新規（analog-bridge パッケージ） |
| /opt/MMDVM_Bridge/MMDVM_Bridge | 🟢 新規（mmdvm-bridge パッケージ） |
| /opt/MMDVM_Bridge/MMDVM_Bridge.ini | 🟢 新規（mmdvm-bridge パッケージ） |
| /opt/MMDVM_Bridge/DVSwitch.ini | 🟢 新規（mmdvm-bridge パッケージ） |
| /opt/md380-emu/md380-emu | 🟢 新規（md380-emu パッケージ） |
| /lib/systemd/system/analog_bridge.service | 🟢 新規（analog-bridge パッケージ） |
| /lib/systemd/system/mmdvm_bridge.service | 🟢 新規（mmdvm-bridge パッケージ） |
| /lib/systemd/system/md380-emu.service | 🟢 新規（md380-emu パッケージ） |

### 4.5 md380-emu の実行権限付与

🔴 **[重要]** md380-emu はパッケージのバグにより実行権限がない状態でインストールされます。必ず付与してください。

```bash
sudo chmod +x /opt/md380-emu/md380-emu
ls -la /opt/md380-emu/md380-emu   # -rwxr-xr-x になっていることを確認
```

---

## 5. qemu のダウングレードとピン留め

🟡 **[Pi-Star 既存パッケージを変更]** `qemu-user-static` は Pi-Star に最初から含まれているパッケージです。Bookworm 標準版（7.2）では md380-emu が SEGV（クラッシュ）するため、Bullseye 版（5.2）にダウングレードします。

> ⚠️ この手順は Bookworm 環境では**必須**です。省略すると md380-emu が起動後すぐにクラッシュし、音声変換ができません。

### 5.1 現在の qemu バージョン確認

🔵 **[Pi-Star 既存]** 現在インストールされている qemu のバージョンを確認します。

```bash
dpkg -l | grep qemu-user-static
```

`1:7.2+dfsg-...` と表示された場合はダウングレードが必要です。

### 5.2 Bullseye 版 qemu の取得 URL 確認

```bash
wget -q 'https://packages.debian.org/bullseye/armhf/qemu-user-static/download' \
  -O - | grep -o 'http[^"]*armhf\.deb' | head -3
```

表示された URL をコピーして次のステップで使用します。

### 5.3 ダウングレードとピン留め

🟡 **[Pi-Star 既存パッケージを変更]** Pi-Star に含まれる qemu 7.2 を Bullseye 版 5.2 に置き換えます。`apt-mark hold` で以後の自動更新を防ぎます。

```bash
wget 'http://security.debian.org/debian-security/pool/updates/main/q/qemu/qemu-user-static_5.2+dfsg-11+deb11u5_armhf.deb' \
  -O /tmp/qemu-user-static_bullseye.deb
sudo dpkg -i /tmp/qemu-user-static_bullseye.deb
sudo apt-mark hold qemu-user-static
```

### 5.4 確認

```bash
dpkg -l | grep qemu-user-static   # 1:5.2+dfsg-... と表示されること
apt-mark showhold                  # qemu-user-static が表示されること
```

### 5.5 md380-emu の動作テスト

```bash
sudo /usr/bin/qemu-arm-static /opt/md380-emu/md380-emu
# Usage メッセージが表示され、SEGV が出なければ成功
```

> ✅ `Usage: /opt/md380-emu/md380-emu [OPTION]` と表示されて Exit 1 で終了すれば正常です。

---

## 6. INI ファイルの設定

🟢 **[新規インストールしたファイルを設定]** 第4章でインストールした DVSwitch パッケージの INI ファイル（デフォルト値のまま）を自局の情報に合わせて編集します。Pi-Star の設定ファイル（`/etc/mmdvmhost`）には一切触れません。

### 6.1 バックアップ

```bash
sudo mkdir -p /opt/dvswitch_bot/bak/ini/$(date +%y%m%d%H%M%S)
sudo cp /opt/MMDVM_Bridge/MMDVM_Bridge.ini /opt/Analog_Bridge/Analog_Bridge.ini \
  /opt/dvswitch_bot/bak/ini/$(date +%y%m%d%H%M%S)/
```

### 6.2 MMDVM_Bridge.ini の編集

🟢 **[新規導入した /opt/MMDVM_Bridge/MMDVM_Bridge.ini を設定]**

```bash
sudo sed -i \
  -e 's/^Callsign=N0CALL/Callsign=JJ2ZAR/' \
  -e 's/^Id=1234567/Id=440251966/' \
  -e 's/^Address=hblink.dvswitch.org/Address=tgif.network/' \
  -e 's/^Password=passw0rd/Password=（TGIFのパスワード）/' \
  -e 's/^Latitude=41.7333/Latitude=35.217245/' \
  -e 's/^Longitude=-50.3999/Longitude=137.0103/' \
  -e 's/^Location=Iceberg, North Atlantic/Location=AichiPref Japan/' \
  /opt/MMDVM_Bridge/MMDVM_Bridge.ini

# DMR と DMR Network を有効化
sudo sed -i \
  -e '/^\[DMR Network\]/,/^\[/ s/^Enable=0/Enable=1/' \
  -e '/^\[DMR\]/,/^\[/ s/^Enable=0/Enable=1/' \
  /opt/MMDVM_Bridge/MMDVM_Bridge.ini

# Local ポートを 63032 に変更（62032 は Pi-Star の MMDVMHost と競合するため）
sudo sed -i 's/^Local=62032/Local=63032/' /opt/MMDVM_Bridge/MMDVM_Bridge.ini
```

> 🔴 `Local=` ポートは必ず **63032** に変更してください。62032 のままにすると 🔵 Pi-Star 既存の MMDVMHost と競合し、Pi-Star の動作に影響します。

### 6.3 Analog_Bridge.ini の編集

🟢 **[新規導入した /opt/Analog_Bridge/Analog_Bridge.ini を設定]**

```bash
sudo sed -i \
  -e 's/^useEmulator = false/useEmulator = true/' \
  -e 's/^gatewayDmrId = 1234567/gatewayDmrId = 4402519/' \
  -e 's/^repeaterID = 123456789/repeaterID = 440251966/' \
  -e 's/^txTg = 9/txTg = 44833/' \
  -e 's/^\(txPort = \)31001/\151001/' \
  -e 's/^\(rxPort = \)31001/\151000/' \
  /opt/Analog_Bridge/Analog_Bridge.ini
```

### 6.4 設定値の確認

```bash
grep -E 'Callsign|^Id=|Enable|Address|^Port=|^Local=|Password' \
  /opt/MMDVM_Bridge/MMDVM_Bridge.ini

grep -E 'useEmulator|gatewayDmrId|repeaterID|txTg|txPort|rxPort' \
  /opt/Analog_Bridge/Analog_Bridge.ini
```

期待される確認値：

| 確認項目 | 期待値 | ファイル |
|---|---|---|
| Callsign | JJ2ZAR | 🟢 MMDVM_Bridge.ini |
| Id | 440251966 | 🟢 MMDVM_Bridge.ini |
| Address | tgif.network | 🟢 MMDVM_Bridge.ini |
| Local | **63032**（重要） | 🟢 MMDVM_Bridge.ini |
| useEmulator | true | 🟢 Analog_Bridge.ini |
| txTg | 44833 | 🟢 Analog_Bridge.ini |
| USRP txPort | 51001 | 🟢 Analog_Bridge.ini |
| USRP rxPort | 51000 | 🟢 Analog_Bridge.ini |

---

## 7. systemd サービスの設定

### 7.1 mmdvm_bridge.service の修正

🟡 **[Pi-Star 既存ファイルを修正]** `/lib/systemd/system/mmdvm_bridge.service` は DVSwitch パッケージがインストールした新規ファイルですが、Pi-Star では `/var/log` が tmpfs（再起動でリセット）のため、起動時にログディレクトリを自動作成する処理を追加します。

> このファイルは 🟢 DVSwitch パッケージが作成したものですが、Pi-Star 環境固有の問題（tmpfs）に対応するため修正が必要です。

```bash
sudo sed -i 's|ExecStartPre = /bin/sh -c '"'"'echo "Starting MMDVM_Bridge|ExecStartPre=/bin/mkdir -p /var/log/mmdvm\nExecStartPre=/bin/mkdir -p /var/log/dvswitch\nExecStartPre = /bin/sh -c '"'"'echo "Starting MMDVM_Bridge|' \
  /lib/systemd/system/mmdvm_bridge.service
```

設定を確認します。

```bash
grep 'ExecStart' /lib/systemd/system/mmdvm_bridge.service
```

以下の3行が表示されれば正しく設定されています。

```
ExecStartPre=/bin/mkdir -p /var/log/mmdvm
ExecStartPre=/bin/mkdir -p /var/log/dvswitch
ExecStartPre = /bin/sh -c 'echo "Starting MMDVM_Bridge: ...'
```

### 7.2 サービスの有効化と起動

🟢 **[新規導入した3サービスを起動]** 起動順序が重要です。md380-emu → Analog_Bridge → MMDVM_Bridge の順に起動してください。

```bash
sudo systemctl daemon-reload
sudo systemctl enable md380-emu analog_bridge mmdvm_bridge

# 順番に起動（各サービスの起動完了を待つ）
sudo systemctl start md380-emu && sleep 3
sudo systemctl start analog_bridge && sleep 3
sudo systemctl start mmdvm_bridge && sleep 3
```

### 7.3 起動確認

```bash
sudo systemctl status md380-emu analog_bridge mmdvm_bridge --no-pager | \
  grep -E 'Active|PID'
```

3サービスすべてが `active (running)` になっていることを確認します。

### 7.4 TGIF 接続確認

```bash
sleep 15 && sudo tail -5 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

以下のメッセージが出れば TGIF への接続成功です。

```
M: 2026-xx-xx xx:xx:xx.xxx DMR, Logged into the master successfully: tgif.network:62031
```

---

## 8. スワップメモリの設定

🟢 **[新規作成]** Pi-Star は標準でスワップなしの設定です。DVSwitch スタックを追加するとメモリが不足する場合があるため、256MB のスワップを新たに設定します。

> ℹ️ スワップを設定することで、🔵 Pi-Star 既存の NextionDriver（OLED/LCD 表示）を停止しなくても安定稼働できます。

### 8.1 スワップファイルの作成と有効化

🟢 **[新規作成]** `/var/swapfile` を新規作成します。Pi-Star の既存ファイルには触れません。

```bash
sudo fallocate -l 256M /var/swapfile
sudo chmod 600 /var/swapfile
sudo mkswap /var/swapfile
sudo swapon /var/swapfile
free -m   # Swap: 255 と表示されることを確認
```

### 8.2 再起動後の自動有効化（永続化）

🟢 **[新規作成]** `/etc/rc.local` を新規作成して起動時に自動有効化します。

```bash
sudo tee /etc/rc.local > /dev/null << 'EOF'
#!/bin/bash
# スワップ有効化（OpenCCVoice for DVSwitch 導入時に追加）
if [ ! -f /var/swapfile ]; then
    fallocate -l 256M /var/swapfile
    chmod 600 /var/swapfile
    mkswap /var/swapfile
fi
swapon /var/swapfile 2>/dev/null
exit 0
EOF
sudo chmod +x /etc/rc.local
sudo systemctl enable rc-local
```

> ⚠️ `systemctl enable rc-local` 実行時に警告が出る場合がありますが、rc.local 自体は正常に動作します。

### 8.3 再起動後の確認

```bash
sudo reboot
# 再接続後
free -m
# Swap: 255 と表示されることを確認
```

---

## 9. 音声合成環境の導入

🟢 **[新規導入]** Open JTalk と SoX は Pi-Star には含まれていません。Raspbian 標準リポジトリから新規インストールします。

### 9.1 パッケージのインストール

🟢 **[新規導入]** 以下のパッケージはすべて新規インストールです。Pi-Star の既存パッケージとは無関係です。

```bash
sudo apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic \
  hts-voice-nitech-jp-atr503-m001 sox
```

| パッケージ | 役割 | 由来 |
|---|---|---|
| open-jtalk | 日本語テキスト音声合成エンジン | 🟢 新規（Raspbian リポジトリ） |
| open-jtalk-mecab-naist-jdic | 形態素解析辞書 | 🟢 新規（Raspbian リポジトリ） |
| hts-voice-nitech-jp-atr503-m001 | 標準音声モデル | 🟢 新規（Raspbian リポジトリ） |
| sox | 音声フォーマット変換ツール | 🟢 新規（Raspbian リポジトリ） |

### 9.2 高品質音声モデル（mei）の取得

🟢 **[新規導入]** 標準の音声モデルより高品質な「mei_normal」を MMDAgent のサンプルパッケージから取得します。

```bash
cd ~
wget -L --content-disposition \
  https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip

# ファイル名にパラメータが付く場合はリネームする
mv MMDAgent_Example-1.8.zip* MMDAgent_Example-1.8.zip

# mei_normal.htsvoice だけ展開
unzip MMDAgent_Example-1.8.zip 'MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice'

sudo mkdir -p /usr/share/hts-voice/mei
sudo cp MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice /usr/share/hts-voice/mei/
rm -rf MMDAgent_Example-1.8 MMDAgent_Example-1.8.zip
```

### 9.3 動作確認

```bash
echo 'テスト、動作確認。' | open_jtalk \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -ow /tmp/test.wav && \
sox /tmp/test.wav -r 8000 -c 1 -b 16 /tmp/test_8k.wav && echo OK
```

> ✅ `OK` と表示されれば音声合成環境の構築完了です。

---

## 10. bot スクリプトの導入

🟢 **[新規導入]** すべて GitHub から新規取得するスクリプトです。Pi-Star の既存ファイルとは無関係です。

### 10.1 スクリプトの取得

```bash
sudo mkdir -p /opt/dvswitch_bot/bin
sudo chown -R pi-star:pi-star /opt/dvswitch_bot
cd /opt/dvswitch_bot/bin

BASE=https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/ocv_dvs_jt
for f in dvs_config.sh create_wav.sh test_send.py dvswitch_bot.py bot_setup.py; do
  curl -fsSL "$BASE/$f" -o "$f"
done
chmod +x *.sh *.py
ls -la /opt/dvswitch_bot/bin/
```

5本のスクリプトはすべて 🟢 新規です。

| ファイル名 | 役割 |
|---|---|
| dvswitch_bot.py | 自動応答デーモン本体 |
| bot_setup.py | bot 設定ツール（対話形式） |
| create_wav.sh | 固定 WAV ファイル生成ツール |
| test_send.py | USRP 単発送信テストツール |
| dvs_config.sh | DVSwitch INI 設定ツール |

### 10.2 コールサインの設定

> 🟢 **V1.94 以降、自局コールサイン（`MY_CALLSIGN`）と DMR ID（`MY_DMR_ID`）は
> 起動時に `MMDVM_Bridge.ini` の `Callsign` と `Analog_Bridge.ini` の `gatewayDmrId`
> から自動取得される。そのため `dvswitch_bot.py` を手修正する必要はない。**
>
> コールサイン・DMR ID は第6章で編集した ini（`MMDVM_Bridge.ini` / `Analog_Bridge.ini`）
> の値がそのまま使われる。値を変更したいときは `dvs_config.sh` またはダッシュボードの
> 「DVSwitch 設定」カードで設定し、bot を再起動すれば反映される。
> （ini が読めない場合のみ従来の既定値へフォールバックし、起動ログに WARN を出す。
> 起動ログの `My DMR ID : ...（source: ini 自動取得）` 行で取得元を確認できる。）

### 10.3 bot 設定ファイルの作成

🟢 **[新規作成]** `/opt/dvswitch_bot/bot_config.json` を新規作成します。

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py
```

入力値の目安：

| 設定項目 | 推奨値 | 説明 |
|---|---|---|
| 最小受信時間（秒） | 0.5 | これ未満の受信は無視 |
| 最大受信時間（秒） | 3.9 | これ以上は通常 QSO として無視 |
| 放送回数（1/2/3） | 2 | 1時間あたりの定時メッセージ回数 |
| ナイトモード | y | 夜間の時報・定時メッセージを抑制 |
| N1（開始時） | 22 | 22時から夜間モード開始 |
| N2（終了時） | 5 | 6時から通常モード再開 |

### 10.4 固定 WAV ファイルの作成

🟢 **[新規作成]** bot が使用する音声ファイルを `/opt/dvswitch_bot/` に新規生成します。

```bash
sudo /opt/dvswitch_bot/bin/create_wav.sh
```

入力内容の例：

| 入力項目 | 入力例 |
|---|---|
| コールサイン | JJ2ZAR |
| 読み仮名（確認・修正） | ジェイジェイツーゼットエーアール |
| 設置場所 | おわりあさひ |
| 定時メッセージ1 | ほんじつはせいてんなり |
| 定時メッセージ2 | おはようございます。こんにちは。こんばんは。 |

生成されるファイル（すべて 🟢 新規）：

| ファイル名 | 内容 |
|---|---|
| fixed_intro.wav | カーチャンク応答イントロ |
| fixed_outro.wav | カーチャンク応答アウトロ |
| time_intro.wav | 時報イントロ |
| 001.wav | 定時メッセージ1 |
| 002.wav | 定時メッセージ2 |
| time_outro.wav | 時報アウトロ |

---

## 11. 常駐化と動作確認

### 11.1 手動起動テスト

常駐化する前に、手動起動で正常動作することを確認します。

```bash
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
```

以下のログが出れば正常起動しています。

```
Config loaded /opt/dvswitch_bot/bot_config.json
Bot ready — monitoring DMR traffic
```

カーチャンクを送信して応答を確認したら `Ctrl+C` で停止します。

### 11.2 systemd サービスファイルの作成

🟢 **[新規作成]** `/etc/systemd/system/dvswitch-bot.service` を新規作成します。Pi-Star の既存サービスファイルとは別の場所（`/etc/systemd/system/`）に作成するため、Pi-Star の動作には影響しません。

```bash
sudo tee /etc/systemd/system/dvswitch-bot.service > /dev/null << 'EOF'
[Unit]
Description=DVSwitch Bot (OpenCCVoice)
After=network.target analog_bridge.service mmdvm_bridge.service md380-emu.service
Wants=analog_bridge.service mmdvm_bridge.service md380-emu.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
Restart=on-failure
RestartSec=10
User=pi-star
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable dvswitch-bot
sudo systemctl start dvswitch-bot
```

### 11.3 起動確認

```bash
sleep 5 && sudo journalctl -u dvswitch-bot -n 15 --no-pager
```

> ✅ `Config loaded` と `Bot ready` が表示されれば常駐化完了です。

### 11.4 再起動後の最終確認

```bash
sudo reboot
# 再接続後
systemctl status md380-emu analog_bridge mmdvm_bridge dvswitch-bot --no-pager | \
  grep -E 'Active|PID'
free -m
sleep 20 && sudo tail -3 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

確認ポイント：

- 4サービスすべてが `active (running)`
- `Swap: 255` が表示されている
- MMDVM_Bridge ログに `Logged into the master successfully` が出ている

---

## 12. 設定値一覧

### 12.1 ポート番号一覧

| ポート | プロトコル | 用途 | 由来 |
|---|---|---|---|
| 51000 | UDP | dvswitch_bot → Analog_Bridge（USRP 受信） | 🟢 新規 |
| 51001 | UDP | Analog_Bridge からの出力（USRP 送信） | 🟢 新規 |
| 2470 | UDP | Analog_Bridge ⇔ md380-emu（AMBE 変換） | 🟢 新規 |
| 31100 | UDP | MMDVM_Bridge → Analog_Bridge（TLV） | 🟢 新規 |
| 31103 | UDP | Analog_Bridge → MMDVM_Bridge（TLV） | 🟢 新規 |
| 62031 | UDP | MMDVM_Bridge → TGIF（送信） | 🔵 Pi-Star 既存ポートと共用（競合なし） |
| 62032 | UDP | MMDVMHost（受信） | 🔵 Pi-Star 既存（MMDVM_Bridge は使用しない） |
| 63032 | UDP | TGIF → MMDVM_Bridge（受信） | 🟢 新規（62032 との競合回避のため変更） |

### 12.2 主要ファイルパス一覧

| パス | 内容 | 由来 |
|---|---|---|
| /opt/MMDVM_Bridge/MMDVM_Bridge.ini | MMDVM_Bridge 設定 | 🟢 新規（DVSwitch パッケージ） |
| /opt/Analog_Bridge/Analog_Bridge.ini | Analog_Bridge 設定 | 🟢 新規（DVSwitch パッケージ） |
| /opt/md380-emu/md380-emu | md380-emu バイナリ | 🟢 新規（DVSwitch パッケージ） |
| /opt/dvswitch_bot/bin/dvswitch_bot.py | bot デーモン本体 | 🟢 新規（GitHub） |
| /opt/dvswitch_bot/bin/bot_setup.py | bot 設定ツール | 🟢 新規（GitHub） |
| /opt/dvswitch_bot/bin/create_wav.sh | WAV 生成ツール | 🟢 新規（GitHub） |
| /opt/dvswitch_bot/bot_config.json | bot 設定ファイル | 🟢 新規（bot_setup.py が生成） |
| /opt/dvswitch_bot/*.wav | 固定 WAV ファイル群 | 🟢 新規（create_wav.sh が生成） |
| /opt/dvswitch_bot/bak/ | バックアップ格納場所 | 🟢 新規 |
| /var/log/mmdvm/ | MMDVM_Bridge ログ（tmpfs・再起動でリセット） | 🟢 新規（起動時に自動作成） |
| /usr/share/hts-voice/mei/mei_normal.htsvoice | 音声モデル | 🟢 新規（MMDAgent より） |
| /var/lib/mecab/dic/open-jtalk/naist-jdic | Open JTalk 辞書 | 🟢 新規（open-jtalk パッケージ） |
| /lib/systemd/system/mmdvm_bridge.service | MMDVM_Bridge サービス定義 | 🟡 DVSwitch パッケージ作成→Pi-Star 対応で修正 |
| /etc/systemd/system/dvswitch-bot.service | bot systemd サービス | 🟢 新規作成 |
| /var/swapfile | スワップファイル（256MB） | 🟢 新規作成 |
| /etc/rc.local | 起動時スワップ有効化スクリプト | 🟢 新規作成 |
| /usr/bin/qemu-arm-static | ARM バイナリ実行環境 | 🟡 Pi-Star 既存→バージョン変更（7.2→5.2） |
| /etc/mmdvmhost | Pi-Star の MMDVMHost 設定 | 🔵 Pi-Star 既存（**変更なし**） |

### 12.3 サービス管理コマンド

```bash
# 全サービスの状態確認
systemctl status md380-emu analog_bridge mmdvm_bridge dvswitch-bot --no-pager

# bot ログ確認（リアルタイム）
sudo journalctl -u dvswitch-bot -f

# TGIF 接続ログ確認
sudo tail -20 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log

# 全サービス再起動（順序を守る）
sudo systemctl restart md380-emu && sleep 3
sudo systemctl restart analog_bridge && sleep 3
sudo systemctl restart mmdvm_bridge && sleep 3
sudo systemctl restart dvswitch-bot
```

---

## 付録A：ポート 62031/62032 の競合問題

### 症状

MMDVM_Bridge を起動すると以下のエラーが出て TGIF に接続できない、または Pi-Star の動作がおかしくなる。

```
Error returned from sendto, err: 1 (74.91.115.118:63031)
DMR, Socket has failed when writing data to the master, retrying connection
```

### 原因

🟢 **DVSwitch** の初期設定では MMDVM_Bridge の `Local=62032`（TGIF からの返信を受け取るポート）がデフォルトです。しかし 🔵 **Pi-Star 既存の** MMDVMHost も同じ 62032 を使用するため競合が発生します。

なお、送信側の `Port=62031` は 🔵 Pi-Star 既存の DMRGateway が `127.0.0.1`（ローカルのみ）にバインドしているため、MMDVM_Bridge が外部（tgif.network:62031）に送信しても競合しません。Pi-Star のファイアウォールも UDP 宛先 62031 を許可しているためそのまま使えます。

### 対処

🟢 **新規導入した** MMDVM_Bridge.ini の `Local=` ポートのみ変更します。

```bash
sudo sed -i 's/^Local=62032/Local=63032/' /opt/MMDVM_Bridge/MMDVM_Bridge.ini
sudo systemctl restart mmdvm_bridge
```

> ✅ `Port=62031`（送信側）はそのままで問題ありません。変更が必要なのは `Local=`（受信側）のみです。

---

## 付録B：DVSwitch リポジトリ URL 変更

### 症状

```
wget http://dvswitch.org/installing | sudo bash
ERROR 404: Not Found.
```

### 原因

DVSwitch のインストールスクリプト URL が変更されていました。旧来の `/installing` というパスは廃止されています。

### 対処

```bash
cd /tmp
wget http://dvswitch.org/bookworm -O dvswitch_bookworm.sh
sudo bash dvswitch_bookworm.sh
```

---

## 付録C：qemu ダウングレード URL の 404 エラー

### 症状

```
wget http://archive.debian.org/debian/pool/main/q/qemu/qemu-user-static_5.2+dfsg-11+deb11u5_armhf.deb
ERROR 404: Not Found.
```

### 原因

`archive.debian.org` は Bullseye 終了後に URL 構造が変わっており、`snapshot.debian.org` の日付指定も合いませんでした。

### 対処

`packages.debian.org` のダウンロードページから現在有効なミラー URL を取得するのが確実です。

```bash
wget -q 'https://packages.debian.org/bullseye/armhf/qemu-user-static/download' \
  -O - | grep -o 'http[^"]*armhf\.deb' | head -3

# 表示された URL でダウンロード
wget '（表示されたURL）' -O /tmp/qemu-user-static_bullseye.deb
sudo dpkg -i /tmp/qemu-user-static_bullseye.deb
sudo apt-mark hold qemu-user-static
```

---

## 付録D：/var/log/mmdvm/ が再起動で消える問題

### 症状

再起動後、🟢 **新規導入した** MMDVM_Bridge が起動直後に `exit code 1` で終了する。

```
mmdvm_bridge.service: Main process exited, code=exited, status=1/FAILURE
```

### 原因

🔵 **Pi-Star 既存の設定**として `/var/log` が tmpfs（メモリ上のファイルシステム）にマウントされており、再起動のたびにリセットされます。🟢 **新規導入した** MMDVM_Bridge はログディレクトリ `/var/log/mmdvm/` が存在しないと起動に失敗します。

### 対処

🟢 **DVSwitch パッケージが作成した** `mmdvm_bridge.service` に `ExecStartPre` でディレクトリを自動作成する処理を追加します（🟡 Pi-Star 環境向けの修正）。

```bash
sudo sed -i 's|ExecStartPre = /bin/sh -c '"'"'echo "Starting MMDVM_Bridge|ExecStartPre=/bin/mkdir -p /var/log/mmdvm\nExecStartPre=/bin/mkdir -p /var/log/dvswitch\nExecStartPre = /bin/sh -c '"'"'echo "Starting MMDVM_Bridge|' \
  /lib/systemd/system/mmdvm_bridge.service
sudo systemctl daemon-reload
```

---

## 付録E：pistar-nextiontext.service の循環依存エラー

### 症状

```
sudo systemctl stop pistar-nextiontext.service
Failed to stop pistar-nextiontext.service: Transaction order is cyclic.
```

### 原因

🔵 **Pi-Star 既存の** `pistar-nextiontext.service` が循環依存関係を持っているため、直接停止できません。

### 対処

🔵 **Pi-Star 既存の** `nextiondriver.service` を先に停止してから `disable` する順序で対処します。

```bash
sudo systemctl stop nextiondriver.service
sudo systemctl disable nextiondriver.service pistar-nextiontext.service \
  phpsessionclean.timer phpsessionclean.service
```

---

## 付録F：NextionDriver が再起動後に復活する問題

### 症状

🔵 **Pi-Star 既存の** `nextiondriver.service` を `disable` しても、再起動後に NextionDriver プロセスが起動している。

### 原因

🔵 **Pi-Star 既存の** `nextiondriver.service` の `[Install]` セクションに `RequiredBy=mmdvmhost.service` が記載されており、🔵 Pi-Star 既存の `mmdvmhost.service` が起動するたびに NextionDriver も必ず起動する仕様になっています。

```
[Install]
RequiredBy=mmdvmhost.service   ← Pi-Star の設計による仕様
```

### 採用した対処：スワップメモリの追加（🟢 新規）

🔵 **Pi-Star 既存の** NextionDriver（43MB）を停止せず、🟢 **新規に** スワップメモリ 256MB を追加することで OOM（メモリ不足）リスクを回避しました。現場で OLED/Nextion LCD が必要な場合はこの方法を推奨します（第8章参照）。

---

## 付録G：dphys-swapfile が見つからない問題

### 症状

```
sudo dphys-swapfile swapoff
sudo: dphys-swapfile: command not found
```

### 原因

🔵 **Pi-Star には** `dphys-swapfile` パッケージがインストールされていません。Pi-Star は起動時に `noswap` オプションを指定してスワップを無効化する構成のため、`dphys-swapfile` が不要とされています。

### 対処

🟢 **新規に** `fallocate` コマンドで直接スワップファイルを作成し、🟢 **新規作成した** `rc.local` で起動時に自動有効化します（第8章参照）。

---

## 付録H：MMDAgent ZIP のファイル名問題

### 症状

```
unzip: cannot find or open MMDAgent_Example-1.8.zip
```

### 原因

SourceForge のダウンロードリダイレクトにより、保存ファイル名が `MMDAgent_Example-1.8.zip?viasf=1&fid=...` のようになります。

### 対処

ダウンロード後にリネームしてから解凍します。

```bash
mv MMDAgent_Example-1.8.zip* MMDAgent_Example-1.8.zip
unzip MMDAgent_Example-1.8.zip 'MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice'
```

---

## 付録I：Port=62031 誤判断の経緯と正しい設定

### 経緯

最初の分析で「`Port=62031`（送信側）も競合する」と誤って判断し、63031 に変更したところ、🔵 **Pi-Star 既存の** ファイアウォール（iptables）に 62031 のみ許可ルールがあり、63031 が REJECT されました。

```
# Pi-Star 既存の iptables ルール（pistar-firewall スクリプトが設定）
Chain OUTPUT (policy DROP)
ACCEPT udp dpt:62031   ← Pi-Star が許可しているのは 62031 のみ
```

その後、62031 に戻したところ `Local=62032` が 🔵 Pi-Star 既存の MMDVMHost と競合する、という二重の問題が発生しました。

### 正しい理解

| 設定項目 | 役割 | 競合状況 | 正しい値 |
|---|---|---|---|
| `Port=62031`（送信先） | MMDVM_Bridge が TGIF に送信する宛先ポート | 🔵 Pi-Star 既存 DMRGateway は 127.0.0.1 のみバインドのため**競合なし** | **62031（変更不要）** |
| `Local=62032`（受信ポート） | TGIF から MMDVM_Bridge が受信するポート | 🔵 Pi-Star 既存 MMDVMHost が同じ 62032 を使用するため**競合あり** | **63032（変更必須）** |

---

*JJ2YYK 尾張旭 DMR デジピーター　2026年6月8日*
