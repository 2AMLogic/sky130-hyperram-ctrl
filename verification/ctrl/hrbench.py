"""Shared harness for the controller benches.

Wraps ``hyperram_ctrl`` with (a) a pad-level driver that feeds the pure-Python
device model (``hyperram_model.model``) from CK/CS#/RESET#/DQ/RWDS and drives
read data back, and (b) a Wishbone-class host and the configuration port.

ASSUMPTIONS stated here because the bench output depends on them:
  * The sky130 cells in the RTL are zero-delay stand-ins, so CK is not delayed
    by the quarter period that spec row 14 requires. The pad driver therefore
    samples DQ/RWDS ``SAMPLE_NS`` (a quarter of the 50 MHz period) after each
    CK edge, the position the real delayed CK would have. Real pad/CK timing is
    NOT claimed by these benches.
  * Read strobe: the model's RWDS is placed ``RWDS_EYE_NS`` after its DQ so
    the zero-delay capture chain sees RWDS mid-eye. Same caveat.
  * Model timing values are PLACEHOLDERS (spec/device-model-params.md rows are
    TBD(src), #2). ``PLACEHOLDER`` is printed by every bench that starts.
"""
from __future__ import annotations

import dataclasses
import random
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb.utils import get_sim_time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hyperram_model"))
from model import HyperRamModel, ModelParams  # noqa: E402

PERIOD_NS = 20
SAMPLE_NS = PERIOD_NS // 4
RWDS_EYE_NS = 5.0
TCSM_MARGIN_CLK = 3          # cfg_tcsm = floor(tCSM / T) - this; see test_row09
MEM_BYTES = 1 << 24          # 16 MiB: host word addresses < 0x400000

PLACEHOLDER = ModelParams(
    t_ck_min_ns=20.0, t_css_ns=2.0, t_csh_ns=2.0, t_cshi_ns=10.0,
    t_csm_ns=1000.0, t_ckd_ns=6.0, t_ckds_ns=6.0, initial_latency_clk=6,
    power_up_ns=2000.0, id0=0x0C81, id1=0x0001, cr0_reset=0x0000,
    cr1_reset=0x0002, rwds_skew_ns=RWDS_EYE_NS,
)

# cfg_adr values (hyperram_ctrl.v header)
CFG_CTRL, CFG_LAT, CFG_TCSM, CFG_PU, CFG_CS_HI, CFG_TAPS, CFG_STATUS = range(7)

REG_SPACE = 1 << 30


def now_ns() -> float:
    """Sim time in ns, rounded to 0.1 ns: the simulator reports a few ps of
    quantisation noise that would otherwise trip the model's tCK half-period
    check at exactly 20 ns."""
    return round(get_sim_time("ps") / 1000.0, 1)


def word_bytes(dat: int) -> bytes:
    """Bytes a host beat puts into memory: word 0 = dat[15:0] upper byte
    first, then word 1 = dat[31:16] (hr_cmd_fsm.v conventions)."""
    return bytes([(dat >> 8) & 0xFF, dat & 0xFF, (dat >> 24) & 0xFF, (dat >> 16) & 0xFF])


def beat_from_bytes(b: bytes) -> int:
    return (b[1]) | (b[0] << 8) | (b[3] << 16) | (b[2] << 24)


