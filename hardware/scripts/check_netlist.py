#!/usr/bin/env python3
"""Independent connectivity checks on the exported KiCad netlist.

ERC only knows generic rules (driven inputs, dangling labels, ...). This script
knows what the board is *supposed* to do and asserts it pin by pin:

  * every one of the 64 LED terminals goes ULN2803 output <- 74HC595 output
  * the 74HC595s form one chain ESP32 IO38 -> bank1 -> ... -> bank8 -> ESP32 IO42
  * clock / latch / output-enable reach all 8 shift registers
  * every matrix line: ESP32 GPIO -> 100R -> terminal, with 22k pull-up
  * power pins, USB, buck-converter feedback voltage, strapping pins, BOM fields

Usage:  python3 check_netlist.py hardware/button-grid.net
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gen"))
from sexpr import find, find_all, parse  # noqa: E402

N_BANKS = 8
ROW_GPIO = ["IO4", "IO5", "IO6", "IO7", "IO15", "IO16", "IO17", "IO18"]
COL_GPIO = ["IO8", "IO9", "IO10", "IO11", "IO12", "IO13", "IO14", "IO21"]
STRAPPING = {"IO0", "IO3", "IO45", "IO46"}

errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)
    return cond


def load(path):
    tree = parse(open(path, encoding="utf-8").read())
    comps = {}
    for c in find_all(find(tree, "components"), "comp"):
        ref = str(find(c, "ref")[1])
        fields = {}
        fl = find(c, "fields")
        if fl:
            for f in find_all(fl, "field"):
                name = str(find(f, "name")[1])
                fields[name] = str(f[2]) if len(f) > 2 else ""
        comps[ref] = {"value": str(find(c, "value")[1]),
                      "footprint": str(find(c, "footprint")[1]) if find(c, "footprint") else "",
                      "fields": fields}
    nets = {}
    pin_net = {}
    for n in find_all(find(tree, "nets"), "net"):
        name = str(find(n, "name")[1])
        nodes = set()
        for node in find_all(n, "node"):
            ref, pin = str(find(node, "ref")[1]), str(find(node, "pin")[1])
            func = find(node, "pinfunction")
            nodes.add((ref, pin))
            pin_net[(ref, pin)] = name
            if func:
                pin_net[(ref, str(func[1]))] = name
        nets[name] = nodes
    return comps, nets, pin_net


def main(path):
    comps, nets, pin_net = load(path)

    def net(ref, pin):
        n = pin_net.get((ref, str(pin)))
        check(n is not None, f"{ref}.{pin} is not connected / missing")
        return n

    def same(a, b, what):
        na, nb = net(*a), net(*b)
        check(na is not None and na == nb, f"{what}: {a[0]}.{a[1]} ({na}) != {b[0]}.{b[1]} ({nb})")

    def on(a, netname, what=""):
        n = net(*a)
        check(n == netname, f"{what or a}: {a[0]}.{a[1]} is on {n}, expected {netname}")

    # ---- LED banks -------------------------------------------------------
    esp = "U1"
    q_pins = ["15", "1", "2", "3", "4", "5", "6", "7"]          # 74HC595 QA..QH
    uln_out = ["18", "17", "16", "15", "14", "13", "12", "11"]  # ULN2803 O1..O8
    led_terminals = 0
    for k in range(1, N_BANKS + 1):
        sr, drv, tb = f"U{10 + k}", f"U{20 + k}", f"J{10 + k}"
        for r in (sr, drv, tb):
            check(r in comps, f"missing {r}")
        check(comps.get(sr, {}).get("value") == "74HC595", f"{sr} should be 74HC595")
        check(comps.get(drv, {}).get("value") == "ULN2803A", f"{drv} should be ULN2803A")
        for i in range(8):
            same((sr, q_pins[i]), (drv, str(i + 1)), f"bank{k} Q{i}->I{i + 1}")
            n = net(drv, uln_out[i])
            same((drv, uln_out[i]), (tb, str(i + 1)), f"bank{k} O{i + 1}->terminal {i + 1}")
            if n:
                check(len(nets[n]) == 2, f"LED net {n} should only join ULN output and terminal, "
                                         f"has {sorted(nets[n])}")
                led_terminals += 1
        on((tb, "9"), "+12V"); on((tb, "10"), "+12V")
        on((drv, "10"), "+12V", "ULN COM"); on((drv, "9"), "GND")
        on((sr, "16"), "+3V3", "595 VCC"); on((sr, "8"), "GND")
        on((sr, "10"), "+3V3", "595 /SRCLR tied high")
        same((sr, "11"), (esp, "IO39"), f"bank{k} SRCLK")
        same((sr, "12"), (esp, "IO40"), f"bank{k} RCLK")
        same((sr, "13"), (esp, "IO41"), f"bank{k} /OE")
        prev = (esp, "IO38") if k == 1 else (f"U{10 + k - 1}", "9")
        same(prev, (sr, "14"), f"chain into bank{k}")
    same((f"U{10 + N_BANKS}", "9"), (esp, "IO42"), "chain return to ESP32 IO42")
    check(led_terminals == 64, f"expected 64 LED channels, found {led_terminals}")
    oe = net(esp, "IO41")
    check(oe and ("R5", "2") in nets[oe] and net("R5", "1") == "+3V3",
          "OE_N needs pull-up (LEDs dark during boot)")

    # ---- button matrix -----------------------------------------------------
    for kind, gpios, rser, rpu, term in (("ROW", ROW_GPIO, 10, 30, "J3"),
                                         ("COL", COL_GPIO, 20, 40, "J4")):
        for i, g in enumerate(gpios):
            same((esp, g), (f"R{rser + i}", "1"), f"{kind}{i} GPIO->series R")
            same((f"R{rser + i}", "2"), (term, str(i + 1)), f"{kind}{i} series R->terminal")
            same((f"R{rpu + i}", "2"), (term, str(i + 1)), f"{kind}{i} pull-up")
            on((f"R{rpu + i}", "1"), "+3V3", f"{kind}{i} pull-up to 3V3")
            check(comps[f"R{rser + i}"]["value"] == "100", f"R{rser + i} should be 100R")
    used = set(ROW_GPIO + COL_GPIO + ["IO38", "IO39", "IO40", "IO41", "IO42"])
    check(not (used & STRAPPING), f"strapping pins used for I/O: {used & STRAPPING}")

    # ---- ESP32 + USB ------------------------------------------------------------
    on((esp, "3V3"), "+3V3"); on((esp, "GND"), "GND")
    same((esp, "USB_D+"), ("J2", "A6"), "USB D+"); same(("J2", "A6"), ("J2", "B6"), "USB D+ A/B")
    same((esp, "USB_D-"), ("J2", "A7"), "USB D-"); same(("J2", "A7"), ("J2", "B7"), "USB D- A/B")
    for cc, rr in (("A5", "R7"), ("B5", "R8")):
        same(("J2", cc), (rr, "1"), f"USB {cc} 5.1k"); on((rr, "2"), "GND")
        check(comps[rr]["value"] == "5.1k", f"{rr} must be 5.1k for USB-C sink")
    on((esp, "EN"), net("R3", "2"), "EN pull-up")

    # ---- power -----------------------------------------------------------------
    on(("J1", "2"), "GND", "jack sleeve")
    same(("J1", "1"), ("D1", "2"), "jack tip -> reverse-protection diode anode")
    on(("D1", "1"), "+12V", "reverse-protection diode cathode")
    on(("U2", "VIN"), net("D2", "1"), "buck VIN from 12V diode")
    on(("D2", "2"), "+12V"); on(("D3", "2"), "VBUS")
    same(("D2", "1"), ("D3", "1"), "diode-OR into buck")
    same(("U2", "SW"), ("L1", "1"), "buck SW->L"); on(("L1", "2"), "+3V3")
    same(("U2", "FB"), ("R1", "2"), "FB divider"); same(("U2", "FB"), ("R2", "1"), "FB divider")

    def ohms(v):
        m = re.fullmatch(r"([\d.]+)([kM]?)", v)
        return float(m.group(1)) * {"": 1, "k": 1e3, "M": 1e6}[m.group(2)]
    vout = 0.596 * (1 + ohms(comps["R1"]["value"]) / ohms(comps["R2"]["value"]))
    check(3.2 <= vout <= 3.45, f"buck output {vout:.2f}V outside ESP32 range")
    print(f"buck output voltage: {vout:.3f} V")

    # ---- generic ----------------------------------------------------------------
    for name, nodes in nets.items():
        refs = {r for r, _ in nodes}
        if len(nodes) < 2 and not name.startswith("unconnected-"):
            errors.append(f"net {name} has a single connection {sorted(nodes)}")
        if "GND" in name and "+" in name:
            errors.append(f"suspicious net {name}")
    for ref, c in comps.items():
        hand = c["fields"].get("Assembly") in ("hand-solder", "none")
        check(c["footprint"], f"{ref} has no footprint")
        if not hand:
            check(re.fullmatch(r"C\d+", c["fields"].get("LCSC", "")),
                  f"{ref} ({c['value']}) has no LCSC part number")

    print(f"{len(comps)} components, {len(nets)} nets, {led_terminals} LED channels checked")
    if errors:
        print(f"\n{len(errors)} PROBLEM(S):")
        for e in errors:
            print("  -", e)
        return 1
    print("netlist OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "hardware/button-grid.net"))
