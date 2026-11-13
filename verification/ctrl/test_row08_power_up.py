"""Row 8: the controller holds RESET# and CS# deasserted for a configured
power-up interval (a register, not hardcoded) before the first access; CT."""
import cocotb
from cocotb.triggers import RisingEdge

from hrbench import CFG_PU, CFG_STATUS, PERIOD_NS, Bench


@cocotb.test()
async def interval_is_honoured_and_pads_quiet(dut):
    """Default interval (256 clocks = 5120 ns) exceeds the model's placeholder
    power-up time (2000 ns): the first access is clean. During the interval
    CS# stays high, DQ/RWDS are not driven, CK is idle and STATUS.ready = 0."""
    b = await Bench(dut).start()
    n_ck = b.ck_edges
    quiet = 0
    while not int(await b.cfg_read(CFG_STATUS)) & 1:
        assert int(dut.hb_cs_n.value) == 1
        assert int(dut.hb_dq_oe.value) == 0 and int(dut.hb_rwds_oe.value) == 0
        quiet += 1
        await RisingEdge(dut.clk)
    assert b.ck_edges == n_ck, "CK toggled during power-up"
    assert quiet * PERIOD_NS >= 2000, f"power-up only {quiet * PERIOD_NS} ns"
    # first access, immediately when ready
    await b.configure(lat=6)
    await b.write(0x0, [0x12345678])
    first_fall = b.cs_events[0][1]
    assert first_fall - b.model._reset_released_ns >= b.params.power_up_ns
    assert await b.read(0x0) == [0x12345678]
    b.model.assert_clean()


@cocotb.test()
async def interval_is_a_register(dut):
    """Programming a shorter interval shortens it by the programmed amount."""
    times = {}
    b0 = None
    for pu in (40, 120):
        b = await (b0.restart(cfg={CFG_PU: pu}) if b0 else Bench(dut).start(cfg={CFG_PU: pu}))
        await first_access(b)
        times[pu] = b.cs_events[0][1] - b.t_rst_release
        b0 = b
    assert times[120] - times[40] == (120 - 40) * PERIOD_NS, times


async def first_access(b):
    """Configure and issue one write: the first CS# fall is cs_events[0]."""
    await b.configure(lat=6)
    await b.write(0x0, [1])


@cocotb.test()
async def too_short_interval_is_flagged_by_the_model(dut):
    """Negative control: an interval shorter than the model's power-up time
    (placeholder 2000 ns) makes the model flag power_up, so the check works."""
    b = await Bench(dut).start(cfg={CFG_PU: 20})
    await b.configure(lat=6)
    await b.write(0x0, [1])
    assert len(b.model.violations_of("power_up")) >= 1
    assert all(v.param == "power_up" for v in b.model.violations)
