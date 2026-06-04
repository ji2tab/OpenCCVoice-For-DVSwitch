# DVSwitch + OpenCCVoice 自動音声応答システム 構築手順書（検証済み版 v2）

**対象機:** Raspberry Pi Zero 2W
**OS:** Raspberry Pi OS (Legacy, 32-bit) Lite — Debian Bookworm ベース
**ホスト名:** OCV / **ユーザー:** ocv
**コールサイン:** JJ2YYK（DMR ID 440239652）
**接続先:** TGIF Network TG 44833
**初版検証日:** 2026-06-02 / **v2 追記日:** 2026-06-03 / **v3 追記日:** 2026-06-04

---

## このドキュメントの位置づけ

本書は実機 OCV 上で**実際に最後まで通した作業ログ**に基づく。各手順には次の印を付けた。

- ✅ **検証済み** — このセッションで実行し、想定どおり動作した
- ⚠️ **要注意** — 公開ドキュメントの記載と実機が食い違っていた箇所（実機の値が正）
- 🔴 **重大** — ここを外すとシステムが成立しない決定的ポイント

ユーザー名は、配布ドキュメントでは `pi-star` だが、本機は `ocv` である。以下すべて `ocv` で記載する。別ユーザーで構築する場合は読み替えること。

> **v2 での主な追記（2026-06-03 のトレースで判明）**
> - **第4.5部** を新設：Quantar_Bridge ほかが Web ダッシュボードで「Does not exist」と
>   表示される問題と、その対処（monit の httpd 設定有効化＋サービス起動）を追加した。
>   これは OS 世代（Bookworm / trixie）に関係なく、DVSwitch インストール直後の素の状態で
>   発生する。trixie のせいではない点に注意。
> - **第1部** に、OS を Bookworm に固定するための sources.list 確認手順を追記した
>   （誤って trixie へ上げないため）。
> - **第1-1部** に、OS イメージ（bookworm 版）の直リンク（複数ミラー）と
>   リンク切れ時の探し方、SHA256 照合手順を追記した。
>
> **v3 での主な変更（2026-06-04 のトレースで判明）**
> - **第2部を実作業順に再構成**：2-3（dvs 初期設定で ini 生成）→ 2-4（dvs 詳細設定で
>   TGIF 切替）→ 2-5（`dvs_config.sh` で TGIF 用の値を確定）の順に並べた。
>   従来は第7部にあった `dvs_config.sh` を **第2-5部に移動**（第7部は参照のみ残置）。
>   取得コマンドは `curl -fsSL` 版を採用。
> - **第6-4部** の `create_wav.sh` の取得 URL を修正（旧 `reate_wav.sh` は 404。
>   リポジトリ側で `create_wav.sh` にリネームされた）。
> - 従来の手動 ini 編集は **付録 D** に移動。TGIF ログイン確認手順も追加。
> - リポジトリに **`dvswitch_bot160.py`（V1.60）** が追加されていることを確認
>   （本手順書は引き続き V1.58 を対象とする）。
> - **第2-3部** に重要な発見を追記：`dvs` の「01 初期設定」を一度通さないと
>   `/opt/Analog_Bridge/` の ini が生成されず、`dvs_config.sh` が前提を満たせない。
>   `dvs` の全画面遷移（初期設定13ステップ＋TGIF切替）も具体的に記載した。

---

## 第0部：今回の構築で判明した「決定的な点」

後続の手順で詳述するが、再現時に必ず意識すべき急所を先に挙げる。

1. 🔴 **md380-emu を動かすには 2 つの必須操作がある（別問題・両方必要）。**
   (a) qemu-user-static を **5.2 (Bullseye版) にダウングロードし `apt-mark hold` で固定**（qemu 7.2 では SEGV）。
   (b) **`md380-emu` バイナリに `chmod +x` で実行権限を付与**（無いと `Permission denied`）。
   バイナリ自体の中身は変更しない。触るのは qemu の入れ替えと実行権限のみ。これが今回最大のハマりどころだった。

2. ⚠️ **USRP ポートは 51000 / 51001。**
   配布ドキュメントには 51000/51001 と書かれた版と 31001 単一の版が混在していたが、実際に動作した値は `rxPort = 51000` / `txPort = 51001`（Analog_Bridge 側）。ボットの送信先は **51000**。

3. ⚠️ **Open JTalk の辞書パスは `/var/lib/mecab/dic/open-jtalk/naist-jdic`。**
   配布ドキュメントの `/var/lib/mecab/dic/naist-jdic` では辞書が開けずエラーになる。

