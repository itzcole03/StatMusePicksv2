FROM python:3.11-slim

WORKDIR /app

# Install build deps (if needed) and cleanup to keep image small
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV PYTHONPATH=/app
EXPOSE 3002

CMD ["/usr/local/bin/python", "-m", "uvicorn", "fastapi_nba:app", "--host", "0.0.0.0", "--port", "3002"]
