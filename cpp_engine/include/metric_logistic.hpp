#pragma once

#include <vector>

namespace computex {

struct LogisticMetrics {
  double accuracy = 0.0;
  double precision = 0.0;
  double recall = 0.0;
  double f1 = 0.0;
};

LogisticMetrics calculateLogisticMetrics(const std::vector<double>& actual,
                                         const std::vector<double>& probabilities,
                                         double threshold);

}  // namespace computex