4. ⚠️ **Web ダッシュボードの「Does not exist」は monit の httpd 無効が主因。**（v2 追記）
   Quantar_Bridge などが「Does not exist」と出るのは、サービス未起動に加えて、
   **monit の httpd（port 2812）がデフォルトでコメントアウト**されており、
   monit のステータス問い合わせ自体が機能していないことが背景にある。第4.5部で対処する。

5. ⚠️ **OS は Bookworm に固定する。**（v2 追記）
   `apt upgrade` 自体ではディストリは上がらないが、sources.list が trixie を指していると
   trixie に上がってしまい、monit などの挙動が手順書（Bookworm 前提）と食い違う。
   第1部で sources.list が bookworm であることを必ず確認する。

---

## 第1部：OS 準備

### 1-1. OS 書き込み・初回起動 ✅

Raspberry Pi OS (Legacy, 32-bit) Lite を書き込み、起動。SSH 等で接続する。

Raspberry Pi Imager では **「Raspberry Pi OS Lite (Legacy, 32-bit)」**
（"A port of Debian Bookworm ..." と表示されるもの）を選ぶ。"Legacy" の付かない
最新版は trixie の可能性があるため注意。

#### OS イメージ直リンク（v2 追記）

Pi Imager のラインナップから取れなくなった場合に備え、イメージの直リンクを控えておく。
本検証で使用したのは **`2025-05-13-raspios-bookworm-armhf-lite.img.xz`**（約 493MB）。
**ファイル名に `bookworm` が含まれるもの**を必ず選ぶこと（`trixie` 版は手順書とズレる）。

ミラー（いずれか到達できるものを使う。JAIST は国内で高速）:

```
# JAIST（北陸先端大）ミラー — 国内・高速
https://ftp.jaist.ac.jp/pub/raspberrypi/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz

# 山形大ミラー
https://ftp.yz.yamagata-u.ac.jp/pub/linux/raspberrypi/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz

# 公式（Raspberry Pi 財団）
https://downloads.raspberrypi.com/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz
```

チェックサム（同ディレクトリの `.sha256` ファイル）:

```
# JAIST
https://ftp.jaist.ac.jp/pub/raspberrypi/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz.sha256
```

> **【リンク切れ時の探し方】** 上記の固定リンクは将来失効しうる。その場合は
> 各ミラーの **`raspios_lite_armhf/images/`** 配下に入り、日付フォルダの中から
> **ファイル名に `bookworm` を含む** `...-armhf-lite.img.xz` を選ぶ。
> - `raspios_lite_armhf/` … stable（時期により bookworm → 将来 trixie に変わりうる）
> - `raspios_oldstable_lite_armhf/` … oldstable（現状 bullseye）
> 「Legacy=Bookworm」が欲しいので、**stable 側に bookworm がある間はそちら**、
> stable が trixie に切り替わった後は **oldstable 側で bookworm を探す**ことになる。

ダウンロード後（任意だが推奨）、SHA256 を照合してから書き込む:

```bash
# 例（Linux/Mac）。.sha256 ファイルと同じ場所で実行
sha256sum -c 2025-05-13-raspios-bookworm-armhf-lite.img.xz.sha256
# Windows: certutil -hashfile 2025-05-13-raspios-bookworm-armhf-lite.img.xz SHA256
```

```bash
uname -a
# Linux OCV 6.12.x+rpt-rpi-v7 ... armv7l を確認
```

### 1-2. 🔴 sources.list が bookworm であることを確認（v2 追記） ✅

`apt upgrade` の前に、リポジトリが bookworm を指していることを確認する。
ここが trixie になっていると、後続のアップグレードで OS 世代が上がってしまう。

```bash
grep -rE "bookworm|trixie" /etc/apt/sources.list /etc/apt/sources.list.d/
```

出力がすべて `bookworm` であること（`trixie` が一つも無いこと）を確認する。
併せて OS コードネームも確認しておく:

```bash
cat /etc/os-release | grep VERSION_CODENAME    # bookworm であること
```

### 1-3. システム更新 ✅

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

再起動後、カーネルが更新版（本検証では 6.12.87）で立ち上がること、
`apt update` の出力に **bookworm のみ**が出て **trixie が出ない**ことを確認する。

```bash
uname -a && cat /etc/os-release | grep VERSION_CODENAME
```

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

### 2-3. 🔴 初期設定メニュー（ini ファイル生成のために必須） ✅

メニューの実体は `dvswitch-menu` ではなく **`/usr/local/dvs/dvs`**。

```bash
sudo /usr/local/dvs/dvs
```

