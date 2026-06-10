# ─── Dockerfile ───────────────────────────────────────────────────────────────
# Yeh file Docker image banati hai taaki server kisi bhi machine pe
# bina setup ke run ho sake.
#
# Build:  docker build -t kvcache .
# Run:    docker run -p 7171:7171 kvcache
# ──────────────────────────────────────────────────────────────────────────────

# Base image — Python 3.12, slim = choti size
FROM python:3.12-slim

# Container ke andar working directory set karo
WORKDIR /app

# Pehle sirf requirements copy karo (Docker cache optimization)
# Agar code badla but requirements nahi — yeh step skip hoga
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ab baaki code copy karo
COPY server.py .

# Yeh port expose karta hai (sirf documentation ke liye)
EXPOSE 7171

# Container start hone pe yeh command chalegi
CMD ["python", "server.py"]