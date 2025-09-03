# Backend Dockerfile (Python)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y supervisor
COPY . .
# Ensure log directory exists for api.log
RUN mkdir -p /app
EXPOSE 8000
CMD ["supervisord", "-c", "/app/supervisord.conf"]
