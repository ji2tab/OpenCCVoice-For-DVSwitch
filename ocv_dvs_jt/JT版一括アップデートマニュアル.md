# JT版一括アップデートマニュアル

**Document Version: V1.0（2026-07-15）**

GitHub（`ji2tab/OpenCCVoice-For-DVSwitch` main）の最新 **JT版（Open JTalk 版）** 一式を、稼働中のノードへ**1回のコピペ**で反映する手順書です。バックアップ → 取得 → 構文チェック → 版確認 → サービス再起動までを一括で行います。

> **前提:** 構築マニュアルに従って OpenCCVoice が**導入済み**のノードが対象です。新規構築は
> 「[OpenCCVoice for DVSwitch 構築・導入・設定 マニュアル](https://jj2yyk.forums.gr.jp/2026/06/06/openccvoice-for-dvswitch-setup-manual/)」を参照してください。
> 更新全般（VV版・個別ファイル更新・トラブル対応の詳細）は別冊『Deploy_manual.md』にあります。本書はその **JT版・全ファイル一括版** です。

---

## 0. 対象と前提

**対象ノード:** JT版 ＝ Raspberry Pi（Open JTalk）系。ocv-uhf / ocv-vhf / Pi-Star 同居機など。

> 🔴 **VV版ノード（ocv-voicevox 等）にはこのブロックを流さないでください。**
> bot が JT版で上書きされ、VOICEVOX が動かなくなります（VV版は `ocv_dvs_vv/` 配下から取得する別手順です）。
> 見分け方: `grep -m1 '^__version__' /opt/dvswitch_bot/bin/dvswitch_bot.py` の版に
> **`vv` サフィックスが付いていれば VV版**（例: V1.96vv）。付いていなければ JT版です。

**共通の前提（構築マニュアルどおりの配置）:**

| 項目 | 値 |
|---|---|
| bot 本体 | `/opt/dvswitch_bot/bin/dvswitch_bot.py` |
| 設定ツール | `/opt/dvswitch_bot/bin/bot_setup.py` |
| 固定WAV生成 | `/opt/dvswitch_bot/bin/create_wav.sh` |
| DVSwitch設定 | `/opt/dvswitch_bot/bin/dvs_config.sh` |
| 送信テスト | `/opt/dvswitch_bot/bin/test_send.py` |
| ダッシュボード | `/opt/dvswitch_bot/web/app.py`（JT/VV 共用版） |
| サービス | `dvswitch-bot` / `dvswitch-web` |

- 対象マシンに SSH でログインでき、インターネット（GitHub raw）へ到達できること
- 設定ファイル（`bot_config.json` / `wav_source.json`）と WAV には**触れません**。設定と音声はそのまま残ります

**Pi-Star 同居機のみ:** 実行前に書き込み可へ切り替えてください。

```bash
rpi-rw
```

---

## 1. 一括アップデート（コピペ1ブロック）

下のブロックを丸ごとコピーして端末に貼り付けます。`curl -fsSL | sudo tee` 方式のため、**取得に失敗（404等）した場合はファイルを書き込む前に停止**し、既存ファイルは壊れません。

```bash
# ================================================
# OpenCCVoice JT版 一括アップデート（GitHub main）
#   対象: bot / bot_setup / create_wav / dvs_config /
#         test_send / dashboard(app.py 共用)
# ================================================
RAW=https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main
BIN=/opt/dvswitch_bot/bin
WEB=/opt/dvswitch_bot/web
TS=$(date +%y%m%d%H%M%S)

# --- 1) バックアップ（タイムスタンプ付き退避）---
for f in dvswitch_bot.py bot_setup.py create_wav.sh dvs_config.sh test_send.py; do
  sudo cp -p "$BIN/$f" "$BIN/$f.bak.$TS" 2>/dev/null
done
sudo cp -p "$WEB/app.py" "$WEB/app.py.bak.$TS" 2>/dev/null
echo "backup done ($TS)"

# --- 2) 取得（JT版=ocv_dvs_jt/。ocv_dvs_vv/ ではない）---
curl -fsSL "$RAW/ocv_dvs_jt/dvswitch_bot.py"  | sudo tee "$BIN/dvswitch_bot.py"  >/dev/null && echo "bot        fetched" && \
curl -fsSL "$RAW/ocv_dvs_jt/bot_setup.py"     | sudo tee "$BIN/bot_setup.py"     >/dev/null && echo "bot_setup  fetched" && \
curl -fsSL "$RAW/ocv_dvs_jt/create_wav.sh"    | sudo tee "$BIN/create_wav.sh"    >/dev/null && echo "create_wav fetched" && \
curl -fsSL "$RAW/ocv_dvs_jt/dvs_config.sh"    | sudo tee "$BIN/dvs_config.sh"    >/dev/null && echo "dvs_config fetched" && \
curl -fsSL "$RAW/ocv_dvs_jt/test_send.py"     | sudo tee "$BIN/test_send.py"     >/dev/null && echo "test_send  fetched" && \
curl -fsSL "$RAW/dashboard/app.py" | sudo tee "$WEB/app.py"           >/dev/null && echo "app        fetched"

# --- 3) 実行権限（シェルスクリプトのみ）---
sudo chmod +x "$BIN/create_wav.sh" "$BIN/dvs_config.sh"

# --- 4) 構文チェック（__pycache__ を書かない ast.parse 方式）---
python3 -c "import ast; ast.parse(open('$BIN/dvswitch_bot.py',encoding='utf-8').read()); print('bot       syntax OK')" && \
python3 -c "import ast; ast.parse(open('$BIN/bot_setup.py',encoding='utf-8').read()); print('bot_setup syntax OK')" && \
python3 -c "import ast; ast.parse(open('$WEB/app.py',encoding='utf-8').read()); print('app       syntax OK')" && \
bash -n "$BIN/create_wav.sh" && bash -n "$BIN/dvs_config.sh" && echo "sh        syntax OK"

# --- 5) 版の確認 ---
echo "bot:        $(grep -m1 '^__version__' $BIN/dvswitch_bot.py)"
echo "create_wav: $(grep -m1 '^SCRIPT_VERSION=' $BIN/create_wav.sh)"
echo "app:        $(grep -m1 'app.py  V' $WEB/app.py)"

# --- 6) サービス再起動（bot と dashboard のみ。ブリッジ群には触れない）---
sudo systemctl restart dvswitch-bot && sudo systemctl restart dvswitch-web && sleep 2 && \
systemctl is-active dvswitch-bot dvswitch-web
```

**Pi-Star 同居機のみ:** 終わったら書き込み不可へ戻します。

```bash
rpi-ro
```

---

## 2. 成功の見え方

- 各ファイルに `fetched`、構文チェックに `syntax OK` が並ぶ
- 版表示が最新（**2026-07-15 時点の目安:** bot `V1.93` / create_wav `V1.2` / app `V3.11`。
  版に `vv` が付いて表示されたら**取得パスを間違えて VV版を入れています** — §5 で戻して確認）
- 最後に `active` が2行（dvswitch-bot / dvswitch-web）
- ブラウザで `http://<IP>:8081/` を開き、tagline の版が新しくなっている
- カーチャンクして応答が返る

---

## 3. 補足事項

- **ブリッジ群（md380-emu / analog_bridge / mmdvm_bridge）は再起動しません。**
  bot と dashboard の更新に無線経路の再起動は不要で、触れないほうが安全です（順序なし同時再起動は Analog_Bridge が無音の半死状態になる既知事象があります）。
- **設定は保持されます。** `bot_config.json` / `wav_source.json` / 各 WAV / DVSwitch の ini には触れません。
- create_wav.sh を V1.1 以前から更新した場合、`--regen`（非対話再生成）を使うには
  `wav_source.json` に texts の記録が必要です。**一度対話モード（引数なし）で生成し直す**と記録されます。
- ダッシュボードが未導入のノード（`/opt/dvswitch_bot/web/` が無い）では、手順1の app 取得と
  再起動が失敗します。その場合はインストーラを使ってください（web/ 作成〜ユニット登録まで自動）:

  ```bash
  curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/install.sh | sudo bash
  ```

---

## 4. 失敗したとき: バックアップから戻す

手順1の冒頭で全ファイルが `*.bak.<タイムスタンプ>` に退避されています。

```bash
# 退避の一覧（最新のタイムスタンプを確認）
ls -la /opt/dvswitch_bot/bin/*.bak.* /opt/dvswitch_bot/web/*.bak.* 2>/dev/null

# 例: bot を戻す（<TS> は上で確認した値）
sudo cp -p /opt/dvswitch_bot/bin/dvswitch_bot.py.bak.<TS> /opt/dvswitch_bot/bin/dvswitch_bot.py
sudo systemctl restart dvswitch-bot
```

app.py も同様に `web/app.py.bak.<TS>` から戻し、`sudo systemctl restart dvswitch-web` します。

---

## 5. トラブルシューティング

**取得が `curl: (22)` で止まる（404/403/429）**
パスの打ち間違い、または GitHub のレート制限です。`-f` により書き込み前に停止しているので既存ファイルは無事です。時間をおいて再実行してください。

**版表示に `vv` が付いた**
VV版（`ocv_dvs_vv/` 配下）を取得しています。§4 でバックアップから戻し、`RAW` のパスがocv_dvs_jt/（本書のとおり）か確認して再実行してください。

**`Unit dvswitch-web.service not found`**
ダッシュボード未導入です。§3 のインストーラを実行してください。

**再起動後に応答が無い**
`sudo journalctl -u dvswitch-bot -n 30 --no-pager` でエラーを確認。構文チェックを通過していれば設定起因が多く、`bot_config.json` は保持されているため通常は起きません。ブリッジ群が疑わしい場合のみ、順序再起動（md380 → analog → mmdvm → bot、3秒間隔）を行います。

---

## 6. 最短まとめ

1. （Pi-Star のみ）`rpi-rw`
2. §1 のブロックを丸ごと貼り付け
3. `syntax OK`・版・`active` 2行を確認
4. （Pi-Star のみ）`rpi-ro`
5. カーチャンクで応答確認

---

*JT版（Open JTalk / Raspberry Pi ノード）専用。VV版ノードの更新は『Deploy_manual.md』の VV版節を参照。リポジトリ: `ji2tab/OpenCCVoice-For-DVSwitch`（main）*
