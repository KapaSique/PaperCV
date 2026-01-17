PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python; fi)
FRONTEND_DIR := frontend

.PHONY: dev backend frontend test lint install

install:
	$(PYTHON) -m pip install -r requirements.txt
	cd $(FRONTEND_DIR) && npm install

backend:
	PYTHONPATH=. $(PYTHON) -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd $(FRONTEND_DIR) && npm install && npm run dev -- --host

dev:
	PYTHONPATH=. $(PYTHON) -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 & \
	cd $(FRONTEND_DIR) && npm install && npm run dev -- --host

test:
	PYTHONPATH=. pytest -q

lint:
	ruff backend cv
	cd $(FRONTEND_DIR) && npm run lint
