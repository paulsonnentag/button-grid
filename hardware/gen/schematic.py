"""Tiny KiCad 9 schematic writer.

Parts are connected purely with net labels placed on pin endpoints (no wires),
which keeps generation simple and the result fully editable in Eeschema.
"""
import uuid as _uuid

from kicadlib import load_symbol, pins
from sexpr import Q, dump, find, find_all

SCH_VERSION = "20250114"
PROJECT = "button-grid"

# nets drawn with power symbols (global); everything else gets a label
POWER_NETS = {"GND": "power:GND", "+3V3": "power:+3V3", "+12V": "power:+12V", "VBUS": "power:VBUS"}


_counter = [0]


def uid(seed=None):
    """Deterministic UUIDs so regenerating gives identical files (clean git diffs)."""
    if seed is None:
        _counter[0] += 1
        seed = f"auto/{_counter[0]}"
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, "button-grid/" + seed))


def font(size=1.27, justify=None, hide=False):
    eff = ["effects", ["font", ["size", size, size]]]
    if justify:
        eff.append(["justify", *justify.split()])
    if hide:
        eff.append(["hide", "yes"])
    return eff


def r(v):
    """Round to the 0.01mm grid so files stay tidy."""
    return round(v, 2)


# label angle (and justification) for a pin, keyed by the pin's angle in the library
_LABEL_ANGLE = {0: 180, 180: 0, 90: 270, 270: 90}
# rotation of power symbols so their graphic points away from the body
_GND_ROT = {0: 270, 180: 90, 90: 0, 270: 180}
_SUP_ROT = {0: 90, 180: 270, 90: 180, 270: 0}


def _rot_pin(px, py, pang, rot):
    """Rotate a library pin (y-up) by the symbol rotation (degrees, CCW)."""
    if rot == 0:
        return px, py, pang
    if rot == 90:
        return -py, px, (pang + 90) % 360
    if rot == 180:
        return -px, -py, (pang + 180) % 360
    if rot == 270:
        return py, -px, (pang + 270) % 360
    raise ValueError(rot)


