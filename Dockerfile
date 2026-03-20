FROM python:3.12-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY co2monitor.py /app/co2monitor.py

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
  CMD test -f /tmp/heartbeat && test $(( $(date +%s) - $(date +%s -r /tmp/heartbeat) )) -lt 300

ENTRYPOINT ["python3", "/app/app.py"]
