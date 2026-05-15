

---

# DVSwitch 拡張マニュアル：Analog_Bridge & md380-emu 完全ガイド

## 1. 全体像（システムはどのようにつながっているか？）

音声をDMRネットワークに流す場合、データは以下の順序でバケツリレーされます。

1. **Pythonスクリプト等:** 音声（WAV/PCM）を生成し、**USRPプロトコル**で `Analog_Bridge` に投げる。
2. **Analog_Bridge:** 受け取った音声を `md380-emu` に渡し、「DMR用の圧縮形式（AMBE）にして！」と依頼する。
3. **md380-emu:** 必死に計算して音声を圧縮し、`Analog_Bridge` に返す。
4. **Analog_Bridge:** 圧縮された音声を `MMDVM_Bridge` (Pi-Star側) へ引き渡す。

---

## 2. md380-emu (AMBEソフトウェア・トランスコーダー)

本来、DVMEGA等の基板に乗っている「ハードウェアAMBEチップ」が行う音声圧縮・解凍処理を、Raspberry PiのCPUを使って**ソフトウェアで強引に行う**エミュレーターです。

### 役割と特徴

* **役割:** 生の音声（PCM）とデジタル圧縮音声（AMBE）の相互変換。
* **通信ポート:** 内部で **UDP 2470番** を使用して Analog_Bridge とだけ会話します。
* **特徴:** 変換中は非常にCPUパワーを使います。これが停止していると、「送信状態にはなる（ダッシュボードは光る）が、無音になる」という現象が起きます。

### 基本操作（サービス管理コマンド）

Raspberry Piのコンソール（SSH）から実行します。

* **状態の確認 (Status):**
```bash
sudo systemctl status md380-emu

```


※ `Active: active (running)` と緑色で表示されていれば正常です。
* **再起動 (Restart) - 音が出ない時の特効薬:**
```bash
sudo systemctl restart md380-emu

```


* **停止 / 起動 (Stop / Start):**
```bash
sudo systemctl stop md380-emu
sudo systemctl start md380-emu

```



---

## 3. Analog_Bridge (音声プロトコル変換ゲートウェイ)

様々な音声プロトコル（USRP、AMBE、DMR、YSF等）を交通整理するルーターです。外部（Pythonスクリプト）からの入力を受け付ける「耳」の設定を行います。

### 設定ファイルパス

```bash
sudo nano /opt/Analog_Bridge/Analog_Bridge.ini

```

### 必須設定項目（[USRP] および [AMBE_AUDIO] セクション）

自動応答システムや外部アプリから音声を流し込むための設定です。

#### ① [USRP] セクション（Pythonスクリプトとの接続口）

```ini
[USRP]
rxPort = 51000
txPort = 51001
address = 127.0.0.1

```

* **`rxPort`:** Analog_Bridgeが「待ち受ける」ポート。Pythonの `UDP_PORT = 51000` と必ず一致させます。
* **`txPort`:** Analog_Bridgeが「出力する」ポート。`rxPort`とは違う番号（51001など）にします。
* **`address`:** `127.0.0.1` にすることで、外部からの不正アクセスを防ぎ、同じラズパイ内のスクリプトからのみ受け付けます。

#### ② [AMBE_AUDIO] セクション（md380-emuとの接続口）

```ini
[AMBE_AUDIO]
address = 127.0.0.1
rxPort = 2470
txPort = 2470

```

* `md380-emu` はデフォルトで 2470番 ポートを使用するため、必ずこの値にします。

### ⚠️ DVSwitch v1.6.4 系における致命的なバグの回避

特定バージョンの Analog_Bridge では、設定ファイルに特定のパラメータが残っていると起動時にクラッシュ（Fatal Parse Error）します。
設定ファイル内の以下の2行を探し、行頭に `;` を付けて必ずコメントアウト（無効化）してください。

```ini
; pcmBufferMS = 200
; jitterQueueSize = 30

```

### 基本操作（サービス管理コマンド）

設定ファイル（Analog_Bridge.ini）を書き換えた後は、**必ず再起動して設定を読み込ませる**必要があります。

* **再起動 (Restart):**
```bash
sudo systemctl restart Analog_Bridge

```


* **状態の確認 (Status) - エラーがないか確認:**
```bash
sudo systemctl status Analog_Bridge

```



---

## 4. トラブルシューティング（症状別フローチャート）

自動応答がうまくいかなくなった際は、以下の切り分けで原因を特定します。

### 症状A：Pythonスクリプトを実行しても、Pi-Starのダッシュボードが一切反応しない

* **原因:** Pythonから Analog_Bridge にデータが届いていません。
* **対策:**
1. Python内の `UDP_PORT` と Analog_Bridge.ini の `[USRP] rxPort` が `51000` で一致しているか確認。
2. Analog_Bridge自体がエラーで落ちていないか `sudo systemctl status Analog_Bridge` で確認。



### 症状B：Pi-Starのダッシュボードは「TX」と光るが、無線機からは音が出ない（無音）

* **原因:** データは届いているが、AMBE（デジタル音声）への圧縮・変換ができていません。
* **対策:**
1. `md380-emu` が停止している可能性が高いです。`sudo systemctl restart md380-emu` を実行します。
2. Analog_Bridge.ini の `[AMBE_AUDIO]` セクションのポートが `2470` になっているか確認します。



### 症状C：音声は出るが、ケロケロしたりブツ切れになる

* **原因:** Raspberry PiのCPUリソース不足、またはSoXの変換エラーです。
* **対策:**
1. `top` や `htop` コマンドでCPU使用率を確認します。重いプロセスがあれば停止します。
2. Pythonスクリプト側の `time.sleep(0.02)` （20msのウェイト）が正しく機能しているか確認します（一気にデータを流し込むとAnalog_Bridgeがパンクします）。
