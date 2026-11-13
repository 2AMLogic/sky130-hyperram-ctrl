"""Row 9: the controller splits transactions so CS# never stays low longer than
the model's tCSM, with a down-counter that ends the burst and re-issues the
remainder; CT with a model that flags the violation.

The device-model tCSM is a placeholder (spec/device-model-params.md tCSM is
TBD(src)); what is verified is the relation
    cfg_tcsm = floor(tCSM / T) - TCSM_MARGIN_CLK  =>  no violation
for the placeholder and for several other tCSM values, at the 50 MHz clock
used here, plus a negative control that shows the model flags it.
"""
import dataclasses

import cocotb

from hrbench import BENCH_PARAMS, PERIOD_NS, TCSM_MARGIN_CLK, Bench


def data(n, seed=1):
    return [(0x9E3779B1 * (k + seed)) & 0xFFFFFFFF for k in range(n)]


async def long_traffic(b, n=40):
    d = data(n)
    n0 = len(b.model.transactions)
    await b.write(0x1000, d)
    assert [b.mem_beat(0x1000 + k) for k in range(n)] == d
    n_wr = len(b.model.transactions) - n0
    n0 = len(b.model.transactions)
    assert await b.read(0x1000, n) == d
    return n_wr, len(b.model.transactions) - n0


@cocotb.test()
async def long_bursts_are_split_and_never_exceed_tcsm(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    n_wr, n_rd = await long_traffic(b)
    assert n_wr > 1 and n_rd > 1, (n_wr, n_rd)          # burst was split, re-issued
    assert b.max_cs_low_ns() <= b.params.t_csm_ns, b.max_cs_low_ns()
    b.model.assert_clean()
    print(f"tCSM {b.params.t_csm_ns} ns, longest CS# low {b.max_cs_low_ns()} ns, "
          f"writes in {n_wr} transactions, reads in {n_rd}")


@cocotb.test()
async def margin_holds_across_tcsm_and_latency(dut):
    """At and around the tCSM boundary: several model tCSM values and
    latencies, every one derived by the same rule."""
    b = await Bench(dut).start()
    for t_csm_clk in (30, 36, 48, 64):
        for lat in (4, 6, 10):
            p = dataclasses.replace(BENCH_PARAMS, t_csm_ns=float(t_csm_clk * PERIOD_NS))
            await b.restart(params=p)
            await b.wait_ready()
            await b.configure(lat=lat)
            await long_traffic(b, 30)
            assert b.max_cs_low_ns() <= p.t_csm_ns, (t_csm_clk, lat, b.max_cs_low_ns())
            b.model.assert_clean()


@cocotb.test()
async def margin_is_tight_not_loose(dut):
    """The rule is not wildly conservative: with the budget one clock per
    margin step looser, the model flags tCSM. Documents where the boundary is."""
    b = await Bench(dut).start()
    flagged_at = None
    for margin in range(TCSM_MARGIN_CLK, -4, -1):
        await b.restart()
        await b.wait_ready()
        await b.configure(lat=6, tcsm=int(b.params.t_csm_ns // PERIOD_NS) - margin)
        await long_traffic(b, 30)
        if b.model.violations_of("tCSM"):
            flagged_at = margin
            break
    print(f"first margin (clocks) at which tCSM is flagged: {flagged_at}")
    assert flagged_at is not None and flagged_at < TCSM_MARGIN_CLK


@cocotb.test()
async def negative_control_limit_disabled_is_flagged(dut):
    """The controller's limit set far above tCSM: the model must flag it."""
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6, tcsm=60000)
    await long_traffic(b, 40)
    assert b.model.violations_of("tCSM"), "model did not flag an over-long CS# low"
    assert b.max_cs_low_ns() > b.params.t_csm_ns
    assert all(v.param == "tCSM" for v in b.model.violations)


@cocotb.test()
async def budget_too_small_sets_status_bit(dut):
    """A budget too small for even one beat is reported (STATUS[1]), not hidden."""
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6, tcsm=8)
    await b.read(0x10, 2)
    await b.idle(10)
    assert (await b.cfg_read(6)) & 2
