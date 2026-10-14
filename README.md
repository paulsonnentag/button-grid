# button-grid

An ESP32-S3 controller board for an 8×8 button matrix with 64 individually
switched 12 V LEDs. It's designed in KiCad 9 and made to be ordered from JLCPCB.

**Site with the design viewer, test results and JLCPCB downloads:** GitHub Pages
for this repo, built by `.github/workflows/pages.yml`.

## What's on the board

| Function | Implementation |
|---|---|
| MCU | ESP32-S3-WROOM-1-N8, native USB-C for flashing and serial |
| LEDs (64, not multiplexed) | 8× 74HC595 in one chain → 8× ULN2803A low-side drivers → screw terminals |
| Buttons (your diode matrix) | 8 rows + 8 columns directly on GPIOs, 100 Ω series resistors, 22 kΩ pull-ups |
| Power | 12 V wall adapter (5.5×2.1 mm, centre +, ≥ 2 A) → SS54 reverse-polarity diode → LED supply; TPS54202 buck converter → 3.3 V |
| Size | 208 × 110 mm, 2 layers |

### Wiring

- **LED terminals J11–J18** (10-pole, 3.5 mm pitch, along the top and bottom
  edges). Pins 1–8 take the cathode (−) wire of 8 LEDs. Pins 9–10 are +12 V for
  the anode (+) wires. Each LED must keep its own series resistor. Twist or
  daisy-chain the + wires of a bank so that at most 2 wires go into one screw.
  Bank 1 (J11) is LEDs 0–7, bank 2 is LEDs 8–15, and so on.
- **ROWS J3 / COLS J4** (8-pole, left edge): connect the 8 row wires and 8
  column wires of your matrix. Which way the diodes point is set in firmware,
  so either orientation works.
- **12 V** goes into the barrel jack. USB-C alone powers only the logic (enough
  to flash firmware). The LEDs need 12 V.

### ESP32 pin map (for the firmware)

| Signal | GPIO |
|---|---|
| ROW0…ROW7 | 4, 5, 6, 7, 15, 16, 17, 18 |
| COL0…COL7 | 8, 9, 10, 11, 12, 13, 14, 21 |
| 74HC595 SER (data in) / SRCLK / RCLK (latch) / OE (active low, pulled high) | 38 / 39 / 40 / 41 |
| Chain return (last 74HC595 QH′), used to self-test the chain | 42 |
| Status LED | 2 |
| USB D− / D+ | 19 / 20 |

To set LEDs, shift out 64 bits, with the bits for bank 8 first, then pulse
RCLK. A 1 turns the LED on. Drive OE low to enable the outputs. PWM on OE
dims all LEDs.

## Repository layout

```
hardware/
  button-grid.kicad_pro/.kicad_sch/.kicad_pcb, led_bank.kicad_sch   <- open these in KiCad 9
  gen/        generators: build_schematic.py, build_pcb.py (placement), finish_pcb.py (pours)
  scripts/    build.sh, route.sh, check.sh, export.sh, check_netlist.py, jlc_bom_cpl.py
site/         build_site.py -> static GitHub Pages site
```

The design was generated from Python. It uses one "LED bank" sheet that is
reused 8 times as a KiCad hierarchical sheet, so a change to that sheet applies
to all 64 channels. The output is an ordinary KiCad project:

- **Editing by hand in KiCad:** just do it, then run `hardware/scripts/check.sh`.
  Once you've edited by hand, don't re-run the generators, because they
  overwrite the files.
- **Editing through the generators:** change `hardware/gen/*.py`, then run
  `build.sh` → `route.sh` → `check.sh`.

Every script runs KiCad from the official `kicad/kicad:9.0` Docker image when
KiCad isn't installed locally. `route.sh` also needs Java 25 and the
[Freerouting](https://freerouting.app) jar.

## How the design is checked

`hardware/scripts/check.sh` runs on every push, and the results are shown on the site:

1. **ERC.** KiCad's electrical rules check on the schematic.
2. **Connectivity assertions** (`check_netlist.py`). These check the intended
   circuit pin by pin: all 64 LED channels, the 74HC595 chain order, the
   clock/latch/enable fan-out, every matrix line, USB-C CC resistors, the buck
   converter's feedback voltage, strapping pins, and LCSC numbers on every
   assembled part. The checker was tested by feeding it deliberately broken
   netlists (swapped LED wires, a broken chain), and it catches them.
3. **DRC with schematic parity.** Manufacturing limits that are safe for
   JLCPCB, a check that every net is routed, and a check that the PCB matches
   the schematic.

Recommended before ordering:

- **Breadboard test** of one channel: an ESP32 dev board, a 74HC595, a
  ULN2803 and one of your LEDs at 12 V.
- **First power-up:** connect 12 V with no LEDs attached and measure 3.3 V.
  Then flash a test firmware that walks one LED at a time, checks the chain
  through GPIO42, and prints matrix presses over USB.

## Ordering (see the site for the files)

Upload the gerber zip, then turn on PCB Assembly with the BOM and CPL files, 2
boards assembled. The screw terminals, barrel jack, buttons and header are
through-hole parts that you solder yourself (`hand-solder-parts.csv`). On
JLCPCB's placement preview, check that the chips and the USB-C connector are
rotated correctly.

**Part numbers:** the LCSC numbers were picked from JLCPCB's catalogue but
couldn't be checked against live stock while building. Check them when you
upload the BOM. Any part flagged as out of stock can be swapped for one with
the same footprint.
