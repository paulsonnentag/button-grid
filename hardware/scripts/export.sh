#!/usr/bin/env bash
# Produce everything needed to order from JLCPCB, plus previews, in build/:
#   build/jlcpcb/button-grid-gerbers.zip   -> "Add gerber file"
#   build/jlcpcb/bom-jlcpcb.csv            -> PCB Assembly: BOM
#   build/jlcpcb/cpl-jlcpcb.csv            -> PCB Assembly: CPL / pick & place
#   build/jlcpcb/hand-solder-parts.csv     -> through-hole parts you solder yourself
#   build/docs/*                           -> schematic PDF, board SVG/PNG renders
set -euo pipefail
cd "$(dirname "$0")/../.."
K=hardware/scripts/kicad.sh
PCB=hardware/button-grid.kicad_pcb
SCH=hardware/button-grid.kicad_sch
J=build/jlcpcb; D=build/docs
rm -rf "$J" "$D"; mkdir -p "$J/gerbers" "$D"

# --- fabrication: gerbers + drill (JLCPCB recommended settings: Protel extensions,
#     subtract soldermask from silk, no X2) ---
$K kicad-cli pcb export gerbers --no-x2 --subtract-soldermask \
    --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
    -o "$J/gerbers/" "$PCB" >/dev/null
$K kicad-cli pcb export drill --format excellon --excellon-separate-th \
    --generate-map --map-format gerberx2 -o "$J/gerbers/" "$PCB" >/dev/null
(cd "$J/gerbers" && zip -q -r ../button-grid-gerbers.zip .)

# --- assembly: BOM + CPL in JLCPCB's column format ---
$K kicad-cli sch export netlist --format kicadsexpr -o build/button-grid.net "$SCH" >/dev/null
$K kicad-cli pcb export pos --format csv --units mm --side front --exclude-dnp \
    -o build/positions.csv "$PCB" >/dev/null
python3 hardware/scripts/jlc_bom_cpl.py build/button-grid.net build/positions.csv "$J"

# --- documentation ---
$K kicad-cli sch export pdf -o "$D/schematic.pdf" "$SCH" >/dev/null
$K kicad-cli sch export svg -o "$D/" "$SCH" >/dev/null
$K kicad-cli pcb export svg --mode-single --fit-page-to-board --exclude-drawing-sheet \
    --layers F.Cu,F.SilkS,F.Mask,Edge.Cuts -o "$D/pcb-front.svg" "$PCB" >/dev/null
$K kicad-cli pcb export svg --mode-single --fit-page-to-board --exclude-drawing-sheet --mirror \
    --layers B.Cu,B.SilkS,B.Mask,Edge.Cuts -o "$D/pcb-back.svg" "$PCB" >/dev/null
$K kicad-cli pcb export svg --mode-single --fit-page-to-board --exclude-drawing-sheet \
    --layers F.SilkS,F.Fab,F.CrtYd,Edge.Cuts -o "$D/assembly.svg" "$PCB" >/dev/null
# 3D renders need an OpenGL context; skip quietly where none is available
for side in top bottom; do
  $K kicad-cli pcb render --side $side --quality high --width 1800 --height 1000 \
      --background opaque --zoom 1.7 -o "$D/render-$side.png" "$PCB" >/dev/null 2>&1 || \
      echo "note: 3D render ($side) not available here"
done
# full KiCad project for download
(cd hardware && zip -q -r ../build/docs/button-grid-kicad.zip \
    button-grid.kicad_pro button-grid.kicad_sch led_bank.kicad_sch button-grid.kicad_pcb)
echo "exports written to build/"