> 🔴 **【重要な発見・v3 追記】この初期設定（01）を一度通さないと
> `/opt/Analog_Bridge/` 配下の実体（`Analog_Bridge.ini` 等）が生成されない。**
> インストール直後は `/opt/Analog_Bridge/` の ini が無い状態のことがあり、
> この `dvs` の「01 初期設定」を完了して初めて生成される。
> したがって、後段の `dvs_config.sh`（第7部）を実行する**前提条件**として、
> ここを必ず一度通しておく必要がある。ini が無いまま `dvs_config.sh` を実行すると
> `[ERROR] 見つかりません` で止まる。

> ⚠️ **ここで入れる値の多くは後で `dvs_config.sh` が上書きする。**
> この初期設定メニューは **Brandmeister 前提**の入力フローで、USRP ポートも
> デフォルト（32001/34001）になる。本構成は **TGIF 接続・USRP 51001/51000** が
> 最終形だが、それらは第7部の `dvs_config.sh` が確定させる。
> よって**この時点では値の厳密さより「一度完走させて ini を生成すること」が目的**。
> パスワードやポートはデフォルトのまま通してよい。

#### 画面遷移（Menu Script v.1.61 / 本トレースの実際の入力）

1. **メインメニュー** → `01 初期設定`（コールサイン、DMR ID、BM Server と AMBE の入力）を選択
2. **「初めに行う設定」確認** → `Yes`（コールサイン・DMR ID 等を ini に書き込む旨）
3. **コールサイン（大文字小文字可）** → 例 `JI2TAB`
4. **CCS7/DMR ID ?** → 例 `4401378`（7桁）
5. **CCS7/DMR ID + 2桁の数（00〜99）?** → 例 `440137811`（DMR ID + ESSID 11）
6. **Dstar module ? (A〜Z)** → 例 `B`（D-STAR 未使用でも入力を求められる）
7. **NXDN ID?（エンターキーを押す）** → 空欄のまま Enter（NXDN 未使用）
8. **USRP ポート番号（50000〜55000 推奨、未記入でデフォルト）** → 空欄のまま
   （後で `dvs_config.sh` が 51001/51000 にするため、ここは未記入でよい）
9. **デフォルト確認（Analog_Bridge.ini）** → `txPort: 32001, rxPort: 34001` と表示。`Yes`
   （この時点ではデフォルト値。第7部で 51001/51000 に上書きされる）
10. **ローカル BM サーバー選択** → 一覧から選択（Brandmeister 用。TGIF 運用では
    後で `dvs_config.sh` が `Address=tgif.network` に上書きするため、ここは任意で可）
11. **Brandmeister のパスワード（エンターキーを押す）** → デフォルト `passw0rd` のまま可
    （TGIF パスワードは後で `dvs_config.sh` が設定）
12. **Hardware Vocoder (AMBE)** → **`4 ハードウェア Vocoder を使わない（ソフトウェア
    Vcoder を使う）`** を選択（md380-emu によるソフトデコードを使うため）
13. **「入力終了」確認** → `Yes`（ini files の設定が始まる）

完了後、再起動する。これで `/opt/Analog_Bridge/Analog_Bridge.ini` 等が生成され、
次の第2-5部の `dvs_config.sh` で TGIF 用の最終値に上書きできる状態になる。

---

### 2-4. ⚠️ 詳細設定で DMR サーバーを TGIF に切替（おまじない） ✅

初期設定（01）に続けて、`dvs` の **詳細設定（02）** で
デフォルト DMR サーバーを **TGIF** に切り替えておく。
後段の `dvs_config.sh` が `Address=tgif.network` を書き込むが、`dvs` メニュー側でも
TGIF を選んでおくことで、メニューが書き出す各種設定が TGIF 前提で整う。

> **【位置づけ】** 厳密な因果（どの設定値が最終的に効くか）まで切り分けてはいないが、
> 初期設定（01）と同様、**通しておくと確実**な手順として実施する。`dvs_config.sh`
> による上書きと矛盾はしない。

```bash
sudo /usr/local/dvs/dvs
```

画面遷移:

1. **メインメニュー** → `02 詳細設定`（TG/Ref管理、マクロ、DMRネットワーク）
2. **詳細設定メニュー** → `24 その他の DMR ネットワーク`（DMRPlus、TGIF、その他ネットワークの設定）
3. **DMR ネットワーク** → `1 デフォルトの DMR サーバー変更`
4. **デフォルトの DMR サーバー変更** → `2 TGIF` を選択（選択後「現在のサーバー: TGIF」になる）
5. メインメニューまで戻って `dvs` を終了

---

### 2-5. 🔴 dvs_config.sh で TGIF 用の値を確定 ✅

`dvs` の初期設定（01・02）で ini が生成・TGIF 化されたら、続けて対話ツール
**`dvs_config.sh`** で、コールサイン／DMR ID／TGIF パスワード／送信 TG／USRP ポートを
一括設定する。**この順序（dvs → dvs_config.sh）が前提**で、ini が無いまま実行すると
`[ERROR] 見つかりません` で止まる。

