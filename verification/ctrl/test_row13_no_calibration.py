"""Row 13: calibration failure -- "not applicable in v1 (no calibration)".

The CT row for v1 is the absence check: the controller exposes no calibration
port and no calibration status bit. Read-capture is a fixed, register-selected
tap (decision 0003). If a calibrated mode is added later this module must be
replaced by the fall-back-and-flag test the row describes.
"""
import cocotb

from hrbench import CFG_STATUS, Bench

# cfg_adr -> the bits the port header documents as readable fields
# (hyperram_ctrl.v, "Configuration port"). CTRL[1] (restart) is self-clearing
# and reads back 0; TAPS reads {9'd0, ck_tap, 1'b0, rd_tap}, so bit 3 is a
# hardwired zero between the two tap fields; STATUS is read-only [2:0];
# address 7 is unmapped and reads 0.
CFG_FIELD_MASK = (0x0001, 0x000F, 0xFFFF, 0xFFFF, 0x000F, 0x0077, 0x0007, 0x0000)


@cocotb.test()
async def no_calibration_port_or_status_bit(dut):
    names = [h._name.lower() for h in dut]
    bad = [n for n in names if "cal" in n or "train" in n or "dll" in n]
    assert not bad, f"calibration-like ports present: {bad}"
    b = await Bench(dut).start()
    await b.wait_ready()
    # STATUS defines bits [2:0] (ready, tcsm_small, busy); nothing above.
    assert (await b.cfg_read(CFG_STATUS)) >> 3 == 0
    assert (await b.cfg_read(7)) == 0
    # No spare config bit holds state: write all-ones everywhere, then every bit
    # outside the documented field must still read 0. A calibration or training
    # field smuggled into the spare bits of an existing register would show up
    # here as a bit that latched. (This replaces a `v < (1 << 16)` loop that a
    # 16-bit cfg_rdata port could never fail.)
    for adr in range(len(CFG_FIELD_MASK)):
        await b.cfg_write(adr, 0xFFFF)
    for adr, mask in enumerate(CFG_FIELD_MASK):
        v = await b.cfg_read(adr)
        assert v & ~mask == 0, \
            f"cfg {adr}: {v:#06x} has bits set outside documented field {mask:#06x}"
