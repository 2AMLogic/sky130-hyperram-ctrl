"""Row 15: Wishbone-class 32-bit pipelined host interface with ack-based
back-pressure; CT, functional."""
import cocotb
from cocotb.triggers import RisingEdge

from hrbench import Bench


@cocotb.test()
async def one_ack_per_accepted_beat_and_none_unasked(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    await b.idle(5)
    assert int(dut.wb_ack.value) == 0
    n0 = len(b.acks)
    await b.write(0x10, [1, 2, 3, 4, 5])
    await b.read(0x10, 5)
    assert len(b.acks) - n0 == 10
    await b.idle(30)
    assert len(b.acks) - n0 == 10          # nothing further acked while idle
    assert int(dut.wb_ack.value) == 0


@cocotb.test()
async def stall_back_pressures_and_data_is_not_lost(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    data = [0xC0DE0000 + k for k in range(24)]
    await b.write(0x40, data)
    assert b.stalls > 0, "a 24-beat burst must see wb_stall"
    assert [b.mem_beat(0x40 + k) for k in range(24)] == data
    assert await b.read(0x40, 24) == data
    assert b.stalls > 0
    b.model.assert_clean()


@cocotb.test()
async def pipelined_reads_overlap(dut):
    """The interface is pipelined: more than one read is accepted before the
    first ack returns."""
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    await b.write(0x60, [10, 20, 30, 40])
    accepted = acked = peak = 0
    d = dut
    d.wb_cyc.value = 1
    d.wb_we.value = 0
    d.wb_sel.value = 0xF
    k = 0
    d.wb_stb.value = 1
    d.wb_adr.value = 0x60
    got = []
    for _ in range(400):
        await RisingEdge(d.clk)
        if int(d.wb_ack.value):
            got.append(int(d.wb_dat_r.value))
            acked += 1
        if k < 4 and not int(d.wb_stall.value):
            accepted += 1
            k += 1
            if k < 4:
                d.wb_adr.value = 0x60 + k
            else:
                d.wb_stb.value = 0
        peak = max(peak, accepted - acked)
        if acked == 4:
            break
    d.wb_cyc.value = 0
    assert got == [10, 20, 30, 40], got
    assert peak >= 2, f"peak outstanding {peak}"


@cocotb.test()
async def dropping_cyc_does_not_cancel_an_accepted_beat(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    d = dut
    d.wb_cyc.value, d.wb_stb.value, d.wb_we.value = 1, 1, 1
    d.wb_adr.value, d.wb_dat_w.value, d.wb_sel.value = 0x90, 0xFEEDFACE, 0xF
    while True:
        await RisingEdge(d.clk)
        if not int(d.wb_stall.value):
            break
    d.wb_cyc.value = d.wb_stb.value = 0           # master walks away
    await b.idle(60)
    assert b.mem_beat(0x90) == 0xFEEDFACE
    b.model.assert_clean()


@cocotb.test()
async def reads_see_earlier_writes_in_order(dut):
    b = await Bench(dut).start()
    await b.wait_ready()
    await b.configure(lat=6)
    for k in range(6):
        await b.write(0xA0 + k, [0x1000 + k])
    assert await b.read(0xA0, 6) == [0x1000 + k for k in range(6)]
    await b.write(0xA3, [0xBEEF])
    assert await b.read(0xA2, 3) == [0x1002, 0xBEEF, 0x1004]
    b.model.assert_clean()
