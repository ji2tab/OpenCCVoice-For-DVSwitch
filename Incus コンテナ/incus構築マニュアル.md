# Incus コンテナ構築マニュアル
**OpenCCVoice for DVSwitch 向け / Debian 12（amd64）コンテナの準備**

---

> **このマニュアルの位置づけ**
>
> OpenCCVoice for DVSwitch を **Incus コンテナ上の Debian 12 Bookworm（amd64）** で
> 動かすための、**コンテナ基盤（OS レイヤ）の準備**に特化したマニュアルです。
> 
> **Incus はあくまで x86_64 Linux 環境を用意する一手段です。** ベアメタルや他の仮想環境（VM 等）で
> 既に amd64 の Debian/Ubuntu 系 Linux が用意できている場合は、本書は不要です。その場合は
> 『OpenCCVoice for DVSwitch 構築マニュアル.md』から直接進めてください。
>
> ここでの作業（コンテナ作成・ネットワーク・SSH・タイムゾーン・qemu 準備・複数機運用）が
> 完了したら、コンテナ内での DVSwitch / 音声 / Bot の構築は
> 『OpenCCVoice for DVSwitch 構築マニュアル.md』へ進んでください。
>
> **対象構成:**
> - ホスト: Ubuntu 24.04 LTS（amd64）+ Incus 6.0.0
> - コンテナ: Debian 12 Bookworm（amd64、`images:debian/12` で作成）
> - ユーザー: `ocv`
> - ネットワーク: macvlan（物理LAN直結）+ 固定IP

**凡例:** ✅ 検証済み ／ ⚠️ 要注意 ／ 🔴 重大（外すと成立しない）

---

## 目次

