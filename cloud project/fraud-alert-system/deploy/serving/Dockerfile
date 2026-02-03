FROM python:3.9-slim


WORKDIR /app

# Install system deps for common Python packages
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc && rm -rf /var/lib/apt/lists/*

# Copy the serving-specific requirements from the repository root build context
# (when the build context is the project root). This ensures we install the
# correct deps (uvicorn/fastapi) instead of any top-level requirements.txt.
COPY ./deploy/serving/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy serving application and model files into the image
# Use the deploy/serving folder from the build context.
COPY ./deploy/serving /app

# Expose port used by Vertex prediction container
ENV PORT=8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
FROM python:3.9-slim

WORKDIR /app

# Install system deps for common Python packages
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and model
COPY . /app

# Expose port used by Vertex prediction container
ENV PORT=8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
