# BioNano-Sim developer commands.
#
# Works on Windows (Git Bash / MSYS), Linux and macOS. On Windows the venv's
# interpreter lives in Scripts/ rather than bin/, so PY is resolved per-OS.

SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV := backend/.venv
ifeq ($(OS),Windows_NT)
  PY := $(VENV)/Scripts/python.exe
else
  PY := $(VENV)/bin/python
endif

.PHONY: help setup setup-backend setup-frontend backend frontend test test-backend \
        test-frontend validate validate-env validate-model demo precomputed lint \
        typecheck build clean clean-all

help: ## Show this help
	@echo "BioNano-Sim — available commands"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "First run:  make setup && make validate"
	@echo "Then, in two terminals:  make backend   |   make frontend"

# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #
setup: setup-backend setup-frontend ## Install everything and fetch local data
	@echo
	@echo "Setup complete. Next: make validate"

setup-backend: ## Create the Python 3.11 venv and install backend dependencies
	@echo "==> Creating $(VENV) with Python 3.11"
	@# uv is fastest and can install the interpreter itself; fall back to the
	@# system python3.11 if uv is unavailable.
	@if command -v uv >/dev/null 2>&1; then \
		uv python install 3.11 && uv venv $(VENV) --python 3.11 && \
		uv pip install --python $(PY) -r backend/requirements-dev.txt; \
	else \
		python3.11 -m venv $(VENV) && \
		$(PY) -m pip install --upgrade pip && \
		$(PY) -m pip install -r backend/requirements-dev.txt; \
	fi
	@echo "==> Fetching protein structures and generating derived data"
	@$(PY) scripts/setup_local.py

setup-frontend: ## Install frontend dependencies and vendor the 3D viewer
	@echo "==> npm install"
	@cd frontend && npm install
	@echo "==> Vendoring the 3Dmol viewer bundle"
	@$(PY) scripts/fetch_viewer.py

# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
backend: ## Run the API at http://localhost:8000 (docs at /docs)
	@cd backend && ../$(VENV)/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000 \
		2>/dev/null || cd backend && ../$(VENV)/bin/python -m uvicorn app.main:app --reload --port 8000

frontend: ## Run the dashboard at http://localhost:5173
	@cd frontend && npm run dev

# --------------------------------------------------------------------------- #
# Validate
# --------------------------------------------------------------------------- #
validate: validate-env validate-model validate-dataset ## Run every environment, model and dataset check

validate-env: ## Check interpreter, packages, OpenMM platforms and data files
	@$(PY) scripts/validate_environment.py

provenance: ## Build the reproducibility manifest (add RELEASE=1 to enforce)
	@$(PY) scripts/build_reproducibility_manifest.py $(if $(RELEASE),--release)

validate-dataset: ## Validate the real stiffness dataset and write its manifest
	@$(PY) scripts/validate_dataset.py

validate-model: ## Verify the ML bundle reproduces its published metrics
	@$(PY) scripts/validate_model.py

# --------------------------------------------------------------------------- #
# Test
# --------------------------------------------------------------------------- #
test: test-backend test-frontend ## Run all tests and checks

test-backend: ## Run the backend test suite (excludes slow OpenMM runs)
	@cd backend && ../$(VENV)/Scripts/python.exe -m pytest -q -m "not slow" \
		2>/dev/null || cd backend && ../$(VENV)/bin/python -m pytest -q -m "not slow"

test-backend-all: ## Run the backend suite including real OpenMM simulations
	@cd backend && ../$(VENV)/Scripts/python.exe -m pytest -q \
		2>/dev/null || cd backend && ../$(VENV)/bin/python -m pytest -q

test-frontend: typecheck lint ## Type-check and lint the frontend

typecheck: ## TypeScript type checking
	@cd frontend && npm run typecheck

lint: ## ESLint (zero warnings allowed)
	@cd frontend && npm run lint

build: ## Production frontend build
	@cd frontend && npm run build

# --------------------------------------------------------------------------- #
# Demo helpers
# --------------------------------------------------------------------------- #
demo: ## Run one simulation end-to-end without the HTTP layer
	@$(PY) scripts/run_demo_simulation.py

precomputed: ## Regenerate the labelled precomputed fallback result for 1UBQ
	@$(PY) scripts/run_demo_simulation.py --pdb-id 1UBQ --write-precomputed

# --------------------------------------------------------------------------- #
# Clean
# --------------------------------------------------------------------------- #
diagnostics: ## Print runtime diagnostics (redacted, safe to share)
	@$(PY) -c "import sys,json; sys.path.insert(0,'backend'); from app.core import diagnostics; print(json.dumps(diagnostics.collect(), indent=2, default=str))"

cleanup: ## Preview runtime cleanup (add APPLY=1 to actually delete)
	@$(PY) scripts/cleanup_runtime.py $(if $(APPLY),--apply)

clean: ## Delete generated jobs, uploads, reports and logs
	@$(PY) scripts/clean_runtime.py --yes

clean-all: clean ## Also delete the venv, node_modules and the frontend build
	@rm -rf $(VENV) frontend/node_modules frontend/dist
	@echo "Removed the virtual environment, node_modules and dist."
