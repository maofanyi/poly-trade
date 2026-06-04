FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir fastapi 'uvicorn[standard]' polymarket-paper-trader websockets

# Copy application code (excluding what's in .dockerignore)
ARG CACHE_BUST=0
COPY . .

# Create data directories for SQLite and pm-trader (persisted via volume)
RUN mkdir -p /app/data/pm-trader

# Expose dashboard port
EXPOSE 8766

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8766/api/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8766"]
