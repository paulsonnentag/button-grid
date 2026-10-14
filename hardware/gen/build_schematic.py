#!/usr/bin/env python3
"""Generate the button-grid KiCad schematic.

  root sheet  : power, ESP32-S3, USB, button-matrix interface, 8x "LED bank"
  led_bank    : 74HC595 -> ULN2803A -> 10-pole screw terminal (8 LEDs + 2x +12V)

Run inside the KiCad 9 docker image (needs /usr/share/kicad/symbols), see
hardware/scripts/build.sh. The output is a normal KiCad project; once you start
editing it by hand in KiCad, treat the .kicad_sch files as the source of truth
(re-running this script overwrites them).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from schematic import Sheet, sheet_symbol, uid  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..")

# ---------------------------------------------------------------------------
# parts catalogue: footprint + LCSC number (JLCPCB assembly)
# "hand" parts are through-hole and soldered by you (not assembled by JLCPCB)
# ---------------------------------------------------------------------------
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_TB = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-{n}-3.5-H_1x{n:02d}_P3.50mm_Horizontal"

LCSC_R = {"100": "C22775", "1k": "C21190", "5.1k": "C23186", "10k": "C25804",
          "22k": "C31850", "100k": "C25803"}
LCSC_C = {"100nF": ("C14663", FP_C), "1uF": ("C15849", FP_C),
          "10uF 25V": ("C15850", FP_C0805), "22uF": ("C45783", FP_C0805)}

HAND = {"Assembly": "hand-solder"}

N_BANKS = 8
ROW_GPIO = ["IO4", "IO5", "IO6", "IO7", "IO15", "IO16", "IO17", "IO18"]
COL_GPIO = ["IO8", "IO9", "IO10", "IO11", "IO12", "IO13", "IO14", "IO21"]


def R(sh, ref, val, x, y, top, bot):
    return sh.part("Device:R", ref, val, x, y, {"1": top, "2": bot},
                   footprint=FP_R, lcsc=LCSC_R[val])


def C(sh, ref, val, x, y, top, bot):
    lcsc, fp = LCSC_C[val]
    return sh.part("Device:C", ref, val, x, y, {"1": top, "2": bot}, footprint=fp, lcsc=lcsc)


# ---------------------------------------------------------------------------
# LED bank sub-sheet (instantiated 8x)
# ---------------------------------------------------------------------------
def build_bank():
    sh = Sheet("led_bank", paper="A4", seed="led_bank", title="LED bank (8 channels)")
    sh.text("One LED bank: 8 LED outputs, low-side switched.\n"
            "LED wiring per channel: +12V terminal -> LED (+ its resistor) -> LEDn terminal.\n"
            "74HC595 output HIGH = LED on.", 20, 25)
    q = [f"Q{i}" for i in range(8)]
    sr = {"SER": "^SER_IN", "SRCLK": "^SRCLK", "~{SRCLR}": "+3V3", "RCLK": "^RCLK",
          "~{OE}": "^OE_N", "VCC": "+3V3", "GND": "GND", "QH'": "^SER_OUT"}
    sr.update({f"Q{c}": q[i] for i, c in enumerate("ABCDEFGH")})
    sh.part("74xx:74HC595", lambda n: f"U{10 + n}", "74HC595", 80.01, 100.33, sr,
            footprint="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", lcsc="C5947")
    drv = {"GND": "GND", "COM": "+12V"}
    drv.update({f"I{i + 1}": q[i] for i in range(8)})
    drv.update({f"O{i + 1}": f"LED{i + 1}" for i in range(8)})
    sh.part("Transistor_Array:ULN2803A", lambda n: f"U{20 + n}", "ULN2803A", 140.97, 100.33, drv,
            footprint="Package_SO:SOIC-18W_7.5x11.6mm_P1.27mm", lcsc="C9683")
    tb = {str(i + 1): f"LED{i + 1}" for i in range(8)}
    tb.update({"9": "+12V", "10": "+12V"})
    sh.part("Connector:Screw_Terminal_01x10", lambda n: f"J{10 + n}", "LEDs", 203.2, 97.79, tb,
            footprint=FP_TB.format(n=10), lcsc="", rot=0, fields=HAND)
    sh.part("Device:C", lambda n: f"C{10 + n}", "100nF", 50.8, 66.04, {"1": "+3V3", "2": "GND"},
            footprint=FP_C, lcsc="C14663")
    sh.part("Device:C", lambda n: f"C{20 + n}", "100nF", 170.18, 66.04, {"1": "+12V", "2": "GND"},
            footprint=FP_C, lcsc="C14663")
    return sh


# ---------------------------------------------------------------------------
# root sheet
# ---------------------------------------------------------------------------
def build_root(bank):
    sh = Sheet("button-grid", paper="A2", seed="root", title="8x8 button grid controller")

    # --- 12V input, reverse protection, buck 3.3V --------------------------
    sh.text("12V input (wall adapter, 5.5x2.1mm centre +)", 25.4, 30.48)
    sh.part("Connector:Barrel_Jack_Switch", "J1", "12V DC", 30.48, 50.8,
            {"1": "VIN_RAW", "2": "GND", "3": None},
            footprint="Connector_BarrelJack:BarrelJack_Horizontal", lcsc="C381116", fields=HAND)
    sh.part("Device:D_Schottky", "D1", "SS54", 60.96, 48.26, {"A": "VIN_RAW", "K": "+12V"},
            footprint="Diode_SMD:D_SMA", lcsc="C22452")
    C(sh, "C1", "10uF 25V", 76.2, 53.34, "+12V", "GND")
    C(sh, "C2", "10uF 25V", 86.36, 53.34, "+12V", "GND")
    sh.flag("+12V", 96.52, 45.72)
    sh.flag("GND", 96.52, 60.96)

    sh.text("Logic supply: 12V or USB VBUS (diode-OR) -> TPS54202 buck -> 3.3V", 25.4, 78.74)
    sh.part("Device:D_Schottky", "D2", "SS34", 40.64, 93.98, {"A": "+12V", "K": "VBUCK"},
            footprint="Diode_SMD:D_SMA", lcsc="C8678")
    sh.part("Device:D_Schottky", "D3", "SS34", 40.64, 104.14, {"A": "VBUS", "K": "VBUCK"},
            footprint="Diode_SMD:D_SMA", lcsc="C8678")
    sh.flag("VBUCK", 55.88, 88.9)
    C(sh, "C3", "10uF 25V", 63.5, 101.6, "VBUCK", "GND")
    C(sh, "C4", "100nF", 73.66, 101.6, "VBUCK", "GND")
    sh.part("Regulator_Switching:TPS54202DDC", "U2", "TPS54202H", 101.6, 101.6,
            {"VIN": "VBUCK", "EN": None, "GND": "GND", "BOOT": "BST", "SW": "SW", "FB": "FB"},
            footprint="Package_TO_SOT_SMD:TSOT-23-6", lcsc="C527684")
    C(sh, "C5", "100nF", 124.46, 93.98, "BST", "SW")
    sh.part("Device:L", "L1", "10uH", 137.16, 101.6, {"1": "SW", "2": "+3V3"},
            footprint="Inductor_SMD:L_Sunlord_SWPA4030S", lcsc="C38117")
    R(sh, "R1", "100k", 152.4, 101.6, "+3V3", "FB")
    R(sh, "R2", "22k", 152.4, 116.84, "FB", "GND")
    C(sh, "C6", "22uF", 165.1, 104.14, "+3V3", "GND")
    C(sh, "C7", "22uF", 175.26, 104.14, "+3V3", "GND")
    sh.flag("+3V3", 185.42, 96.52)
    sh.text("Vout = 0.596V * (1 + R1/R2) = 3.31V", 101.6, 127.0, size=1.5)

    # --- USB-C (programming / serial console) --------------------------------
    sh.text("USB-C: firmware upload + serial console (native USB of the ESP32-S3)", 220.98, 30.48)
    sh.part("Connector:USB_C_Receptacle_USB2.0_16P", "J2", "USB-C", 236.22, 66.04,
            {"VBUS": "VBUS", "GND": "GND", "SHIELD": "GND", "CC1": "CC1", "CC2": "CC2",
             "D-": "USB_DN", "D+": "USB_DP", "SBU1": None, "SBU2": None},
            footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948")
    R(sh, "R7", "5.1k", 269.24, 60.96, "CC1", "GND")
    R(sh, "R8", "5.1k", 279.4, 60.96, "CC2", "GND")
    sh.flag("VBUS", 289.56, 45.72)

    # --- ESP32-S3 ---------------------------------------------------------------
    sh.text("ESP32-S3-WROOM-1-N8", 220.98, 162.56)
    esp = {"3V3": "+3V3", "GND": "GND", "EN": "EN", "IO0": "ESP_BOOT",
           "USB_D-": "USB_DN", "USB_D+": "USB_DP", "TXD0": "TXD0", "RXD0": "RXD0",
           "IO38": "SER0", "IO39": "SRCLK", "IO40": "RCLK", "IO41": "OE_N",
           "IO42": f"SER{N_BANKS}", "IO2": "STATUS"}
    esp.update({g: f"ROW{i}" for i, g in enumerate(ROW_GPIO)})
    esp.update({g: f"COL{i}" for i, g in enumerate(COL_GPIO)})
    for g in ["IO1", "IO3", "IO35", "IO36", "IO37", "IO45", "IO46", "IO47", "IO48"]:
        esp[g] = None
    sh.part("RF_Module:ESP32-S3-WROOM-1", "U1", "ESP32-S3-WROOM-1-N8", 254.0, 213.36, esp,
            footprint="RF_Module:ESP32-S3-WROOM-1", lcsc="C2913198")
    C(sh, "C9", "10uF 25V", 279.4, 172.72, "+3V3", "GND")
    C(sh, "C10", "100nF", 289.56, 172.72, "+3V3", "GND")
    # reset / boot
    R(sh, "R3", "10k", 205.74, 175.26, "+3V3", "EN")
    C(sh, "C8", "1uF", 195.58, 190.5, "EN", "GND")
    sh.part("Switch:SW_Push", "SW1", "RESET", 205.74, 198.12, {"1": "EN", "2": "GND"},
            footprint="Button_Switch_THT:SW_PUSH_6mm", lcsc="", fields=HAND)
    R(sh, "R4", "10k", 180.34, 175.26, "+3V3", "ESP_BOOT")
    sh.part("Switch:SW_Push", "SW2", "BOOT", 180.34, 198.12, {"1": "ESP_BOOT", "2": "GND"},
            footprint="Button_Switch_THT:SW_PUSH_6mm", lcsc="", fields=HAND)
    # LEDs off while the ESP32 boots: OE_N pulled high
    R(sh, "R5", "10k", 297.18, 236.22, "+3V3", "OE_N")
    # status LED
    R(sh, "R6", "1k", 195.58, 233.68, "STATUS", "STATUS_A")
    sh.part("Device:LED", "D4", "status", 195.58, 248.92, {"A": "STATUS_A", "K": "GND"},
            footprint="LED_SMD:LED_0603_1608Metric", lcsc="C2286", rot=90)
    # debug UART header
    sh.part("Connector_Generic:Conn_01x03", "J5", "UART", 312.42, 190.5,
            {"1": "GND", "2": "TXD0", "3": "RXD0"},
            footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", lcsc="",
            fields=HAND)

    # --- button matrix -----------------------------------------------------------
    sh.text("Button matrix (8 rows x 8 columns, diodes on the buttons).\n"
            "100R series resistors protect the GPIOs, 22k pull-ups keep long wires defined.\n"
            "Rows/columns are plain GPIOs, so diode direction is set in firmware.", 25.4, 160.02)
    for i in range(8):
        x = 30.48 + i * 12.7
        R(sh, f"R{10 + i}", "100", x, 185.42, f"ROW{i}", f"ROW{i}_T")
        R(sh, f"R{30 + i}", "22k", x, 205.74, "+3V3", f"ROW{i}_T")
        R(sh, f"R{20 + i}", "100", x, 238.76, f"COL{i}", f"COL{i}_T")
        R(sh, f"R{40 + i}", "22k", x, 259.08, "+3V3", f"COL{i}_T")
    sh.part("Connector:Screw_Terminal_01x08", "J3", "ROWS", 144.78, 193.04,
            {str(i + 1): f"ROW{i}_T" for i in range(8)}, footprint=FP_TB.format(n=8), lcsc="",
            fields=HAND)
    sh.part("Connector:Screw_Terminal_01x08", "J4", "COLS", 144.78, 246.38,
            {str(i + 1): f"COL{i}_T" for i in range(8)}, footprint=FP_TB.format(n=8), lcsc="",
            fields=HAND)

    # --- mounting holes -------------------------------------------------------
    for i in range(4):
        sh.part("Mechanical:MountingHole", f"H{i + 1}", "M3", 30.48 + i * 12.7, 304.8, {},
                footprint="MountingHole:MountingHole_3.2mm_M3", lcsc="", fields={"Assembly": "none"})

    # --- LED banks ---------------------------------------------------------------
    sh.text("LED banks: 74HC595 chain, bank 1 is first in the chain (LEDs 0-7)", 365.76, 30.48)
    sheets, bank_paths = [], []
    for k in range(N_BANKS):
        x, y = 381.0, 40.64 + k * 33.02
        spec = [("SER_IN", "L", 5.08), ("SRCLK", "L", 10.16), ("RCLK", "L", 15.24),
                ("OE_N", "L", 20.32), ("SER_OUT", "R", 5.08)]
        su, node, pts = sheet_symbol(f"Bank {k + 1}", "led_bank.kicad_sch", x, y, 30.48, 25.4,
                                     spec, sh.uuid, page=k + 2, seed=f"bank{k}")
        sheets.append(node)
        bank_paths.append(f"/{sh.uuid}/{su}")
        nets = {"SER_IN": f"SER{k}", "SRCLK": "SRCLK", "RCLK": "RCLK", "OE_N": "OE_N",
                "SER_OUT": f"SER{k + 1}"}
        for pname, px, py, ang in pts:
            sh.label(nets[pname], px, py, ang)
    return sh, sheets, bank_paths


def write_project(out):
    bank = build_bank()
    root, sheets, bank_paths = build_root(bank)
    root.write(os.path.join(out, "button-grid.kicad_sch"), [("/" + root.uuid, 0)],
               sheets=sheets, is_root=True)
    bank.write(os.path.join(out, "led_bank.kicad_sch"),
               [(p, k + 1) for k, p in enumerate(bank_paths)])
    print("wrote schematic to", out)


if __name__ == "__main__":
    write_project(OUT)
