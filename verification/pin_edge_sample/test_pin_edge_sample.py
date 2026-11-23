"""The pad driver's pin-edge sample is the settled pin value (issue #205).

``hrbench.Bench._ck_mon`` at ``HRBENCH_SAMPLE_NS=0`` (the mode
flow/functional-verification-ctrl-sdf.json selects, and this Makefile) reads
DQ, RWDS and their output enables in the timestep of the ``hb_ck`` edge that
wakes it. ``pin_edge_host`` is a stand-in host that moves those pins at a
selectable offset from its own CK edge; the real monitor runs over it, and
for every offset this module asserts:

* what the monitor handed the device model is the pins' settled value at the
  end of the CK edge's timestep: the new value for a change in the same
  timestep or 1 ps before the edge, the old value for a change 1 ps after.
  A read in the wake-up timestep itself is order-dependent -- on the
  same-timestep cases it returns whichever update the simulator applied
  first, a wrong byte with nothing raised;
* the model's outputs keep their edge-relative delays (tCKD, tCKDS plus the
  RWDS eye offset): the read-phase sync adds no time offset.

Not a controller or device claim: the model runs on the bench placeholder
parameters and the host is a fixture.
"""

import cocotb
from cocotb.triggers import Timer
from cocotb.utils import get_sim_time

import hrbench
from hrbench import Bench
from model import HyperRamModel, ca_bytes

CK_FIRST, PINS_FIRST, PINS_BEFORE, PINS_AFTER = range(4)
SKEWS = {
    "pins change in the CK edge's timestep, CK updated first": CK_FIRST,
    "pins change in the CK edge's timestep, pins updated first": PINS_FIRST,
    "pins change 1 ps before the CK edge": PINS_BEFORE,
    "pins change 1 ps after the CK edge": PINS_AFTER,
}
IDLE = (0x00, 0, 0, 0)
STEP_NS = 22
WORD = 0x8101E
READ_DATA = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]
WRITE_DATA = [0xAA, 0xBB, 0xCC, 0xDD]
WRITE_MASK = [1, 0, 1, 0]
CA_EDGES = 6
LATENCY_EDGES = 6
READ_DQ_DELAY_NS = 6
READ_RWDS_DELAY_NS = 11


def edge(k):
    return 1 - k % 2


def settled(host):
    return [(edge(k), dq if dq_oe else None, rwds if rwds_oe else None)
            for k, (dq, dq_oe, rwds, rwds_oe) in enumerate(host)]


async def step(dut, skew, dq, dq_oe, rwds, rwds_oe):
    dut.skew.value = skew
    dut.dq_in.value, dut.dq_oe_in.value = dq, dq_oe
    dut.rwds_in.value, dut.rwds_oe_in.value = rwds, rwds_oe
    await Timer(1, unit="ns")
    dut.step.value = 1
    await Timer(1, unit="ns")
    dut.step.value = 0
    await Timer(STEP_NS, unit="ns")


async def transaction(dut, bench, skew, host, ck_log):
    """Select the host and present ``host[i]`` = (dq, dq_oe, rwds, rwds_oe) at
    CK edge i; return the samples the monitor took at those edges and the
    simulator timestamps (ps) of the edges themselves."""
    await step(dut, skew, *IDLE)
    await step(dut, skew, *host[0])
    first, edges = len(bench.samples), len(ck_log)
    dut.hb_cs_n.value = 0
    await Timer(30, unit="ns")
    for k in range(len(host)):
        ahead = host[k + 1] if k + 1 < len(host) else host[k]
        await step(dut, skew, *(ahead if skew == PINS_AFTER else host[k]))
    dut.hb_cs_n.value = 1
    await Timer(40, unit="ns")
    return bench.samples[first:], [t for t, _ in ck_log[edges:]]


def watch(dut, name, log):
    async def run():
        while True:
            await getattr(dut, name).value_change
            value = getattr(dut, name).value
            if value.is_resolvable:
                log.append((get_sim_time("ps"), int(value)))

    return cocotb.start_soon(run())


def decode(info):
    return (info.is_read, info.is_register, info.linear, info.word_addr, info.latency_clk,
            info.extra_latency, info.bytes_transferred, info.bytes_masked)