1. [アーキテクチャ上の重要な前提](#1-アーキテクチャ上の重要な前提)
2. [Incus コンテナの作成](#2-incusコンテナの作成)
3. [ネットワーク（macvlan 固定IP）](#3-ネットワークmacvlan固定ip)
4. [SSH アクセスの設定](#4-sshアクセスの設定)
5. [タイムゾーン・ロケール設定](#5-タイムゾーンロケール設定)
6. [md380-emu 実行のためのホスト側 qemu 準備](#6-md380-emu実行のためのホスト側qemu準備)
7. [複数コンテナ運用（UHF/VHF 分離など）](#7-複数コンテナ運用uhfvhf分離など)
8. [付録A：トラブルシューティング早見表（コンテナ基盤）](#付録aトラブルシューティング早見表コンテナ基盤)
9. [付録B：ストレージの仕組み](#付録bストレージの仕組み)

> **完了後の導線:** 本マニュアルの 1〜6 章まで完了したら、
> コンテナ内で『OpenCCVoice for DVSwitch 構築マニュアル.md』を実施してください。
> 7 章は複数機運用時のみ。

---

## 1. アーキテクチャ上の重要な前提

OpenCCVoice の原本手順は **Raspberry Pi OS（armhf、ARM32 ネイティブ）** を前提にしています。
本コンテナ環境は **Debian 12（amd64、x86_64 ネイティブ）** です。

DVSwitch スタックの構成要素のうち、実行バイナリのアーキテクチャに依存するのは
**md380-emu（ARM32 静的リンクバイナリ）ただ1つ**です。他のコンポーネント
（analog_bridge, mmdvm_bridge, dvswitch_bot.py, Open JTalk 等）はすべて
amd64 ネイティブで動作します。

```
┌─────────────────────┐
│ dvswitch_bot.py     │ ← amd64ネイティブ（Python）
└──────────┬──────────┘
           │ USRP (UDP 51000)
           ▼
┌─────────────────────┐
│ Analog_Bridge       │ ← amd64ネイティブ
└──────────┬──────────┘
           │ AMBE (UDP 2470)
           ▼
┌─────────────────────┐
│ md380-emu           │ ← 🔴 ARM32バイナリ（qemu-arm-static経由で実行）
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ MMDVM_Bridge        │ ← amd64ネイティブ
└──────────┬──────────┘
           │ DMR (UDP 62031)
           ▼
        TGIF Network
```

> ⚠️ **armhf コンテナを直接作ろうとしない。** `incus launch images:debian/11/armhf ...`
> は `Requested architecture isn't supported by this host` で失敗します。Incus の
> アーキテクチャ検証はイメージのメタデータのみを見ており、qemu-user-static/binfmt_misc の
> 登録状況を考慮しないためです。md380-emu 以外は amd64 依存が無いため、
> **素直に amd64 コンテナを使うのが正解**です。

---

## 2. Incus コンテナの作成

Incus ホスト（Ubuntu 24.04、Incus 導入済み）で、Debian 12（amd64）の
システムコンテナを作成します。

```bash
incus init images:debian/12 ocv
incus start ocv
incus list
incus exec ocv -- uname -a
```

---

## 3. ネットワーク（macvlan 固定IP）

デフォルトの `incusbr0`（NAT）では物理 LAN の IP が取れないため、
macvlan デバイスに差し替えます。

```bash
# eth0をmacvlan方式にオーバーライド
incus config device add ocv eth0 nic nictype=macvlan parent=<物理NIC名>

incus restart ocv
incus exec ocv -- ip addr show eth0
```

物理 NIC 名は `incus network list` で確認できます（例: `enp2s0`）。

### 固定IP化（systemd-networkd）

Debian 12 コンテナは既定で `systemd-networkd` + `DHCP=true` の
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

> ⚠️ Debian 12 標準コンテナには NetworkManager が入っていないため、`nmtui` は
> 使えません。systemd-networkd の `.network` ファイルを直接編集するのが最も確実です。

---

## 4. SSH アクセスの設定

Debian 12 の最小コンテナイメージには SSH サーバーが入っていないため、別途導入します。

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

以降の作業は SSH 接続（`ssh ocv@192.168.1.XXX`）で行えます。

---

## 5. タイムゾーン・ロケール設定

コンテナは既定で UTC・C ロケールのため、必ず設定してください。
bot の時報機能（正時判定）に直接影響します。

```bash
sudo timedatectl set-timezone Asia/Tokyo
sudo apt install -y locales
sudo sed -i 's/^# *ja_JP.UTF-8 UTF-8/ja_JP.UTF-8 UTF-8/' /etc/locale.gen
sudo locale-gen
sudo update-locale LANG=ja_JP.UTF-8 LANGUAGE=ja_JP:ja LC_ALL=ja_JP.UTF-8
```

設定後、ログの日時が JST になっているか必ず確認してください。

---

## 6. md380-emu 実行のためのホスト側 qemu 準備

md380-emu は ARM32・静的リンクバイナリです。amd64 ホスト上でこれを実行するには、
**ホスト側（コンテナの外、Incus ホスト自体）** の binfmt_misc 登録が必要です。

```bash
# ホスト側で実行
sudo apt install -y qemu-user-static binfmt-support
cat /proc/sys/fs/binfmt_misc/qemu-arm   # flags: に F が含まれること（fix binary）
```

`F` フラグ（fix binary、interpreter の fd を登録時に固定）が付いていれば、
コンテナ内に `qemu-arm-static` バイナリ自体を配置しなくても、カーネルが
自動的に ARM32 バイナリの実行を qemu にディスパッチします。

> 💡 **qemu ダウングレードは不要:** amd64 版の dvswitch-server パッケージは、
> md380-emu 実行専用の `qemu-arm-static`（5.2.0）を `/opt/md380-emu/` 配下に
> あらかじめ同梱しています。原本（RPi 版）で必須だった「システム全体の
> qemu-user-static を 5.2 へダウングレード」は、本コンテナ環境では不要です。
> 詳細な確認手順は『OpenCCVoice for DVSwitch 構築マニュアル.md』の md380-emu 章を参照。

---

## 7. 複数コンテナ運用（UHF/VHF 分離など）

1台のホスト上に複数の独立した OpenCCVoice 環境（例: UHF 機・VHF 機）を
並行稼働させられます。まずは 1 台目のコンテナ内で OpenCCVoice の構築
（『構築マニュアル.md』）を完了させてから、以下で複製するのが効率的です。

### 7-1. コンテナの複製と個体分離

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

コンテナ名の変更（リネーム）は停止が必要です。

```bash
incus stop ocv
incus rename ocv ocv-uhf
incus start ocv-uhf
incus exec ocv-uhf -- hostnamectl set-hostname ocv-uhf
```

### 7-2. DMR ID の分離運用について

🔴 **重要:** 複製したコンテナを TGIF に**同時ログインさせる場合**、
DMR ID（コールサイン7桁 + ESSID 2桁）が完全一致していると、TGIF サーバー側が
重複ログインとみなして**約1〜2分周期でタイムアウト・再接続を繰り返す**
不安定な挙動になります。

```bash
# ログに以下が周期的に出る場合はID重複が濃厚
# E: ... DMR, Connection to the master has timed out, retrying connection
```

| パターン | 対応 |
|---|---|
| **並行稼働させる**（例: UHF 機と VHF 機を両方常時運用） | `dvs_config.sh` で ESSID および送信 TG を個体ごとに変える（例: ESSID 68→UHF、84→VHF） |
| **片方は予備機・停止運用**（複製は保険/待機用） | ESSID 共通のままで問題ない。ただし稼働させる方は常に1台だけになるよう、不要な側のサービスを確実に停止（`systemctl disable` 推奨） |

いずれの場合も、設定変更後は必ずログで TGIF ログインの安定性を数分程度確認してください。

```bash
grep -E "^Id=|^Callsign=" /opt/MMDVM_Bridge/MMDVM_Bridge.ini
grep -E "repeaterID|gatewayDmrId|txTg" /opt/Analog_Bridge/Analog_Bridge.ini
sudo tail -f /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

---

## 付録A：トラブルシューティング早見表（コンテナ基盤）

| 症状 | 原因 | 対処 |
|---|---|---|
| `incus launch images:debian/11/armhf ...` が `architecture isn't supported` で失敗 | Incus のアーキ検証はイメージメタデータのみ参照、qemu 登録は無関係 | amd64 コンテナ（`images:debian/12`）を使う（2章） |
| コンテナの IPv4 欄が `incus list` で空欄 | macvlan 未設定 or 静的IP 未反映直後 | `incus config device add ... nictype=macvlan`、数秒待って再確認（3章） |
| SSH 接続できない | openssh-server 未導入 | 4章の手順でインストール・有効化 |
| ログのタイムスタンプが UTC | タイムゾーン未設定 | `timedatectl set-timezone Asia/Tokyo`（5章） |
| md380-emu が SEGV するか心配 | qemu の binfmt 準備 or 同梱バイナリ確認不足 | ホスト側 binfmt 登録（6章）を確認。実行確認は構築マニュアル側で実施 |
| 複製後のコンテナで TGIF 接続が数十秒〜数分周期でタイムアウト | DMR ID（ESSID）が複製元と重複 | `dvs_config.sh` で ESSID/送信 TG を分離、または片方を確実に停止（7-2） |
| `incus rename` が失敗する | コンテナが起動中 | `incus stop` してから実行 |

## 付録B：ストレージの仕組み

Incus のデフォルトストレージプールは、環境によって `btrfs` ドライバ +
ループバックイメージファイル（例: `/var/lib/incus/disks/default.img`）
という構成になっていることがあります。

```bash
incus storage list
incus storage show default
df -h
```

btrfs は CoW（Copy-on-Write）に対応しているため、`incus copy` によるコンテナ複製や
`incus snapshot create` によるスナップショットは、実データを丸ごと複製せず
差分のみを消費する形で高速・省容量に行われます。

DVSwitch/OpenCCVoice のワークロードは非常に軽量なため、ループバックデバイス経由の
オーバーヘッドは実務上ほぼ無視できます。容量が逼迫してきた場合は以下で拡張できます。

```bash
incus storage set default size=30GiB
```

---

*Incus コンテナ構築マニュアル（Debian 12 / amd64 版）*
*次工程: OpenCCVoice for DVSwitch 構築マニュアル.md*
