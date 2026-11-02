"""Row 5: linear bursts, any length up to the CS-low limit (longer ones are
split, see row 9); CT, functional."""
import cocotb

from hrbench import Bench


def pattern(base, n):
    return [((base + k) * 0x01010101 ^ (k << 13) ^ 0xA5C3_0000) & 0xFFFFFFFF for k in range(n)]


@cocotb.test()
async def linear_bursts_of_many_lengths(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6, tcsm=64)
    base = 0x100
    for n in (1, 2, 3, 4, 5, 8, 11, 16):
        data = pattern(base, n)
        await b.write(base, data)
        assert [b.mem_beat(base + k) for k in range(n)] == data, f"write n={n}"
        assert await b.read(base, n) == data, f"read n={n}"
        base += 0x40
    b.model.assert_clean()


@cocotb.test()
async def single_word_register_style_beat_at_odd_addresses(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    for adr in (0x0, 0x1, 0x7, 0x8, 0x3FFF):
        await b.write(adr, [0xDEAD0000 | adr])
        assert await b.read(adr) == [0xDEAD0000 | adr]
    b.model.assert_clean()


@cocotb.test()
async def burst_is_one_transaction_when_it_fits(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6, tcsm=64)
    n0 = len(b.model.transactions)
    await b.write(0x200, pattern(7, 6))
    assert len(b.model.transactions) - n0 == 1
    n0 = len(b.model.transactions)
    await b.read(0x200, 6)
    assert len(b.model.transactions) - n0 == 1
    t = b.model.transactions[-1]
    assert t.linear and t.bytes_transferred >= 6 * 4
    b.model.assert_clean()
