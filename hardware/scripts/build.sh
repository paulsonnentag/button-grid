#!/usr/bin/env bash
# Regenerate the KiCad project from the Python generators (schematic + placement),
# then run every check. Routing is a separate step (route.sh) because it is slow.
#
#   hardware/scripts/build.sh            # schematic + placed PCB + checks
#
# WARNING: overwrites hardware/*.kicad_sch and *.kicad_pcb. Once you edit the
# design by hand in KiCad, stop using this and just run check.sh.
set -euo pipefail
cd "$(dirname "$0")/../.."
K=hardware/scripts/kicad.sh
$K python3 hardware/gen/build_project.py hardware
$K python3 hardware/gen/build_schematic.py hardware
$K kicad-cli sch export netlist --format kicadsexpr -o hardware/button-grid.net hardware/button-grid.kicad_sch
$K python3 hardware/gen/build_pcb.py hardware/button-grid.net hardware/button-grid.kicad_pcb
