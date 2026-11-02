"""Row 3: 48-bit CA over 3 CK cycles (6 bytes, DDR); CT, functional."""
import cocotb
from cocotb.triggers import RisingEdge

from hrbench import Bench, REG_SPACE


@cocotb.test()
async def ca_is_six_bytes_and_decodes(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.write(0x155, [0xA1B2C3D4])
    t = b.model.transactions[-1]
    assert (t.is_read, t.is_register, t.linear) == (False, False, True)
    assert t.word_addr == 2 * 0x155
    await b.read(0x155)
    t = b.model.transactions[-1]
    assert (t.is_read, t.is_register, t.linear, t.word_addr) == (True, False, True, 2 * 0x155)
    b.model.assert_clean()


@cocotb.test()
async def ca_address_bits_walk(dut):
    """Every host address bit reaches the matching CA bit (reads beyond the
    modelled array return 0 and are flagged array_bounds, which is expected)."""
    b = await Bench(dut).start()
    await b.wait_ready()
    for bit in range(30):
        adr = 1 << bit
        await b.read(adr)
        t = b.model.transactions[-1]
        assert t.word_addr == 2 * adr, f"bit {bit}: CA word address {t.word_addr:#x}"
        assert t.is_read and not t.is_register and t.linear
    odd = [v for v in b.model.violations if v.param != "array_bounds"]
    assert not odd, odd


@cocotb.test()
async def ca_register_space_bit(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.read(0, reg=True)
    t = b.model.transactions[-1]
    assert t.is_register and t.is_read and t.word_addr == 0
    await b.read(0x400, reg=True)
    assert b.model.transactions[-1].word_addr == 0x800
    b.model.assert_clean()


@cocotb.test()
async def ca_spans_three_ck_cycles(dut):
    """CK produces exactly 6 edges (3 cycles) for the CA of a register write,
    which has no latency and one data word (2 more edges)."""
    b = await Bench(dut).start()
    await b.wait_ready()
    n0 = b.ck_edges
    await b.write(0x400, [0x0000], reg=True)      # CR0 <- 0
    assert b.ck_edges - n0 == 6 + 2, f"{b.ck_edges - n0} CK edges"
    b.model.assert_clean()
