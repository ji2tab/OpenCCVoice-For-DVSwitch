# 別資料：公式マニュアル（DVSwitch_install.pdf）との差分

> 🔒 **取り扱い注意：本資料は公開しない（個人検証用）。**
> md380-emu のソース／ファームウェアに関する記述を含み、ライセンス上の懸念があるため。

**対象:** 公式 `DVSwitch_install.pdf` の **Appendix E: Installing DVSwitch on an existing Linux installation**
**今回の環境:** Raspberry Pi Zero 2W / Raspberry Pi OS (Legacy, 32-bit) Lite — **Debian Bookworm** ベース
**主旨:** 本手順書が公式マニュアルと異なる箇所と、その**根本原因**を整理する。

---

## 結論：差分の本質は「OS が Bookworm である」こと

公式 Appendix E は **Buster（Debian 10）** を前提に書かれている。
本手順は **Bookworm（Debian 12）** で実施したため、インストーラ名・互換性対応で差が出た。
差分のほとんどは Bookworm 世代に由来する。

---

## 公式 Appendix E の手順（原文の要旨）

```bash
wget http://dvswitch.org/buster
sudo chmod +x buster
sudo ./buster
sudo apt-get update
sudo apt-get install dvswitch-server
# インストール完了後 reboot
# ターミナルで "dvs" を実行して設定メニューへ
```

---

## 差分一覧

| 項目 | 公式 Appendix E（Buster 前提） | 今回（Bookworm） | 根本原因 |
|---|---|---|---|
| インストーラ名 | `wget http://dvswitch.org/buster` | `wget http://dvswitch.org/bookworm` | OS 世代の違い。Bookworm 機に `buster` を使うと Buster 前提のリポジトリ設定が入り不整合の恐れ |
| 実行ビット付与 | `sudo chmod +x buster` | `chmod +x bookworm` | 同一（ファイル名のみ差） |
| インストーラ実行 | `sudo ./buster` | `sudo ./bookworm` | 同一（ファイル名のみ差） |
| パッケージ導入 | `sudo apt-get install dvswitch-server` | `sudo apt install dvswitch-server -y` | 実質同一 |
| 設定メニュー起動 | `dvs`（PATH 前提） | `/usr/local/dvs/dvs`（フルパス） | 本環境では `dvs` 単体が `command not found`。PATH 未通のためフルパスで実行 |
| md380-emu の qemu | **記載なし**（Buster の qemu 5.2 で問題が出ない） | qemu 5.2 へ**ダウングレード＋hold が必須** | 🔴 Bookworm 標準の qemu 7.2 が md380-emu と非互換で SEGV |

---

## なぜ公式には qemu 対策が載っていないのか

公式 Appendix E は Buster 環境を想定している。
**Buster 標準の qemu-user-static は 5.2 系**であり、md380-emu の ARM バイナリと問題なく動く。
そのため公式手順には qemu に関する記述が一切ない。

一方 **Bookworm の qemu-user-static は 7.2 系**で、md380-emu が実際の AMBE デコード時に
`status=11/SEGV` でクラッシュする。これは公式マニュアルが**想定していない世代差**から生じた
トラブルであり、本手順書が独自に対策（5.2 へダウングロード＋`apt-mark hold`）を加えた最大の理由。

> 同一の Zero 2W でも、Bullseye（Debian 11, qemu 5.2）で動作していた実機があった事実が、
> 「qemu のバージョンが原因」という切り分けの決め手になった。

### 技術的根拠（Debian バグ報告で裏付け）

この現象は本案件固有の偶発事故ではなく、**Debian の既知の不具合**として複数報告されている。

- **Debian Bug #1014177**（qemu-user-static: QEMU aarch64 user mode emulation always segfaults）
  「QEMU のユーザーモードエミュレーションは Bullseye の qemu 5.2 では正常動作するが、
  bookworm 系（qemu 7.2）では segfault する」という趣旨の報告。今回の
  「5.2 で動く／7.2 で SEGV」という観察と一致する。

- **Debian Bug #1053101**（qemu-user-static: segfault when running ... certain static binaries / qemu 7.2+dfsg-7+deb12u2）
  より具体的な原因分析。**完全に静的リンクされた qemu エミュレータ自身が `0x00040000`
  にマップされ、ターゲット側の静的実行ファイルが同じ `0x00040000` にマップしようとした際、
  qemu がそのアドレスを変換しないため SIGSEGV が発生する**と報告。原因は
  **PIE（位置独立実行ファイル）の扱い**にあると見られている。

**なぜ md380-emu がこれを踏むのか:**
md380-emu は travisgoodspeed/md380tools 由来で、**MD380 ファームウェアを特定アドレスの
メモリにリンクした静的 32bit ARM 実行ファイル**であり、binfmt 経由で qemu 上で動く
（公式 Wiki の記述より）。すなわち「固定アドレスにマップする静的 ARM バイナリを qemu で動かす」
という、#1053101 が指摘するアドレス衝突パターンそのものに該当する。

