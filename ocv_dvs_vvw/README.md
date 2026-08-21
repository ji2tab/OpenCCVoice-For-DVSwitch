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

## 送出タイミング（V2.08vvw）— 頭欠け・切れ際の対策（JTW V2.10jtw 同等）

カーチャンク応答・時報・定時メッセージの「語頭が欠ける／切れ際が乱れる」対策を、JTW（ocv-uhf）で
実機（RF 受信・DroidStar ログ・45日1390サンプル統計）まで追い込んで確定した内容を VVW へ移植した版です。
頭欠けの原因は3つ（いずれも解消）:

1. **素材WAVに語頭前の助走が無かった** … `create_wav.sh` V1.4vv が助走を焼き込む
   （fixed_intro ≈2.0s / time_intro・001・002 ≈0.5s）。**素材を作り直すときは V1.4vv 以降を使うこと。**
2. **録音WAVのノイズフロア段差** … 20ms のフェードインで平滑化。
3. **音声ストリーム先頭の SET_INFO（keyup=0）が語頭を巻き込む** … 送出直前の別経路に一本化。

禁止事項: **前パディングを 0 にしない**（ヘッダ喪失で幽霊ストリーム化）／**EOT を 0 にしない**（ストリーム未クローズ）。

> ⚠️ **VVW（ocv-voicevox / VOICEVOX / 直 TGIF）は JTW と経路が異なります。** 上記の実測値は JTW で確定した
> ものです。配置後に ocv-voicevox 実機で「頭欠け・切れ際・幽霊ストリーム（DroidStar ログ）」を必ず確認して
> ください。`STARTUP_PRE_PADDING_PACKETS=150`（起動アナウンス専用）は安全側で据え置いており、RF 確認後に
> `PRE_PADDING_PACKETS` と同値まで下げてよい構成です。詳細と巻き戻し手順はリポジトリ直下の `Changelog.md`。

## 主なファイル

- `dvswitch_bot.py` — **V2.08vvw** VVW版 常駐 bot（送出タイミング実測総見直し済み。JTW V2.10jtw 同等）
- `bot_config.json` — 設定サンプル。**VVW版は WEATHER 4キー入り**（既定 `WEATHER_ENABLED: false`。座標例は尾張旭。自局の緯度経度に書き換えて有効化）
- `voice_make.py` — **V1.03vvm** 定時音声生成（VOICEVOX。取得・合成・地名・1本化＋終わりの助走）
- `create_wav.sh` — **V1.4vv** 固定WAV生成（VOICEVOX 話者選択＋素材WAVへ語頭の助走を焼き込む。V2.08vvw 頭欠け対策）
- `vv_say.py` — **V2.0vv** VOICEVOX 合成ツール（話者可変）
- `bot_setup.py` / `dvs_config.sh` / `test_send.py` / `wav_source.json` — VV版（`ocv_dvs_vv/`）と共通
- Web ダッシュボードは JT/VV/VVW 共用: リポジトリ直下の `dashboard/app.py`

## 構築・導入

VV版の構築手順書『ocv_dvs_vv/OpenCCVoice for DVSwitch VV版（VOICEVOX）構築手順書.md』に従って構築し、bot のみ本ディレクトリの `dvswitch_bot.py` を使用してください。天気の設定キーは `bot_config.json` へ追記します（三位一体 UI 対応までは手書き）。

> ⚠️ 現時点で bot_setup.py / ダッシュボードは WEATHER キー未対応です。これらで設定を保存すると WEATHER キーが消えます（bot は機能OFFとして安全に動作継続）。UI 対応版が出るまで、天気設定の変更は JSON 直接編集で行ってください。
