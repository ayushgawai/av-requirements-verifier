# av-requirements-verifier

Requirement traceability, scenario-log verification and release gating for an autonomous-driving software stack. A YAML catalog of executable requirements is checked against synthetic 10 Hz replay logs for two planner versions; version B carries 12 seeded regressions so the coverage matrix, diff and release gate have something real to catch.

## Design

```
 requirements/catalog.yaml        data/version_{A,B}/S????.csv      cpp/avrv_metrics
 44 requirements                   1,000 logs (500/version)          C++17 CLI binary
 id/metric/threshold/               ego+lead tracks, ped,            per-frame TTC +
 severity/blocking                  latency, stop-line @10Hz         latency percentiles
        |                                  |                                |
        v                                  v                                |
   +--------------+   generate   +----------------+   subprocess (or Py fallback)
   | avrv.catalog | -----------> | avrv.generate  |                |
   +--------------+              +----------------+                v
                                                        +------------------+
   results_{V}.json                                     |  avrv.checker    |
   coverage_{V}.csv/.html  <--------------------------- | scenario metrics |
   gate exit 0/1                                        | fleet aggregation|
   diff A B (ranked regressions)                        +------------------+
```

| Component | File | Notes |
|---|---|---|
| Requirements catalog | `requirements/catalog.yaml` (44 reqs) | `id, description, metric, threshold, comparator (gte/lte), agg (min/max/mean/p95), severity (critical/major/minor), blocking, unit` |
| Log generator | `src/avrv/generate.py` | Deterministic per-scenario seed; same base scenario for A and B; 12 regressions in B only, listed in `data/REGRESSIONS.md` / `manifest.json` |
| C++ metrics | `cpp/avrv_metrics.cpp`, `cpp/metrics.hpp` | Per-frame TTC = gap/closing-speed, latency percentiles; called via subprocess, automatic Python fallback if not built |
| Checker / gate / diff | `src/avrv/checker.py` | Per-scenario metrics → fleet aggregation → PASS/FAIL per requirement; gate fails (exit 1) on any blocking FAIL; diff ranks PASS→FAIL regressions by severity |
| CLI | `src/avrv/cli.py` | `avrv generate / verify / diff / gate / bench` |
| Tests | `tests/test_avrv.py`, `cpp/test_metrics.cpp` | pytest (4 tests) + CTest unit test for TTC/percentile |

Seeded regressions in B (ground truth, also written to `data/REGRESSIONS.md`): gap collapse, excessive closing speed, red-light run, hard braking, lateral-jerk spike, lane drift, pedestrian clearance, perception-latency spike, planning-latency spike (12 scenario instances: S0007, S0023, S0041, S0058, S0079, S0101, S0137, S0163, S0199, S0233, S0271, S0307).

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install pytest pyyaml
.venv/bin/pip install cmake   # or any system cmake >= 3.16, for the C++ checker
.venv/bin/cmake -S cpp -B cpp/build && .venv/bin/cmake --build cpp/build
export PYTHONPATH=src          # or: .venv/bin/pip install -e .

.venv/bin/python -m avrv generate                       # 1,000 logs -> data/
.venv/bin/python -m avrv verify --version A             # -> results/results_A.json, coverage_A.{csv,html}
.venv/bin/python -m avrv verify --version B
.venv/bin/python -m avrv diff A B                       # regressions ranked by severity, worst scenario@timestamp
.venv/bin/python -m avrv gate --version B               # exit 1 = do not release
.venv/bin/python -m avrv bench --count 200              # scaled-down bench (see below)
```

## Sanity runs (actual output, this machine)

Full pipeline at the default scale (1,000 logs, C++ checker built):

```
$ avrv generate --count 1000 --seed 42
generated 1000 logs in data/ (A+B), 12 regressions in B

$ avrv verify --version A
version A: 44/44 requirements PASS (cpp=True, 1.3s) -> results/results_A.json, coverage_A.{csv,html}

$ avrv verify --version B
version B: 25/44 requirements PASS (cpp=True, 1.0s) -> results/results_B.json, coverage_B.{csv,html}
  FAIL REQ-001 [critical blocking] value=-0.17 threshold=gte 5.0 worst=S0023@4.9s
  FAIL REQ-002 [critical blocking] value=0.0 threshold=gte 2.5 worst=S0023@4.9s
  FAIL REQ-004 [critical blocking] value=1.0 threshold=lte 0.0 worst=S0041@4.9s
  FAIL REQ-007 [critical blocking] value=0.913 threshold=lte 0.35 worst=S0101@4.9s
  FAIL REQ-008 [critical blocking] value=0.7 threshold=gte 1.5 worst=S0137@4.9s
  FAIL REQ-009 [critical blocking] value=190.0 threshold=lte 80.0 worst=S0163@4.9s
  FAIL REQ-010 [critical blocking] value=240.0 threshold=lte 100.0 worst=S0199@4.9s
  ... (19 failing requirements total)

$ avrv diff A B        # top rows; every row: severity, A/B status+value, worst scenario@timestamp
REQ-010  critical PASS (69.9)   FAIL (240.0)  S0199@4.9s  REGRESSED
REQ-009  critical PASS (54.87)  FAIL (190.0)  S0163@4.9s  REGRESSED
REQ-002  critical PASS (24.08)  FAIL (0.0)    S0023@4.9s  REGRESSED
REQ-001  critical PASS (12.04)  FAIL (-0.17)  S0023@4.9s  REGRESSED
REQ-008  critical PASS (3.001)  FAIL (0.7)    S0137@4.9s  REGRESSED

$ avrv gate --version A   ->  GATE PASS: 0 blocking requirement(s) failing for version A   (exit 0)
$ avrv gate --version B   ->  GATE FAIL: 10 blocking requirement(s) failing for version B  (exit 1)

$ avrv bench --count 200   # scaled down honestly: 200 logs, not the full 1,000
bench: generate 200 logs 0.03s | verify A (100 scenarios x 44 reqs) 0.20s
```

Tests:

```
$ .venv/bin/pytest -q
4 passed in 1.65s

$ .venv/bin/ctest --test-dir cpp/build --output-on-failure
1/1 Test #1: metrics ..........................   Passed    0.18 sec
100% tests passed out of 1
```

## Limitations (honest)

- **Synthetic data only.** Logs are 5 s, 50-frame, single-lead-vehicle scenarios from a hand-written generator — not real replay, sensor data, or a simulator. Metrics like TTC assume constant speeds within a frame and a fixed 4.5 m vehicle length.
- **One scenario shape.** No intersections beyond a single stop line, no multi-agent interaction, no weather/occlusion; the 12 regressions are deliberately large so the gate demonstrably trips.
- **Timestamps in diff/gate** are the worst-TTC timestamp within the worst scenario, not necessarily the exact frame where a non-TTC metric (e.g. lane offset) peaked.
- **Catalog loader** parses only the flat scalar YAML subset used by `requirements/catalog.yaml` (no nested maps/anchors) — it keeps the tool stdlib-only; swap in PyYAML if the catalog grows structure.
- **Coverage matrix is PASS/FAIL per cell** against each requirement's per-scenario threshold; fleet verdicts use the requirement's aggregation (min/max/mean/p95), so a requirement can fail fleet-wide while most cells pass.
- The C++ binary is optional: without `cpp/build/avrv_metrics`, the checker falls back to identical Python math (slower, reported as `cpp=False`).

## License

MIT — see `LICENSE`. Copyright (c) 2026 Ayush Gawai.
