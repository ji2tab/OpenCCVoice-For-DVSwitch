# DVSwitch Bot 音声ファイル生成マニュアル

**対象システム:** DVSwitch ログ監視・自動音声応答システム V1.58 (JJ2YYK デジピーター)
**最終更新:** 2026年5月
**実行環境:** Raspberry Pi 等の Linux 環境 (open-jtalk / sox 導入済み)

---

## 概要

bot が読み込む 5 つの WAV ファイルを Open JTalk + SoX で生成する手順書です。
コマンドはすべてターミナルにコピペで実行できます。

### 生成するファイル一覧

| # | ファイル名 | 用途 | 発話内容 |
|---|---|---|---|
| 1 | `fixed_intro.wav` | カーチャンク応答の **イントロ** | こちらは、JJ2YYK、尾張旭 DMR デジピーターです。 |
| 2 | `fixed_outro.wav` | カーチャンク応答の **アウトロ** | カーチャンクです。 |
| 3 | `time_intro.wav`  | 時報の **イントロ** | こちらは、JJ2YYK、 |
| 4 | `001.wav`         | 定時メッセージ 1 | こちらは…OpenCCVoice…からの音声です。 |
| 5 | `002.wav`         | 定時メッセージ 2 | こちらは…TGIF 168 と XLX 834 モジュール Z に接続しています。 |

### ⚠️ V1.58 での変更点

- `time_outro.wav` は **生成不要** になりました。
  時報の「です」は bot 側で動的合成 (`〇〇時です`) に統合されました。
- 旧ファイル名 `fixed_start.wav` / `fixed_end.wav` は廃止。
  bot は `fixed_intro.wav` / `fixed_outro.wav` を期待します。

---

## 共通設定

### パス情報

```text
Open JTalk 辞書 : /var/lib/mecab/dic/open-jtalk/naist-jdic
音声モデル(メイ) : /usr/share/hts-voice/mei/mei_normal.htsvoice
出力ディレクトリ : /opt/dvswitch_bot/
作業ディレクトリ : /tmp/
```

### 音声フォーマット (全ファイル共通)

| 項目 | 値 |
|---|---|
| サンプリングレート | 8000 Hz |
| チャンネル | モノラル (1ch) |
| ビット深度 | 16 bit |
| 前後の無音 | SoX `silence` フィルタで自動トリム |

### sox の共通オプション

全ファイルで以下を統一して使います:

```bash
-r 8000 -c 1 -b 16
silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

- `-r 8000 -c 1 -b 16` … 8kHz / mono / 16bit に変換
- `silence 1 0.1 1% reverse silence 1 0.1 1% reverse` … 前後の無音(0.1秒未満・閾値1%以下)をトリム

> 💡 bot 本体が前後 1.5 秒のパディングを自動付与するため、ここでは無音をしっかり削っておきます。

---

## ① fixed_intro.wav (カーチャンク応答のイントロ)

```bash
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。" | \
  open_jtalk \
    -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
    -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
    -ow /tmp/fixed_intro_raw.wav

sox /tmp/fixed_intro_raw.wav \
  -r 8000 -c 1 -b 16 \
  /opt/dvswitch_bot/fixed_intro.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

---

## ② fixed_outro.wav (カーチャンク応答のアウトロ)

```bash
echo "カーチャンクです。" | \
  open_jtalk \
    -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
    -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
    -ow /tmp/fixed_outro_raw.wav

sox /tmp/fixed_outro_raw.wav \
  -r 8000 -c 1 -b 16 \
  /opt/dvswitch_bot/fixed_outro.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

---

## ③ time_intro.wav (時報のイントロ)

```bash
echo "こちらは、ジェイジェイツーワイワイケー、" | \
  open_jtalk \
    -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
    -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
    -ow /tmp/time_intro_raw.wav

sox /tmp/time_intro_raw.wav \
  -r 8000 -c 1 -b 16 \
  /opt/dvswitch_bot/time_intro.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

> 💡 V1.58 以降は、この後に bot が「〇〇時です」を動的合成して連結します。

---

## ④ 001.wav (定時メッセージ 1)

```bash
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。オープン、シーシーヴォイス、フォー、ディーブイスイッチからの音声です。" | \
  open_jtalk \
    -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
    -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
    -ow /tmp/001_raw.wav

sox /tmp/001_raw.wav \
  -r 8000 -c 1 -b 16 \
  /opt/dvswitch_bot/001.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

---

## ⑤ 002.wav (定時メッセージ 2)

```bash
echo "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。ＴＧＩＦ１６８と、ＸＬＸ８３４モジュールＺに インターネット接続しています。" | \
  open_jtalk \
    -x /var/lib/mecab/dic/open-jtalk/naist-jdic \
    -m /usr/share/hts-voice/mei/mei_normal.htsvoice \
    -ow /tmp/002_raw.wav

sox /tmp/002_raw.wav \
  -r 8000 -c 1 -b 16 \
  /opt/dvswitch_bot/002.wav \
  silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

---

## 動作確認

### 1. ファイルの存在とフォーマット確認

```bash
ls -lh /opt/dvswitch_bot/*.wav
```

期待される出力:

