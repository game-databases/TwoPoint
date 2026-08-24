# Two Point Campus — reproducible A→Z extraction entrypoint (piece 1).
# Thin wrapper over run_all.py (the real entrypoint). Usage:
#   make setup                                          # create .venv + install pinned UnityPy
#   make extract GAME=/path/to/Two Point Campus         # full A→Z
#   make stage   GAME=... ONLY=verify-client            # single stage in isolation
#   make list                                           # enumerate stages
SHELL := /bin/sh
PY    ?= python
GAME  ?=
ONLY  ?=

.PHONY: help setup extract stage list

help:
	@$(PY) run_all.py --help

list:
	@$(PY) run_all.py --list

setup:
	$(PY) -m venv .venv
	@if [ -x ".venv/bin/python" ]; then VPY=".venv/bin/python"; \
	else VPY=".venv/Scripts/python.exe"; fi; \
	PIN=$$($(PY) run_all.py --print-unitypy-pin); \
	echo "installing UnityPy==$${PIN} into pack .venv"; \
	"$$VPY" -m pip install "UnityPy==$${PIN}"
	@echo "venv ready — UnityPy installed at the EXTRACTION-LOG-pinned version."

extract:
	@test -n "$(GAME)" || (echo "usage: make extract GAME='/path/to/Two Point Campus'"; exit 2)
	TPC_GAME_DIR="$(GAME)" $(PY) run_all.py "$(GAME)"

stage:
	@test -n "$(GAME)" -a -n "$(ONLY)" || (echo "usage: make stage GAME=/path/to/game ONLY=<stage-id>"; exit 2)
	TPC_GAME_DIR="$(GAME)" $(PY) run_all.py "$(GAME)" --only "$(ONLY)"
