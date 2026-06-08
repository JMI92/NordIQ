FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2, cryptography, lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Alembic migrations then start the API
CMD ["sh", "-c", "alembic upgrade head && uvicorn nordiq.api.main:app --host 0.0.0.0 --port 8000"]
