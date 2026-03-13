#pragma once

#include <string>
#include <unordered_map>
#include <vector>

namespace computex {

std::vector<std::vector<double>> oneHotEncode(
    const std::vector<std::string>& column,
    std::unordered_map<std::string, int>& indexMap);

}  // namespace computex