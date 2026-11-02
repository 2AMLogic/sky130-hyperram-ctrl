"""Row 13: calibration failure -- "not applicable in v1 (no calibration)".

The CT row for v1 is the absence check: the controller exposes no calibration
port and no calibration status bit. Read-capture is a fixed, register-selected
tap (decision 0003). If a calibrated mode is added later this module must be
replaced by the fall-back-and-flag test the row describes.
"""
import cocotb

from hrbench import CFG_STATUS, Bench


@cocotb.test()
async def no_calibration_port_or_status_bit(dut):
    names = [h._name.lower() for h in dut]
    bad = [n for n in names if "cal" in n or "train" in n or "dll" in n]
    assert not bad, f"calibration-like ports present: {bad}"
    b = await Bench(dut).start()
    await b.wait_ready()
    # STATUS defines bits [2:0] (ready, tcsm_small, busy); nothing above.
    for adr in range(8):
        v = await b.cfg_read(adr)
        assert v < (1 << 16)
    assert (await b.cfg_read(CFG_STATUS)) >> 3 == 0
    assert (await b.cfg_read(7)) == 0