> 取得は `curl` でも `wget` でもよい。以下は `curl` 版。

```bash
cd ~ && curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_config.sh -o dvs_config.sh && chmod +x dvs_config.sh && cat dvs_config.sh
```

中身を確認したら実行:

```bash
sudo ./dvs_config.sh
```

このツールがすること:

- 編集前に **`/opt/bak/YYMMDDHHMMSS/`** へ 3 つの ini を自動バックアップ
  （`MMDVM_Bridge.ini` / `DVSwitch.ini` / `Analog_Bridge.ini`）
- 対話入力 5 項目：`callsign` / `dmrid(7桁)` / `essid(2桁)` / `tgifpassword` / `txtgif`
- 固定セット：
  - MMDVM `[DMR] Enable=1`、`[DMR Network] Enable=1`、`Address=tgif.network`
  - Analog `[USRP] txPort=51001` / `rxPort=51000` / `usrpAudio=AUDIO_USE_GAIN` / `tlvAudio=AUDIO_USE_GAIN`
- `Id`（MMDVM）と `repeaterID`（Analog）は **dmrid(7桁) + essid(2桁)** で組み立てる
- `gatewayDmrId`（Analog）は dmrid(7桁) をセット

オプション:

```bash
sudo ./dvs_config.sh -r     # バックアップから復元（日付フォルダを選択）
sudo ./dvs_config.sh -d     # /opt/bak/ 配下のバックアップを全削除
sudo ./dvs_config.sh -h     # ヘルプ
```

#### 対話入力の値（本トレースの実績値）

| 項目 | 入力例（本トレース） | 備考 |
|---|---|---|
| Callsign | `JI2TAB` | 自局コールサイン |
| DMR ID(7桁) | `4401378` | |
| ESSID(2桁) | `11` | |
| TGIF Password | （TGIF アカウントの値） | TGIF サイトで発行したもの |
| 送信 TG（txTg） | `44833` | ボット音声が乗る DMR TG |

確認画面で内容を確認し、`y` で保存。`/opt/bak/...` にバックアップが取られ、
3 ファイルに値が書き込まれる。

#### 設定反映（サービス再起動）と TGIF ログイン確認

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
```

TGIF への DMR ログインが成功したかをログで確認する。**MMDVM_Bridge のログは
journal ではなく日付別ログファイル**（`/var/log/mmdvm/MMDVM_Bridge-YYYY-MM-DD.log`）
に出る点に注意:

```bash
sudo tail -40 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

末尾付近に次の行が出ていればログイン成功:

```
DMR, Logged into the master successfully: tgif.network:62031
```

> ⚠️ **`dvs_config.sh` は `DVSwitch.ini` を変更しない**（バックアップのみ）。
> `exportTG` を明示設定したい場合は付録 D を参照。本トレースでは `txTg=44833`
> （Analog 側）で送信経路が確立し、ログインも成功している。

> **TGIF が 4000 に戻る件:** TGIF Network 側のダッシュボードで TG を指定しても、
> Static 設定がないと一定時間でデフォルト（4000）へ戻る。送信側（ローカル）の TG は
> `txTg` = 44833 で決まる。受信を継続したい場合は TGIF ダッシュボードで 44833 を
> Static 登録すること。

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
auto-restart を無限に繰り返す。インストール直後は `activating (auto-restart)` の表示になる。

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

# 🔴 必須：md380-emu バイナリに実行権限を付与する
#   （実行ビットが無いと Permission denied で起動しない。qemu を直しても無意味）
ls -la /opt/md380-emu/md380-emu        # 確認
sudo chmod +x /opt/md380-emu/md380-emu # 付与

sudo systemctl restart md380-emu
sudo systemctl status md380-emu --no-pager   # active (running) を確認

