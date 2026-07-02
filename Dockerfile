# Build:  docker build -t kvcache .
# Run:    docker run -p 7171:7171 kvcache

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py config.py models.py .
COPY cache/ ./cache/

EXPOSE 7171

CMD ["python", "server.py"]