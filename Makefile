.PHONY: install dev test build

# Python interpreter used to create the backend venv. Override for a specific
# version, e.g. `make install PYTHON=python3.12`. macOS has no bare `python`.
PYTHON ?= python3

install:
	cd backend && $(PYTHON) -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

dev:
	./scripts/dev.sh

test:
	cd backend && . .venv/bin/activate && pytest -q

build:
	cd frontend && npm run build
