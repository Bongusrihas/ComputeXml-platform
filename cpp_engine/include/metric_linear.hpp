#pragma once

#include <vector>

namespace computex {

struct LinearMetrics {
  double rmse = 0.0;
  double mae = 0.0;
  double mse = 0.0;
  double r2 = 0.0;
};

LinearMetrics calculateLinearMetrics(const std::vector<double>& actual,
                                     const std::vector<double>& predicted);

}  // namespace computex
