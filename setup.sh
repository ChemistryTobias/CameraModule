#!/usr/bin/env bash
set -e

# 1) Install Docker
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
fi

# 2) Install Docker Compose
if ! command -v docker-compose &>/dev/null; then
  sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
fi

# 3) Clone CameraModule repo
TARGET="/opt/CAMERAMODULE"
if [ -d "$TARGET/.git" ]; then
  git -C "$TARGET" pull
else
  sudo git clone https://github.com/ChemistryTobias/CameraModule.git "$TARGET"
fi

cd "$TARGET"

# 4) Build & start
docker compose up -d --build

echo "Camera server set-up completed! It will restart on reboot."