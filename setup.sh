#!/usr/bin/env bash
# setup.sh — install Docker, clone repo, deploy & add host cron
set -e

# 1) Install Docker if missing
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
fi

# 2) Install Docker Compose if missing
if ! command -v docker-compose &>/dev/null; then
  sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
fi

# 3) Clone or update the repo
TARGET="/opt/CAMERAMODULE"
if [ -d "$TARGET/.git" ]; then
  git -C "$TARGET" pull
else
  sudo git clone https://github.com/ChemistryTobias/CameraModule.git "$TARGET"
fi

cd "$TARGET"

# 4) Build and start the container
docker-compose up -d --build

# 5) Add HOST-level @reboot cron to restart Compose stack
CRON_FILE="/etc/cron.d/start_cameramodule"
sudo tee "$CRON_FILE" >/dev/null <<EOF
# Restart CameraModule on reboot
@reboot root cd $TARGET && /usr/bin/docker-compose up -d
EOF
sudo chmod 0644 "$CRON_FILE"

echo "Setup complete. Container will auto-restart on Pi reboot."