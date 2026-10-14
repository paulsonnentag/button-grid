#!/usr/bin/env python3
"""Import Freerouting's session file and add GND pours on both copper layers.

    python3 hardware/gen/finish_pcb.py hardware/button-grid.kicad_pcb hardware/button-grid.ses
"""
import math
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


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def add_stitching_vias(board, gnd, pitch=6.0, margin=2.5, clearance=0.35, via=0.6, drill=0.3):
    """GND vias on a grid wherever they fit, tying the top and bottom pours together."""
    mm = pcbnew.ToMM
    obstacles = []  # (kind, geometry, half-width)
    for t in board.GetTracks():
        if t.GetNetCode() == gnd.GetNetCode():
            continue
        if t.GetClass() == "PCB_VIA":
            obstacles.append(("pt", (mm(t.GetPosition().x), mm(t.GetPosition().y)),
                              mm(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            obstacles.append(("seg", (mm(t.GetStart().x), mm(t.GetStart().y),
                                      mm(t.GetEnd().x), mm(t.GetEnd().y)), mm(t.GetWidth()) / 2))
    keep_out = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            keep_out.append((mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        if cy.OutlineCount():
            bb = cy.BBox()
            # stay out from under parts (and the ESP32 antenna keep-out)
            keep_out.append((mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
    edge = board.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = mm(edge.GetLeft()), mm(edge.GetTop()), mm(edge.GetRight()), mm(edge.GetBottom())
    r = via / 2
    added = 0
    y = y0 + margin
    while y <= y1 - margin:
        x = x0 + margin
        while x <= x1 - margin:
            ok = all(not (l - r - clearance < x < rr + r + clearance and t - r - clearance < y < b + r + clearance)
                     for l, t, rr, b in keep_out)
            if ok:
                for kind, g, hw in obstacles:
                    d = math.hypot(x - g[0], y - g[1]) if kind == "pt" else _seg_dist(x, y, *g)
                    if d < hw + r + clearance:
                        ok = False
                        break
            if ok:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
                v.SetWidth(pcbnew.FromMM(via))
                v.SetDrill(pcbnew.FromMM(drill))
                v.SetNet(gnd)
                board.Add(v)
                added += 1
            x += pitch
        y += pitch
    return added


def main(pcb, ses):
    board = pcbnew.LoadBoard(pcb)
    for t in list(board.GetTracks()):
        if not t.IsLocked() or t.GetNetname() == "GND" and t.GetClass() == "PCB_VIA":
            board.Remove(t)
    locked = {(t.GetClass(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)
              for t in board.GetTracks()}
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("SES import failed")
    # the session also contains our locked pre-routes: drop the unlocked copies
    for t in list(board.GetTracks()):
        key = (t.GetClass(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)
        if key in locked and not t.IsLocked():
            board.Remove(t)
    # the router necks tracks down at some pads; keep everything >= 0.2mm (JLCPCB min 0.127)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < pcbnew.FromMM(0.2):
            t.SetWidth(pcbnew.FromMM(0.2))
    for z in list(board.Zones()):
        if z.GetZoneName().startswith("GND_"):
            board.Remove(z)
    gnd = board.FindNet("GND")
    # through-hole GND pins (buttons, header) can end up in small pour pockets
    # between tracks where thermal spokes don't reach; connect them solidly instead
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd.GetNetCode() and pad.HasHole():
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    print(f"added {add_stitching_vias(board, gnd)} GND stitching vias")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        add_gnd_zone(board, layer, gnd)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pcb, board)
    n_tracks = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
    n_vias = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
    print(f"imported {n_tracks} tracks, {n_vias} vias; GND pours filled")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
