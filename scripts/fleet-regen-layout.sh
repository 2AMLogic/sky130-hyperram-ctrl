#!/usr/bin/env bash
#
# scripts/fleet-regen-layout.sh -- regenerate the layout-dependent records on a
# Spot batch `repo-script` job (heavy image), never on a shared dispatch host.
#
#   scripts/fleet-regen-layout.sh probe   report the image's toolchain facts and
#                                         exit 0 (writes fleet-probe.txt)
#   scripts/fleet-regen-layout.sh         regenerate the netlist, the STA
#                                         records, evidence/item1.json, then
#                                         layout/records/,
#                                         layout/lvs/records/, evidence/item2.json
#                                         and the cited-evidence pins in
#                                         manifests/, re-render the signoff
#                                         record, then verify freshness
#                                         (writes fleet-regen.log)
#
# Why this script exists: `make layout` (~25 min place-and-route) and the
# synthesis/freshness half of the flow must not run on the shared dispatch
# worker (operator ruling on issue #52, 2026-11-03). It is submitted with
# infra/aws/repo-script-submit.py (2AMLogic/2am):
#
#   infra/aws/repo-script-submit.py --source-dir <checkout> --commit <sha> \
#     --repo 2AMLogic/sky130-hyperram-ctrl --issue 52 --image-profile heavy \
#     --timeout 7200 --wait-for-capacity 600 \
#     --pip klayout-tools==0.8.0 --pip ciel==2.6.1 \
#     --script scripts/fleet-regen-layout.sh [--shard probe] \
#     --output sim/hyperram/records --output evidence/item1.json \
#     --output layout/records --output layout/lvs/records \
#     --output evidence/item2.json \
#     --output manifests/sky130-hyperram-ctrl.json \
#     --output manifests/sky130-hyperram-ctrl.signoff.json \
#     --shard-output 0:fleet-regen.log --out <dir>
#
# It deliberately does NOT call scripts/setup-env.sh: that script hard-fails on
# missing iverilog/verilator/ngspice, which the layout flow never runs, and the
# heavy image carries only the synthesis/P&R toolchain. What the flow needs is
# the pinned klt (0.8.0), an OpenROAD that runs, and the pinned sky130A PDK --
# provisioned here from the image's baked PDK when it matches the pin, else
# fetched with ciel.
set -euo pipefail

MODE="${1:-regen}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

KLT_PIN="$(scripts/klt.sh --pin)"
# The PDK/ciel pins, read from scripts/setup-env.sh rather than duplicated here
# (the grep keeps the assignment's surrounding double quotes; strip them).
strip_quotes() { printf '%s' "${1//\"/}"; }
CIEL_PIN="$(strip_quotes "$(grep -E '^CIEL_VERSION=' scripts/setup-env.sh | cut -d= -f2-)")"
PDK_COMMIT="$(strip_quotes "$(grep -E '^CIEL_SKY130_VERSION=' scripts/setup-env.sh | cut -d= -f2-)")"

