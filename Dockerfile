FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.in ./
RUN pip install --no-cache-dir -r requirements.in

COPY . .

CMD ["fastapi", "dev", "home_content_store/app.py", "--host", "0.0.0.0", "--port", "8000"]
