"""Self-test for the device model: a trivial host driver exercises CA decode,
latency (variable, doubled, fixed), linear bursts, RWDS write masking,
register space, power-up, and the tCSM violation flag (with its negative
control). No simulator or DUT needed: `python3 -m unittest -v`.

The timing values below are PLACEHOLDERS chosen for functional coverage.
They are not datasheet numbers; spec/device-model-params.md is still TBD(src).
"""
import unittest

from model import (CR0_FIXED_LATENCY_BIT, REG_CR0, REG_ID0, REG_ID1,
                   HyperRamModel, ModelParams, ca_bytes)

PLACEHOLDER = ModelParams(
    t_ck_min_ns=20.0, t_css_ns=2.0, t_csh_ns=2.0, t_cshi_ns=10.0,
    t_csm_ns=400.0, t_ckd_ns=3.0, t_ckds_ns=3.0, initial_latency_clk=3,
    power_up_ns=1000.0, id0=0x0C81, id1=0x0001, cr0_reset=0x0000,
    cr1_reset=0x0002,
)
HALF = 10.0  # half CK period, ns (50 MHz)


class Host:
    """Minimal host: drives CS#/CK/DQ/RWDS against the model, keeps time."""

    def __init__(self, model, t=2000.0):
        self.m, self.t = model, t

    def _edge(self, dq=None, rwds=None):
        self.t += HALF
        self._ck ^= 1
        return self.m.clock(self.t, self._ck, dq, rwds)

    def begin(self, ca):
        self.m.cs_fall(self.t)
        self.t += 5.0
        self._ck = 0
        self.ca_rwds = None
        for b in ca:
            out = self._edge(dq=b)
            self.ca_rwds = out.rwds
        return self.ca_rwds

    def end(self):
        self.t += 5.0
        self.m.cs_rise(self.t)
        self.t += 20.0

    def idle(self, edges):
        for _ in range(edges):
            self._edge()

    def read(self, word, nwords, register=False):
        rwds_ca = self.begin(ca_bytes(word, True, register))
        lat = self.m.p.initial_latency_clk * (2 if rwds_ca else 1)
        self.idle(2 * lat)
        data = [self._edge().dq for _ in range(2 * nwords)]
        self.end()
        return bytes(data)

    def write(self, word, data, mask=None, register=False):
        rwds_ca = self.begin(ca_bytes(word, False, register))
        lat = 0 if register else self.m.p.initial_latency_clk * (2 if rwds_ca else 1)
        self.idle(2 * lat)
        for i, b in enumerate(data):
            self._edge(dq=b, rwds=(mask[i] if mask else 0))
        self.end()