qemu-arm-static --version    # qemu-arm version 5.2.x になっていること
```

一括版（トレースで実際に通したワンライナー）:

```bash
wget http://archive.raspbian.org/raspbian/pool/main/q/qemu/qemu-user-static_5.2+dfsg-11+deb11u5_armhf.deb -O /tmp/qemu52.deb && sudo systemctl stop md380-emu && sudo dpkg -i /tmp/qemu52.deb && sudo apt-mark hold qemu-user-static && sudo chmod +x /opt/md380-emu/md380-emu && sudo systemctl restart md380-emu && sleep 3 && sudo systemctl status md380-emu --no-pager && qemu-arm-static --version
```

> 🔴 **この節の「必須操作」は 2 つある。両方やらないと md380-emu は動かない。**
> 1. **qemu を 5.2 へダウングレード**（＋ `apt-mark hold` で固定）… SEGV を止める
> 2. **`chmod +x` で実行権限を付与**… `Permission denied` を止める
> この 2 つは独立した別問題で、片方だけでは不十分。
> （バイナリ自体は中身を一切変更しない。触るのは qemu の入れ替えと実行権限のみ。）

> ⚠️ **この段階での running 表示は「起動できた」ことの確認に過ぎない。**
> SEGV は実際に AMBE デコードが走ったときに発生するため、`status=11/SEGV`
> が**出ないことの最終確認は、経路が開通する第8部の送信テスト後に行う**
> （本手順書の実作業でも、SEGV が発覚したのは TGIF 接続後だった）。

> **【経緯メモ】** 実作業では、qemu の SEGV に気づく前段階で、まず
> インストール直後の `md380-emu` に実行ビットが立っておらず `Permission denied` で
> つまずいた（パッケージ側の不備と思われる）。本手順書では上記コマンドブロックに
> `chmod +x` を組み込んだため独立した節は設けていないが、操作自体は省略不可。

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

## 第4.5部：ダッシュボードの赤字「Does not exist」を消す（v2 新設）

### この部で何をするか（対象と目的）

**対象:** DVSwitch ダッシュボード（`http://<IP>/` と `http://<IP>:2812/`）。
**目的:** ダッシュボード上で赤字「Does not exist」と出ているプロセス
（典型は **Quantar_Bridge**）を、緑の「OK」にする。

**この部の作業を一言でいうと:**
1. **監視役（monit）が外部から見えるようにする**（今は塞がっていて全プロセスの状態が取れない）
2. **止まっているプロセスを起動して、自動起動も有効にする**
3. **monit に状態を取り直させて、ダッシュボードを「OK」にする**

```
[現状] ダッシュボード ──見られない──▶ monit(:2812 塞がってる) ──▶ 各プロセス(一部停止)
                                                  ↓ この部で直す
[完了] ダッシュボード ──OK表示──▶ monit(:2812 開通) ──▶ 各プロセス(起動＆自動起動)
```

### なぜ「Does not exist」になるのか（原因は2つ）

赤字「Does not exist」は、独立した **2 つの原因**が重なって出ている。
**OS 世代（Bookworm / trixie）は無関係**で、DVSwitch インストール直後の素の状態で起きる。

| # | 原因 | 何が起きているか |
|---|---|---|
| 1 | **monit の Web 機能（:2812）が無効** | `/etc/monit/monitrc` の httpd 設定がコメントアウトされたまま。monit に状態を問い合わせる窓口が閉じているので、ダッシュボードはどのプロセスの状態も取得できず、軒並み「Does not exist」になる |
| 2 | **プロセス自体が停止＋自動起動オフ** | 例えば `quantar-bridge` はパッケージは入っていても `quantar_bridge.service` が停止・`disabled`。プロセスが実在しないので、当然「無い」と表示される |

> **【誤解の整理】** v1 検証時は trixie 環境で初めて気づいたため「trixie のせい」と
> 疑ったが、Bookworm のクリーン環境でも同様に起きることを 2026-06-03 に確認した。
> 原因は OS 世代ではなく、上記 2 点。

---

### ステップ1：原因1を直す前に「症状」を確認する ✅

**目的:** monit の窓口が本当に閉じているかを、エラーメッセージで確認する。

```bash
sudo monit status
```

→ **`Error receiving data -- Connection reset by peer`** が出れば、monit の Web 機能が
無効（原因1が該当）。次のステップで開通させる。

---

### ステップ2：原因1を直す — monit の Web 機能（:2812）を開通させる 🔴

**目的:** monit に状態を問い合わせる窓口（port 2812）を開け、LAN 内のブラウザから
ダッシュボードを見られるようにする。

**まず現状の該当行と行番号を確認**（行番号は環境で前後するので必ず確認する）:

```bash
sudo grep -nE "set httpd|use address|allow localhost|allow admin" /etc/monit/monitrc
```

標準状態では次の 4 行がコメントアウトされている（先頭が `#`）:

```
159:#set httpd port 2812 and
160:#    use address localhost  # only accept connection from localhost ...
161:#    allow localhost        # allow localhost to connect to the server and
162:#    allow admin:monit      # require user 'admin' with password 'monit'
```

**この4行を、LAN内からパスワードなしで開ける設定に置き換える**
（`grep` で見えた実際の行番号に合わせること。下記は 159〜162 の例）:

```bash
sudo sed -i '159,162c\
set httpd port 2812 and\
    use address 0.0.0.0\
    allow localhost\
    allow 192.168.1.0/24' /etc/monit/monitrc
```

