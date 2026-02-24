FROM python:3.11-slim

WORKDIR /app

# Copy shared schemas first (required by worker)
COPY shared/ ./shared/

# Copy worker source
COPY worker/requirements.txt ./worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt

COPY worker/ ./worker/

# Make packages importable
ENV PYTHONPATH=/app

CMD ["python", "-m", "worker.app.worker"]
