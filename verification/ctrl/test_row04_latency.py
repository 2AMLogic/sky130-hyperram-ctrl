"""Row 4: variable latency with RWDS-signalled extra latency; fixed latency
selectable by configuration; CT, functional."""
import cocotb

from hrbench import CFG_CTRL, Bench
from model import CR0_FIXED_LATENCY_BIT

DATA = [0x11223344, 0x55667788, 0x99AABBCC]


@cocotb.test()
async def variable_latency_normal(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    for lat in (4, 5, 6, 9, 15):
        b.model.violations.clear()
        await b.configure(lat=lat)
        await b.write(0x10, DATA)
        assert await b.read(0x10, 3) == DATA, f"lat {lat}"
        t = b.model.transactions[-1]
        assert t.latency_clk == lat and not t.extra_latency, (lat, t)
        b.model.assert_clean()


async def ck_edges_for_one_beat_write(b, adr):
    n0 = b.ck_edges
    await b.write(adr, [0x5A5A5A5A])
    return b.ck_edges - n0


@cocotb.test()
async def doubling_decision_at_the_pins(dut):
    """RWDS high in CA makes the controller wait 2 x lat clocks instead of
    lat: a write runs exactly 2 x lat more CK edges. This checks the
    controller's decision on the pins; the read data path follows below."""
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    base = await ck_edges_for_one_beat_write(b, 0x20)
    b.model.request_extra_latency = True
    doubled = await ck_edges_for_one_beat_write(b, 0x20)
    assert doubled - base == 2 * 6, (base, doubled)
    assert b.model.transactions[-1].latency_clk == 12


# Data-path check of doubled latency (the junk word from the RWDS fall after CA
# is flushed through ST_LAT, #48).
@cocotb.test()
async def variable_latency_doubled_by_rwds(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    await b.write(0x20, DATA)
    b.model.request_extra_latency = True
    assert await b.read(0x20, 3) == DATA
    t = b.model.transactions[-1]
    assert t.extra_latency and t.latency_clk == 12
    await b.write(0x30, DATA)            # writes honour it too
    assert b.model.transactions[-1].latency_clk == 12
    b.model.request_extra_latency = False
    assert await b.read(0x30, 3) == DATA
    assert b.model.transactions[-1].latency_clk == 6
    b.model.assert_clean()


@cocotb.test()
async def fixed_latency_configuration(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    # Put the device in fixed-latency mode through the register space, then
    # tell the controller (CTRL[0]).
    await b.write(0x400, [1 << CR0_FIXED_LATENCY_BIT], reg=True)
    assert b.model.fixed_latency
    await b.cfg_write(CFG_CTRL, 1)
    await b.write(0x40, DATA)
    assert await b.read(0x40, 3) == DATA
    t = b.model.transactions[-1]
    assert t.extra_latency and t.latency_clk == 12, t
    b.model.assert_clean()
    # Back to variable on both sides.
    await b.write(0x400, [0], reg=True)
    await b.cfg_write(CFG_CTRL, 0)
    assert await b.read(0x40, 3) == DATA
    assert b.model.transactions[-1].latency_clk == 6
    b.model.assert_clean()


@cocotb.test()
async def controller_latency_shorter_than_device_is_caught(dut):
    """Sensitivity control: a write issued with less latency than the device
    applies lands in the wrong place, so the bench does see a latency
    disagreement. (A read that waits too little is absorbed by the capture
    ring, which pops only what has arrived.)"""
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=4, device_lat=6)
    await b.write(0x50, DATA)
    assert [b.mem_beat(0x50 + k) for k in range(3)] != DATA


@cocotb.test()
async def clamp_below_four(dut):
    """cfg_lat < 4 is clamped to 4 (hr_cmd_fsm.v), so a device latency of 4
    works with cfg_lat = 1."""
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=1, device_lat=4)
    await b.write(0x60, DATA)
    assert await b.read(0x60, 3) == DATA
    assert b.model.transactions[-1].latency_clk == 4
    b.model.assert_clean()
