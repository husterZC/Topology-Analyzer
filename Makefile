.PHONY: help bootstrap python-env install install-dev test booksim-fetch booksim-apply-overlay booksim-build booksim-link clean-runs clean-build clean

BOOTSTRAP_PYTHON ?= python3
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip
PIP_CACHE_DIR ?= .cache/pip
BOOKSIM_REPO ?= https://github.com/booksim/booksim2.git
BOOKSIM_DIR ?= external/booksim2
BOOKSIM_BIN ?= $(BOOKSIM_DIR)/src/booksim
LOCAL_BIN_DIR ?= bin
LOCAL_BOOKSIM ?= $(LOCAL_BIN_DIR)/booksim
VENV_BOOKSIM ?= $(VENV)/bin/booksim

help:
	@echo "Topology-Analyzer make targets"
	@echo ""
	@echo "  make bootstrap    Create .venv, install Python package, clone/build BookSim"
	@echo "  make python-env   Create repo-local Python virtual environment"
	@echo "  make install      Install package in editable mode into .venv"
	@echo "  make install-dev  Same as install; kept for explicit dev workflow"
	@echo "  make test         Run unit tests"
	@echo "  make booksim-fetch"
	@echo "                   Clone BookSim2 into external/booksim2 if needed"
	@echo "  make booksim-apply-overlay"
	@echo "                   Apply Topology-Analyzer's anynet route-table overlay"
	@echo "  make booksim-build"
	@echo "                   Build BookSim after applying the overlay"
	@echo "  make booksim-link"
	@echo "                   Link BookSim into .venv/bin/booksim and bin/booksim"
	@echo "  make clean-runs   Remove generated benchmark run outputs under ./runs"
	@echo "  make clean-build  Remove Python build/cache artifacts"
	@echo "  make clean        Run clean-runs and clean-build"
	@echo ""
	@echo "Variables:"
	@echo "  BOOTSTRAP_PYTHON=python3  Host Python used to create .venv"
	@echo "  VENV=.venv                Virtual environment directory"
	@echo "  PIP_CACHE_DIR=.cache/pip  Repo-local pip cache"
	@echo "  BOOKSIM_REPO=...          BookSim2 git URL"
	@echo "  BOOKSIM_DIR=...           BookSim2 checkout/build directory"

bootstrap: install-dev booksim-link
	@echo ""
	@echo "Bootstrap complete."
	@echo "Activate Python env with:"
	@echo "  source $(VENV)/bin/activate"
	@echo "BookSim binary links:"
	@echo "  $(VENV_BOOKSIM)"
	@echo "  $(LOCAL_BOOKSIM)"

python-env:
	@test -x "$(PYTHON)" || "$(BOOTSTRAP_PYTHON)" -m venv "$(VENV)"
	PIP_CACHE_DIR="$(PIP_CACHE_DIR)" $(PIP) install --upgrade pip setuptools wheel

install: python-env
	PIP_CACHE_DIR="$(PIP_CACHE_DIR)" $(PIP) install -e .

install-dev: install

test: install-dev
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests

booksim-fetch:
	@mkdir -p "$(dir $(BOOKSIM_DIR))"
	@if [ -d "$(BOOKSIM_DIR)" ]; then \
		echo "Using existing BookSim checkout: $(BOOKSIM_DIR)"; \
	else \
		git clone "$(BOOKSIM_REPO)" "$(BOOKSIM_DIR)"; \
	fi

booksim-apply-overlay: booksim-fetch
	@test -f "$(BOOKSIM_DIR)/src/booksim_config.cpp" || (echo "Invalid BOOKSIM_DIR: $(BOOKSIM_DIR)" && exit 1)
	@if grep -q "route_table_file" "$(BOOKSIM_DIR)/src/booksim_config.cpp"; then \
		echo "BookSim anynet route-table overlay already applied"; \
	else \
		patch -p1 -d "$(BOOKSIM_DIR)" < booksim_overlays/booksim2/table_anynet.patch; \
	fi

booksim-build: booksim-apply-overlay
	$(MAKE) -C "$(BOOKSIM_DIR)/src"

booksim-link: python-env booksim-build
	@test -x "$(BOOKSIM_BIN)" || (echo "BookSim binary not found: $(BOOKSIM_BIN)" && exit 1)
	mkdir -p "$(LOCAL_BIN_DIR)" "$(VENV)/bin"
	ln -sf "$(abspath $(BOOKSIM_BIN))" "$(LOCAL_BOOKSIM)"
	ln -sf "$(abspath $(BOOKSIM_BIN))" "$(VENV_BOOKSIM)"

clean-runs:
	rm -rf runs
	mkdir -p runs

clean-build:
	rm -rf build dist *.egg-info src/*.egg-info src/topoanalyzer.egg-info "$(LOCAL_BOOKSIM)" "$(PIP_CACHE_DIR)"
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -prune -exec rm -rf {} +
	find . -type d -name '.mypy_cache' -prune -exec rm -rf {} +
	find . -type d -name '.ruff_cache' -prune -exec rm -rf {} +

clean: clean-runs clean-build