class Bench:
    def __init__(self, dut, params: ModelParams = PLACEHOLDER, ca_rwds_skew_ns: float = 0.0):
        self.dut = dut
        self.params = params
        self.model = HyperRamModel(params, MEM_BYTES)
        self.ca_rwds_skew_ns = ca_rwds_skew_ns
        self.cs_low = False
        self.cs_events: List[Tuple[str, float]] = []
        self.acks: List[Tuple[float, int]] = []
        self.ck_edges = 0

    # ------------------------------------------------------------ bring-up
    async def start(self, reset: bool = True, cfg: Optional[dict] = None):
        d = self.dut
        print("model parameters (PLACEHOLDERS, not datasheet values):")
        print(self.params.describe())
        for s in (d.wb_cyc, d.wb_stb, d.wb_we, d.cfg_we):
            s.value = 0
        for s in (d.wb_adr, d.wb_sel, d.wb_dat_w, d.cfg_adr, d.cfg_wdata,
                  d.hb_dq_i, d.hb_rwds_i):
            s.value = 0
        d.rst_n.value = 0
        cocotb.start_soon(Clock(d.clk, PERIOD_NS, unit="ns").start())
        self.model.reset_assert(now_ns())
        cocotb.start_soon(self._reset_mon())
        cocotb.start_soon(self._cs_mon())
        cocotb.start_soon(self._ck_mon())
        await self._release(cfg)
        return self

    async def _release(self, cfg):
        d = self.dut
        await Timer(3 * PERIOD_NS, unit="ns")
        await RisingEdge(d.clk)
        d.rst_n.value = 1
        self.t_rst_release = now_ns()
        self.cs_events.clear()
        if cfg:
            for adr, val in cfg.items():
                await self.cfg_write(adr, val)

    async def restart(self, params: Optional[ModelParams] = None, cfg: Optional[dict] = None,
                      ca_rwds_skew_ns: Optional[float] = None):
        """Reset the DUT and a fresh model inside one test (sweeps). The pad
        monitors keep running; only one Bench per test may call start()."""
        d = self.dut
        d.rst_n.value = 0
        d.cfg_we.value = 0
        d.wb_cyc.value = d.wb_stb.value = 0
        if params is not None:
            self.params = params
        if ca_rwds_skew_ns is not None:
            self.ca_rwds_skew_ns = ca_rwds_skew_ns
        self.model = HyperRamModel(self.params, MEM_BYTES)
        self.model.reset_assert(now_ns())
        self.cs_low = False
        await self._release(cfg)
        return self

    async def wait_ready(self, timeout_clk: int = 20000):
        for _ in range(timeout_clk):
            if (await self.cfg_read(CFG_STATUS)) & 1:
                return
            await RisingEdge(self.dut.clk)
        raise AssertionError("controller never became ready")

    # ------------------------------------------------------ pad-level model
    async def _reset_mon(self):
        while True:
            await self.dut.hb_reset_n.value_change
            v = self.dut.hb_reset_n.value
            if not v.is_resolvable:
                continue
            if int(v):
                self.model.reset_release(now_ns())
            else:
                self.model.reset_assert(now_ns())

    async def _cs_mon(self):
        while True:
            await self.dut.hb_cs_n.value_change
            v = self.dut.hb_cs_n.value
            if not v.is_resolvable:
                continue
            t = now_ns()
            if int(v) == 0:
                self.cs_low = True
                self.cs_events.append(("fall", t))
                self.model.cs_fall(t)
            elif self.cs_low:
                self.cs_low = False
                self.cs_events.append(("rise", t))
                self.model.cs_rise(t)
                self.dut.hb_dq_i.value = 0
                self.dut.hb_rwds_i.value = 0

    async def _ck_mon(self):
        d = self.dut
        while True:
            await d.hb_ck.value_change
            if not self.cs_low or not d.hb_ck.value.is_resolvable:
                continue
            t = now_ns()
            ck = int(d.hb_ck.value)
            self.ck_edges += 1
            await Timer(SAMPLE_NS, unit="ns")
            dq = int(d.hb_dq_o.value) if d.hb_dq_oe.value == 1 else None
            rw = int(d.hb_rwds_o.value) if d.hb_rwds_oe.value == 1 else None
            out = self.model.clock(t, ck, dq, rw)
            extra = 0.0 if out.dq is not None else self.ca_rwds_skew_ns
            cocotb.start_soon(self._drive(d.hb_dq_i, out.dq, out.dq_delay_ns))
            cocotb.start_soon(self._drive(d.hb_rwds_i, out.rwds, out.rwds_delay_ns + extra))

    async def _drive(self, sig, val, delay_ns):
        """Drive a device output ``delay_ns`` after its CK edge; a pin the device
        does not drive is parked at 0."""
        if val is None:
            sig.value = 0
            return
        wait = delay_ns - SAMPLE_NS
        assert wait >= 0, "tCKD/tCKDS placeholder must be >= the sample offset"
        if wait:
            await Timer(wait, unit="ns")
        sig.value = val

    # ------------------------------------------------------- configuration
    async def cfg_write(self, adr: int, val: int):
        d = self.dut
        d.cfg_adr.value, d.cfg_wdata.value, d.cfg_we.value = adr, val, 1
        await RisingEdge(d.clk)
        d.cfg_we.value = 0

    async def cfg_read(self, adr: int) -> int:
        self.dut.cfg_adr.value = adr
        await Timer(1, unit="ns")
        return int(self.dut.cfg_rdata.value)

    def set_device_latency(self, clk: int):
        self.model.p = dataclasses.replace(self.model.p, initial_latency_clk=clk)

    async def configure(self, lat=6, tcsm=None, fixed=False, cs_hi=None, pu=None,
                        device_lat=None):
        """Program the controller and make the model agree (the model's latency
        is a placeholder input, so it follows the controller unless
        ``device_lat`` says otherwise). ``tcsm`` defaults to the model's tCSM in
        clocks less TCSM_MARGIN_CLK (row 9 shows the margin is sufficient)."""
        if pu is not None:
            await self.cfg_write(CFG_PU, pu)
        await self.cfg_write(CFG_LAT, lat)
        self.set_device_latency(max(lat, 4) if device_lat is None else device_lat)
        if tcsm is None:
            tcsm = int(self.model.p.t_csm_ns // PERIOD_NS) - TCSM_MARGIN_CLK
        await self.cfg_write(CFG_TCSM, tcsm)
        if cs_hi is not None:
            await self.cfg_write(CFG_CS_HI, cs_hi)
        await self.cfg_write(CFG_CTRL, int(fixed))

    # ---------------------------------------------------------------- host
    async def xfer(self, beats: Sequence[Tuple[int, int, int, int]],
                   gaps: Optional[Sequence[int]] = None, timeout_clk: int = 40000
                   ) -> List[int]:
        """Pipelined Wishbone transfer. ``beats`` = (we, adr, dat, sel). Returns
        the ack-ordered ``wb_dat_r`` values (reads and writes both ack).
        ``gaps[i]`` idle clocks inserted before beat i."""
        d = self.dut
        n = len(beats)
        got: List[int] = []
        i = 0
        gap_left = gaps[0] if gaps else 0
        stalls = 0

        def drive(k):
            we, adr, dat, sel = beats[k]
            d.wb_cyc.value, d.wb_stb.value, d.wb_we.value = 1, 1, we
            d.wb_adr.value, d.wb_dat_w.value, d.wb_sel.value = adr, dat, sel

        def idle():
            d.wb_stb.value = 0

        d.wb_cyc.value = 1
        if gap_left:
            idle()
        else:
            drive(0)
        for _ in range(timeout_clk):
            await RisingEdge(d.clk)
            stall = int(d.wb_stall.value)
            if int(d.wb_ack.value):
                got.append(int(d.wb_dat_r.value))
                self.acks.append((now_ns(), got[-1]))
            if i < n:
                if gap_left:
                    gap_left -= 1
                    if gap_left == 0:
                        drive(i)
                elif stall:
                    stalls += 1
                else:
                    i += 1
                    if i < n:
                        gap_left = gaps[i] if gaps else 0
                        idle() if gap_left else drive(i)
                    else:
                        idle()
            if i >= n and len(got) >= n:
                break
        else:
            raise AssertionError(f"transfer timed out: issued {i}/{n}, acked {len(got)}")
        d.wb_cyc.value = 0
        d.wb_stb.value = 0
        self.stalls = stalls
        await RisingEdge(d.clk)
        assert not int(d.wb_ack.value), "extra ack after the last beat"
        return got

    async def write(self, adr, dats, sels=None, gaps=None, reg=False):
        base = adr | (REG_SPACE if reg else 0)
        beats = [(1, base + k, dat, 0xF if sels is None else sels[k]) for k, dat in enumerate(dats)]
        return await self.xfer(beats, gaps)

    async def read(self, adr, n=1, gaps=None, reg=False):
        base = adr | (REG_SPACE if reg else 0)
        return await self.xfer([(0, base + k, 0, 0xF) for k in range(n)], gaps)

    async def idle(self, clks):
        for _ in range(clks):
            await RisingEdge(self.dut.clk)

    # --------------------------------------------------------------- checks
    def mem_beat(self, adr: int) -> int:
        b = 4 * adr
        return beat_from_bytes(bytes(self.model.mem[b:b + 4]))

    def max_cs_low_ns(self) -> float:
        return max((t.cs_low_ns or 0.0) for t in self.model.transactions) if self.model.transactions else 0.0


def seeded(seed: int) -> random.Random:
    print(f"random seed {seed}")
    return random.Random(seed)
