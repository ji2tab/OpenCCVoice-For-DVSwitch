# ocv_dvs_vv — VOICEVOX 版（VV版）

DVSwitch 自動音声応答システムの VOICEVOX 版スクリプト群です（x86_64 Linux 用。ベアメタル / VM / コンテナのいずれでも動作します。Incus コンテナで環境を用意する場合は『Incus コンテナ/incus構築マニュアル.md』を先に実施してください）。

構築手順は『[OpenCCVoice for DVSwitch VV版（VOICEVOX）構築手順書.md](./OpenCCVoice%20for%20DVSwitch%20VV%E7%89%88%EF%BC%88VOICEVOX%EF%BC%89%E6%A7%8B%E7%AF%89%E6%89%8B%E9%A0%86%E6%9B%B8.md)』を参照してください。

## ダッシュボードについて

このディレクトリには専用のダッシュボード（旧 app.py）は含まれません。
**Web ダッシュボードは JT版・VV版で共用です。リポジトリ直下の `dashboard/app.py` を使用してください。**

以前このディレクトリにあった `app.py`（V2.85）は、V3.0 で共用ダッシュボード（`dashboard/app.py`）へ統合される前の旧版です。VV ノード実機も共用の `dashboard/app.py`（V3.11 以降）で稼働しているため削除しました。

## 主なファイル

- `create_wav.sh` — VV版 WAV 生成スクリプト
- `dvswitch_bot.py` — VV版 常駐 bot（デーモン）
- `vv_say.py` — VOICEVOX 音声合成
- `bot_setup.py` / `dvs_config.sh` / `test_send.py` — JT版（`ocv_dvs_jt/`）と共通（同一内容）
- `bot_config.json` / `wav_source.json` — 設定・音声ソース定義
