#!/usr/bin/env python3
"""Import Freerouting's session file and add GND pours on both copper layers.

    python3 hardware/gen/finish_pcb.py hardware/button-grid.kicad_pcb hardware/button-grid.ses
"""
import sys

import pcbnew


def add_gnd_zone(board, layer, gnd):
    bb = board.GetBoardEdgesBoundingBox()
    inset = pcbnew.FromMM(0.3)
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(gnd)
    z.SetZoneName(f"GND_{board.GetLayerName(layer)}")
    z.SetLocalClearance(pcbnew.FromMM(0.3))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(pcbnew.FromMM(0.3))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()),
                 (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        dx = inset if x == bb.GetLeft() else -inset
        dy = inset if y == bb.GetTop() else -inset
        o.Append(x + dx, y + dy)
    board.Add(z)
    return z


def main(pcb, ses):
    board = pcbnew.LoadBoard(pcb)
    for t in list(board.GetTracks()):
        board.Remove(t)
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("SES import failed")
    for z in list(board.Zones()):
        if z.GetZoneName().startswith("GND_"):
            board.Remove(z)
    gnd = board.FindNet("GND")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        add_gnd_zone(board, layer, gnd)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pcb, board)
    n_tracks = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
    n_vias = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
    print(f"imported {n_tracks} tracks, {n_vias} vias; GND pours filled")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
