# Cold-start entry point: `make -C verification` (after scripts/setup-env.sh).
# Runs the device-model self-test and the controller benches (one module per
# CT row of spec/target-spec.md, plus random traffic).
SHELL := /bin/bash
export PATH := $(abspath ../.venv)/bin:$(PATH)

.PHONY: all model-selftest ctrl

all: model-selftest ctrl

model-selftest:
	cd hyperram_model && python3 -m unittest -v test_model

ctrl:
	$(MAKE) -C ctrl
