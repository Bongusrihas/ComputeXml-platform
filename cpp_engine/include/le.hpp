#pragma once

#include <string>
#include <unordered_map>
#include <vector>

namespace computex {

std::vector<double> labelEncode(
    const std::vector<std::string>& column,
    std::unordered_map<std::string, int>& mapOut);

}  // namespace computex