**書き換え結果を確認:**

```bash
sudo sed -n '159,162p' /etc/monit/monitrc
```

期待する内容（4行とも先頭の `#` が消えている）:

```
set httpd port 2812 and
    use address 0.0.0.0
    allow localhost
    allow 192.168.1.0/24
```

**各行の意味（なぜこの値か）:**

| 行 | 意味 | この値にする理由 |
|---|---|---|
| `set httpd port 2812 and` | monit の Web 機能を 2812 番で有効化 | これが無効だと窓口が閉じたまま |
| `use address 0.0.0.0` | 全ネットワーク面で待ち受け | `localhost` だと **PC のブラウザ（外部IP）から開けない** |
| `allow localhost` | ローカルからの接続を許可 | 本体内からの監視用 |
| `allow 192.168.1.0/24` | LAN からパスワードなしで許可 | LAN 内運用のため。**自分の LAN が別セグメントなら変更**（例 192.168.0.0/24） |

> ⚠️ **パスワードを掛けたい場合:** `allow 192.168.1.0/24` を入れず、代わりに
> `allow admin:monit`（ユーザー admin / パスワード monit）を使う。セキュリティ的には
> こちらが本来望ましい。LAN 内限定運用ならパスワードなしでも実用上は可。

> ⚠️ **`use address localhost` のままにしない:** これだと monit は 127.0.0.1 だけで
> 待ち受け、`http://192.168.1.74:2812/` のような外部 IP から開けなくなる。
> 開けなくなったら `use address 0.0.0.0` に直して `sudo monit reload`。

---

### ステップ3：原因2を直す — 止まっているプロセスを起動する 🔴

**目的:** 「Does not exist」だった当該サービス（例 Quantar_Bridge）を起動し、
再起動後も自動で上がるようにする（`enable` ＝自動起動、`--now` ＝今すぐ起動）。

```bash
sudo systemctl enable --now quantar_bridge
```

> 他のプロセスが対象なら、`quantar_bridge` の部分をそのサービスの systemd ユニット名に
> 置き換える。

---

### ステップ4：monit に状態を取り直させて「OK」を確認する ✅

**目的:** ここまでの変更（窓口開通＋プロセス起動）を monit に反映させ、
ダッシュボードが「OK」になることを確認する。

```bash
sudo systemctl restart monit && sleep 8 && sudo monit reload && sleep 12 && sudo monit status Quantar_Bridge
```

→ `status  OK` と出れば成功。ブラウザで `http://<IP>:2812/` を開くと、当該プロセスが
緑の「OK」になり、パスワードなしで表示される。

> **【ハマりどころ】**
> - **すぐ確認すると「Does not exist」のまま**に見えることがある。monit は状態収集に
>   少し時間がかかるため、`reload` 後 **十数秒待って**から `sudo monit status` を見る
>   （上のコマンドは `sleep` で待ち時間を入れてある）。
> - **`:2812` が外部から開けない** → ステップ2の `use address` が `localhost` に
>   なっていないか確認し、`0.0.0.0` に直して `sudo monit reload`。

---

### 補足：使わないプロセスが「Does not exist」のままでも

Quantar_Bridge 以外（未使用モードのゲートウェイ等）が「Does not exist」でも、
**使う予定がなければ実害はない**。ただし将来使うものは、ステップ3・4と同じ手順
（`enable --now` ＋ `monit reload`）で起動・監視下に置く。

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
wget https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/create_wav.sh -O create_wav.sh
chmod +x create_wav.sh
sudo ./create_wav.sh
```

> ⚠️ **【v3 修正】ファイル名は `create_wav.sh`。**
> 初版検証時はリポジトリ上のファイル名が `reate_wav.sh`（先頭 c 欠落）だったが、
> 2026-06-04 のトレース時点で **`create_wav.sh` にリネーム**されていた。
> 旧 URL（`reate_wav.sh`）は **404** になる。最新のファイル名はリポジトリ直下で
> `curl -s https://api.github.com/repos/ji2tab/OpenCCVoice-For-DVSwitch/contents/ | grep '"name"'`
> で確認できる。

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

## 第7部：DVSwitch 側の経路・TG 設定（→ 第2-5部に統合）

> **【v3 で移動】** DVSwitch 側の設定（`dvs_config.sh` による一括設定）は、
> 実作業の順序（`dvs` で ini 生成 → 直後に `dvs_config.sh` で上書き）に合わせ、
> **第2-5部** に移動した。`dvs` の初期設定（2-3）・TGIF 切替（2-4）に続けて
> 2-5 で `dvs_config.sh` を流す流れになっている。

