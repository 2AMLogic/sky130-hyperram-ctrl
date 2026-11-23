# The bench's pin-edge sample (issue #205): hrbench.Bench._ck_mon at
# HRBENCH_SAMPLE_NS=0 -- the mode flow/functional-verification-ctrl-sdf.json
# selects -- against pin_edge_host.v, a stand-in host that moves DQ/RWDS and
# their output enables at a selectable offset from its own CK edge.
SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
VERILOG_SOURCES = $(abspath pin_edge_host.v)
COCOTB_TOPLEVEL = pin_edge_host
COCOTB_TEST_MODULES = test_pin_edge_sample
export HRBENCH_SAMPLE_NS := 0
export PYTHONPATH := $(abspath ../ctrl):$(abspath ../hyperram_model):$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim
