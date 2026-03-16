FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY co2monitor.py /app/co2monitor.py

ENTRYPOINT ["python3", "/app/app.py"]
