FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install minimal system packages useful for pip builds (kept small)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy function source
COPY . /app

# Use Functions Framework to serve the entrypoint
ENV PORT 8080
EXPOSE 8080
CMD ["functions-framework", "--target=fraud_checker", "--port=8080"]
FROM python:3.11-slim

# Install minimal system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy function source
COPY . /app

# Use Functions Framework to run the function
ENV PORT=8080
EXPOSE 8080

CMD ["functions-framework", "--target=fraud_checker", "--port=8080"]
