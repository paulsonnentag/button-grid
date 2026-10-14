import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
ok = pcbnew.ExportSpecctraDSN(b, sys.argv[2])
print("DSN export", "ok" if ok else "FAILED")
sys.exit(0 if ok else 1)
