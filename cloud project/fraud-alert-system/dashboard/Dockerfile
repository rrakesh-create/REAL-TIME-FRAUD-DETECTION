FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

# Streamlit listens on $PORT; set default
ENV PORT=8080

EXPOSE 8080

# Run Streamlit on container start
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh
CMD ["/bin/sh", "/app/startup.sh"]
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

# Streamlit listens on $PORT; set default
ENV PORT=8080

EXPOSE 8080

# Run Streamlit on container start using startup.sh which reads $PORT at runtime
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh
CMD ["/bin/sh", "/app/startup.sh"]
