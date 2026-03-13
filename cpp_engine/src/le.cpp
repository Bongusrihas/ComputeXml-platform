#include "le.hpp"

namespace computex {

std::vector<double> labelEncode(const std::vector<std::string>& column,
                                std::unordered_map<std::string, int>& mapOut) {
  mapOut.clear();
  std::vector<double> out;
  out.reserve(column.size());

  int nextId = 0;
  for (const auto& value : column) {
    auto it = mapOut.find(value);
    if (it == mapOut.end()) {
      mapOut[value] = nextId;
      out.push_back(static_cast<double>(nextId));
      nextId += 1;
    } else {
      out.push_back(static_cast<double>(it->second));
    }
  }
  return out;
}

}  // namespace computex