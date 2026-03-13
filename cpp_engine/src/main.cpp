#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>

#include "cublas_models.hpp"
#include "openblas_models.hpp"
#include "parser.hpp"

using computex::ParseOptions;
using computex::ParsedData;
using computex::RawTable;
using computex::TrainResult;

static std::string readAll(const std::string& path) {
  std::ifstream in(path);
  if (!in.is_open()) throw std::runtime_error("Cannot open input JSON: " + path);
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

static std::string extractString(const std::string& text, const std::string& key) {
  std::regex re("\\\"" + key + "\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"");
  std::smatch m;
  if (std::regex_search(text, m, re)) return m[1];
  return "";
}

static std::string toJsonResult(const TrainResult& res, const std::string& model,
                                const std::string& hardware, std::size_t rows,
                                std::size_t cols) {
  std::ostringstream out;
  out << "{";
  out << "\"status\":\"ok\",";
  out << "\"model\":\"" << model << "\",";
  out << "\"hardware\":\"" << hardware << "\",";
  out << "\"rows\":" << rows << ",";
  out << "\"cols\":" << cols << ",";
  out << "\"rmse\":" << res.rmse << ",";
  out << "\"accuracy\":" << res.accuracy << ",";
  out << "\"model_coefficients\":[";
  for (std::size_t i = 0; i < res.coefficients.size(); ++i) {
    if (i) out << ",";
    out << res.coefficients[i];
  }
  out << "]}";
  return out.str();
}

int main(int argc, char** argv) {
  try {
    if (argc < 3) {
      std::cerr << "Usage: engine <input_json> <output_json>\n";
      return 1;
    }

    const std::string inPath = argv[1];
    const std::string outPath = argv[2];
    const std::string inJson = readAll(inPath);

    const std::string hardwareReq = extractString(inJson, "hardware");
    const std::string model = extractString(inJson, "model");
    const std::string storedFile = extractString(inJson, "stored_file");
    const std::string nulls = extractString(inJson, "nulls");
    const std::string fill = extractString(inJson, "fill");
    const std::string removeNulls = extractString(inJson, "remove_nulls");

    ParseOptions options;
    options.fillNulls = nulls != "no";
    options.numericFill = fill.empty() ? "mean" : fill;
    options.removeNullRows = removeNulls == "remove";
    options.stringFill = "mode";

    const std::string csvPath = "/app/input_output/" + storedFile;
    RawTable table = computex::parseCsvStream(csvPath);
    computex::fillNullsInPlace(table, options);
    ParsedData data = computex::toNumericDataset(table);

    TrainResult result;
    std::string actualHardware = hardwareReq == "gpu" ? "gpu" : "cpu";

    if (actualHardware == "gpu") {
      try {
        result = computex::trainCuBlas(model, data.X, data.y);
      } catch (...) {
        actualHardware = "cpu";
        result = computex::trainOpenBlas(model, data.X, data.y);
      }
    } else {
      result = computex::trainOpenBlas(model, data.X, data.y);
    }

    std::string output = toJsonResult(result, model, actualHardware, data.rows, data.cols);

    std::ofstream out(outPath);
    out << output;

    return 0;
  } catch (const std::exception& ex) {
    std::ofstream out(argv[2]);
    out << "{\"status\":\"error\",\"message\":\"" << ex.what() << "\"}";
    return 1;
  }
}