音声の流れ（参考・再掲）:
**ボット → (USRP 51000) → Analog_Bridge → (TLV) → MMDVM_Bridge → TGIF**

- DVSwitch 側の対話設定 → **第2-5部**
- 手動 ini 編集（旧第7部の内容） → **付録D**

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

第3-2部でダウングレードした qemu の効果を、ここで**実際のデコードを走らせて確定**する。
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

### 9-1. 常駐化後のログの見方（手動起動時の画面出力の代わり）

**手動起動（`python3 ~/dvswitch_bot158.py`）では、カーチャンク検知や送信ログが
ターミナル画面にリアルタイム表示**されていた。常駐化すると bot はバックグラウンドで
動くため画面には出なくなり、**出力は journal に記録される**（unit 定義の
`StandardOutput=journal` / `StandardError=journal` による）。

つまり「画面で見ていたもの」は消えるのではなく journal に移る。以下で確認する。

**リアルタイム監視（旧・画面表示の代わり。これを常用する）:**

```bash
sudo journalctl -u dvswitch-bot -f
```

`-f` は `tail -f` 相当。カーチャンク検知・定時放送などが流れてくるのを
そのまま眺められる。終了は `Ctrl+C`（bot は止まらず、ログ表示だけ終わる）。

**直近のログをまとめて見る:**

```bash
sudo journalctl -u dvswitch-bot -n 50 --no-pager
```

**今日のログだけ／時間で絞る:**

```bash
sudo journalctl -u dvswitch-bot --since today --no-pager
sudo journalctl -u dvswitch-bot --since "1 hour ago" --no-pager
```

**サービスの稼働状態（落ちていないか）:**

```bash
sudo systemctl status dvswitch-bot --no-pager
```

> **【bot 独自のログファイルがある場合】**
> `dvswitch_bot158.py` は Python の `logger` を使っており、journal とは別に
> **独自のログファイル**へ書いている可能性がある（V2.0 系ではログローテーションの
> 仕組みも持つ）。その場合は journal と併せてそのファイルも確認する。場所はスクリプトの
> ログ設定で決まるので、不明なときは次で確認:
> ```bash
> grep -nE "logging|FileHandler|basicConfig|filename=" ~/dvswitch_bot158.py
> ```
> ログファイルが判明したら `tail -f <そのパス>` で同様にリアルタイム監視できる。

### 9-2. 手動起動に戻して画面で見たいとき

デバッグ等で再び画面出力を見たいときは、いったん常駐を止めてから手動起動する
（常駐したまま手動起動すると二重起動になり、USRP 送信が重なるため）。

```bash
sudo systemctl stop dvswitch-bot      # 常駐を一時停止
python3 ~/dvswitch_bot158.py          # 画面出力で手動起動（Ctrl+C で終了）
```

確認が済んだら常駐に戻す:

```bash
sudo systemctl start dvswitch-bot
```

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
| md380-emu 実行権限 | （記載なし） | `chmod +x` 必須（3-2 に統合） | 🔴 |
| qemu-user-static | （記載なし） | 5.2 へダウングレード＋hold | 🔴 |
| Apache DocumentRoot | （記載なし） | /usr/share/dvswitch | ⚠️ |
| 送信 TG | （環境依存） | txTg / exportTG = 44833 | 🔴 |
| **monit httpd（:2812）** | **（記載なし）** | **デフォルト無効。有効化が必要（第4.5部）** | **🔴**（v2追記） |
| **Quantar_Bridge 等のサービス** | **（記載なし）** | **disabled・未起動。`enable --now` が必要（第4.5部）** | **🔴**（v2追記） |
| **OS 世代** | **（記載なし）** | **bookworm に固定。sources.list 確認（第1部）** | **⚠️**（v2追記） |
| **DVSwitch 側設定** | **手動 ini 編集** | **`dvs_config.sh` で一括設定（第2-5部）。手動は付録D** | **⚠️**（v3変更） |
| **DMR サーバー TGIF 切替** | **（記載なし）** | **dvs 詳細設定02→24→TGIF（第2-4部）** | **⚠️**（v3追記） |
| **create_wav.sh の URL** | **`reate_wav.sh`** | **`create_wav.sh` にリネーム（旧URLは404）** | **⚠️**（v3修正） |
| **dvs 初期設定の必須性** | **（記載なし）** | **「01初期設定」完走で初めて /opt/Analog_Bridge の ini が生成（第2-3部）** | **🔴**（v3追記） |

## 付録B：トラブルシューティング早見表

