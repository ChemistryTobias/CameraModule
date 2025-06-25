# ────────────────────────────────────────────────────────
# 1) Base image: use the existing slim-bookworm tag
# ────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

# ────────────────────────────────────────────────────────
# 2) Add the Raspberry Pi OS repository (so we can install
#    libcamera-apps, picamera2, etc.)
# ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
      wget \
      ca-certificates \
    && wget -O - http://archive.raspberrypi.org/debian/raspberrypi.gpg.key \
         | apt-key add - \
    && echo "deb http://archive.raspberrypi.org/debian bookworm main" \
         > /etc/apt/sources.list.d/raspi.list \
    && apt-get update

# ────────────────────────────────────────────────────────
# 3) Install all OS-level deps (now available from the Pi OS repo)
# ────────────────────────────────────────────────────────
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libcamera-apps \
      libcamera-dev \
      python3-libcamera \
      python3-picamera2 \
      cron \
    && rm -rf /var/lib/apt/lists/*

# ────────────────────────────────────────────────────────
# 4) Pin PyPI deps
# ────────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
      av==12.3.0 \
      picamera2==0.3.27

# ────────────────────────────────────────────────────────
# 5) Copy your code into the container
# ────────────────────────────────────────────────────────
WORKDIR /opt/camera
COPY server/camera_server.py server/
COPY client/camera_driver.py client/
RUN chmod +x server/camera_server.py

# ────────────────────────────────────────────────────────
# 6) Configure @reboot cron job for the server
# ────────────────────────────────────────────────────────
RUN printf "PATH=/usr/local/bin:/usr/bin:/bin\n" \
       > /etc/cron.d/camera_server \
 && printf "@reboot root python3 /opt/camera/server/camera_server.py >> /var/log/camera_server.log 2>&1\n" \
       >> /etc/cron.d/camera_server \
 && chmod 0644 /etc/cron.d/camera_server \
 && crontab /etc/cron.d/camera_server \
 && touch /var/log/camera_server.log

# ────────────────────────────────────────────────────────
# 7) Run cron in foreground so Docker keeps the container alive
# ────────────────────────────────────────────────────────
CMD ["cron", "-f"]