class Sheet:
    def __init__(self, name, paper="A3", seed=None, title=None):
        self.name = name
        self.paper = paper
        self.uuid = uid(seed or name)
        self.title = title or name
        self.lib = {}           # lib_id -> symbol tree
        self.items = []         # sexpr items
        self.parts = []         # (ref_by_instance, part dict) for symbol instances
        self.pwr_count = 0
        self.instances = None   # list of (path, refmap) set by the project for sub-sheets
        self._seen_points = {}

    # ---- primitives -------------------------------------------------------
    def _use(self, lib_id):
        if lib_id not in self.lib:
            self.lib[lib_id] = load_symbol(lib_id)
        return self.lib[lib_id]

    def label(self, net, x, y, angle):
        key = (r(x), r(y))
        if self._seen_points.get(key) == net:
            return
        self._seen_points[key] = net
        just = "right bottom" if angle in (180, 270) else "left bottom"
        if net.startswith("^"):  # hierarchical label
            name = net[1:]
            self.items.append(["hierarchical_label", Q(name), ["shape", "bidirectional"],
                               ["at", r(x), r(y), angle], font(justify=just.split()[0]),
                               ["uuid", Q(uid())]])
        else:
            self.items.append(["label", Q(net), ["at", r(x), r(y), angle], font(justify=just),
                               ["uuid", Q(uid())]])

    def no_connect(self, x, y):
        self.items.append(["no_connect", ["at", r(x), r(y)], ["uuid", Q(uid())]])

    def text(self, s, x, y, size=2.0):
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", r(x), r(y), 0],
                           font(size, justify="left bottom"), ["uuid", Q(uid())]])

    def power(self, net, x, y, pin_angle):
        lib_id = POWER_NETS[net] if net in POWER_NETS else "power:PWR_FLAG"
        rot = (_GND_ROT if net == "GND" else _SUP_ROT)[pin_angle]
        self.pwr_count += 1
        self._symbol(lib_id, "#PWR", net if net in POWER_NETS else "PWR_FLAG", x, y, rot,
                     footprint="", lcsc=None, is_power=True)

    # ---- symbols ---------------------------------------------------------
    def _symbol(self, lib_id, ref, value, x, y, rot, footprint, lcsc, is_power=False,
                fields=None, dnp=False):
        sym = self._use(lib_id)
        su = uid()
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", r(x), r(y), rot], ["unit", 1],
                ["exclude_from_sim", "no"],
                ["in_bom", "no" if is_power or lib_id.startswith("Mechanical:") else "yes"],
                ["on_board", "no" if is_power else "yes"], ["dnp", "yes" if dnp else "no"],
                ["fields_autoplaced", "yes"], ["uuid", Q(su)]]
        props = {}
        for p in find_all(sym, "property"):
            props[str(p[1])] = p
        values = {"Reference": ref, "Value": value, "Footprint": footprint,
                  "Datasheet": str(props["Datasheet"][2]) if "Datasheet" in props else "",
                  "Description": str(props["Description"][2]) if "Description" in props else ""}
        if lcsc is not None:
            values["LCSC"] = lcsc
        for k, v in (fields or {}).items():
            values[k] = v
        for k, v in values.items():
            hide = k not in ("Reference", "Value") or is_power and k == "Reference"
            if k in props:
                at = find(props[k], "at")
                lx, ly = float(at[1]), float(at[2])
                lx, ly, _ = _rot_pin(lx, ly, 0, rot)
                pos = ["at", r(x + lx), r(y - ly), 0]
            else:
                pos = ["at", r(x), r(y), 0]
            node.append(["property", Q(k), Q(v), pos, font(hide=hide)])
        for num, *_ in pins(sym):
            node.append(["pin", Q(num), ["uuid", Q(uid())]])
        part = {"node": node, "ref": ref, "is_power": is_power}
        self.parts.append(part)
        self.items.append(node)
        return part

    def part(self, lib_id, ref, value, x, y, conns, footprint="", lcsc="", rot=0,
             fields=None, dnp=False):
        """Place a symbol and attach `conns` = {pin number or name: net|None}.

        `ref` may be a str or a callable(instance_index) for sub-sheets.
        Every pin must be mentioned (None means no-connect) so nothing is forgotten.
        """
        sym = self._use(lib_id)
        part = self._symbol(lib_id, ref, value, x, y, rot, footprint, lcsc,
                            fields=fields, dnp=dnp)
        plist = pins(sym)
        by_num = {p[0]: p for p in plist}
        handled = set()
        for key, net in conns.items():
            matches = [p for p in plist if p[0] == key] or [p for p in plist if p[1] == key]
            if not matches:
                raise KeyError(f"{lib_id} has no pin {key!r}")
            for num, _name, px, py, pang, _t in matches:
                handled.add(num)
                px, py, pang = _rot_pin(px, py, pang, rot)
                X, Y = x + px, y - py
                if net is None:
                    self.no_connect(X, Y)
                elif net in POWER_NETS:
                    self.power(net, X, Y, pang)
                else:
                    self.label(net, X, Y, _LABEL_ANGLE[pang])
        missing = set(by_num) - handled
        if missing:
            raise ValueError(f"{ref}: unconnected pins {sorted(missing)}")
        return part

    def flag(self, net, x, y):
        """PWR_FLAG on `net` (marks it as driven for ERC)."""
        self.power("PWR_FLAG", x, y, 270)
        if net in POWER_NETS:
            self.power(net, x, y, 90)
        else:
            self.label(net, x, y, 0)

    # ---- output ------------------------------------------------------------
    def to_sexpr(self, instances, sheets=(), is_root=False):
        """instances: list of (path, refsuffix_fn) — one per placement of this sheet."""
        tree = ["kicad_sch", ["version", SCH_VERSION], ["generator", Q("eeschema")],
                ["generator_version", Q("9.0")], ["uuid", Q(self.uuid)],
                ["paper", Q(self.paper)],
                ["title_block", ["title", Q(self.title)], ["company", Q("button-grid")],
                 ["comment", 1, Q("Generated by hardware/gen/build_schematic.py - editable in KiCad")]]]
        tree.append(["lib_symbols", *self.lib.values()])
        pwr_idx = 0
        for item in self.items:
            if item[0] == "symbol":
                part = next(p for p in self.parts if p["node"] is item)
                inst = ["instances", ["project", Q(PROJECT)]]
                if part["is_power"]:
                    pwr_idx += 1
                for k, (path, n) in enumerate(instances):
                    if part["is_power"]:
                        ref = f"#PWR{n * 1000 + pwr_idx:04d}"
                    else:
                        ref = part["ref"](n) if callable(part["ref"]) else part["ref"]
                    inst[1].append(["path", Q(path), ["reference", Q(ref)], ["unit", 1]])
                    if k == 0:
                        for prop in find_all(item, "property"):
                            if prop[1] == "Reference":
                                prop[2] = Q(ref)
                item.append(inst)
            tree.append(item)
        for s in sheets:
            tree.append(s)
        if is_root:
            tree.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        tree.append(["embedded_fonts", "no"])
        return tree

    def write(self, path, *args, **kw):
        with open(path, "w", encoding="utf-8") as f:
            f.write(dump(self.to_sexpr(*args, **kw)) + "\n")


def sheet_symbol(name, file, x, y, w, h, pins_spec, root_uuid, page, seed):
    """Hierarchical sheet box. pins_spec = [(pin_name, side, offset_mm)] side in L/R."""
    su = uid(seed)
    node = ["sheet", ["at", r(x), r(y)], ["size", r(w), r(h)],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"],
            ["fields_autoplaced", "yes"],
            ["stroke", ["width", 0.1524], ["type", "solid"]],
            ["fill", ["color", 0, 0, 0, 0.0]],
            ["uuid", Q(su)],
            ["property", Q("Sheetname"), Q(name), ["at", r(x), r(y - 0.7), 0],
             font(justify="left bottom")],
            ["property", Q("Sheetfile"), Q(file), ["at", r(x), r(y + h + 0.6), 0],
             font(justify="left top")]]
    pin_points = []
    for pname, side, off in pins_spec:
        if side == "L":
            px, py, ang, just = x, y + off, 180, "left"
        else:
            px, py, ang, just = x + w, y + off, 0, "right"
        node.append(["pin", Q(pname), "bidirectional", ["at", r(px), r(py), ang],
                     ["uuid", Q(uid())], font(justify=just)])
        pin_points.append((pname, px, py, ang))
    node.append(["instances", ["project", Q(PROJECT),
                               ["path", Q("/" + root_uuid), ["page", Q(str(page))]]]])
    return su, node, pin_points
