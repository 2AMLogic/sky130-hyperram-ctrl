"""Row 16: host bursts via incrementing address cycles; back-pressure by
stall; the controller never drops data; CT, functional."""
import cocotb

from hrbench import Bench, seeded


def data(n, seed):
    return [(0x2545F491 * (k + 1) * (seed + 3)) & 0xFFFFFFFF for k in range(n)]


@cocotb.test()
async def long_write_burst_with_random_host_gaps(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    rnd = seeded(16)
    for rep in range(6):
        n = rnd.choice([8, 20, 33, 64])
        adr = 0x500 + 0x100 * rep
        d = data(n, rep)
        gaps = [rnd.choice([0, 0, 0, 1, 2, 5, 17]) for _ in range(n)]
        await b.write(adr, d, gaps=gaps)
        assert [b.mem_beat(adr + k) for k in range(n)] == d, f"rep {rep} n {n}"
    b.model.assert_clean()


@cocotb.test()
async def long_read_burst_with_random_host_gaps(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    rnd = seeded(17)
    d = data(100, 9)
    await b.write(0x800, d)
    pos = 0
    while pos < 100:
        n = min(rnd.choice([1, 3, 8, 21, 40]), 100 - pos)
        gaps = [rnd.choice([0, 0, 0, 1, 3, 9]) for _ in range(n)]
        got = await b.read(0x800 + pos, n, gaps=gaps)
        assert got == d[pos:pos + n], f"burst at {pos} n {n}"
        pos += n
    b.model.assert_clean()


@cocotb.test()
async def burst_longer_than_cs_low_budget_loses_nothing(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=10)               # long latency, short useful budget
    d = data(80, 4)
    n0 = len(b.model.transactions)
    await b.write(0x2000, d)
    assert len(b.model.transactions) - n0 >= 3
    assert await b.read(0x2000, 80) == d
    assert len(b.acks) >= 160
    assert b.max_cs_low_ns() <= b.params.t_csm_ns
    b.model.assert_clean()


@cocotb.test()
async def non_sequential_beats_start_new_transactions(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    n0 = len(b.model.transactions)
    await b.xfer([(1, 0x10, 0xAAAA0001, 0xF), (1, 0x50, 0xAAAA0002, 0xF), (1, 0x11, 0xAAAA0003, 0xF)])
    assert len(b.model.transactions) - n0 == 3
    assert [b.mem_beat(a) for a in (0x10, 0x50, 0x11)] == [0xAAAA0001, 0xAAAA0002, 0xAAAA0003]
    b.model.assert_clean()
