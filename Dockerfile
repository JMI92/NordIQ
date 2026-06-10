FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2, cryptography, lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps before copying source — layer is cached unless requirements change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Non-root user for security
RUN adduser --disabled-password --gecos "" nordiq \
    && mkdir -p /app/reports /tmp/nordiq_reports \
    && chown -R nordiq:nordiq /app /tmp/nordiq_reports

USER nordiq

# Default: API with migrations (overridden in docker-compose for frontend)
ENTRYPOINT ["scripts/entrypoint.sh"]
