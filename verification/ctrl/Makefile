# Controller benches: one cocotb module per CT row of spec/target-spec.md plus
# a random-traffic scoreboard, against rtl/hyperram_ctrl with zero-delay
# stand-ins for the named sky130 cells (they carry no timing: pad and delay
# timing are rows 11, 12 and 14, proved by SPICE and STA, not here).
# `make` runs everything; `make COCOTB_TEST_MODULES=test_row09_max_cs_low`
# runs one module.
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
COCOTB_TEST_MODULES ?= test_row03_command_address,test_row04_latency,test_row05_bursts,test_row06_write_mask,test_row07_register_space,test_row08_power_up,test_row09_max_cs_low,test_row10_rwds_extra_latency,test_row13_no_calibration,test_row15_host_interface,test_row16_host_bursts,test_random_traffic
export PYTHONPATH := $(abspath .):$(abspath ../hyperram_model):$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

ifeq ($(GL),1)
$(SIM_BUILD)/sim.vvp: gl-preflight
.PHONY: gl-preflight
gl-preflight:
	@test -f $(PDK_VLOG)/sky130_fd_sc_hd.v || { echo "FATAL: PDK models not found under $(PDK_VLOG); run scripts/setup-env.sh or set PDK_ROOT"; exit 1; }
	@$(GL_CHECK)
endif
