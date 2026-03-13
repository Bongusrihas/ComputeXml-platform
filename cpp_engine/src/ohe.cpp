#include "ohe.hpp"

namespace computex {

std::vector<std::vector<double>> oneHotEncode(
    const std::vector<std::string>& column,
    std::unordered_map<std::string, int>& indexMap) {
  indexMap.clear();
  int next = 0;
  for (const auto& value : column) {
    if (!indexMap.count(value)) {
      indexMap[value] = next++;
    }
  }

  std::vector<std::vector<double>> out(column.size(), std::vector<double>(indexMap.size(), 0.0));
  for (std::size_t i = 0; i < column.size(); ++i) {
    out[i][indexMap[column[i]]] = 1.0;
  }
  return out;
}

}  // namespace computex