log() { echo "[fleet-regen $(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- pinned klt on $PATH ----------------------------------------------------
# The job venv (submitter --pip) should already provide klayout-tools==pin and
# ciel==pin ahead of the image tools; this fallback keeps the script runnable
# on a bare host. Never touches a host-wide install.
ensure_klt() {
  if have klt && [ "$(klt --version 2>/dev/null | awk '{print $NF}')" = "${KLT_PIN}" ]; then
    log "klt $(klt --version) (on PATH)"
    return 0
  fi
  log "PATH klt is not the pin; building a local venv"
  local venv="${REPO_ROOT}/.fleet-venv"
  if [ ! -x "${venv}/bin/python3" ]; then
    python3 -m venv "${venv}" 2>/dev/null \
      || (have uv && uv venv --quiet "${venv}") \
      || { echo "FATAL: cannot create a venv (no python3 -m venv, no uv)" >&2; exit 4; }
  fi
  if ! "${venv}/bin/python3" -m pip --version >/dev/null 2>&1; then
    have uv || { echo "FATAL: venv has no pip and uv is unavailable" >&2; exit 4; }
    uv pip install --quiet --python "${venv}/bin/python3" "klayout-tools==${KLT_PIN}" "ciel==${CIEL_PIN}" \
      || { echo "FATAL: uv pip install of the pinned klt/ciel failed (network access to PyPI?)" >&2; exit 4; }
  else
    "${venv}/bin/python3" -m pip install --quiet "klayout-tools==${KLT_PIN}" "ciel==${CIEL_PIN}" \
      || { echo "FATAL: pip install of the pinned klt/ciel failed (network access to PyPI?)" >&2; exit 4; }
  fi
  export PATH="${venv}/bin:${PATH}"
  [ "$(klt --version 2>/dev/null | awk '{print $NF}')" = "${KLT_PIN}" ] \
    || { echo "FATAL: cannot put pinned klt ${KLT_PIN} on PATH" >&2; exit 4; }
  log "klt $(klt --version) (local venv)"
}

# --- pinned yowasp-yosys on $PATH (synthesis / freshness) --------------------
# `flow/hyperram.py synth|check` (and the item-1 attestation's freshness
# command, which runs that file) refuse to answer unless the `yosys` on $PATH
# is the pinned yowasp-yosys build: require_pinned_yosys checks both the
# engine version the response reports and the yosys.wasm sha256 of the $PATH
# entry point. The heavy image's native yosys is not that build, so install
# the pinned wheel into the same local venv as klt and link it as `yosys`,
# exactly the way scripts/setup-env.sh does.
wasm_sha_of() {
  local venv="${REPO_ROOT}/.fleet-venv"
  "${venv}/bin/python3" - <<'PY'
import hashlib, os
import yowasp_yosys
p = os.path.join(os.path.dirname(yowasp_yosys.__file__), "yosys.wasm")
print(hashlib.sha256(open(p, "rb").read()).hexdigest())
PY
}

ensure_yowasp_yosys() {
  local want_ver want_sha got_sha venv="${REPO_ROOT}/.fleet-venv"
  want_ver="$(strip_quotes "$(grep -E '^YOWASP_YOSYS_VERSION=' scripts/setup-env.sh | cut -d= -f2-)")"
  want_sha="$(strip_quotes "$(grep -E '^YOWASP_YOSYS_WASM_SHA256=' scripts/setup-env.sh | cut -d= -f2-)")"
  # Bootstrap the venv if ensure_klt found the pinned klt on PATH and skipped
  # it, then put it first so the linked `yosys` (and the venv klt, if any)
  # win over the image's tools.
  if [ ! -x "${venv}/bin/python3" ]; then
    python3 -m venv "${venv}" 2>/dev/null \
      || (have uv && uv venv --quiet "${venv}") \
      || { echo "FATAL: cannot create a venv (no python3 -m venv, no uv)" >&2; exit 4; }
  fi
  export PATH="${venv}/bin:${PATH}"
  if [ -x "${venv}/bin/yowasp-yosys" ] \
     && [ "$(realpath "${venv}/bin/yosys" 2>/dev/null)" = "$(realpath "${venv}/bin/yowasp-yosys")" ]; then
    got_sha="$(wasm_sha_of 2>/dev/null || true)"
    if [ "${got_sha}" = "${want_sha}" ]; then
      log "pinned yowasp-yosys ${want_ver} already in ${venv} (yosys.wasm sha256:${got_sha})"
      return 0
    fi
  fi
  log "installing yowasp-yosys==${want_ver} into ${venv}"
  if "${venv}/bin/python3" -m pip --version >/dev/null 2>&1; then
    "${venv}/bin/python3" -m pip install --quiet "yowasp-yosys==${want_ver}" \
      || { echo "FATAL: pip install yowasp-yosys==${want_ver} failed (network access to PyPI?)" >&2; exit 4; }
  else
    have uv || { echo "FATAL: venv has no pip and uv is unavailable" >&2; exit 4; }
    uv pip install --quiet --python "${venv}/bin/python3" "yowasp-yosys==${want_ver}" \
      || { echo "FATAL: uv pip install of yowasp-yosys==${want_ver} failed (network access to PyPI?)" >&2; exit 4; }
  fi
  got_sha="$(wasm_sha_of)" \
    || { echo "FATAL: could not hash the YoWASP yosys.wasm module after install" >&2; exit 4; }
  [ "${got_sha}" = "${want_sha}" ] \
    || { echo "FATAL: Yosys/ABC build identity mismatch: expected sha256:${want_sha}, got sha256:${got_sha}. Do not mint evidence from this environment." >&2; exit 4; }
  ln -sfn "yowasp-yosys" "${venv}/bin/yosys" \
    || { echo "FATAL: could not link ${venv}/bin/yosys" >&2; exit 4; }
  log "yosys.wasm sha256:${got_sha} (matches pin)"
}

# --- sky130A PDK at the pinned open_pdks commit ------------------------------
pdk_ok() {
  grep -q "${PDK_COMMIT}" "$1/sky130A/SOURCES" 2>/dev/null \
    && ls "$1"/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib >/dev/null 2>&1 \
    && ls "$1"/sky130A/libs.ref/sky130_fd_sc_hd/lef/*.lef >/dev/null 2>&1
}

ensure_pdk() {
  if [ -z "${PDK_ROOT:-}" ] && [ -d /opt/pdk/sky130A ]; then
    export PDK_ROOT=/opt/pdk
    log "using the image's baked PDK root /opt/pdk"
  fi
  if [ -n "${PDK_ROOT:-}" ] && pdk_ok "${PDK_ROOT}"; then
    log "pinned PDK verified at ${PDK_ROOT} (open_pdks ${PDK_COMMIT:0:12})"
    return 0
  fi
  if [ -n "${PDK_ROOT:-}" ]; then
    log "WARNING: PDK at ${PDK_ROOT:-<unset>} is missing or not open_pdks ${PDK_COMMIT:0:12}; fetching a fresh one"
  fi
  export PDK_ROOT="${REPO_ROOT}/.fleet-pdk"
  mkdir -p "${PDK_ROOT}"
  ciel enable --pdk-root "${PDK_ROOT}" --pdk-family sky130 \
    -l sky130_fd_pr -l sky130_fd_sc_hd -l sky130_fd_io "${PDK_COMMIT}" \
    || { echo "FATAL: ciel enable failed (network, or GitHub rate limit)" >&2; exit 4; }
  pdk_ok "${PDK_ROOT}" || { echo "FATAL: freshly provisioned PDK does not verify" >&2; exit 4; }
  log "PDK provisioned with ciel at ${PDK_ROOT} (open_pdks ${PDK_COMMIT:0:12})"
}

report_pdk() {
  echo "PDK_ROOT=${PDK_ROOT:-<unset>} PDK=${PDK:-<unset>}"
  if [ -n "${PDK_ROOT:-}" ] && [ -f "${PDK_ROOT}/sky130A/SOURCES" ]; then
    echo "sky130A/SOURCES: $(grep -m1 open_pdks "${PDK_ROOT}/sky130A/SOURCES" || head -1 "${PDK_ROOT}/sky130A/SOURCES")"
    for f in libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib \
             libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef \
             libs.ref/sky130_fd_io/lib/sky130_fd_io__top_gpiov2_tt_tt_025C_1v80_3v30.lib \
             libs.ref/sky130_fd_io/lef/sky130_fd_io.lef; do
      [ -s "${PDK_ROOT}/sky130A/${f}" ] && echo "present: sky130A/${f}" || echo "MISSING: sky130A/${f}"
    done
  else
    echo "sky130A/SOURCES: not found under PDK_ROOT"
  fi
}

if [ "${MODE}" = "probe" ]; then
  {
    echo "== heavy-image probe, $(date -u +%Y-%m-%dT%H:%M:%SZ) =="
    echo "RS_SOURCE_COMMIT=${RS_SOURCE_COMMIT:-<unset>} RS_SRC_SHA256=${RS_SRC_SHA256:-<unset>}"
    echo "whoami=$(whoami) HOME=${HOME} pwd=$(pwd)"
    echo "PATH=${PATH}"
    for t in klt openroad yosys python3 pip3 uv jq git curl; do
      if have "$t"; then
        v="$("$t" --version 2>&1 | head -1 || true)"
        echo "tool $t: $(command -v "$t") :: ${v}"
      else
        echo "tool $t: MISSING"
      fi
    done
    if have openroad; then openroad -version >/dev/null 2>&1 && echo "openroad runs: yes" || echo "openroad runs: NO"; fi
    report_pdk
    echo "--- venv capability ---"
    if python3 -m venv /tmp/probe-venv 2>/tmp/probe-venv.err; then
      echo "python3 -m venv: OK"
      /tmp/probe-venv/bin/pip --version 2>&1 | head -1 || true
    else
      echo "python3 -m venv: FAILED: $(tail -2 /tmp/probe-venv.err | tr '\n' ' ')"
    fi
    rm -rf /tmp/probe-venv /tmp/probe-venv.err
    echo "--- network ---"
    curl -fsS -m 20 -o /dev/null -w "pypi.org: HTTP %{http_code}\n" https://pypi.org/simple/ || echo "pypi.org: UNREACHABLE"
    curl -fsS -m 20 -o /dev/null -w "github.com: HTTP %{http_code}\n" https://github.com || echo "github.com: UNREACHABLE"
    echo "--- disk ---"
    df -h "${REPO_ROOT}" /tmp | sed 1d
    echo "== probe done =="
  } > fleet-probe.txt 2>&1
  cat fleet-probe.txt
  exit 0
fi

# --- regen -------------------------------------------------------------------
LOG="${REPO_ROOT}/fleet-regen.log"
exec > >(tee "${LOG}") 2>&1
log "regen start: RS_SOURCE_COMMIT=${RS_SOURCE_COMMIT:-<unset>} src_sha256=${RS_SRC_SHA256:-<unset>}"

ensure_klt
have openroad || { echo "FATAL: openroad not on PATH" >&2; exit 4; }
openroad -version >/dev/null 2>&1 || { echo "FATAL: openroad on PATH but not runnable" >&2; exit 4; }
log "openroad: $(openroad -version 2>&1 | head -1)"
ensure_pdk
export PDK="${PDK:-sky130A}"
ensure_yowasp_yosys

# Clean the outputs this run owns, so a partial failure surfaces as missing
# declared outputs (job exit 3) instead of silently re-collecting stale files.
# Runs after the toolchain checks above, so an early failure cannot leave the
# records deleted.
rm -rf layout/records/* layout/lvs/records/* evidence/item2.json
mkdir -p layout/records layout/lvs/records

STEP_T0=$(date +%s)
step() { log "step $1 done in $(( $(date +%s) - STEP_T0 ))s"; STEP_T0=$(date +%s); }

# --- netlist + STA + item-1 evidence (the half the layout phase reads) -------
# The layout phase below place-and-routes the *committed* netlist, and the
# item-1 envelope binds the RTL and netlist hashes, so the netlist is
# regenerated first: pinned-yowasp synthesis, re-timing of the fresh netlist,
# a byte-compare freshness check, the structural 32-chain-cell assertion
# (issue #101: the refactor must be naming-only), then the item-1 attestation,
# whose freshness command re-runs that check itself.
log "regenerating the netlist (pinned yowasp-yosys synthesis)"
python3 flow/hyperram.py synth
step synth
log "re-timing the fresh netlist (klt sta, all shipped liberty corners)"
python3 flow/hyperram.py sta
step sta
log "freshness: re-synthesize and byte-compare against the committed netlist"
python3 -I flow/hyperram.py check
step check
log "structural check: 32 chain cells, one shared hr_tap_delay module"
python3 - <<'PY'
import re
net = open("sim/hyperram/records/hyperram_ctrl.netlist.v").read()
insts = re.findall(r"^\s*sky130_fd_sc_hd__dlygate4sd3_1\s+(\\?\S+)", net, re.M)
assert len(insts) == 32, f"expected 32 dlygate4sd3_1 instances, found {len(insts)}"
assert "module hr_tap_delay" in net, "hr_tap_delay module missing from the netlist"
under = [i for i in insts if i.startswith(("\\u_ck_dly.", "\\u_rwds_dly."))]
assert len(under) == 32, f"chain cells not under the named instantiations: {len(insts) - len(under)} stray"
print("cell check ok: 32 dlygate4sd3_1, all under u_ck_dly.g_dly / u_rwds_dly.g_dly")
PY
step cell-check
log "re-recording the item-1 attestation (re-runs the freshness check itself)"
scripts/klt.sh signoff --attest 1 --inventory attest/item1.json -o evidence/item1.json
step attest-item1

log "running make layout (klt place-and-route, ~25 min)"
make layout
step layout
log "running make drc"
make drc
step drc
log "running layout/lvs/run.sh"
bash layout/lvs/run.sh
step lvs
log "running layout/erc/run.sh"
bash layout/erc/run.sh
step erc
log "running make layout-check (must be fresh)"
make layout-check
step layout-check
log "re-hashing committed reports against the new artifacts (cheap --check modes)"
scripts/klt.sh drc --check layout/records/drc.report.json
bash layout/lvs/run.sh check
bash layout/erc/run.sh check
step checks

# Re-pin the manifest citations for the evidence this run regenerated, then
# re-render the verdict of record (manifests/README.md: same PR as the change).
#
# The pinned content_hash is the INPUT artifact the cited envelope binds --
# its self-reported provenance.input.content_hash (design-evidence-tiers.md,
# "Staleness is failure": klt signoff gates the pin against that self-report)
# -- not the evidence file's own bytes. item2/DRC/ERC all bind the routed GDS,
# LVS binds its extracted netlist, the P&R response binds the routed netlist.
log "re-pinning manifest citations and re-rendering the signoff record"
python3 - <<'PY'
import json, pathlib
def input_hash(path):
    doc = json.loads(pathlib.Path(path).read_text())
    def find(node):
        if isinstance(node, dict):
            prov = node.get("provenance")
            if isinstance(prov, dict):
                inp = prov.get("input")
                if isinstance(inp, dict) and inp.get("content_hash"):
                    return inp["content_hash"]
            for v in node.values():
                found = find(v)
                if found:
                    return found
        elif isinstance(node, list):
            for v in node:
                found = find(v)
                if found:
                    return found
    found = find(doc)
    if not found:
        raise SystemExit(f"FATAL: no provenance.input.content_hash in {path}")
    return found
targets = {
    "evidence/item1.json",
    "evidence/item2.json",
    "layout/records/drc.report.json",
    "layout/lvs/records/report.json",
    "layout/records/erc.report.json",
    "layout/records/place-and-route.response.json",
}
mp = pathlib.Path("manifests/sky130-hyperram-ctrl.json")
man = json.loads(mp.read_text())
def fix(node):
    if isinstance(node, dict):
        if node.get("file") in targets:
            node["content_hash"] = input_hash(node["file"])
        else:
            for v in node.values():
                fix(v)
    elif isinstance(node, list):
        for v in node:
            fix(v)
fix(man)
mp.write_text(json.dumps(man, indent=2) + "\n")
print("manifest citations re-pinned:", ", ".join(sorted(targets)))
PY
SIGNOFF_RC=0
scripts/klt.sh signoff --manifest manifests/sky130-hyperram-ctrl.json \
  --tiers-doc manifests/design-evidence-tiers.md --format json \
  > manifests/sky130-hyperram-ctrl.signoff.json || SIGNOFF_RC=$?
[ "${SIGNOFF_RC}" -eq 0 ] || [ "${SIGNOFF_RC}" -eq 3 ] \
  || { echo "FATAL: klt signoff exited ${SIGNOFF_RC} (manifest, tier doc or cited evidence is broken)" >&2; exit "${SIGNOFF_RC}"; }
log "signoff rendered (rc=${SIGNOFF_RC}; 3 = grader ran, some item unmet)"
python3 -c 'import json; d=json.load(open("manifests/sky130-hyperram-ctrl.signoff.json")); print("signoff: t1_met", d["t1_met_count"], "of", d["t1_item_count"])'
step signoff

# Verdicts: the AC is DRC clean, LVS match, ERC clean -- fail the job otherwise.
python3 - <<'PY'
import json
drc = json.load(open("layout/records/drc.report.json"))
assert drc["status"] == "clean" and drc["violation_count"] == 0, f"DRC not clean: {drc['status']} n={drc.get('violation_count')}"
lvs = json.load(open("layout/lvs/records/report.json"))
assert lvs["status"] == "match", f"LVS not a match: {lvs['status']}"
pc = lvs.get("power_connectivity") or {}
assert pc.get("status") == "match", f"LVS power connectivity: {pc.get('status')}"
erc = json.load(open("layout/records/erc.report.json"))
assert erc["erc_status"] == "clean", f"ERC not clean: {erc['erc_status']}"
print("verdicts: DRC clean; LVS match (power match); ERC clean")
PY

python3 - <<'PY'
import json
req = json.load(open("layout/place-and-route.json"))
r = json.load(open("layout/records/place-and-route.response.json"))
print(f"P&R: engine {r['engine']} {r.get('engine_version','')} "
      f"corner {req['pdk']['corner']} (interconnect {r.get('interconnect_corner')}) "
      f"clk {req['constraints']['clock_period_ns']}ns core {r['core_area_um2']}um2 "
      f"worst_slack {r.get('worst_slack_ns')}ns TNS {r.get('total_negative_slack_ns')}ns "
      f"spef_worst_slack {r.get('spef_sta',{}).get('worst_slack_ns')}ns")
PY

log "regen complete"
