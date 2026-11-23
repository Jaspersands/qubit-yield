PYTHON ?= python

.PHONY: setup test lint frontend reproduce serve check

setup:
	$(PYTHON) -m pip install -e '.[dev,research]'
	cd web && npm ci

test:
	$(PYTHON) -m pytest
	cd web && npm test

lint:
	$(PYTHON) -m ruff check src tests scripts

frontend:
	cd web && npm run build

reproduce:
	$(PYTHON) -m qubityield.cli reproduce
	$(PYTHON) scripts/validate_qiskit.py
	$(PYTHON) scripts/execute_notebook.py
	cd web && npm run build
	cd web && npm run build:preview
	cd web && npm run test:preview
	$(PYTHON) scripts/build_manifest.py
	$(PYTHON) -m qubityield.cli verify-manifest

serve: frontend
	$(PYTHON) -m qubityield.cli serve

check: lint test frontend

