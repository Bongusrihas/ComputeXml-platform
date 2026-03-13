#include "cublas_models.hpp"

#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef COMPUTEX_HAS_CUBLAS
#include <cublas_v2.h>
#include <cuda_runtime.h>
#endif

namespace computex {

#ifdef COMPUTEX_HAS_CUBLAS
namespace {

void checkCuda(cudaError_t code, const char* msg) {
  if (code != cudaSuccess) {
    throw std::runtime_error(std::string(msg) + ": " + cudaGetErrorString(code));
  }
}

void checkCublas(cublasStatus_t code, const char* msg) {
  if (code != CUBLAS_STATUS_SUCCESS) {
    throw std::runtime_error(std::string(msg) + ": cuBLAS call failed");
  }
}

std::vector<double> flattenColMajor(const std::vector<std::vector<double>>& X) {
  if (X.empty()) return {};
  const std::size_t n = X.size();
  const std::size_t d = X[0].size();
  std::vector<double> out(n * d, 0.0);
  for (std::size_t r = 0; r < n; ++r) {
    if (X[r].size() != d) {
      throw std::runtime_error("Inconsistent feature width");
    }
    for (std::size_t c = 0; c < d; ++c) {
      out[c * n + r] = X[r][c];
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

TrainResult trainCuLike(const std::vector<std::vector<double>>& X, const std::vector<double>& y,
                        bool logistic) {
  TrainResult out;
  if (X.empty()) return out;

  const std::size_t n = X.size();
  const std::size_t d = X[0].size();
  if (y.size() != n) {
    throw std::runtime_error("X/y size mismatch");
  }

  const auto aHost = flattenColMajor(X);
  out.coefficients.assign(d, 0.0);

  const double lr = logistic ? 0.01 : 0.001;
  const int epochs = logistic ? 450 : 500;

  cublasHandle_t handle;
  checkCublas(cublasCreate(&handle), "cublasCreate");

  double *dA = nullptr, *dW = nullptr, *dPred = nullptr, *dErr = nullptr, *dGrad = nullptr;
  checkCuda(cudaMalloc(&dA, sizeof(double) * aHost.size()), "cudaMalloc A");
  checkCuda(cudaMalloc(&dW, sizeof(double) * d), "cudaMalloc W");
  checkCuda(cudaMalloc(&dPred, sizeof(double) * n), "cudaMalloc pred");
  checkCuda(cudaMalloc(&dErr, sizeof(double) * n), "cudaMalloc err");
  checkCuda(cudaMalloc(&dGrad, sizeof(double) * d), "cudaMalloc grad");

  checkCuda(cudaMemcpy(dA, aHost.data(), sizeof(double) * aHost.size(), cudaMemcpyHostToDevice),
            "copy A");
  checkCuda(cudaMemcpy(dW, out.coefficients.data(), sizeof(double) * d, cudaMemcpyHostToDevice),
            "copy W");

  std::vector<double> pred(n, 0.0), err(n, 0.0), grad(d, 0.0);
  const double one = 1.0;
  const double zero = 0.0;

  for (int epoch = 0; epoch < epochs; ++epoch) {
    checkCublas(cublasDgemv(handle, CUBLAS_OP_N, static_cast<int>(n), static_cast<int>(d), &one,
                            dA, static_cast<int>(n), dW, 1, &zero, dPred, 1),
                "cublasDgemv forward");

    checkCuda(cudaMemcpy(pred.data(), dPred, sizeof(double) * n, cudaMemcpyDeviceToHost),
              "copy pred to host");

    if (logistic) {
      pred = sigmoid(pred);
    }

    for (std::size_t i = 0; i < n; ++i) {
      err[i] = pred[i] - y[i];
    }

    checkCuda(cudaMemcpy(dErr, err.data(), sizeof(double) * n, cudaMemcpyHostToDevice),
              "copy err to device");

    checkCublas(cublasDgemv(handle, CUBLAS_OP_T, static_cast<int>(n), static_cast<int>(d), &one,
                            dA, static_cast<int>(n), dErr, 1, &zero, dGrad, 1),
                "cublasDgemv grad");

    checkCuda(cudaMemcpy(grad.data(), dGrad, sizeof(double) * d, cudaMemcpyDeviceToHost),
              "copy grad to host");

    for (std::size_t j = 0; j < d; ++j) {
      out.coefficients[j] -= lr * grad[j] / static_cast<double>(n);
    }

    checkCuda(cudaMemcpy(dW, out.coefficients.data(), sizeof(double) * d, cudaMemcpyHostToDevice),
              "copy W to device");
  }

  checkCublas(cublasDgemv(handle, CUBLAS_OP_N, static_cast<int>(n), static_cast<int>(d), &one, dA,
                          static_cast<int>(n), dW, 1, &zero, dPred, 1),
              "cublasDgemv final");
  checkCuda(cudaMemcpy(pred.data(), dPred, sizeof(double) * n, cudaMemcpyDeviceToHost),
            "copy final pred");

  if (logistic) {
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
  } else {
    double mse = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
      const double e = pred[i] - y[i];
      mse += e * e;
    }
    out.rmse = std::sqrt(mse / static_cast<double>(n));
    out.accuracy = 0.0;
  }

  cudaFree(dA);
  cudaFree(dW);
  cudaFree(dPred);
  cudaFree(dErr);
  cudaFree(dGrad);
  cublasDestroy(handle);

  return out;
}

}  // namespace
#endif

TrainResult trainCuBlas(const std::string& model, const std::vector<std::vector<double>>& X,
                        const std::vector<double>& y) {
#ifdef COMPUTEX_HAS_CUBLAS
  if (model == "logistic_regression") {
    return trainCuLike(X, y, true);
  }
  return trainCuLike(X, y, false);
#else
  throw std::runtime_error("cuBLAS not available in this build.");
#endif
}

}  // namespace computex
