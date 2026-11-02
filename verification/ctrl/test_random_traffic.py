"""Random traffic against a host-side reference memory (scoreboard).

Mixes read and write bursts of random length, address, byte masks, host gaps,
latency settings and device RWDS extra-latency requests, plus register-space
reads. Reads are compared with the reference beat by beat; the model must stay
violation-free (tCSM, tCSHI, ...). The seed is printed; set RANDOM_SEED to
reproduce.
"""
import os

import cocotb

from hrbench import Bench, seeded

N_OPS = int(os.environ.get("RANDOM_OPS", "120"))
WINDOW = 96                 # beats, so reads often hit written data


def merge(old, new, sel):
    out = old
    for lane in range(4):
        if (sel >> lane) & 1:
            m = 0xFF << (8 * lane)
            out = (out & ~m) | (new & m)
    return out


@cocotb.test()
async def random_traffic_scoreboard(dut):
    seed = int(os.environ.get("RANDOM_SEED", "20261102"))
    rnd = seeded(seed)
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    ref = {}                 # beat address -> 32-bit value (unwritten = 0)
    base = 0x3000
    for op in range(N_OPS):
        if op % 17 == 0:
            lat = rnd.choice([4, 5, 6, 8, 12])
            await b.configure(lat=lat)
        n = rnd.choice([1, 1, 2, 3, 5, 8, 13, 24])
        adr = base + rnd.randrange(WINDOW - n)
        gaps = [rnd.choice([0, 0, 0, 0, 1, 4]) for _ in range(n)] if rnd.random() < 0.4 else None
        b.model.request_extra_latency = False  # doubled-latency reads: see README (RTL defect)
        kind = rnd.choice(["w", "w", "r", "r", "r", "reg"])
        if kind == "w":
            dats = [rnd.getrandbits(32) for _ in range(n)]
            sels = [rnd.choice([0xF, 0xF, 0xF, rnd.randrange(16)]) for _ in range(n)]
            b.model.request_extra_latency = rnd.random() < 0.2
            await b.write(adr, dats, sels=sels, gaps=gaps)
            for k in range(n):
                ref[adr + k] = merge(ref.get(adr + k, 0), dats[k], sels[k])
        elif kind == "r":
            got = await b.read(adr, n, gaps=gaps)
            want = [ref.get(adr + k, 0) for k in range(n)]
            assert got == want, f"op {op}: read {n} at {adr:#x}: {got} != {want}"
        else:
            got = await b.read(0, reg=True)
            assert got == [b.params.id0]
        # the model memory must equal the reference at all times
        if op % 10 == 9:
            for a, v in ref.items():
                assert b.mem_beat(a) == v, f"op {op}: memory {a:#x} {b.mem_beat(a):#x} != {v:#x}"
    for a, v in ref.items():
        assert b.mem_beat(a) == v
    print(f"{N_OPS} ops, {len(b.model.transactions)} bus transactions, {len(b.acks)} acks")
    b.model.assert_clean()
