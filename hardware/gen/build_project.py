#!/usr/bin/env python3
"""Write button-grid.kicad_pro: JLCPCB-safe design rules and net classes."""
import json
import os
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..")


def netclass(name, track, clearance=0.2, via=0.6, drill=0.3, prio=0):
    return {"name": name, "clearance": clearance, "track_width": track,
            "via_diameter": via, "via_drill": drill,
            "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
            "wire_width": 6, "bus_width": 12, "line_style": 0,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
            "priority": prio}


project = {
    "meta": {"filename": "button-grid.kicad_pro", "version": 3},
    "board": {
        "design_settings": {
            # JLCPCB 2-layer standard capabilities are 0.127mm track/space,
            # 0.3mm drill; we stay comfortably above them.
            "rules": {
                "min_clearance": 0.15, "min_track_width": 0.15,
                "min_via_annular_width": 0.13, "min_via_diameter": 0.5,
                "min_through_hole_diameter": 0.3, "min_hole_clearance": 0.25,
                "min_hole_to_hole": 0.5, "min_copper_edge_clearance": 0.3,
                "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.12,
                "solder_mask_to_copper_clearance": 0.0, "min_connection": 0.0,
                "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
                "max_error": 0.005, "allow_blind_buried_vias": False, "allow_microvias": False,
                "use_height_for_length_calcs": True,
            },
            "track_widths": [0.0, 0.25, 0.5, 0.8, 1.2],
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3},
                               {"diameter": 0.8, "drill": 0.4}],
            "rule_severities": {
                # hand-soldered THT parts overlap a bit with silk; not a fab issue
                "silk_overlap": "ignore", "silk_over_copper": "warning",
                "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
            },
        },
    },
    "net_settings": {
        "meta": {"version": 4},
        "classes": [
            netclass("Default", 0.25),
            netclass("Power", 0.8, clearance=0.2, via=0.8, drill=0.4, prio=1),
            netclass("Supply3V3", 0.5, prio=2),
        ],
        "netclass_patterns": [
            {"netclass": "Power", "pattern": "+12V"},
            {"netclass": "Power", "pattern": "GND"},
            {"netclass": "Power", "pattern": "*VIN_RAW"},
            {"netclass": "Power", "pattern": "*VBUCK"},
            {"netclass": "Power", "pattern": "VBUS"},
            {"netclass": "Power", "pattern": "*/SW"},
            {"netclass": "Supply3V3", "pattern": "+3V3"},
        ],
    },
    "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
    "sheets": [],
    "text_variables": {},
}

with open(os.path.join(OUT, "button-grid.kicad_pro"), "w") as f:
    json.dump(project, f, indent=2)
print("wrote project file")
