# OpenCCVoice for DVSwitch 構築・導入・設定 完全マニュアル

**自動音声応答（デジピーター）システム — Bookworm + DVSwitch-Server 版**

---

> **このマニュアルの位置づけ**
>
> Raspberry Pi Zero 2 W（Raspberry Pi OS Bookworm 32-bit）上に DVSwitch-Server を構築し、
> DMR ネットワーク（TGIF）で自動音声応答を行うシステム「**OpenCCVoice for DVSwitch**」の、
> **新規構築から運用までを通しで再現できる実務マニュアル**です。
>
> すべて実機（ホスト名 OCV）で検証済みの手順に基づきます。**手順とその理由を簡潔に**記載し、
> 設計思想・開発秘話・試行錯誤の背景は別冊『開発ノート（ブログ材料）』に分離しています。
>
> **対象構成:**
> - OS: Raspberry Pi OS (Legacy, 32-bit) Lite — Debian Bookworm ベース
> - ユーザー: `ocv`（配布ドキュメントの `pi-star` は読み替え）
> - `ocv` 以外のユーザー名で構築する場合: 本書中の `chown ocv:ocv`、systemdユニットの `User=ocv`、`/home/ocv/` を含むパスなど、`ocv` と書かれている箇所はすべて実際に使用するユーザー名に読み替えること
> - Bot: デーモン本体 `dvswitch_bot.py` ＋ 設定ツール `bot_setup.py`（分離構成）
> - スクリプト配置: `/opt/dvswitch_bot/bin/` に集約
> - 接続先: TGIF Network

**凡例:** ✅ 検証済み ／ ⚠️ 要注意（実機の値が正） ／ 🔴 重大（外すと成立しない）

---

## 目次

