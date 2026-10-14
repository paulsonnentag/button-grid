"""Minimal S-expression reader/writer for KiCad files.

Atoms are kept as Python str. Quoted strings are wrapped in `Q` so that they
are written back quoted; bare atoms (keywords, numbers) stay plain `str`.
"""
import re


class Q(str):
    """A quoted string atom."""


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def parse(text):
    stack, cur = [], []
    pos, n = 0, len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"bad sexpr at {pos}: {text[pos:pos+40]!r}")
        pos = m.end()
        lp, rp, qs, atom = m.groups()
        if lp:
            stack.append(cur)
            cur = []
        elif rp:
            done, cur = cur, stack.pop()
            cur.append(done)
        elif qs is not None:
            cur.append(Q(qs.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")))
        elif atom is not None:
            cur.append(atom)
    assert not stack, "unbalanced parens"
    return cur[0] if len(cur) == 1 else cur


def _atom(a):
    if isinstance(a, Q):
        return '"' + a.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(a, bool):
        return "yes" if a else "no"
    if isinstance(a, float):
        s = f"{a:.4f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(a)


def dump(node, indent=0):
    """Pretty-print in KiCad's tab-indented style."""
    if not isinstance(node, list):
        return _atom(node)
    simple = all(not isinstance(c, list) for c in node)
    if simple:
        return "(" + " ".join(_atom(c) for c in node) + ")"
    out = "(" + " ".join(_atom(c) for c in node if not isinstance(c, list))
    # keep leading atoms on the head line, children on their own lines
    head_done = False
    parts = [out]
    for c in node:
        if isinstance(c, list):
            head_done = True
            parts.append("\n" + "\t" * (indent + 1) + dump(c, indent + 1))
        elif head_done:
            parts.append(" " + _atom(c))
    return "".join(parts) + "\n" + "\t" * indent + ")"


def find(node, key):
    """First child list whose head is `key`."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]
