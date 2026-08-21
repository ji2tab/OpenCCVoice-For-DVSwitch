# JTW版 改修まとめ（V2.05jtw / V2.04jtw / V3.2）

| ファイル | 版 | 内容 |
|---|---|---|
| `dvswitch_bot.py` | **V2.05jtw** | 天気の付与先分割（V2.04jtw）＋ VV版タイミングの反映（V2.05jtw） |
| `bot_setup.py` | **V2.04jtw** | 天気の付与先の対話 |
| `app.py` | **V3.2** | 天気カード＋未知キー保護 |
| `voice_make.py` | V1.01vmp | **改修不要**（`--weather` の有無を見るだけの設計のため） |

---

# 1. 天気読み上げ — 付与先の個別指定（三位一体変更）

## 追加した設定キー（bot_config.json / いずれも任意キー）

| キー | 既定 | 対象 |
|---|---|---|
| `WEATHER_ENABLED` | false | 親スイッチ（V2.03jtw から変更なし） |
| `WEATHER_ON_TIME_SIGNAL` | **true** | 時報（:00）・30分案内（:30） |
| `WEATHER_ON_MESSAGE` | **true** | 定時メッセージ（001/002） |
| `WEATHER_LATITUDE` / `WEATHER_LONGITUDE` | — | 取得座標（有効時は必須） |

新キーの既定を true にしたため、**キーが無い既存の JTW 設定は V2.03jtw と完全に同一動作**
（全定時音声へ一様付与）になる。

## 検証ルール（三者で同一）

`WEATHER_ENABLED=true` のとき、実際に天気を付ける先が1つ以上あること。

- 時報系: `WEATHER_ON_TIME_SIGNAL` かつ `TIME_SIGNAL_MODE >= 1`
- メッセージ系: `WEATHER_ON_MESSAGE` かつ `ANNOUNCE_FREQ > 0`

両方とも成立しなければエラー。V2.03jtw の「mode0 かつ freq0 は不可」を包含する一般化。
座標は必須かつ範囲内（緯度 -90〜90 / 経度 -180〜180）。

## dvswitch_bot.py（V2.04jtw 分）

1. `_weather_wanted()` を `_weather_wanted(kind)` に変更し、kind で付与先を分岐。
   V2.03jtw のコメントが予告していた分岐点そのもので、判断は bot 側のこの1箇所だけ。
   `time_signal` / `half_hour` → 時報系、`message` → メッセージ系。未知の kind は
   安全側で付けない（警告ログ）。
2. `_vmp_spawn()` は kind 別の判定を1回だけ評価し、コマンドとログの両方で使い回す。
3. `_load_config()` に `WEATHER_ON_*` の読み取りを追加。`_as_bool()` に既定値引数を
   追加した（従来の呼び出しは `default=False` のまま無影響）。
4. 併用不可の判定を上記の一般化ルールへ差し替え。
5. 起動バナーに実際の付与先を表示（例 `付与先: :00/:30 + 001/002`）。
6. 起動バナーの版表記をベタ書きから `__version__` 参照へ変更（VV版 V1.95a と同じ整理）。

## bot_setup.py V2.03jtw → V2.04jtw

1. 定時メッセージ（再生周期）の選択後の天気対話を拡張。天気を ON にすると、
   付与先を2問（時報系 / メッセージ系）で選ぶ。
2. 鳴る音声が無い系統は問わずに OFF 固定にし、理由を表示
   （時刻案内 mode0 / 定時メッセージ 0 回）。
3. 付与先が両方 OFF になった場合は天気自体を OFF に倒す（保存時の検証エラーを未然に回避）。
4. 確認画面に付与先を表示。`validate()` を上記の一般化ルールへ差し替え。

## app.py V3.11 → V3.2

1. Bot設定カードの下に「天気読み上げ」カードを新設（左カラムを2カード縦積みに変更）。
   チェックボックス3つ（有効 / 時報系 / メッセージ系）＋緯度経度。
