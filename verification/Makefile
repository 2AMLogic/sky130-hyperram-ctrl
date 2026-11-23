# Cold-start entry point: `make -C verification` (after scripts/setup-env.sh).
# Runs the device-model self-test, the controller benches (one module per
# CT row of spec/target-spec.md, plus random traffic) and the pin-edge
# sampling suite.
SHELL := /bin/bash
export PATH := $(abspath ../.venv)/bin:$(PATH)

.PHONY: all model-selftest ctrl pin-edge-sample

all: model-selftest ctrl pin-edge-sample

model-selftest:
	cd hyperram_model && python3 -m unittest -v test_model

ctrl:
	$(MAKE) -C ctrl

pin-edge-sample:
	$(MAKE) -C pin_edge_sample
