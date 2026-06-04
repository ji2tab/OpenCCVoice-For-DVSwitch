# DVSwitch + OpenCCVoice 自動音声応答システム 完全マニュアル V3.0

> **このマニュアルについて**
>
> Raspberry Pi Zero 2W（Bookworm 32-bit）上に DVSwitch-Server を構築し、
> DMR ネットワーク（TGIF）で自動音声応答（デジピーター応答）を行うシステムの
> 構築・運用マニュアルです。
>
> **実機 OCV（JJ2YYK / TGIF TG 44833）で最後まで通した作業ログ**に基づき、
> すべての手順が検証済みです。
>
> **V3.0 での統合内容:**
> - 検証済み版 v3（2026-06-04 実機トレース）を正とし、全技術内容を確定
> - Bot を「設定ツール `bot_setup.py` ＋ デーモン本体 `dvswitch_bot.py`」構成に更新
> - OS は Bookworm 専用に絞り、Bullseye 節を削除
> - 要検証マーク解除（実機で確定した内容のみ記載）

**凡例**

- ✅ **検証済み** — 実機で実行し、想定どおり動作した
- ⚠️ **要注意** — 公開ドキュメントの記載と実機が食い違っていた箇所（実機の値が正）
- 🔴 **重大** — ここを外すとシステムが成立しない決定的ポイント

---

## 目次

### 第1章：システムの概要と準備

