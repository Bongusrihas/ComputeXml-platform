#include "linear_open.hpp"
#include "metric_linear.hpp"

#include <cblas.h>

#include <cmath>
#include <stdexcept>
#include <utility>
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

std::vector<double> solveSystem(std::vector<double> matrix, std::vector<double> values, std::size_t size) {
  for (std::size_t pivot = 0; pivot < size; ++pivot) {
    std::size_t bestRow = pivot;
    for (std::size_t row = pivot + 1; row < size; ++row) {
      if (std::fabs(matrix[row * size + pivot]) > std::fabs(matrix[bestRow * size + pivot])) {
        bestRow = row;
      }
    }

    if (std::fabs(matrix[bestRow * size + pivot]) < 1e-12) {
      throw std::runtime_error("Normal equation matrix is singular");
    }

    if (bestRow != pivot) {
      for (std::size_t column = 0; column < size; ++column) {
        std::swap(matrix[pivot * size + column], matrix[bestRow * size + column]);
      }
      std::swap(values[pivot], values[bestRow]);
    }

    const double diagonal = matrix[pivot * size + pivot];
    for (std::size_t column = pivot; column < size; ++column) {
      matrix[pivot * size + column] /= diagonal;
    }
    values[pivot] /= diagonal;

    for (std::size_t row = 0; row < size; ++row) {
      if (row == pivot) continue;
      const double factor = matrix[row * size + pivot];
      for (std::size_t column = pivot; column < size; ++column) {
        matrix[row * size + column] -= factor * matrix[pivot * size + column];
      }
      values[row] -= factor * values[pivot];
    }
  }

  return values;
}

}  // namespace

TrainResult trainLinearOpen(const std::vector<std::vector<double>>& X, const std::vector<double>& y) {
  TrainResult result;
  if (X.empty()) return result;
  if (X.size() != y.size()) {
    throw std::runtime_error("X and y row count do not match");
  }

  const std::size_t rowCount = X.size();
  const std::size_t featureCount = X[0].size();
  const std::size_t width = featureCount + 1;
  const auto designMatrix = flattenWithBias(X);

  std::vector<double> xtx(width * width, 0.0);
  std::vector<double> xty(width, 0.0);

  cblas_dgemm(CblasRowMajor, CblasTrans, CblasNoTrans, static_cast<int>(width),
              static_cast<int>(width), static_cast<int>(rowCount), 1.0, designMatrix.data(),
              static_cast<int>(width), designMatrix.data(), static_cast<int>(width), 0.0,
              xtx.data(), static_cast<int>(width));

  cblas_dgemv(CblasRowMajor, CblasTrans, static_cast<int>(rowCount), static_cast<int>(width),
              1.0, designMatrix.data(), static_cast<int>(width), y.data(), 1, 0.0, xty.data(), 1);

  for (std::size_t diagonal = 0; diagonal < width; ++diagonal) {
    xtx[diagonal * width + diagonal] += 1e-8;
  }

  result.coefficients = solveSystem(xtx, xty, width);
  result.variant = featureCount <= 1 ? "simple_linear" : "multilinear";

  std::vector<double> predictions(rowCount, 0.0);
  cblas_dgemv(CblasRowMajor, CblasNoTrans, static_cast<int>(rowCount), static_cast<int>(width),
              1.0, designMatrix.data(), static_cast<int>(width), result.coefficients.data(), 1,
              0.0, predictions.data(), 1);

  const auto metrics = calculateLinearMetrics(y, predictions);
  result.rmse = metrics.rmse;
  result.mae = metrics.mae;
  result.mse = metrics.mse;
  result.r2 = metrics.r2;
  result.accuracy = 0.0;
  return result;
}

}  // namespace computex
