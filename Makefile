# ─── Makefile ─────────────────────────────────────────────────────────────────
# make install      → dependencies install karo
# make run          → server locally start karo
# make test         → tests chalaao (server must be running)
# make benchmark    → latency metrics chalaao
# make docker-build → Docker image banao
# make docker-run   → Docker container start karo
# make docker-stop  → container band karo
# make clean        → cache/temp files hataao
# ──────────────────────────────────────────────────────────────────────────────

IMAGE_NAME  = kvcache
SERVER_PORT = 7171
PYTHON      = python3

.PHONY: install run test benchmark docker-build docker-run docker-stop clean help

help:
	@echo ""
	@echo "  In-Memory KV Cache — Available Commands"
	@echo "  ──────────────────────────────────────────"
	@echo "  make install       Install Python dependencies"
	@echo "  make run           Start server locally (port $(SERVER_PORT))"
	@echo "  make test          Run test suite (server must be running)"
	@echo "  make benchmark     Run latency benchmark (server must be running)"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Build + run in Docker"
	@echo "  make docker-stop   Stop running container"
	@echo "  make clean         Remove cache and temp files"
	@echo ""

install:
	@echo "→ Installing dependencies..."
	pip install -r requirements.txt

run:
	@echo "→ Starting server on http://localhost:$(SERVER_PORT)"
	$(PYTHON) server.py

test:
	@echo "→ Running tests..."
	$(PYTHON) test_server.py

benchmark:
	@echo "→ Running benchmark..."
	$(PYTHON) metrics.py

docker-build:
	@echo "→ Building Docker image '$(IMAGE_NAME)'..."
	docker build -t $(IMAGE_NAME) .

docker-run: docker-build
	@echo "→ Starting container on http://localhost:$(SERVER_PORT)"
	docker run --rm -p $(SERVER_PORT):$(SERVER_PORT) --name $(IMAGE_NAME) $(IMAGE_NAME)

docker-stop:
	@echo "→ Stopping container..."
	docker stop $(IMAGE_NAME) || true

clean:
	@echo "→ Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "   Done."