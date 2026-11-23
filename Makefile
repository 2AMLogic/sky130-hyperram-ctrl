# Toolchain smoke flow on rtl/smoke/ (NOT the design). `make smoke` runs lint,
# the cocotb test, synthesis and three-corner STA, then writes the record.
# `make hyperram-lint | hyperram-synth | hyperram-check | hyperram-sta` cover the
# controller RTL and the pre-layout timing of its netlist;
# `make layout | layout-check` place-and-route its netlist (layout/);
# `make drc` runs klt drc on the routed GDS (T1 item 3);
# `make delay-chain` runs the 45-corner ngspice RWDS delay-chain campaign on the
# batch fleet (spec open question (b), issue 99; local_only: needs ngspice + PDK).
# `make post-route-sdf` writes the post-route SDF (klt sta, def + spef, on the
# committed layout; never re-routes) and `make post-route-verify` the
# SDF-annotated controller bench run (T1 item 7, issue 171; local_only: needs
# openroad/PDK/Icarus >= 13 respectively).
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
HR_RTL  := $(HR_DIR)/hyperram_ctrl.v $(HR_DIR)/hr_cmd_fsm.v $(HR_DIR)/hr_dq_out.v $(HR_DIR)/hr_rd_capture.v $(HR_DIR)/hr_tap_delay.v

.PHONY: hyperram-lint hyperram-synth hyperram-check hyperram-sta

hyperram-lint:
	# warnings are fatal; sim/ holds zero-delay stand-ins for the named sky130 cells
	verilator --lint-only -Wall --top-module hyperram_ctrl $(HR_DIR)/sim/sky130_cells_behav.v $(HR_RTL)

hyperram-synth:
	python3 flow/hyperram.py synth

# re-synthesize and compare with the committed netlist (T1 item 1 freshness)
hyperram-check:
	python3 flow/hyperram.py check

# klt sta on the committed netlist at all 16 shipped liberty corners (~30 s, no
# place-and-route); graded inside decision 0004's 1.62-1.98 V supply window,
# reported outside it. Not a prerequisite of anything.
hyperram-sta:
	python3 flow/hyperram.py sta

# regenerate only the pre-layout STA prose from the committed sta.json (no
# OpenROAD, no PDK); and the cheap freshness check that binds the committed
# STA.md to that record byte-for-byte (CI runs this one; the STA itself is
# local_only)
hyperram-sta-note:
	python3 flow/hyperram.py sta-note

hyperram-sta-check:
	python3 flow/hyperram.py sta-check

.PHONY: hyperram-sta-note hyperram-sta-check

# klt sta in def+spef mode on the routed DEF/SPEF at all 16 shipped corners with
# BOTH clocks declared (clk primary, hb_rwds_i the RWDS strobe, propagated;
# issue #172), run twice: clocks related, then asynchronous clock_groups --
# both readings provisional pending #2 (C4). ~25 min per request; needs
# OpenROAD + the pinned PDK (PDK_ROOT). Negative in-window slack is a filed
# finding, not a gate. Not a prerequisite of anything.
hyperram-sta-postroute:
	python3 flow/hyperram.py sta-postroute

# cheap freshness check: request/DEF/SPEF hashes vs the committed records
# (CI runs this one; the STA itself is local_only)
hyperram-sta-postroute-check:
	python3 flow/hyperram.py sta-postroute-check

.PHONY: hyperram-sta-postroute hyperram-sta-postroute-check

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
	scripts/klt.sh drc --deck sky130 --format json layout/records/hyperram_ctrl.gds > layout/records/drc.report.json

.PHONY: delay-chain

# The RWDS delay-chain ngspice campaign (spec open question (b), issue 99):
# 5x3x3 decision-0004 corners submitted to the batch fleet through `klt sim`
# (--wait-for-capacity 600; never a hand-run ngspice grid), the raw report
# committed verbatim, and taps.csv / summary.csv / RECORD.md derived from it.
# local_only like smoke/layout/drc: needs ngspice and the PDK, absent from CI.
delay-chain:
	python3 flow/delay_chain.py sim

.PHONY: post-route-sdf post-route-verify

# T1 item 7 (issue 171): the post-route SDF and the SDF-annotated bench run.
# post-route-sdf analyses the committed DEF + SPEF once (klt sta, def mode,
# sdf: true, corner tt_025C_1v80) and commits layout/records/hyperram_ctrl.tt_025C_1v80.sdf
# with the producing response; it never re-routes. post-route-verify runs the
# controller benches on the routed netlist with that SDF back-annotated
# (make -C verification/ctrl sdf is the same run) and records the report plus
# its input digests. local_only: needs openroad + PDK, resp. Icarus >= 13 + PDK.
post-route-sdf:
	python3 flow/post_route.py sdf

post-route-verify:
	python3 flow/post_route.py verify
