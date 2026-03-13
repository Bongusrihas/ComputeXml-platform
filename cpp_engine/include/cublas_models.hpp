#pragma once

#include <string>
#include <vector>

#include "openblas_models.hpp"

namespace computex {

TrainResult trainCuBlas(const std::string& model, const std::vector<std::vector<double>>& X,
                        const std::vector<double>& y);

}  // namespace computex