- [第0部：今回の構築で判明した「決定的な点」](#第0部今回の構築で判明した決定的な点)
- [第1部：システムの全体像と設計思想](#第1部システムの全体像と設計思想)
- [第2部：事前準備チェックリスト](#第2部事前準備チェックリスト)
- [専門用語ミニ辞典](#専門用語ミニ辞典)

### 第2章：OS のインストールと DVSwitch の実装

- [第3部：OS 準備](#第3部os-準備)
- [第4部：DVSwitch-Server インストール](#第4部dvswitch-server-インストール)
- [第5部：dvs_config.sh で TGIF 用の値を確定](#第5部dvs_configsh-で-tgif-用の値を確定)
- [第6部：サービスの起動確認と修正](#第6部サービスの起動確認と修正)
- [第7部：Monit Service Manager（:2812）の「Does not exist」を消す](#第7部monit-service-manager2812のdoes-not-existを消す)
- [第8部：DVSwitch Dashboard（:80）の表示設定](#第8部dvswitch-dashboard80の表示設定)

### 第3章：音声合成環境と Bot の実装

- [第9部：音声合成環境（Open JTalk + SoX）](#第9部音声合成環境open-jtalk--sox)
- [第10部：ボット用ディレクトリと固定 WAV の作成](#第10部ボット用ディレクトリと固定-wav-の作成)
- [第11部：送信テスト](#第11部送信テスト)
- [第12部：Bot 本体（デーモン版）と設定ツールの導入](#第12部bot-本体デーモン版と設定ツールの導入)
- [第13部：常駐化（systemd）](#第13部常駐化systemd)

### 第4章：運用・バックアップ・法令

- [第14部：運用上の注意と法令遵守](#第14部運用上の注意と法令遵守)
- [第15部：バックアップとリストア](#第15部バックアップとリストア)

### 第5章：付録

- [付録A：修正点まとめ（配布ドキュメント vs 実機）](#付録a修正点まとめ)
- [付録B：トラブルシューティング早見表](#付録bトラブルシューティング早見表)
- [付録C：固定 WAV の個別コマンド生成（検証済み文面）](#付録c固定-wav-の個別コマンド生成)
- [付録D：DVSwitch 側 ini の手動編集（参照用）](#付録ddvswitch-側-ini-の手動編集参照用)
- [付録E：ダッシュボードの Platform 表示を正す](#付録eダッシュボードの-platform-表示を正す)
- [付録F：クイックリファレンス](#付録fクイックリファレンス)
- [付録G：開発秘話 — 5つの魔法](#付録g開発秘話--5つの魔法)

> **最短ルート（クリーン構築）:** 第3部 → 第4部 → 第5部 → 第6部 → 第7部 →
> 第8部 → 第9部 → 第10部 → 第11部 → 第12部 → 第13部。
> 付録は参照用。

---

# 第1章：システムの概要と準備

## 第0部：今回の構築で判明した「決定的な点」

後続の手順で詳述するが、再現時に必ず意識すべき急所を先に挙げる。

1. 🔴 **md380-emu を動かすには 2 つの必須操作がある（別問題・両方必要）。**
   - (a) qemu-user-static を **5.2（Bullseye版）にダウングレードし `apt-mark hold` で固定**（qemu 7.2 では SEGV）。
   - (b) **`md380-emu` バイナリに `chmod +x` で実行権限を付与**（無いと `Permission denied`）。
   バイナリ自体の中身は変更しない。触るのは qemu の入れ替えと実行権限のみ。これが今回最大のハマりどころだった。

2. ⚠️ **USRP ポートは 51000 / 51001。**
   配布ドキュメントには 51000/51001 と書かれた版と 31001 単一の版が混在していたが、実際に動作した値は `rxPort = 51000` / `txPort = 51001`（Analog_Bridge 側）。ボットの送信先は **51000**。

3. ⚠️ **Open JTalk の辞書パスは `/var/lib/mecab/dic/open-jtalk/naist-jdic`。**
   配布ドキュメントの `/var/lib/mecab/dic/naist-jdic` では辞書が開けずエラーになる。

4. ⚠️ **Web ダッシュボードの「Does not exist」は monit の httpd 無効が主因。**
   Quantar_Bridge などが「Does not exist」と出るのは、サービス未起動に加えて、
   **monit の httpd（port 2812）がデフォルトでコメントアウト**されており、
   monit のステータス問い合わせ自体が機能していないことが背景にある。第7部で対処する。

5. ⚠️ **OS は Bookworm に固定する。**
   `apt upgrade` 自体ではディストリは上がらないが、sources.list が trixie を指していると
   trixie に上がってしまい、monit などの挙動が手順書（Bookworm 前提）と食い違う。
   第3部で sources.list が bookworm であることを必ず確認する。

6. 🔴 **`dvs` の「01 初期設定」完走が ini 生成の前提条件。**
   インストール直後は `/opt/Analog_Bridge/` の ini が存在しない。`dvs` の初期設定（01）を
   一度完走させて初めて ini が生成される。ini が無い状態で `dvs_config.sh` を実行すると
   `[ERROR] 見つかりません` で止まる。

7. 🔴 **Bot の常駐化は「設定ツール＋デーモン本体」構成を使う。**
   対話設定内蔵の従来版（V1.58/V1.60）は systemd 常駐で `EOFError` により即停止する。
   `bot_setup.py`（対話・JSON 保存）と `dvswitch_bot.py`（JSON を読むだけのデーモン本体）
   に分離して使う。

---

## 第1部：システムの全体像と設計思想

### 1-1. データの流れ

音声を DMR ネットワークに流す際、データは以下の順序でバケツリレーされる。

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
           │
           ▼
┌─────────────────────┐
│   MMDVM_Bridge      │  ← TGIF ネットワークへの橋渡し
└──────────┬──────────┘
           │ DMR (UDP 62031)
           ▼
      TGIF Network TG 44833
```

| コンポーネント | 役割 | 重要度 |
|---|---|---|
| `dvswitch_bot.py` | ログ監視・カーチャンク検知・WAV 送信 | 🔴 必須 |
| `analog_bridge` | 音声プロトコル変換ゲートウェイ | 🔴 必須 |
| `md380-emu` | PCM ⇔ AMBE ソフトウェアコーデック | 🔴 必須 |
| `mmdvm_bridge` | TGIF（DMR ネットワーク）接続中核 | 🔴 必須 |
| `webproxy` | ダッシュボード補助 | 補助 |

> **注意:** `dvswitch-server` という単体のサービスは存在しない（メタパッケージのため）。
> 実体は上記のユニット群。

### 1-2. 設計思想

#### なぜ「ログ監視」なのか？

DVSwitch の心臓部が出力する **MMDVM_Bridge の動作ログ（テキスト）** をリアルタイムで
直接監視する。デジタルデータとしての「通信開始（header）」と「通信終了（end of voice）」を
文字列として正確にキャッチするため、誤動作が一切なく、完璧なタイミングでの応答が可能。
VOX 方式のノイズ誤検知・バタつきとは無縁。

#### なぜ「USRP（UDP）注入」なのか？

仮想サウンドカード経由の音声ルーティングは設定が複雑で競合しやすい。
生成した WAV を USRP プロトコルにパッケージングして DVSwitch のポート（51000）へ
**ネットワーク通信として直接投げ込む**ことで、OS の音声ミキサー設定を完全にバイパス。

#### なぜ「絶対時刻同期」なのか？ ⭐ 最大のブレイクスルー

DMR は「20ms ごとに 1 パケット（1 秒間に厳密に 50 パケット）」という規格。
単純な `time.sleep(0.02)` ではプログラムの処理時間が毎回上乗せされてドリフトが蓄積し、
Analog_Bridge のバッファが枯渇してプツプツ・ケロケロが発生する。

```python
# ❌ 悪い例（ドリフトが蓄積する）
while ...:
    送信()
    time.sleep(0.02)   # 処理時間が上乗せされる

# ✅ 正しい例（絶対時刻に同期する）
next_send_time = time.monotonic()
while ...:
    送信()
    next_send_time += 0.02              # 絶対時刻を 20ms 進める
    sleep_duration = next_send_time - time.monotonic()
    if sleep_duration > 0:
        time.sleep(sleep_duration)      # 遅れた場合は待たずに次へ
```

`time.monotonic()` は単調増加が保証されており、NTP 等のシステム時刻調整による
巻き戻りの影響を受けない。詳細は付録G「魔法 1」を参照。

---

## 第2部：事前準備チェックリスト

実装を始める前に、以下が揃っているか確認すること。

### ハードウェア・OS

- [ ] Raspberry Pi Zero 2W が起動し、SSH で接続できる
- [ ] microSD カード（16GB 以上、Class 10 推奨）
- [ ] 電源（5V 2.5A 以上）

### 資格・登録

- [ ] アマチュア無線技士免許（第三級以上推奨）
- [ ] DMR ID の登録（[radioid.net](https://radioid.net)）
- [ ] TGIF アカウントとパスワード

### 必須パッケージの存在確認（DVSwitch 導入後に実行）

```bash
# Analog_Bridge の存在確認
ls -la /opt/Analog_Bridge/Analog_Bridge.ini

# MMDVM_Bridge の存在確認
ls -la /opt/MMDVM_Bridge/MMDVM_Bridge.ini

# md380-emu の存在確認
sudo systemctl status md380-emu

# ログディレクトリの存在確認
ls -la /var/log/mmdvm/
```

---

## 専門用語ミニ辞典

| 用語 | 読み方 | 意味 |
|---|---|---|
| **DMR** | ディーエムアール | Digital Mobile Radio。デジタル業務無線規格を流用したアマチュア無線方式 |
| **AMBE** | アンビー | Advanced Multi-Band Excitation。DMR で使われる音声圧縮方式（特許あり） |
| **USRP** | ユーエスアールピー | DVSwitch 内でプロトコル名として使われる。Python → Analog_Bridge 間の音声転送規格 |
| **PCM** | ピーシーエム | Pulse Code Modulation。生（無圧縮）のデジタル音声データ |
| **MMDVM** | エムエムディーブイエム | Multi-Mode Digital Voice Modem。多モード対応のデジタル音声モデム |
| **DVSwitch** | ディーブイスイッチ | デジタル音声をプロトコル変換する一連のソフトウェア群 |
| **Analog_Bridge** | アナログブリッジ | DVSwitch の中核。アナログ音声とデジタル音声を変換 |
| **MMDVM_Bridge** | エムエムディーブイエムブリッジ | MMDVM 系プロトコルを DVSwitch に橋渡しする |
| **md380-emu** | エムディーサンパチマルエミュ | MD-380 ファームウェアを利用した AMBE ソフトウェア変換器 |
| **カーチャンク** | — | 短時間の PTT 操作（カー局がする「ブッ」というキー操作） |
| **TG（トークグループ）** | — | DMR における通話グループ。本構成では TGIF TG 44833 |
| **UDP** | ユーディーピー | User Datagram Protocol。早いが信頼性の低い通信プロトコル。音声転送に向く |
| **systemd** | システムディー | Linux のサービス管理機構 |

---

# 第2章：OS のインストールと DVSwitch の実装

## 第3部：OS 準備

### 3-1. OS 書き込み・初回起動 ✅

Raspberry Pi OS (Legacy, 32-bit) Lite を書き込み、起動。SSH 等で接続する。

Raspberry Pi Imager では **「Raspberry Pi OS Lite (Legacy, 32-bit)」**
（"A port of Debian Bookworm ..." と表示されるもの）を選ぶ。"Legacy" の付かない
最新版は trixie の可能性があるため注意。

#### OS イメージ直リンク

本検証で使用したのは **`2025-05-13-raspios-bookworm-armhf-lite.img.xz`**（約 493MB）。
**ファイル名に `bookworm` が含まれるもの**を必ず選ぶこと（`trixie` 版は手順書とズレる）。

```
# JAIST（北陸先端大）ミラー — 国内・高速
https://ftp.jaist.ac.jp/pub/raspberrypi/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz

# 山形大ミラー
https://ftp.yz.yamagata-u.ac.jp/pub/linux/raspberrypi/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz

# 公式（Raspberry Pi 財団）
https://downloads.raspberrypi.com/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz
```

SHA256 チェックサム（JAIST）:
```
https://ftp.jaist.ac.jp/pub/raspberrypi/raspios_lite_armhf/images/raspios_lite_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-lite.img.xz.sha256
```

ダウンロード後、照合してから書き込む（推奨）:

```bash
# Linux/Mac
sha256sum -c 2025-05-13-raspios-bookworm-armhf-lite.img.xz.sha256
# Windows
certutil -hashfile 2025-05-13-raspios-bookworm-armhf-lite.img.xz SHA256
```

> **リンク切れ時の探し方:** 各ミラーの `raspios_lite_armhf/images/` 配下から
> **ファイル名に `bookworm` を含む** `...-armhf-lite.img.xz` を選ぶ。
> stable が trixie に切り替わった後は `raspios_oldstable_lite_armhf/` 側で bookworm を探す。

起動後に確認:

```bash
uname -a
# Linux OCV 6.12.x+rpt-rpi-v7 ... armv7l を確認
```

### 3-2. 🔴 sources.list が bookworm であることを確認 ✅

`apt upgrade` の前に、リポジトリが bookworm を指していることを確認する。

```bash
grep -rE "bookworm|trixie" /etc/apt/sources.list /etc/apt/sources.list.d/
```

出力がすべて `bookworm` であること（`trixie` が一つも無いこと）を確認する。

```bash
cat /etc/os-release | grep VERSION_CODENAME    # bookworm であること
```

### 3-3. システム更新 ✅

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

再起動後に確認:

```bash
uname -a && cat /etc/os-release | grep VERSION_CODENAME
```

---

## 第4部：DVSwitch-Server インストール

### 4-1. リポジトリ登録 ✅

```bash
cd /tmp
wget http://dvswitch.org/bookworm
cat bookworm          # 中身を確認してから実行する（GPGキー取得とリポジトリ追加のみ）
chmod +x bookworm
sudo ./bookworm
```

`Verified: Valid DVSwitch Keyring (72147EC1E788D4C3)` と
`Finished DVSwitch repository install` が出れば成功。

### 4-2. 本体インストール ✅

```bash
sudo apt install dvswitch-server -y
```

- `Error, YSFHosts.txt file does not seem to be valid` が出るが**無害**（YSF未使用時）。
- `Could not execute systemctl` も**実機起動後は問題なし**。

### 4-3. 🔴 初期設定メニュー（ini ファイル生成のために必須） ✅

メニューの実体は **`/usr/local/dvs/dvs`**（`dvswitch-menu` ではない）。

```bash
sudo /usr/local/dvs/dvs
```

> 🔴 **この初期設定（01）を一度通さないと `/opt/Analog_Bridge/` 配下の ini が生成されない。**
> 後段の `dvs_config.sh`（第5部）を実行する前提条件として、ここを必ず一度通しておく。
> ini が無いまま `dvs_config.sh` を実行すると `[ERROR] 見つかりません` で止まる。

> ⚠️ **ここで入れる値の多くは後で `dvs_config.sh` が上書きする。**
> この時点では値の厳密さより「一度完走させて ini を生成すること」が目的。
> パスワードやポートはデフォルトのまま通してよい。

#### 画面遷移（Menu Script v.1.61 の実際の入力）

1. **メインメニュー** → `01 初期設定` を選択
2. `初めに行う設定` → `Yes`
3. `Callsign` → 例 `JJ2YYK`
4. `CCS7/DMR ID ?` → 例 `4402396`（7桁）
5. `CCS7/DMR ID + 2桁の数（00〜99）?` → 例 `440239652`（DMR ID + ESSID 52）
6. `Dstar module ? (A〜Z)` → 例 `B`（D-STAR 未使用でも入力を求められる）
7. `NXDN ID?` → 空欄のまま Enter（NXDN 未使用）
8. `USRP ポート番号` → 空欄のまま（後で `dvs_config.sh` が 51001/51000 にする）
9. `Analog_Bridge.ini` 確認 → `Yes`（デフォルト値。第5部で上書きされる）
10. `ローカル BM サーバー選択` → 任意（TGIF 運用では後で上書きされる）
11. `Brandmeister のパスワード` → デフォルト `passw0rd` のまま Enter で可
12. `Hardware Vocoder (AMBE)` → **`4 ハードウェア Vocoder を使わない（ソフトウェア Vocoder を使う）`** を選択
13. `入力終了` → `Yes`

完了後、再起動する。

### 4-4. ⚠️ 詳細設定で DMR サーバーを TGIF に切替 ✅

```bash
sudo /usr/local/dvs/dvs
```

画面遷移:

1. **メインメニュー** → `02 詳細設定`
2. **詳細設定メニュー** → `24 その他の DMR ネットワーク`
3. **DMR ネットワーク** → `1 デフォルトの DMR サーバー変更`
4. → `2 TGIF` を選択（「現在のサーバー: TGIF」になることを確認）
5. メインメニューまで戻って `dvs` を終了

---

## 第5部：dvs_config.sh で TGIF 用の値を確定（🔴 必須）

`dvs` の初期設定（01・02）で ini が生成・TGIF 化されたら、対話ツール
**`dvs_config.sh`** で、コールサイン／DMR ID／TGIF パスワード／送信 TG／USRP ポートを
一括設定する。**この順序（dvs → dvs_config.sh）が前提。**

### 5-0. 🔴 ツール置き場 `/opt/dvswitch_bot/bin/` を作り、全スクリプトを取得

本手順で使う 5 本のスクリプト（`dvs_config.sh` / `create_wav.sh` / `test_send.py` /
`dvswitch_bot.py` / `bot_setup.py`）は、**すべて `/opt/dvswitch_bot/bin/` に集約**する。
ホーム直下に散らからず、後の管理（バックアップ・更新）も一箇所で済む。

> **配置の考え方:** スクリプト（実行ファイル）は `/opt/dvswitch_bot/bin/`、
> bot が読む WAV・設定 JSON は `/opt/dvswitch_bot/` 直下。役割で階層を分ける。

```bash
# 置き場を作成（bin はスクリプト、直下は WAV・JSON 用）
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

> 5 本が並び、`.sh`/`.py` に実行権（`x`）が付いていれば取得完了。
> 以降の各部（固定 WAV 作成・送信テスト・bot 常駐化）は、ここで取得済みの
> スクリプトを使う。個別の再ダウンロードは不要。

### 5-1. dvs_config.sh を実行

中身を確認したら実行（`bin/` に cd して実行、または絶対パスで）:

```bash
cd /opt/dvswitch_bot/bin
sudo ./dvs_config.sh
```

このツールがすること:

- 編集前に **`/opt/bak/YYMMDDHHMMSS/`** へ 3 つの ini を自動バックアップ
  （`MMDVM_Bridge.ini` / `DVSwitch.ini` / `Analog_Bridge.ini`）
- 対話入力 5 項目：`callsign` / `dmrid(7桁)` / `essid(2桁)` / `tgifpassword` / `txtgif`
- 固定セット：
  - MMDVM: `[DMR] Enable=1`、`[DMR Network] Enable=1`、`Address=tgif.network`
  - Analog: `[USRP] txPort=51001` / `rxPort=51000` / `usrpAudio=AUDIO_USE_GAIN` / `tlvAudio=AUDIO_USE_GAIN`
- `Id`（MMDVM）と `repeaterID`（Analog）は **dmrid(7桁) + essid(2桁)** で組み立てる
- `gatewayDmrId`（Analog）は dmrid(7桁) をセット

オプション:

```bash
sudo ./dvs_config.sh -r     # バックアップから復元
sudo ./dvs_config.sh -d     # /opt/bak/ 配下のバックアップを全削除
sudo ./dvs_config.sh -h     # ヘルプ
```

#### 対話入力の値（本トレースの実績値）

| 項目 | 入力例 | 備考 |
|---|---|---|
| Callsign | `JJ2YYK` | 自局コールサイン |
| DMR ID(7桁) | `4402396` | 自局 DMR ID |
| ESSID(2桁) | `52` | サブ番号（枝番号） |
| TGIF Password | （TGIF アカウントの値） | TGIF サイトで発行したもの |
| 送信 TG（txTg） | `44833` | ボット音声が乗る DMR TG |

確認画面で内容を確認し、`y` で保存。

#### 設定反映とTGIF ログイン確認

```bash
sudo systemctl restart analog_bridge mmdvm_bridge
```

TGIF ログイン確認（**MMDVM_Bridge のログは journal ではなく日付別ログファイル**に出る）:

```bash
sudo tail -40 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

末尾付近に次の行が出ていればログイン成功:

```
DMR, Logged into the master successfully: tgif.network:62031
```

> ⚠️ **`dvs_config.sh` は `DVSwitch.ini` を変更しない**（バックアップのみ）。
> `exportTG` を明示設定したい場合は付録D を参照。

> **TGIF が TG 4000 に戻る件:** TGIF Network 側のダッシュボードで Static 設定が無いと
> 一定時間でデフォルト（4000）へ戻る。受信を継続したい場合は TGIF ダッシュボードで
> 44833 を Static 登録すること。

---

## 第6部：サービスの起動確認と修正

### 6-1. サービス一覧の確認 ✅

```bash
sudo systemctl list-units --all | grep -E "analog|mmdvm|md380|bridge|dvswitch|webproxy"
```

**見るべきポイント:**
- `analog_bridge` / `mmdvm_bridge` / `webproxy` が `active (running)` であること
- `md380-emu` が `activating (auto-restart)` になっていないか

### 6-2. 🔴🔴 md380-emu の SEGV と qemu ダウングレード ✅

**症状:** TGIF 等から実際に信号が入り AMBE デコードが走った瞬間、
`md380-emu.service: Main process exited, code=killed, status=11/SEGV` を吐いて
auto-restart を無限に繰り返す。

**原因:** Bookworm 標準の **qemu-user-static 7.2.x** が md380-emu の ARM バイナリと非互換。
Bullseye の **qemu 5.2.x** では正常動作する。

**対処:** Bullseye 版 qemu パッケージを公式アーカイブから取得してダウングレードする。

```bash
# 一括実行版（トレースで実際に通したワンライナー）
wget http://archive.raspbian.org/raspbian/pool/main/q/qemu/qemu-user-static_5.2+dfsg-11+deb11u5_armhf.deb -O /tmp/qemu52.deb && sudo systemctl stop md380-emu && sudo dpkg -i /tmp/qemu52.deb && sudo apt-mark hold qemu-user-static && sudo chmod +x /opt/md380-emu/md380-emu && sudo systemctl restart md380-emu && sleep 3 && sudo systemctl status md380-emu --no-pager && qemu-arm-static --version
```

> 🔴 **この節の「必須操作」は 2 つある。両方やらないと md380-emu は動かない。**
> 1. **qemu を 5.2 へダウングレード**（＋ `apt-mark hold` で固定）… SEGV を止める
> 2. **`chmod +x` で実行権限を付与**… `Permission denied` を止める
>
> この 2 つは独立した別問題。片方だけでは不十分。

> ⚠️ **この段階での running 表示は「起動できた」ことの確認に過ぎない。**
> SEGV は実際に AMBE デコードが走ったときに発生する。最終確認は第11部の送信テスト後に行う。

---

## 第7部：Monit Service Manager（:2812）の「Does not exist」を消す

### この部で何をするか

**対象:** `http://<IP>:2812/`（Monit Service Manager。DVSwitch Dashboard の :80 とは別物）

**目的:** 赤字「Does not exist」と出ているプロセスを緑の「OK」にする。

**原因は 2 つある（OS 世代は無関係。DVSwitch インストール直後の素の状態で起きる）:**

| # | 原因 | 何が起きているか |
|---|---|---|
| 1 | **monit の Web 機能（:2812）が無効** | `/etc/monit/monitrc` の httpd 設定がコメントアウトされたまま |
| 2 | **プロセス自体が停止＋自動起動オフ** | `quantar_bridge.service` 等が disabled・未起動 |

### ステップ 1：症状を確認する ✅

```bash
sudo monit status
```

`Error receiving data -- Connection reset by peer` が出れば、monit の Web 機能が無効（原因1が該当）。

### ステップ 2：monit の Web 機能（:2812）を開通させる 🔴

まず行番号を確認する（環境で前後するので必ず確認）:

```bash
sudo grep -nE "set httpd|use address|allow localhost|allow admin" /etc/monit/monitrc
```

標準状態では次の 4 行がコメントアウトされている:

```
159:#set httpd port 2812 and
160:#    use address localhost
161:#    allow localhost
162:#    allow admin:monit
```

`grep` で見えた実際の行番号に合わせて置き換える（下記は 159〜162 の例）:

```bash
sudo sed -i '159,162c\
set httpd port 2812 and\
    use address 0.0.0.0\
    allow localhost\
    allow 192.168.1.0/24' /etc/monit/monitrc
```

> ⚠️ **自分の LAN が `192.168.1.0/24` 以外の場合は変更**（例: `192.168.0.0/24`）。
> `use address 0.0.0.0` にすること（`localhost` のままだと外部 IP から開けない）。

書き換え結果を確認:

```bash
sudo sed -n '159,162p' /etc/monit/monitrc
```

### ステップ 3：止まっているプロセスを起動する 🔴

```bash
sudo systemctl enable --now quantar_bridge
```

他のプロセスが対象なら、`quantar_bridge` の部分をそのサービスの systemd ユニット名に置き換える。

### ステップ 4：monit に状態を取り直させて「OK」を確認する ✅

```bash
sudo systemctl restart monit && sleep 8 && sudo monit reload && sleep 12 && sudo monit status Quantar_Bridge
```

`status  OK` と出れば成功。

> **ハマりどころ:** monit は状態収集に少し時間がかかる。`reload` 後 **十数秒待って**から確認する。

> **使わないプロセスが「Does not exist」のままでも:** 使う予定がなければ実害はない。

---

## 第8部：DVSwitch Dashboard（:80）の表示設定

### 8-1. DocumentRoot の変更（:80 で DVSwitch Dashboard を表示）✅

> これは **DVSwitch Dashboard**（:80）の設定。Monit Service Manager（:2812・第7部）とは別物。

初期状態では `http://<IP>/` が Apache のデフォルトページを表示する。
DVSwitch Dashboard の実体は `/usr/share/dvswitch` なので DocumentRoot を変更する:

```bash
sudo sed -i 's|DocumentRoot /var/www/html|DocumentRoot /usr/share/dvswitch|' \
  /etc/apache2/sites-enabled/000-default.conf
sudo systemctl restart apache2
```

`http://<IP>/` で「DVSwitch Dashboard」が表示されれば成功。

> **補足:** Zero 2W + SD カードでは初回表示が重い。`top` で `wa`（I/O待ち）が高い場合は
> SD のランダムアクセス遅延が主因。サービスを止めるより、まず全サービスを正常稼働させてから判断する。

---

# 第3章：音声合成環境と Bot の実装

## 第9部：音声合成環境（Open JTalk + SoX）

### 9-1. パッケージ導入 ✅

```bash
sudo apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic \
  hts-voice-nitech-jp-atr503-m001 sox unzip
```

| パッケージ | 用途 |
|---|---|
| open-jtalk | 日本語テキスト音声合成エンジン本体 |
| open-jtalk-mecab-naist-jdic | 日本語形態素解析用辞書 |
| hts-voice-nitech-jp-atr503-m001 | 標準音声モデル（男声・動作確認用） |
| sox | 音声フォーマット変換ツール |
| unzip | ZIP ファイル解凍用 |

### 9-2. 高品質音声「メイ」導入 ✅

```bash
cd ~
wget -L --content-disposition \
  https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip

# ファイル名にクエリ文字列が付くことがあるので実ファイル名を確認
ls *.zip*
unzip 'MMDAgent_Example-1.8.zip'*

sudo mkdir -p /usr/share/hts-voice/mei
sudo cp MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice /usr/share/hts-voice/mei/
rm -rf MMDAgent_Example-1.8 'MMDAgent_Example-1.8.zip'*
```

### 9-3. 🔴 動作確認（辞書パスに注意） ✅

⚠️ 辞書パスは **`/var/lib/mecab/dic/open-jtalk/naist-jdic`**（`open-jtalk/` を含む）。

```bash
echo "テスト、動作確認。" | open_jtalk \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -ow /tmp/test.wav && \
sox /tmp/test.wav -r 8000 -c 1 -b 16 /tmp/test_8k.wav && echo OK
```

`OK` が出れば成功。`Cannot open ... naist-jdic` が出る場合はパスが誤り。

> **なぜ `open-jtalk/` を挟むのか:** Debian/Raspbian の `open-jtalk-mecab-naist-jdic`
> パッケージは辞書を `/var/lib/mecab/dic/open-jtalk/naist-jdic/` に配置する。
> 配布ドキュメントの `/var/lib/mecab/dic/naist-jdic` は一階層ずれており誤り。
> 不明な場合は `find /var/lib/mecab -name "sys.dic"` で確認する。

---

## 第10部：ボット用ディレクトリと固定 WAV の作成

### 10-1. ボット用ディレクトリ（第5-0で作成済み） ✅

`/opt/dvswitch_bot/`（および `bin/`）は**第5-0で作成済み**。固定 WAV はこの直下
（`/opt/dvswitch_bot/`）に置く。未作成の場合のみ次を実行:

```bash
sudo mkdir -p /opt/dvswitch_bot/bin
sudo chown -R ocv:ocv /opt/dvswitch_bot
```

> 別ユーザーで運用する場合は `ocv` を読み替えること。

### 10-2. 固定 WAV 作成（対話式スクリプト） ✅

固定 WAV は第5-0で取得済みの対話式スクリプト `create_wav.sh` で生成する。
出力先はスクリプト内で `/opt/dvswitch_bot/`（直下）に固定。

```bash
cd /opt/dvswitch_bot/bin
sudo ./create_wav.sh
```

対話入力の流れ:

1. コールサイン（例 `JJ2YYK`）→ 自動カナ変換結果を確認・修正
2. 設置場所の地名（例 `おわりあさひ`。ひらがな推奨）
3. 定時メッセージ1 → カナ確認・修正
4. 定時メッセージ2 → カナ確認・修正
5. 確認プロンプトで `Y`

生成されるファイル:

| ファイル | 用途 |
|---|---|
| `fixed_intro.wav` | カーチャンク応答のイントロ |
| `fixed_outro.wav` | カーチャンク応答のアウトロ |
| `time_intro.wav` | 時報のイントロ |
| `001.wav` | 定時メッセージ1 |
| `002.wav` | 定時メッセージ2 |

確認:

```bash
ls -la /opt/dvswitch_bot/
soxi /opt/dvswitch_bot/*.wav    # 全ファイル 8000Hz / 1ch / 16-bit を確認
```

> 個別コマンドで手動生成する方法（TGIF 送信まで検証した文面）は **付録C** を参照。

---

## 第11部：送信テスト

### 11-1. テスト送信ツール（第5-0で取得済み） ✅

`test_send.py` は第5-0で `/opt/dvswitch_bot/bin/` に取得済み。

主要パラメータ（必要なら確認）:

```python
UDP_IP = "127.0.0.1"
UDP_PORT = 51000
PACKET_INTERVAL = 0.02            # 20ms
PRE_POST_PADDING_PACKETS = 75     # 前後 1.5 秒の無音
```

### 11-2. 実行 ✅

```bash
python3 /opt/dvswitch_bot/bin/test_send.py /opt/dvswitch_bot/001.wav
```

TGIF TG 44833 で音声が出れば**経路開通**。

> 第5部でサービスは設定反映済みなので、ここでの再起動は不要。
> bot が常駐している場合は二重送信になるため、テスト時は bot を停止する。

### 11-3. 🔴 md380-emu SEGV の最終確認 ✅

```bash
sudo journalctl -u md380-emu -n 20 --no-pager   # SEGV が出ていないこと
sudo systemctl status md380-emu --no-pager       # active (running) のまま
```

SEGV が再発する場合は qemu が 7.2 に戻っていないか確認する
（`qemu-arm-static --version` が 5.2.x か、`apt-mark` で hold 済みか）。

---

## 第12部：Bot 本体（デーモン版）と設定ツールの導入

### この部で何をするか

送信テスト（第11部）で経路が開通したので、自動応答 bot を導入する。

| ファイル | 役割 |
|---|---|
| `bot_setup.py` | 対話で設定を作り、`/opt/dvswitch_bot/bot_config.json` に保存する設定ツール |
| `dvswitch_bot.py` | デーモン本体。起動時に JSON を読むだけ（対話しない）。常駐向け |

> **なぜ分けるのか:** 従来版（V1.58 / V1.60）は起動時に `input()` で対話設定を求めるため、
> systemd で常駐させると**標準入力が無く `EOFError` で即停止**する。
> デーモン本体は、設定ファイルが**無い／壊れている／値が不正**なら
> **エラーを出して停止する（フェイルセーフ）**。

機能: ナイトモード・毎正時時報・定時メッセージ（001/002 交互）・カーチャンク応答・
絶対時刻同期送信・ログローテーション自動追従

### 12-1. bot 本体とツール（第5-0で取得済み） ✅

`dvswitch_bot.py` と `bot_setup.py` は第5-0で `/opt/dvswitch_bot/bin/` に取得済み。
未取得の場合のみ次を実行:

```bash
cd /opt/dvswitch_bot/bin
BASE=https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main
curl -fsSL "$BASE/dvswitch_bot.py" -o dvswitch_bot.py
curl -fsSL "$BASE/bot_setup.py"  -o bot_setup.py
chmod +x dvswitch_bot.py bot_setup.py
```

### 12-2. ⚠️ パラメータの確認 ✅

```bash
grep -nE "^UDP_IP|^UDP_PORT|^DICT_PATH|^CONFIG_PATH" /opt/dvswitch_bot/bin/dvswitch_bot.py
```

期待値:

| 変数 | 正しい値 |
|---|---|
| `UDP_IP` | `127.0.0.1` |
| `UDP_PORT` | `51000`（Analog_Bridge の rxPort と一致） |
| `DICT_PATH` | `/var/lib/mecab/dic/open-jtalk/naist-jdic` |
| `CONFIG_PATH` | `/opt/dvswitch_bot/bot_config.json` |

`MY_CALLSIGN` も自局に合わせる（既定は `JJ2YYK`）:

```bash
grep -n "^MY_CALLSIGN" /opt/dvswitch_bot/bin/dvswitch_bot.py
# 変更が必要なら:
# sudo sed -i 's/^MY_CALLSIGN = .*/MY_CALLSIGN = "JJ2YYK"/' /opt/dvswitch_bot/bin/dvswitch_bot.py
```

### 12-3. 🔴 設定ツールで bot_config.json を作成 ✅

**デーモン本体を動かす前に、必ず設定ツールを実行する。**
未実行だと本体はフェイルセーフで起動を拒否する（それが正しい挙動）。

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py
```

対話入力:

| 項目 | 内容 | 既定 |
|---|---|---|
| 最小受信時間 (秒) | これ未満は無視 | 0.5 |
| 最大受信時間 (秒) | これ以上はカーチャンクとしない（通常 QSO 扱い） | 3.9 |
| 放送回数 (1/2/3) | 1時間あたりの定時メッセージ回数（正時除く） | 2 |
| ナイトモード (y/n) | 夜間の時報・定時メッセージ抑制 | y |
| N1（開始時） | この時刻の時報まで送出 → 以降抑制 | 22 |
| N2（終了時） | この時刻まで抑制 → N2+1時の時報で再開 | 5 |

確認:

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py -s     # 現在の設定を表示＋有効性チェック
cat /opt/dvswitch_bot/bot_config.json
```

### 12-4. 手動起動で動作確認（常駐化の前に） ✅

```bash
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py
```

- 起動時に `[..] Config loaded /opt/dvswitch_bot/bot_config.json` が出ればフェイルセーフ通過。
- 設定が無い／不正だとここでエラーを出して止まる（その場合は 12-3 をやり直す）。
- 実際にカーチャンクを送って応答が返るか確認する。
- 確認できたら `Ctrl+C` で停止し、第13部の常駐化へ進む。

---

## 第13部：常駐化（systemd）

> 🔴 **前提:** 第12-3 で `bot_config.json` を作成済みであること。
> 未作成だとデーモンはフェイルセーフで起動を拒否し、`Restart=on-failure` により
> **再起動を繰り返して止まり続ける**（設定漏れに気づける、意図した挙動）。

```bash
sudo tee /etc/systemd/system/dvswitch-bot.service > /dev/null << 'EOF'
[Unit]
Description=DVSwitch Bot (OpenCCVoice, daemon based on V1.60)
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

> 別ユーザーで運用する場合は `ExecStart` のパスと `User=` を読み替えること。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dvswitch-bot
sudo systemctl status dvswitch-bot --no-pager
```

`active (running)` で、ログに `Config loaded` と `Bot ready` が出ていれば成功。

> ⚠️ `activating (auto-restart)` を繰り返す場合は設定ファイル不正の可能性が高い。
> `sudo journalctl -u dvswitch-bot -n 30 --no-pager` で `Config error` を確認し、
> `sudo python3 /opt/dvswitch_bot/bin/bot_setup.py` で設定を作り直す。

### 13-1. 常駐化後のログの見方

常駐化すると出力は journal に記録される（`StandardOutput=journal` による）。

```bash
# リアルタイム監視（これを常用する）
sudo journalctl -u dvswitch-bot -f

# 直近 50 行
sudo journalctl -u dvswitch-bot -n 50 --no-pager

# 今日のログ
sudo journalctl -u dvswitch-bot --since today --no-pager

# サービスの稼働状態
sudo systemctl status dvswitch-bot --no-pager
```

### 13-2. 手動起動に戻したいとき

```bash
sudo systemctl stop dvswitch-bot                    # 常駐を一時停止
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py       # 画面出力で手動起動（Ctrl+C で終了）
sudo systemctl start dvswitch-bot                   # 確認後、常駐に戻す
```

> **設定を変えたいとき:**
> ```bash
> sudo python3 /opt/dvswitch_bot/bin/bot_setup.py    # 対話で bot_config.json を更新
> sudo systemctl restart dvswitch-bot                # デーモンを再起動して反映
> ```

---

# 第4章：運用・バックアップ・法令

## 第14部：運用上の注意と法令遵守

### 14-1. 電波法の遵守

- [ ] **アマチュア無線技士の免許**を保有していること
- [ ] **コールサイン**を正しく送出していること（システムは応答時に必ず自局コールサインを送出する設計）
- [ ] **自動運用に関する規定**を理解していること（長時間常時無人運用の場合は所轄の総合通信局に相談）

### 14-2. 推奨される運用方法

1. 応答後の抑制時間（デフォルト 15 秒）は変更しない
2. 応答頻度をログで定期的に確認する
3. 同じ TG/リフレクターで他局が交信中に割り込まないよう確認する

### 14-3. ハードウェアの保護

- **SD カードの寿命**: 一時ファイルは `/dev/shm`（RAM ディスク）に書いているが、ログローテーションは定期削除を設定推奨
- **温度管理**: ヒートシンクを装着推奨（`vcgencmd measure_temp` で確認。70℃超は要注意）
- **電源**: 5V 2.5A 以上。電源不足はファイル破損の原因

---

## 第15部：バックアップとリストア

### 15-1. 設定ファイルのバックアップ

```bash
mkdir -p ~/dvswitch_backup
cd ~/dvswitch_backup

sudo cp /opt/Analog_Bridge/Analog_Bridge.ini ./
sudo cp /opt/MMDVM_Bridge/MMDVM_Bridge.ini ./
cp /opt/dvswitch_bot/bin/dvswitch_bot.py ./
cp /opt/dvswitch_bot/bin/bot_setup.py ./
sudo cp /etc/systemd/system/dvswitch-bot.service ./ 2>/dev/null || true
cp /opt/dvswitch_bot/bot_config.json ./
cp /usr/share/hts-voice/mei/mei_normal.htsvoice ./

sudo chown -R $USER:$USER ~/dvswitch_backup
```

```bash
cd ~
tar czf dvswitch_backup_$(date +%Y%m%d).tar.gz dvswitch_backup/
```

このファイルを別の PC やクラウドにコピーして保管する。

### 15-2. SD カード全体のバックアップ（推奨）

ラズパイをシャットダウンし、SD カードを別の PC に挿して:

```bash
# デバイス名を確認（環境により /dev/mmcblk0 や /dev/sdc 等、必ず確認する）
sudo fdisk -l
sudo dd if=/dev/sdb of=~/pistar_backup_$(date +%Y%m%d).img bs=4M status=progress
gzip ~/pistar_backup_*.img
```

### 15-3. リストア手順（新しい Pi で再構築する場合）

1. 第3部から順番に実施
2. バックアップを展開して設定ファイルを戻す:

```bash
cd ~
tar xzf dvswitch_backup_YYYYMMDD.tar.gz
sudo cp ~/dvswitch_backup/Analog_Bridge.ini /opt/Analog_Bridge/
sudo cp ~/dvswitch_backup/MMDVM_Bridge.ini /opt/MMDVM_Bridge/
sudo mkdir -p /opt/dvswitch_bot/bin
sudo cp ~/dvswitch_backup/dvswitch_bot.py /opt/dvswitch_bot/bin/
sudo cp ~/dvswitch_backup/bot_setup.py /opt/dvswitch_bot/bin/
sudo chmod +x /opt/dvswitch_bot/bin/*.py
sudo cp ~/dvswitch_backup/dvswitch-bot.service /etc/systemd/system/
sudo cp ~/dvswitch_backup/bot_config.json /opt/dvswitch_bot/
sudo chown -R ocv:ocv /opt/dvswitch_bot
sudo systemctl daemon-reload
sudo systemctl restart analog_bridge mmdvm_bridge md380-emu
sudo systemctl enable --now dvswitch-bot
```

3. 第11部の動作確認手順を実施

### 15-4. 定期バックアップの自動化（cron）

```bash
crontab -e
```

以下を追加:

```cron
# 毎週日曜 3:00 に DVSwitch 設定をバックアップ
0 3 * * 0 tar czf /home/ocv/dvswitch_backup_$(date +\%Y\%m\%d).tar.gz /opt/Analog_Bridge/Analog_Bridge.ini /opt/MMDVM_Bridge/MMDVM_Bridge.ini /opt/dvswitch_bot/bin/dvswitch_bot.py /opt/dvswitch_bot/bin/bot_setup.py /opt/dvswitch_bot/bot_config.json
```

---

# 第5章：付録

## 付録A：修正点まとめ（配布ドキュメント vs 実機）

| 項目 | 配布ドキュメント | 実機（正） | 印 |
|---|---|---|---|
| ユーザー名 | pi-star | ocv | ⚠️ |
| メニューコマンド | dvswitch-menu | /usr/local/dvs/dvs | ⚠️ |
| USRP rxPort | 51000 / 31001 混在 | 51000 | ⚠️ |
| USRP txPort | 51001 / 31001 混在 | 51001 | ⚠️ |
| ボット UDP_PORT | 51000 | 51000 | ✅ |
| Open JTalk 辞書 | /var/lib/mecab/dic/naist-jdic | /var/lib/mecab/dic/open-jtalk/naist-jdic | ⚠️ |
| md380-emu 実行権限 | （記載なし） | `chmod +x` 必須（第6部） | 🔴 |
| qemu-user-static | （記載なし） | 5.2 へダウングレード＋hold | 🔴 |
| Apache DocumentRoot | （記載なし） | /usr/share/dvswitch | ⚠️ |
| 送信 TG | （環境依存） | txTg / exportTG = 44833 | 🔴 |
| monit httpd（:2812） | （記載なし） | デフォルト無効。有効化が必要（第7部） | 🔴 |
| Quantar_Bridge 等のサービス | （記載なし） | disabled・未起動。`enable --now` が必要（第7部） | 🔴 |
| OS 世代 | （記載なし） | bookworm に固定。sources.list 確認（第3部） | ⚠️ |
| DVSwitch 側設定 | 手動 ini 編集 | `dvs_config.sh` で一括設定（第5部）。手動は付録D | ⚠️ |
| DMR サーバー TGIF 切替 | （記載なし） | dvs 詳細設定02→24→TGIF（第4-4部） | ⚠️ |
| create_wav.sh の URL | `reate_wav.sh` | `create_wav.sh` にリネーム（旧URLは404） | ⚠️ |
| dvs 初期設定の必須性 | （記載なし） | 「01初期設定」完走で /opt/Analog_Bridge の ini が生成（第4-3部） | 🔴 |
| Platform 表示 Unknown | （記載なし） | platformDetect.sh に device-tree 判定を追記（付録E） | ⚠️ |
| bot の常駐化 | 対話設定内蔵版を直接常駐 | bot_setup.py＋dvswitch_bot.py に分離（第12部）。EOFError 回避＋フェイルセーフ | 🔴 |
| スクリプト配置 | ホーム直下に散在 | 5本を `/opt/dvswitch_bot/bin/` に集約（第5-0で一括取得）。systemd の ExecStart も同パス | ⚠️ |

---

## 付録B：トラブルシューティング早見表

| 症状 | 原因 | 対処 |
|---|---|---|
| md380-emu が `Permission denied` | 実行ビット無し | `sudo chmod +x /opt/md380-emu/md380-emu` |
| md380-emu が `status=11/SEGV` を繰り返す | qemu 7.2 の不具合 | qemu 5.2 へダウングレード＋`apt-mark hold`（第6-2部） |
| Open JTalk が `Cannot open ... naist-jdic` | 辞書パス誤り | `/var/lib/mecab/dic/open-jtalk/naist-jdic` を使う |
| `http://<IP>/` が Apache 既定ページ | DocumentRoot 未変更 | `/usr/share/dvswitch` に変更（第8部） |
| 音声は出るが TG が 4000 に戻る | TGIF 側 Static 未設定 | TGIF ダッシュボードで 44833 を Static 登録 |
| ボット音声が無音 | md380-emu 停止 or Analog_Bridge 設定ミス | md380-emu 稼働確認、USRP ポート確認 |
| 音声がプツプツ・ケロケロ | UDP ドリフト | `dvswitch_bot.py` が `time.monotonic()` ベースの絶対時刻同期になっているか確認 |
| dvswitch-bot が `activating (auto-restart)` を繰り返す | 設定ファイル不正/未作成 | `journalctl -u dvswitch-bot` で確認 → `sudo python3 bot_setup.py` で作成 |
| 手動起動の bot が `Config error` で停止 | `bot_config.json` が無い/壊れ/値不正 | `sudo python3 bot_setup.py` で作成。`-s` で検証 |
| Quantar_Bridge 等が「Does not exist」 | monit httpd 無効＋サービス未起動 | 第7部：monitrc の httpd 有効化＋`enable --now`＋`monit reload` |
| `sudo monit status` が `Connection reset by peer` | monit httpd（:2812）がコメントアウト | 第7部 ステップ2：monitrc の httpd ブロックを有効化 |
| `:2812` が外部 IP から開けない | `use address localhost` になっている | `use address 0.0.0.0` に変更して `sudo monit reload` |
| `monit reload` 後も「Does not exist」のまま | monit のデータ収集待ち | 十数秒待って再度 `sudo monit status` |

---

## 付録C：固定 WAV の個別コマンド生成（検証済み文面）

スクリプトを使わず手動で作る場合、またはこのセッションで TGIF 送信まで検証した文面を
そのまま再現したい場合のコマンド。各ファイルは 8kHz / mono / 16bit PCM。

```bash
# fixed_intro.wav（カーチャンク応答イントロ）
echo "こちらは、ジェイジェイツーワイワイケー、おわりあさひ ディーエムアール デジピーターです。" | \
open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -ow /tmp/temp_intro.wav && \
sudo sox /tmp/temp_intro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/fixed_intro.wav

# fixed_outro.wav（カーチャンク応答アウトロ）
echo "カーチャンクです。" | \
open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -ow /tmp/temp_outro.wav && \
sudo sox /tmp/temp_outro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/fixed_outro.wav

# time_intro.wav（時報イントロ・前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、" | \
open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -ow /tmp/time_intro.wav && \
sox /tmp/time_intro.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/time_intro.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse

# 001.wav（定時メッセージ1・前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。オープン、シーシーヴォイス、フォー、ディーブイスイッチからの音声です。" | \
open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -ow /tmp/001_raw.wav && \
sox /tmp/001_raw.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/001.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse

# 002.wav（定時メッセージ2・前後トリム）
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。ティージーアイエフ、ヨンヨンハチサンサンと、インターネット接続しています。" | \
open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
  -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
  -ow /tmp/002_raw.wav && \
sox /tmp/002_raw.wav -r 8000 -c 1 -b 16 /opt/dvswitch_bot/002.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

確認:

```bash
ls -la /opt/dvswitch_bot/
soxi /opt/dvswitch_bot/*.wav    # 全ファイル 8000Hz / 1ch / 16-bit を確認
```

---

## 付録D：DVSwitch 側 ini の手動編集（参照用）

第5部は `dvs_config.sh` による一括設定を本手順とした。
スクリプトが `[WARN] キー ... が見つからず変更できません` を出した場合などの参照用。

### D-1. Analog_Bridge.ini（USRP / 送信 TG）

`/opt/Analog_Bridge/Analog_Bridge.ini`

```ini
[USRP]
address = 127.0.0.1
txPort = 51001        ; Analog_Bridge → 外部（USRP送信）
rxPort = 51000        ; 外部 → Analog_Bridge（ボットはここへ送る）
```

```ini
[AMBE_AUDIO]
txTg = 44833          ; ★ボット音声が乗る DMR TG（最重要）
txTs = 2
colorCode = 1
```

> **補足:** DVSwitch v1.6.4 系の特定バージョンでは `jitterQueueSize` / `pcmBufferMS` が
> コメントアウトされていないと起動時にクラッシュする。該当行があれば先頭に `;` を付ける。

### D-2. DVSwitch.ini（DMR exportTG）

`/opt/MMDVM_Bridge/DVSwitch.ini` の `[DMR]`:

```ini
[DMR]
address = 127.0.0.1
exportTG = 44833      ; ★エクスポート TG
```

> ⚠️ **`dvs_config.sh` はこの `DVSwitch.ini` を変更しない**（バックアップのみ）。
> exportTG を明示設定したい場合はここを手動で編集する。

### D-3. MMDVM_Bridge.ini（TGIF 接続）

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

## 付録E：ダッシュボードの Platform 表示を正す（参照用）

### なぜ Unknown になるのか

`/usr/local/sbin/platformDetect.sh` は `/proc/cpuinfo` の Revision 値を case 文で
機種名に変換しているが、Zero 2 W の Revision（例 `902120`）が case に載っていないため
`Unknown ARM based System` に落ちる。

`/proc/device-tree/model` には完成された機種名があるため、これを使えば新機種でも正しく表示できる。

確認:

```bash
/usr/local/sbin/platformDetect.sh        # → Unknown ARM based System
tr -d '\0' < /proc/device-tree/model; echo   # → Raspberry Pi Zero 2 W Rev 1.0
grep -m1 Revision /proc/cpuinfo          # → 例: 902120
```

### E-1. バックアップ（必須）

```bash
sudo cp /usr/local/sbin/platformDetect.sh /usr/local/sbin/platformDetect.sh.bak.$(date +%F)
```

### 方法B（推奨）：既存スクリプトに device-tree 判定を最小追記

既存ロジックを壊さず、**シェバン直後に device-tree 判定ブロックを差し込むだけ**。
device-tree が取れればそれを返し、取れなければ従来どおり既存ロジックに流れる。

#### B-1. 挿入ブロックを一時ファイルに用意

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
```

#### B-2. /tmp で組み立てて動作確認してから本番に反映

```bash
{ head -1 /usr/local/sbin/platformDetect.sh; \
  cat /tmp/dt_block.sh; \
  tail -n +2 /usr/local/sbin/platformDetect.sh; } > /tmp/platformDetect.test.sh
chmod +x /tmp/platformDetect.test.sh

head -15 /tmp/platformDetect.test.sh              # シェバン直後にブロックが入っているか確認

/tmp/platformDetect.test.sh                       # Raspberry Pi Zero 2 W Rev 1.0 が返ればOK
sudo -u www-data /tmp/platformDetect.test.sh      # www-data でも同じ結果か確認
```

#### B-3. 本番へ反映

```bash
sudo cp /tmp/platformDetect.test.sh /usr/local/sbin/platformDetect.sh
sudo chmod 0755 /usr/local/sbin/platformDetect.sh
/usr/local/sbin/platformDetect.sh        # 最終確認
```

### 方法A（代替）：スクリプト全体を POSIX-sh 版に差し替え

既存を**まるごと新版に置き換える**。判定順序が見直されており、device-tree を最優先で使う。
完全版は旧マニュアル（`DVSwitch-Server 導入完全マニュアル 改訂版`）の第IV部を参照。

### E-2. Web サーバ再起動とダッシュボード確認

> ⚠️ **本環境は Bookworm / Apache2。**
> `lighttpd` ではなく **`apache2`** を再起動する。

```bash
sudo systemctl restart apache2
```

ブラウザで `http://<IP>/` を開き **Ctrl+F5**。
`Hardware Info → Platform` が **`Raspberry Pi Zero 2 W Rev 1.0`** になれば成功。

### E-3. トラブルシュート

| 症状 | 確認・対処 |
|---|---|
| 端末では正しいが Dashboard が Unknown のまま | Ctrl+F5。`sudo systemctl restart apache2` |
| `sudo -u www-data ...` で結果が違う | `sudo chmod 0755 /usr/local/sbin/platformDetect.sh` |
| PHP の `exec()` が無効 | `php.ini` の `disable_functions` を確認 |
| 元に戻したい | `sudo cp /usr/local/sbin/platformDetect.sh.bak.YYYY-MM-DD /usr/local/sbin/platformDetect.sh` |

---

## 付録F：クイックリファレンス

### ポート番号一覧

| ポート | 用途 | プロトコル |
|---|---|---|
| 51000 | dvswitch_bot.py → Analog_Bridge（USRP 受信） | UDP |
| 51001 | Analog_Bridge からの出力（txPort） | UDP |
| 2470 | Analog_Bridge ⇔ md380-emu（AMBE） | UDP |
| 62031 | MMDVM_Bridge → TGIF ネットワーク（DMR） | UDP |
| 80 | DVSwitch Dashboard（Apache） | TCP |
| 2812 | Monit Service Manager | TCP |

### 主要ファイルパス一覧

| パス | 内容 |
|---|---|
| `/opt/Analog_Bridge/Analog_Bridge.ini` | Analog_Bridge 設定ファイル |
| `/opt/MMDVM_Bridge/MMDVM_Bridge.ini` | MMDVM_Bridge 設定ファイル |
| `/opt/MMDVM_Bridge/DVSwitch.ini` | DVSwitch 設定ファイル（exportTG） |
| `/var/log/mmdvm/MMDVM_Bridge-*.log` | ログファイル（Bot の監視対象） |
| `/usr/share/hts-voice/mei/mei_normal.htsvoice` | メイの音声モデル |
| `/var/lib/mecab/dic/open-jtalk/naist-jdic` | Open JTalk 辞書 |
| `/opt/dvswitch_bot/bin/dvswitch_bot.py` | 自動応答 Bot デーモン本体 |
| `/opt/dvswitch_bot/bin/bot_setup.py` | Bot 設定ツール |
| `/opt/dvswitch_bot/bin/test_send.py` | USRP テスト送信ツール |
| `/opt/dvswitch_bot/bin/create_wav.sh` | 固定 WAV 生成スクリプト |
| `/opt/dvswitch_bot/bin/dvs_config.sh` | DVSwitch ini 設定ツール |
| `/opt/dvswitch_bot/bot_config.json` | Bot 設定ファイル |
| `/opt/dvswitch_bot/*.wav` | 固定 WAV ファイル群 |
| `/etc/systemd/system/dvswitch-bot.service` | systemd サービス定義 |
| `/etc/monit/monitrc` | monit 設定ファイル |
| `/usr/local/sbin/platformDetect.sh` | ダッシュボード Platform 判定スクリプト |

### サービス管理コマンド一覧

```bash
# 全サービスまとめて再起動
sudo systemctl restart analog_bridge mmdvm_bridge md380-emu dvswitch-bot

# 個別
sudo systemctl restart analog_bridge
sudo systemctl restart mmdvm_bridge
sudo systemctl restart md380-emu
sudo systemctl restart dvswitch-bot

# 状態確認
sudo systemctl status analog_bridge mmdvm_bridge md380-emu dvswitch-bot --no-pager

# ログ確認
sudo journalctl -u dvswitch-bot -f
sudo journalctl -u md380-emu -n 20 --no-pager
sudo tail -f /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log
```

### トラブル時の最速チェックリスト

```bash
# 1. 全サービスの状態確認
sudo systemctl status analog_bridge mmdvm_bridge md380-emu dvswitch-bot --no-pager

# 2. md380-emu の qemu バージョン確認
qemu-arm-static --version    # 5.2.x であること

# 3. TGIF ログイン確認
sudo tail -20 /var/log/mmdvm/MMDVM_Bridge-$(date +%Y-%m-%d).log

# 4. ポートが開いているか
sudo ss -ulnp | grep -E "51000|2470|62031"

# 5. 全部再起動
sudo systemctl restart analog_bridge mmdvm_bridge md380-emu
```

---

## 付録G：開発秘話 — 5つの魔法

システムを実用レベルの堅牢なものへと昇華させた技術的ブレイクスルーを記録する。

### 魔法 1：【時を操る魔法】絶対時刻によるパケット同期（ドリフト補正）

**課題:** 単純な `time.sleep(0.02)` で 20ms ずつ待機すると、プログラムの処理時間が積もり
DVSwitch のバッファが枯渇して音声が「プツプツ・ケロケロ」に破綻する。

**解決策:** 送信開始時の「絶対時刻」を `time.monotonic()` で記憶し、
`next_send_time = T0 + (seq × 0.02)` で「次は正確に何秒後に送るべきか」を毎回逆算。
`time.monotonic()` は単調増加が保証され NTP 等の時刻調整による巻き戻りの影響を受けない。

**効果:** どんな負荷状況でも透き通るような音質を実現。**本システムの最大の核心技術。**

### 魔法 2：【千里眼の魔法】MMDVM ログ監視による「真の Busy」抽出

**課題:** VOX 方式はノイズ誤検知・無音バタつきが避けられない。

**解決策:** 音声には一切頼らず、MMDVM が吐き出すログの `received network voice header` と
`end of voice transmission` を文字列として直接監視する。

**効果:** 誤動作ゼロ・完全無欠のタイミングで応答。TGIFChanger の GPIO 制御でも使われた大魔法。

### 魔法 3：【空間転移の魔法】USRP プロトコルによる UDP ダイレクト注入

**課題:** 仮想サウンドカード経由の音声ルーティングは設定が複雑で競合しやすい。

**解決策:** サウンドカードを完全に捨て、生成した音声データを USRP プロトコルにパッケージングして
DVSwitch のポート（51000）へネットワーク通信として直接投げ込む。

**効果:** OS の音声ミキサー設定を完全バイパスし、競合トラブルを根絶。

### 魔法 4：【声帯の魔法】`communicate()` による完全なテキストストリーム注入

**課題:** Open JTalk を Python から呼び出す際、引数でテキストを渡すと 0 秒の無音 WAV が
作られる現象が発生。

**解決策:** `subprocess.Popen` と `communicate()` を使い、UTF-8 にエンコードしたテキストを
標準入力ストリームとして直接流し込む。

**効果:** 「ダッシュボードは光るのに音が出ない」という最も厄介なバグを完全排除。

### 魔法 5：【調和の魔法】シンプルな一発生成によるノイズ排除

**課題:** 固定 WAV と生成 WAV の SoX 結合で波形の不連続（クリックノイズ）が発生。

**解決策:** 複雑なファイル結合を捨て、Python の文字列操作の段階で「1つの長い文章」を
完成させ、Open JTalk に一気に喋らせてシンプルな 8kHz 変換だけを行う力技へ回帰。

**効果:** 処理が圧倒的に軽くなり、継ぎ目ノイズを根本から消滅。

### 5つの魔法のまとめ

| # | 魔法の名前 | 何を解決したか | 技術キーワード |
|---|---|---|---|
| 1 | 時を操る魔法 | プツプツ・ケロケロ音声 | 絶対時刻同期・time.monotonic() |
| 2 | 千里眼の魔法 | VOX 誤検知・バタつき | ログ監視・文字列パターン検知 |
| 3 | 空間転移の魔法 | サウンドカード地獄 | USRP プロトコル・UDP 直接注入 |
| 4 | 声帯の魔法 | 音が出ない不可解バグ | subprocess.Popen + communicate() |
| 5 | 調和の魔法 | 継ぎ目ノイズ | シンプル化・文字列で一発生成 |

### 設計思想として残したいこと

1. **「複雑にして賢くする」のではなく「シンプルにして堅牢にする」**
2. **「音声を解釈する」のではなく「ログ（文字）を読む」**
3. **「OS の機能に頼る」のではなく「ネットワーク通信に統一する」**
4. **「曖昧な相対時刻」ではなく「正確な絶対時刻」を基準にする**
5. **「便利な引数渡し」ではなく「確実なストリーム入力」を選ぶ**

---

*初版作成: 2026-06-02（検証済み版 v1）*  
*v2 更新: 2026-06-03（monit 対処・OS 固定確認・OS イメージ直リンク追加）*  
*v3 更新: 2026-06-04（dvs 初期設定手順確定・dvs_config.sh 独立化・create_wav.sh URL 修正・bot 分離構成確定・Platform 表示修正追加）*  
*V3.0 統合: 2026-06-04（検証済み版 v3 を正とし、V2.3 完全マニュアルと改訂版マニュアルを合流。Bookworm 専用に統一。要検証マーク解除）*  
*対応 Bot: dvswitch_bot.py（デーモン版・V1.60 ベース）＋ bot_setup.py（設定ツール）*  
*実機: OCV（Raspberry Pi Zero 2W / Bookworm 32-bit）/ JJ2YYK / TGIF TG 44833*
