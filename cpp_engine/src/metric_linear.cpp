#include "metric_linear.hpp"

#include <cmath>

namespace computex {

LinearMetrics calculateLinearMetrics(const std::vector<double>& actual,
                                     const std::vector<double>& predicted) {
  LinearMetrics metrics;
  if (actual.empty() || actual.size() != predicted.size()) {
    return metrics;
  }

  double squaredErrorSum = 0.0;
  double absoluteErrorSum = 0.0;
  double meanTarget = 0.0;
  for (double value : actual) {
    meanTarget += value;
  }
  meanTarget /= static_cast<double>(actual.size());

  double totalVariance = 0.0;
  for (std::size_t index = 0; index < actual.size(); ++index) {
    const double error = predicted[index] - actual[index];
    squaredErrorSum += error * error;
    absoluteErrorSum += std::fabs(error);

    const double centered = actual[index] - meanTarget;
    totalVariance += centered * centered;
  }

  metrics.mse = squaredErrorSum / static_cast<double>(actual.size());
  metrics.rmse = std::sqrt(metrics.mse);
  metrics.mae = absoluteErrorSum / static_cast<double>(actual.size());
  metrics.r2 = totalVariance > 0.0 ? 1.0 - (squaredErrorSum / totalVariance) : 1.0;
  return metrics;
}

}  // namespace computex
