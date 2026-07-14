# vv_say.py ソフトウェア仕様書（VV版 V2.0vv）

**対象ファイル:** `/opt/voicevox/vv_say.py`
**対象バージョン:** VV版（`dvs_ocv_vv/`）**V2.0vv**
**役割:** VOICEVOX CORE でテキストを音声合成し、WAV として保存する VV版固有の小ツール。`create_wav.sh`（VV版）から呼ばれ、固定 WAV の音声本体を生成する。
**位置づけ:** 本ファイルは **VV版（VOICEVOX 系ノード）専用**。JT版（リポジトリ直下、Open JTalk）には存在しない。版番号の `vv` サフィックスは VOICEVOX 系ノード用ファイルであることを示す命名規約。

この文書は**スクリプト本体の内部仕様**を記述する技術文書です。VV版の構築・運用手順は
`dvs_ocv_vv/` の『VV版（VOICEVOX）構築手順書』、システム全体は別冊『システム仕様書』を参照してください。

---

## 目次

1. [概要と責務](#1-概要と責務)
2. [依存・実行環境](#2-依存実行環境)
3. [定数仕様](#3-定数仕様)
4. [コマンドライン仕様（Usage）](#4-コマンドライン仕様usage)
5. [話者解決の優先順](#5-話者解決の優先順)
6. [関数仕様](#6-関数仕様)
7. [処理フロー](#7-処理フロー)
8. [設計上の要点](#8-設計上の要点)
9. [改修時の注意点](#9-改修時の注意点)

---

## 1. 概要と責務

`vv_say.py` は、与えられたテキストを VOICEVOX CORE で合成し WAV ファイルに書き出すだけの単機能ツール。責務は次の1点。

- **テキスト → VOICEVOX 合成 → WAV 保存**（話者は引数・`wav_source.json`・既定の順で解決）

カーチャンク検知・スケジューラ・送信などは持たない。`create_wav.sh`（VV版）が固定 WAV を作る際の合成エンジンとして呼ばれる。bot 本体（`dvswitch_bot.py` VV版）は VOICEVOX を同一プロセス内で直接使うため、`vv_say.py` は経由しない。

---

## 2. 依存・実行環境

| 項目 | 内容 |
|---|---|
| Python | `voicevox_core` を含む venv の python3（`/opt/dvswitch_bot/venv/bin/python3`）で実行する |
| ライブラリ | `voicevox_core.blocking`（`Onnxruntime` / `OpenJtalk` / `Synthesizer` / `VoiceModelFile`） |
| 後段変換 | 8kHz / mono / 16bit への変換は本スクリプトでは行わず、呼び出し側（`create_wav.sh` の SoX）が担う |

システムの `/usr/bin/python3` では `voicevox_core` を import できないため、必ず venv の python3 で起動する。

---

## 3. 定数仕様

| 定数 | 値 | 意味 |
|---|---|---|
| `__version__` | `"V2.0vv"` | 機械可読の版表記（固定行）。`--version` で出力 |
| `DIST_DIR` | `/opt/voicevox/dist` | VOICEVOX 配布物のルート |
| `VVM_DIR` | `{DIST_DIR}/models/vvms` | 音声モデル（`.vvm`）の置き場所 |
| `SRC_JSON` | `/opt/dvswitch_bot/wav_source.json` | 話者選択（`"voice"`）の記録元 |
| `DEFAULT_STYLE_ID` | `30` | 既定話者 No.7（アナウンス）の style_id |
| `DEFAULT_VVM` | `"6.vvm"` | 既定話者のモデル |

既定話者は `create_wav.sh` / `dvswitch_bot.py`（VV版）と揃えて **No.7（アナウンス）= style_id 30 / 6.vvm** とする。

---

## 4. コマンドライン仕様（Usage）

```
vv_say.py "<text>" <output_wav_path> [style_id] [vvm]
vv_say.py --version
```

| 引数 | 要否 | 意味 |
|---|---|---|
| `<text>` | 必須 | 合成する日本語テキスト |
| `<output_wav_path>` | 必須 | 出力 WAV のパス |
| `[style_id]` | 任意 | 話者の style_id（明示指定）。空文字は未指定扱い |
| `[vvm]` | 任意 | 音声モデル（ファイル名 or フルパス）。空文字は未指定扱い |
| `--version` / `-V` | — | `vv_say.py V2.0vv` を出力して終了 |

引数不足（2 個未満）のときは Usage を stderr に出して `exit 1`。

---

## 5. 話者解決の優先順

`_resolve_voice()` が次の優先順で `(style_id, vvm_path)` を確定する。style_id と vvm は不一致による合成失敗を避けるため必ずセットで扱う。

1. **コマンドライン引数**（`style_id` と `vvm` が両方そろっていれば最優先）
2. **`wav_source.json` の `"voice"`**（`create_wav.sh` が保存した選択）
3. **既定 No.7（アナウンス）**（`style_id 30` / `6.vvm`）

`vvm` がファイル名なら `VVM_DIR` を前置してフルパス化し、絶対パス・パス区切りを含む場合はそのまま使う。解決後の `vvm` が実在しなければ stderr にエラーを出して `exit 1`。

---

## 6. 関数仕様

| 関数 | 役割 | 備考 |
|---|---|---|
| `_resolve_onnxruntime_so()` | onnxruntime の `.so` をバージョン非依存で解決 | `glob` で `libvoicevox_onnxruntime.so*`。無ければ `FileNotFoundError` |
| `_load_voice_from_json()` | `wav_source.json` の `"voice"` から `(style_id, vvm)` を取得 | 取れなければ `(None, None)`。style_id は int 化できるときのみ採用 |
| `_vvm_to_path(vvm)` | `.vvm` ファイル名をフルパスへ | 既にパスならそのまま |
| `_resolve_voice(argv)` | 引数 → JSON → 既定 の順で話者を確定 | 第5章の優先順を実装 |
| `main()` | Usage 判定・話者解決・合成・保存 | `--version` の早期リターンを含む |

---

## 7. 処理フロー

1. `--version` / `-V` なら版を出力して終了
2. 引数チェック（不足なら Usage 出力＋`exit 1`）
3. `_resolve_voice()` で `(style_id, vvm_path)` を確定。`vvm_path` が実在しなければ `exit 1`
4. `Onnxruntime.load_once()`（`.so` は glob 解決）／ `OpenJtalk(dict)` ／ `Synthesizer` を構築
5. `VoiceModelFile.open(vvm_path)` → `load_voice_model()`
6. `create_audio_query(text, style_id)` → `synthesis(query, style_id)` で WAV バイト列を生成
7. 出力パスへ書き込み

---

## 8. 設計上の要点

- **出力サンプリングレートをハードコードしない。** V1.0 の `query.output_sampling_rate=48000` 固定は撤去（deprecation 対応）。VOICEVOX のネイティブ出力に任せ、8kHz への変換は呼び出し側（`create_wav.sh` の SoX）が行う。
- **`.so` はバージョン非依存の glob で解決。** V1.0 のバージョン付き直書き（`.so.1.17.3`）を廃止。リリースで版番号が変わっても壊れない。
- **話者を `create_wav.sh` / bot と共有。** `wav_source.json` の `"voice"` を参照することで、固定 WAV と bot の動的合成の話者が揃う。V2.0vv は `create_wav.sh` V1.2+（voice 記録）／ `dvswitch_bot.py` V1.96+ と対応。

---

## 9. 改修時の注意点

| 注意点 | 内容 |
|---|---|
| **venv 実行** | `voicevox_core` は venv 側にのみ入る。`/usr/bin/python3` で叩かない |
| **style_id と vvm はセット** | 片方だけ変えると合成失敗。優先順で必ず組として確定させる |
| **サンプリングレート** | 48kHz 等をハードコードで戻さない（deprecation・8kHz 変換は SoX の責務） |
| **`.so` パス** | 固定パスに戻さない。glob 解決を維持する |
| **既定話者** | No.7（30 / 6.vvm）。`create_wav.sh` / bot の既定と必ず揃える |

---

*vv_say.py ソフトウェア仕様書（VV版 V2.0vv）*
*対象: /opt/voicevox/vv_say.py（VV版固有 / dvs_ocv_vv/vv_say.py）*
*Contributors: JA2CCV / JI2TAB / JJ2YYK / OpenCCVoice Contributors*
