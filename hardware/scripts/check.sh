#!/usr/bin/env bash
# Run every design check and write reports + a summary JSON to build/reports/.
#   1. ERC          - KiCad electrical rules check on the schematic
#   2. netlist      - our own pin-by-pin connectivity assertions (check_netlist.py)
#   3. DRC          - KiCad design rules (JLCPCB-safe limits) + schematic/PCB parity
# Exit code is non-zero if any check fails.
set -uo pipefail
cd "$(dirname "$0")/../.."
K=hardware/scripts/kicad.sh
OUT=build/reports
mkdir -p "$OUT"
fail=0
declare -A status

$K kicad-cli sch erc --severity-all --exit-code-violations --format json \
    -o "$OUT/erc.json" hardware/button-grid.kicad_sch >/dev/null
r=$?; status[erc]=$r
$K kicad-cli sch erc --severity-all -o "$OUT/erc.rpt" hardware/button-grid.kicad_sch >/dev/null

$K kicad-cli sch export netlist --format kicadsexpr -o "$OUT/button-grid.net" \
    hardware/button-grid.kicad_sch >/dev/null
python3 hardware/scripts/check_netlist.py "$OUT/button-grid.net" > "$OUT/netlist.txt" 2>&1
r=$?; status[netlist]=$r

$K kicad-cli pcb drc --schematic-parity --severity-error --exit-code-violations --format json \
    -o "$OUT/drc.json" hardware/button-grid.kicad_pcb >/dev/null
r=$?; status[drc]=$r
$K kicad-cli pcb drc --schematic-parity --severity-all -o "$OUT/drc.rpt" \
    hardware/button-grid.kicad_pcb >/dev/null

python3 - "$OUT" "${status[erc]}" "${status[netlist]}" "${status[drc]}" <<'EOF'
import json, sys
out, erc, net, drc = sys.argv[1], *map(int, sys.argv[2:])
summary = {"erc": erc == 0, "netlist": net == 0, "drc": drc == 0}
json.dump(summary, open(f"{out}/summary.json", "w"), indent=2)
for k, v in summary.items():
    print(f"{k:8s} {'PASS' if v else 'FAIL'}")
EOF

for k in erc netlist drc; do [ "${status[$k]}" = 0 ] || fail=1; done
exit $fail
