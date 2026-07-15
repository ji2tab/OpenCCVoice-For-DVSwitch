# dvs_ocv_JT — Open JTalk 版（JT版）

DVSwitch 自動音声応答システムの Open JTalk 版スクリプト群です（Raspberry Pi ノード用。Raspberry Pi OS Bookworm 上で MMDVM_Bridge / Analog_Bridge と同居して動作します。音声合成は Open JTalk + SoX を使用します）。

構築手順は『[OpenCCVoice_構築導入設定_完全マニュアル.md](./OpenCCVoice_%E6%A7%8B%E7%AF%89%E5%B0%8E%E5%85%A5%E8%A8%AD%E5%AE%9A_%E5%AE%8C%E5%85%A8%E3%83%9E%E3%83%8B%E3%83%A5%E3%82%A2%E3%83%AB.md)』を参照してください。

## ダッシュボードについて

このディレクトリには専用のダッシュボードは含まれません。
**Web ダッシュボードは JT版・VV版で共用です。リポジトリ直下の [`dashboard/app.py`](../dashboard/app.py)（V3.11 以降）を使用してください。**

## 主なファイル

- `dvswitch_bot.py` — JT版 常駐 bot（デーモン。カーチャンク検出→応答合成→USRP送出）
- `create_wav.sh` — JT版 固定WAV生成スクリプト（Open JTalk + SoX）
- `bot_setup.py` / `dvs_config.sh` / `test_send.py` — VV版（`../dvs_ocv_vv/`）と共通（同一内容）

## 関連ドキュメント

- [OpenCCVoice_操作マニュアル.md](./OpenCCVoice_%E6%93%8D%E4%BD%9C%E3%83%9E%E3%83%8B%E3%83%A5%E3%82%A2%E3%83%AB.md) — 運用者向け逆引き操作集
- [カスタム音声.md](./%E3%82%AB%E3%82%B9%E3%82%BF%E3%83%A0%E9%9F%B3%E5%A3%B0.md) — 標準音声を自前の音声に差し替える手順
- [JT版一括アップデートマニュアル.md](./JT%E7%89%88%E4%B8%80%E6%8B%AC%E3%82%A2%E3%83%83%E3%83%97%E3%83%87%E3%83%BC%E3%83%88%E3%83%9E%E3%83%8B%E3%83%A5%E3%82%A2%E3%83%AB.md) — 稼働ノードへ最新版を一括反映する手順
- [OpenCCVoice for DVSwitch — Pi-Star 同居構築手順書.md](./OpenCCVoice%20for%20DVSwitch%20%E2%80%94%20Pi-Star%20%E5%90%8C%E5%B1%85%E6%A7%8B%E7%AF%89%E6%89%8B%E9%A0%86%E6%9B%B8.md) — Pi-Star 同居構成の構築手順
- ソフトウェア仕様書は [`../specification/`](../specification/) を参照してください。
