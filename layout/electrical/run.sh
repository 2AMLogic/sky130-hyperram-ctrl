#!/usr/bin/env bash
# Capture a DEF/SPEF measurement, or verify both published reports from its inputs.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
case "${1:-}" in
  "") exec python3 -I layout/electrical/classify.py --measure ;;
  check) exec python3 -I layout/electrical/classify.py --check ;;
  *) echo "usage: $0 [check]" >&2; exit 2 ;;
esac
