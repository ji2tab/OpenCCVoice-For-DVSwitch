## V2.08vvw / V1.03vvm (2026-08-21)  送出タイミング実測総見直し（JTW V2.10jtw の VVW 移植）

JTW（ocv-uhf）で RF 実機・DroidStar ログ・45日1390サンプル統計から確定した頭切れ対策を
VVW（ocv-voicevox / VOICEVOX / 直 TGIF）へ移植した版。前後パディングの定数分離も同時に実施
（VVW は分離が未コミットだったため V2.07vvw から1版で分離＋タイミングをまとめる）。

### 頭切れの原因3つ（JTW で確定・VVW でも同構造のため移植）
1. 素材WAVに語頭前の助走が無かった → create_wav.sh V1.4vv が助走を焼き込む。
2. 録音WAVのノイズフロア段差 → 20ms フェードインで平滑化。
3. ストリーム先頭の SET_INFO（keyup=0）が語頭を巻き込む → TX_METADATA_BEFORE_VOICE=False。

### 定数（V2.08vvw）
| 定数 | 旧 | 新 |
|---|---|---|
| PRE_PADDING_PACKETS | —（共有85=1.70s） | **25 (0.50s)** ヘッダ保護。0 禁止 |
| POST_PADDING_PACKETS | —（共有85=1.70s） | **6 (0.12s)** 終端フラッシュ |
| STARTUP_PRE_PADDING_PACKETS | 150 | **150 据え置き**（VVW固有・RF確認後に縮小可） |
| USRP_EOT_REPEAT | 3 | **1**（0 は下限で禁止） |
| REPLY_TX_LEAD_DELAY_SEC | 1.5 | **0.0**（fixed_intro の助走へ移動） |
| REPLY_TAIL_SEC | — | **1.0** 新設（署名にも追加） |
| TX_METADATA_BEFORE_VOICE | — | **False** 新設 |
| ASSERT_IDENTITY_ON_RX_END | — | **False** 新設 |

V1.03vvm: `LEAD_BEFORE_INTRO_SEC` 0.5→0.0（素材側へ）、`SLOT_TAIL_SEC=1.0` 新設。
create_wav.sh V1.32vv→V1.4vv: apply_leads 新設（fixed_intro pad 1.78 / 他 fade 0.02+pad 0.5）。

### 禁止事項（JTW 実測）
- 前パディング 0 禁止（先頭トーンが消えると VoiceLCHeader が中継で失われ幽霊ストリーム化）。
- EOT 0 禁止（Analog_Bridge がストリームを閉じられず受信機が固まる）。max(1,…) で下限保証。

### ⚠ VVW は要 RF 再確認
上記実測は JTW（ocv-uhf / Open JTalk）で確定。VVW は合成エンジン・経路が異なるため、配置後に
ocv-voicevox 実機で頭欠け・切れ際・幽霊ストリーム（DroidStar ログの started/ended と bot 実測の一致）
を必ず確認すること。STARTUP_PRE_PADDING_PACKETS=150 は安全側で据え置き（本来冗長の可能性が高い）。

### 検証（本セッション）
- 送出関数をスタブ実行: 前25/後6 でトーン5個・EOT1、起動 pre=150 で +125pkt、EOT=0 でも下限1、
  TX_METADATA_BEFORE_VOICE の True/False でストリーム先頭 SET_INFO の有無が切り替わることを確認。
- create_wav.sh apply_leads: 模擬素材で fixed_intro 語頭2000ms / time_intro・001・002 語頭520ms＋
  先頭無音を生成（JTW V1.3 と同一結果）。
- py_compile / bash -n 全通過。

### デプロイ（ocv-voicevox）
dvswitch_bot.py（V2.08vvw）/ voice_make.py（V1.03vvm）/ create_wav.sh（V1.4vv）を差し替え →
`sudo systemctl restart dvswitch-bot` → 一度 `sudo ./create_wav.sh --regen`（記録済み話者・texts で
素材を助走付きに焼き直す）→ 起動アナウンス・時報・カーチャンクを RF ＋ DroidStar で確認。
