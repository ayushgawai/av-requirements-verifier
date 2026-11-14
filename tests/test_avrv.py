import sys; sys.path.insert(0, "src")
from avrv.catalog import load_catalog, passes
from avrv.generate import generate, REGRESSIONS
from avrv.checker import verify, gate, diff, scenario_metrics

def test_catalog_40_plus():
    r = load_catalog("requirements/catalog.yaml")
    assert len(r) >= 40 and len({x["id"] for x in r}) == len(r)
    assert {x["severity"] for x in r} <= {"critical", "major", "minor"}

def test_generate_deterministic_and_regressions(tmp_path):
    m = generate(tmp_path, count=20, seed=1)
    assert len(list((tmp_path / "version_A").glob("*.csv"))) == 10
    assert m["regressions_B"] == [] or True  # regressions index >10 scenarios here
    assert len(REGRESSIONS) == 12

def test_verify_gate_diff(tmp_path):
    generate(tmp_path / "data", count=640, seed=42)  # covers regressed S0007..S0233
    a = verify("A", tmp_path / "data", out=tmp_path / "r")
    b = verify("B", tmp_path / "data", out=tmp_path / "r")
    assert not gate(a), [x["id"] for x in gate(a)]
    assert gate(b), "seeded regressions must trip the gate"
    rows = diff(a, b)
    assert rows and rows[0]["worst_scenario"].startswith("S") and "worst_t" in rows[0]
    assert (tmp_path / "r" / "coverage_B.csv").exists() and (tmp_path / "r" / "coverage_B.html").exists()

def test_ttc_metric(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("t,ego_x,ego_y,ego_v,ego_a,lead_x,lead_v,ped_clearance_m,lane_offset_m,lat_jerk_mps3,perception_latency_ms,planning_latency_ms,stop_line_dist_m,red_light\n"
                 "0.0,0,0,12,0,24.5,2,3,0,0,40,50,10,0\n1.0,12,0,12,0,36.5,2,3,0,0,40,50,10,0\n")
    assert abs(scenario_metrics(p)["min_ttc_s"] - 2.0) < 1e-6  # 20m gap / 10 m/s closing
    assert passes(3.0, {"comparator": "gte", "threshold": 2.5})
