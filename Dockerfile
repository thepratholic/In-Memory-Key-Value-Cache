# ---- build stage ----
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage ----
FROM python:3.12-slim

# Non-root user for security
RUN useradd -r -s /bin/false appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY server.py .

USER appuser

EXPOSE 7171

CMD ["python", "server.py"]
