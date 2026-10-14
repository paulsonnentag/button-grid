"""Export the board to Specctra DSN for Freerouting.

Clearances are padded by 10um so rounding in the router can't produce a
track that is a few microns under KiCad's DRC limit.
"""
import re
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
if not pcbnew.ExportSpecctraDSN(b, sys.argv[2]):
    sys.exit("DSN export FAILED")
with open(sys.argv[2]) as f:
    dsn = f.read()
dsn = re.sub(r"\(clearance ([\d.]+)", lambda m: f"(clearance {float(m.group(1)) + 10:g}", dsn)
with open(sys.argv[2], "w") as f:
    f.write(dsn)
print("DSN export ok")