### 第1章：準備
- [1. システムの全体像](#1-システムの全体像)
- [2. 事前準備チェックリスト](#2-事前準備チェックリスト)
- [3. 専門用語ミニ辞典](#3-専門用語ミニ辞典)
- [4. 構築の急所（先に知っておくべき決定的ポイント）](#4-構築の急所)

### 第2章：OS と DVSwitch-Server
- [5. OS 準備](#5-os-準備)
- [6. ネットワーク（固定 IP）](#6-ネットワーク固定-ip)
- [7. DVSwitch-Server インストール](#7-dvswitch-server-インストール)
- [8. dvs 初期設定（ini 生成）と TGIF 切替](#8-dvs-初期設定ini-生成と-tgif-切替)

### 第3章：設定とサービス
- [9. スクリプト一式の取得（bin/ 集約）](#9-スクリプト一式の取得)
- [10. dvs_config.sh で TGIF 用の値を確定](#10-dvs_configsh-で-tgif-用の値を確定)
- [11. サービス起動確認と md380-emu 修正](#11-サービス起動確認と-md380-emu-修正)
- [12. Monit Service Manager（:2812）の表示修正](#12-monit-service-manager2812の表示修正)
- [13. DVSwitch Dashboard（:80）の表示設定](#13-dvswitch-dashboard80の表示設定)

### 第4章：音声と Bot
- [14. 音声合成環境（Open JTalk + SoX）](#14-音声合成環境open-jtalk-sox)
- [15. 固定 WAV の作成](#15-固定-wav-の作成)
- [16. 送信テスト](#16-送信テスト)
- [17. Bot 本体と設定ツールの導入](#17-bot-本体と設定ツールの導入)
- [18. 常駐化（systemd）](#18-常駐化systemd)

### 第5章：運用
- [19. 設定変更・音声差し替え・バックアップ](#19-設定変更音声差し替えバックアップ)
- [20. 運用上の注意と法令遵守](#20-運用上の注意と法令遵守)
- [21. システム全体のバックアップとリストア](#21-システム全体のバックアップとリストア)
- [22. Web ダッシュボード（OpenCCVoice for DVSwitch Web Dashboard）](#22-web-ダッシュボード)

### 付録
- [付録A：トラブルシューティング早見表](#付録aトラブルシューティング早見表)
- [付録B：固定 WAV の個別コマンド生成](#付録b固定-wav-の個別コマンド生成)
- [付録C：DVSwitch 側 ini の手動編集（参照用）](#付録cdvswitch-側-ini-の手動編集参照用)
- [付録D：ダッシュボードの Platform 表示を正す](#付録dダッシュボードの-platform-表示を正す)
- [付録E：クイックリファレンス](#付録eクイックリファレンス)

> **最短ルート（クリーン構築）:** 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 →
> 15 → 16 → 17 → 18。22 は任意。付録は参照用。

---

# 第1章：準備

## 1. システムの全体像

音声を DMR ネットワークへ流すとき、データは次の順でバケツリレーされる。

```
┌─────────────────────┐
│  dvswitch_bot.py    │  ← ログ監視・WAV 送信
└──────────┬──────────┘
           │ USRP プロトコル (UDP 51000)
           ▼
┌─────────────────────┐
│   Analog_Bridge     │  ← 音声プロトコル変換ゲートウェイ
└──────────┬──────────┘
           │ AMBE 変換 (UDP 2470)
           ▼
┌─────────────────────┐
│     md380-emu       │  ← PCM ⇔ AMBE ソフトウェア変換
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│   MMDVM_Bridge      │  ← TGIF ネットワークへの橋渡し
└──────────┬──────────┘
           │ DMR (UDP 62031)
           ▼
        TGIF Network
```

| コンポーネント | 役割 | 重要度 |
|---|---|---|
| `dvswitch_bot.py` | ログ監視・カーチャンク検知・WAV 送信 | 🔴 必須 |
| `analog_bridge` | 音声プロトコル変換ゲートウェイ | 🔴 必須 |
| `md380-emu` | PCM ⇔ AMBE ソフトウェアコーデック | 🔴 必須 |
| `mmdvm_bridge` | TGIF（DMR ネットワーク）接続中核 | 🔴 必須 |
| `webproxy` | ダッシュボード補助 | 補助 |

> `dvswitch-server` という単体サービスは存在しない（メタパッケージ）。実体は上記ユニット群。

**このシステムができること:**
1. カーチャンク自動応答（短い PTT を検知して自局名を応答）
2. 毎正時の時報（任意で毎30分の案内も追加可。`TIME_SIGNAL_MODE` で切替）
3. 起動アナウンス（起動の数秒後に「起動しました。」を1回送出）
4. 定時メッセージ（001/002 を交互送出）
5. ナイトモード（夜間は時報・定時を抑制。カーチャンク応答は24時間動作）
6. ログローテーション自動追従（日付が変わっても監視を継続）
7. watchdog 擬似終端救済（SFR 中継で終端が落ちた送信も拾ってカーチャンク応答）

## 2. 事前準備チェックリスト

### ハードウェア
- [ ] Raspberry Pi Zero 2 W（起動・SSH 接続可）
- [ ] microSD カード（16GB 以上、Class 10 推奨）
- [ ] 電源（5V 2.5A 以上）

### 資格・登録
- [ ] アマチュア無線技士免許（第三級以上推奨）
- [ ] DMR ID の登録（[radioid.net](https://radioid.net)）
- [ ] TGIF アカウントとパスワード（[tgif.network](https://tgif.network)）

## 3. 専門用語ミニ辞典

| 用語 | 意味 |
|---|---|
| **DMR** | Digital Mobile Radio。デジタル業務無線規格を流用したアマチュア無線方式 |
| **AMBE** | DMR で使われる音声圧縮方式（特許あり） |
| **USRP** | DVSwitch 内で使われる音声転送プロトコル名。bot → Analog_Bridge 間で使用 |
| **PCM** | 生（無圧縮）のデジタル音声データ |
| **Analog_Bridge** | DVSwitch の中核。音声プロトコルを変換 |
| **MMDVM_Bridge** | MMDVM 系プロトコルを DVSwitch に橋渡しし、DMR ネットワークに接続 |
| **md380-emu** | MD-380 ファームを利用した AMBE ソフトウェア変換器 |
| **カーチャンク** | 短時間の PTT 操作（「ブッ」というキー操作） |
| **TG（トークグループ）** | DMR の通話グループ |
| **ESSID** | DMR ID に付ける2桁の枝番号 |

## 4. 構築の急所

再現時に必ず意識すべき決定的ポイント。詳細は各章で扱う。

1. 🔴 **md380-emu を動かすには 2 つの必須操作がある（別問題・両方必要）。**
   - (a) qemu-user-static を **5.2（Bullseye 版）にダウングレード**し `apt-mark hold` で固定（qemu 7.2 では SEGV）
   - (b) **`md380-emu` バイナリに `chmod +x`** で実行権限を付与（無いと Permission denied）
2. ⚠️ **USRP ポートは rxPort=51000 / txPort=51001。** bot の送信先は 51000。
3. ⚠️ **Open JTalk の辞書パスは `/var/lib/mecab/dic/open-jtalk/naist-jdic`**（`open-jtalk/` を含む）。
4. ⚠️ **OS は Bookworm に固定する。** sources.list が trixie を指していないか確認。
5. 🔴 **`dvs` の「01 初期設定」完走が ini 生成の前提条件。** これを通さないと `/opt/Analog_Bridge/` の ini が生成されず、`dvs_config.sh` が前提を満たせない。
6. ⚠️ **「Does not exist」は monit の httpd 無効が主因。** OS 世代とは無関係。
7. 🔴 **Bot は「設定ツール＋デーモン本体」構成を使う。** 対話設定内蔵の旧版は systemd 常駐で `EOFError` 停止する。

---

# 第2章：OS と DVSwitch-Server

## 5. OS 準備

### 5-1. OS 書き込み・初回起動 ✅

Raspberry Pi Imager で **「Raspberry Pi OS Lite (Legacy, 32-bit)」**
（"A port of Debian Bookworm ..." と表示されるもの）を選び、microSD に書き込む。
"Legacy" の付かない最新版は trixie の可能性があるため選ばない。SSH・WiFi・ロケール等の
初期設定を済ませてから起動する。

> 💡 **ユーザー名について:** この初期設定（Imager の歯車アイコン「詳細な設定」）で作成するユーザー名を、本書では既定で `ocv` としている。別のユーザー名で作成した場合は、以降のコマンド例中の `ocv` をすべて実際に設定したユーザー名に読み替えること。

#### OS イメージ直リンク（Imager から取れない場合）

本検証で使用したのは **`2025-05-13-raspios-bookworm-armhf-lite.img.xz`**（約 493MB）。
**ファイル名に `bookworm` を含むもの**を必ず選ぶ。

```
# JAIST（北陸先端大）ミラー — 国内・高速
https://ftp.jaist.ac.jp/pub/raspberrypi/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz

# 公式（Raspberry Pi 財団）
https://downloads.raspberrypi.com/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz
```

> **リンク切れ時:** 各ミラーの `raspios_lite_armhf/images/` 配下から、ファイル名に
> `bookworm` を含む `...-armhf-lite.img.xz` を選ぶ。stable が trixie に切り替わった後は
> `raspios_oldstable_lite_armhf/` 側で bookworm を探す。

起動後に確認:

```bash
uname -a    # ... armv7l を確認
```

### 5-2. 🔴 sources.list が bookworm であることを確認 ✅

`apt upgrade` の前に、リポジトリが bookworm を指していることを確認する。trixie だと
アップグレードで OS 世代が上がり、monit 等の挙動が手順と食い違う。

```bash
grep -rE "bookworm|trixie" /etc/apt/sources.list /etc/apt/sources.list.d/
cat /etc/os-release | grep VERSION_CODENAME    # bookworm であること
```

出力がすべて `bookworm` で、`trixie` が一つも無いことを確認する。

### 5-3. システム更新 ✅

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

再起動後、`apt update` の出力に bookworm のみが出て trixie が出ないことを確認する。

## 6. ネットワーク（固定 IP）

無人運用するため、IP アドレスを固定しておくと管理しやすい。Bookworm は
**NetworkManager** が既定のため、`nmtui`（テキスト UI）で設定するのが簡単。

```bash
sudo nmtui
```

`Edit a connection` → 使用中の接続を選択 → `IPv4 CONFIGURATION` を `Manual` にして、
アドレス（例 `192.168.1.74/24`）・ゲートウェイ・DNS を入力 → 保存。反映:

```bash
sudo systemctl restart NetworkManager     # または再起動
ip addr                                    # 設定した IP を確認
```

> ⚠️ Bullseye 時代の `dhcpcd.conf` 方式は Bookworm では標準で効かない。`nmtui`/`nmcli`
> または `/etc/NetworkManager/system-connections/` を使う。

## 7. DVSwitch-Server インストール

### 7-1. リポジトリ登録 ✅

```bash
cd /tmp
wget http://dvswitch.org/bookworm
cat bookworm          # 中身を確認（GPGキー取得とリポジトリ追加のみ）
chmod +x bookworm
sudo ./bookworm
```

`Verified: Valid DVSwitch Keyring (72147EC1E788D4C3)` と
`Finished DVSwitch repository install` が出れば成功。

> 🔴 **OS 世代に合った 1 本のスクリプトを使う。** Bookworm なら `bookworm`、Bullseye なら
> `buster` を流用する。公式手順に「bookworm を実行してから buster へ切替」のような二段階は
> 存在しない。誤った codename を実行した場合は、`dvswitch.list` と関連キーリングを削除し、
> 正しいスクリプトを実行し直して再生成させる。

### 7-2. 本体インストール ✅

```bash
sudo apt install dvswitch-server -y
```

- `Error, YSFHosts.txt file does not seem to be valid` は **無害**（YSF 未使用時）。
- `Could not execute systemctl`（chroot 起因）も実機起動後は問題なし。

## 8. dvs 初期設定（ini 生成）と TGIF 切替

### 8-1. 🔴 初期設定メニュー（ini 生成のために必須） ✅

メニューの実体は **`/usr/local/dvs/dvs`**（`dvswitch-menu` ではない）。

```bash
sudo /usr/local/dvs/dvs
```

> 🔴 **この初期設定（01）を一度完走しないと `/opt/Analog_Bridge/` の ini が生成されない。**
> ini が無いまま後段の `dvs_config.sh` を実行すると `[ERROR] 見つかりません` で止まる。

> ⚠️ **ここで入れる値の多くは後で `dvs_config.sh` が上書きする。** この時点では
> 値の厳密さより「一度完走させて ini を生成すること」が目的。ポート・パスワードは
> デフォルトのまま通してよい。

#### 画面遷移（Menu Script v.1.61）

各ステップの `コード体` は画面に実際に表示されるプロンプト、「→」の右が入力値。

1. メインメニュー → `01 初期設定` を選択
2. `初めに行う設定` → `Yes`
3. `Callsign` → 例 `JJ2YYK`
4. `CCS7/DMR ID ?` → 例 `4402396`（7桁）
5. `CCS7/DMR ID + 2桁の数（00〜99）?` → 例 `440239652`（DMR ID + ESSID）
6. `Dstar module ? (A〜Z)` → 例 `B`（D-STAR 未使用でも入力を求められる）
7. `NXDN ID?` → 空欄のまま Enter
8. `USRP ポート番号` → 空欄のまま（後で `dvs_config.sh` が 51001/51000 にする）
9. `Analog_Bridge.ini` 確認 → `Yes`（デフォルト値。後で上書きされる）
10. `ローカル BM サーバー選択` → 任意（TGIF 運用では後で上書き）
11. `Brandmeister のパスワード` → デフォルトのまま Enter で可
12. `Hardware Vocoder (AMBE)` → **`4 ハードウェア Vocoder を使わない（ソフトウェア Vocoder を使う）`** を選択
13. `入力終了` → `Yes`

完了後、再起動する。これで `/opt/Analog_Bridge/Analog_Bridge.ini` 等が生成される。

### 8-2. ⚠️ 詳細設定で DMR サーバーを TGIF に切替 ✅

```bash
sudo /usr/local/dvs/dvs
```

1. メインメニュー → `02 詳細設定`
2. → `24 その他の DMR ネットワーク`
3. → `1 デフォルトの DMR サーバー変更`
4. → `2 TGIF` を選択（「現在のサーバー: TGIF」になることを確認）
5. メインメニューまで戻って終了

---

# 第3章：設定とサービス

## 9. スクリプト一式の取得

### 9-0. 🔴 ツール置き場 `/opt/dvswitch_bot/bin/` を作り、全スクリプトを取得 ✅

本システムで使う 5 本のスクリプトは、すべて `/opt/dvswitch_bot/bin/` に集約する。
スクリプト（実行ファイル）は `bin/`、bot が読む WAV・設定 JSON は `/opt/dvswitch_bot/` 直下、
という役割分担。

```bash
# 置き場を作成
sudo mkdir -p /opt/dvswitch_bot/bin
sudo chown -R ocv:ocv /opt/dvswitch_bot

# 5 本を bin/ に一括取得
cd /opt/dvswitch_bot/bin
BASE=https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main
for f in dvs_config.sh create_wav.sh test_send.py dvswitch_bot.py bot_setup.py; do
  curl -fsSL "$BASE/$f" -o "$f"
done
chmod +x *.sh *.py
ls -la /opt/dvswitch_bot/bin/
```

| スクリプト | 役割 |
|---|---|
| `dvs_config.sh` | DVSwitch ini を TGIF 用に一括設定（第10章） |
| `create_wav.sh` | 固定 WAV を対話生成（第15章） |
| `test_send.py` | USRP 単発送信テスト（第16章） |
| `dvswitch_bot.py` | 自動応答デーモン本体（第17章） |
| `bot_setup.py` | bot 設定ツール（第17章） |

> 5 本が並び実行権（`x`）が付いていれば取得完了。以降の各章はここで取得済みのものを使う。

## 10. dvs_config.sh で TGIF 用の値を確定

🔴 **必須。** `dvs` の初期設定で ini が生成されたら、`dvs_config.sh` でコールサイン・
DMR ID・TGIF パスワード・送信 TG・USRP ポートを一括設定する。

```bash
cd /opt/dvswitch_bot/bin
# バックアップ先フォルダを事前に作成（無いとバックアップ時にエラーになる）
sudo mkdir -p /opt/dvswitch_bot/bak/ini /opt/dvswitch_bot/bak/wav
sudo chown -R ocv:ocv /opt/dvswitch_bot/bak
sudo ./dvs_config.sh
```

このツールがすること:

- 編集前に **`/opt/dvswitch_bot/bak/ini/YYMMDDHHMMSS/`** へ 3 つの ini を自動バックアップ
- 対話入力 5 項目：`callsign` / `dmrid(7桁)` / `essid(2桁)` / `tgifpassword` / `txtgif`
- 固定セット：
  - MMDVM: `[DMR] Enable=1`、`[DMR Network] Enable=1`、`Address=tgif.network`
  - Analog: `[USRP] txPort=51001` / `rxPort=51000` / `usrpAudio=AUDIO_USE_GAIN` / `tlvAudio=AUDIO_USE_GAIN`
- `Id`（MMDVM）と `repeaterID`（Analog）は **dmrid(7桁) + essid(2桁)** で組み立てる
- `gatewayDmrId`（Analog）は dmrid(7桁) をセット

| 項目 | 入力例 | 備考 |
|---|---|---|
| Callsign | `JJ2YYK` | 自局コールサイン |
| DMR ID(7桁) | `4402396` | 自局 DMR ID |
| ESSID(2桁) | `52` | サブ番号 |
| TGIF Password | （TGIF の値） | TGIF サイトで発行 |
| 送信 TG（txTg） | `44833` | ボット音声が乗る DMR TG |

確認画面で `y` で保存。オプション:

```bash
sudo ./dvs_config.sh -r     # バックアップから復元
sudo ./dvs_config.sh -d     # /opt/dvswitch_bot/bak/ini/ 配下を全削除
sudo ./dvs_config.sh -h     # ヘルプ
```

### 設定反映と TGIF ログイン確認

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
sudo tail -40 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

> **MMDVM_Bridge のログは journal ではなく日付別ファイル**（`/var/log/mmdvm/MMDVM_Bridge-YYYY-MM-DD.log`）。

末尾付近に次が出ていればログイン成功:

```
DMR, Logged into the master successfully: tgif.network:62031
```

> ⚠️ `dvs_config.sh` は `DVSwitch.ini` を変更しない（バックアップのみ）。`exportTG` を
> 明示設定したい場合は付録C を参照。
>
> **TGIF が TG 4000 に戻る件:** TGIF 側で Static 設定が無いと一定時間でデフォルト（4000）へ
> 戻る。受信を継続したい場合は TGIF ダッシュボードで対象 TG を Static 登録する。

## 11. サービス起動確認と md380-emu 修正

### 11-1. サービス一覧の確認 ✅

```bash
sudo systemctl list-units --all | grep -E "analog|mmdvm|md380|bridge|webproxy"
```

- `analog_bridge` / `mmdvm_bridge` / `webproxy` が `active (running)` であること
- `md380-emu` が `activating (auto-restart)` になっていないか（なっていれば次節で対処）

### 11-2. 🔴🔴 md380-emu の SEGV と qemu ダウングレード ✅

**症状:** TGIF 等から信号が入り AMBE デコードが走った瞬間、
`md380-emu.service: ... status=11/SEGV` を吐いて auto-restart を繰り返す。

**原因:** Bookworm 標準の qemu-user-static 7.2.x が md380-emu の ARM バイナリと非互換。
Bullseye の qemu 5.2.x では正常動作する。

**対処（一括実行版）:**

```bash
wget http://archive.raspbian.org/raspbian/pool/main/q/qemu/qemu-user-static_5.2+dfsg-11+deb11u5_armhf.deb -O /tmp/qemu52.deb && sudo systemctl stop md380-emu && sudo dpkg -i /tmp/qemu52.deb && sudo apt-mark hold qemu-user-static && sudo chmod +x /opt/md380-emu/md380-emu && sudo systemctl restart md380-emu && sleep 3 && sudo systemctl status md380-emu --no-pager && qemu-arm-static --version
```

> 🔴 **必須操作は 2 つ。両方やらないと動かない。**
> 1. qemu を 5.2 へダウングレード（＋ `apt-mark hold` で固定）… SEGV を止める
> 2. `chmod +x` で実行権限を付与 … Permission denied を止める
>
> この 2 つは独立した別問題。`qemu-arm-static --version` が 5.2.x であることを確認。

> ⚠️ この段階の running 表示は「起動できた」確認に過ぎない。SEGV は実デコード時に出るため、
> 最終確認は第16章の送信テスト後に行う。

## 12. Monit Service Manager（:2812）の表示修正

**対象:** `http://<IP>:2812/`（サービス監視画面。DVSwitch Dashboard の :80 とは別物）。
**目的:** 赤字「Does not exist」（典型は Quantar_Bridge）を緑の「OK」にする。
**原因（2つ。OS 世代は無関係）:** ① monit の httpd（:2812）が無効、② プロセス自体が停止・自動起動オフ。

### ステップ1：症状確認 ✅

```bash
sudo monit status
```

`Error receiving data -- Connection reset by peer` が出れば monit の Web 機能が無効。

### ステップ2：monit の Web 機能を開通させる 🔴

行番号を確認（環境で前後する）:

```bash
sudo grep -nE "set httpd|use address|allow localhost|allow admin" /etc/monit/monitrc
```

標準では次の 4 行がコメントアウトされている。`grep` の行番号に合わせて置き換える（例 159〜162）:

```bash
sudo sed -i '159,162c\
set httpd port 2812 and\
    use address 0.0.0.0\
    allow localhost\
    allow 192.168.1.0/24' /etc/monit/monitrc
```

> ⚠️ 自分の LAN が `192.168.1.0/24` 以外なら変更する。`use address 0.0.0.0` にすること
> （`localhost` のままだと外部 IP から開けない）。パスワードを掛けたい場合は
> `allow 192.168.1.0/24` の代わりに `allow admin:monit` を使う。

書き換え結果を確認:

```bash
sudo sed -n '159,162p' /etc/monit/monitrc
```

### ステップ3：止まっているプロセスを起動 🔴

```bash
sudo systemctl enable --now quantar_bridge
```

対象が他のサービスなら、その systemd ユニット名に置き換える。

### ステップ4：monit に反映させて「OK」を確認 ✅

```bash
sudo systemctl restart monit && sleep 8 && sudo monit reload && sleep 12 && sudo monit status Quantar_Bridge
```

`status  OK` と出れば成功。

> **ハマりどころ:** monit は状態収集に時間がかかる。`reload` 後は十数秒待ってから確認する。
> 使わないプロセスが「Does not exist」のままでも、使う予定がなければ実害はない。

## 13. DVSwitch Dashboard（:80）の表示設定

**対象:** `http://<IP>/`（DVSwitch Dashboard。:2812 とは別物）。
初期状態は Apache のデフォルトページが出るので、DocumentRoot を DVSwitch の実体に変える。

```bash
sudo sed -i 's|DocumentRoot /var/www/html|DocumentRoot /usr/share/dvswitch|' \
  /etc/apache2/sites-enabled/000-default.conf
sudo systemctl restart apache2
```

`http://<IP>/` で「DVSwitch Dashboard」が表示されれば成功。

> **DocumentRoot が変わって見える件:** DVSwitch 導入で VirtualHost が追加・有効化され、
> DocumentRoot が `/usr/share/dvswitch` に切り替わるのは想定どおりの挙動。競合する場合は
> `apache2ctl -S` で有効な VirtualHost を確認し、不要なサイト定義を `a2dissite <名>.conf`
> で無効化して `sudo systemctl reload apache2`。
>
> **補足:** Zero 2W + SD カードでは初回表示が重い。`top` で `wa`（I/O待ち）が高い場合は
> SD のランダムアクセス遅延が主因。

---

# 第4章：音声と Bot

## 14. 音声合成環境（Open JTalk + SoX）

### 14-1. パッケージ導入 ✅

```bash
sudo apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic \
  hts-voice-nitech-jp-atr503-m001 sox unzip
```

### 14-2. 高品質音声「メイ」導入 ✅

```bash
cd ~
wget -L --content-disposition \
  https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip
ls *.zip*                                  # 実ファイル名を確認
unzip 'MMDAgent_Example-1.8.zip'*

sudo mkdir -p /usr/share/hts-voice/mei
sudo cp MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice /usr/share/hts-voice/mei/
rm -rf MMDAgent_Example-1.8 'MMDAgent_Example-1.8.zip'*
```

### 14-3. 🔴 動作確認（辞書パスに注意） ✅

⚠️ 辞書パスは **`/var/lib/mecab/dic/open-jtalk/naist-jdic`**（`open-jtalk/` を含む）。

```bash
echo "テスト、動作確認。" | open_jtalk \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -ow /tmp/test.wav && \
sox /tmp/test.wav -r 8000 -c 1 -b 16 /tmp/test_8k.wav && echo OK
```

`OK` が出れば成功。`Cannot open ... naist-jdic` が出る場合はパスが誤り
（不明なときは `find /var/lib/mecab -name "sys.dic"` で実体を確認）。

## 15. 固定 WAV の作成

固定 WAV は対話式スクリプト `create_wav.sh` で生成する。出力先は `/opt/dvswitch_bot/` 直下。

```bash
cd /opt/dvswitch_bot/bin
sudo ./create_wav.sh
```

対話入力の流れ:
1. コールサイン（例 `JJ2YYK`）→ 自動カナ変換結果を確認・修正
2. 設置場所の地名（例 `おわりあさひ`。確実に読ませたいときはひらがな推奨）
3. 定時メッセージ1 → カナ確認・修正
4. 定時メッセージ2 → カナ確認・修正
5. 確認プロンプトで `Y`

生成されるファイル:

| ファイル | 用途 |
|---|---|
| `fixed_intro.wav` | カーチャンク応答イントロ |
| `fixed_outro.wav` | カーチャンク応答アウトロ |
| `time_intro.wav` | 時報イントロ |
| `001.wav` / `002.wav` | 定時メッセージ |

> 💡 **自動バックアップ／復元:** `create_wav.sh` は上書き直前に既存 WAV を
> `/opt/dvswitch_bot/bak/wav/YYMMDDHHMMSS/` へ自動退避する。失敗したら
> `sudo ./create_wav.sh -r` で前のセットに戻せる（`-d` 全削除 / `-h` ヘルプ）。
> bot は送出のたびに WAV を読むため、上書きは再起動なしで次の送出から反映される。

確認:

```bash
ls -la /opt/dvswitch_bot/
soxi /opt/dvswitch_bot/*.wav    # 全ファイル 8000Hz / 1ch / 16-bit を確認
```

> 💡 **カスタム音声:** ここで作る標準 WAV とは別に、intro/001/002 を自前の WAV（`cstm_intro.wav`/`cstm_001.wav`/`cstm_002.wav`）へ個別差し替えできる（V1.73〜）。手順は `カスタム音声.md` 参照。

> 手動で個別生成する方法（検証済み文面）は付録B を参照。

## 16. 送信テスト

### 16-1. 実行 ✅

```bash
python3 /opt/dvswitch_bot/bin/test_send.py /opt/dvswitch_bot/001.wav
```

TGIF の対象 TG で音声が出れば **経路開通**。

> 第10章でサービスは反映済みなので、ここでの再起動は不要。bot が常駐している場合は
> 二重送信になるため、テスト時は `sudo systemctl stop dvswitch-bot` で止める。

### 16-2. 🔴 md380-emu SEGV の最終確認 ✅

```bash
sudo journalctl -u md380-emu -n 20 --no-pager   # SEGV が出ていないこと
sudo systemctl status md380-emu --no-pager       # active (running) のまま
```

SEGV が再発する場合は qemu が 7.2 に戻っていないか確認（`qemu-arm-static --version` が
5.2.x、`apt-mark` で hold 済みか）。

## 17. Bot 本体と設定ツールの導入

| ファイル | 役割 |
|---|---|
| `bot_setup.py` | 対話で設定を作り `/opt/dvswitch_bot/bot_config.json` に保存 |
| `dvswitch_bot.py` | デーモン本体。起動時に JSON を読むだけ（対話しない） |

> 🔴 **デーモン本体は、設定が無い／壊れている／値が不正なら起動を拒否する（フェイルセーフ）。**
> そのため常駐させる前に必ず設定ツールを実行する。

### 17-1. パラメータの確認 ✅

```bash
grep -nE "^UDP_IP|^UDP_PORT|^DICT_PATH|^CONFIG_PATH" /opt/dvswitch_bot/bin/dvswitch_bot.py
```

| 変数 | 正しい値 |
|---|---|
| `UDP_IP` | `127.0.0.1` |
| `UDP_PORT` | `51000`（Analog_Bridge の rxPort と一致） |
| `DICT_PATH` | `/var/lib/mecab/dic/open-jtalk/naist-jdic` |
| `CONFIG_PATH` | `/opt/dvswitch_bot/bot_config.json` |

> 🟢 **V1.94 以降、自局コールサイン（`MY_CALLSIGN`）と DMR ID（`MY_DMR_ID`）は
> `MMDVM_Bridge.ini` の `Callsign` と `Analog_Bridge.ini` の `gatewayDmrId` から
> 起動時に自動取得される。そのためソース（`dvswitch_bot.py`）を手修正する必要はない。**
> コールサイン・DMR ID の設定は `dvs_config.sh`（第16章）またはダッシュボードの
> 「DVSwitch 設定」カードで行い、変更後は bot を再起動すれば反映される。
> （ini が読めない場合のみ従来の既定値へフォールバックし、起動ログに WARN を出す。
> 起動ログの `My DMR ID : ...（source: ini 自動取得）` 行で取得元を確認できる。）

### 17-2. 🔴 設定ツールで bot_config.json を作成 ✅

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py
```

| 項目 | 内容 | 既定 |
|---|---|---|
| 最小受信時間 (秒) | これ未満は無視 | 0.5 |
| 最大受信時間 (秒) | これ以上はカーチャンクとしない（通常 QSO 扱い） | 3.9 |
| 放送回数 | 1時間あたりの定時メッセージ回数（有効範囲は時刻案内モード依存。下記参照） | 2 |
| ナイトモード (y/n) | 夜間の時報・定時メッセージ抑制 | y |
| N1（開始時） | この時刻の時報まで送出 → 以降抑制 | 22 |
| N2（終了時） | この時刻まで抑制 → N2+1 時の時報で再開 | 5 |

#### 時刻案内モード（`TIME_SIGNAL_MODE`）— V1.64〜

時報の頻度を `bot_config.json` の `TIME_SIGNAL_MODE` で選べる（任意キー。未設定の旧設定は従来動作＝モード1）。

| モード | 動作 |
|---|---|
| 0 | 時刻案内なし |
| 1 | 毎正時のみ「○○時です」（従来動作） |
| 2 | 毎正時「○○時です」＋毎30分「○○時30分です」 |

**放送回数の有効範囲はモードに依存する**（正時/30分は時刻案内が占有するため）: モード0→0/1/2/3/4、モード1→0/1/2/3、モード2→0/2。

#### 送出音量 `TX_GAIN` — V1.68〜

bot が出す全音声の音量を線形倍率 `TX_GAIN`（`1.0`=等倍、主用途は減衰）で一律調整できる。`bot_config.json` の**任意キー**で、無ければ等倍。値が不正でも送出は止めず 1.0 にフォールバックする（有効範囲: 0 より大〜5.0 以下）。

> 💡 `TX_GAIN` は `bot_setup.py`（対話）とダッシュボード（app.py）の双方で設定でき、保存し直しても消えない。直接調整したい場合は `bot_config.json` を手動編集してもよい。

#### カスタム音声（cstm）— V1.73〜

intro（名乗り）・定時メッセージ001・002 を、自前の WAV に**個別に**差し替えられる。`bot_setup.py` の対話で次の任意キーを設定する（いずれも既定 `false`）。

| キー | 意味 |
|---|---|
| `USE_CSTM_INTRO` | intro に `cstm_intro.wav` を使う |
| `USE_CSTM_001` | 001 に `cstm_001.wav` を使う |
| `USE_CSTM_002` | 002 に `cstm_002.wav` を使う |

カスタムファイル（`/opt/dvswitch_bot/` 直下に置く `cstm_*.wav`、8000Hz/モノラル/16bit）が無ければ自動的に標準へフォールバックするため、ON にしても送出は止まらない。ダッシュボードの「カスタム音声 — 差し替え」カードでも設定できる。詳しい手順は `カスタム音声.md` を参照。

確認:

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py -s     # 表示＋有効性チェック
cat /opt/dvswitch_bot/bot_config.json
```

### 17-3. 手動起動で動作確認 ✅

```bash
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
```

- `Config loaded /opt/dvswitch_bot/bot_config.json` が出ればフェイルセーフ通過
- 設定が無い／不正だとここで止まる（その場合は 17-2 をやり直す）
- カーチャンクを送って応答が返るか確認 → `Ctrl+C` で停止 → 第18章へ

## 18. 常駐化（systemd）

> 🔴 **前提:** 17-2 で `bot_config.json` を作成済みであること。未作成だとフェイルセーフで
> 起動を拒否し、`Restart=on-failure` で再起動を繰り返す（設定漏れに気づける意図した挙動）。

```bash
sudo tee /etc/systemd/system/dvswitch-bot.service > /dev/null << 'EOF'
[Unit]
Description=DVSwitch Bot (OpenCCVoice, daemon V1.94)
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
```

> 別ユーザーで運用する場合は `ExecStart` のパスと `User=` を読み替える。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dvswitch-bot
sudo systemctl status dvswitch-bot --no-pager
```

`active (running)` で、ログに `Config loaded` と `Bot ready` が出ていれば成功。

> ⚠️ `activating (auto-restart)` を繰り返す場合は設定ファイル不正の可能性。
> `sudo journalctl -u dvswitch-bot -n 30 --no-pager` で `Config error` を確認し、
> `bot_setup.py` で作り直す。

---

# 第5章：運用

## 19. 設定変更・音声差し替え・バックアップ

### 19-1. 動作設定を変える

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py    # 対話で bot_config.json を更新
sudo systemctl restart dvswitch-bot                # 再起動して反映
```

### 19-2. 音声を作り直す

```bash
cd /opt/dvswitch_bot/bin
sudo ./create_wav.sh        # 上書き前に自動バックアップ。再起動不要で反映
sudo ./create_wav.sh -r     # 失敗したら前のセットに戻す
```

intro/001/002 を自前の音声に差し替えたいときは、カスタム音声（cstm）機能を使う（詳細は `カスタム音声.md`）。

### 19-3. DVSwitch 設定（コールサイン・TG 等）を変える

```bash
cd /opt/dvswitch_bot/bin
sudo ./dvs_config.sh        # 編集前に自動バックアップ。最後にサービス再起動を確認
sudo ./dvs_config.sh -r     # 失敗したら ini を戻す
```

### 19-4. ログの見方

常駐化すると出力は journal に集約される。

```bash
sudo journalctl -u dvswitch-bot -f                 # リアルタイム監視（常用）
sudo journalctl -u dvswitch-bot -n 50 --no-pager   # 直近 50 行
sudo journalctl -u dvswitch-bot --since today --no-pager
sudo systemctl status dvswitch-bot --no-pager      # 稼働状態
```

### 19-5. 手動起動に戻して画面で見たいとき

```bash
sudo systemctl stop dvswitch-bot                    # 常駐を一時停止
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py       # 画面出力で手動起動（Ctrl+C で終了）
sudo systemctl start dvswitch-bot                   # 確認後、常駐に戻す
```

### 19-6. バックアップの所在

| 種類 | 場所 | 作るツール |
|---|---|---|
| ini バックアップ | `/opt/dvswitch_bot/bak/ini/<日付>/` | `dvs_config.sh` |
| WAV バックアップ | `/opt/dvswitch_bot/bak/wav/<日付>/` | `create_wav.sh` |

システムに関するものはすべて `/opt/dvswitch_bot/` 配下に集約されている。

## 20. 運用上の注意と法令遵守

### 20-1. 電波法の遵守
- [ ] アマチュア無線技士の免許を保有していること
- [ ] コールサインを正しく送出していること（システムは応答時に必ず自局コールサインを送出する設計）
- [ ] 自動運用に関する規定を理解していること（長時間の常時無人運用は所轄の総合通信局に相談を推奨）

### 20-2. 推奨される運用
1. 応答後の抑制時間（既定 15 秒）は短くしすぎない
2. 応答頻度をログで定期的に確認する
3. 他局が交信中の TG に割り込まないよう確認する

### 20-3. ハードウェアの保護
- **SD カードの寿命:** 一時ファイルは `/dev/shm`（RAM）に書いているが、ログは定期削除を設定推奨
- **温度管理:** ヒートシンク推奨（`vcgencmd measure_temp`。70℃ 超は要注意）
- **電源:** 5V 2.5A 以上。電源不足はファイル破損の原因

## 21. システム全体のバックアップとリストア

### 21-1. 設定ファイルのバックアップ

```bash
mkdir -p ~/dvswitch_backup && cd ~/dvswitch_backup
sudo cp /opt/Analog_Bridge/Analog_Bridge.ini ./
sudo cp /opt/MMDVM_Bridge/MMDVM_Bridge.ini ./
cp /opt/dvswitch_bot/bin/dvswitch_bot.py ./
cp /opt/dvswitch_bot/bin/bot_setup.py ./
sudo cp /etc/systemd/system/dvswitch-bot.service ./ 2>/dev/null || true
cp /opt/dvswitch_bot/bot_config.json ./
cp /usr/share/hts-voice/mei/mei_normal.htsvoice ./
sudo chown -R $USER:$USER ~/dvswitch_backup
cd ~ && tar czf dvswitch_backup_$(date +%Y%m%d).tar.gz dvswitch_backup/
```

このファイルを別の PC やクラウドに保管する。

### 21-2. SD カード全体のバックアップ（推奨）

ラズパイをシャットダウンし、SD カードを別 PC に挿して:

```bash
sudo fdisk -l    # デバイス名を必ず確認（/dev/mmcblk0 や /dev/sdc 等）
sudo dd if=/dev/sdb of=~/backup_$(date +%Y%m%d).img bs=4M status=progress
gzip ~/backup_*.img
```

### 21-3. リストア（新しい Pi で再構築）

1. 第5章〜第18章を順に実施
2. バックアップを展開して設定ファイルを戻す:

```bash
cd ~ && tar xzf dvswitch_backup_YYYYMMDD.tar.gz
sudo cp ~/dvswitch_backup/Analog_Bridge.ini /opt/Analog_Bridge/
sudo cp ~/dvswitch_backup/MMDVM_Bridge.ini /opt/MMDVM_Bridge/
sudo mkdir -p /opt/dvswitch_bot/bin
sudo cp ~/dvswitch_backup/dvswitch_bot.py ~/dvswitch_backup/bot_setup.py /opt/dvswitch_bot/bin/
sudo chmod +x /opt/dvswitch_bot/bin/*.py
sudo cp ~/dvswitch_backup/dvswitch-bot.service /etc/systemd/system/
sudo cp ~/dvswitch_backup/bot_config.json /opt/dvswitch_bot/
sudo chown -R ocv:ocv /opt/dvswitch_bot
sudo systemctl daemon-reload
sudo systemctl restart analog_bridge mmdvm_bridge md380-emu
sudo systemctl enable --now dvswitch-bot
```

3. 第16章の動作確認を実施

### 21-4. 定期バックアップの自動化（cron）

```bash
crontab -e
```

```cron
# 毎週日曜 3:00 に DVSwitch 設定をバックアップ
0 3 * * 0 tar czf /home/ocv/dvswitch_backup_$(date +\%Y\%m\%d).tar.gz /opt/Analog_Bridge/Analog_Bridge.ini /opt/MMDVM_Bridge/MMDVM_Bridge.ini /opt/dvswitch_bot/bin/dvswitch_bot.py /opt/dvswitch_bot/bin/bot_setup.py /opt/dvswitch_bot/bot_config.json
```

## 22. Web ダッシュボード（OpenCCVoice for DVSwitch Web Dashboard）

Bot の設定・監視・サービス制御をブラウザから行える Web ダッシュボード（任意導入）。
Raspberry Pi 上の Flask アプリとして動作する。

> **前提:** 第17章で `bot_setup.py` を実行し `bot_config.json` が存在すること。

### 機能一覧

| 機能 | 説明 |
|---|---|
| サービス制御 | dvswitch-bot の Start / Stop / Restart |
| Bot 設定 | `bot_config.json` の項目をフォームで編集・保存（送出音量 `TX_GAIN` を含む） |
| カスタム音声 | intro/001/002 を標準⇄カスタム（`cstm_*.wav`）に個別切替（「カスタム音声 — 差し替え」カード。保存で自動再起動・反映） |
| DVSwitch 設定 | `MMDVM_Bridge.ini` / `Analog_Bridge.ini` をフォームで編集 |
| 自動バックアップ | DVSwitch 設定保存時に `/opt/dvswitch_bot/bak/ini/` へ自動バックアップ |
| ログ表示 | MMDVM_Bridge ログ末尾5行を表示・30秒自動更新 |
| バックアップ一覧 | ini バックアップのタイムスタンプ一覧（最新10件） |
| 変更ログ | Bot 設定の変更履歴（項目・変更前後の値・日時）を記録・表示 |

### インストール ✅

```bash
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/install.sh | sudo bash
```

完了するとIPアドレスが表示される:

```
✔ dvswitch-web が起動しました！
  ブラウザでアクセス: http://192.168.1.81:8081/
```

### アクセス

```
http://<Raspberry-Pi-IP>:8081/
```

### アンインストール

```bash
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/uninstall.sh | sudo bash
```

> **削除されるもの:** dvswitch-web サービス / `/opt/dvswitch_bot/web/app.py`
>
> **残るもの（保護）:** `bot_config.json` / `bot_change_log.json` / `bak/ini/`（バックアップ）

### サービス管理

```bash
sudo systemctl status dvswitch-web          # 状態確認
sudo systemctl restart dvswitch-web         # 再起動
journalctl -u dvswitch-web -n 30            # ログ確認
```

---

# 付録

## 付録A：トラブルシューティング早見表

| 症状 | 原因 | 対処 |
|---|---|---|
| md380-emu が `Permission denied` | 実行ビット無し | `sudo chmod +x /opt/md380-emu/md380-emu` |
| md380-emu が `status=11/SEGV` を繰り返す | qemu 7.2 の不具合 | qemu 5.2 へダウングレード＋`apt-mark hold`（第11章） |
| Open JTalk が `Cannot open ... naist-jdic` | 辞書パス誤り | `/var/lib/mecab/dic/open-jtalk/naist-jdic` を使う |
| `http://<IP>/` が Apache 既定ページ | DocumentRoot 未変更 | `/usr/share/dvswitch` に変更（第13章） |
| 音声は出るが TG が 4000 に戻る | TGIF 側 Static 未設定 | TGIF ダッシュボードで対象 TG を Static 登録 |
| ボット音声が無音 | md380-emu 停止 or Analog 設定ミス | md380-emu 稼働確認、USRP ポート確認 |
| 音声がプツプツ・ケロケロ | UDP ドリフト | bot が `time.monotonic()` ベースの絶対時刻同期か確認 |
| dvswitch-bot が `activating (auto-restart)` | 設定ファイル不正/未作成 | `journalctl` で確認 → `bot_setup.py` で作成 |
| 手動起動の bot が `Config error` で停止 | bot_config.json 不正/欠落 | `bot_setup.py` で作成。`-s` で検証 |
| SFR 中継でカーチャンクに反応しない | 終端パケット落ちで end が記録されない | V1.67 以降に更新。ログに `watchdog pseudo-end` が出れば救済動作中（`watchdog ignored (high loss)` はロス過大で対象外） |
| 30分案内が出ない | `TIME_SIGNAL_MODE` が 2 でない | `bot_config.json` の `TIME_SIGNAL_MODE` を 2 に（放送回数の有効範囲も変わる・第17章） |
| `TX_GAIN` が効かない／消えた | `bot_setup.py`・ダッシュボードが非対応 | `TX_GAIN` は手動キー。保存ツールで消えるため再追記（第17章）。不正値は等倍にフォールバック |
| Quantar_Bridge 等が「Does not exist」 | monit httpd 無効＋未起動 | 第12章：httpd 有効化＋`enable --now`＋`monit reload` |
| `sudo monit status` が `Connection reset by peer` | monit httpd 無効 | 第12章 ステップ2 |
| `:2812` が外部から開けない | `use address localhost` | `0.0.0.0` に変更して `monit reload` |
| `monit reload` 後も「Does not exist」 | データ収集待ち | 十数秒待って再確認 |
| dvswitch-web が起動しない | ポート競合 or flask 未インストール | `journalctl -u dvswitch-web -n 30` で確認 |
| `:8081` にアクセスできない | サービス未起動 | `sudo systemctl status dvswitch-web` で確認 |

## 付録B：固定 WAV の個別コマンド生成

スクリプトを使わず手動で作る場合の検証済み文面。各ファイルは 8kHz / mono / 16bit PCM。
`fixed_*` は単純変換、`time_intro` / `001` / `002` は前後トリム付き。

```bash
# fixed_intro.wav
echo "こちらは、ジェイジェイツーワイワイケー、おわりあさひ ディーエムアール デジピーターです。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/temp_intro.wav && sudo sox /tmp/temp_intro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/fixed_intro.wav

# fixed_outro.wav
echo "カーチャンクです。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/temp_outro.wav && sudo sox /tmp/temp_outro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/fixed_outro.wav

# time_intro.wav（前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/time_intro.wav && sox /tmp/time_intro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/time_intro.wav silence 1 0.1 1% reverse silence 1 0.1 1% reverse

# 001.wav（前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。オープン、シーシーヴォイス、フォー、ディーブイスイッチからの音声です。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/001_raw.wav && sox /tmp/001_raw.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/001.wav silence 1 0.1 1% reverse silence 1 0.1 1% reverse

# 002.wav（前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。ティージーアイエフ、ヨンヨンハチサンサンと、インターネット接続しています。" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/mei/mei_normal.htsvoice -ow /tmp/002_raw.wav && sox /tmp/002_raw.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/002.wav silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

## 付録C：DVSwitch 側 ini の手動編集（参照用）

`dvs_config.sh` が `[WARN] キー ... が見つからず変更できません` を出した場合などの参照用。

### Analog_Bridge.ini（`/opt/Analog_Bridge/Analog_Bridge.ini`）

```ini
[USRP]
address = 127.0.0.1
txPort = 51001        ; Analog_Bridge → 外部（USRP送信）
rxPort = 51000        ; 外部 → Analog_Bridge（ボットはここへ送る）

[AMBE_AUDIO]
txTg = 44833          ; ★ボット音声が乗る DMR TG
txTs = 2
colorCode = 1
```

> DVSwitch v1.6.4 系の特定版では `jitterQueueSize` / `pcmBufferMS` がコメントアウトされて
> いないと起動時にクラッシュする。該当行があれば先頭に `;` を付ける。

### DVSwitch.ini（`/opt/MMDVM_Bridge/DVSwitch.ini`）

```ini
[DMR]
address = 127.0.0.1
exportTG = 44833      ; ★エクスポート TG
```

> ⚠️ `dvs_config.sh` はこの `DVSwitch.ini` を変更しない（バックアップのみ）。

### MMDVM_Bridge.ini（`/opt/MMDVM_Bridge/MMDVM_Bridge.ini`）

```ini
[DMR]
Enable=1

[DMR Network]
Enable=1
Address=tgif.network
Password=（TGIF のパスワード）
```

`[General]` の `Callsign` と `Id`（dmrid + essid）も自局の値にする。反映:

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
```

## 付録D：ダッシュボードの Platform 表示を正す

ダッシュボードの「Platform」が `Unknown ARM based System` になるのを、正しい機種名にする。
`/usr/local/sbin/platformDetect.sh` が `/proc/cpuinfo` の Revision を case 変換しており、
Zero 2 W の Revision が載っていないため Unknown に落ちる。`/proc/device-tree/model` を
優先的に使うよう直す。

### バックアップ（必須）

```bash
sudo cp /usr/local/sbin/platformDetect.sh /usr/local/sbin/platformDetect.sh.bak.$(date +%F)
```

### 推奨：device-tree 判定を最小追記

```bash
cat > /tmp/dt_block.sh << 'EOF'

# --- device-tree model を最優先で返す（新機種対応・前段に挿入） ---
for __p in /sys/firmware/devicetree/base/model /proc/device-tree/model; do
  if [ -r "$__p" ]; then
    __dt=$(tr -d '\0' < "$__p" | sed 's/[[:space:]]\+$//')
    if [ -n "$__dt" ]; then
      echo "$__dt"
      exit 0
    fi
  fi
done
EOF

# /tmp で組み立てて確認してから本番へ
{ head -1 /usr/local/sbin/platformDetect.sh; cat /tmp/dt_block.sh; \
  tail -n +2 /usr/local/sbin/platformDetect.sh; } > /tmp/platformDetect.test.sh
chmod +x /tmp/platformDetect.test.sh
/tmp/platformDetect.test.sh                       # Raspberry Pi Zero 2 W Rev 1.0 が返ればOK
sudo -u www-data /tmp/platformDetect.test.sh      # www-data でも同じ結果か
sudo cp /tmp/platformDetect.test.sh /usr/local/sbin/platformDetect.sh
sudo chmod 0755 /usr/local/sbin/platformDetect.sh
```

### Web サーバ再起動

> ⚠️ 本環境は Bookworm / Apache2。`lighttpd` ではなく **`apache2`** を再起動する。

```bash
sudo systemctl restart apache2
```

ブラウザで `http://<IP>/` を開き **Ctrl+F5**。Platform が機種名になれば成功。
戻したいときは `sudo cp /usr/local/sbin/platformDetect.sh.bak.YYYY-MM-DD /usr/local/sbin/platformDetect.sh`。

## 付録E：クイックリファレンス

### ポート番号一覧

| ポート | 用途 | プロトコル |
|---|---|---|
| 51000 | dvswitch_bot.py → Analog_Bridge（USRP 受信） | UDP |
| 51001 | Analog_Bridge からの出力（txPort） | UDP |
| 2470 | Analog_Bridge ⇔ md380-emu（AMBE） | UDP |
| 62031 | MMDVM_Bridge → TGIF（DMR） | UDP |
| 80 | DVSwitch Dashboard（Apache） | TCP |
| 2812 | Monit Service Manager | TCP |
| 8081 | OpenCCVoice Web Dashboard（Flask） | TCP |

### 主要ファイルパス一覧

| パス | 内容 |
|---|---|
| `/opt/Analog_Bridge/Analog_Bridge.ini` | Analog_Bridge 設定 |
| `/opt/MMDVM_Bridge/MMDVM_Bridge.ini` | MMDVM_Bridge 設定 |
| `/opt/MMDVM_Bridge/DVSwitch.ini` | DVSwitch 設定（exportTG） |
| `/var/log/mmdvm/MMDVM_Bridge-*.log` | ログ（bot の監視対象） |
| `/usr/share/hts-voice/mei/mei_normal.htsvoice` | 音声モデル |
| `/var/lib/mecab/dic/open-jtalk/naist-jdic` | Open JTalk 辞書 |
| `/opt/dvswitch_bot/bin/` | スクリプト 5 本 |
| `/opt/dvswitch_bot/bot_config.json` | Bot 設定 |
| `/opt/dvswitch_bot/*.wav` | 固定 WAV |
| `/opt/dvswitch_bot/bak/{ini,wav}/` | バックアップ |
| `/opt/dvswitch_bot/web/app.py` | Web ダッシュボード本体 |
| `/etc/systemd/system/dvswitch-bot.service` | systemd サービス定義 |
| `/etc/systemd/system/dvswitch-web.service` | Web ダッシュボード systemd 定義 |
| `/etc/monit/monitrc` | monit 設定 |
| `/usr/local/sbin/platformDetect.sh` | Platform 判定スクリプト |

### サービス管理コマンド

```bash
# 全サービスまとめて再起動
sudo systemctl restart analog_bridge mmdvm_bridge md380-emu dvswitch-bot

# 状態確認
sudo systemctl status analog_bridge mmdvm_bridge md380-emu dvswitch-bot --no-pager

# ログ
sudo journalctl -u dvswitch-bot -f
sudo tail -f /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log

# Web ダッシュボード
sudo systemctl status dvswitch-web
sudo systemctl restart dvswitch-web
journalctl -u dvswitch-web -n 30
```

### トラブル時の最速チェック

```bash
sudo systemctl status analog_bridge mmdvm_bridge md380-emu dvswitch-bot --no-pager
qemu-arm-static --version                          # 5.2.x であること
sudo tail -20 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
sudo ss -ulnp | grep -E "51000|2470|62031"
```

---

*OpenCCVoice for DVSwitch 構築・導入・設定 完全マニュアル*
*対象: Raspberry Pi Zero 2 W / Raspberry Pi OS Bookworm 32-bit / DVSwitch-Server / ocv ユーザ*
*Bot: dvswitch_bot.py（デーモン版）＋ bot_setup.py（設定ツール）*
*設計思想・開発秘話は別冊『開発ノート（ブログ材料）』を参照*
