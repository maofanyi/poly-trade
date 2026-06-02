FROM python:3.11-slim

WORKDIR /app

# Install pm-trader
RUN pip install --no-cache-dir polymarket-paper-trader

# Copy scripts
COPY copy_trader.py .
COPY copy_dashboard.html .

# Persistent state volume
VOLUME ["/app/data"]

# Expose dashboard port
EXPOSE 8766

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8766/copy_trader_state.json')" || exit 1

# Run monitor with dashboard, scan every 5 minutes
CMD ["python", "copy_trader.py", "--interval", "300"]
