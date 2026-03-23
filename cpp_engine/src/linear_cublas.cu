#include "linear_cublas.hpp"
#include "metric_linear.hpp"

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

void checkCuda(cudaError_t code, const char* message) {
  if (code != cudaSuccess) {
    throw std::runtime_error(std::string(message) + ": " + cudaGetErrorString(code));
  }
}

void checkCuBlas(cublasStatus_t code, const char* message) {
  if (code != CUBLAS_STATUS_SUCCESS) {
    throw std::runtime_error(std::string(message) + ": cuBLAS call failed");
  }
}

std::vector<double> flattenColumnMajorWithBias(const std::vector<std::vector<double>>& X) {
  if (X.empty()) return {};

  const std::size_t rowCount = X.size();
  const std::size_t featureCount = X[0].size();
  const std::size_t width = featureCount + 1;
  std::vector<double> flattened(rowCount * width, 0.0);

  for (std::size_t row = 0; row < rowCount; ++row) {
    flattened[row] = 1.0;
    for (std::size_t column = 0; column < featureCount; ++column) {
      flattened[(column + 1) * rowCount + row] = X[row][column];
    }
  }

  return flattened;
}

}  // namespace
#endif

TrainResult trainLinearCuBlas(const std::vector<std::vector<double>>& X,
                              const std::vector<double>& y) {
  TrainResult result;

#ifdef COMPUTEX_HAS_CUBLAS
  if (X.empty()) return result;
  if (X.size() != y.size()) {
    throw std::runtime_error("X and y row count do not match");
  }

  const std::size_t rowCount = X.size();
  const std::size_t featureCount = X[0].size();
  const std::size_t width = featureCount + 1;
  const auto matrix = flattenColumnMajorWithBias(X);

  result.coefficients.assign(width, 0.0);
  result.variant = featureCount <= 1 ? "simple_linear" : "multilinear";

  cublasHandle_t handle;
  checkCuBlas(cublasCreate(&handle), "cublasCreate");

  double *deviceMatrix = nullptr, *deviceWeights = nullptr, *devicePredictions = nullptr,
         *deviceErrors = nullptr, *deviceGradient = nullptr;

  checkCuda(cudaMalloc(&deviceMatrix, sizeof(double) * matrix.size()), "cudaMalloc matrix");
  checkCuda(cudaMalloc(&deviceWeights, sizeof(double) * width), "cudaMalloc weights");
  checkCuda(cudaMalloc(&devicePredictions, sizeof(double) * rowCount), "cudaMalloc predictions");
  checkCuda(cudaMalloc(&deviceErrors, sizeof(double) * rowCount), "cudaMalloc errors");
  checkCuda(cudaMalloc(&deviceGradient, sizeof(double) * width), "cudaMalloc gradient");

  checkCuda(cudaMemcpy(deviceMatrix, matrix.data(), sizeof(double) * matrix.size(),
                       cudaMemcpyHostToDevice),
            "copy matrix");
  checkCuda(cudaMemcpy(deviceWeights, result.coefficients.data(), sizeof(double) * width,
                       cudaMemcpyHostToDevice),
            "copy weights");

  std::vector<double> predictions(rowCount, 0.0);
  std::vector<double> errors(rowCount, 0.0);
  std::vector<double> gradient(width, 0.0);
  const double one = 1.0;
  const double zero = 0.0;
  const double learningRate = 0.0005;
  const int epochCount = 800;

  for (int epoch = 0; epoch < epochCount; ++epoch) {
    checkCuBlas(cublasDgemv(handle, CUBLAS_OP_N, static_cast<int>(rowCount),
                            static_cast<int>(width), &one, deviceMatrix, static_cast<int>(rowCount),
                            deviceWeights, 1, &zero, devicePredictions, 1),
                "linear forward");

    checkCuda(cudaMemcpy(predictions.data(), devicePredictions, sizeof(double) * rowCount,
                         cudaMemcpyDeviceToHost),
              "copy predictions");

    for (std::size_t row = 0; row < rowCount; ++row) {
      errors[row] = predictions[row] - y[row];
    }

    checkCuda(cudaMemcpy(deviceErrors, errors.data(), sizeof(double) * rowCount,
                         cudaMemcpyHostToDevice),
              "copy errors");

    checkCuBlas(cublasDgemv(handle, CUBLAS_OP_T, static_cast<int>(rowCount),
                            static_cast<int>(width), &one, deviceMatrix, static_cast<int>(rowCount),
                            deviceErrors, 1, &zero, deviceGradient, 1),
                "linear gradient");

    checkCuda(cudaMemcpy(gradient.data(), deviceGradient, sizeof(double) * width,
                         cudaMemcpyDeviceToHost),
              "copy gradient");

    for (std::size_t column = 0; column < width; ++column) {
      result.coefficients[column] -= learningRate * gradient[column] /
                                     static_cast<double>(rowCount);
    }

    checkCuda(cudaMemcpy(deviceWeights, result.coefficients.data(), sizeof(double) * width,
                         cudaMemcpyHostToDevice),
              "copy updated weights");
  }

  const auto metrics = calculateLinearMetrics(y, predictions);
  result.rmse = metrics.rmse;
  result.mae = metrics.mae;
  result.mse = metrics.mse;
  result.r2 = metrics.r2;
  result.accuracy = 0.0;

  cudaFree(deviceMatrix);
  cudaFree(deviceWeights);
  cudaFree(devicePredictions);
  cudaFree(deviceErrors);
  cudaFree(deviceGradient);
  cublasDestroy(handle);
  return result;
#else
  throw std::runtime_error("CUDA/cuBLAS is not available in this build.");
#endif
}

}  // namespace computex
