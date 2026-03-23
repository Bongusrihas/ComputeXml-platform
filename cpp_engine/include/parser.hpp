#pragma once

#include <string>
#include <vector>

namespace computex {

struct TrainResult {
  std::vector<double> coefficients;
  double rmse = 0.0;
  double mae = 0.0;
  double mse = 0.0;
  double r2 = 0.0;
  double accuracy = 0.0;
  double precision = 0.0;
  double recall = 0.0;
  double f1 = 0.0;
  std::string variant = "simple_linear";
};

struct ParsedData {
  std::vector<std::vector<double>> X;
  std::vector<double> y;
  std::size_t rows = 0;
  std::size_t cols = 0;
};

struct ParseOptions {
  bool fillNulls = true;
  bool removeNullRows = false;
  std::string numericFill = "mean";
  std::string stringFill = "mode";
};

struct RawTable {
  std::vector<std::string> headers;
  std::vector<std::vector<std::string>> rows;
};

RawTable parseCsvStream(const std::string& filePath);
void fillNullsInPlace(RawTable& table, const ParseOptions& options);
ParsedData toNumericDataset(const RawTable& table);

}  // namespace computex