| 症状 | 原因 | 対処 |
|---|---|---|
| md380-emu が `Permission denied` | 実行ビット無し | `sudo chmod +x /opt/md380-emu/md380-emu` |
| md380-emu が `status=11/SEGV` を繰り返す | qemu 7.2 のユーザーモード不具合（Debian Bug #1014177 / #1053101）。md380-emu の静的 ARM バイナリが影響を受ける | qemu 5.2 へダウングレード＋`apt-mark hold`（詳細は別資料「公式マニュアルとの差分」） |
| Open JTalk が `Cannot open ... naist-jdic` | 辞書パス誤り | `/var/lib/mecab/dic/open-jtalk/naist-jdic` を使う |
| `http://<IP>/` が Apache 既定ページ | DocumentRoot 未変更 | `/usr/share/dvswitch` に変更 |
| 音声は出るが TG が 4000 に戻る | TGIF 側 Static 未設定 | TGIF ダッシュボードで 44833 を Static 登録 |
| ボット音声が無音 | md380-emu 停止 or Analog_Bridge 設定 | md380-emu 稼働確認、USRP ポート確認 |
| **ダッシュボードで Quantar_Bridge 等が「Does not exist」** | **monit httpd 無効＋サービス未起動** | **第4.5部：monitrc の httpd 有効化＋`systemctl enable --now`＋`monit reload`** |
| **`sudo monit status` が `Connection reset by peer`** | **monit httpd（:2812）がコメントアウト** | **monitrc の httpd ブロックを有効化（第4.5-2）** |
| **`:2812` が外部 IP から開けない** | **`use address localhost` になっている** | **`use address 0.0.0.0` に変更して `sudo monit reload`** |
| **`monit reload` 後も「Does not exist」のまま** | **monit のデータ収集待ち** | **十数秒待って再度 `sudo monit status`** |

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

## 付録D：DVSwitch 側 ini の手動編集（旧第7部・参照用）

第7部は `dvs_config.sh` による一括設定を本手順とした。
ここでは、スクリプトを使わず手動で ini を編集する場合、またはスクリプトが
想定外の ini 構成に当たって `[WARN] キー ... が見つからず変更できません` を出した
場合の参照用に、初版で行っていた手動設定を残す。

各値は環境に合わせて読み替えること（本例では送信 TG = 44833）。

### D-1. Analog_Bridge.ini（USRP / 送信 TG）

`/opt/Analog_Bridge/Analog_Bridge.ini`

```ini
[USRP]
address = 127.0.0.1
txPort = 51001        ; Analog_Bridge → 外部（USRP送信）
rxPort = 51000        ; 外部 → Analog_Bridge（ボットはここへ送る）
```

`[AMBE_AUDIO]` セクションの送信 TG:

```ini
[AMBE_AUDIO]
txTg = 44833          ; ★ボット音声が乗る DMR TG（最重要）
txTs = 2
colorCode = 1
```

> **補足:** `gatewayDmrId` / `repeaterID` は運用するコールサイン／DMR ID に合わせる。
> `dvs_config.sh` はこの 2 つを dmrid(7桁) / dmrid+essid で自動設定する。

### D-2. DVSwitch.ini（DMR exportTG）

`/opt/MMDVM_Bridge/DVSwitch.ini` の `[DMR]`:

```ini
[DMR]
address = 127.0.0.1
exportTG = 44833      ; ★エクスポート TG
```

> ⚠️ **`dvs_config.sh` はこの `DVSwitch.ini` を変更しない**（バックアップのみ）。
> exportTG を明示的に設定したい場合は、この付録に従って手動で編集する。

### D-3. MMDVM_Bridge.ini（TGIF 接続）

`dvs_config.sh` を使わない場合、TGIF への DMR 接続情報も手動で設定する:

```ini
[DMR]
Enable=1

[DMR Network]
Enable=1
Address=tgif.network
Password=（TGIF のパスワード）
```

`[General]` の `Callsign` と `Id`（dmrid + essid）も自局の値にする。

### D-4. 設定反映

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
```

---

*初版作成: 2026-06-02*
*v2 更新: 2026-06-03（第4.5部 Quantar_Bridge 対処、第1部 OS固定確認、OSイメージ直リンクを追記）*
*v3 更新: 2026-06-04（第2部を実作業順に再構成：2-3 dvs初期設定→2-4 TGIF切替→2-5 dvs_config.sh。dvs_config.sh を第7部から第2-5部へ移動し curl 版に。create_wav.sh のファイル名修正、TGIF ログイン確認手順を追加、dvs の全画面遷移を追記、手動編集を付録Dへ移動、第4.5部を目的明確化で改稿、第9部に常駐化後のログ確認手順を追加）*
*対応 bot: dvswitch_bot158.py V1.58（リポジトリに V1.60=dvswitch_bot160.py も存在）/ 実機: OCV (Zero 2W, Bookworm 32-bit)*
