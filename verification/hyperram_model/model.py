"""Behavioural device model for the HyperBus-class interface.

Written from the public interface definition cited in
``spec/device-model-params.md`` (HyperBus Specification, doc 001-99253,
Rev. *C). No vendor model is imported; no part is named or targeted, and
nothing here claims conformance to a particular device.

The model is a pure-Python, edge-level state machine so it can be exercised
without a simulator (``test_model.py``) and wrapped by a cocotb pad driver
for the controller benches. The caller supplies the simulation time in ns on
every pin event; the model never reads a wall clock.

Timing values are *inputs*: ``ModelParams`` has no defaults for them. While
the rows of ``spec/device-model-params.md`` read ``TBD(src)``, benches pass
placeholder values chosen for functional coverage and must say so in their
output (``ModelParams.describe``). Every check names its parameter; a
violation is recorded in ``HyperRamModel.violations`` and a bench fails on any
it did not expect (``assert_clean``).

Interface assumptions (public definition, restated so a reviewer can check):
  * CA is 6 bytes on the first 3 CK cycles (a byte per CK edge, DDR):
    CA[47] = read(1)/write(0), CA[46] = register space(1)/memory(0),
    CA[45] = linear(1)/wrapped(0) burst,
    word address = {CA[44:16], CA[2:0]} (16-bit words).
  * The device drives RWDS during CA: high requests doubled initial latency.
    In fixed-latency mode (CR0[3] = 1) latency is always doubled.
  * Latency is counted in CK cycles from the end of CA. Register writes have
    zero latency; register reads and memory reads/writes use it.
  * Read data is edge-aligned with RWDS (RWDS high on the first byte of each
    word). Write data is centre-aligned; RWDS high on a write byte masks it
    (memory space only).
  * Not modelled here: wrapped bursts (out of v1 scope; flagged as
    ``burst_type``), the CR0 latency-field encoding, and sub-edge DQ
    setup/hold (tIS/tIH).
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import List, Optional

CA_BYTES = 6

# Register-space word addresses.
REG_ID0 = 0x000000
REG_ID1 = 0x000001
REG_CR0 = 0x000800
REG_CR1 = 0x000801
CR0_FIXED_LATENCY_BIT = 3


@dataclass(frozen=True)
class ModelParams:
    """Timing and identity inputs. No defaults for datasheet values.

    Times in ns. Each field maps to a row of ``spec/device-model-params.md``.
    """

    t_ck_min_ns: float        # tCK    : minimum clock period
    t_css_ns: float           # tCSS   : CS# low to first CK edge, minimum
    t_csh_ns: float           # tCSH   : last CK edge to CS# high, minimum
    t_cshi_ns: float          # tCSHI  : CS# high between transactions, minimum
    t_csm_ns: float           # tCSM   : CS# low maximum
    t_ckd_ns: float           # tCKD   : CK edge to read data output delay
    t_ckds_ns: float          # tCKDS  : CK edge to RWDS output delay
    initial_latency_clk: int  # initial latency count, CK cycles
    power_up_ns: float        # reset / power-up: RESET# high to first access
    id0: int                  # identification register 0 content
    id1: int                  # identification register 1 content
    cr0_reset: int            # CR0 value after reset
    cr1_reset: int            # CR1 value after reset
    # Fault-injection knobs for the read-capture margin sweep. Zero is "none";
    # these are test stimulus, not datasheet values.
    dq_skew_ns: float = 0.0     # extra delay of read DQ relative to nominal tCKD
    rwds_skew_ns: float = 0.0   # extra delay of RWDS relative to nominal tCKDS

    def describe(self) -> str:
        return "\n".join(f"  {f.name} = {getattr(self, f.name)}" for f in fields(self))


@dataclass(frozen=True)
class Violation:
    param: str      # the parameter the check names (spec/device-model-params.md)
    t_ns: float
    detail: str


@dataclass(frozen=True)
class PadOutput:
    """What the device drives after a CK edge. Delays are from that edge."""

    dq: Optional[int]       # None when the device does not drive DQ
    rwds: Optional[int]     # None when the device does not drive RWDS
    dq_delay_ns: float = 0.0
    rwds_delay_ns: float = 0.0


@dataclass
class Transaction:
    is_read: bool
    is_register: bool
    linear: bool
    word_addr: int
    latency_clk: int            # total latency applied (0 for register write)
    extra_latency: bool         # RWDS high during CA
    t_cs_fall_ns: float
    t_cs_rise_ns: Optional[float] = None
    bytes_transferred: int = 0  # data bytes moved (read out or write in)
    bytes_masked: int = 0
    cs_low_ns: Optional[float] = None


@dataclass
class _Txn:
    start_ns: float
    last_edge_ns: Optional[float] = None
    edge_idx: int = 0
    ca: List[int] = field(default_factory=list)
    info: Optional[Transaction] = None
    data_start: int = 0
    byte_addr: int = 0
    pending_hi: Optional[int] = None
    extra: bool = False
    tcsm_flagged: bool = False


class HyperRamModel:
    def __init__(self, params: ModelParams, mem_bytes: int = 1 << 16):
        self.p = params
        self.mem = bytearray(mem_bytes)
        self.violations: List[Violation] = []
        self.transactions: List[Transaction] = []
        # Test stimulus: when True the device raises RWDS during CA of the next
        # transactions (a stand-in for a refresh collision).
        self.request_extra_latency = False
        self._reset_regs()
        self._txn: Optional[_Txn] = None
        self._cs_low = False
        self._reset_n = True
        # Powered up long ago unless a bench calls reset_assert/reset_release.
        self._reset_released_ns: Optional[float] = -params.power_up_ns
        self._cs_rose_ns: Optional[float] = None

    # ------------------------------------------------------------- state
    def _reset_regs(self):
        self.regs = {
            REG_ID0: self.p.id0,
            REG_ID1: self.p.id1,
            REG_CR0: self.p.cr0_reset,
            REG_CR1: self.p.cr1_reset,
        }

    @property
    def fixed_latency(self) -> bool:
        return bool((self.regs[REG_CR0] >> CR0_FIXED_LATENCY_BIT) & 1)

    def _flag(self, param: str, t_ns: float, detail: str):
        self.violations.append(Violation(param, t_ns, detail))

    def violations_of(self, param: str) -> List[Violation]:
        return [v for v in self.violations if v.param == param]

    def assert_clean(self):
        assert not self.violations, "device-model violations:\n" + "\n".join(
            f"  {v.param} @ {v.t_ns} ns: {v.detail}" for v in self.violations
        )

    # --------------------------------------------------------- reset / CS
    def reset_assert(self, t_ns: float):
        """RESET# low: abort any transaction, registers return to reset values."""
        self._reset_n = False
        self._reset_released_ns = None
        self._txn = None
        self._cs_low = False
        self._reset_regs()

    def reset_release(self, t_ns: float):
        self._reset_n = True
        self._reset_released_ns = t_ns

    def cs_fall(self, t_ns: float):
        assert not self._cs_low, "CS# fell twice"
        if (not self._reset_n or self._reset_released_ns is None
                or t_ns - self._reset_released_ns < self.p.power_up_ns):
            self._flag("power_up", t_ns, "access before reset/power-up interval elapsed")
        if self._cs_rose_ns is not None and t_ns - self._cs_rose_ns < self.p.t_cshi_ns:
            self._flag("tCSHI", t_ns, f"CS# high {t_ns - self._cs_rose_ns} ns")
        self._cs_low = True
        self._txn = _Txn(start_ns=t_ns)
        self._txn.extra = self.fixed_latency or self.request_extra_latency

    def cs_rise(self, t_ns: float):
        assert self._cs_low, "CS# rose while high"
        txn = self._txn
        if txn.last_edge_ns is not None and t_ns - txn.last_edge_ns < self.p.t_csh_ns:
            self._flag("tCSH", t_ns, f"{t_ns - txn.last_edge_ns} ns after last CK edge")
        self._check_tcsm(txn, t_ns)
        if txn.info is not None:
            txn.info.t_cs_rise_ns = t_ns
            txn.info.cs_low_ns = t_ns - txn.start_ns
        self._cs_low = False
        self._txn = None
        self._cs_rose_ns = t_ns

    def _check_tcsm(self, txn: _Txn, t_ns: float):
        if not txn.tcsm_flagged and t_ns - txn.start_ns > self.p.t_csm_ns:
            txn.tcsm_flagged = True
            self._flag("tCSM", t_ns, f"CS# low {t_ns - txn.start_ns} ns")

    # --------------------------------------------------------- CK edges
    def clock(self, t_ns: float, ck: int, dq_in: Optional[int] = None,
              rwds_in: Optional[int] = None) -> PadOutput:
        """One CK edge (``ck`` is the new level, 1 = rising). Pins are the
        values sampled at the edge. Returns what the device drives from this
        edge on. With CS# high the edge is ignored and nothing is driven.
        """
        if not self._cs_low:
            return PadOutput(None, None)
        txn = self._txn
        if txn.edge_idx == 0 and t_ns - txn.start_ns < self.p.t_css_ns:
            self._flag("tCSS", t_ns, f"first CK edge {t_ns - txn.start_ns} ns after CS#")
        if txn.last_edge_ns is not None and (t_ns - txn.last_edge_ns) * 2 < self.p.t_ck_min_ns:
            self._flag("tCK", t_ns, f"half period {t_ns - txn.last_edge_ns} ns")
        txn.last_edge_ns = t_ns
        self._check_tcsm(txn, t_ns)

        i = txn.edge_idx
        txn.edge_idx += 1
        rwds_delay = self.p.t_ckds_ns + self.p.rwds_skew_ns
        if i < CA_BYTES:
            assert dq_in is not None, "DQ must be driven by the host during CA"
            txn.ca.append(dq_in & 0xFF)
            if i == CA_BYTES - 1:
                self._start_burst(txn)
            return PadOutput(None, 1 if txn.extra else 0, rwds_delay_ns=rwds_delay)
        if i < txn.data_start:
            # latency: reads drive RWDS low, writes leave the bus to the host
            return PadOutput(None, 0 if txn.info.is_read else None,
                             rwds_delay_ns=rwds_delay)
        return self._data_edge(txn, i, dq_in, rwds_in)

    def _start_burst(self, txn: _Txn):
        ca = int.from_bytes(bytes(txn.ca), "big")
        is_read = bool((ca >> 47) & 1)
        is_reg = bool((ca >> 46) & 1)
        linear = bool((ca >> 45) & 1)
        word = (((ca >> 16) & 0x1FFFFFFF) << 3) | (ca & 0x7)
        if not is_read and is_reg:
            latency = 0
        else:
            latency = self.p.initial_latency_clk * (2 if txn.extra else 1)
        txn.data_start = CA_BYTES + 2 * latency
        txn.byte_addr = word * 2
        txn.info = Transaction(is_read, is_reg, linear, word, latency, txn.extra,
                               txn.start_ns)
        self.transactions.append(txn.info)
        if not linear:
            self._flag("burst_type", txn.last_edge_ns,
                       "wrapped burst requested; only linear is modelled")

    def _data_edge(self, txn: _Txn, i: int, dq_in: Optional[int],
                   rwds_in: Optional[int]) -> PadOutput:
        info = txn.info
        t = txn.last_edge_ns
        info.bytes_transferred += 1
        if info.is_read:
            value = self._read_byte(info, txn, t)
            first_of_word = (i - txn.data_start) % 2 == 0
            return PadOutput(value, 1 if first_of_word else 0,
                             dq_delay_ns=self.p.t_ckd_ns + self.p.dq_skew_ns,
                             rwds_delay_ns=self.p.t_ckds_ns + self.p.rwds_skew_ns)
        assert dq_in is not None, "DQ must be driven by the host on write data"
        masked = (not info.is_register) and bool(rwds_in)
        if masked:
            info.bytes_masked += 1
        self._write_byte(info, txn, dq_in & 0xFF, masked, t)
        return PadOutput(None, None)

    # ------------------------------------------------------ memory / regs
    def _mem_index(self, byte_addr: int, t: float) -> Optional[int]:
        if byte_addr >= len(self.mem):
            self._flag("array_bounds", t, f"byte address {byte_addr:#x} beyond array")
            return None
        return byte_addr

    def _read_byte(self, info: Transaction, txn: _Txn, t: float) -> int:
        addr = txn.byte_addr
        txn.byte_addr += 1
        if info.is_register:
            word = self.regs.get(addr >> 1, 0)
            return (word >> (8 if addr % 2 == 0 else 0)) & 0xFF
        idx = self._mem_index(addr, t)
        return 0 if idx is None else self.mem[idx]

    def _write_byte(self, info: Transaction, txn: _Txn, value: int, masked: bool, t: float):
        addr = txn.byte_addr
        txn.byte_addr += 1
        if info.is_register:
            if addr % 2 == 0:
                txn.pending_hi = value
                return
            word_addr = addr >> 1
            word = ((txn.pending_hi or 0) << 8) | value
            txn.pending_hi = None
            if word_addr in (REG_CR0, REG_CR1):   # ID registers are read-only
                self.regs[word_addr] = word
            return
        if masked:
            return
        idx = self._mem_index(addr, t)
        if idx is not None:
            self.mem[idx] = value


def ca_bytes(word_addr: int, read: bool, register: bool = False,
             linear: bool = True) -> List[int]:
    """Host-side helper: encode the 6 CA bytes for a word address."""
    ca = (int(read) << 47) | (int(register) << 46) | (int(linear) << 45)
    ca |= ((word_addr >> 3) & 0x1FFFFFFF) << 16
    ca |= word_addr & 0x7
    return list(ca.to_bytes(CA_BYTES, "big"))
