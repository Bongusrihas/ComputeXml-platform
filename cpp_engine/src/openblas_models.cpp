#include "openblas_models.hpp"

#include <cblas.h>

#include <cmath>
#include <stdexcept>

namespace computex {

namespace {

std::vector<double> flattenRowMajorWithBias(const std::vector<std::vector<double>>& X) {
  if (X.empty()) return {};
  const std::size_t n = X.size();
  const std::size_t d = X[0].size();
  const std::size_t p = d + 1;

  std::vector<double> out(n * p, 0.0);
  for (std::size_t i = 0; i < n; ++i) {
    if (X[i].size() != d) {
      throw std::runtime_error("Inconsistent feature width");
    }
    out[i * p] = 1.0;  // bias term
    for (std::size_t j = 0; j < d; ++j) {
      out[i * p + (j + 1)] = X[i][j];
    }
  }
  return out;
}

std::vector<double> sigmoid(const std::vector<double>& z) {
  std::vector<double> out(z.size(), 0.0);
  for (std::size_t i = 0; i < z.size(); ++i) {
    out[i] = 1.0 / (1.0 + std::exp(-z[i]));
  }
  return out;
}

std::vector<double> solveLinearSystem(std::vector<double> a, std::vector<double> b, std::size_t n) {
  for (std::size_t i = 0; i < n; ++i) {
    std::size_t pivot = i;
    for (std::size_t r = i + 1; r < n; ++r) {
      if (std::fabs(a[r * n + i]) > std::fabs(a[pivot * n + i])) {
        pivot = r;
      }
    }

    if (std::fabs(a[pivot * n + i]) < 1e-12) {
      throw std::runtime_error("Singular matrix in normal equation solve");
    }

    if (pivot != i) {
      for (std::size_t c = 0; c < n; ++c) {
        std::swap(a[i * n + c], a[pivot * n + c]);
      }
      std::swap(b[i], b[pivot]);
    }

    const double diag = a[i * n + i];
    for (std::size_t c = i; c < n; ++c) {
      a[i * n + c] /= diag;
    }
    b[i] /= diag;

    for (std::size_t r = 0; r < n; ++r) {
      if (r == i) continue;
      const double factor = a[r * n + i];
      for (std::size_t c = i; c < n; ++c) {
        a[r * n + c] -= factor * a[i * n + c];
      }
      b[r] -= factor * b[i];
    }
  }

  return b;
}

TrainResult trainLinearRegressionClosedForm(const std::vector<std::vector<double>>& X,
                                            const std::vector<double>& y) {
  TrainResult out;
  if (X.empty()) return out;

  const std::size_t n = X.size();
  const std::size_t d = X[0].size();
  const std::size_t p = d + 1;

  if (y.size() != n) {
    throw std::runtime_error("X/y size mismatch");
  }

  const auto a = flattenRowMajorWithBias(X);
  std::vector<double> xtx(p * p, 0.0);
  std::vector<double> xty(p, 0.0);

  cblas_dgemm(CblasRowMajor, CblasTrans, CblasNoTrans, static_cast<int>(p), static_cast<int>(p),
              static_cast<int>(n), 1.0, a.data(), static_cast<int>(p), a.data(),
              static_cast<int>(p), 0.0, xtx.data(), static_cast<int>(p));

  cblas_dgemv(CblasRowMajor, CblasTrans, static_cast<int>(n), static_cast<int>(p), 1.0,
              a.data(), static_cast<int>(p), y.data(), 1, 0.0, xty.data(), 1);

  // tiny ridge for stability
  for (std::size_t i = 0; i < p; ++i) {
    xtx[i * p + i] += 1e-8;
  }

  out.coefficients = solveLinearSystem(xtx, xty, p);

  std::vector<double> pred(n, 0.0);
  cblas_dgemv(CblasRowMajor, CblasNoTrans, static_cast<int>(n), static_cast<int>(p), 1.0,
              a.data(), static_cast<int>(p), out.coefficients.data(), 1, 0.0, pred.data(), 1);

  double mse = 0.0;
  for (std::size_t i = 0; i < n; ++i) {
    const double e = pred[i] - y[i];
    mse += e * e;
  }
  out.rmse = std::sqrt(mse / static_cast<double>(n));
  out.accuracy = 0.0;
  return out;
}

TrainResult trainLogisticRegressionGD(const std::vector<std::vector<double>>& X,
                                      const std::vector<double>& y) {
  TrainResult out;
  if (X.empty()) return out;

  const std::size_t n = X.size();
  const std::size_t d = X[0].size();
  const std::size_t p = d + 1;

  if (y.size() != n) {
    throw std::runtime_error("X/y size mismatch");
  }

  const auto a = flattenRowMajorWithBias(X);
  out.coefficients.assign(p, 0.0);

  const double lr = 0.05;
  const int epochs = 1200;

  std::vector<double> pred(n, 0.0);
  std::vector<double> err(n, 0.0);
  std::vector<double> grad(p, 0.0);

  for (int epoch = 0; epoch < epochs; ++epoch) {
    cblas_dgemv(CblasRowMajor, CblasNoTrans, static_cast<int>(n), static_cast<int>(p), 1.0,
                a.data(), static_cast<int>(p), out.coefficients.data(), 1, 0.0, pred.data(), 1);

    pred = sigmoid(pred);

    for (std::size_t i = 0; i < n; ++i) {
      err[i] = pred[i] - y[i];
    }

    cblas_dgemv(CblasRowMajor, CblasTrans, static_cast<int>(n), static_cast<int>(p), 1.0,
                a.data(), static_cast<int>(p), err.data(), 1, 0.0, grad.data(), 1);

    for (std::size_t j = 0; j < p; ++j) {
      out.coefficients[j] -= lr * grad[j] / static_cast<double>(n);
    }
  }

  cblas_dgemv(CblasRowMajor, CblasNoTrans, static_cast<int>(n), static_cast<int>(p), 1.0,
              a.data(), static_cast<int>(p), out.coefficients.data(), 1, 0.0, pred.data(), 1);
  pred = sigmoid(pred);

  int correct = 0;
  for (std::size_t i = 0; i < n; ++i) {
    const int cls = pred[i] >= 0.5 ? 1 : 0;
    if (cls == static_cast<int>(y[i])) {
      correct += 1;
    }
  }

  out.accuracy = static_cast<double>(correct) / static_cast<double>(n);
  out.rmse = 0.0;
  return out;
}

}  // namespace

TrainResult trainOpenBlas(const std::string& model, const std::vector<std::vector<double>>& X,
                          const std::vector<double>& y) {
  if (model == "logistic_regression") {
    return trainLogisticRegressionGD(X, y);
  }
  return trainLinearRegressionClosedForm(X, y);
}

}  // namespace computex
