#include "metric_logistic.hpp"

#include <cmath>

namespace computex {

LogisticMetrics calculateLogisticMetrics(const std::vector<double>& actual,
                                         const std::vector<double>& probabilities,
                                         double threshold) {
  LogisticMetrics metrics;
  if (actual.empty() || actual.size() != probabilities.size()) {
    return metrics;
  }

  int truePositive = 0;
  int falsePositive = 0;
  int trueNegative = 0;
  int falseNegative = 0;

  for (std::size_t index = 0; index < actual.size(); ++index) {
    const int predicted = probabilities[index] >= threshold ? 1 : 0;
    const int expected = actual[index] >= 0.5 ? 1 : 0;

    if (predicted == 1 && expected == 1) truePositive += 1;
    if (predicted == 1 && expected == 0) falsePositive += 1;
    if (predicted == 0 && expected == 0) trueNegative += 1;
    if (predicted == 0 && expected == 1) falseNegative += 1;
  }

  const double sampleCount = static_cast<double>(actual.size());
  metrics.accuracy = sampleCount > 0.0 ? static_cast<double>(truePositive + trueNegative) / sampleCount : 0.0;

  const double predictedPositive = static_cast<double>(truePositive + falsePositive);
  const double actualPositive = static_cast<double>(truePositive + falseNegative);

  metrics.precision = predictedPositive > 0.0 ? static_cast<double>(truePositive) / predictedPositive : 0.0;
  metrics.recall = actualPositive > 0.0 ? static_cast<double>(truePositive) / actualPositive : 0.0;
  metrics.f1 = (metrics.precision + metrics.recall) > 0.0
                   ? (2.0 * metrics.precision * metrics.recall) / (metrics.precision + metrics.recall)
                   : 0.0;
  return metrics;
}

}  // namespace computex
