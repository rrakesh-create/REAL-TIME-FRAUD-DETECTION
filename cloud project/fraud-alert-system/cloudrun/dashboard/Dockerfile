FROM python:3.10-slim
WORKDIR /app
# Use requirements copied into this build context (cloudrun/dashboard)
COPY ./requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
# Copy the dashboard app files that are now inside this context
COPY ./app.py /app/app.py
ENV PORT=8080
EXPOSE 8080
# Streamlit needs the server.port and server.address env, use --server.headless true
CMD ["streamlit", "run", "app.py", "--server.port", "8080", "--server.address", "0.0.0.0", "--server.headless", "true"]
