#pragma once
#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>
// Per-frame TTC: gap / closing speed, +inf when not closing.
inline double frame_ttc(double gap_m, double ego_v, double lead_v) {
  double closing = ego_v - lead_v;
  if (closing <= 1e-9 || gap_m <= 0) return gap_m <= 0 ? 0.0 : std::numeric_limits<double>::infinity();
  return gap_m / closing;
}
inline double percentile(std::vector<double> v, double q) {
  if (v.empty()) return 0.0;
  std::sort(v.begin(), v.end());
  size_t i = std::min(v.size() - 1, (size_t)std::floor(q * v.size()));
  return v[i];
}
