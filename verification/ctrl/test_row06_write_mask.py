"""Row 6: RWDS as a per-byte write mask; CT, functional."""
import cocotb

from hrbench import Bench

OLD = 0x11223344
NEW = 0xA1B2C3D4


@cocotb.test()
async def every_byte_lane_pattern(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    for sel in range(16):
        adr = 0x80 + sel
        await b.write(adr, [OLD])
        n_masked0 = sum(t.bytes_masked for t in b.model.transactions)
        await b.write(adr, [NEW], sels=[sel])
        want = 0
        for lane in range(4):
            src = NEW if (sel >> lane) & 1 else OLD
            want |= src & (0xFF << (8 * lane))
        assert b.mem_beat(adr) == want, f"sel {sel:#x}: {b.mem_beat(adr):#010x} != {want:#010x}"
        assert sum(t.bytes_masked for t in b.model.transactions) - n_masked0 == 4 - bin(sel).count("1")
        assert await b.read(adr) == [want]
    b.model.assert_clean()


@cocotb.test()
async def mask_inside_a_burst(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.write(0x300, [OLD] * 4)
    await b.write(0x300, [NEW] * 4, sels=[0xF, 0x0, 0x5, 0xA])
    got = [b.mem_beat(0x300 + k) for k in range(4)]
    assert got[0] == NEW and got[1] == OLD
    assert got[2] == (NEW & 0x00FF00FF) | (OLD & 0xFF00FF00)
    assert got[3] == (NEW & 0xFF00FF00) | (OLD & 0x00FF00FF)
    b.model.assert_clean()


@cocotb.test()
async def register_writes_are_not_masked(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.write(0x400, [0x1234], sels=[0x0], reg=True)  # sel ignored in register space
    assert b.model.regs[0x800] == 0x1234
    b.model.assert_clean()
