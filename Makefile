.PHONY: install run test docker-build docker-up docker-down smoke-test clean

PORT ?= 7171

install:
	pip install -r requirements.txt

run:
	python server.py

# Run with a single worker (useful for debugging)
run-dev:
	uvicorn server:app --host 0.0.0.0 --port $(PORT) --reload --log-level info

test:
	pytest test_server.py -v

docker-build:
	docker build -t kv-cache-python:latest .

docker-up:
	docker run -d \
		--name kv-cache-python \
		-p $(PORT):7171 \
		--ulimit nofile=1048576:1048576 \
		--restart=unless-stopped \
		kv-cache-python:latest

docker-down:
	docker stop kv-cache-python && docker rm kv-cache-python

smoke-test:
	@echo "==> PUT"
	curl -s -X POST http://localhost:$(PORT)/put \
		-H "Content-Type: application/json" \
		-d '{"key":"hello","value":"world"}' | python -m json.tool
	@echo "==> GET"
	curl -s "http://localhost:$(PORT)/get?key=hello" | python -m json.tool
	@echo "==> DELETE"
	curl -s -X DELETE "http://localhost:$(PORT)/delete?key=hello" | python -m json.tool
	@echo "==> STATS"
	curl -s "http://localhost:$(PORT)/stats" | python -m json.tool
	@echo "==> HEALTH"
	curl -s "http://localhost:$(PORT)/health" | python -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
