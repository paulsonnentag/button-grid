"""Load symbols from KiCad .kicad_sym libraries, flatten `extends`, list pins."""
import copy
import os

from sexpr import Q, find, find_all, parse

SYMBOL_DIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
_cache = {}


def _lib(name):
    if name not in _cache:
        with open(os.path.join(SYMBOL_DIR, name + ".kicad_sym"), encoding="utf-8") as f:
            tree = parse(f.read())
        _cache[name] = {s[1]: s for s in find_all(tree, "symbol")}
    return _cache[name]


def load_symbol(lib_id):
    """Return a flattened symbol tree named `lib_id` (e.g. "Device:R")."""
    lib, name = lib_id.split(":")
    syms = _lib(lib)
    sym = copy.deepcopy(syms[name])
    ext = find(sym, "extends")
    if ext:
        parent = load_symbol(f"{lib}:{ext[1]}")
        pname = parent[1].split(":")[1]
        merged = [c for c in parent if not (isinstance(c, list) and c[0] == "property")]
        # child's properties override the parent's
        child_props = {p[1]: p for p in find_all(sym, "property")}
        parent_props = [p for p in find_all(parent, "property")]
        props = [child_props.pop(p[1], p) for p in parent_props] + list(child_props.values())
        out = [merged[0], Q(name)]
        for c in merged[2:]:
            if isinstance(c, list) and c[0] == "symbol":
                c = copy.deepcopy(c)
                c[1] = Q(name + c[1][len(pname):])
            out.append(c)
        # insert properties right after the flags
        idx = next(i for i, c in enumerate(out) if isinstance(c, list) and c[0] == "symbol")
        sym = out[:idx] + props + out[idx:]
    sym = copy.deepcopy(sym)
    sym[1] = Q(lib_id)
    return sym


def pins(sym):
    """[(number, name, x, y, angle, etype)] for all pins of unit 1 / common units."""
    res = []
    for sub in find_all(sym, "symbol"):
        unit = sub[1].rsplit("_", 2)[-2]
        if unit not in ("0", "1"):
            continue
        for p in find_all(sub, "pin"):
            at = find(p, "at")
            res.append((str(find(p, "number")[1]), str(find(p, "name")[1]),
                        float(at[1]), float(at[2]), int(float(at[3])) if len(at) > 3 else 0,
                        str(p[1])))
    return res
