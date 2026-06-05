# OpenCCVoice-For-DVSwitch ダッシュボード 取扱説明書

このドキュメントでは、DVSwitch向け「OpenCCVoice」ダッシュボードの導入（インストール）および削除（アンインストール）手順について説明します。

## 1. 導入（インストール）

システムにダッシュボードをインストールするには、ターミナルを開き、以下のコマンドを実行してください。

```bash
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/install.sh | sudo bash

```

> **注意事項**
> * インストールには管理者権限が必要です。コマンド実行時に `sudo` のパスワードを求められる場合があります。
> * 事前にインターネット接続が正常であるか確認してください。
> 
> 

---

## 2. 削除（アンインストール）

ダッシュボードをシステムから削除する場合は、ターミナルで以下のコマンドを実行してください。

```bash
curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/uninstall.sh | sudo bash

```

> **注意事項**
> * この操作により、ダッシュボードに関連する設定やファイルがシステムから削除されます。
> * 実行前にもう一度、削除して問題ないか確認してください。
> 
>
