# 1) Base image
FROM python:3.11-slim-bookworm

# 2) Install minimal tools to fetch & import the Pi GPG key
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      wget \
      ca-certificates \
      gnupg \
    && rm -rf /var/lib/apt/lists/*

# 3) Import the Raspberry Pi archive key into a keyring and add the Pi repo
RUN mkdir -p /usr/share/keyrings && \
    wget -qO- http://archive.raspberrypi.org/debian/raspberrypi.gpg.key \
      | gpg --dearmor > /usr/share/keyrings/raspberrypi-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] \
      http://archive.raspberrypi.org/debian bookworm main" \
      > /etc/apt/sources.list.d/raspi.list

# 4) Install libcamera, picamera2, cron from the Pi OS repo
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libcamera-apps \
      libcamera-dev \
      python3-libcamera \
      python3-picamera2 \
      cron \
    && rm -rf /var/lib/apt/lists/*

# 5) Pin your PyPI deps
RUN pip install --no-cache-dir \
      av==12.3.0 \
      picamera2==0.3.27

# 6) Copy your code
WORKDIR /opt/camera
COPY server/ /opt/camera/server/
COPY client/ /opt/camera/client/
RUN chmod +x /opt/camera/server/camera_server.py

# 7) Configure @reboot cron job
RUN printf "PATH=/usr/local/bin:/usr/bin:/bin\n" \
       > /etc/cron.d/camera_server \
 && printf "@reboot root python3 /opt/camera/server/camera_server.py >> /var/log/camera_server.log 2>&1\n" \
       >> /etc/cron.d/camera_server \
 && chmod 0644 /etc/cron.d/camera_server \
 && crontab /etc/cron.d/camera_server \
 && touch /var/log/camera_server.log

# 8) Run cron in foreground
CMD ["cron", "-f"]