FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project (backend needs project root for imports)
COPY . .

# Expose the port Cloud Run will use
EXPOSE 8080

# Cloud Run sets PORT env var; uvicorn binds to it
CMD ["python", "-m", "uvicorn", "Backend.app:app", "--host", "0.0.0.0", "--port", "8080"]
