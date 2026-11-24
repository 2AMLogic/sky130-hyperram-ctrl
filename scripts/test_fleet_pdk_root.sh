#!/usr/bin/env bash
#
# scripts/test_fleet_pdk_root.sh -- drive the runtime PDK_ROOT guard in
# scripts/fleet-regen-layout.sh over fixture directory shapes, the way a
# fleet job meets it, with no installed PDK, no EDA tools and no network
# (issue #193).
#
# What is under test: the value-level assertion after the ensure_pdk call --
#
#   pdk_root_physical="$(realpath -e -- "${PDK_ROOT}")"
#   if [[ "${pdk_root_physical}/" == "${REPO_ROOT%/}/"* ]]; then
#     echo "FATAL: PDK_ROOT=${PDK_ROOT} is inside the repo (issue #142)" >&2
#     exit 4
#   fi
#
# This guard is the one authoritative PDK_ROOT check (the static checker was
# removed, issue #228), and it lives outside ensure_pdk on purpose, so it also
# covers the verified-PDK early return. Two silent weakenings must stay caught:
#
#   1. REPO_ROOT (the `cd -P ... pwd -P` at the top of the fleet script)
#      must stay physical: a logical REPO_ROOT lets a PDK reached through a
#      symlinked checkout escape the prefix test.
#   2. The guard must stay after ensure_pdk's verified-PDK early return:
#      moved below it, every repo-local PDK takes the early return first
#      and bypasses the guard entirely.
#
# How: run the production fleet script itself (copied verbatim into a
# throwaway checkout, so its REPO_ROOT is computed there) against fixture
# PDK roots that pass pdk_ok, with a stub klt/openroad/ciel on a private
# PATH and a pre-made .fleet-venv whose python3 stub refuses pip. Rejection
# is exit 4 plus the issue #142 diagnostic; success is the script reaching
# ensure_yowasp_yosys -- the first step after the guard -- whose offline
# "installing yowasp-yosys==" log line is the sentinel. Nothing reaches the
# network: the ciel stub refuses to fetch and the venv python3 stub makes
# pip unavailable.
#
# Cases: rejected -- a PDK at the checkout root itself, in an absolute
# repo-local subdirectory, in a relative subdirectory, through a symlink
# that points into the checkout, and through a symlinked checkout; accepted
# -- an external sibling whose name starts with the checkout directory's
# name, the shared-prefix shape the prefix test must not over-reject.
#
# One function of the copy is neutralised: expose_klt_on_system_path(), which
# symlinks the PATH klt into /usr/local/bin when that is writable (CI runners,
# not dev hosts). It runs before the guard and independently of it, and in
# this fixture the klt is a throwaway stub -- left alone it would plant a
# dangling /usr/local/bin/klt on the runner. Stubbing it keeps the fixture
# host-agnostic and leaves the guard, ensure_pdk and the REPO_ROOT computation
# (everything the two weakenings above touch) byte-for-byte production.
set -euo pipefail

REPO_ROOT="$(CDPATH='' cd -P -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

fail() { echo "::error::test_fleet_pdk_root: $*" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/fleet-pdk-root-test.XXXXXXXX")"
trap 'rm -rf "${WORK}"' EXIT
CHK="${WORK}/fixture-checkout"
LINK="${WORK}/link-to-checkout"
STUB="${WORK}/stub-bin"
FLEET="${CHK}/scripts/fleet-regen-layout.sh"
VENV_BIN="${CHK}/.fleet-venv/bin"

# --- the throwaway checkout: the production scripts, verbatim -----------------
# The three files the fleet script reads before the sentinel: itself,
# scripts/klt.sh (the pin, line "KLT_PIN=") and scripts/setup-env.sh (the
# CIEL/PDK/yosys pins). Anything else it grows a pre-guard dependency on is
# missing here, so this fixture fails loudly and gets updated, not silently.
mkdir -p "${CHK}/scripts" "${STUB}" "${VENV_BIN}"
cp "${REPO_ROOT}/scripts/fleet-regen-layout.sh" "${REPO_ROOT}/scripts/klt.sh" \
   "${REPO_ROOT}/scripts/setup-env.sh" "${CHK}/scripts/"
chmod 755 "${CHK}/scripts/fleet-regen-layout.sh" "${CHK}/scripts/klt.sh"

# The one deliberate deviation from verbatim (see the header): turn
# expose_klt_on_system_path into a no-op in the copy by returning at its first
# line. Fail loudly if the function is renamed so the stub silently stops
# applying and the fixture starts writing to /usr/local/bin again.
STUB_LINE='expose_klt_on_system_path() {'
[ "$(grep -cFx -- "${STUB_LINE}" "${FLEET}")" -eq 1 ] \
  || fail "fleet script no longer defines exactly one '${STUB_LINE}' -- update the fixture's stub"
sed -i "s/^expose_klt_on_system_path() {\$/expose_klt_on_system_path() { return 0/" "${FLEET}"
grep -qFx -- 'expose_klt_on_system_path() { return 0' "${FLEET}" \
  || fail "could not neutralise expose_klt_on_system_path in the fixture copy"

strip_quotes() { printf '%s' "${1//\"/}"; }
KLT_PIN="$("${REPO_ROOT}/scripts/klt.sh" --pin)"
PDK_COMMIT="$(strip_quotes "$(grep -E '^CIEL_SKY130_VERSION=' "${REPO_ROOT}/scripts/setup-env.sh" | cut -d= -f2-)")"

# --- the fixture PDK: just enough for pdk_ok ----------------------------------
# $1 = PDK root directory
make_pdk_fixture() {
  mkdir -p "$1/sky130A/libs.ref/sky130_fd_sc_hd/lib" \
           "$1/sky130A/libs.ref/sky130_fd_sc_hd/lef"
  printf 'open_pdks %s\n' "${PDK_COMMIT}" >"$1/sky130A/SOURCES"
  : >"$1/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
  : >"$1/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"
}

# --- the stub toolchain ---------------------------------------------------------
# klt reports the pin, which satisfies ensure_klt's PATH branch without a
# venv; openroad answers -version. ciel REFUSES, so a fixture PDK that
# fails pdk_ok dies loudly offline instead of fetching. The .fleet-venv
# python3 stub makes wasm_sha_of return nothing and pip unavailable, so
# ensure_yowasp_yosys logs the sentinel line and then fails offline; uv is
# kept off the private PATH so the pip-less branch is taken deterministically.
cat >"${STUB}/klt" <<EOF
#!/bin/sh
case \$1 in --version) echo "klt (klayout-tools fixture) ${KLT_PIN}";; esac
exit 0
EOF
cat >"${STUB}/openroad" <<'EOF'
#!/bin/sh
[ "${1:-}" = "-version" ] && echo "OpenROAD fixture stub"
exit 0
EOF
cat >"${STUB}/ciel" <<'EOF'
#!/bin/sh
echo "ciel fixture stub: refusing to fetch a PDK in an offline test" >&2
exit 4
EOF
cat >"${VENV_BIN}/python3" <<'EOF'
#!/bin/sh
exit 1
EOF
cat >"${VENV_BIN}/yowasp-yosys" <<'EOF'
#!/bin/sh
exit 0
EOF
ln -s yowasp-yosys "${VENV_BIN}/yosys"
chmod 755 "${STUB}/klt" "${STUB}/openroad" "${STUB}/ciel" \
          "${VENV_BIN}/python3" "${VENV_BIN}/yowasp-yosys"

