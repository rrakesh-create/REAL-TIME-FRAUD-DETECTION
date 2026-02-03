FROM python:3.10-slim
WORKDIR /app
# Use local requirements in the build context
COPY ./requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
# Copy the generator app into the image
COPY ./generator.py /app/generator.py
ENV PORT=8080
EXPOSE 8080
# Use gunicorn to serve the Flask app; the generator module defines `app`
CMD ["gunicorn", "-b", ":8080", "generator:app"]
