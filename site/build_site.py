#!/usr/bin/env python3
"""Build the static GitHub Pages site into build/site/.

Expects hardware/scripts/check.sh and export.sh to have run (build/reports,
build/jlcpcb, build/docs). Uses only the Python standard library.
"""
import csv
import datetime
import html
import json
import os
import shutil
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = os.path.join(ROOT, "build")
SITE = os.path.join(B, "site")


def rel(*p):
    return os.path.join(B, *p)


def copy(src, dst_name=None):
    if not os.path.exists(src):
        return None
    dst = os.path.join(SITE, "files", dst_name or os.path.basename(src))
    shutil.copy(src, dst)
    return "files/" + os.path.basename(dst)


def read(path, limit=200_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()[:limit]
    except FileNotFoundError:
        return "(not generated)"


def git(*args):
    try:
        return subprocess.check_output(["git", "-C", ROOT, *args], text=True).strip()
    except Exception:
        return ""


def table(path, limit=None):
    try:
        with open(path, newline="") as f:
            rows = list(csv.reader(f))
    except FileNotFoundError:
        return "<p>(not generated)</p>"
    head, body = rows[0], rows[1:limit]
    h = "".join(f"<th>{html.escape(c)}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def drc_counts():
    try:
        d = json.load(open(rel("reports", "drc.json")))
    except Exception:
        return None
    return {"violations": len(d.get("violations", [])),
            "unconnected": len(d.get("unconnected_items", [])),
            "parity": len(d.get("schematic_parity", []))}


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(os.path.join(SITE, "files"))
    os.makedirs(os.path.join(SITE, "kicad"))

    # KiCad sources for the interactive viewer
    for f in ("button-grid.kicad_sch", "led_bank.kicad_sch", "button-grid.kicad_pcb",
              "button-grid.kicad_pro"):
        shutil.copy(os.path.join(ROOT, "hardware", f), os.path.join(SITE, "kicad", f))

    dl = {
        "gerbers": copy(rel("jlcpcb", "button-grid-gerbers.zip")),
        "bom": copy(rel("jlcpcb", "bom-jlcpcb.csv")),
        "cpl": copy(rel("jlcpcb", "cpl-jlcpcb.csv")),
        "hand": copy(rel("jlcpcb", "hand-solder-parts.csv")),
        "pdf": copy(rel("docs", "schematic.pdf")),
        "kicad": copy(rel("docs", "button-grid-kicad.zip")),
        "front": copy(rel("docs", "pcb-front.svg")),
        "back": copy(rel("docs", "pcb-back.svg")),
        "assembly": copy(rel("docs", "assembly.svg")),
        "r_top": copy(rel("docs", "render-top.png")),
        "r_bottom": copy(rel("docs", "render-bottom.png")),
        "erc": copy(rel("reports", "erc.rpt")),
        "drc": copy(rel("reports", "drc.rpt")),
        "net": copy(rel("reports", "netlist.txt")),
    }
    try:
        summary = json.load(open(rel("reports", "summary.json")))
    except Exception:
        summary = {}
    counts = drc_counts()

    def badge(ok):
        if ok is None:
            return '<span class="badge na">not run</span>'
        return '<span class="badge ok">PASS</span>' if ok else '<span class="badge bad">FAIL</span>'

    all_ok = bool(summary) and all(summary.values())
    commit = git("rev-parse", "--short", "HEAD")
    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    hero = dl["r_top"] or dl["front"]

    tests = [
        ("erc", "Electrical rules check (ERC)",
         "KiCad checks the schematic for unconnected pins, undriven power inputs, conflicting "
         "outputs, dangling labels and similar mistakes.", "erc.rpt"),
        ("netlist", "Connectivity assertions",
         "Our own script (<code>hardware/scripts/check_netlist.py</code>) reads the netlist and "
         "checks the intended circuit pin by pin: all 64 LED terminals go through a ULN2803 "
         "output to the right 74HC595 output; the shift registers form one chain from ESP32 "
         "IO38 to IO42; clock/latch/enable reach every chip; every matrix line has its series "
         "resistor and pull-up; USB CC resistors; buck converter feedback gives 3.3 V; "
         "no strapping pins used; every assembled part has an LCSC number.", "netlist.txt"),
        ("drc", "Design rules check (DRC) + schematic parity",
         "KiCad checks the PCB against JLCPCB-safe manufacturing limits (clearances, track "
         "widths, drill sizes, board edge), that every net is fully routed, and that the PCB "
         "matches the schematic exactly.", "drc.rpt"),
    ]
    test_html = ""
    for key, title, desc, rpt in tests:
        extra = ""
        if key == "drc" and counts:
            extra = (f'<p class="meta">{counts["violations"]} violations · '
                     f'{counts["unconnected"]} unrouted connections · '
                     f'{counts["parity"]} schematic/PCB mismatches (errors and warnings)</p>')
        text = read(rel("reports", rpt))
        test_html += f"""
      <div class="test">
        <div class="test-head">{badge(summary.get(key))}<h3>{title}</h3></div>
        <p>{desc}</p>{extra}
        <details><summary>Full report</summary><pre>{html.escape(text)}</pre></details>
      </div>"""

    def a(key, label, note):
        if not dl.get(key):
            return f'<li class="missing">{label} <span>(not generated)</span></li>'
        return f'<li><a href="{dl[key]}" download>{label}</a><span>{note}</span></li>'

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Button Grid PCB</title>
<script type="module" src="https://kicanvas.org/kicanvas/kicanvas.js"></script>
<style>
:root {{
  --bg: #f6f7f9; --card: #ffffff; --text: #1d2330; --muted: #5d6677; --line: #dfe3ea;
  --accent: #2f6fdd; --ok: #1f8a4c; --bad: #c62f2f; --code: #f0f2f6;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #12151b; --card: #1a1f27; --text: #e6e9ef; --muted: #9aa3b2; --line: #2b323d;
          --accent: #6b9cff; --ok: #3fbf74; --bad: #ff6b6b; --code: #222833; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text);
       font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }}
header h1 {{ margin: 0 0 4px; font-size: 1.9rem; }}
header p {{ margin: 0; color: var(--muted); }}
nav {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0 8px; }}
nav a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
section {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px;
          padding: 20px; margin: 20px 0; }}