**結論:**
SEGV は md380-emu のビルド不良が単独原因ではなく、**qemu 7.2 系ユーザーモードの
静的バイナリ／PIE アドレスマッピングの問題が主因**で、md380-emu の「固定アドレスに
マップする静的 ARM バイナリ」という性質がそれを顕在化させた、両者の組み合わせ問題。
Buster/Bullseye の qemu 5.2 系ではこの問題が顕在化しないため、5.2 へのダウングレードが
有効な回避策となる。

> 一次情報を辿る場合は Debian BTS で上記バグ番号（#1014177 / #1053101）を参照。
> 将来 qemu 側で修正版が bookworm に入れば、ダウングレードは不要になる可能性がある。

---

## 設定メニュー `dvs` について

公式は `dvs`（引数なし）で起動と記載。これは PATH が通っている、または
ダッシュボード導入時にリンクが張られる前提と思われる。
本環境では `sudo dvs` が `command not found` になったため、実体のフルパス
**`/usr/local/dvs/dvs`** を直接実行した。機能は同一。

---

## md380-emu のソースと「環境に合わせた再ビルド」について

### ⚠️ 取り扱い注意（公開禁止）

本節および本資料・関連成果物は **公開しない**。
md380-emu は **TYT MD380 ハンディ機のファームウェアを内部に取り込んでビルド**される
性質上、ファームウェア由来コードの再配布にライセンス上の懸念があるためである。
ビルド成果物・ファームウェアイメージを含むものは外部に出さず、個人の検証範囲に留める。

### ソースのありか

- ソースは **`travisgoodspeed/md380tools`** リポジトリの `emulator/` 配下
  （`md380-emu.c` / `ambe.c` ほか）。これが大元。
- DVSwitch が deb で配るバイナリ（OCV に入った 2025-09-09 版など）は、
  この大元ソースを DVSwitch 側がビルドして
  `dvswitch.org/ASL_Repository/...` 等で配布しているもの。
- ロジックは 2018 年頃から本質的に変わっておらず、「新しくなって qemu 7.2 問題が
  解消された版」は本調査時点（2026-06）では確認できなかった。

### ソースだけではビルドできない

Makefile は、コンパイル済みオブジェクトに加えて
**MD380 ファームウェアイメージ（D002.032）とコアダンプ（d02032-core）を
`objcopy` で固定アドレスに焼き込んでリンク**する構造になっている。
すなわち AMBE コーデックの実体はファームウェア内にあり、ソースはそれを呼び出す殻に近い。
したがって再ビルドには **MD380 ファームウェア本体の入手・展開**が前提になる
（ここがライセンス上の懸念点でもある）。
ビルド環境も古く、公式 Wiki は **gcc-6-arm-linux-gnueabi**（Bookworm 標準には無い）と
qemu を備えた Debian/Testing を指定している。

### 🔴 再ビルドしても qemu 7.2 問題は解決しない見込み

最重要点。md380-emu は設計上、ファームウェアを `0x0800C000`、SRAM を `0x20000000` という
**固定アドレスにマップ**する（`md380-emu.c` の `mapimage()`）。
これは前述の Debian Bug #1053101 が指摘する「静的バイナリの固定アドレス衝突」を
踏みやすい構造そのもの。**同じソースを環境に合わせて再ビルドしても、この固定アドレス設計が
変わらない限り qemu 7.2 では同じ SEGV を踏む公算が大きい。**
よって「環境に合わせた再ビルド」は qemu 7.2 問題の解決策にはならない。

### 現実的な選択肢

1. **qemu 5.2 へダウングレード（今回採用）** — 最も確実。ソースもファームも触らない。
2. ハードウェア AMBE ドングル（ThumbDV / DV3000 等）へ移行 — qemu を介さない。別途コストと設定。
3. 別系統のソフトデコーダ（mbelib 系）へ移行 — ライセンス・音質の論点が別途発生。

---

## まとめ

- 公式 Appendix E は **Buster 前提**。Bookworm で実施する場合、インストーラ名は **`bookworm`** を使う。
- 公式が触れていない **qemu 7.2 → 5.2 ダウングレード** が Bookworm では事実上必須（md380-emu の SEGV 回避）。
- md380-emu の**再ビルドは qemu 7.2 問題の解にならない**（固定アドレス設計のため）。ソース／ファームはライセンス上の懸念があり**公開しない**。
- 設定メニューは公式の `dvs` ＝本環境の `/usr/local/dvs/dvs`。PATH の差。
- それ以外（chmod、apt install、reboot の流れ）は公式と実質同一。

---

*作成: 2026-06-02 / 本体手順書「DVSwitch_OpenCCVoice_構築手順書.md」の補足資料 / 実機: OCV (Zero 2W, Bookworm 32-bit)*
