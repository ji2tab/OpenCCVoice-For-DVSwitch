# ocv-voicevox コンテナ 構成バックアップ

> **このリポジトリでの配置について**: このディレクトリ（`Incus コンテナ/`）には、下記「構成」に記載の各ファイルをフラットに配置しています（`bin/`・`voicevox/`・`web/`・`config/` のようなサブフォルダは作成していません）。各ファイルの実機での配置パスは「構成」セクションの矢印（→）の通りです。
>
> **秘匿情報について**: `MMDVM_Bridge.ini` の `[DMR Network] Password` は公開リポジトリのため `********MASKED********` に置き換えています。実際に使用する際は各自のTGIFパスワードを設定してください。

作成日: 2026-07-08
対象: Incus コンテナ `ocv-voicevox`（192.168.1.170 / macvlan on enp2s0）
ホスト: ocv-pc（Intel Core i5-7200U, x86_64, 192.168.1.67）
用途: OpenCCVoice for DVSwitch の VOICEVOX 統合版（新規独立局、TGIF 直結）

このバックアップは、Open JTalk から VOICEVOX CORE へ音声合成を全面移行した
作業（2026-07-07〜08）の成果一式を記録したもの。すべてコンテナ実機からの
実ファイル（vv_say.py 含む）を正本としている。

--------------------------------------------------------------------------------
## 構成

```
ocv-voicevox-backup/
├── bin/                         → /opt/dvswitch_bot/bin/ に対応
│   ├── dvswitch_bot.py          bot 本体（V1.95a + 頭無音0.0調整済み）
│   ├── create_wav.sh            固定WAV生成（6箇所を VOICEVOX 呼び出しに改変済み）
│   ├── bot_setup.py             bot_config.json 対話生成ツール（VOICEVOX未対応=今後の課題）
│   ├── dvs_config.sh            DVSwitch ini 対話編集ツール（TGIF前提）
│   └── test_send.py             送信テストユーティリティ
├── voicevox/                    → /opt/voicevox/ に対応
│   └── vv_say.py                固定フレーズ合成ヘルパー（create_wav.sh が呼ぶ）
├── web/                         → /opt/dvswitch_bot/web/ に対応
│   └── app.py                   Flask ダッシュボード（VOICEVOX未対応=今後の課題）
└── config/                      各所の設定ファイル
    ├── bot_config.json          → /opt/dvswitch_bot/bot_config.json
    ├── wav_source.json          → /opt/dvswitch_bot/wav_source.json（create_wav.sh 入力記録）
    ├── Analog_Bridge.ini        → /opt/Analog_Bridge/Analog_Bridge.ini（txTg=44833）
    └── MMDVM_Bridge.ini         → /opt/MMDVM_Bridge/MMDVM_Bridge.ini
```

