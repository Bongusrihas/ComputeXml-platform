#pragma once

#include <vector>

#include "parser.hpp"

namespace computex {

TrainResult trainLogisticOpen(const std::vector<std::vector<double>>& X, const std::vector<double>& y);

}  // namespace computex
