"""Self-test for the device model: a trivial host driver exercises CA decode,
latency (variable, doubled, fixed), linear bursts, RWDS write masking,
register space, power-up, and the tCSM and ck_phase violation flags (each
with its negative control). No simulator or DUT needed:
`python3 -m unittest -v`.

The timing values are the one PLACEHOLDER set defined beside the model
(``model.PLACEHOLDER``), chosen for functional coverage. They are not
datasheet numbers; every spec/device-model-params.md row but tCKD/tCKDS
is still TBD(src).
Nothing below restates one of those numbers: every expectation is derived
from PLACEHOLDER, so a value ratified by #2 is entered once, in model.py.
"""
import dataclasses
import unittest

from model import (CR0_FIXED_LATENCY_BIT, PLACEHOLDER, REG_CR0, REG_ID0,
                   REG_ID1, HyperRamModel, ca_bytes)

HALF = 10.0                                   # half CK period, ns (50 MHz)
LAT = PLACEHOLDER.initial_latency_clk         # CK cycles, CA included
CS_PAD_NS = 5.0                               # Host pad either side of CS# low
# Host gap between transactions: one CK period, but never shorter than tCSHI.
CS_HIGH_NS = max(2 * HALF, PLACEHOLDER.t_cshi_ns + HALF)


def latency_idle_edges(lat=LAT):
    """Edges ``Host`` must idle after CA before the first data edge: latency
    is ``2 * lat`` half-periods from the first CA edge, and CA took 6."""
    return 2 * lat - 6


def read_cs_low_ns(nwords, lat=LAT):
    """CS# low time of ``Host.read(_, nwords)``: a CS_PAD_NS pad at each end
    plus one HALF per CK edge (6 CA + latency_idle_edges + 2 * nwords data)."""
    return 2 * CS_PAD_NS + HALF * (2 * lat + 2 * nwords)


