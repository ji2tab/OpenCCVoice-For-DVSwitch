
---

### MMDVM_Bridge の役割

* **受信（外部 → 内部）:** Pi-Starやネットワークから届いたDMRのデジタル音声データを受け取り、Analog_Bridge へパスします。
* **送信（内部 → 外部）:** 自動応答スクリプトやスマートフォンから Analog_Bridge 経由で作られた音声を、ネットワーク（Pi-Star側）へ送り出します。

### 設定ファイルの場所

設定ファイルは以下の場所にあります。

```bash
sudo nano /opt/MMDVM_Bridge/MMDVM_Bridge.ini

```

### 重要な設定セクション

自動音声応答システム（Pythonスクリプト）と正しく連携するために、以下のセクションを確認してください。

#### 1. [Analog_Bridge] セクション（Analog_Bridgeとの通信）

このセクションは、内部の相棒である Analog_Bridge との通信ポートを定義します。

```ini
[Analog_Bridge]
Address=127.0.0.1
# Analog_Bridge.iniの [AMBE_AUDIO] rxPort に合わせる（通常不要）
# ただし、音声データ（PCM/USRP）のやり取りはここではなく
# Analog_Bridge が直接行っているため、この設定はDVSwitchの
# 内部ルーティング用（制御コマンド等）としてデフォルトのままでOKです。

```

※自動応答システムの音声は `Analog_Bridge`（51000番ポート）へ直接投げるため、ここのポート番号は変更しなくても大丈夫です。

#### 2. [DMR Network] セクション（Pi-Star/ネットワークとの通信）

このセクションが最も重要です。MMDVM_Bridgeがどこに接続するか（Pi-Starなのか、直接サーバーなのか）を定義します。

**Pi-Star (MMDVMHost) と接続する場合:**

```ini
[DMR Network]
Enable=1
Address=127.0.0.1      # Pi-Starと同じラズパイ上で動いている場合
Port=62031             # MMDVMHostの待ち受けポート（デフォルトは62031）
Jitter=300
Password=PASSWORD      # Pi-StarのDMR Configurationで設定したパスワード
Slot1=1
Slot2=1
Debug=0

```

* **注意:** Pi-Star側（MMDVMHost）でも、`MMDVMHost.ini` の `[DMR Network]` セクションでこの `Port` と `Password` が一致している必要があります。

### 設定の反映（再起動）

設定ファイルを変更した後は、必ずサービスを再起動してください。

```bash
sudo systemctl restart MMDVM_Bridge

```

また、状態を確認するには以下のコマンドを使用します。

```bash
sudo systemctl status MMDVM_Bridge

```

---

### 💡 トラブルシューティング（MMDVM_Bridge編）

* **Pi-Starのダッシュボードに何も表示されない場合:**
`MMDVM_Bridge` と Pi-Star (`MMDVMHost`) 間の接続（PortまたはPassword）が間違っている可能性が高いです。
* **Pythonスクリプトからの送信時のみダッシュボードが反応しない場合:**
この場合は `MMDVM_Bridge` の問題ではなく、手前の `Analog_Bridge` (Port 51000) または `md380-emu` (Port 2470) の問題です。

MMDVM_Bridgeの設定は、一度Pi-Starと繋がってしまえば、自動応答システムの構築過程で頻繁に変更する必要はありません。
