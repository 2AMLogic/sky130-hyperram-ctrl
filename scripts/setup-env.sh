#!/usr/bin/env bash
#
# scripts/setup-env.sh -- pin and provision this repo's RTL-flow environment.
#
#   1. Creates a local .venv and installs `klayout-tools` (klt) at a pinned
#      git commit, plus the pinned cocotb and ciel.
#   2. Installs the pinned Yosys build (YoWASP wheel) into .venv and verifies
#      its WebAssembly module's sha256 (the mapper identity `yosys -V` does
#      not report), exposing it as .venv/bin/yosys.
#   3. Provisions the pinned sky130A PDK via `ciel` with BOTH sky130_fd_pr and
#      sky130_fd_sc_hd enabled, verifies the open_pdks revision from SOURCES,
#      and FAILS LOUDLY if the sky130_fd_sc_hd liberty/LEF is missing.
#   4. Checks iverilog, verilator and openroad are on $PATH and records their
#      versions (they are host tools: this script never installs them).
#
# Exit 0: environment ready.  Exit 1: anything above failed.
#
# Usage: ./scripts/setup-env.sh [--pdk-root=/path]
#
# Pins are recorded in docs/environment.md; update both together.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

# --- pinned versions -- keep in sync with docs/environment.md -------------
KLT_VERSION="0.8.0"
COCOTB_VERSION="2.0.1"
CIEL_VERSION="2.6.1"
CIEL_PDK_FAMILY="sky130"
CIEL_SKY130_VERSION="f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7"
YOWASP_YOSYS_VERSION="0.68.0.0.post1208"
YOWASP_YOSYS_WASM_SHA256="e37a7e65e3fa4efbbd64a9c1b0e906be16cdc6c4d5273109d17537f78449f38c"
ICARUS_MIN_MAJOR="12"
VERILATOR_MIN_MAJOR="5"
# ----------------------------------------------------------------------------

PDK_ROOT="${PDK_ROOT:-${HOME}/.ciel}"
VENV_DIR="${REPO_ROOT}/.venv"

for arg in "$@"; do
  case "${arg}" in
    --pdk-root=*) PDK_ROOT="${arg#--pdk-root=}" ;;
    -h|--help) sed -n '2,21p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: ${arg}" >&2; exit 1 ;;
  esac
done

fail() { echo "FATAL: $*" >&2; exit 1; }

echo "== 1/4 python venv + klt ${KLT_VERSION} =="
# Prefer uv (no python3-venv package needed); fall back to python -m venv + pip.
if command -v uv >/dev/null 2>&1; then
  [ -d "${VENV_DIR}" ] || uv venv --quiet --python ">=3.10,<3.14" "${VENV_DIR}" || fail "uv venv failed."
  VENV_PY="${VENV_DIR}/bin/python3"
  pip_install() { uv pip install --quiet --python "${VENV_PY}" "$@"; }
else
  PYTHON_BIN=""
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    found="$(command -v "${candidate}" || true)"
    [ -n "${found}" ] || continue
    ver="$("${found}" -c 'import sys; print(sys.version_info[1] if sys.version_info[0]==3 else 99)' 2>/dev/null)"
    if [ "${ver:-99}" -le 13 ] 2>/dev/null && [ "${ver:-0}" -ge 10 ]; then PYTHON_BIN="${found}"; break; fi
  done
  [ -n "${PYTHON_BIN}" ] || fail "no Python 3.10-3.13 on \$PATH (cocotb ${COCOTB_VERSION} does not build on 3.14+)."
  [ -d "${VENV_DIR}" ] || "${PYTHON_BIN}" -m venv "${VENV_DIR}" || fail "venv creation failed (install uv, or Debian/Ubuntu python3-venv)."
  VENV_PY="${VENV_DIR}/bin/python3"
  pip_install() { "${VENV_DIR}/bin/pip" install --quiet "$@"; }
fi
pip_install "klayout-tools==${KLT_VERSION}" "cocotb==${COCOTB_VERSION}" "ciel==${CIEL_VERSION}" \
  || fail "pip install of klayout-tools/cocotb/ciel failed (network access to PyPI?)."
echo "klt: $("${VENV_DIR}/bin/klt" --version 2>&1)"

echo
echo "== 2/4 yosys (YoWASP ${YOWASP_YOSYS_VERSION}) =="
pip_install "yowasp-yosys==${YOWASP_YOSYS_VERSION}" \
  || fail "pip install yowasp-yosys==${YOWASP_YOSYS_VERSION} failed."
