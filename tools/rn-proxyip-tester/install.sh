#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/rn-proxyip-tester}"
SERVICE_NAME="${SERVICE_NAME:-rn-proxyip-tester}"
PORT="${PORT:-8788}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 root 执行: sudo bash install.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip ca-certificates openssl

mkdir -p "$APP_DIR"
cp -a app.py requirements.txt static "$APP_DIR"/
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ -f "/etc/${SERVICE_NAME}.env" ]; then
  echo "保留现有 /etc/${SERVICE_NAME}.env"
else
  TOKEN="$(openssl rand -hex 24)"
  cat > "/etc/${SERVICE_NAME}.env" <<EOF
PROXY_TESTER_TOKEN=${TOKEN}
BIND_HOST=127.0.0.1
PORT=${PORT}
CHECK_CONCURRENCY=50
SPEED_CONCURRENCY=4
PROBE_TIMEOUT=7
SPEED_BYTES=5242880
SPEED_REPEATS=3
MAX_TARGETS=5000
EOF
  chmod 600 "/etc/${SERVICE_NAME}.env"
  echo "已生成 API Token: ${TOKEN}"
fi

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=RN ProxyIP Tester
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=/etc/${SERVICE_NAME}.env
ExecStart=/bin/bash -lc 'exec ${APP_DIR}/.venv/bin/uvicorn app:app --host "\${BIND_HOST:-127.0.0.1}" --port "\${PORT:-8788}"'
Restart=always
RestartSec=3
User=root
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
sleep 1
systemctl --no-pager --full status "$SERVICE_NAME" || true

echo
echo "本机检测地址: http://127.0.0.1:${PORT}/health"
echo "查看 Token: sudo cat /etc/${SERVICE_NAME}.env"
echo "推荐先用 SSH 隧道访问：ssh -L ${PORT}:127.0.0.1:${PORT} root@你的RN"
