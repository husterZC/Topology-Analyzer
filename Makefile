.PHONY: help install install-dev test booksim-apply-overlay booksim-build clean-runs clean-build clean

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
BOOKSIM_DIR ?=

help:
	@echo "Topology-Analyzer make targets"
	@echo ""
	@echo "  make install      Install package in editable mode"
	@echo "  make install-dev  Same as install; kept for explicit dev workflow"
	@echo "  make test         Run unit tests"
	@echo "  make booksim-apply-overlay BOOKSIM_DIR=/path/to/booksim2"
	@echo "                   Apply Topology-Analyzer's anynet route-table overlay"
	@echo "  make booksim-build BOOKSIM_DIR=/path/to/booksim2"
	@echo "                   Build BookSim after applying the overlay"
	@echo "  make clean-runs   Remove generated benchmark run outputs under ./runs"
	@echo "  make clean-build  Remove Python build/cache artifacts"
	@echo "  make clean        Run clean-runs and clean-build"
	@echo ""
	@echo "Variables:"
	@echo "  PYTHON=python3    Python interpreter to use"
	@echo "  BOOKSIM_DIR=...   BookSim2 checkout for overlay/build targets"

install:
	$(PIP) install -e .

install-dev: install

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests

booksim-apply-overlay:
	@test -n "$(BOOKSIM_DIR)" || (echo "Set BOOKSIM_DIR=/path/to/booksim2" && exit 1)
	patch -p1 -d "$(BOOKSIM_DIR)" < booksim_overlays/booksim2/table_anynet.patch

booksim-build:
	@test -n "$(BOOKSIM_DIR)" || (echo "Set BOOKSIM_DIR=/path/to/booksim2" && exit 1)
	$(MAKE) -C "$(BOOKSIM_DIR)/src"

clean-runs:
	rm -rf runs
	mkdir -p runs

clean-build:
	rm -rf build dist *.egg-info src/*.egg-info src/topoanalyzer.egg-info
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -prune -exec rm -rf {} +
	find . -type d -name '.mypy_cache' -prune -exec rm -rf {} +
	find . -type d -name '.ruff_cache' -prune -exec rm -rf {} +

clean: clean-runs clean-build