@cocotb.test()
async def pin_edge_sample_is_the_settled_value(dut):
    assert hrbench.SAMPLE_NS == 0, "this suite runs at HRBENCH_SAMPLE_NS=0"
    bench = Bench(dut)
    bench.samples = []

    def recording(t_ns, ck, dq_in=None, rwds_in=None):
        bench.samples.append((t_ns, ck, dq_in, rwds_in))
        return HyperRamModel.clock(bench.model, t_ns, ck, dq_in, rwds_in)

    def fresh_model():
        bench.model = HyperRamModel(bench.params, hrbench.MEM_BYTES)
        bench.model.clock = recording
        bench.model.mem[base:base + len(READ_DATA)] = bytes(READ_DATA)

    dut.hb_cs_n.value = 1
    await Timer(1, unit="ns")
    cocotb.start_soon(bench._cs_mon())
    dq_log, rwds_log, ck_log = [], [], []
    watch(dut, "hb_dq_i", dq_log)
    watch(dut, "hb_rwds_i", rwds_log)
    watch(dut, "hb_ck", ck_log)

    read_ca, write_ca = ca_bytes(WORD, read=True), ca_bytes(WORD, read=False)
    assert len(set(read_ca)) == len(set(write_ca)) == CA_EDGES
    base = WORD * 2
    read_host = [(b, 1, 0, 0) for b in read_ca] + [IDLE] * (LATENCY_EDGES + len(READ_DATA))
    write_host = ([(b, 1, 0, 0) for b in write_ca] + [IDLE] * LATENCY_EDGES
                  + list(zip(WRITE_DATA, [1] * 4, WRITE_MASK, [1] * 4)))
    data_first = CA_EDGES + LATENCY_EDGES
    data_last = data_first + len(READ_DATA) - 1

    failures = []
    for label, skew in SKEWS.items():
        fresh_model()
        raised = []

        async def ck_mon():
            try:
                await bench._ck_mon()
            except AssertionError as exc:
                raised.append(f"{type(exc).__name__}: {exc}")

        monitor = cocotb.start_soon(ck_mon())

        def check(name, got, want):
            if got != want:
                failures.append(f"{label} / {name}:\n   got      {got}\n   expected {want}")

        def alive(host, count):
            if raised:
                failures.append(f"{label} / the pad monitor raised {raised[0]}")
            elif count != len(host):
                failures.append(f"{label} / the pad monitor sampled {count} of"
                                f" {len(host)} CK edges")
            return not raised and count == len(host)

        samples, edge_ps = await transaction(dut, bench, skew, read_host, ck_log)
        check("read CA sample", [s[1:] for s in samples], settled(read_host))
        if alive(read_host, len(samples)):
            until = edge_ps[data_last] + READ_RWDS_DELAY_NS * 1000
            def drive(log):
                return [(t, v) for t, v in log if edge_ps[data_first] <= t <= until]
            check("read DQ drive", drive(dq_log),
                  [(edge_ps[data_first + j] + READ_DQ_DELAY_NS * 1000, b)
                   for j, b in enumerate(READ_DATA)])
            check("read RWDS drive", drive(rwds_log),
                  [(edge_ps[data_first + j] + READ_RWDS_DELAY_NS * 1000, 1 - j % 2)
                   for j in range(len(READ_DATA))])
            check("read CA decoded", decode(bench.model.transactions[-1]),
                  (True, False, True, WORD, 6, False, len(READ_DATA), 0))
        dq_log.clear()
        rwds_log.clear()

        samples, _ = await transaction(dut, bench, skew, write_host, ck_log)
        check("write sample", [s[1:] for s in samples], settled(write_host))
        if alive(write_host, len(samples)):
            check("write decoded", decode(bench.model.transactions[-1]),
                  (False, False, True, WORD, 6, False, len(WRITE_DATA), sum(WRITE_MASK)))
            kept = [byte if mask else new
                    for byte, new, mask in zip(READ_DATA, WRITE_DATA, WRITE_MASK)]
            check("bytes written under RWDS masking",
                  list(bench.model.mem[base:base + len(WRITE_DATA)]), kept)
            check("model violations", [str(v) for v in bench.model.violations], [])
        monitor.cancel()
    assert not failures, "\n".join(failures)
