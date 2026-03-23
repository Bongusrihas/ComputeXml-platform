#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>

#include "linear_cublas.hpp"
#include "linear_open.hpp"
#include "logistic_cublas.hpp"
#include "logistic_open.hpp"
#include "parser.hpp"

namespace {

std::string readAll(const std::string& path) {
  std::ifstream input(path);
  if (!input.is_open()) {
    throw std::runtime_error("Cannot open job file: " + path);
  }

  std::ostringstream stream;
  stream << input.rdbuf();
  return stream.str();
}

std::string extractString(const std::string& text, const std::string& key) {
  std::regex pattern("\\\"" + key + "\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"");
  std::smatch match;
  if (std::regex_search(text, match, pattern)) {
    return match[1];
  }
  return "";
}

std::string toJson(const computex::TrainResult& result, const std::string& model,
                   const std::string& hardware, std::size_t rows, std::size_t cols) {
  std::ostringstream stream;
  stream << "{";
  stream << "\"status\":\"ok\",";
  stream << "\"model\":\"" << model << "\",";
  stream << "\"variant\":\"" << result.variant << "\",";
  stream << "\"hardware\":\"" << hardware << "\",";
  stream << "\"rows\":" << rows << ",";
  stream << "\"cols\":" << cols << ",";
  stream << "\"rmse\":" << result.rmse << ",";
  stream << "\"mae\":" << result.mae << ",";
  stream << "\"mse\":" << result.mse << ",";
  stream << "\"r2\":" << result.r2 << ",";
  stream << "\"accuracy\":" << result.accuracy << ",";
  stream << "\"precision\":" << result.precision << ",";
  stream << "\"recall\":" << result.recall << ",";
  stream << "\"f1\":" << result.f1 << ",";
  stream << "\"model_coefficients\":[";
  for (std::size_t index = 0; index < result.coefficients.size(); ++index) {
    if (index) stream << ",";
    stream << result.coefficients[index];
  }
  stream << "]}";
  return stream.str();
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc < 3) {
      std::cerr << "Usage: engine <input_json> <output_json>\n";
      return 1;
    }

    const std::string inputPath = argv[1];
    const std::string outputPath = argv[2];
    const std::string jobJson = readAll(inputPath);

    const std::string hardwareRequest = extractString(jobJson, "hardware");
    const std::string model = extractString(jobJson, "model");
    const std::string storedPath = extractString(jobJson, "stored_path");
    const std::string fillNulls = extractString(jobJson, "nulls");
    const std::string numericFill = extractString(jobJson, "fill");
    const std::string removeNulls = extractString(jobJson, "remove_nulls");

    computex::ParseOptions options;
    options.fillNulls = fillNulls != "no";
    options.numericFill = numericFill.empty() ? "mean" : numericFill;
    options.removeNullRows = removeNulls == "remove";
    options.stringFill = "mode";

    computex::RawTable table = computex::parseCsvStream(storedPath);
    computex::fillNullsInPlace(table, options);
    computex::ParsedData data = computex::toNumericDataset(table);

    computex::TrainResult result;
    std::string actualHardware = hardwareRequest == "gpu" ? "gpu" : "cpu";
    const bool isLogistic = model == "logistic_regression";

    if (actualHardware == "gpu") {
      try {
        result = isLogistic ? computex::trainLogisticCuBlas(data.X, data.y)
                            : computex::trainLinearCuBlas(data.X, data.y);
      } catch (...) {
        actualHardware = "cpu";
        result = isLogistic ? computex::trainLogisticOpen(data.X, data.y)
                            : computex::trainLinearOpen(data.X, data.y);
      }
    } else {
      result = isLogistic ? computex::trainLogisticOpen(data.X, data.y)
                          : computex::trainLinearOpen(data.X, data.y);
    }

    std::ofstream output(outputPath);
    output << toJson(result, model, actualHardware, data.rows, data.cols);
    return 0;
  } catch (const std::exception& error) {
    if (argc >= 3) {
      std::ofstream output(argv[2]);
      output << "{\"status\":\"error\",\"message\":\"" << error.what() << "\"}";
    }
    std::cerr << error.what() << "\n";
    return 1;
  }
}
