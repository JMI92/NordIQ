#!/bin/sh
# Frontend container entrypoint — starts Streamlit.
set -e

echo "[entrypoint] Starting Streamlit frontend…"
exec streamlit run nordiq/frontend/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
