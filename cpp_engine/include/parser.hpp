#pragma once

#include <map>
#include <string>
#include <vector>

namespace computex {

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