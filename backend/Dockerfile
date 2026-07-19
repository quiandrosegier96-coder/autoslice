FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# v2 — force rebuild
COPY . .

# Create temp upload directory
RUN mkdir -p /app/temp

# SQLite database is stored in a volume
VOLUME ["/data"]

ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/autoslice.db

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
