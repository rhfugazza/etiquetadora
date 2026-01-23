FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV QUEUE_FILE=/data/queue
ENV PRINT_QUEUE_FILE=/data/print_queue
ENV INFLIGHT_FILE=/data/inflight
ENV LOG_FILE=/data/print_log
RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
