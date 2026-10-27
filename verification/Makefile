# Cold-start entry point: `make -C verification` (after scripts/setup-env.sh).
# Runs the device-model self-test and the cocotb smoke test. Controller
# benches (one per CT row of spec/target-spec.md) join once the RTL exists.
SHELL := /bin/bash
export PATH := $(abspath ../.venv)/bin:$(PATH)

.PHONY: all model-selftest smoke

all: model-selftest smoke

model-selftest:
	cd hyperram_model && python3 -m unittest -v test_model

smoke:
	$(MAKE) -C smoke
