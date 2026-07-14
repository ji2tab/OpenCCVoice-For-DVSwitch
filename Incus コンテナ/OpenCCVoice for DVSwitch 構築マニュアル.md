# OpenCCVoice for DVSwitch 構築マニュアル
**Debian 12 Bookworm（amd64）版 / OS インストール完了後から**

---

> **このマニュアルの位置づけ**
>
> **OS（Debian 12 Bookworm / amd64）のインストールが完了し、ネットワーク・SSH・
> タイムゾーンなどの基本設定が済んでいる状態**を起点とした構築マニュアルです。
>
> Incus コンテナ基盤の準備（コンテナ作成・macvlan・SSH・qemu 準備・複数機運用）は
> 本書に含みません。**別冊『incus構築マニュアル.md』** を参照してください。
> 物理マシン（ベアメタル）や他の仮想環境でも、amd64 の Debian 12 が用意できていれば
> 本書の手順はそのまま適用できます。
>
> **前提（本書の起点）:**
> - OS: Debian 12 Bookworm（amd64）インストール済み
> - ネットワーク（固定IP等）・SSH・タイムゾーン（Asia/Tokyo）・ロケール設定済み
> - `sudo` 可能なユーザー（例: `ocv`）でログイン済み
> - Incus 上で動かす場合は、md380-emu 実行のためのホスト側 qemu 準備が
>   済んでいること（→『incus構築マニュアル.md』6章）

**凡例:** ✅ 検証済み ／ ⚠️ 要注意 ／ 🔴 重大（外すと成立しない）

---

## 目次

1. [DVSwitch-Server インストール](#1-dvswitch-serverインストール)
2. [dvs 初期設定（ini 生成）と TGIF 切替](#2-dvs初期設定ini生成とtgif切替)
3. [スクリプト一式の取得](#3-スクリプト一式の取得)
4. [dvs_config.sh で TGIF 用の値を確定](#4-dvs_configshでtgif用の値を確定)
5. [md380-emu の確認と起動](#5-md380-emuの確認と起動)
6. [音声合成環境（Open JTalk + SoX）](#6-音声合成環境open-jtalk-sox)
7. [固定 WAV の作成](#7-固定wavの作成)
8. [送信テスト](#8-送信テスト)
9. [Bot 本体と設定ツールの導入](#9-bot本体と設定ツールの導入)
10. [常駐化（systemd）](#10-常駐化systemd)

> **最短ルート:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

---

## 1. DVSwitch-Server インストール

```bash
sudo apt update
sudo apt install -y wget
cd /tmp
wget http://dvswitch.org/bookworm
chmod +x bookworm
sudo ./bookworm
```

`Verified: Valid DVSwitch Keyring` と `Finished DVSwitch repository install` が
出れば成功。リポジトリの `apt-cache policy` 出力に `b=amd64` と表示されることを
確認してください（armhf 版と混同していないかのチェック）。

```bash
sudo apt install dvswitch-server -y
```

---

## 2. dvs 初期設定（ini 生成）と TGIF 切替

```bash
sudo /usr/local/dvs/dvs
```

`01 初期設定` を完走 → 再起動 → `02 詳細設定 → 24 その他のDMRネットワーク →
1 デフォルトのDMRサーバー変更 → 2 TGIF` で TGIF へ切替。

---

## 3. スクリプト一式の取得

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

---

## 4. dvs_config.sh で TGIF 用の値を確定

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

## 5. md380-emu の確認と起動

md380-emu は ARM32・静的リンクバイナリです。amd64 環境では qemu-arm-static 経由で
実行されます。

### 5-1. アーキテクチャと同梱 qemu の確認

```bash
file /opt/md380-emu/md380-emu
/opt/md380-emu/qemu-arm-static --version
file /opt/md380-emu/qemu-arm-static
```

`md380-emu` が **ARM 32-bit / statically linked**、`qemu-arm-static` が
**5.2.0 系 / x86-64** であることを確認します。amd64 版の dvswitch-server は
md380-emu 専用の qemu-arm-static（5.2.0）を同梱しているため、
**システム全体の qemu-user-static をダウングレードする必要はありません。**

### 5-2. 実行権限の付与と起動

```bash
sudo chmod +x /opt/md380-emu/md380-emu
sudo systemctl restart md380-emu
sleep 3
sudo systemctl status md380-emu --no-pager
```

`active (running)` で `status=11/SEGV` が出ていなければ正常です。

> 💡 Incus コンテナで動かす場合、ホスト側の binfmt_misc 登録（`F` フラグ）が
> 前提です。未実施の場合は『incus構築マニュアル.md』6章を先に確認してください。

---

## 6. 音声合成環境（Open JTalk + SoX）

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

---

## 7. 固定 WAV の作成

```bash
cd /opt/dvswitch_bot/bin
sudo ./create_wav.sh
```

> ⚠️ **カナ確認は毎回丁寧に。** コールサインの読み（例:「ツー」/「ニー」）が
> 名乗り部分と定時メッセージ部分で揺れやすいので、確認画面に出る全項目の
> カナ表記を必ず見比べてから `y` を押してください。既存 WAV は自動バックアップされます。

---

## 8. 送信テスト

**このステップが md380-emu SEGV の最終確認を兼ねます。**

```bash
python3 /opt/dvswitch_bot/bin/test_send.py /opt/dvswitch_bot/001.wav

sudo journalctl -u md380-emu -n 20 --no-pager
sudo systemctl status md380-emu --no-pager
```

`status=11/SEGV` が出ておらず `active (running)` を維持していれば正常です。

---

## 9. Bot 本体と設定ツールの導入

```bash
sudo python3 /opt/dvswitch_bot/bin/bot_setup.py
python3 /opt/dvswitch_bot/bin/dvswitch_bot.py   # 手動起動で動作確認
```

`Config loaded` → `Bot ready — monitoring DMR traffic` が出れば成功。
カーチャンクを送って応答を確認後、`Ctrl+C` で停止。

---

## 10. 常駐化（systemd）

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

*OpenCCVoice for DVSwitch 構築マニュアル（Debian 12 / amd64 版）*
*OS インストール完了後を起点とした構築手順。Incus コンテナ基盤の準備は別冊『incus構築マニュアル.md』参照。*
