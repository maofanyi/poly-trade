FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir fastapi 'uvicorn[standard]' polymarket-paper-trader

# Copy application code (excluding what's in .dockerignore)
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose dashboard port
EXPOSE 8766

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8766/api/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8766"]
