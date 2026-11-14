"""Synthetic 10 Hz replay logs. 12 seeded regressions in version B (REGRESSIONS.md is
written next to the logs so the ground truth is auditable, not hidden)."""
import csv, json, math, random
from pathlib import Path

HEADER = ["t","ego_x","ego_y","ego_v","ego_a","lead_x","lead_v","ped_clearance_m",
          "lane_offset_m","lat_jerk_mps3","perception_latency_ms","planning_latency_ms",
          "stop_line_dist_m","red_light"]
FRAMES = 50  # 5 s at 10 Hz
# (scenario_index % 500, kind) injected only in version B
REGRESSIONS = [(7,"gap"),(23,"ttc"),(41,"stop"),(58,"brake"),(79,"jerk"),(101,"lane"),
               (137,"ped"),(163,"perception"),(199,"planning"),(233,"gap"),(271,"lane"),(307,"stop")]
KINDS = {"gap":"following gap collapses","ttc":"closing speed too high","stop":"runs red light",
         "brake":"repeated hard braking","jerk":"lateral jerk spike","lane":"lane offset drift",
         "ped":"pedestrian clearance too small","perception":"perception latency spike",
         "planning":"planning latency spike"}

def generate(out, count=1000, seed=42):
    out = Path(out); per = count // 2
    manifest = {"seed": seed, "count": count, "regressions_B": []}
    for version in ("A", "B"):
        d = out / f"version_{version}"; d.mkdir(parents=True, exist_ok=True)
        for idx in range(per):
            rng = random.Random(seed * 10000 + idx)  # same base scenario for A and B
            bad = dict(REGRESSIONS).get(idx) if version == "B" else None
            if bad: manifest["regressions_B"].append({"scenario": f"S{idx:04d}", "kind": bad, "effect": KINDS[bad]})
            _write(d / f"S{idx:04d}.csv", rng, bad)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "REGRESSIONS.md").write_text("# Seeded regressions (version B only)\n\n" +
        "\n".join(f"- {r['scenario']}: {r['kind']} — {r['effect']}" for r in manifest["regressions_B"]) + "\n")
    return manifest

def _write(path, rng, bad):
    speed, gap0 = rng.uniform(8, 13), rng.uniform(14, 22)
    lane0, ped0 = rng.uniform(-.05, .05), rng.uniform(3, 6)
    ego_x, red = 0.0, 1 if (bad == "stop" or rng.random() < .4) else 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(HEADER)
        for i in range(FRAMES):
            t = i / 10.0; gap = gap0 - 0.04 * i; accel, jerk, lane, ped = 0.3, 0.3, lane0, ped0
            perc, plan = rng.uniform(30, 55), rng.uniform(40, 70)
            stop_d = max(0.0, 25.0 - ego_x)  # stop line at x=25 m
            v = 0.0 if (red and stop_d < 2.0 and bad != "stop") else speed
            if bad == "gap" and i > 30: gap -= (i - 30) * 0.55
            if bad == "ttc" and i > 30: gap -= (i - 30) * 0.9
            if bad == "stop": pass  # handled above: never brakes for the red light
            if bad == "brake" and i % 8 == 0: accel = -4.8
            if bad == "jerk" and 25 < i < 35: jerk = 3.2
            if bad == "lane" and i > 20: lane += (i - 20) * 0.03
            if bad == "ped" and i > 25: ped = 0.7
            if bad == "perception" and i > 20: perc = 190.0
            if bad == "planning" and i > 20: plan = 240.0
            ego_x += v * 0.1
            w.writerow([f"{t:.1f}", f"{ego_x:.3f}", f"{lane:.3f}", f"{v:.3f}", f"{accel:.3f}",
                        f"{ego_x + gap + 4.5:.3f}", f"{v - 0.5:.3f}", f"{ped:.3f}", f"{lane:.3f}",
                        f"{jerk:.3f}", f"{perc:.2f}", f"{plan:.2f}", f"{stop_d:.3f}", red])
