# Toolchain smoke flow on rtl/smoke/ (NOT the design). `make smoke` runs lint,
# the cocotb test, synthesis and three-corner STA, then writes the record.
# `make hyperram-lint | hyperram-synth | hyperram-check` cover the controller RTL;
# `make layout | layout-check` place-and-route its netlist (layout/);
# `make drc` runs klt drc on the routed GDS (T1 item 3).
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

HR_DIR  := rtl/hyperram_ctrl
HR_RTL  := $(HR_DIR)/hyperram_ctrl.v $(HR_DIR)/hr_cmd_fsm.v $(HR_DIR)/hr_dq_out.v $(HR_DIR)/hr_rd_capture.v

.PHONY: hyperram-lint hyperram-synth hyperram-check

hyperram-lint:
	# warnings are fatal; sim/ holds zero-delay stand-ins for the named sky130 cells
	verilator --lint-only -Wall --top-module hyperram_ctrl $(HR_DIR)/sim/sky130_cells_behav.v $(HR_RTL)

hyperram-synth:
	python3 flow/hyperram.py synth

# re-synthesize and compare with the committed netlist (T1 item 1 freshness)
hyperram-check:
	python3 flow/hyperram.py check

.PHONY: layout layout-check

# klt place-and-route (50 MHz, PDN + tapcells) on the committed netlist; ~25 min.
layout:
	python3 flow/hyperram.py layout

# cheap freshness check: request inputs vs the committed response, GDS vs item-2 envelope
layout-check:
	python3 flow/hyperram.py layout-check

.PHONY: drc

# klt drc (curated sky130 deck, ~1 min, no PDK) on the routed GDS -> item-3 report
drc:
	uvx --from klayout-tools==0.8.0 klt drc --deck sky130 --format json layout/records/hyperram_ctrl.gds > layout/records/drc.report.json
