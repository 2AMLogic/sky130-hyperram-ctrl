"""Row 10: the controller samples RWDS during CA and doubles latency when it
is asserted; the sampling point is tied to CK, not the delayed strobe; CT."""
import cocotb

from hrbench import Bench

DATA = [0x0BADCAFE, 0x12345678]


async def one_beat_write_edges(b, adr):
    n0 = b.ck_edges
    await b.write(adr, [0x5A5A5A5A])
    return b.ck_edges - n0


@cocotb.test()
async def doubles_only_when_rwds_high(dut):
    """Measured on writes, whose length depends only on the controller's
    latency decision: 2 x lat clocks instead of lat is exactly 2 x lat more
    CK edges."""
    b = await Bench(dut).start()
    await b.wait_ready()
    for lat in (4, 5, 7):
        await b.configure(lat=lat)
        b.model.request_extra_latency = False
        plain = [await one_beat_write_edges(b, 0x70) for _ in range(2)]
        assert plain[0] == plain[1]
        b.model.request_extra_latency = True
        dbl = [await one_beat_write_edges(b, 0x70) for _ in range(2)]
        assert dbl == [plain[0] + 2 * lat] * 2, (lat, plain, dbl)
        assert b.model.transactions[-1].latency_clk == 2 * lat
        b.model.assert_clean()


@cocotb.test()
async def sampling_is_independent_of_rwds_skew_after_ck(dut):
    """Fault injection: the device's RWDS during CA is late by up to 8 ns after
    its nominal tCKDS. The decision (write length in CK edges) must not change:
    the controller samples on its own clock, never on an RWDS edge. (The
    strobe used for read DATA keeps its eye position; only the CA phase is
    skewed here, per Bench.ca_rwds_skew_ns.)"""
    b = await Bench(dut).start()
    ref = None
    for skew in (0.0, 4.0, 8.0):
        await b.restart(ca_rwds_skew_ns=skew)
        await b.wait_ready()
        await b.configure(lat=5)
        b.model.request_extra_latency = True
        e = await one_beat_write_edges(b, 0x70)
        ref = e if ref is None else ref
        assert e == ref, f"skew {skew} ns changed the decision: {e} vs {ref} edges"
        assert b.model.transactions[-1].latency_clk == 10
        b.model.assert_clean()


@cocotb.test()
async def doubled_latency_read_returns_correct_data(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=5)
    await b.write(0x70, DATA)
    b.model.request_extra_latency = True
    assert await b.read(0x70, 2) == DATA


@cocotb.test()
async def doubled_latency_write_is_correct(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=5)
    b.model.request_extra_latency = True
    await b.write(0x78, DATA)
    assert [b.mem_beat(0x78), b.mem_beat(0x79)] == DATA
    assert b.model.transactions[-1].latency_clk == 10
    b.model.assert_clean()
