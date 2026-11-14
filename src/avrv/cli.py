import argparse, json, sys, time
from pathlib import Path
from .generate import generate
from .checker import verify, gate, diff

def _load(v, results="results"):
    p = Path(results) / f"results_{v}.json"
    if not p.exists(): verify(v, out=results)
    return json.loads(p.read_text())

def main(argv=None):
    p = argparse.ArgumentParser(prog="avrv", description=__doc__)
    s = p.add_subparsers(dest="cmd", required=True)
    g = s.add_parser("generate"); g.add_argument("--count", type=int, default=1000); g.add_argument("--seed", type=int, default=42); g.add_argument("--out", default="data")
    v = s.add_parser("verify"); v.add_argument("--version", choices="AB", required=True); v.add_argument("--data", default="data"); v.add_argument("--catalog", default="requirements/catalog.yaml"); v.add_argument("--out", default="results")
    d = s.add_parser("diff"); d.add_argument("a"); d.add_argument("b"); d.add_argument("--results", default="results")
    gt = s.add_parser("gate"); gt.add_argument("--version", choices="AB", default="B"); gt.add_argument("--results", default="results")
    b = s.add_parser("bench"); b.add_argument("--count", type=int, default=100)
    a = p.parse_args(argv)
    if a.cmd == "generate":
        m = generate(a.out, a.count, a.seed); print(f"generated {m['count']} logs in {a.out}/ (A+B), {len(m['regressions_B'])} regressions in B")
    elif a.cmd == "verify":
        t = time.time(); r = verify(a.version, a.data, a.catalog, a.out)
        npass = sum(x["status"] == "PASS" for x in r["results"])
        print(f"version {a.version}: {npass}/{len(r['results'])} requirements PASS (cpp={r['cpp']}, {time.time()-t:.1f}s) -> {a.out}/results_{a.version}.json, coverage_{a.version}.{{csv,html}}")
        for x in r["results"]:
            if x["status"] == "FAIL": print(f"  FAIL {x['id']} [{x['severity']}{' blocking' if x['blocking'] else ''}] value={x['value']} threshold={x['comparator']} {x['threshold']} worst={x['worst_scenario']}@{x['worst_t']}s")
    elif a.cmd == "diff":
        rows = diff(_load(a.a, a.results), _load(a.b, a.results))
        print(f"{'REQ':8} {'SEV':8} {'A':16} {'B':16} {'WORST':14} EFFECT")
        for x in rows: print(f"{x['id']:8} {x['severity']:8} {x['A']:16} {x['B']:16} {x['worst_scenario']}@{x['worst_t']}s  {'REGRESSED' if x['regressed'] else x['B']}")
        if not rows: print("no differences")
    elif a.cmd == "gate":
        bad = gate(_load(a.version, a.results))
        print(f"GATE {'FAIL' if bad else 'PASS'}: {len(bad)} blocking requirement(s) failing for version {a.version}")
        for x in bad: print(f"  {x['id']} [{x['severity']}] value={x['value']} worst={x['worst_scenario']}@{x['worst_t']}s")
        return 1 if bad else 0
    elif a.cmd == "bench":
        t = time.time(); generate("/tmp/avrv-bench", a.count); gen = time.time() - t
        t = time.time(); verify("A", "/tmp/avrv-bench", out="/tmp/avrv-bench-results"); ver = time.time() - t
        print(f"bench: generate {a.count} logs {gen:.2f}s | verify A ({a.count//2} scenarios x 44 reqs) {ver:.2f}s")
    return 0

if __name__ == "__main__":
    sys.exit(main())
