#!/bin/bash
# ============================================================
# uninstall.sh  OpenCCVoice for DVSwitch Web Dashboard V3.11
#
# 使い方:
#   curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/uninstall.sh | sudo bash
# ============================================================
set -e

WEB_DIR="/opt/dvswitch_bot/web"
SERVICE_DST="/etc/systemd/system/dvswitch-web.service"

if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] sudo で実行してください"
  echo "  curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/uninstall.sh | sudo bash"
  exit 1
fi

echo "[1/3] サービス停止・無効化..."
systemctl stop dvswitch-web.service 2>/dev/null || true
systemctl disable dvswitch-web.service 2>/dev/null || true

echo "[2/3] サービスファイル削除..."
rm -f "$SERVICE_DST"
systemctl daemon-reload

echo "[3/3] アプリファイル削除..."
rm -f "$WEB_DIR/app.py"
rmdir "$WEB_DIR" 2>/dev/null || echo "       (他のファイルが残っているため $WEB_DIR は削除しません)"

echo ""
echo "✔ アンインストール完了"
echo "  以下のファイルはそのまま残しています（手動削除が必要な場合のみ）:"
echo "  /opt/dvswitch_bot/bot_config.json"
echo "  /opt/dvswitch_bot/bot_change_log.json"
echo "  /opt/dvswitch_bot/bak/ini/"
