#!/bin/bash
# ============================================================
# install.sh  OpenCCVoice for DVSwitch Web Dashboard V3.21
# curl対応版 — GitHubから直接取得してインストール
#
# 使い方:
#   curl -fsSL https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard/install.sh | sudo bash
# ============================================================
set -e

GITHUB_RAW="https://raw.githubusercontent.com/ji2tab/OpenCCVoice-For-DVSwitch/main/dashboard"
WEB_DIR="/opt/dvswitch_bot/web"
SERVICE_DST="/etc/systemd/system/dvswitch-web.service"

if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] sudo で実行してください"
  echo "  curl -fsSL ${GITHUB_RAW}/install.sh | sudo bash"
  exit 1
fi

echo "[1/4] flask インストール確認..."
python3 -c "import flask" 2>/dev/null || apt-get install -y python3-flask

echo "[2/4] ファイルを取得・配置: $WEB_DIR"
mkdir -p "$WEB_DIR"
curl -fsSL "${GITHUB_RAW}/app.py" -o "$WEB_DIR/app.py"
chmod 755 "$WEB_DIR/app.py"

echo "[3/4] systemd サービス登録: $SERVICE_DST"
curl -fsSL "${GITHUB_RAW}/dvswitch-web.service" -o "$SERVICE_DST"
systemctl daemon-reload
systemctl enable dvswitch-web.service

echo "[4/4] サービス起動..."
systemctl restart dvswitch-web.service
sleep 2

STATUS=$(systemctl is-active dvswitch-web.service)
if [ "$STATUS" = "active" ]; then
  IP=$(hostname -I | awk '{print $1}')
  echo ""
  echo "✔ dvswitch-web が起動しました！"
  echo "  ブラウザでアクセス: http://${IP}:8081/"
  echo ""
else
  echo ""
  echo "✖ サービスの起動に失敗しました。ログを確認:"
  echo "  journalctl -u dvswitch-web -n 30"
fi
