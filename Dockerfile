# Dockerfile
# ─────────────────────────────────────────────────────────────
# 1) Base image: Python 3.11 on Debian Bookworm slim
FROM python:3.11-slim-bookworm

# ─────────────────────────────────────────────────────────────
# 2) Install tools to fetch & trust the Raspberry Pi archive key
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      wget \
      gnupg \
      ca-certificates && \
    mkdir -p /usr/share/keyrings && \
    wget -qO- http://archive.raspberrypi.org/debian/raspberrypi.gpg.key \
      | gpg --dearmor > /usr/share/keyrings/raspberrypi-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] \
      http://archive.raspberrypi.org/debian bookworm main" \
      > /etc/apt/sources.list.d/raspi.list && \
    rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────
# 3) Install libcamera, picamera2 & Python bindings, plus cron if you need it on host
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libcamera-apps \
      libcamera-dev \
      python3-libcamera \
      python3-picamera2 && \
    rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────
# 4) Install any PyPI dependencies (e.g. PyAV)
RUN pip install --no-cache-dir \
      av==12.3.0

# ─────────────────────────────────────────────────────────────
# 5) Copy your server and client code
WORKDIR /opt/camera
COPY server/ /opt/camera/server/
COPY client/ /opt/camera/client/
RUN chmod +x /opt/camera/server/camera_server.py

# ─────────────────────────────────────────────────────────────
# 6) Run your server directly (no in-container cron)
CMD ["python3", "/opt/camera/server/camera_server.py"]