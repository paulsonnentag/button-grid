#!/usr/bin/env python3
"""Turn KiCad's netlist + position file into JLCPCB's BOM and CPL CSVs.

JLCPCB's parts library sometimes defines a footprint's 0deg orientation
differently from KiCad. ROTATION_FIX holds the usual corrections; always check
the 3D placement preview on the JLCPCB order page before paying.
"""
import csv
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gen"))
from sexpr import find, find_all, parse  # noqa: E402

ROTATION_FIX = [  # (footprint regex, degrees added)
    (r"^SOIC-", 270),
    (r"^TSOT-23", 180),
    (r"^SOT-23", 180),
    (r"^D_SMA", 180),
]


def comps_from_netlist(path):
    tree = parse(open(path, encoding="utf-8").read())
    out = []
    for c in find_all(find(tree, "components"), "comp"):
        fields = {}
        fl = find(c, "fields")
        if fl:
            for f in find_all(fl, "field"):
                fields[str(find(f, "name")[1])] = str(f[2]) if len(f) > 2 else ""
        out.append({"ref": str(find(c, "ref")[1]), "value": str(find(c, "value")[1]),
                    "footprint": str(find(c, "footprint")[1]), "fields": fields})
    return out


def natural(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def main(netlist, positions, outdir):
    comps = comps_from_netlist(netlist)
    smd = [c for c in comps if c["fields"].get("Assembly") not in ("hand-solder", "none")]
    hand = [c for c in comps if c["fields"].get("Assembly") == "hand-solder"]

    groups = OrderedDict()
    for c in sorted(smd, key=lambda c: natural(c["ref"])):
        key = (c["value"], c["footprint"].split(":")[1], c["fields"].get("LCSC", ""))
        groups.setdefault(key, []).append(c["ref"])
    with open(os.path.join(outdir, "bom-jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, fp, lcsc), refs in groups.items():
            w.writerow([val, ",".join(refs), fp, lcsc])

    hgroups = OrderedDict()
    for c in sorted(hand, key=lambda c: natural(c["ref"])):
        hgroups.setdefault((c["value"], c["footprint"].split(":")[1]), []).append(c["ref"])
    with open(os.path.join(outdir, "hand-solder-parts.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "Value", "Designators", "Footprint", "LCSC (optional)"])
        for (val, fp), refs in hgroups.items():
            lcsc = next(c["fields"].get("LCSC", "") for c in hand if c["ref"] == refs[0])
            w.writerow([len(refs), val, ",".join(refs), fp, lcsc])

    smd_refs = {c["ref"] for c in smd}
    rows = []
    with open(positions, newline="") as f:
        for r in csv.DictReader(f):
            if r["Ref"] not in smd_refs:
                continue
            rot = float(r["Rot"])
            for pat, delta in ROTATION_FIX:
                if re.search(pat, r["Package"]):
                    rot = (rot + delta) % 360
                    break
            rows.append([r["Ref"], f'{float(r["PosX"]):.3f}mm', f'{float(r["PosY"]):.3f}mm',
                         "Top" if r["Side"].lower().startswith("top") else "Bottom", f"{rot:g}"])
    missing = smd_refs - {r[0] for r in rows}
    if missing:
        raise SystemExit(f"parts in BOM but not in position file: {sorted(missing)}")
    with open(os.path.join(outdir, "cpl-jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writerows(sorted(rows, key=lambda r: natural(r[0])))
    print(f"BOM: {len(groups)} lines / {len(smd)} parts; CPL: {len(rows)} placements; "
          f"hand-solder: {len(hand)} parts")


if __name__ == "__main__":
    main(*sys.argv[1:4])
