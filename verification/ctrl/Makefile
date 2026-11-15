# Controller benches: one cocotb module per CT row of spec/target-spec.md plus
# a random-traffic scoreboard, against rtl/hyperram_ctrl with zero-delay
# stand-ins for the named sky130 cells (they carry no timing: pad and delay
# timing are rows 11, 12 and 14, proved by SPICE and STA, not here).
# `make` runs everything; `make COCOTB_TEST_MODULES=test_row09_max_cs_low`
# runs one module.
#
# The bench list is not written out here. It is derived from this directory by
# the one controller-bench rule, applied identically in the three places that
# need it (issue #93): every `test_*.py` beside this Makefile except
# `test_all.py` is a bench module. test_all.py (the aggregator cited by
# flow/functional-verification-ctrl.json) globs with the same rule, and
# scripts/check_bench_coverage.py asserts attest/item9.json declares every file
# the rule can see -- so a bench added on disk cannot be missing from one list
# while present in another, and cannot be silently unattested.
SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
RTL             = $(abspath ../../rtl/hyperram_ctrl)
ifeq ($(GL),1)
GL_PDK_ROOT    ?= $(or $(PDK_ROOT),$(HOME)/.ciel)
PDK_VLOG        = $(GL_PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog
GL_NETLIST     ?= $(abspath ../../sim/hyperram/records/hyperram_ctrl.netlist.v)
VERILOG_SOURCES = $(GL_NETLIST) $(PDK_VLOG)/primitives.v $(PDK_VLOG)/sky130_fd_sc_hd.v
COMPILE_ARGS   += -DFUNCTIONAL -DUNIT_DELAY=\#0
SIM_BUILD       = sim_build_gl
ifeq ($(origin GL_NETLIST),file)
GL_CHECK        = cd $(abspath ../..) && env -u PDK_ROOT PDK=sky130A python3 flow/hyperram.py check
endif
else
VERILOG_SOURCES = $(RTL)/sim/sky130_cells_behav.v $(RTL)/hr_dq_out.v \
                  $(RTL)/hr_rd_capture.v $(RTL)/hr_cmd_fsm.v $(RTL)/hyperram_ctrl.v
endif
COCOTB_TOPLEVEL = hyperram_ctrl
# The controller-bench rule (see the header): every test_*.py in this directory
# except the test_all.py aggregator, as a comma-separated module list. `?=`, so
# `make COCOTB_TEST_MODULES=test_row09_max_cs_low` still selects one module.
BENCH_DIR      := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
BENCH_MODULES  := $(sort $(basename $(filter-out test_all.py,$(notdir $(wildcard $(BENCH_DIR)test_*.py)))))
empty          :=
space          := $(empty) $(empty)
comma          := ,
ifeq ($(strip $(BENCH_MODULES)),)
$(error no controller bench matched test_*.py in $(BENCH_DIR): the glob or the benches moved)
endif
COCOTB_TEST_MODULES ?= $(subst $(space),$(comma),$(BENCH_MODULES))
export PYTHONPATH := $(abspath .):$(abspath ../hyperram_model):$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

ifeq ($(GL),1)
$(SIM_BUILD)/sim.vvp: gl-preflight
.PHONY: gl-preflight
gl-preflight:
	@test -f $(PDK_VLOG)/sky130_fd_sc_hd.v || { echo "FATAL: PDK models not found under $(PDK_VLOG); run scripts/setup-env.sh or set PDK_ROOT"; exit 1; }
	@$(GL_CHECK)
endif
