# ocv_dvs_vvw — VOICEVOX + 天気読み上げ版（VVW版）

DVSwitch 自動音声応答システムの **VVW版**（VOICEVOX + Weather）です。VV版（`ocv_dvs_vv/`）に「時報に続く当地の天気読み上げ（Open-Meteo）」を搭載した系譜で、x86_64 Linux 用です。

## VV版との関係

- **VV版（`ocv_dvs_vv/`）**: 天気なしの安定版（bot V1.99vv で凍結）。
- **VVW版（本ディレクトリ）**: 天気搭載の発展版。bot は V1.99vv から分岐し V2.02vvw〜。天気系の改修は本系譜で行います。
- 版サフィックス `vvw` = VOICEVOX + Weather 搭載を示します。

## 天気読み上げ機能（概要）

- `WEATHER_HOURS` に指定した毎正時の時報に続けて「続いて当地の天気は、晴れ、気温は25度です」を読み上げ（Open-Meteo API・キー不要・追加依存なし）。
- 対象正時の約2分前に取得し、イントロ＋時報＋天気の完成WAVを**事前生成**（正時は再生のみ＝遅延ゼロ）。取得失敗時は天気を省略して時報は定刻どおり。
- 設定は `bot_config.json` の任意キー: `WEATHER_ENABLED` / `WEATHER_LATITUDE` / `WEATHER_LONGITUDE` / `WEATHER_HOURS`（未設定なら従来動作）。

## 主なファイル

- `dvswitch_bot.py` — VVW版 常駐 bot（V2.02vvw〜）
- `vv_say.py` / `create_wav.sh` / `bot_setup.py` / `dvs_config.sh` / `test_send.py` / `wav_source.json` — **VV版（`ocv_dvs_vv/`）と共通（同一内容）**
- Web ダッシュボードは JT/VV/VVW 共用: リポジトリ直下の `dashboard/app.py`

## 構築・導入

VV版の構築手順書『ocv_dvs_vv/OpenCCVoice for DVSwitch VV版（VOICEVOX）構築手順書.md』に従って構築し、bot のみ本ディレクトリの `dvswitch_bot.py` を使用してください。天気の設定キーは `bot_config.json` へ追記します（三位一体 UI 対応までは手書き）。

> ⚠️ 現時点で bot_setup.py / ダッシュボードは WEATHER キー未対応です。これらで設定を保存すると WEATHER キーが消えます（bot は機能OFFとして安全に動作継続）。UI 対応版が出るまで、天気設定の変更は JSON 直接編集で行ってください。
