// avrv_metrics <log.csv> -> one JSON line: per-frame TTC + latency stats (C++ hot path).
// CSV columns (see avrv/generate.py): t,ego_x,ego_y,ego_v,ego_a,lead_x,lead_v,ped_clearance_m,
//   lane_offset_m,lat_jerk_mps3,perception_latency_ms,planning_latency_ms,stop_line_dist_m,red_light
#include "metrics.hpp"
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
int main(int argc, char** argv) {
  if (argc < 2) { std::fprintf(stderr, "usage: avrv_metrics <log.csv>\n"); return 2; }
  std::ifstream in(argv[1]); if (!in) { std::fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
  std::string line; std::getline(in, line); // header
  double min_ttc = 1e18, min_gap = 1e18, worst_t = 0, sum_p = 0, sum_q = 0; std::vector<double> perc, plan;
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    std::stringstream ss(line); std::string cell; double v[14] = {0};
    for (int i = 0; i < 14 && std::getline(ss, cell, ','); i++) v[i] = std::stod(cell);
    double gap = v[5] - v[1] - 4.5; // lead_x - ego_x - vehicle length
    double ttc = frame_ttc(gap, v[3], v[6]);
    if (ttc < min_ttc) { min_ttc = ttc; worst_t = v[0]; }
    min_gap = std::min(min_gap, gap); perc.push_back(v[10]); plan.push_back(v[11]); sum_p += v[10]; sum_q += v[11];
  }
  if (min_ttc > 1e17) min_ttc = 999.0; if (min_gap > 1e17) min_gap = 999.0;
  std::printf("{\"min_ttc_s\":%.4f,\"min_gap_m\":%.4f,\"worst_ttc_t\":%.1f,"
              "\"p95_perception_latency_ms\":%.3f,\"p95_planning_latency_ms\":%.3f,"
              "\"max_perception_latency_ms\":%.3f,\"max_planning_latency_ms\":%.3f,"
              "\"mean_perception_latency_ms\":%.3f,\"mean_planning_latency_ms\":%.3f}\n",
    min_ttc, min_gap, worst_t, percentile(perc, .95), percentile(plan, .95),
    perc.empty()?0:*std::max_element(perc.begin(), perc.end()),
    plan.empty()?0:*std::max_element(plan.begin(), plan.end()),
    perc.empty()?0:sum_p/perc.size(), plan.empty()?0:sum_q/plan.size());
  return 0;
}
