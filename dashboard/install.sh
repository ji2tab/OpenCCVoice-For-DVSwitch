#!/bin/bash
# ============================================================
# install.sh  OpenCCVoice for DVSwitch Web Dashboard V2.2
# 配置先: /opt/dvswitch_bot/web/
# 使い方: sudo bash install.sh
# ============================================================
set -e

WEB_DIR="/opt/dvswitch_bot/web"
SERVICE_DST="/etc/systemd/system/dvswitch-web.service"

if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] sudo で実行してください: sudo bash install.sh"
  exit 1
fi

echo "[1/4] flask インストール確認..."
python3 -c "import flask" 2>/dev/null || apt-get install -y python3-flask

echo "[2/4] ファイルを配置: $WEB_DIR"
mkdir -p "$WEB_DIR"
cp -f app.py "$WEB_DIR/app.py"
chmod 755 "$WEB_DIR/app.py"

echo "[3/4] systemd サービス登録: $SERVICE_DST"
cp -f dvswitch-web.service "$SERVICE_DST"
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
