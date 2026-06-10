# ─── Makefile ─────────────────────────────────────────────────────────────────
# Commonly used commands — shortcuts taaki baar baar long commands na likhne padein.
#
# Usage:
#   make install     → dependencies install karo
#   make run         → server locally start karo
#   make test        → tests chalaao
#   make docker-build → Docker image banao
#   make docker-run  → Docker container start karo
#   make clean       → cache/temp files hataao
# ──────────────────────────────────────────────────────────────────────────────

# Variables
IMAGE_NAME  = kvcache
SERVER_PORT = 7171
PYTHON      = python3

.PHONY: install run test docker-build docker-run docker-stop clean help


# ── Default: help dikhao ──────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  In-Memory KV Cache — Available Commands"
	@echo "  ──────────────────────────────────────────"
	@echo "  make install       Install Python dependencies"
	@echo "  make run           Start server locally (port $(SERVER_PORT))"
	@echo "  make test          Run test suite (server must be running)"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Run server in Docker container"
	@echo "  make docker-stop   Stop running Docker container"
	@echo "  make clean         Remove cache and temp files"
	@echo ""


# ── Local Development ─────────────────────────────────────────────────────────

install:
	@echo "→ Installing dependencies..."
	pip install -r requirements.txt

run:
	@echo "→ Starting server on http://localhost:$(SERVER_PORT)"
	@echo "   Press Ctrl+C to stop."
	$(PYTHON) server.py

test:
	@echo "→ Running tests (make sure server is running first)..."
	$(PYTHON) test_server.py


# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	@echo "→ Building Docker image '$(IMAGE_NAME)'..."
	docker build -t $(IMAGE_NAME) .

docker-run: docker-build
	@echo "→ Starting container on http://localhost:$(SERVER_PORT)"
	docker run --rm -p $(SERVER_PORT):$(SERVER_PORT) --name $(IMAGE_NAME) $(IMAGE_NAME)

docker-stop:
	@echo "→ Stopping container '$(IMAGE_NAME)'..."
	docker stop $(IMAGE_NAME) || true


# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	@echo "→ Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "   Done."