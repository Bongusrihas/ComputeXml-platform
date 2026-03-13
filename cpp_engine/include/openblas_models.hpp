#pragma once

#include <string>
#include <vector>

namespace computex {

struct TrainResult {
  std::vector<double> coefficients;
  double rmse = 0.0;
  double accuracy = 0.0;
};

TrainResult trainOpenBlas(const std::string& model, const std::vector<std::vector<double>>& X,
                          const std::vector<double>& y);

}  // namespace computex