class ModelSelfTest(unittest.TestCase):
    def setUp(self):
        print("\nplaceholder model params (NOT datasheet values):")
        print(PLACEHOLDER.describe())
        self.m = HyperRamModel(PLACEHOLDER)
        self.h = Host(self.m)

    def test_ca_decode_and_linear_burst(self):
        self.h.write(0x1235, bytes([1, 2, 3, 4, 5, 6]))
        t = self.m.transactions[-1]
        self.assertEqual((t.is_read, t.is_register, t.linear, t.word_addr),
                         (False, False, True, 0x1235))
        self.assertEqual(self.m.mem[0x1235 * 2:0x1235 * 2 + 6], bytes([1, 2, 3, 4, 5, 6]))
        self.assertEqual(self.h.read(0x1235, 3), bytes([1, 2, 3, 4, 5, 6]))
        self.m.assert_clean()

    def test_read_rwds_edge_aligned_with_data(self):
        self.m.mem[0:4] = b"\xaa\xbb\xcc\xdd"
        self.h.begin(ca_bytes(0, True))
        self.h.idle(2 * 3)
        outs = [self.h._edge() for _ in range(4)]
        self.assertEqual([o.rwds for o in outs], [1, 0, 1, 0])
        self.assertEqual([o.dq for o in outs], [0xAA, 0xBB, 0xCC, 0xDD])
        self.assertEqual(outs[0].dq_delay_ns, PLACEHOLDER.t_ckd_ns)
        self.h.end()

    def test_skew_knob_moves_dq_against_rwds(self):
        m = HyperRamModel(ModelParams(**{**PLACEHOLDER.__dict__, "dq_skew_ns": 1.5}))
        h = Host(m)
        h.begin(ca_bytes(0, True))
        h.idle(6)
        out = h._edge()
        self.assertEqual(out.dq_delay_ns - out.rwds_delay_ns, 1.5)

    def test_latency_variable_normal_and_doubled(self):
        self.assertEqual(self.h.begin(ca_bytes(0, True)), 0)
        self.h.end()
        self.assertEqual(self.m.transactions[-1].latency_clk, 3)
        self.m.request_extra_latency = True
        self.assertEqual(self.h.begin(ca_bytes(0, True)), 1)
        self.h.end()
        self.assertEqual(self.m.transactions[-1].latency_clk, 6)
        self.assertTrue(self.m.transactions[-1].extra_latency)

    def test_doubled_latency_data_timing(self):
        self.m.mem[0:2] = b"\x12\x34"
        self.m.request_extra_latency = True
        self.assertEqual(self.h.read(0, 1), b"\x12\x34")

    def test_fixed_latency_via_cr0(self):
        self.h.write(REG_CR0, bytes([0, 1 << CR0_FIXED_LATENCY_BIT]), register=True)
        self.assertTrue(self.m.fixed_latency)
        self.assertEqual(self.h.begin(ca_bytes(0, True)), 1)  # always doubled
        self.h.end()
        self.assertEqual(self.m.transactions[-1].latency_clk, 6)

    def test_write_mask(self):
        self.m.mem[0:4] = b"\x11\x22\x33\x44"
        self.h.write(0, bytes([0xA1, 0xA2, 0xA3, 0xA4]), mask=[1, 0, 0, 1])
        self.assertEqual(bytes(self.m.mem[0:4]), b"\x11\xa2\xa3\x44")
        self.assertEqual(self.m.transactions[-1].bytes_masked, 2)
        self.m.assert_clean()

    def test_register_space(self):
        self.assertEqual(self.h.read(REG_ID0, 1, register=True), b"\x0c\x81")
        self.assertEqual(self.h.read(REG_ID1, 1, register=True), b"\x00\x01")
        self.h.write(REG_CR0, b"\xab\xcd", register=True)
        self.assertEqual(self.h.read(REG_CR0, 1, register=True), b"\xab\xcd")
        self.h.write(REG_ID0, b"\xff\xff", register=True)  # read-only
        self.assertEqual(self.h.read(REG_ID0, 1, register=True), b"\x0c\x81")
        self.assertEqual(self.m.transactions[-4].latency_clk, 0)  # reg write: no latency
        self.m.assert_clean()

    def test_reset_restores_registers_and_powerup_check(self):
        self.h.write(REG_CR0, b"\xab\xcd", register=True)
        self.m.reset_assert(self.h.t)
        self.m.reset_release(self.h.t + 100)
        self.assertEqual(self.m.regs[REG_CR0], PLACEHOLDER.cr0_reset)
        self.h.t += 200  # only 100 ns after release: too early
        self.h.read(0, 1)
        self.assertEqual(len(self.m.violations_of("power_up")), 1)

    def test_tcsm_flag_negative_control_and_boundary(self):
        # words so that CS# low stays within, then beyond, tCSM (400 ns).
        # CS# low = 5 + 10*(6 CA + 6 latency + 2*n data edges) + 5.
        ok = (400 - 10 - 120) // 20       # 13 words -> 5+10*(12+26)+5 = 390 ns
        self.h.read(0, ok)
        self.assertEqual(self.m.violations_of("tCSM"), [])
        self.h.read(0, ok + 2)            # 430 ns, beyond tCSM
        flagged = self.m.violations_of("tCSM")
        self.assertEqual(len(flagged), 1)
        self.assertGreater(self.m.transactions[-1].cs_low_ns, PLACEHOLDER.t_csm_ns)

    def test_cs_high_time_and_other_named_checks(self):
        self.h.begin(ca_bytes(0, True))
        self.m.cs_rise(self.h.t + 5)
        self.m.cs_fall(self.h.t + 5 + 4)  # 4 ns high < tCSHI
        self.assertEqual(len(self.m.violations_of("tCSHI")), 1)

    def test_every_violation_names_a_spec_parameter(self):
        self.h.read(0, 40)
        self.assertTrue(all(v.param for v in self.m.violations))


if __name__ == "__main__":
    unittest.main()