WASM_SHA="$("${VENV_PY}" - <<'PY'
import hashlib, os
import yowasp_yosys
p = os.path.join(os.path.dirname(yowasp_yosys.__file__), "yosys.wasm")
print(hashlib.sha256(open(p, "rb").read()).hexdigest())
PY
)" || fail "could not hash the YoWASP yosys.wasm module."
if [ "${WASM_SHA}" != "${YOWASP_YOSYS_WASM_SHA256}" ]; then
  fail "Yosys/ABC build identity mismatch: expected sha256:${YOWASP_YOSYS_WASM_SHA256}, got sha256:${WASM_SHA}. Do not mint evidence from this environment."
fi
ln -sfn "yowasp-yosys" "${VENV_DIR}/bin/yosys" || fail "could not link ${VENV_DIR}/bin/yosys."
echo "yosys.wasm sha256:${WASM_SHA} (matches pin)"

echo
echo "== 3/4 sky130A PDK (open_pdks ${CIEL_SKY130_VERSION:0:12}) under ${PDK_ROOT} =="
pdk_ok() {
  grep -q "${CIEL_SKY130_VERSION}" "${PDK_ROOT}/sky130A/SOURCES" 2>/dev/null \
    && ls "${PDK_ROOT}"/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib >/dev/null 2>&1
}
if pdk_ok; then
  echo "pinned PDK already present; not re-fetching"
else
  mkdir -p "${PDK_ROOT}" || fail "cannot create ${PDK_ROOT}."
  "${VENV_DIR}/bin/ciel" enable --pdk-root "${PDK_ROOT}" --pdk-family "${CIEL_PDK_FAMILY}" \
      -l sky130_fd_pr -l sky130_fd_sc_hd "${CIEL_SKY130_VERSION}" \
    || fail "'ciel enable' failed for sky130 ${CIEL_SKY130_VERSION:0:12} (network, or GitHub rate limit: set GITHUB_TOKEN)."
fi
[ -f "${PDK_ROOT}/sky130A/SOURCES" ] || fail "${PDK_ROOT}/sky130A/SOURCES missing; cannot verify the open_pdks revision."
grep -q "${CIEL_SKY130_VERSION}" "${PDK_ROOT}/sky130A/SOURCES" \
  || fail "PDK revision mismatch: ${PDK_ROOT}/sky130A/SOURCES does not name ${CIEL_SKY130_VERSION}."
# sky130_fd_pr alone is the known trap (synthesis cannot run without the std-cell library).
for f in "libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" \
         "libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ss_100C_1v60.lib" \
         "libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ff_n40C_1v95.lib"; do
  [ -s "${PDK_ROOT}/sky130A/${f}" ] \
    || fail "sky130_fd_sc_hd is missing (${PDK_ROOT}/sky130A/${f}). Re-run 'ciel enable ... -l sky130_fd_sc_hd ${CIEL_SKY130_VERSION}'."
done
ls "${PDK_ROOT}"/sky130A/libs.ref/sky130_fd_sc_hd/lef/*.lef >/dev/null 2>&1 \
  || fail "sky130_fd_sc_hd LEF is missing under ${PDK_ROOT}/sky130A/libs.ref/sky130_fd_sc_hd/lef/."
echo "sky130A ready (open_pdks ${CIEL_SKY130_VERSION:0:12} verified via SOURCES; sky130_fd_sc_hd present)"

echo
echo "== 4/4 host tools (iverilog, verilator, openroad) =="
missing=0
major_of() { sed -E 's/[^0-9]*([0-9]+).*/\1/'; }
if command -v iverilog >/dev/null 2>&1; then
  v="$(iverilog -V 2>/dev/null | head -1)"; echo "  iverilog:  ${v}"
  [ "$(printf '%s' "${v}" | sed -E 's/.*version ([0-9]+).*/\1/')" -ge "${ICARUS_MIN_MAJOR}" ] 2>/dev/null \
    || { echo "  -> need Icarus >= ${ICARUS_MIN_MAJOR}"; missing=1; }
else echo "  iverilog:  MISSING"; missing=1; fi
if command -v verilator >/dev/null 2>&1; then
  v="$(verilator --version | head -1)"; echo "  verilator: ${v}"
  [ "$(printf '%s' "${v}" | major_of)" -ge "${VERILATOR_MIN_MAJOR}" ] || { echo "  -> need Verilator >= ${VERILATOR_MIN_MAJOR}"; missing=1; }
else echo "  verilator: MISSING"; missing=1; fi
# Run it, don't just find it: the usual install is a Docker wrapper that exists on
# $PATH but cannot execute without access to the Docker daemon.
if command -v openroad >/dev/null 2>&1; then
  if ov="$(openroad -version 2>&1)"; then echo "  openroad:  ${ov}"
  else echo "  openroad:  on \$PATH but NOT RUNNABLE: $(printf '%s' "${ov}" | head -1)"; missing=1; fi
else echo "  openroad:  MISSING"; missing=1; fi
[ "${missing}" -eq 0 ] || fail "host tools missing or too old (this script does not install host tools; see docs/environment.md)."

echo
echo "environment ready. Run: make smoke"