2. JTW 判定 `jtw_available()` を追加。`bin/voice_make.py` の存在、または bot 版文字列に
   `jtw` を含むかの OR。非 JTW ノードではカードごとグレーアウトし、保存ルートでも
   天気キーに一切触れない。
3. **未知キー保護（V3.11 以前の欠陥修正）**。従来の保存ルートは bot_config.json を
   「ダッシュボードが知っているキーだけ」で作り直していたため、JTW ノードで保存すると
   `WEATHER_*` が黙って消えていた。V3.2 は既存ファイルを土台に差分更新するため、
   知らないキーは失われない。
4. 組み立て・検証を `build_bot_cfg()` / `validate_bot_cfg()` に集約し、`/bot_config` と
   `/save_all` の重複を解消。
5. 座標欄を空で保存すると既存値を維持する。

## 組み合わせ互換

| bot | ダッシュボード / setup | 挙動 |
|---|---|---|
| V2.04jtw 以降 | V3.2 / V2.04jtw | 付与先を個別指定できる（本来の構成） |
| V2.03jtw | V3.2 / V2.04jtw | 付与先キーは無視され全定時音声へ一様付与。設定は壊れない |
| V2.04jtw 以降 | V3.11 / V2.03jtw | 旧setupで保存すると付与先キーが消え、既定 true＝一様付与に戻る |
| JT版 / VV版 | V3.2 | 天気カードはグレーアウト。天気キーには触れない |

---

# 2. 送出タイミング — VV版 V1.98vv の実測値を反映（V2.05jtw）

> ⚠️ **この節（V2.05jtw 時点の値）は V2.10jtw で全面的に置き換えられました。**
> 下表の 85 / 5 / 1.5 / 0.0 や「巻き戻し＝75 / 65 / 1.0 / 1.5」は**現行では使いません**。
> V2.10jtw は前パディング 25(0.5s)／後パディング 6(0.12s)／EOT 1／TX lead 0.0 とし、
> 語頭前の無音は素材WAV側（create_wav.sh V1.3 の助走）が持ちます。**前パディング 0 と
> EOT 0 は禁止**（ヘッダ喪失／ストリーム未クローズ）。現行の値と根拠・巻き戻し手順は
> リポジトリ直下の `Changelog.md`（V2.10jtw の節）を参照してください。以下は歴史的記録です。


## 変更した定数（コードは無変更）

| 定数 | V2.04jtw まで | **V2.05jtw** | 意味 |
|---|---|---|---|
| `REPLY_TX_LEAD_DELAY_SEC` | 1.0 | **0.5** | キャッシュ命中時の送出前ガード |
| `PRE_POST_PADDING_PACKETS` | 75（1.5s） | **85（1.7s）** | 前後パディング |
| `NOISE_LEAD_PACKETS` | 65（1.3s） | **5（0.1s）** | 先頭トーンの長さ |
| `PRE_AUDIO_SILENCE_SEC` | 1.5 | **0.0** | WAVに焼き込む頭無音 |

キャッシュ命中時の立ち上がり積算: `0.5 + 1.7 + 0.0 = 2.2秒`（従来 4.0秒）

## 設計思想の変更

同じ「intro 頭欠けを防ぐ」目的に対し、手段を切り替えた。

- 旧（JT系）: ストリーム内に無音を焼き込む＋長いトーン（1.3s）でゲートをこじ開ける
- 新（VV系）: 焼き込み無音を廃止し、前パディング自体を伸ばす（1.7s）。トーンは 0.1s

VV版 V1.98vv の実測で判明したのは、**頭欠けを決めているのはトーンの長さではなく
前パディング全体の長さだった**という点。V1.88 時代の「トーンでゲートの床を跨ぐ」
という説明は誤りだったとファイル内に明記されている。トーンを 0.1s に削ったことで、
ゲート開放後に残っていた「ブーン」も消えている。

