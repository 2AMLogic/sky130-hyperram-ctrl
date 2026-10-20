# cocotb + Icarus smoke test; run via the top-level `make smoke-sim`.
SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
VERILOG_SOURCES = $(abspath ../../rtl/smoke/smoke_counter.v)
COCOTB_TOPLEVEL = smoke_counter
COCOTB_TEST_MODULES = test_smoke_counter
include $(shell cocotb-config --makefiles)/Makefile.sim
