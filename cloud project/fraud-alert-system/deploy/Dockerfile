FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir numpy==1.23.5 -r requirements.txt

COPY . .

ENV AIP_MODEL_DIR="/app/model"

EXPOSE 8080

ENTRYPOINT ["python", "main.py"]