h2 {{ margin-top: 0; }}
.status {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-top: 12px; }}
.badge {{ font-size: .75rem; font-weight: 700; padding: 3px 9px; border-radius: 99px; color: #fff; }}
.badge.ok {{ background: var(--ok); }} .badge.bad {{ background: var(--bad); }}
.badge.na {{ background: var(--muted); }}
.big {{ font-size: 1rem; padding: 6px 14px; }}
img.hero {{ width: 100%; border-radius: 8px; border: 1px solid var(--line); background: #fff; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.grid2 figure {{ margin: 0; }} .grid2 img {{ width: 100%; background: #fff; border-radius: 8px;
  border: 1px solid var(--line); }}
figcaption {{ color: var(--muted); font-size: .9rem; }}
@media (max-width: 700px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
kicanvas-embed {{ display: block; width: 100%; height: 640px; border: 1px solid var(--line);
                 border-radius: 8px; overflow: hidden; }}
.test {{ border-top: 1px solid var(--line); padding: 14px 0; }}
.test:first-of-type {{ border-top: 0; }}
.test-head {{ display: flex; gap: 10px; align-items: center; }}
.test-head h3 {{ margin: 0; font-size: 1.1rem; }}
.meta {{ color: var(--muted); font-size: .9rem; }}
details summary {{ cursor: pointer; color: var(--accent); }}
pre {{ background: var(--code); padding: 12px; border-radius: 8px; overflow: auto; max-height: 420px;
      font-size: .8rem; }}
code {{ background: var(--code); padding: 1px 5px; border-radius: 4px; font-size: .9em; }}
ul.dl {{ list-style: none; padding: 0; margin: 0; }}
ul.dl li {{ padding: 8px 0; border-bottom: 1px solid var(--line); display: flex; gap: 12px;
           flex-wrap: wrap; align-items: baseline; }}
ul.dl a {{ color: var(--accent); font-weight: 600; }}
ul.dl span, li.missing span {{ color: var(--muted); font-size: .9rem; }}
ol li {{ margin: 6px 0; }}
.tw {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .85rem; }}
th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
td:nth-child(2) {{ word-break: break-word; }}
footer {{ color: var(--muted); font-size: .85rem; text-align: center; }}
</style>
</head>
<body>
<main>
<header>
  <h1>Button Grid PCB</h1>
  <p>ESP32-S3 controller for an 8×8 diode button matrix with 64 individually switched 12 V LEDs
     (8× 74HC595 + 8× ULN2803A). Two-layer board, {208} × {110} mm, built for JLCPCB.</p>
  <div class="status">
    <span class="badge {'ok' if all_ok else 'bad'} big">{'All checks pass' if all_ok else 'Checks failing'}</span>
    <span class="meta">commit <code>{html.escape(commit or "local")}</code> · built {when}</span>
  </div>
  <nav><a href="#board">Board</a><a href="#viewer">Design files</a><a href="#tests">Tests</a>
       <a href="#order">Order at JLCPCB</a><a href="#bom">Parts</a></nav>
</header>

<section id="board">
  <h2>Board</h2>
  {f'<img class="hero" src="{hero}" alt="PCB top view">' if hero else '<p>(render not generated)</p>'}
  <div class="grid2" style="margin-top:16px">
    {f'<figure><img src="{dl["front"]}" alt="front copper"><figcaption>Top copper + silkscreen</figcaption></figure>' if dl["front"] else ''}
    {f'<figure><img src="{dl["back"]}" alt="back copper"><figcaption>Bottom copper (mirrored)</figcaption></figure>' if dl["back"] else ''}
  </div>
  <h3>How it works</h3>
  <ul>
    <li><b>LEDs:</b> 74HC595 chain (bank 1 first) → ULN2803A low-side switches → screw terminals.
        Each 10-pole terminal: pins 1–8 = LED cathode wires, pins 9–10 = +12 V for the LED anodes.
        LEDs are dark at power-up (<code>OE</code> is pulled high until firmware enables it).</li>
    <li><b>Buttons:</b> rows and columns go straight to 16 ESP32 GPIOs through 100 Ω resistors
        with 22 kΩ pull-ups (terminals ROWS and COLS on the left edge).</li>
    <li><b>Power:</b> 12 V wall adapter (5.5×2.1 mm, centre +, ≥2 A) → SS54 reverse-polarity diode →
        LED supply; TPS54202 buck → 3.3 V logic. USB-C alone can also power the logic for flashing.</li>
  </ul>
</section>

<section id="viewer">
  <h2>Design files</h2>
  <p>Interactive viewer (pan/zoom, click parts). Use the panel to switch between the root schematic,
     the LED-bank sheet and the PCB. Open the files themselves in KiCad 9.</p>
  <kicanvas-embed controls="full">
    <kicanvas-source src="kicad/button-grid.kicad_sch"></kicanvas-source>
    <kicanvas-source src="kicad/led_bank.kicad_sch"></kicanvas-source>
    <kicanvas-source src="kicad/button-grid.kicad_pcb"></kicanvas-source>
  </kicanvas-embed>
  <ul class="dl" style="margin-top:12px">
    {a("kicad", "KiCad project (.zip)", "schematic + PCB, open in KiCad 9")}
    {a("pdf", "Schematic PDF", "all sheets")}
    {a("assembly", "Assembly drawing (SVG)", "part placement and references")}
  </ul>
</section>

<section id="tests">
  <h2>Tests</h2>
  <p>Run automatically on every push by GitHub Actions (<code>hardware/scripts/check.sh</code>).</p>
  {test_html}
</section>

<section id="order">
  <h2>Order at JLCPCB</h2>
  <ul class="dl">
    {a("gerbers", "Gerber + drill files (.zip)", "upload on jlcpcb.com → Add gerber file")}
    {a("bom", "BOM (CSV)", "PCB Assembly → BOM file")}
    {a("cpl", "Pick &amp; place / CPL (CSV)", "PCB Assembly → CPL file")}
    {a("hand", "Hand-solder parts list (CSV)", "screw terminals, barrel jack, buttons, header")}
  </ul>
  <ol>
    <li>Upload the gerber zip. Defaults are fine: 2 layers, 1.6 mm, HASL. Quantity 5.</li>
    <li>Enable <b>PCB Assembly</b>, "Economic", top side, assemble <b>2</b> boards.</li>
    <li>Upload the BOM and CPL. Check that every line matched a part and is in stock.</li>
    <li>On the placement preview, check the rotation of the chips (pin-1 dot) and the USB-C
        connector, and fix it with the rotate button if one is turned.</li>
    <li>Order the through-hole parts from the hand-solder list (LCSC/Amazon/eBay) and solder
        them yourself: 3.5 mm pitch screw terminals (8× 10-pole, 2× 8-pole), 5.5×2.1 mm barrel
        jack, 2× 6 mm push buttons, 1×3 pin header.</li>
  </ol>
</section>

<section id="bom">
  <h2>Parts assembled by JLCPCB</h2>
  {table(rel("jlcpcb", "bom-jlcpcb.csv"))}
  <h3>Parts you solder yourself</h3>
  {table(rel("jlcpcb", "hand-solder-parts.csv"))}
</section>

<footer>Generated from <code>hardware/</code> by <code>site/build_site.py</code>.</footer>
</main>
</body>
</html>
"""
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    print("site written to", SITE)


if __name__ == "__main__":
    main()
