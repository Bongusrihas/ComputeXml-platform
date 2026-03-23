#include "parser.hpp"

#include <algorithm>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include <csv.hpp>

namespace computex {

namespace {

bool isNumber(const std::string& value) {
  if (value.empty()) return false;
  char* end = nullptr;
  std::strtod(value.c_str(), &end);
  return end != value.c_str() && *end == '\0';
}

bool isNullLike(const std::string& value) {
  return value.empty() || value == "NULL" || value == "null" || value == "NA" ||
         value == "NaN";
}

std::string findMode(const std::unordered_map<std::string, int>& counts) {
  std::string mode = "unknown";
  int best = -1;
  for (const auto& [value, count] : counts) {
    if (count > best) {
      best = count;
      mode = value;
    }
  }
  return mode;
}

std::vector<double> labelEncode(const std::vector<std::string>& column) {
  std::unordered_map<std::string, double> mapping;
  std::vector<double> encoded;
  encoded.reserve(column.size());

  double next = 0.0;
  for (const auto& value : column) {
    if (!mapping.count(value)) {
      mapping[value] = next;
      next += 1.0;
    }
    encoded.push_back(mapping[value]);
  }

  return encoded;
}

std::vector<std::vector<double>> oneHotEncode(const std::vector<std::string>& column) {
  std::unordered_map<std::string, int> mapping;
  int next = 0;
  for (const auto& value : column) {
    if (!mapping.count(value)) {
      mapping[value] = next++;
    }
  }

  std::vector<std::vector<double>> encoded(column.size(),
                                           std::vector<double>(mapping.size(), 0.0));
  for (std::size_t row = 0; row < column.size(); ++row) {
    encoded[row][mapping[column[row]]] = 1.0;
  }

  return encoded;
}

}  // namespace

RawTable parseCsvStream(const std::string& filePath) {
  csv::CSVReader reader(filePath);
  RawTable table;

  table.headers = reader.get_col_names();
  if (table.headers.empty()) {
    throw std::runtime_error("CSV has no headers: " + filePath);
  }

  for (csv::CSVRow& row : reader) {
    std::vector<std::string> parsedRow;
    parsedRow.reserve(table.headers.size());

    for (std::size_t column = 0; column < table.headers.size(); ++column) {
      if (column < row.size()) {
        parsedRow.push_back(row[column].get<std::string>());
      } else {
        parsedRow.emplace_back("");
      }
    }

    table.rows.push_back(std::move(parsedRow));
  }

  return table;
}

void fillNullsInPlace(RawTable& table, const ParseOptions& options) {
  if (table.rows.empty() || table.headers.empty()) return;

  // The CSV is loaded once into RAM, and missing values are filled in row order
  // using only the values that have already been seen in that column.
  const std::size_t columnCount = table.headers.size();
  std::vector<bool> numericColumns(columnCount, true);

  for (std::size_t column = 0; column < columnCount; ++column) {
    for (const auto& row : table.rows) {
      if (!isNullLike(row[column]) && !isNumber(row[column])) {
        numericColumns[column] = false;
        break;
      }
    }
  }

  std::vector<std::unordered_map<std::string, int>> frequency(columnCount);
  std::vector<double> runningSum(columnCount, 0.0);
  std::vector<int> runningCount(columnCount, 0);
  std::vector<std::vector<double>> seenValues(columnCount);
  std::vector<std::vector<std::string>> cleanedRows;
  cleanedRows.reserve(table.rows.size());

  for (auto row : table.rows) {
    bool rowHasNull = false;

    for (std::size_t column = 0; column < columnCount; ++column) {
      std::string& value = row[column];
      if (!isNullLike(value)) {
        if (numericColumns[column]) {
          const double numericValue = std::stod(value);
          runningSum[column] += numericValue;
          runningCount[column] += 1;
          seenValues[column].push_back(numericValue);
        } else {
          frequency[column][value] += 1;
        }
        continue;
      }

      rowHasNull = true;
      if (options.removeNullRows) {
        continue;
      }

      if (!options.fillNulls) {
        continue;
      }

      if (numericColumns[column]) {
        double replacement = 0.0;
        if (options.numericFill == "median" && !seenValues[column].empty()) {
          auto values = seenValues[column];
          std::nth_element(values.begin(), values.begin() + values.size() / 2, values.end());
          replacement = values[values.size() / 2];
        } else if (runningCount[column] > 0) {
          replacement = runningSum[column] / static_cast<double>(runningCount[column]);
        }

        value = std::to_string(replacement);
        runningSum[column] += replacement;
        runningCount[column] += 1;
        seenValues[column].push_back(replacement);
      } else {
        const std::string mode = findMode(frequency[column]);
        value = mode;
        frequency[column][mode] += 1;
      }
    }

    if (!(options.removeNullRows && rowHasNull)) {
      cleanedRows.push_back(std::move(row));
    }
  }

  table.rows = std::move(cleanedRows);
}

ParsedData toNumericDataset(const RawTable& table) {
  ParsedData data;
  if (table.rows.empty() || table.headers.size() < 2) {
    return data;
  }

  const std::size_t featureColumnCount = table.headers.size() - 1;
  std::vector<bool> numericColumns(featureColumnCount, true);

  for (std::size_t column = 0; column < featureColumnCount; ++column) {
    for (const auto& row : table.rows) {
      if (!isNullLike(row[column]) && !isNumber(row[column])) {
        numericColumns[column] = false;
        break;
      }
    }
  }

  std::vector<std::vector<double>> features(table.rows.size());

  for (std::size_t column = 0; column < featureColumnCount; ++column) {
    if (numericColumns[column]) {
      for (std::size_t row = 0; row < table.rows.size(); ++row) {
        features[row].push_back(isNullLike(table.rows[row][column]) ? 0.0
                                                                    : std::stod(table.rows[row][column]));
      }
      continue;
    }

    std::vector<std::string> values(table.rows.size());
    for (std::size_t row = 0; row < table.rows.size(); ++row) {
      values[row] = table.rows[row][column];
    }

    std::unordered_map<std::string, int> uniqueValues;
    for (const auto& value : values) {
      uniqueValues[value] += 1;
    }

    if (uniqueValues.size() > 7) {
      auto encoded = labelEncode(values);
      for (std::size_t row = 0; row < table.rows.size(); ++row) {
        features[row].push_back(encoded[row]);
      }
    } else {
      auto encoded = oneHotEncode(values);
      for (std::size_t row = 0; row < table.rows.size(); ++row) {
        features[row].insert(features[row].end(), encoded[row].begin(), encoded[row].end());
      }
    }
  }

  data.X = std::move(features);
  data.y.resize(table.rows.size(), 0.0);
  const std::size_t targetColumn = table.headers.size() - 1;

  for (std::size_t row = 0; row < table.rows.size(); ++row) {
    const auto& value = table.rows[row][targetColumn];
    data.y[row] = isNullLike(value) ? 0.0 : std::stod(value);
  }

  data.rows = data.X.size();
  data.cols = data.X.empty() ? 0 : data.X[0].size();
  return data;
}

}  // namespace computex
