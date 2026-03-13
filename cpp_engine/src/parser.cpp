#include "parser.hpp"

#include <algorithm>
#include <cstdlib>
#include <numeric>
#include <stdexcept>
#include <unordered_map>

#include <csv.hpp>

#include "le.hpp"
#include "ohe.hpp"

namespace computex {

RawTable parseCsvStream(const std::string& filePath) {
  csv::CSVReader reader(filePath);
  RawTable table;

  table.headers = reader.get_col_names();
  if (table.headers.empty()) {
    throw std::runtime_error("CSV has no headers: " + filePath);
  }

  for (csv::CSVRow& row : reader) {
    std::vector<std::string> out;
    out.reserve(table.headers.size());
    for (std::size_t i = 0; i < table.headers.size(); ++i) {
      if (i < row.size()) {
        out.push_back(row[i].get<std::string>());
      } else {
        out.emplace_back("");
      }
    }
    table.rows.push_back(std::move(out));
  }
  return table;
}

static bool isNumber(const std::string& v) {
  if (v.empty()) return false;
  char* end = nullptr;
  std::strtod(v.c_str(), &end);
  return end != v.c_str() && *end == '\0';
}

void fillNullsInPlace(RawTable& table, const ParseOptions& options) {
  if (table.rows.empty() || table.headers.empty()) return;

  const std::size_t cols = table.headers.size();
  std::vector<bool> numeric(cols, true);

  for (std::size_t c = 0; c < cols; ++c) {
    for (const auto& row : table.rows) {
      const auto& v = row[c];
      if (!v.empty() && !isNumber(v)) {
        numeric[c] = false;
        break;
      }
    }
  }

  std::vector<std::size_t> keep;
  keep.reserve(table.rows.size());

  std::vector<std::unordered_map<std::string, int>> freq(cols);
  std::vector<double> runningSum(cols, 0.0);
  std::vector<int> runningCount(cols, 0);
  std::vector<std::vector<double>> seenValues(cols);

  for (std::size_t r = 0; r < table.rows.size(); ++r) {
    bool hasNull = false;
    for (std::size_t c = 0; c < cols; ++c) {
      std::string& v = table.rows[r][c];
      const bool nullish = v.empty() || v == "NULL" || v == "null" || v == "NA";
      if (!nullish) {
        if (numeric[c]) {
          double x = std::stod(v);
          runningSum[c] += x;
          runningCount[c] += 1;
          seenValues[c].push_back(x);
        } else {
          freq[c][v] += 1;
        }
        continue;
      }

      hasNull = true;
      if (options.removeNullRows) continue;
      if (!options.fillNulls) continue;

      if (numeric[c]) {
        double fill = 0.0;
        if (options.numericFill == "median") {
          auto values = seenValues[c];
          if (!values.empty()) {
            std::nth_element(values.begin(), values.begin() + values.size() / 2, values.end());
            fill = values[values.size() / 2];
          }
        } else {
          fill = runningCount[c] == 0 ? 0.0 : runningSum[c] / runningCount[c];
        }
        v = std::to_string(fill);
        runningSum[c] += fill;
        runningCount[c] += 1;
        seenValues[c].push_back(fill);
      } else {
        std::string mode = "";
        int best = -1;
        for (const auto& it : freq[c]) {
          if (it.second > best) {
            best = it.second;
            mode = it.first;
          }
        }
        if (mode.empty()) mode = "unknown";
        v = mode;
        freq[c][mode] += 1;
      }
    }

    if (!(options.removeNullRows && hasNull)) {
      keep.push_back(r);
    }
  }

  if (options.removeNullRows) {
    std::vector<std::vector<std::string>> filtered;
    filtered.reserve(keep.size());
    for (auto i : keep) filtered.push_back(std::move(table.rows[i]));
    table.rows = std::move(filtered);
  }
}

ParsedData toNumericDataset(const RawTable& table) {
  ParsedData data;
  if (table.rows.empty() || table.headers.size() < 2) return data;

  const std::size_t cols = table.headers.size();
  const std::size_t featureCols = cols - 1;

  std::vector<bool> numeric(featureCols, true);
  for (std::size_t c = 0; c < featureCols; ++c) {
    for (const auto& row : table.rows) {
      if (!isNumber(row[c])) {
        numeric[c] = false;
        break;
      }
    }
  }

  std::vector<std::vector<double>> features(table.rows.size());

  for (std::size_t c = 0; c < featureCols; ++c) {
    if (numeric[c]) {
      for (std::size_t r = 0; r < table.rows.size(); ++r) {
        features[r].push_back(std::stod(table.rows[r][c]));
      }
      continue;
    }

    std::vector<std::string> col(table.rows.size());
    for (std::size_t r = 0; r < table.rows.size(); ++r) col[r] = table.rows[r][c];

    std::unordered_map<std::string, int> freq;
    for (const auto& v : col) freq[v] += 1;

    if (freq.size() > 7) {
      std::unordered_map<std::string, int> mapOut;
      auto enc = labelEncode(col, mapOut);
      for (std::size_t r = 0; r < table.rows.size(); ++r) features[r].push_back(enc[r]);
    } else {
      std::unordered_map<std::string, int> indexMap;
      auto enc = oneHotEncode(col, indexMap);
      for (std::size_t r = 0; r < table.rows.size(); ++r) {
        features[r].insert(features[r].end(), enc[r].begin(), enc[r].end());
      }
    }
  }

  data.X = std::move(features);
  data.y.resize(table.rows.size(), 0.0);
  for (std::size_t r = 0; r < table.rows.size(); ++r) {
    const auto& yv = table.rows[r][cols - 1];
    data.y[r] = isNumber(yv) ? std::stod(yv) : 0.0;
  }

  data.rows = data.X.size();
  data.cols = data.X.empty() ? 0 : data.X[0].size();
  return data;
}

}  // namespace computex
