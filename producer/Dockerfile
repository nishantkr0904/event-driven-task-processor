FROM python:3.11-slim

WORKDIR /app

# Copy shared schemas first (required by producer)
COPY shared/ ./shared/

# Copy producer source
COPY producer/requirements.txt ./producer/requirements.txt
RUN pip install --no-cache-dir -r producer/requirements.txt

COPY producer/ ./producer/

# Make packages importable
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "producer.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
