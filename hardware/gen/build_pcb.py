#!/usr/bin/env python3
"""Create button-grid.kicad_pcb from the exported netlist and place every part.

Run inside the KiCad 9 docker image (needs the `pcbnew` module):
    python3 hardware/gen/build_pcb.py hardware/button-grid.net hardware/button-grid.kicad_pcb

Placement only; routing is done afterwards by Freerouting (see route.sh) and the
GND pours by finish_pcb.py. Like the schematic generator, this is a bootstrap:
once you move things by hand in KiCad, the .kicad_pcb file is the source of truth.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
from sexpr import find, find_all, parse  # noqa: E402

FP_DIR = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

# board outline (mm) and page offset
W, H = 208.0, 110.0
X0, Y0 = 40.0, 40.0
N_BANKS = 8
BANK_PITCH = 38.0
BANK_X = 12.0


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(X0 + x), pcbnew.FromMM(Y0 + y))


def placements():
    """ref -> (x, y, rotation_deg, side) in board coordinates (origin top-left)."""
    p = {}
    for k in range(1, N_BANKS + 1):
        top = k <= 4
        x0 = BANK_X + BANK_PITCH * ((k - 1) % 4)
        cx = x0 + 17.5
        if top:
            # terminal: wire entry facing the top edge, pads run right->left from pin 1
            p[f"J{10 + k}"] = (x0 + 31.5 + 0.0, 6.04, 180, "F")
            p[f"U{20 + k}"] = (cx, 19.0, 90, "F")
            p[f"U{10 + k}"] = (cx, 32.0, 270, "F")
            p[f"C{20 + k}"] = (x0 + 29.0, 17.0, 90, "F")
            p[f"C{10 + k}"] = (x0 + 26.0, 32.0, 90, "F")
        else:
            p[f"J{10 + k}"] = (x0, H - 6.04, 0, "F")
            p[f"U{20 + k}"] = (cx, H - 19.0, 270, "F")
            p[f"U{10 + k}"] = (cx, H - 32.0, 90, "F")
            p[f"C{20 + k}"] = (x0 + 29.0, H - 17.0, 90, "F")
            p[f"C{10 + k}"] = (x0 + 26.0, H - 32.0, 90, "F")

    # button matrix: terminals on the left edge, wire entry facing left
    p["J3"] = (6.04, 22.0, 270, "F")
    p["J4"] = (6.04, 63.5, 270, "F")
    for i in range(8):
        x = 16.0 + 3.0 * i
        p[f"R{10 + i}"] = (x, 42.0, 90, "F")   # row series
        p[f"R{30 + i}"] = (x, 46.5, 90, "F")   # row pull-up
        p[f"R{20 + i}"] = (x, 63.5, 90, "F")   # col series
        p[f"R{40 + i}"] = (x, 68.0, 90, "F")   # col pull-up

    # ESP32-S3 module at the right edge, antenna pointing out of the board
    p["U1"] = (W - 27.8, 55.0, 270, "F")
    p["C9"] = (W - 46.0, 47.0, 0, "F")
    p["C10"] = (W - 46.0, 50.0, 0, "F")
    p["R3"] = (W - 52.0, 44.0, 0, "F")
    p["C8"] = (W - 52.0, 47.0, 0, "F")
    p["SW1"] = (W - 68.0, 40.0, 0, "F")
    p["R4"] = (W - 52.0, 62.0, 0, "F")
    p["SW2"] = (W - 68.0, 62.0, 0, "F")
    p["R5"] = (W - 52.0, 56.0, 0, "F")
    p["R6"] = (W - 52.0, 68.0, 0, "F")
    p["D4"] = (W - 52.0, 71.0, 0, "F")
    p["J5"] = (W - 80.0, 50.0, 0, "F")

    # power: barrel jack top-right (opening to the right edge), buck converter next to it
    p["J1"] = (W - 14.04, 14.0, 180, "F")
    p["D1"] = (W - 22.0, 25.0, 180, "F")
    p["C1"] = (W - 26.0, 30.0, 90, "F")
    p["C2"] = (W - 23.0, 30.0, 90, "F")
    p["D2"] = (W - 40.0, 8.0, 0, "F")
    p["D3"] = (W - 40.0, 13.0, 0, "F")
    p["C3"] = (W - 34.0, 18.0, 90, "F")
    p["C4"] = (W - 31.0, 18.0, 90, "F")
    p["U2"] = (W - 33.0, 24.0, 0, "F")
    p["C5"] = (W - 33.0, 28.5, 0, "F")
    p["L1"] = (W - 39.0, 24.0, 90, "F")
    p["R1"] = (W - 36.0, 30.0, 90, "F")
    p["R2"] = (W - 33.0, 31.5, 0, "F")
    p["C6"] = (W - 43.0, 22.0, 90, "F")
    p["C7"] = (W - 43.0, 27.0, 90, "F")

    # USB-C bottom-right, opening to the right edge
    p["J2"] = (W - 4.2, 94.0, 90, "F")
    p["R7"] = (W - 13.0, 90.0, 90, "F")
    p["R8"] = (W - 13.0, 98.0, 90, "F")

    # mounting holes
    p["H1"] = (4.5, 4.5, 0, "F")
    p["H2"] = (W - 4.5, 4.5, 0, "F")
    p["H3"] = (4.5, H - 4.5, 0, "F")
    p["H4"] = (W - 4.5, H - 4.5, 0, "F")
    return p


def read_netlist(path):
    tree = parse(open(path, encoding="utf-8").read())
    comps = []
    for c in find_all(find(tree, "components"), "comp"):
        fields = {}
        fl = find(c, "fields")
        if fl:
            for f in find_all(fl, "field"):
                fields[str(find(f, "name")[1])] = str(f[2]) if len(f) > 2 else ""
        sp = find(c, "sheetpath")
        comps.append({
            "ref": str(find(c, "ref")[1]), "value": str(find(c, "value")[1]),
            "footprint": str(find(c, "footprint")[1]), "fields": fields,
            "sheet_names": str(find(sp, "names")[1]), "sheet_tstamps": str(find(sp, "tstamps")[1]),
            "uuid": str(find(c, "tstamps")[1]),
        })
    pad_net = {}
    names = []
    for n in find_all(find(tree, "nets"), "net"):
        name = str(find(n, "name")[1])
        names.append(name)
        for node in find_all(n, "node"):
            pad_net[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name
    return comps, names, pad_net


def add_outline(board):
    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(mm(*a))
        seg.SetEnd(mm(*b))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)


def add_text(board, text, x, y, size=1.5, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(mm(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(size * 0.15))
    board.Add(t)


def main(net_path, out_path):
    comps, net_names, pad_net = read_netlist(net_path)
    board = pcbnew.NewBoard(out_path)
    board.SetCopperLayerCount(2)

    nets = {}
    for name in net_names:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    place = placements()
    missing = [c["ref"] for c in comps if c["ref"] not in place]
    if missing:
        raise SystemExit(f"no placement for {missing}")

    for c in comps:
        lib, name = c["footprint"].split(":")
        fp = pcbnew.FootprintLoad(os.path.join(FP_DIR, lib + ".pretty"), name)
        if fp is None:
            raise SystemExit(f"footprint {c['footprint']} not found")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(c["ref"])
        if c["ref"].startswith("H"):
            fp.Reference().SetVisible(False)
        # the module's optional 0.2mm thermal vias are below JLCPCB's standard
        # 0.3mm minimum drill; the big GND pad is enough for this low-power board
        for pad in list(fp.Pads()):
            if pad.HasHole() and pad.GetDrillSize().x < pcbnew.FromMM(0.3):
                fp.Remove(pad)
        fp.SetValue(c["value"])
        for k, v in c["fields"].items():
            if k in ("Footprint", "Datasheet", "Description"):
                continue
            fp.SetField(k, v)
            f = fp.GetFieldByName(k)
            if f:
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
        fp.SetPath(pcbnew.KIID_PATH(c["sheet_tstamps"] + c["uuid"]))
        fp.SetSheetname(c["sheet_names"])
        fp.SetSheetfile("led_bank.kicad_sch" if c["sheet_names"].startswith("/Bank")
                        else "button-grid.kicad_sch")
        if c["fields"].get("Assembly") in ("hand-solder", "none"):
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        for pad in fp.Pads():
            n = pad_net.get((c["ref"], pad.GetNumber()))
            if n:
                pad.SetNet(nets[n])
        x, y, rot, side = place[c["ref"]]
        board.Add(fp)
        fp.SetPosition(mm(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), False)

    add_outline(board)
    add_text(board, "button-grid  8x8  ESP32-S3", W / 2 - 22, H / 2 + 2, 2.0)
    for k in range(1, N_BANKS + 1):
        x0 = BANK_X + BANK_PITCH * ((k - 1) % 4)
        y = 13.5 if k <= 4 else H - 13.5
        first = (k - 1) * 8
        add_text(board, f"LED {first}-{first + 7}  (+12V at 9,10)", x0 + 1, y, 1.0)
    add_text(board, "ROWS", 1.0, 17.0, 1.0)
    add_text(board, "COLS", 1.0, 58.5, 1.0)
    pcbnew.SaveBoard(out_path, board)
    print(f"placed {len(comps)} footprints -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
