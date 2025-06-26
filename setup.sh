#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/ChemistryTobias/CameraModule.git"
TARGET="/opt/CameraModule"
CRON_FILE="/etc/cron.d/camera_module"

# 1) Ensure git is available (no other packages will be installed)
if ! command -v git &>/dev/null; then
  echo "Installing git…"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y git
fi

# 3) Installing the Picamera2 Library (if not already available)
if ! python3 - <<<'import picamera2' &>/dev/null; then
  echo "Installing python3-picamera2…"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3-picamera2
fi

# 3) Clone or update the repo
if [ -d "$TARGET/.git" ]; then
  echo "Updating CameraModule…"
  git -C "$TARGET" pull
else
  echo "Cloning CameraModule to $TARGET…"
  git clone "$REPO_URL" "$TARGET"
fi

# 4) Create host-level @reboot cron job
echo "Installing @reboot cron job…"
cat > "$CRON_FILE" <<EOF
# Run camera_server.py at boot
@reboot root cd $TARGET/server && /usr/bin/python3 camera_server.py >> $TARGET/server.log 2>&1
EOF
chmod 0644 "$CRON_FILE"

echo "✅ Camera server successfully initiated or updated."