def words_within_tcsm(lat=LAT):
    """Largest ``Host.read`` word count whose CS# low still fits inside tCSM."""
    return int((PLACEHOLDER.t_csm_ns - 2 * CS_PAD_NS - 2 * HALF * lat) // (2 * HALF))


class Host:
    """Minimal host: drives CS#/CK/DQ/RWDS against the model, keeps time.

    ``first_edge_rising=False`` inverts every CK level (CK idling high, so CA
    launches on a falling edge). The model must reject that; nothing else
    about the transaction changes, which is why the check is needed.
    """

    def __init__(self, model, t=2000.0, first_edge_rising=True):
        self.m, self.t = model, t
        self.first_edge_rising = first_edge_rising

    def _edge(self, dq=None, rwds=None):
        self.t += HALF
        self._ck ^= 1
        return self.m.clock(self.t, self._ck, dq, rwds)

    def begin(self, ca):
        self.m.cs_fall(self.t)
        self.t += CS_PAD_NS
        self._ck = 0 if self.first_edge_rising else 1
        self.ca_rwds = None
        for b in ca:
            out = self._edge(dq=b)
            self.ca_rwds = out.rwds
        return self.ca_rwds

    def end(self):
        self.t += CS_PAD_NS
        self.m.cs_rise(self.t)
        self.t += CS_HIGH_NS

    def idle(self, edges):
        for _ in range(edges):
            self._edge()

    def read(self, word, nwords, register=False):
        rwds_ca = self.begin(ca_bytes(word, True, register))
        lat = self.m.p.initial_latency_clk * (2 if rwds_ca else 1)
        self.idle(2 * lat - 6)
        data = [self._edge().dq for _ in range(2 * nwords)]
        self.end()
        return bytes(data)

    def write(self, word, data, mask=None, register=False):
        rwds_ca = self.begin(ca_bytes(word, False, register))
        lat = 0 if register else self.m.p.initial_latency_clk * (2 if rwds_ca else 1)
        self.idle(2 * lat - 6 if lat else 0)
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
        self.h.idle(latency_idle_edges())
        outs = [self.h._edge() for _ in range(4)]
        self.assertEqual([o.rwds for o in outs], [1, 0, 1, 0])
        self.assertEqual([o.dq for o in outs], [0xAA, 0xBB, 0xCC, 0xDD])
        self.assertEqual(outs[0].dq_delay_ns, PLACEHOLDER.t_ckd_ns)
        self.h.end()

    def test_skew_knob_moves_dq_against_rwds(self):
        m = HyperRamModel(dataclasses.replace(PLACEHOLDER, dq_skew_ns=1.5))
        h = Host(m)
        h.begin(ca_bytes(0, True))
        h.idle(latency_idle_edges())
        out = h._edge()
        self.assertEqual(out.dq_delay_ns, PLACEHOLDER.t_ckd_ns + 1.5)
        self.assertEqual(out.rwds_delay_ns, PLACEHOLDER.t_ckds_ns)

    def test_latency_variable_normal_and_doubled(self):
        self.assertEqual(self.h.begin(ca_bytes(0, True)), 0)
        self.h.end()
        self.assertEqual(self.m.transactions[-1].latency_clk, LAT)
        self.m.request_extra_latency = True
        self.assertEqual(self.h.begin(ca_bytes(0, True)), 1)
        self.h.end()
        self.assertEqual(self.m.transactions[-1].latency_clk, 2 * LAT)
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
        self.assertEqual(self.m.transactions[-1].latency_clk, 2 * LAT)

    def test_write_mask(self):
        self.m.mem[0:4] = b"\x11\x22\x33\x44"
        self.h.write(0, bytes([0xA1, 0xA2, 0xA3, 0xA4]), mask=[1, 0, 0, 1])
        self.assertEqual(bytes(self.m.mem[0:4]), b"\x11\xa2\xa3\x44")
        self.assertEqual(self.m.transactions[-1].bytes_masked, 2)
        self.m.assert_clean()

    def test_register_space(self):
        id0, id1 = (w.to_bytes(2, "big") for w in (PLACEHOLDER.id0, PLACEHOLDER.id1))
        self.assertEqual(self.h.read(REG_ID0, 1, register=True), id0)
        self.assertEqual(self.h.read(REG_ID1, 1, register=True), id1)
        self.h.write(REG_CR0, b"\xab\xcd", register=True)
        self.assertEqual(self.h.read(REG_CR0, 1, register=True), b"\xab\xcd")
        self.h.write(REG_ID0, b"\xff\xff", register=True)  # read-only
        self.assertEqual(self.h.read(REG_ID0, 1, register=True), id0)
        self.assertEqual(self.m.transactions[-4].latency_clk, 0)  # reg write: no latency
        self.m.assert_clean()

    def test_reset_restores_registers_and_powerup_check(self):
        self.h.write(REG_CR0, b"\xab\xcd", register=True)
        self.m.reset_assert(self.h.t)
        released = self.h.t + 100
        self.m.reset_release(released)
        self.assertEqual(self.m.regs[REG_CR0], PLACEHOLDER.cr0_reset)
        # Start the read halfway into the power-up interval: too early.
        self.h.t = released + PLACEHOLDER.power_up_ns / 2
        self.h.read(0, 1)
        self.assertEqual(len(self.m.violations_of("power_up")), 1)

    def test_tcsm_flag_negative_control_and_boundary(self):
        # The largest read that stays within tCSM, then one that goes beyond.
        # Asserted both ways first, so a future PLACEHOLDER change that broke
        # the derivation would fail here instead of quietly testing nothing.
        ok = words_within_tcsm()
        self.assertGreaterEqual(ok, 1)
        self.assertLessEqual(read_cs_low_ns(ok), PLACEHOLDER.t_csm_ns)
        self.assertGreater(read_cs_low_ns(ok + 2), PLACEHOLDER.t_csm_ns)
        self.h.read(0, ok)
        self.assertEqual(self.m.violations_of("tCSM"), [])
        self.h.read(0, ok + 2)
        flagged = self.m.violations_of("tCSM")
        self.assertEqual(len(flagged), 1)
        self.assertGreater(self.m.transactions[-1].cs_low_ns, PLACEHOLDER.t_csm_ns)

    def test_ck_phase_flag_negative_control(self):
        """The model reads the CK level it is passed (#86).

        Positive control first: a read driven on the documented phase records
        no ``ck_phase`` violation. Then the same read with every CK level
        inverted -- identical bytes, identical edge count -- is flagged, once,
        by name. Without the check both runs look alike, so a controller that
        launched CA half a cycle off would pass every bench.
        """
        self.m.mem[0:4] = b"\x11\x22\x33\x44"
        good = self.h.read(0, 2)
        self.assertEqual(self.m.violations_of("ck_phase"), [])
        self.m.assert_clean()

        bad_model = HyperRamModel(PLACEHOLDER)
        bad_model.mem[0:4] = b"\x11\x22\x33\x44"
        bad = Host(bad_model, first_edge_rising=False).read(0, 2)
        # Data is unaffected -- byte order comes from the edge count, not the
        # level -- so the violation is the only thing that distinguishes them.
        self.assertEqual(bad, good)
        flagged = bad_model.violations_of("ck_phase")
        self.assertEqual(len(flagged), 1, flagged)
        self.assertIn("edge 0", flagged[0].detail)
        self.assertIn("falling", flagged[0].detail)

    def test_ck_phase_flags_a_single_slipped_edge(self):
        """A phase slip part-way through a transaction is flagged too, at the
        edge where it starts, and not again for the rest of the burst."""
        self.h.begin(ca_bytes(0, True))
        self.assertEqual(self.m.violations_of("ck_phase"), [])
        # Repeat the current level instead of toggling: one stuck/duplicated
        # CK edge, from here on every edge is on the wrong phase.
        self.h.t += HALF
        self.m.clock(self.h.t, self.h._ck)
        self.h.idle(latency_idle_edges() - 1)
        [self.h._edge() for _ in range(2)]
        self.h.end()
        flagged = self.m.violations_of("ck_phase")
        self.assertEqual(len(flagged), 1, flagged)
        self.assertIn("edge 6", flagged[0].detail)

    def test_cs_high_time_and_other_named_checks(self):
        self.h.begin(ca_bytes(0, True))
        self.m.cs_rise(self.h.t + 5)
        # CS# high for half of tCSHI: too short, whatever tCSHI is set to.
        self.m.cs_fall(self.h.t + 5 + PLACEHOLDER.t_cshi_ns / 2)
        self.assertEqual(len(self.m.violations_of("tCSHI")), 1)

    def test_every_violation_names_a_spec_parameter(self):
        self.h.read(0, words_within_tcsm() + 2)   # long enough to trip tCSM
        self.assertTrue(self.m.violations, "read did not trip any check")
        self.assertTrue(all(v.param for v in self.m.violations))


if __name__ == "__main__":
    unittest.main()
