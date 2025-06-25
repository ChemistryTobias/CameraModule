# 1) Base image — Python 3.11 on Debian Bookworm
FROM python:3.11-slim-bookworm

# 2) Install wget + ca-certs, then add the Pi OS key & repo
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      wget \
      ca-certificates \
    && mkdir -p /usr/share/keyrings \
    # fetch the Raspberry Pi GPG key directly into our keyring
    && wget -qO /usr/share/keyrings/raspberrypi-archive-keyring.gpg \
         http://archive.raspberrypi.org/debian/raspberrypi.gpg.key \
    # create a sources.list entry that uses that key
    && echo "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] \
         http://archive.raspberrypi.org/debian bookworm main" \
         > /etc/apt/sources.list.d/raspi.list \
    && apt-get update

# 3) Install the camera packages & cron
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libcamera-apps \
      libcamera-dev \
      python3-libcamera \
      python3-picamera2 \
      cron \
    && rm -rf /var/lib/apt/lists/*

# 4) Pin PyPI deps
RUN pip install --no-cache-dir \
      av==12.3.0 \
      picamera2==0.3.27

# 5) Copy code
WORKDIR /opt/camera
COPY server/ /opt/camera/server/
COPY client/ /opt/camera/client/
RUN chmod +x /opt/camera/server/camera_server.py

# 6) @reboot cron job
RUN printf "PATH=/usr/local/bin:/usr/bin:/bin\n" \
       > /etc/cron.d/camera_server \
 && printf "@reboot root python3 /opt/camera/server/camera_server.py >> /var/log/camera_server.log 2>&1\n" \
       >> /etc/cron.d/camera_server \
 && chmod 0644 /etc/cron.d/camera_server \
 && crontab /etc/cron.d/camera_server \
 && touch /var/log/camera_server.log

# 7) Foreground cron
CMD ["cron", "-f"]