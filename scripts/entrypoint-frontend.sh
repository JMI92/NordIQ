#!/bin/sh
# Frontend container entrypoint — starts Streamlit.
set -e

echo "[entrypoint] Starting Streamlit frontend…"
export PYTHONPATH=/app:${PYTHONPATH}
exec streamlit run uusio/frontend/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
