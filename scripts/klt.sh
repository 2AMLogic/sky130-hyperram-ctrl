#!/usr/bin/env bash
# scripts/klt.sh -- the one klt pin and the one rule for choosing which klt runs.
#
#   scripts/klt.sh <args...>   run the pinned klt with <args...>
#   scripts/klt.sh --pin       print the pinned version ("0.8.0") and exit
#
# Resolution rule (one place, so CI and local runs cannot use different klt
# builds): use the `klt` on $PATH when its version is exactly the pin -- that
# picks up the .venv klt scripts/setup-env.sh installs, since the Makefile puts
# .venv/bin first -- otherwise run the pin through `uvx`. Never installs or
# changes a host-wide tool.
#
# This is the only executable copy of the klt version. scripts/check_ci.sh,
# layout/erc/run.sh, layout/lvs/run.sh, the Makefile `drc` target and the flow
# runners (flow/hyperram.py and flow/smoke.py, through flow/klt_run.py) call
# this script; scripts/setup-env.sh and .github/workflows/ci.yml read the pin
# from `--pin`. Bumping klt means editing KLT_VERSION below, then the vendored
# tier doc and the signoff record (see manifests/README.md).
set -euo pipefail

KLT_VERSION="0.8.0"

if [ "${1:-}" = "--pin" ]; then
  printf '%s\n' "${KLT_VERSION}"
  exit 0
fi

if command -v klt >/dev/null 2>&1 \
  && [ "$(klt --version 2>/dev/null | awk '{print $NF}')" = "${KLT_VERSION}" ]; then
  exec klt "$@"
fi
exec uvx --from "klayout-tools==${KLT_VERSION}" klt "$@"