# --- driver and assertions ------------------------------------------------------
OUT=""
RC=0

run_fleet() { # $1 = fleet script path, $2 = PDK_ROOT value
  RC=0
  OUT="$(env PATH="${STUB}:/usr/bin:/bin" PDK_ROOT="$2" "$1" 2>&1)" || RC=$?
  # Proves the stub above held on a host where /usr/local/bin is writable (CI
  # runners): the production function logs this line right after it links.
  if printf '%s\n' "${OUT}" | grep -qF -- 'symlinked into /usr/local/bin'; then
    fail "the fleet script touched /usr/local/bin: expose_klt_on_system_path stub did not apply"
  fi
}

line_of() { printf '%s\n' "${OUT}" | grep -nF -- "$1" | head -1 | cut -d: -f1; }

expect_in() { # $1 = case name, $2 = literal that must be in the output
  printf '%s\n' "${OUT}" | grep -qF -- "$2" || fail "case $1: output lacks: $2"
}

expect_absent() { # $1 = case name, $2 = literal that must not be in the output
  if printf '%s\n' "${OUT}" | grep -qF -- "$2"; then
    fail "case $1: output must not contain: $2"
  fi
}

expect_before() { # $1 = case name, $2 = early literal, $3 = late literal
  local early late
  early="$(line_of "$2")"
  late="$(line_of "$3")"
  if [ -z "${early}" ] || [ -z "${late}" ]; then
    fail "case $1: a marker of the order check is missing ($2 / $3)"
  fi
  [ "${early}" -lt "${late}" ] || fail "case $1: '$2' must precede '$3'"
}

expect_reject() { # $1 = case name, $2 = PDK_ROOT, $3 = fleet script (default: ${FLEET})
  run_fleet "${3:-${FLEET}}" "$2"
  [ "${RC}" -eq 4 ] || fail "case $1: expected exit 4, got ${RC}"
  # ensure_pdk's verified-PDK early return ran, and ran before the guard
  expect_in "$1" "pinned PDK verified at"
  expect_in "$1" "is inside the repo (issue #142)"
  # the guard fired before the first step after it
  expect_absent "$1" "installing yowasp-yosys"
  expect_before "$1" "pinned PDK verified at" "is inside the repo (issue #142)"
  echo "ok $1: rejected with the issue #142 diagnostic"
}

expect_pass() { # $1 = case name, $2 = PDK_ROOT
  run_fleet "${FLEET}" "$2"
  expect_in "$1" "pinned PDK verified at"
  # reached ensure_yowasp_yosys, the first step after the guard
  expect_in "$1" "installing yowasp-yosys=="
  expect_absent "$1" "is inside the repo (issue #142)"
  expect_before "$1" "pinned PDK verified at" "installing yowasp-yosys=="
  echo "ok $1: reached the first step after the guard"
}

# --- the cases -------------------------------------------------------------------
make_pdk_fixture "${CHK}"                          # sky130A/ at the checkout root itself
make_pdk_fixture "${CHK}/pdk"                      # repo-local subdirectory
make_pdk_fixture "${WORK}/fixture-checkout-pdk"    # external sibling, shared name prefix
ln -s "${CHK}" "${LINK}"
ln -s "${CHK}/pdk" "${WORK}/pdk-alias"

expect_reject "pdk-at-checkout-root" "${CHK}"
expect_reject "pdk-absolute-repo-local" "${CHK}/pdk"
expect_reject "pdk-relative-subdir" "pdk"
expect_reject "pdk-symlink-into-checkout" "${WORK}/pdk-alias"
expect_reject "pdk-via-symlinked-checkout" "${LINK}/pdk" "${LINK}/scripts/fleet-regen-layout.sh"
expect_pass "external-sibling-name-prefix" "${WORK}/fixture-checkout-pdk"

echo "ok: fleet PDK_ROOT runtime guard holds over every fixture shape"
