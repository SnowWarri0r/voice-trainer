.PHONY: install dev test build

install:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

dev:
	./scripts/dev.sh

test:
	cd backend && . .venv/bin/activate && pytest -q

build:
	cd frontend && npm run build