注: VOICEVOX CORE 本体（/opt/voicevox/dist/ 配下の onnxruntime・models/vvms/*.vvm・
open_jtalk 辞書）と Python venv（/opt/dvswitch_bot/venv/）は容量が大きいため本
バックアップに含めていない。復元時は download ツールで再取得・venv 再構築する
（下記「復元手順」参照）。固定WAV（fixed_intro.wav 等）も create_wav.sh で再生成
できるため含めていない。

--------------------------------------------------------------------------------
## V1.95a の主な変更点（V1.92 から）

1. 音声合成を Open JTalk → VOICEVOX CORE（Python バインディング）へ全面移行。
   話者は dvswitch_bot.py 冒頭の VOICEVOX_STYLE_ID / VOICEVOX_VVM_PATH で変更。
   固定フレーズ側は vv_say.py の DEFAULT_STYLE_ID / VVM_PATH。両者を必ず揃える。
   現在の話者: No.7（アナウンス）= style_id 30 / 6.vvm。
2. キャッシュ命中時の送出リード REPLY_TX_LEAD_DELAY_SEC を 1.0 → 2.5 に変更。
   直TGIF接続環境で 1.0s だと受信ストリーム残処理と TX が重なり音声が崩れる
   （もごもご/同期ずれ）症状を解消。
3. キャッシュ一時ファイル（.building）に PID+スレッドID を付与しユニーク化（保険）。
4. キャッシュ署名 _reply_signature() に VOICEVOX 話者ID・モデルを追加。
   話者変更でキャッシュ自動再生成。CACHE_SCHEMA を v1→v2。
5. 第30条セッション判定のギャップ計算を修正（tx_start = now - dur）。
   従来は「前回終了→今回終了」で判定し、無音が短くても通話が長いとセッションが
   誤リセットされた。「前回終了→今回開始」の純粋な無通信時間で判定するよう修正。
6. QSO_SESSION_GAP_SEC を SUPPRESS_DURATION_SEC のエイリアスから独立させ 60 秒に
   （TGIFChanger の自TG復帰判定と運用基準を統一）。

### 実機で追加調整済みの値（V1.95a 出荷後）
- PRE_AUDIO_SILENCE_SEC = 0.0（頭無音削減。直TGIF環境では SFR 折り返し対策の
  焼き込み無音が不要と判断）

--------------------------------------------------------------------------------
## 既知の残課題（今後）

- bot_setup.py / app.py の VOICEVOX 話者選択対応（三位一体対応）。現状は
  dvswitch_bot.py と vv_say.py の 2 ファイルを手修正して話者を変える。
- systemd サービス化（dvswitch-bot.service）が未実施。手動起動のみ。
  サービス化時は ExecStart を venv の python3
  (/opt/dvswitch_bot/venv/bin/python3) にすること（voicevox_core が venv 内のため）。
- REPLY_TX_LEAD_DELAY_SEC(2.5s) の最小化（頭のタイムラグ短縮）は途中。
- キャッシュ race condition の真因（.building 競合説）は保険対応のみ。
  REPLY_TX_LEAD_DELAY_SEC 拡大で症状は解消済みだが根治ではない。

--------------------------------------------------------------------------------
## 復元手順（新しいコンテナに展開する場合の概略）

1. Debian 12 コンテナ作成・macvlan・固定IP・SSH・タイムゾーン/ロケール設定
2. DVSwitch-Server 導入（dvswitch.org/bookworm → apt install dvswitch-server）
   → dvs で初期設定 → TGIF 切替
3. md380-emu: 同梱 qemu-arm-static 5.2 系で動作（システム全体のダウングレード不要）。
   実行権限付与（chmod +x /opt/md380-emu/md380-emu）
4. VOICEVOX CORE 導入:
   mkdir -p /opt/voicevox && cd /opt/voicevox
   curl -sSfL <download-linux-x64 の最新URL> -o download && chmod +x download
   ./download -o /opt/voicevox/dist --exclude c-api --models-pattern '[0-9]*.vvm'
5. venv 構築:
   cd /opt/dvswitch_bot
   python3 -m venv venv --system-site-packages
   source venv/bin/activate
   pip install <voicevox_core-*-manylinux_2_34_x86_64.whl の最新URL>
6. 本バックアップの bin/・voicevox/・web/・config/ を各対応パスへ配置
7. create_wav.sh で固定WAV生成（sudo ./create_wav.sh）
8. sudo ./dvs_config.sh で自局情報を反映（Callsign/DMR ID/ESSID/Password/txTg）
9. venv の python3 で bot 起動して動作確認

--------------------------------------------------------------------------------
## 重要な設定値（この構成時点）

- 自局: JJ2YYK / DMR ID 4402396 / ESSID 88
- 送信 TG: 44833（TGIF）
- VOICEVOX 話者: No.7（アナウンス）style_id=30 / 6.vvm
- キャッシュ: ON / hit lead=2.5s / schema=v2
- 第30条: interval=10min / session gap=60s
- 頭無音: PRE_AUDIO_SILENCE_SEC=0.0

※ MMDVM_Bridge.ini / Analog_Bridge.ini には TGIF パスワード等の秘匿情報を
  含む。取り扱いに注意すること。
