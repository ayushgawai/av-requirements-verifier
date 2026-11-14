"""Checker: per-scenario metrics (TTC/latency via C++ binary when built, else Python
fallback), fleet aggregation, coverage matrix (CSV+HTML), release gate, diff."""
import csv, html, json, math, subprocess
from pathlib import Path
from .catalog import load_catalog, passes

SEV = {"critical": 0, "major": 1, "minor": 2}
CPP_BIN = Path(__file__).resolve().parents[2] / "cpp" / "build" / "avrv_metrics"

def _pct(v, q):
    s = sorted(v); return s[min(len(s) - 1, int(q * len(s)))] if s else 0.0

def scenario_metrics(path):
    rows = list(csv.DictReader(open(path)))
    f = lambda k: [float(r[k]) for r in rows]
    gaps = [float(r["lead_x"]) - float(r["ego_x"]) - 4.5 for r in rows]
    m, cpp = {}, CPP_BIN.exists()
    if cpp:  # C++ hot path for per-frame TTC + latency percentiles
        m.update(json.loads(subprocess.run([str(CPP_BIN), str(path)], capture_output=True, text=True, check=True).stdout))
    else:  # ponytail: Python fallback, swap is automatic once the binary is built
        ttcs = [g / (float(r["ego_v"]) - float(r["lead_v"])) if float(r["ego_v"]) > float(r["lead_v"]) else 999.0 for g, r in zip(gaps, rows)]
        perc, plan = f("perception_latency_ms"), f("planning_latency_ms")
        m.update(min_ttc_s=min(ttcs), min_gap_m=min(gaps), worst_ttc_t=float(rows[ttcs.index(min(ttcs))]["t"]),
                 p95_perception_latency_ms=_pct(perc, .95), p95_planning_latency_ms=_pct(plan, .95),
                 max_perception_latency_ms=max(perc), max_planning_latency_ms=max(plan),
                 mean_perception_latency_ms=sum(perc)/len(perc), mean_planning_latency_ms=sum(plan)/len(plan))
    ttcs = [g / (float(r["ego_v"]) - float(r["lead_v"])) if float(r["ego_v"]) > float(r["lead_v"]) else 999.0 for g, r in zip(gaps, rows)]
    red_cross = any(int(r["red_light"]) and float(r["stop_line_dist_m"]) == 0 and float(r["ego_v"]) > 1 for r in rows)
    stop_ds = [float(r["stop_line_dist_m"]) for r in rows if int(r["red_light"]) and float(r["ego_v"]) == 0]
    m.update(max_speed_mps=max(f("ego_v")), mean_speed_mps=sum(f("ego_v"))/len(rows),
             max_decel_mps2=max(-a for a in f("ego_a")), max_accel_mps2=max(f("ego_a")),
             hard_brake_rate=sum(a < -4 for a in f("ego_a"))/len(rows),
             max_lat_jerk_mps3=max(abs(x) for x in f("lat_jerk_mps3")), mean_abs_lat_jerk_mps3=sum(abs(x) for x in f("lat_jerk_mps3"))/len(rows),
             max_lane_offset_m=max(abs(x) for x in f("lane_offset_m")), mean_abs_lane_offset_m=sum(abs(x) for x in f("lane_offset_m"))/len(rows),
             min_ped_clearance_m=min(f("ped_clearance_m")), ped_near_rate=sum(x < 2 for x in f("ped_clearance_m"))/len(rows),
             mean_gap_m=sum(gaps)/len(gaps), low_ttc_rate=sum(t < 3 for t in ttcs)/len(rows),
             stop_violation=1.0 if red_cross else 0.0, min_stop_distance_m=min(stop_ds) if stop_ds else 2.0,
             worst_t=m.get("worst_ttc_t", 0.0), cpp=cpp)
    return m

def _agg(vals, agg):
    return {"min": min, "max": max, "mean": lambda v: sum(v)/len(v), "p95": lambda v: _pct(v, .95)}[agg](vals)

def verify(version, data="data", catalog="requirements/catalog.yaml", out="results"):
    reqs, logs = load_catalog(catalog), sorted((Path(data) / f"version_{version}").glob("*.csv"))
    assert logs, f"no logs for version {version} in {data} (run: avrv generate)"
    per = {p.stem: scenario_metrics(p) for p in logs}
    results, matrix = [], {}
    for r in reqs:
        vals = [per[s][r["metric"]] for s in per]
        value, ok = _agg(vals, r["agg"]), None
        ok = passes(value, r)
        worst_s = min(per, key=lambda s: per[s][r["metric"]]) if r["comparator"] == "gte" else max(per, key=lambda s: per[s][r["metric"]])
        results.append({**r, "value": round(value, 4), "status": "PASS" if ok else "FAIL",
                        "worst_scenario": worst_s, "worst_value": round(per[worst_s][r["metric"]], 4),
                        "worst_t": per[worst_s].get("worst_t", 0.0), "scenarios": len(vals)})
        matrix[r["id"]] = {s: ("PASS" if passes(per[s][r["metric"]], r) else "FAIL") for s in per}
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    report = {"version": version, "cpp": any(v["cpp"] for v in per.values()), "results": results}
    (out / f"results_{version}.json").write_text(json.dumps(report, indent=2))
    with open(out / f"coverage_{version}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["requirement"] + list(per))
        for rid, row in matrix.items(): w.writerow([rid] + [row[s] for s in per])
    cells = "".join(f"<tr><td>{rid}</td>" + "".join(f'<td class="{row[s]}">{row[s]}</td>' for s in per) + "</tr>" for rid, row in matrix.items())
    (out / f"coverage_{version}.html").write_text(
        f"<!doctype html><title>Coverage {version}</title><style>td.FAIL{{background:#fbb}}td.PASS{{background:#bfb}}table{{font-size:10px}}</style>"
        f"<h1>Requirement x scenario coverage - version {html.escape(version)}</h1><table><tr><th>req</th>{''.join(f'<th>{s}</th>' for s in per)}</tr>{cells}</table>")
    return report

def gate(report):
    bad = [r for r in report["results"] if r["blocking"] and r["status"] == "FAIL"]
    return bad

def diff(a, b):
    rb = {r["id"]: r for r in b["results"]}
    out = []
    for r in a["results"]:
        o = rb[r["id"]]
        if r["status"] != o["status"] or (o["status"] == "FAIL" and r["status"] == "FAIL"):
            out.append({"id": r["id"], "severity": r["severity"], "blocking": r["blocking"],
                        "A": f'{r["status"]} ({r["value"]})', "B": f'{o["status"]} ({o["value"]})',
                        "delta": round(o["value"] - r["value"], 4), "regressed": r["status"] == "PASS" and o["status"] == "FAIL",
                        "worst_scenario": o["worst_scenario"], "worst_t": o["worst_t"], "worst_value": o["worst_value"]})
    out.sort(key=lambda x: (not x["regressed"], SEV[x["severity"]], -abs(x["delta"])))
    return out
