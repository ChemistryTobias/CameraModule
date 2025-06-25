# 1) Base image
FROM python:3.11.2-slim-bookworm

# 2) Install OS packages (all pinned)
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libcamera-apps=1.7.0+git5a3f5965aca9-1 \
      libcamera-dev=0.5.0+rpt20250429-1 \
      python3-libcamera=0.5.0+rpt20250429-1 \
      python3-picamera2=0.3.27-1 \
      cron=3.0pl1-162 \
    && rm -rf /var/lib/apt/lists/*

# 3) Pin PyPI packages
RUN pip install --no-cache-dir \
      av==12.3.0 \
      picamera2==0.3.27

# 4) Copy server & client code
WORKDIR /opt/camera
COPY server/    /opt/camera/server/
RUN chmod +x /opt/camera/server/camera_server.py

# 5) Configure @reboot cron job for camera_server.py
RUN printf "PATH=/usr/local/bin:/usr/bin:/bin\n" \
     > /etc/cron.d/camera_server && \
    printf "@reboot root python3 /opt/camera/server/camera_server.py >> /var/log/camera_server.log 2>&1\n" \
     >> /etc/cron.d/camera_server && \
    chmod 0644 /etc/cron.d/camera_server && \
    crontab /etc/cron.d/camera_server && \
    touch /var/log/camera_server.log

# 6) Run cron in foreground
CMD ["cron", "-f"]