```text
-rw-r--r-- 1 ... fixed_intro.wav
-rw-r--r-- 1 ... fixed_outro.wav
-rw-r--r-- 1 ... time_intro.wav
-rw-r--r-- 1 ... 001.wav
-rw-r--r-- 1 ... 002.wav
```

### 2. 各ファイルの仕様確認

```bash
for f in /opt/dvswitch_bot/{fixed_intro,fixed_outro,time_intro,001,002}.wav; do
  echo "=== $f ==="
  soxi "$f"
done
```

各ファイルが以下の条件を満たしていること:

- **Sample Rate** : 8000 Hz
- **Channels** : 1
- **Precision** : 16-bit

### 3. 試聴 (テスト送信)

bot を一旦停止してから:

```bash
# bot を止める (systemd の場合)
sudo systemctl stop dvswitch_bot

# テスト送信(各ファイル)
python3 ~/test_send.py /opt/dvswitch_bot/fixed_intro.wav
python3 ~/test_send.py /opt/dvswitch_bot/fixed_outro.wav
python3 ~/test_send.py /opt/dvswitch_bot/time_intro.wav
python3 ~/test_send.py /opt/dvswitch_bot/001.wav
python3 ~/test_send.py /opt/dvswitch_bot/002.wav

# 確認できたら bot を再開
sudo systemctl start dvswitch_bot
```

---

## 一括実行用スクリプト (おまけ)

すべて一括で生成したい場合は、以下を `generate_voices.sh` として保存して実行できます:

```bash
#!/bin/bash
# DVSwitch Bot 音声ファイル一括生成

set -e

DICT="/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE="/usr/share/hts-voice/mei/mei_normal.htsvoice"
OUT_DIR="/opt/dvswitch_bot"
TMP_DIR="/tmp"

SOX_OPTS=(-r 8000 -c 1 -b 16)
SILENCE_OPTS=(silence 1 0.1 1% reverse silence 1 0.1 1% reverse)

generate() {
    local out_name="$1"
    local text="$2"
    local raw="${TMP_DIR}/${out_name%.wav}_raw.wav"
    local final="${OUT_DIR}/${out_name}"

    echo "🎙️  生成中: ${out_name}"
    echo "${text}" | open_jtalk -x "${DICT}" -m "${VOICE}" -ow "${raw}"
    sox "${raw}" "${SOX_OPTS[@]}" "${final}" "${SILENCE_OPTS[@]}"
    rm -f "${raw}"
    echo "✅ 完成: ${final}"
}

generate "fixed_intro.wav" "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。"
generate "fixed_outro.wav" "カーチャンクです。"
generate "time_intro.wav"  "こちらは、ジェイジェイツーワイワイケー、"
generate "001.wav"         "こちらは、ジェイジェイツーワイワイケー、尾張旭、DMR、デジピーターです。オープン、シーシーヴォイス、フォー、ディーブイスイッチからの音声です。"
generate "002.wav"         "こちらは、ジェイジェイツーワイワイケー、おわりあさひ ディーエムアール デジピーターです。ティージーアイエフ、イチロクハチと、エックスエルエックス ハチサンヨン モジュールゼットに インターネット接続しています。"

echo ""
echo "=== 生成完了 ==="
ls -lh "${OUT_DIR}"/*.wav
```

使い方:

```bash
chmod +x generate_voices.sh
./generate_voices.sh
```

---

## トラブルシューティング

### Q. `open_jtalk: command not found`

A. Open JTalk が入っていません。インストール:

```bash
sudo apt update
sudo apt install open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001
```

メイの音声モデルは別途必要なので、入っていない場合は手動で配置してください。

### Q. `sox FAIL formats: can't open input file`

A. Open JTalk の出力 (`/tmp/*_raw.wav`) が生成されていません。
辞書パスや音声モデルのパスが正しいか確認:

```bash
ls -l /var/lib/mecab/dic/open-jtalk/naist-jdic
ls -l /usr/share/hts-voice/mei/mei_normal.htsvoice
```

### Q. 書き込み権限エラー (`/opt/dvswitch_bot/`)

A. ディレクトリの所有者を確認:

```bash
ls -ld /opt/dvswitch_bot
```

書き込めない場合は `sudo` 付きで sox を実行するか、ディレクトリの所有者を変更:

```bash
sudo chown $(whoami):$(whoami) /opt/dvswitch_bot
```

### Q. 読み上げ内容を変更したい

A. 各セクションの `echo "..."` の中身を書き換えてから再実行してください。
コールサインは **カタカナ表記** (ジェイジェイツーワイワイケー) にすることで、Open JTalk が正しく読み上げます。

---

## 読み替えメモ (カタカナ表記の参考)

| アルファベット/数字 | カタカナ |
|---|---|
| A B C D E | エー / ビー / シー / ディー / イー |
| F G H I J | エフ / ジー / エイチ / アイ / ジェイ |
| K L M N O | ケー / エル / エム / エヌ / オー |
| P Q R S T | ピー / キュー / アール / エス / ティー |
| U V W X Y Z | ユー / ブイ / ダブリュー / エックス / ワイ / ゼット |
| 0 1 2 3 4 | ゼロ / ワン / ツー / スリー / フォー |
| 5 6 7 8 9 | ファイブ / シックス / セブン / エイト / ナイン |

---

**Document Version:** 1.0 (for bot V1.58)
**Author:** JJ2YYK
