# DVSwitch-Server 導入完全マニュアル（改訂版）

**Raspberry Pi Zero 2 W / Bullseye・Bookworm 両対応版**

> **改訂版について**
> 本版は初版に対し、(a) 元ブログの実作業ログ（bookworm 経由 → buster 修復）を「実際に起きたこと」として忠実に独立記載、(b) 検証が取れていない箇所に **🔶要検証** マークを明示、(c) DVSwitch 公式ドキュメント・公式リポジトリビルダーで裏取りした結果を注記、の3点を反映したものです。
>
> **凡例**
> - ✅ **公式裏取り済み**：DVSwitch 公式ドキュメント／公式 System-Builder で確認できた手順
> - 🔶 **要検証**：元ブログ記事のみが根拠で、公式・一次情報での確認が取れていない箇所。実機で確認のうえ確定してください
> - 📝 **実ログ**：元ブログの実作業記録（試行錯誤を含む）をそのまま記載した箇所

---

## 目次

1. [はじめに](#1-はじめに)
2. [DVSwitch-Server とは](#2-dvswitch-server-とは)
3. [世代別リポジトリ対応表と原則](#3-世代別リポジトリ対応表と原則)
4. [第I部：Bullseye 環境での導入（推奨手順）](#第i部bullseye-環境での導入推奨手順)
5. [第I部・別記：実際に起きたこと（bookworm 経由 → buster 修復ログ）](#第i部別記実際に起きたことbookworm-経由--buster-修復ログ)
6. [第II部：Bookworm 環境での導入](#第ii部bookworm-環境での導入)
7. [第III部：Web サーバ設定（Apache / lighttpd）](#第iii部web-サーバ設定apache--lighttpd)
8. [第IV部：Platform 表示の修正（platformDetect.sh）](#第iv部platform-表示の修正platformdetectsh)
9. [第V部：トラブルシュート＆失敗・修復事例](#第v部トラブルシュート失敗修復事例)
10. [第VI部：要検証項目一覧（確定作業用）](#第vi部要検証項目一覧確定作業用)
11. [付録：チェックリスト](#付録チェックリスト)

---

## 1. はじめに

このマニュアルは、Raspberry Pi 上に DVSwitch-Server を構築するための実践ガイドです。Raspberry Pi OS の世代（Bullseye / Bookworm）によって導入手順とハマりどころが異なるため、章を分けて両対応としています。

本書には**推奨手順**（公式に沿った最短ルート）と、**実ログ**（元ブログで実際にたどった試行錯誤の記録）の両方を収録しています。初めて構築する場合は推奨手順に従ってください。実ログは「同じ失敗をしたときの修復」と「なぜそうなるかの理解」のために残しています。

**実運用での推奨構成**

- ハードウェア：Raspberry Pi Zero 2 W（ARMv7 / Cortex-A53）
- OS：Raspberry Pi OS Lite（Debian 11 Bullseye ベース、armhf）
- Web サーバ：lighttpd（DVSwitch 標準）または Apache（Bookworm の一部構成）

---

## 2. DVSwitch-Server とは

DVSwitch-Server は、デジタル音声（DMR / D-STAR / YSF / NXDN / P25 など）のクロスモード・ブリッジ運用を実現するサーバソフトウェア群です。`apt` で一括導入すると、主に次のコンポーネントが入ります。

| コンポーネント | 役割 |
|---|---|
| `dvswitch-server` | メニュー、ダッシュボード、モニタ機能の本体（設定メニュー `dvs` を含む） |
| `analog-reflector` | hUC 対応アナログリフレクタ（WebUI 付き） |
| `stfu` | BrandMeister 直結用コンポーネント |
| `mmdvm-bridge` | MMDVM プロトコルのブリッジ |
| `md380-emu` | AMBE ソフトウェアコーデック（MD380 ファーム流用） |
| `lighttpd` / `php` | ダッシュボード配信用 Web サーバと PHP |
| `mosquitto` | MQTT ブローカ（コンポーネント間メッセージング） |

> ✅ **公式裏取り済み**：DVSwitch 公式 System-Builder のドキュメントは、導入完了時に「Dashboard・System Monitor・設定メニュー（`dvs`）を含む完全な DVSwitch Server」が入ると説明しています。なお `dvs` メニューはスーパーユーザの PATH には含まれないため、フルパスまたは所定ディレクトリから起動します。

---

## 3. 世代別リポジトリ対応表と原則

DVSwitch はリポジトリ追加スクリプトを OS 世代ごとに提供しています。

| Raspberry Pi OS | Debian ベース | 使用するスクリプト | 区分 |
|---|---|---|---|
| Buster | Debian 10 | `buster` | ✅ 正規対応 |
| **Bullseye** | **Debian 11** | **`buster` を流用** | 🔶 専用なし。最も近い安定版を流用（後述） |
| Bookworm | Debian 12 | `bookworm` | ✅ 正規対応 |

### 原則：OS 世代に合った「1本のスクリプト」を最初から使う

> ✅ **公式裏取り済み**：DVSwitch の公式手順およびコミュニティの導入ガイドは、いずれも「OS に対応するスクリプトを1本取得 → 実行 → `apt install`」という単線の流れです。**公式手順に「bookworm を実行してから buster へ切り替える」という二段階フローは存在しません。**

つまり、

- Bullseye なら最初から **`buster`** を取得・実行する（後述の推奨手順）
- Bookworm なら最初から **`bookworm`** を取得・実行する

のが正しい進め方です。元ブログの「失敗、修復例」に出てくる「bookworm を実行 → 後から buster へ修正」という流れは、**正規手順ではなく、実機での試行錯誤の記録**です。これは本書の「[第I部・別記：実際に起きたこと](#第i部別記実際に起きたことbookworm-経由--buster-修復ログ)」に、修復の参考として独立収録しています。

### 🔶 要検証：Bullseye での buster 流用について

元ブログは「Bullseye には専用リポジトリがないため buster を流用」としています。DVSwitch 公式リポジトリのインデックスには各 codename 別のディレクトリが存在しますが、本改訂時点で `bullseye` ディレクトリの有無、および buster パッケージが Bullseye 上で完全に依存解決できるかは一次情報で確定できませんでした。元ブログでは buster 流用で動作した実績が報告されていますが、**実機で `apt install` がエラーなく完了することを必ず確認**してください（確認方法は[第VI部](#第vi部要検証項目一覧確定作業用)）。

---

## 第I部：Bullseye 環境での導入（推奨手順）

> この第I部は「最初からやり直すならこうする」という**推奨ルート**です。すでに bookworm スクリプトを実行してしまった場合は、先に[第I部・別記](#第i部別記実際に起きたことbookworm-経由--buster-修復ログ)の修復を行ってください。

### I-1. OS イメージの準備

Raspberry Pi OS Bullseye（Debian 11 ベース、armhf）の Lite イメージを使用します。

```
https://ftp.jaist.ac.jp/pub/raspberrypi/raspios_oldstable_lite_armhf/images/raspios_oldstable_lite_armhf-2025-05-07/
```

> 🔶 **要検証**：このミラー上のイメージ名・配置は時期により変わります。`raspios_oldstable_lite_armhf` 配下に Bullseye ベースの Lite があることを確認してください。なぜ oldstable（Bullseye）の Lite かというと、DVSwitch が Bullseye 専用リポジトリを提供していない前提で、最も近い安定版である buster リポジトリとの依存差を最小化するためです（この前提自体が上記 🔶 要検証）。

イメージを Raspberry Pi Imager 等で microSD に書き込み、SSH・WiFi・ロケール等の初期設定を済ませてから起動してください。

### I-2. 固定 IP アドレスの設定（Bullseye / dhcpcd 方式）

Bullseye は `dhcpcd` がネットワーク管理のデフォルトです。`dhcpcd.conf` を編集します。

```bash
sudo nano /etc/dhcpcd.conf
```

ファイル末尾までスクロールし、以下を追加します（値は自ネットワークに合わせて変更）。

```conf
interface wlan0
static ip_address=192.168.3.9/24
static routers=192.168.3.1
static domain_name_servers=192.168.3.1
```

保存後、再起動するか `sudo systemctl restart dhcpcd` で反映します。

> ⚠️ **Bookworm では方式が異なります**。Bookworm は NetworkManager がデフォルトのため、この `dhcpcd.conf` 方式は標準では効きません。Bookworm の固定 IP は[第II部](#ii-0-bookworm-の固定-ip-について)を参照してください。

### I-3. リポジトリ追加とインストール（推奨：buster 一本）

`root` になり、作業ディレクトリへ移動します。

```bash
sudo su -
cd /tmp
```

> ⚠️ **補足（セキュリティ）**：`sudo su -` でrootシェルを取得する方法は動作しますが、`sudo apt install ...` のように各コマンドに `sudo` を付ける方が操作ログが残り、より安全です。Raspberry Pi OS の慣例として `sudo su -` も広く使われているため実用上は問題ありません。

事前に本体を最新化します（公式ガイドが推奨）。

```bash
apt update
apt upgrade
# 更新が入った場合は再起動
```

DVSwitch のリポジトリ追加スクリプト（buster 用）を取得・実行します。

```bash
wget http://dvswitch.org/buster
chmod +x buster
./buster
apt update
apt install dvswitch-server analog-reflector stfu -y
```

> ✅ **公式裏取り済み**：`wget http://dvswitch.org/buster` → `chmod +x buster` → `./buster` → `apt update` → `apt install dvswitch-server …` というリポジトリ追加〜導入の流れは、公式系ドキュメントの記述と一致します。
>
> 🔶 **要検証（コマンド順序）**：元ブログは `./buster` の**前**に `apt update --allow-releaseinfo-change` を置いていますが、この時点では DVSwitch リポジトリはまだ追加されていません。`--allow-releaseinfo-change` が意味を持つのは「すでに登録済みのリポジトリの Release 情報が変わったとき」です。本推奨手順では順序を整理し、`./buster`（リポジトリ追加）の**後**に `apt update` を置いています。`apt update` 時に Release 情報変更の警告／エラーが出た場合に限り、次項のように `--allow-releaseinfo-change` を付けて再実行してください。

Release 情報変更エラーが出た場合のみ：

```bash
apt update --allow-releaseinfo-change
```

### I-4. 各コマンドの意味と理由

| コマンド | 何をしているか | なぜ必要か |
|---|---|---|
| `apt update` / `apt upgrade` | 既存（OS本体）パッケージを最新化 | 公式ガイドが導入前の最新化を推奨。依存衝突を減らす |
| `wget http://dvswitch.org/buster` | buster 用リポジトリ追加スクリプトをダウンロード | APT 経由導入には公式リポジトリ追加が必要。Bullseye 専用がないため buster 用を流用（🔶 要検証） |
| `chmod +x buster` | スクリプトに実行権限を付与 | ダウンロードファイルは通常実行不可のため |
| `./buster` | スクリプトを実行 | 公式 GPG キー追加、`/etc/apt/sources.list.d/dvswitch.list` 追加、キーリング配置を自動で行う |
| `apt update` | 追加済みリポジトリを含めて再更新 | これをしないと `apt install` で DVSwitch パッケージが見つからない |
| `apt install dvswitch-server analog-reflector stfu -y` | DVSwitch サーバ一式を導入 | 主要コンポーネント（§2 の表）を一括導入。`-y` で確認自動 Yes |
| `apt update --allow-releaseinfo-change` | Release 情報変更を許可して更新 | 登録済みリポジトリの Release 情報が変わってエラーになる場合のみ使用（条件付き） |

### I-5. sources.list の確認

リポジトリ定義が buster を指しているか確認します。

```bash
cat /etc/apt/sources.list.d/dvswitch.list
```

おおむね次の形になっているはずです。

```
deb [signed-by=/usr/share/keyrings/dvswitch-keyring.gpg] http://dvswitch.org/DVSwitch_Repository buster hamradio
```

> 🔶 **要検証（行末の codename・キーリングパス）**：行末が `buster hamradio` であるべき、というのは元ブログの記述に基づきます。`./buster` スクリプトが実際に書き込む codename・コンポーネント名・キーリングパスは、スクリプトのバージョンで異なる可能性があります。特に `signed-by=` のパスが `/usr/share/keyrings/dvswitch-keyring.gpg` ではなく `/etc/apt/trusted.gpg.d/` になっている場合もあります（古いバージョンのスクリプトは後者を使うものが多い）。`./buster` 実行後に実ファイルを `cat` し、その内容を**正**としてください（スクリプトが書いた値を手で変えると不整合になります）。手修正が必要なのは、誤って別 codename のスクリプトを実行した場合の救済時のみです（[別記](#第i部別記実際に起きたことbookworm-経由--buster-修復ログ)参照）。

### I-6. WebUI へのアクセス

導入後、ブラウザから DVSwitch のダッシュボード／WebUI にアクセスします。

```
http://<RaspberryPiのIPアドレス>/
例：http://192.168.3.9/
```

> 🔶 **要検証（ポート番号）**：初版では `http://<IP>:2812/` と記載しましたが、これは見直しが必要です。
> - DVSwitch **公式ユーザーガイド**は、クライアント設定でホスト名を入れる際「**ポート番号は付けない**」と明記しています（これはクライアント接続先の話で、ダッシュボード URL とは別文脈ですが、`:2812` を公式標準として確認はできませんでした）。
> - `2812` は一般に **monit** のデフォルト管理ポートです。DVSwitch ダッシュボード本体（lighttpd/Apache 配信）は通常 **80 番**で、`/usr/share/dvswitch` 等が DocumentRoot になります。
> - 元ブログ内でも「IP のみ（ポートなし）」「`:2812`」「Apache 80番」が混在しています。
>
> **実機で次を確認して URL を確定してください**：`sudo ss -tlnp | grep -E ':(80|2812|443)'` でリッスン中のポートとプロセス名（lighttpd / apache2 / monit）を見て、ダッシュボードを出しているプロセスのポートを採用します。

---

## 第I部・別記：実際に起きたこと（bookworm 経由 → buster 修復ログ）

> 📝 **実ログ**：ここは「正しい手順」ではありません。元ブログ「DVSwitch-Server を Raspberry Pi Zero 2 W で動かす完全ガイド（Bullseye 対応）失敗、修復例」で**実際にたどった操作**を、再現と理解のためにそのまま記録したものです。これからクリーンに構築する人は[第I部の推奨手順](#第i部bullseye-環境での導入推奨手順)に従ってください。同じ状態に陥った人は、ここを修復ガイドとして使えます。

### 何が起きたか

Bullseye 機に対して、標準手順のつもりで **bookworm スクリプトを取得・実行**してしまいました。

```bash
sudo su -
cd /tmp
wget http://dvswitch.org/bookworm     # ← Bullseye なのに bookworm を取得（ここが原因）
chmod +x bookworm
apt update --allow-releaseinfo-change
./bookworm
apt update
apt install dvswitch-server analog-reflector stfu -y
```

この結果、Debian 12 用リポジトリが Bullseye（Debian 11）に登録され、`apt install` でパッケージが見つからない／依存関係が崩れる状態になりました。

### どう修復したか

その後、設定メニュー側から buster スクリプトを取得し直し、リポジトリ定義を buster へ手修正しています。

```bash
cd /usr/local/dvs
./dvs
wget http://dvswitch.org/buster
chmod +x buster
./buster
```

続いて `sources.list` を手で buster に修正：

```bash
nano /etc/apt/sources.list.d/dvswitch.list
```

```
deb [signed-by=/usr/share/keyrings/dvswitch-keyring.gpg] http://dvswitch.org/DVSwitch_Repository buster hamradio
```

最後に再更新・再導入：

```bash
apt update
apt install dvswitch-server analog-reflector stfu -y
```

### この別記に対する技術的コメント

- 📝 **実ログ**：`cd /usr/local/dvs` → `./dvs` は、bookworm スクリプトが一度通って `dvs` メニュー環境ができていたために可能になった操作です。**クリーン構築では `/usr/local/dvs` はまだ存在しません**。だからこそ推奨手順（第I部）は最初から `buster` 一本で通します。なお、修復目的であれば `./dvs` の実行は必須ではなく、直接 `wget http://dvswitch.org/buster` から始めることができます。`./dvs` はブログ筆者が既存の dvs メニュー環境を経由したという実作業の記録です。
- 🔶 **要検証**：手修正で行末を `bookworm` → `buster` に変えると同じ結果になる、というのは元ブログの主張です。スクリプトが配置するキーリングや署名情報が bookworm 実行時のもののまま残っていると、署名検証で別エラーが出る可能性があります。確実なのは、誤実行に気づいた時点で `dvswitch.list` と関連キーリングを削除し、正しい `buster` スクリプトを実行し直して**スクリプトに再生成させる**ことです。手修正は最後の手段と考えてください。

---

## 第II部：Bookworm 環境での導入

Bookworm（Debian 12）は DVSwitch が正規対応する世代で、`bookworm` スクリプトをそのまま使えます。一方、Bookworm はネットワーク管理や Web 構成が大きく変わっており、特に Apache の DocumentRoot が「勝手に変わったように見える」点に注意します。

### II-0. Bookworm の固定 IP について

> 🔶 **要検証 / 補足（元ブログに記載なし）**：Bookworm は **NetworkManager** がデフォルトです。第I部の `dhcpcd.conf` 方式は Bookworm では標準で効きません。Bookworm で固定 IP にする場合は `nmtui`（テキスト UI）または `nmcli` で接続プロファイルに静的アドレスを設定するのが標準的です。`raspi-config` → "System Options" → "Wireless LAN" 経由での設定や、`/etc/NetworkManager/system-connections/` 配下の接続ファイルを直接編集する方法も利用できます。元ブログは Bookworm 側の固定 IP 手順を扱っていないため、本書では方式の違いの指摘に留めます。実際の設定値は環境に合わせて確定してください。

### II-1. 標準導入手順

```bash
sudo su -
cd /tmp
apt update
apt upgrade
wget http://dvswitch.org/bookworm
chmod +x bookworm
./bookworm
apt update
apt install dvswitch-server analog-reflector stfu -y
```

> ✅ **公式裏取り済み**：Bookworm 上で `wget http://dvswitch.org/bookworm` → `chmod +x bookworm` → `./bookworm` → `apt update` → `apt install dvswitch-server` という流れは、複数の導入ガイドの記述と一致します。

### II-2. DocumentRoot が「勝手に変わる」ように見える理由

導入後、Web のドキュメントルートが `/var/www/html` ではなく `/usr/share/dvswitch` に切り替わることがあります。これは不具合ではなく、次の仕組みによる挙動です。

1. **VirtualHost 優先**：Debian 系はサイト設定を `sites-available` / `sites-enabled` で管理し、`VirtualHost` が優先されます。スクリプトが独自 VirtualHost を追加すると、デフォルトの `000-default.conf`（`/var/www/html`）よりそちらが有効化されることがあります。
2. **インストールスクリプトの挙動**：bookworm 向け導入で Web UI を `/usr/share/dvswitch` に配置し、Apache 側にそのパスを使う設定が入る場合があります。
3. **競合の起き方**：`sites-enabled` に複数設定があると、ポート 80 のデフォルトホストが DVSwitch 側に切り替わることがあります。

要点：**Bookworm の構成 ＋ DVSwitch 導入で VirtualHost が追加・有効化され、結果として DocumentRoot が `/usr/share/dvswitch` に切り替わる**のが想定どおりのシナリオです。

---

## 第III部：Web サーバ設定（Apache / lighttpd）

### III-1. Apache：DocumentRoot を DVSwitch に合わせる

> 適用対象は、Apache が使われている構成（主に Bookworm の一部）です。Bullseye 標準は lighttpd です（[III-3](#iii-3-lighttpd標準構成bullseye)）。

**① デフォルト VirtualHost を開く**

```bash
sudo nano /etc/apache2/sites-enabled/000-default.conf
```

**② DocumentRoot を変更**

変更前：

```apache
DocumentRoot /var/www/html
```

変更後：

```apache
DocumentRoot /usr/share/dvswitch
```

**③ Directory ディレクティブを追加**（`DocumentRoot` 行の直下）

```apache
<Directory /usr/share/dvswitch>
    Options Indexes FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>
```

**④ 保存して Apache を再起動**

```bash
sudo systemctl restart apache2
```

> ✅ **一般原則として妥当**：Debian/Ubuntu 系で VirtualHost（sites-enabled）が DocumentRoot を主導するのは Apache の標準挙動です。DVSwitch インストーラや更新で新しい設定が追加された場合はそちらが優先されるため、必要に応じて無効化・調整します。
> 🔶 **要検証**：`/usr/share/dvswitch` が当該環境の実際の Web UI 配置先かは、導入後に `ls /usr/share/dvswitch` 等で実在を確認してから設定してください（配置先はスクリプトのバージョン依存）。

### III-2. Apache：競合チェックと「勝手に変わる」対策

```bash
apache2ctl -S
```

有効な VirtualHost と DocumentRoot が一覧表示されます。不要なサイト定義は無効化します。

```bash
# 例：DVSwitch が提供したサイト定義名を無効化する場合
sudo a2dissite dvswitch.conf
sudo systemctl reload apache2
```

> 🔶 **要検証**：`dvswitch.conf` という定義名は環境依存です。**先に `ls /etc/apache2/sites-enabled/` で実際のファイル名を確認**し、無効化対象を特定してから実行してください。

### III-3. lighttpd：標準構成（Bullseye）

Bullseye 標準導入では lighttpd が使われます。設定変更後はサービスを再起動します。

```bash
sudo systemctl restart lighttpd
```

ダッシュボード表示が更新されない場合は、ブラウザで `Ctrl + F5`（ハードリロード）でキャッシュを無効化します。

---

## 第IV部：Platform 表示の修正（platformDetect.sh）

### IV-1. なぜ正しく表示する必要があるのか

DVSwitch Dashboard の「Hardware Info → Platform」が「Unknown ARM based System」のままだと、機種特定ができずトラブルシュートが長引き、保守性・構成管理が低下します。原因は、古い判定スクリプトが Raspberry Pi Zero 2 W などの新しい機種を認識できないことです。解決策は、Raspberry Pi が提供する **Device Tree のモデル情報**を優先的に使うことです。

**対象環境**

- Raspberry Pi Zero 2 W（ARMv7）
- OS：Debian GNU/Linux 11 (bullseye)
- DVSwitch Dashboard（`/var/www/html/include/system.php` を参照）
- Web サーバ：lighttpd

> 🔶 **要検証（フォールバックの BCM 判定）**：本スクリプトは Device Tree（`/proc/device-tree/model` 等）を**最優先**で読むため、実機では正しく機種名が出る設計です。ただしフォールバック節にある「`BCM2710` → Raspberry Pi Zero 2 W」のマッピングは、Pi Zero 2 W の SoC（RP3A0、内部は BCM2710A1 相当）が環境によって `/proc/cpuinfo` の `Hardware` 行に必ず `BCM2710` と出るとは限らないため、フォールバックに落ちた場合の確実性は保証できません。通常は Device Tree 優先で問題になりません。

### IV-2. 手順

**STEP 1：既存スクリプトをバックアップ**

```bash
sudo cp /usr/local/sbin/platformDetect.sh /usr/local/sbin/platformDetect.sh.bak.$(date +%F)
```

**STEP 2：新しいスクリプトを作成**

```bash
sudo nano /usr/local/sbin/platformDetect.sh.new
```

以下を貼り付けて保存します（POSIX sh 互換・安全版）。

```sh
#!/bin/sh
#
# platformDetect.sh - Return the board/platform name for DVSwitch Dashboard
# Safe POSIX-sh version (no bash-only features)
#

# --- Armbian: prefer BOARD_NAME if available ---
BOARD_NAME=""
if [ -r /etc/armbian-release ]; then
  . /etc/armbian-release
fi

if [ -n "$BOARD_NAME" ]; then
  echo "$BOARD_NAME"
  exit 0
fi

# --- 1) Try device-tree model (most reliable on Raspberry Pi); handle NUL-termination ---
for p in /sys/firmware/devicetree/base/model /proc/device-tree/model; do
  if [ -r "$p" ]; then
    # remove NULs and trailing spaces
    dt_model=$(tr -d '\0' < "$p" | sed 's/[[:space:]]\+$//')
    if [ -n "$dt_model" ]; then
      echo "$dt_model"
      exit 0
    fi
  fi
done

# --- 2) Try /proc/cpuinfo Model line ---
model_line=$(grep -m1 -E '^Model[[:space:]]*:' /proc/cpuinfo 2>/dev/null | sed 's/^Model[[:space:]]*:[[:space:]]*//')
if [ -n "$model_line" ]; then
  echo "$model_line"
  exit 0
fi

# --- 3) Fallback: use Hardware field with minimal mapping ---
hardware_field=$(grep -m1 -E '^Hardware[[:space:]]*:' /proc/cpuinfo 2>/dev/null | sed 's/^Hardware[[:space:]]*:[[:space:]]*//')

# Known SBCs
echo "$hardware_field" | grep -qi '^ODROID' && { echo "Odroid XU3/XU4 System"; exit 0; }

if echo "$hardware_field" | grep -qi 'sun8i'; then
  if [ -n "$BOARD_NAME" ]; then
    echo "$BOARD_NAME"
  else
    echo "sun8i based Pi Clone"
  fi
  exit 0
fi

echo "$hardware_field" | grep -qi 's5p4418' && { echo "Samsung Artik"; exit 0; }

# --- Important: BCM2710 -> Raspberry Pi Zero 2 W ---
echo "$hardware_field" | grep -qi 'BCM2710' && { echo "Raspberry Pi Zero 2 W"; exit 0; }

# --- 4) Legacy Raspberry revision mapping (best-effort) ---
model_name=$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | sed 's/.*: //')
echo "$model_name" | grep -q '^ARM' && {
  board_rev=$(grep -m1 'Revision' /proc/cpuinfo 2>/dev/null | awk '{print $3}' | sed 's/^100//')
  case "$board_rev" in
    *0002)   echo "Model B Rev 1.0 (256MB)"; exit 0;;
    *0003)   echo "Model B Rev 1.0 + ECN0001 (no fuses, D14 removed) (256MB)"; exit 0;;
    *0004)   echo "Model B Rev 2.0 (256MB)"; exit 0;;
    *0005)   echo "Model B Rev 2.0 (256MB)"; exit 0;;
    *0006)   echo "Model B Rev 2.0 (256MB)"; exit 0;;
    *0007)   echo "Model A Mounting holes (256MB)"; exit 0;;
    *0008)   echo "Model A Mounting holes (256MB)"; exit 0;;
    *0009)   echo "Model A Mounting holes (256MB)"; exit 0;;
    *000d)   echo "Model B Rev 2.0 (512MB)"; exit 0;;
    *000e)   echo "Model B Rev 2.0 (512MB)"; exit 0;;
    *000f)   echo "Model B Rev 2.0 (512MB)"; exit 0;;
    *0010)   echo "Model B+ Rev 1.0 (512MB)"; exit 0;;
    *0011)   echo "Compute Module 1 Rev 1.0 (512MB)"; exit 0;;
    *0012)   echo "Model A+ Rev 1.1 (256MB)"; exit 0;;
    *0013)   echo "Model B+ Rev 1.2 (512MB)"; exit 0;;
    *0014)   echo "Compute Module 1 Rev 1.0 (512MB)"; exit 0;;
    *0015)   echo "Model A+ Rev 1.1"; exit 0;;
    *900021) echo "Model A+ Rev 1.1 (512MB)"; exit 0;;
    *900032) echo "Model B+ Rev 1.2 (512MB)"; exit 0;;
    *900092) echo "Pi Zero Rev 1.2 (512MB)"; exit 0;;
    *900093) echo "Pi Zero Rev 1.3 (512MB)"; exit 0;;
    *9000c1) echo "Pi Zero W Rev 1.1 (512MB)"; exit 0;;
    *9020e0) echo "Pi 3 Model A+ (512MB) - Sony, UK"; exit 0;;
    *920092) echo "Pi Zero Rev 1.2 (512MB)"; exit 0;;
    *920093) echo "Pi Zero Rev 1.3 (512MB)"; exit 0;;
    *900061) echo "Compute Module 1 Rev 1.1"; exit 0;;
    *a01040) echo "Pi 2 Model B (1GB) - Sony, UK"; exit 0;;
    *a01041) echo "Pi 2 Model B (1GB) - Sony, UK"; exit 0;;
    *a02082) echo "Pi 3 Model B (1GB) - Sony, UK"; exit 0;;
    *a020a0) echo "Compute Module 3 Rev 1.0 (1GB)"; exit 0;;
    *a020d3) echo "Pi 3 Model B+ (1GB) - Sony, UK"; exit 0;;
    *a21041) echo "Pi 2 Model B (1GB) - Embest, CH"; exit 0;;
    *a22042) echo "Pi 2 Model B (1GB) - Embest, CH"; exit 0;;
    *a22082) echo "Pi 3 Model B (1GB) - Embest, CH"; exit 0;;
    *a220a0) echo "Compute Module 3 Rev 1.0 (1GB)"; exit 0;;
    *a32082) echo "Pi 3 Model B (1GB) - Sony, JPN"; exit 0;;
    *a52082) echo "Pi 3 Model B (1GB) - Stadium"; exit 0;;
    *a22083) echo "Pi 3 Model B (1GB) - Embest"; exit 0;;
    *a02100) echo "Compute Module 3+ Rev 1.0 (1GB)"; exit 0;;
    *a03111) echo "Pi 4 Model B (1GB) - Sony, UK"; exit 0;;
    *b03111) echo "Pi 4 Model B (2GB) - Sony, UK"; exit 0;;
    *c03111) echo "Pi 4 Model B (4GB) - Sony, UK"; exit 0;;
    *b03112) echo "Pi 4 Model B Rev 1.2 (2GB) - Sony, UK"; exit 0;;
    *c03112) echo "Pi 4 Model B Rev 1.2 (4GB) - Sony, UK"; exit 0;;
    *d03114) echo "Pi 4 Model B Rev 1.4 (8GB)"; exit 0;;
  esac
}

# --- 5) Final fallback: generic arch label ---
echo "Generic $(uname -m) class computer"
exit 0
```

**STEP 3：権限を付与**

```bash
sudo chmod 0755 /usr/local/sbin/platformDetect.sh.new
```

**STEP 4：動作確認**

```bash
/usr/local/sbin/platformDetect.sh.new
# → Raspberry Pi Zero 2 W Rev 1.0（Device Tree から取得される想定）

sudo -u www-data /usr/local/sbin/platformDetect.sh.new
# → 同じ結果ならOK
```

`www-data` での確認が重要なのは、ダッシュボード（Web サーバ）が `www-data` 権限でこのスクリプトを呼ぶためです。直接実行は通るのに `www-data` で空になる場合、`/proc/device-tree/model` 等の読み取り権限や PHP の `exec()` 制限が原因です。

**STEP 5：置き換え**

```bash
sudo mv /usr/local/sbin/platformDetect.sh.new /usr/local/sbin/platformDetect.sh
```

**STEP 6：Web サーバ再起動**

```bash
sudo systemctl restart lighttpd
```

**STEP 7：Dashboard をハードリロード**

ブラウザで `Ctrl + F5`。「Hardware Info → Platform」に正しい機種名（例：Raspberry Pi Zero 2 W Rev 1.0）が表示されれば成功です。

---

## 第V部：トラブルシュート＆失敗・修復事例

### V-1. bookworm スクリプトを誤実行（Bullseye）

**症状**：`apt install` で DVSwitch 関連パッケージが見つからない／依存関係が崩れる。
**原因**：Bullseye（Debian 11）に bookworm（Debian 12）用リポジトリが登録されている。
**修復**：[第I部・別記](#第i部別記実際に起きたことbookworm-経由--buster-修復ログ)を参照。推奨は、`dvswitch.list` と関連キーリングを削除し、正しい `buster` スクリプトを実行し直してスクリプトに再生成させる方法です。

### V-2. Platform が「Unknown ARM based System」のまま

| チェック項目 | コマンド／対処 |
|---|---|
| PHP の `exec()` が無効 | `php.ini` の `disable_functions` に `exec` が含まれていないか確認 |
| 権限問題 | `sudo -u www-data /usr/local/sbin/platformDetect.sh` を実行しエラー確認 |
| dash 非互換 | 本スクリプトは POSIX 互換のため dash でも動作。旧版に bash 専用構文が残っていないか確認 |
| ブラウザキャッシュ | `Ctrl + F5` でハードリロード |
| Device Tree 読めない | `cat /proc/device-tree/model` が読めるか、`www-data` で読めるかを確認 |
| AppArmor/SELinux | Raspberry Pi OS Lite は標準で無効だが、カスタム環境では `/proc/device-tree/model` へのアクセスが制限されることがある。`aa-status` または `sestatus` で確認 |

### V-3. WebUI にアクセスできない

- リッスンポートとプロセスを確認：`sudo ss -tlnp | grep -E ':(80|443|2812)'`
- Web サーバ稼働確認：`sudo systemctl status lighttpd`（または `apache2`）
- 固定 IP 設定ミス：`ip addr` で実 IP を確認し、設定ファイルと一致しているか確認
- URL は実機のリッスンポートに合わせて確定（[I-6 の 🔶 要検証](#i-6-webui-へのアクセス)参照）

### V-4. Bookworm で DocumentRoot が想定と違う

- `apache2ctl -S` で有効 VirtualHost と DocumentRoot を確認
- `ls /etc/apache2/sites-enabled/` で実ファイル名を確認 → 不要定義を `a2dissite <実名>.conf` で無効化 → `sudo systemctl reload apache2`
- Web UI の実配置先を `ls /usr/share/dvswitch` 等で確認してから DocumentRoot を設定

---

## 第VI部：要検証項目一覧（確定作業用）

実機で確認し、確定値に置き換えてから運用・公開してください。

| # | 項目 | 確認コマンド／方法 | 確定したら反映する箇所 |
|---|---|---|---|
| 1 | Bullseye で buster 流用が依存解決できるか | `apt install dvswitch-server analog-reflector stfu` がエラーなく完了するか | §3、I-3 |
| 2 | `./buster` 後の順序（`apt update` で Release 変更エラーが出るか） | `./buster` 後に `apt update` を実行し挙動を確認 | I-3 |
| 3 | `dvswitch.list` の実際の codename・コンポーネント・キーリングパス（`signed-by=` のパスが `/usr/share/keyrings/` か `/etc/apt/trusted.gpg.d/` かも必ず確認） | `cat /etc/apt/sources.list.d/dvswitch.list` | I-5 |
| 4 | ダッシュボードの実リッスンポート（80 か 2812 か他か） | `sudo ss -tlnp \| grep -E ':(80\|443\|2812)'` | I-6、V-3 |
| 5 | Web UI の実配置ディレクトリ | `ls /usr/share/dvswitch`（無ければ `/var/www/html` 等を確認） | III-1、III-2 |
| 6 | Apache サイト定義の実ファイル名 | `ls /etc/apache2/sites-enabled/` | III-2、V-4 |
| 7 | OS イメージ名・配置（ミラー側） | ミラーの `raspios_oldstable_lite_armhf` を実確認 | I-1 |
| 8 | platformDetect.sh の出力（Device Tree 経路で機種名が出るか） | `/usr/local/sbin/platformDetect.sh` と `sudo -u www-data` 版 | IV-2 |
| 9 | Bookworm の固定 IP 設定方式（NetworkManager） | `nmcli`/`nmtui` で静的化できるか | II-0 |

---

## 付録：チェックリスト

### Bullseye 導入チェック（推奨手順）

- [ ] OS は Raspberry Pi OS Lite（Bullseye / armhf）
- [ ] 固定 IP（`dhcpcd.conf`）を設定済み
- [ ] `apt update && apt upgrade` 済み（必要なら再起動）
- [ ] **最初から** `wget http://dvswitch.org/buster` を使用（bookworm を踏んでいない）
- [ ] `./buster` 実行 → `apt update`
- [ ] `apt install dvswitch-server analog-reflector stfu` 完了（🔶要検証#1）
- [ ] `dvswitch.list` の内容を確認（手修正せずスクリプト生成値を確認）（🔶要検証#3）
- [ ] 実リッスンポートを確認し WebUI URL を確定（🔶要検証#4）

### bookworm 誤実行からの復旧チェック

- [ ] 誤って bookworm を実行したことを確認
- [ ] `dvswitch.list` と関連キーリングを削除
- [ ] 正しい `buster` スクリプトを実行し直し（スクリプトに再生成させる）
- [ ] `apt update` → `apt install …` 再実行

### Bookworm 導入チェック

- [ ] `wget http://dvswitch.org/bookworm` を使用
- [ ] 固定 IP は NetworkManager（nmtui/nmcli）で設定（🔶要検証#9）
- [ ] `apache2ctl -S` で DocumentRoot を確認
- [ ] Web UI 実配置先を確認のうえ DocumentRoot を設定（🔶要検証#5）
- [ ] `<Directory …>` ディレクティブ追加
- [ ] 競合サイト定義を実ファイル名で特定し無効化（🔶要検証#6）

### Platform 表示修正チェック

- [ ] 既存 `platformDetect.sh` をバックアップ
- [ ] POSIX 互換版を `.new` で作成 → 権限 0755
- [ ] 直接実行と `www-data` 実行で同じ結果（🔶要検証#8）
- [ ] 本体に置き換え → Web サーバ再起動 → ハードリロード
- [ ] Platform に正しい機種名が表示

---

*本マニュアルは JJ2YYK 氏のブログ記事 4 本（2025年12月）を統合・再構成し、DVSwitch 公式ドキュメントおよび公式 System-Builder の記述で裏取りのうえ、検証未確定箇所を明示したものです。公開・運用前に第VI部の要検証項目を実機で確定してください。*
