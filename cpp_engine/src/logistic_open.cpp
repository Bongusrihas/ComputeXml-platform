#include "logistic_open.hpp"
#include "metric_logistic.hpp"

#include <cblas.h>

#include <cmath>
#include <stdexcept>
#include <vector>

namespace computex {

namespace {

std::vector<double> flattenWithBias(const std::vector<std::vector<double>>& X) {
  if (X.empty()) return {};

  const std::size_t rowCount = X.size();
  const std::size_t featureCount = X[0].size();
  const std::size_t width = featureCount + 1;
  std::vector<double> flattened(rowCount * width, 0.0);

  for (std::size_t row = 0; row < rowCount; ++row) {
    if (X[row].size() != featureCount) {
      throw std::runtime_error("Inconsistent feature width");
    }

    flattened[row * width] = 1.0;
    for (std::size_t column = 0; column < featureCount; ++column) {
      flattened[row * width + column + 1] = X[row][column];
    }
  }

  return flattened;
}

double sigmoid(double value) { return 1.0 / (1.0 + std::exp(-value)); }

}  // namespace

TrainResult trainLogisticOpen(const std::vector<std::vector<double>>& X,
                              const std::vector<double>& y) {
  TrainResult result;
  if (X.empty()) return result;
  if (X.size() != y.size()) {
    throw std::runtime_error("X and y row count do not match");
  }

  const std::size_t rowCount = X.size();
  const std::size_t featureCount = X[0].size();
  const std::size_t width = featureCount + 1;
  const auto designMatrix = flattenWithBias(X);

  result.coefficients.assign(width, 0.0);
  result.variant = "binary_logistic";

  const double learningRate = 0.05;
  const int epochCount = 1500;

  std::vector<double> logits(rowCount, 0.0);
  std::vector<double> errors(rowCount, 0.0);
  std::vector<double> gradient(width, 0.0);

  for (int epoch = 0; epoch < epochCount; ++epoch) {
    cblas_dgemv(CblasRowMajor, CblasNoTrans, static_cast<int>(rowCount),
                static_cast<int>(width), 1.0, designMatrix.data(), static_cast<int>(width),
                result.coefficients.data(), 1, 0.0, logits.data(), 1);

    for (std::size_t row = 0; row < rowCount; ++row) {
      const double probability = sigmoid(logits[row]);
      errors[row] = probability - y[row];
    }

    cblas_dgemv(CblasRowMajor, CblasTrans, static_cast<int>(rowCount), static_cast<int>(width),
                1.0, designMatrix.data(), static_cast<int>(width), errors.data(), 1, 0.0,
                gradient.data(), 1);

    for (std::size_t column = 0; column < width; ++column) {
      result.coefficients[column] -= learningRate * gradient[column] /
                                     static_cast<double>(rowCount);
    }
  }

  cblas_dgemv(CblasRowMajor, CblasNoTrans, static_cast<int>(rowCount), static_cast<int>(width),
              1.0, designMatrix.data(), static_cast<int>(width), result.coefficients.data(), 1,
              0.0, logits.data(), 1);

  std::vector<double> probabilities(rowCount, 0.0);
  for (std::size_t row = 0; row < rowCount; ++row) {
    probabilities[row] = sigmoid(logits[row]);
  }

  const auto metrics = calculateLogisticMetrics(y, probabilities, 0.5);
  result.rmse = 0.0;
  result.accuracy = metrics.accuracy;
  result.precision = metrics.precision;
  result.recall = metrics.recall;
  result.f1 = metrics.f1;
  return result;
}

}  // namespace computex