`NOISE_LEAD_PACKETS=5` は `_FADE_STEPS` と同数のため、5個すべてがフェード扱いになり、
振幅 150 の定常トーンは1ブロックも送出されない（振幅 112→82→52→30→12 のみ）。
それでもゲートは開く、というのが実測結果である（理屈では未解明）。

## ⚠️ JT系での実波検証は未実施

VV版の値は **ocv-voicevox（直 TGIF 接続・VOICEVOX 合成 0.9秒）** での実測である。
JTW ノードは Open JTalk（合成 1.5秒前後）で、経路も異なる可能性がある。

- `REPLY_TX_LEAD_DELAY_SEC` はキャッシュ命中時のみのガード。ミス時は合成時間が
  ガードを兼ねるため、JTW の方が総リードは長くなる（安全側）
- 配置後は必ず実機で「intro の頭欠け」「頭のブーン」の有無を確認すること

## 巻き戻し手順

コードは一切変えていないため、定数を戻すだけで完全に元へ戻る。

1. 頭欠けが出る → `PRE_POST_PADDING_PACKETS` を 85 → 90, 95 と増やす方向で試す
2. 頭シャーが出る → `NOISE_LEAD_PACKETS` を 5 → 65 に戻す
3. 完全復帰 → 4定数すべてを V2.04jtw の値（75 / 65 / 1.0 / 1.5）へ戻す

## キャッシュへの影響

`PRE_AUDIO_SILENCE_SEC` はキャッシュ署名（`_reply_signature`）に含まれるため、
値を変えると既存のキャッシュは自動的に無効化される。`CACHE_SCHEMA` を上げる必要はない。

## コメントのみの修正（挙動不変）

- `send_usrp_wav_with_padding()` の docstring「前後 1.5 秒」→ 実際の計算式に修正
- `GATE_BURST_PACKETS` / `GATE_BURST_AMP` に【未使用】注記（定義のみで参照されていない）
- `USRP_EOT_REPEAT` の「複数回送って確実化」→ 既定 1 で多重送出は無効、と実態に修正

---

# 検証内容

- `ast.parse` 構文チェック（3ファイル）
- **版表記の全箇所一致**: docstring タイトル / Document Version / `__version__` / 起動バナー
- **三者の検証ルール一致**: 12パターンの設定で bot `_load_config` / setup `validate` /
  dashboard `validate_bot_cfg` の判定が完全一致
- `_weather_wanted(kind)` の分岐（6パターン）と `_vmp_spawn` の `--weather` 付与
- bot_setup 対話フロー（mode1/freq2、mode2/freq0 の2シナリオ）
- ダッシュボード実レンダリング（JTW / 非JTW でのカード状態、保存時の未知キー保持、
  検証エラー4種）
- **送出ロジックの無変更確認**: `send_usrp_wav_with_padding()` のコード64行が
  V2.04jtw と完全一致（差は定数値とコメントのみ）
- タイミング4定数が VV版 V1.99vv と一致

---

# デプロイ

```bash
# JTW ノード
sudo cp dvswitch_bot.py /opt/dvswitch_bot/bin/dvswitch_bot.py
sudo cp bot_setup.py    /opt/dvswitch_bot/bin/bot_setup.py
sudo cp app.py          /opt/dvswitch_bot/web/app.py
sudo systemctl restart dvswitch-bot dvswitch-web

# JT / VV ノード（ダッシュボードのみ更新）
sudo cp app.py /opt/dvswitch_bot/web/app.py
sudo systemctl restart dvswitch-web
```

配置後の確認:

```bash
journalctl -u dvswitch-bot -n 40
```

- `DVSwitch Bot V2.05jtw ... starting up`
- `Weather readout : ON (...) 付与先: ...`

そのうえで実機のカーチャンク応答で **intro の頭欠け・頭のブーン** を確認する。
問題があれば上記「巻き戻し手順」に従って定数を戻す。
