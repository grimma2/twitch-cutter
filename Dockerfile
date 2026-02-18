FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Run the pipeline (listens for webhooks / polls VODs, sends to Opus)
CMD ["python", "-u", "main.py"]
