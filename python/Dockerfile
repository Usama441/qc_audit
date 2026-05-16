FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the Redis queue consumer
CMD ["python", "worker.py"]
