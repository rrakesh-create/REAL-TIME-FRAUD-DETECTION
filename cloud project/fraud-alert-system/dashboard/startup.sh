#!/bin/sh
# Startup wrapper to set Streamlit config from the runtime PORT
PORT=${PORT:-8080}
export STREAMLIT_SERVER_PORT=$PORT
export STREAMLIT_SERVER_ADDRESS="0.0.0.0"
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_SERVER_ENABLECORS=false

echo "Starting Streamlit on port $PORT"
exec streamlit run app.py --server.port $PORT --server.address 0.0.0.0
