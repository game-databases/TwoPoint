# Two Point Campus — reproducible extraction and verification entrypoint.
SHELL := /bin/sh
PY    ?= python
GAME  ?=
ONLY  ?=
ROOT_FLAG ?=

.PHONY: help setup extract stage list contracts docs-check test

help:
	@$(PY) run_all.py --help

list:
	@$(PY) run_all.py --list

docs-check:
	@$(PY) tools/check_documentation.py

test: docs-check
	@$(PY) -m pytest tests -q

contracts:
	@$(PY) tools/stage10_check_contracts.py $(ROOT_FLAG)

setup:
	$(PY) -m venv .venv
	@if [ -x ".venv/bin/python" ]; then VPY=".venv/bin/python"; \
	else VPY=".venv/Scripts/python.exe"; fi; \
	PIN=$$($(PY) run_all.py --print-unitypy-pin); \
	echo "installing UnityPy==$${PIN} into pack .venv"; \
	"$$VPY" -m pip install "UnityPy==$${PIN}"
	@echo "venv ready"

extract:
	@test -n "$(GAME)" || (echo "usage: make extract GAME='/path/to/Two Point Campus'"; exit 2)
	TPC_GAME_DIR="$(GAME)" $(PY) run_all.py "$(GAME)"

stage:
	@test -n "$(GAME)" -a -n "$(ONLY)" || (echo "usage: make stage GAME=/path/to/game ONLY=<stage-id>"; exit 2)
	TPC_GAME_DIR="$(GAME)" $(PY) run_all.py "$(GAME)" --only "$(ONLY)"
