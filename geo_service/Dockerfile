# ---------------------------- Build / Install dependencies ----------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools and common libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy source code
COPY . .

# ---------------------------- Runtime ----------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed dependencies
COPY --from=builder /install /usr/local
# Copy app source code
COPY --from=builder /app /app

EXPOSE 5000

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

CMD ["python", "api_proximity.py", "--host=0.0.0.0", "--port=5000"]