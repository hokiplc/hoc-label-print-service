#!/usr/bin/env bash
# Install hoc-label-print-service on Raspberry Pi OS.
# Run as: sudo ./deploy/install.sh
set -euo pipefail

APP_DIR=/opt/hoc-label-print
DATA_DIR=/var/lib/hoc-label-print
LOG_DIR=/var/log/hoc-label-print
SERVICE_USER=hoclabel
REPO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

echo "==> Installing OS packages"
apt-get update
apt-get install -y python3 python3-venv python3-pip libusb-1.0-0 udev

echo "==> Creating service user"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi
usermod -aG plugdev "$SERVICE_USER" || true

echo "==> Copying application to $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude '.git' "$REPO_SRC"/ "$APP_DIR"/

echo "==> Creating data/log directories"
mkdir -p "$DATA_DIR/previews" "$LOG_DIR"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR" "$DATA_DIR" "$LOG_DIR"

echo "==> Creating Python virtualenv"
sudo -u "$SERVICE_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "==> Creating .env from .env.example (EDIT THIS BEFORE STARTING)"
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  sed -i "s#HOC_PREVIEW_DIR=.*#HOC_PREVIEW_DIR=$DATA_DIR/previews#" "$APP_DIR/.env"
  sed -i "s#HOC_LOG_DIR=.*#HOC_LOG_DIR=$LOG_DIR#" "$APP_DIR/.env"
  sed -i "s#HOC_DB_PATH=.*#HOC_DB_PATH=$DATA_DIR/jobs.db#" "$APP_DIR/.env"
  sed -i "s#HOC_FONT_DIR=.*#HOC_FONT_DIR=$APP_DIR/fonts#" "$APP_DIR/.env"
  chown "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR/.env"
fi

echo "==> Installing udev rule for USB printer access"
cp "$APP_DIR/deploy/99-brother-ql700.rules" /etc/udev/rules.d/99-brother-ql700.rules
udevadm control --reload-rules
udevadm trigger

echo "==> Installing systemd unit"
cp "$APP_DIR/deploy/hoc-label-print.service" /etc/systemd/system/hoc-label-print.service
systemctl daemon-reload
systemctl enable hoc-label-print.service

cat <<'EOF'

==> Install complete.

Next steps:
  1. Edit /opt/hoc-label-print/.env and set HOC_API_KEY and HOC_ALLOWED_CIDRS.
  2. Place DejaVuSans.ttf and DejaVuSans-Bold.ttf into /opt/hoc-label-print/fonts/
     (Debian package: apt-get install -y fonts-dejavu-core, then symlink/copy from
     /usr/share/fonts/truetype/dejavu/).
  3. Plug in the Brother QL-700 over USB and load 62mm continuous label media.
  4. Reboot or re-login so the 'plugdev' group membership takes effect.
  5. Start the service:   systemctl start hoc-label-print
  6. Check status:        systemctl status hoc-label-print
  7. Run diagnostics:     sudo -u hoclabel /opt/hoc-label-print/.venv/bin/python -m scripts.diagnostics

EOF
