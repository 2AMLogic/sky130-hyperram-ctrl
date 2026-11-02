"""Row 7: read/write of the device register space via the CA address-space
bit; CT, functional.

Reachability limit found by this bench (see PR): a host register address is a
32-bit-word address, so the device register word address is always even. ID0
(0x000) and CR0 (0x800) are reachable; ID1 (0x001) and CR1 (0x801) are not.
"""
import cocotb

from hrbench import Bench
from model import REG_CR0, REG_ID0


@cocotb.test()
async def read_id_and_config_registers(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    assert await b.read(REG_ID0 >> 1, reg=True) == [b.params.id0]
    assert await b.read(REG_CR0 >> 1, reg=True) == [b.params.cr0_reset]
    t = b.model.transactions[-1]
    assert t.is_register and t.is_read and t.latency_clk == 6
    b.model.assert_clean()


@cocotb.test()
async def write_then_read_back_register(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.write(REG_CR0 >> 1, [0x8F17], reg=True)
    t = b.model.transactions[-1]
    assert t.is_register and not t.is_read and t.latency_clk == 0
    assert b.model.regs[REG_CR0] == 0x8F17
    assert await b.read(REG_CR0 >> 1, reg=True) == [0x8F17]
    await b.write(REG_CR0 >> 1, [0], reg=True)
    b.model.assert_clean()


@cocotb.test()
async def read_only_register_ignores_write(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.write(REG_ID0 >> 1, [0xFFFF], reg=True)
    assert b.model.regs[REG_ID0] == b.params.id0
    assert await b.read(REG_ID0 >> 1, reg=True) == [b.params.id0]
    b.model.assert_clean()


@cocotb.test()
async def register_access_does_not_touch_memory(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.write(0x0, [0xCAFEF00D])
    await b.write(REG_CR0 >> 1, [0x1111], reg=True)
    assert b.mem_beat(0x0) == 0xCAFEF00D
    await b.write(REG_CR0 >> 1, [0], reg=True)
    b.model.assert_clean()
