# OpenCCVoice for DVSwitch — 作業ルール

DVSwitch / DMR 環境向けの自動音声応答（デジピーター）システム。
Raspberry Pi / x86_64 Linux 上で 24 時間無人動作する Python 3 デーモンとシェルスクリプト、
および日本語の運用マニュアル・仕様書で構成される。

## 言語

- Issue / PR / コミットメッセージ / ドキュメントは**すべて日本語**で書く。
- README の英語セクション（English）は日本語セクションの要約。日本語側を変更したら
  英語側も内容が矛盾しないよう確認する。

## リポジトリ構成

| ディレクトリ | エディション | 音声合成 | 天気 |
|---|---|---|---|
| `ocv_dvs_jt/` | JT版（安定） | Open JTalk + SoX | — |
| `ocv_dvs_jtw/` | JTW版（JT版＋天気） | Open JTalk + SoX | Open-Meteo |
| `ocv_dvs_vv/` | VV版（安定） | VOICEVOX | — |
| `ocv_dvs_vvw/` | VVW版（VV版＋天気） | VOICEVOX | Open-Meteo |
| `dashboard/` | 共用 Web ダッシュボード（`app.py`） | — | — |
| `specification/` | ソフトウェア仕様書 | — | — |
| `Incus コンテナ/` | Incus 構築リソース（ini サンプル・マニュアル） | — | — |

## エディション間の同期ルール（重要）

- `create_wav.sh` / `dvs_config.sh` / `test_send.py` は
  **JT版とJTW版で同一内容**、**VV版とVVW版で同一内容**。
  片方だけ直してはいけない。必ず対になる側も同じ変更を入れる。
- `bot_setup.py` は JT版・VV版・VVW版が共通、JTW版のみ天気対応で別系統。
- **天気関連の改修は w 付きの系譜（jtw / vvw）だけで行う。**
  安定版（jt / vv）はそのまま維持する。
- VVW版 `dvswitch_bot.py` は JTW版を土台に音声エンジンのみ VOICEVOX へ換装した版。
  換装点は 定数ブロック / `_generate_hybrid()` / `_reply_signature()` の3箇所のみ。
  JTW版に機能追加したら、この3箇所を避けて VVW版へ移植できるか確認する。

## コード規約

- **JT版・JTW版の Python は標準ライブラリのみ。サードパーティ依存を追加しない。**
  （VV版・VVW版は `venv/` 内の `voicevox_core` を使う）
- 実行環境は Python 3（Raspberry Pi OS Bookworm 32-bit）。新しい構文機能に依存しない。
- シェルスクリプトは bash。ini や WAV を書き換えるものは
  既存の自動バックアップ（`bak/ini/`, `bak/wav/`）の仕組みを壊さない。
- 実機の配置先は `/opt/dvswitch_bot/`（`bin/`, `web/`, `venv/`, `*.wav`,
  `bot_config.json`, `wav_source.json`, `bak/`）。パスを変えるときは
  マニュアルと仕様書の記述もすべて合わせる。

## 版数管理

- スクリプトを変更したら、ファイル冒頭のバージョン表記と
  **README の「版数」テーブルの両方**を更新する。
- バージョン表記の形式は系譜ごとに固定：
  JT版は `V1.95`、JTW版は `V2.07jtw`、VV版は `V1.99vv`、VVW版は `V2.07vvw` のように
  サフィックスを付ける。既存の採番規則から外れない。

## raw URL パス

README のクイックスタートは `raw.githubusercontent.com/.../main/ocv_dvs_jt/...` を参照している。
ディレクトリ名を変えると既存ユーザーの取得スクリプトが 404 になるため、
**ディレクトリのリネームや移動は提案のみ**とし、勝手に実行しない。

## ドキュメント

- 変更がユーザーの操作手順に影響する場合は、該当するドキュメントも同じ PR で更新する。
  - 構築導入設定 完全マニュアル — 新規構築の通し手順
  - 操作マニュアル — 日常運用の逆引き
  - カスタム音声マニュアル — 音声差し替え（cstm 機能）
  - VV版構築手順書 — VOICEVOX 版の構築
  - README_PROJECT — 理念・背景
- スクリプトの内部仕様（定数・関数・処理フロー・パケット構造）を変えたら
  `specification/` の該当仕様書も更新する。

## やってはいけないこと

- 動作確認なしに `dvswitch_bot.py` の送信系（USRP/UDP 51000 への WAV 送出）を書き換える。
  実機でしか検証できないため、変更は小さく分け、影響範囲を PR 本文に明記する。
- 安定版（JT版・VV版）に新機能を入れる。まず w 系譜で実績を作る。
- `.github/workflows/` を無断で変更する。
- ライセンス・クレジット（JA2CCV 局の設計考案が基礎、JI2TAB / JJ2YYK ほか協力）の記述を削る。
