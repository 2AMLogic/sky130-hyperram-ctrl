# Toolchain smoke flow on rtl/smoke/ (NOT the design). `make smoke` runs lint,
# the cocotb test, synthesis and three-corner STA, then writes the record.
# Run scripts/setup-env.sh first; targets use .venv/bin tools when present.

SHELL := /bin/bash
VENV  := $(CURDIR)/.venv
export PATH := $(VENV)/bin:$(PATH)
export PDK ?= sky130A

SMOKE_RTL := rtl/smoke/smoke_counter.v
REC       := sim/smoke/records
NETLIST   := $(REC)/smoke_counter.netlist.v

.PHONY: smoke smoke-lint smoke-sim smoke-synth smoke-sta smoke-record

smoke: smoke-lint smoke-sim smoke-synth smoke-sta smoke-record

smoke-lint:
	# warnings are fatal by default in verilator (no -Wno-fatal)
	verilator --lint-only -Wall --top-module smoke_counter $(SMOKE_RTL)

smoke-sim:
	$(MAKE) -C verification/smoke

smoke-synth:
	python3 flow/smoke.py synth

smoke-sta: $(NETLIST)
	python3 flow/smoke.py sta

$(NETLIST):
	$(MAKE) smoke-synth

smoke-record:
	python3 flow/smoke.py record
