FROM node:20-alpine AS frontend-build

WORKDIR /app/print-queue-fairy

COPY print-queue-fairy/package.json print-queue-fairy/package-lock.json ./
RUN npm ci

COPY print-queue-fairy/ .

ARG VITE_N8N_WEBHOOK_BASE_URL
ENV VITE_N8N_WEBHOOK_BASE_URL=$VITE_N8N_WEBHOOK_BASE_URL

RUN npm run build

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV QUEUE_FILE=/data/queue
ENV PRINT_QUEUE_FILE=/data/print_queue
ENV INFLIGHT_FILE=/data/inflight
ENV LOG_FILE=/data/print_log
ENV FRONTEND_DIR=/app/frontend

RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY --from=frontend-build /app/print-queue-fairy/dist /app/frontend

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
