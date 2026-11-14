#!/usr/bin/env bash
#
# sim/pad-sta/run-opensta.sh -- regenerate the committed pad-liberty STA
# evidence (sim/pad-sta/records/opensta-*.log), which answers
# spec/target-spec.md open question (a): do the pinned PDK's sky130_fd_io
# liberty views give OpenSTA arcs through the pad cells?
#
# The pinned klt 0.8.0's `klt sta` cannot drive this experiment (it offers
# no way to load a second liberty for a macro cell -- see
# sim/pad-sta/records/RECORD.md "Tool gap"), so this script drives
# OpenROAD's embedded OpenSTA directly with one committed, self-contained
# session script per configuration, exactly the fallback the issue names.
#
# Sessions written to sim/pad-sta/records/:
#   opensta-tt-5pf.log   tt_tt_025C_1v80_3v30 pad + tt_025C_1v80 core, 5 pF
#   opensta-tt-10pf.log  ... 10 pF (primary load)
#   opensta-tt-20pf.log  ... 20 pF (load-sensitivity check)
#   opensta-ss-10pf.log  ss_ss_100C_1v60_3v00 pad + ss_100C_1v60 core
#   opensta-ff-oow-10pf.log  LABELLED OUT-OF-WINDOW comparison: ff core
#                        (ff_n40C_1v95) paired with the 5.5 V-class pad
#                        liberty ff_ff_n40C_1v95_5v50 -- NOT a decision-0002
#                        corner (vddio 5.50 V is outside the ratified
#                        3.3 V +-10 % window); committed only to show what
#                        a fast edge looks like, since no in-window fast pad
#                        liberty exists.
#   opensta-nolib.log    NEGATIVE CONTROL: pad LEF read, pad liberty NOT
#                        loaded -- the pad must black-box and no arc may be
#                        reported through it.
#   opensta-nolib-nolef.log  NEGATIVE CONTROL, harder form: neither pad LEF
#                        nor pad liberty loaded (the Test Plan's literal
#                        "[WARNING STA-0198] ... Creating black box"
#                        wording; the session then hard-errors on the LEF
#                        master lookup).
#
# Environment: PDK_ROOT (default ~/.ciel) must hold the pinned sky130A
# (open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7); `openroad` must be
# on $PATH. Logs embed the absolute paths of the machine that produced
# them; the arc numbers, not byte-identical logs, are what must reproduce.
#
# Usage: sim/pad-sta/run-opensta.sh [--pdk-root DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECORDS_DIR="${SCRIPT_DIR}/records"
PDK_ROOT="${PDK_ROOT:-${HOME}/.ciel}"

while [ $# -gt 0 ]; do
  case "$1" in
    --pdk-root=*) PDK_ROOT="${1#*=}" ;;
    -h|--help) sed -n '2,52p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

IO_REF="${PDK_ROOT}/sky130A/libs.ref/sky130_fd_io"
SC_REF="${PDK_ROOT}/sky130A/libs.ref/sky130_fd_sc_hd"
TCL="${SC_REF}/techlef/sky130_fd_sc_hd__nom.tlef"
SC_LEF="${SC_REF}/lef/sky130_fd_sc_hd.lef"
IO_LEF="${IO_REF}/lef/sky130_fd_io.lef"
SC_LIB_DIR="${SC_REF}/lib"
IO_LIB_DIR="${IO_REF}/lib"
NETLIST="${RECORDS_DIR}/padwrap.v"

for f in "${TCL}" "${SC_LEF}" "${IO_LEF}" "${NETLIST}" \
         "${SC_LIB_DIR}/sky130_fd_sc_hd__tt_025C_1v80.lib" \
         "${IO_LIB_DIR}/sky130_fd_io__top_gpiov2_tt_tt_025C_1v80_3v30.lib"; do
  [ -r "$f" ] || { echo "FATAL: missing $f (PDK_ROOT=${PDK_ROOT})" >&2; exit 1; }
done
command -v openroad >/dev/null || { echo "FATAL: openroad not on \$PATH" >&2; exit 1; }

# session <tag> <core-lib-suffix> <pad-lib-suffix|NONE> <load_pf> [lef-absent]
session() {
  local tag="$1" core="$2" padlib="$3" load="$4" lef="${5:-}"
  local tcl_dir
  tcl_dir="$(mktemp -d)"
  local tcl="${tcl_dir}/session.tcl"
  {
    echo "read_lef ${TCL}"
    echo "read_lef ${SC_LEF}"
    [ "${lef}" = "lef-absent" ] || echo "read_lef ${IO_LEF}"
    echo "read_liberty ${SC_LIB_DIR}/sky130_fd_sc_hd__${core}.lib"
    [ "${padlib}" = "NONE" ] || echo "read_liberty ${IO_LIB_DIR}/sky130_fd_io__${padlib}.lib"
    cat <<EOF
read_verilog ${NETLIST}
link_design padwrap
create_clock -name clk -period 20 [get_ports clk]
set_input_delay 0.0 -clock clk [get_ports pad_ipad]
set_output_delay 0.0 -clock clk [get_ports pad_opad]
set_load ${load} [get_nets pad_opad]
puts "BEGIN-REPORT"
report_checks -path_delay min_max -digits 4 -group_path_count 20 -fields {slew cap input_pin net}
report_worst_slack -max -digits 4
report_worst_slack -min -digits 4
puts "END-REPORT"
EOF
  } > "${tcl}"
  echo "== session ${tag}: core=${core} pad=${padlib} load=${load}pF lef=${lef:-read}"
  openroad -no_init -exit "${tcl}" > "${RECORDS_DIR}/opensta-${tag}.log" 2>&1 || true
  rm -rf "${tcl_dir}"
}

session tt-5pf        tt_025C_1v80 top_gpiov2_tt_tt_025C_1v80_3v30 5.0
session tt-10pf       tt_025C_1v80 top_gpiov2_tt_tt_025C_1v80_3v30 10.0
session tt-20pf       tt_025C_1v80 top_gpiov2_tt_tt_025C_1v80_3v30 20.0
session ss-10pf       ss_100C_1v60 top_gpiov2_ss_ss_100C_1v60_3v00 10.0
session ff-oow-10pf   ff_n40C_1v95 top_gpiov2_ff_ff_n40C_1v95_5v50 10.0
session nolib         tt_025C_1v80 NONE 10.0
session nolib-nolef   tt_025C_1v80 NONE 10.0 lef-absent

echo "done: logs in ${RECORDS_DIR}/"
