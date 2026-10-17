"""Toolchain smoke test -- NOT a design test. See rtl/smoke/smoke_counter.v."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def counter_increments_and_wraps(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.rst_n.value = 0
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.count.value) == 1, "first edge after reset release must give 1"

    for expected in range(2, 256):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.count.value) == expected

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.count.value) == 0, "counter must wrap 255 -> 0"
