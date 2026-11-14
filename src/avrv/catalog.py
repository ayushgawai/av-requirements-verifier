"""Stdlib-only loader for the flat catalog YAML subset (list of scalar maps)."""
from pathlib import Path

def _val(s):
    s = s.strip()
    if s in ("true", "false"): return s == "true"
    try: return int(s)
    except ValueError:
        try: return float(s)
        except ValueError: return s

def load_catalog(path):
    reqs, cur = [], None
    for raw in Path(path).read_text().splitlines():
        line = raw.rstrip()
        if line.startswith("  - "):
            cur = {}; reqs.append(cur); line = "    " + line[4:]
        if cur is not None and ":" in line and not line.startswith("requirements"):
            k, _, v = line.strip().partition(":")
            if v.strip(): cur[k.strip()] = _val(v)
    assert reqs and all({"id","description","metric","threshold","severity"} <= r.keys() for r in reqs), "bad catalog"
    return reqs

def passes(value, req):
    return value >= req["threshold"] if req["comparator"] == "gte" else value <= req["threshold"]
