# OpenCCVoice デプロイ（更新）手順マニュアル

GitHub の最新版を、稼働中の OpenCCVoice システムに反映する手順書です。

> **前提:** 本手順は、構築マニュアル
> 「[OpenCCVoice for DVSwitch 構築・導入・設定 マニュアル](https://jj2yyk.forums.gr.jp/2026/06/06/openccvoice-for-dvswitch-setup-manual/)」
> に従ってシステムが**導入済み**であることを前提とします。新規構築の手順（OS・DVSwitch-Server・
> bot 本体の初期導入）は構築マニュアルを参照してください。本書はその後、GitHub 上で更新された
> コードを稼働中システムへ反映する「更新作業」だけを扱います。

対象: すでに OpenCCVoice が構築済みのノード（JT版＝Raspberry Pi / Pi-Star 同居環境、VV版＝x86_64 Linux / VOICEVOX 環境）
やること: GitHub から最新コードを取得 → 構文チェック → サービス再起動

---

## 0. 前提

- 構築マニュアルに従って OpenCCVoice が**導入済み**であること（最重要）
- 対象マシンに SSH でログインできること
- インターネット（GitHub）に接続できること
- 構成は構築マニュアルどおり（下記が共通の前提）

| 項目 | 値 |
|---|---|
| bot 本体 | `/opt/dvswitch_bot/bin/dvswitch_bot.py` |
| 設定ツール | `/opt/dvswitch_bot/bin/bot_setup.py` |
| ダッシュボード | `/opt/dvswitch_bot/web/app.py` |
| bot サービス | `dvswitch-bot` |
| ダッシュボードサービス | `dvswitch-web` |
| GitHub リポジトリ | `ji2tab/OpenCCVoice-For-DVSwitch`（main ブランチ） |

ログインユーザー名（`ocv` / `pi-star` 等）は問いません。手順はすべて `sudo` で実行するため、ユーザーに関係なく動作します。構築マニュアルにあるとおり、配布ドキュメントの `pi-star` は環境により `ocv` に読み替えてください（どちらでも本手順は動作します）。

> **補足:** ダッシュボード（`app.py` / `dvswitch-web` / ポート 8081）は、構築マニュアル本体ではなく別記事「ダッシュボード 導入／取扱説明書」で扱われる追加要素です。ダッシュボードを導入していない環境では、本書のうち bot 本体・設定ツールの更新だけを行い、ダッシュボード（app.py）に関する箇所は読み飛ばしてください。

---

## 1. 既設ノードのアップデート手順（検証済みワンライナー）

稼働中のノードを GitHub `main` の最新版へ最短で更新するコマンドです。ノードの種類（JT版 / VV版）で使い分けてください。いずれも raw URL の3パス（`create_wav.sh` / `dvs_ocv_vv/create_wav.sh` / `dashboard/app.py`）は実在確認済みです。

### JT版ノード（Raspberry Pi / Open JTalk）

`create_wav.sh`（JT版）と共用ダッシュボード `app.py` を更新し、ダッシュボードを再起動して版を確認します。

```bash
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_ocv_JT/create_wav.sh | sudo tee /opt/dvswitch_bot/bin/create_wav.sh >/dev/null && sudo chmod +x /opt/dvswitch_bot/bin/create_wav.sh && curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/app.py | sudo tee /opt/dvswitch_bot/web/app.py >/dev/null && sudo systemctl restart dvswitch-web && grep -m1 SCRIPT_VERSION= /opt/dvswitch_bot/bin/create_wav.sh && grep -m1 '^__version__' /opt/dvswitch_bot/web/app.py
```

### VV版ノード（x86_64 Linux / VOICEVOX）

`create_wav.sh`（VV版）・`dvswitch_bot.py`（VV版）・共用ダッシュボード `app.py` を更新し、bot とダッシュボードの両サービスを再起動して版を確認します。

```bash
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_ocv_vv/create_wav.sh | sudo tee /opt/dvswitch_bot/bin/create_wav.sh >/dev/null && sudo chmod +x /opt/dvswitch_bot/bin/create_wav.sh && curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_ocv_vv/dvswitch_bot.py | sudo tee /opt/dvswitch_bot/bin/dvswitch_bot.py >/dev/null && curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/app.py | sudo tee /opt/dvswitch_bot/web/app.py >/dev/null && sudo systemctl restart dvswitch-bot dvswitch-web && grep -m1 SCRIPT_VERSION= /opt/dvswitch_bot/bin/create_wav.sh && grep -m1 '^__version__' /opt/dvswitch_bot/bin/dvswitch_bot.py && grep -m1 '^__version__' /opt/dvswitch_bot/web/app.py
```

> **注意事項**
>
> - **404 時は書き込み前に停止:** `curl -f` を付けているため、パスの打ち間違いなどで HTTP 404 が返った場合はエラー終了し、`tee` による上書きは行われません（既存ファイルは保護されます）。
> - **push 直後は CDN キャッシュに注意:** GitHub へ push した直後は raw の CDN キャッシュにより旧内容が返ることがあります。末尾の版確認（`SCRIPT_VERSION=` / `__version__`）の出力が古い場合は、1〜2分ほど待ってから再実行してください。
> - **VV版は bot 再起動を含む:** VV版の `dvswitch_bot.py` 差し替えは動的合成時の話者にも影響するため、`dvswitch-bot` の再起動を含めています（JT版の固定WAV運用と異なり、無反映を防ぐため必須）。

---

## 2. 3ファイル一括デプロイ（コピペ用）

以下をそのまま貼り付けて実行します。`#` の行はコメントなので一緒に貼って問題ありません。

各ステップは `&&` で連結しており、途中で失敗すると止まります。壊れたファイルのままサービスが再起動されることはありません。

```bash
# ============================================================
# OpenCCVoice 一括デプロイ: bot / bot_setup / app
# ============================================================

# --- 1) バックアップ（既存ファイルを退避。タイムスタンプ付き）---
TS=$(date +%y%m%d%H%M%S); \
sudo cp /opt/dvswitch_bot/bin/dvswitch_bot.py /opt/dvswitch_bot/bin/dvswitch_bot.py.$TS.bak 2>/dev/null; \
sudo cp /opt/dvswitch_bot/bin/bot_setup.py    /opt/dvswitch_bot/bin/bot_setup.py.$TS.bak    2>/dev/null; \
sudo cp /opt/dvswitch_bot/web/app.py          /opt/dvswitch_bot/web/app.py.$TS.bak          2>/dev/null; \
echo "backup done ($TS)"

# --- 2) 取得（GitHub raw → sudo tee で上書き）---
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_ocv_JT/dvswitch_bot.py  | sudo tee /opt/dvswitch_bot/bin/dvswitch_bot.py >/dev/null && echo "bot       fetched" && \
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dvs_ocv_JT/bot_setup.py     | sudo tee /opt/dvswitch_bot/bin/bot_setup.py    >/dev/null && echo "bot_setup fetched" && \
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/app.py | sudo tee /opt/dvswitch_bot/web/app.py          >/dev/null && echo "app       fetched"

# --- 3) 構文チェック（__pycache__ を書かない ast.parse 方式）---
python3 -c "import ast; ast.parse(open('/opt/dvswitch_bot/bin/dvswitch_bot.py',encoding='utf-8').read()); print('bot       syntax OK')" && \
python3 -c "import ast; ast.parse(open('/opt/dvswitch_bot/bin/bot_setup.py',encoding='utf-8').read()); print('bot_setup syntax OK')" && \
python3 -c "import ast; ast.parse(open('/opt/dvswitch_bot/web/app.py',encoding='utf-8').read()); print('app       syntax OK')"

# --- 4) 版表記の確認 ---
echo "bot: $(grep -m1 '^__version__' /opt/dvswitch_bot/bin/dvswitch_bot.py)"; \
echo "app: $(grep -m1 'app.py  V2' /opt/dvswitch_bot/web/app.py)"

# --- 5) サービス再起動（bot と dashboard）---
sudo systemctl restart dvswitch-bot && \
sudo systemctl restart dvswitch-web && \
sleep 2 && \
systemctl is-active dvswitch-bot dvswitch-web
```

### 成功の見え方

順に次が出れば成功です。

```
backup done (260624XXXXXX)
bot       fetched
bot_setup fetched
app       fetched
bot       syntax OK
bot_setup syntax OK
app       syntax OK
bot: __version__ = "V1.xx"
app:  app.py  V2.xx
active
active
```

最後に `active` が2つ出れば、bot とダッシュボードが新版で起動しています。

---

## 3. 個別に1ファイルだけ更新したい場合

3つ全部ではなく、1ファイルだけ直したいときの最小手順です。app.py を例にします。

```bash
# バックアップ → 取得 → 構文チェック → 再起動
sudo cp /opt/dvswitch_bot/web/app.py /opt/dvswitch_bot/web/app.py.$(date +%y%m%d%H%M%S).bak 2>/dev/null; \
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/app.py | sudo tee /opt/dvswitch_bot/web/app.py >/dev/null && \
python3 -c "import ast; ast.parse(open('/opt/dvswitch_bot/web/app.py',encoding='utf-8').read()); print('app syntax OK')" && \
sudo systemctl restart dvswitch-web && \
sleep 2 && systemctl is-active dvswitch-web
```

ファイルごとの「GitHub URL」「配置先」「再起動するサービス」の対応:

| ファイル | GitHub URL（raw, main） | 配置先 | 再起動 |
|---|---|---|---|
| bot 本体 | `.../main/dvswitch_bot.py` | `/opt/dvswitch_bot/bin/dvswitch_bot.py` | `dvswitch-bot` |
| 設定ツール | `.../main/bot_setup.py` | `/opt/dvswitch_bot/bin/bot_setup.py` | （再起動不要※） |
| ダッシュボード | `.../main/dashboard/app.py` | `/opt/dvswitch_bot/web/app.py` | `dvswitch-web` |
| WAV作成ツール | `.../main/create_wav.sh` | `/opt/dvswitch_bot/bin/create_wav.sh` | （再起動不要※） |

URL の先頭は共通で `https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch`

※ bot_setup.py と create_wav.sh は実行ツールなので、置き換えてもサービス再起動は不要です。create_wav.sh は取得後に実行権限が必要です:

```bash
sudo chmod +x /opt/dvswitch_bot/bin/create_wav.sh
```

---

## 4. 構文チェックについて（なぜ ast.parse か）

取得したファイルが壊れていないか、再起動の前に確認しています。

`python3 -m py_compile` でも構文チェックできますが、これはコンパイル結果を `__pycache__/` に書き込もうとします。書き込み権限が無いディレクトリ（例: `/opt/dvswitch_bot/web/`）だと `Permission denied` エラーになります。

そこで、ファイルに何も書き込まずに構文だけ検査する `ast.parse` 方式を使っています。

```bash
python3 -c "import ast; ast.parse(open('対象ファイル',encoding='utf-8').read()); print('syntax OK')"
```

`syntax OK` が出れば文法的に問題なし。エラー（`SyntaxError`）が出たら、そのファイルは壊れているので**再起動せず**、バックアップから戻してください（次項）。

---

## 5. 失敗したとき: バックアップから戻す

デプロイで問題が起きたら、手順1で取ったバックアップに戻せます。

最近のバックアップを確認:

```bash
ls -t /opt/dvswitch_bot/web/app.py.*.bak | head -5
```

戻す（app.py の例。タイムスタンプは上の一覧から選ぶ）:

```bash
sudo cp /opt/dvswitch_bot/web/app.py.<タイムスタンプ>.bak /opt/dvswitch_bot/web/app.py
sudo systemctl restart dvswitch-web
systemctl is-active dvswitch-web
```

bot を戻す場合は `bin/dvswitch_bot.py` と `dvswitch-bot` に読み替えてください。

---

## 6. 状態の確認コマンド

デプロイ後やトラブル時に使う確認コマンドです。

サービスが動いているか:

```bash
systemctl is-active dvswitch-bot dvswitch-web
```

サービスのログ（エラーが出ていないか）:

```bash
journalctl -u dvswitch-bot -n 30 --no-pager
journalctl -u dvswitch-web -n 30 --no-pager
```

現在のバージョン:

```bash
grep -m1 '^__version__' /opt/dvswitch_bot/bin/dvswitch_bot.py
grep -m1 'app.py  V2'   /opt/dvswitch_bot/web/app.py
```

ダッシュボードが応答するか（マシン自身から）:

```bash
curl -I http://localhost:8081/
```

`HTTP/1.1 200 OK` が返ればダッシュボードは正常稼働。

---

## 7. トラブルシューティング

### ダッシュボードがブラウザで開けない

まず原因を切り分けます。マシン自身から応答があるか確認:

```bash
curl -I http://localhost:8081/
```

- **200 OK が返る** → サーバーは正常。原因はネットワーク（ファイアウォール or 端末側）。下記へ。
- **Connection refused 等** → サービスが落ちている。`systemctl is-active dvswitch-web` と `journalctl` で確認。

### ポート 8081 が外部（他端末）から開けない（Pi-Star 環境）

Pi-Star はファイアウォール（iptables）が標準で厳しく、許可されたポート（22/80/443 等）以外は弾きます。8081 は標準では開いていません。

確認:

```bash
sudo iptables -L -n | grep 8081
```

何も出なければ 8081 は許可されていません。一時的に開ける（再起動で消えます）:

```bash
sudo iptables -I INPUT -p tcp --dport 8081 -j ACCEPT
```

これで他端末のブラウザから `http://<マシンのIP>:8081/` が開けるか確認します。

> 注意（セキュリティ）: 8081 を開けると、同じ LAN 上の誰でも認証なしでダッシュボード（サービス操作を含む）にアクセスできるようになります。常時開放する前に、本当に必要か検討してください。一時確認だけなら、確認後に次で閉じられます:
> ```bash
> sudo iptables -D INPUT -p tcp --dport 8081 -j ACCEPT
> ```

### URL の打ち間違いに注意

ダッシュボードは **http**（https ではない）、ポート **8081** 込みです。

```
正: http://192.168.x.x:8081/
誤: https://...  /  ポート番号なし
```

---

## 8. 最短まとめ

1. SSH でマシンにログイン
2. 「§1 の一括デプロイ」をコピペ実行
3. `active` が2つ出れば完了
4. ブラウザで `http://<マシンのIP>:8081/` を開いて確認
   （Pi-Star で開けないときは §6 のファイアウォール）

以上です。
