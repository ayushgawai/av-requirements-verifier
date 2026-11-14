#include "metrics.hpp"
#include <cassert>
#include <cmath>
int main() {
  assert(std::fabs(frame_ttc(10, 12, 2) - 1.0) < 1e-9);   // 10m gap, 10 m/s closing
  assert(std::isinf(frame_ttc(10, 2, 12)));                // opening, not closing
  assert(frame_ttc(-1, 12, 2) == 0.0);                     // overlap
  assert((percentile({1, 2, 3, 4}, .95) == 4));
  return 0;
}
