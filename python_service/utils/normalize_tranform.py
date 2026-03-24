import numpy as np
from .dao import PredictRequest
from .cleaner import to_clean_text

def normalize_raw_inputs(request: PredictRequest) -> dict:
    if isinstance(request.inputs, dict):
        return request.inputs
    return {}


def transform_prediction_inputs(raw_inputs: dict, transformers: list[dict]) -> list[float]:
    transformed_values: list[float] = []

    for transformer in transformers:
        column_name = transformer["column"]
        raw_value = raw_inputs.get(column_name)
        text_value = to_clean_text(raw_value)
        encoding = transformer["encoding"]

        if encoding == "double":
            if text_value == "":
                raise ValueError(f"Enter a numeric value for {column_name}.")
            try:
                transformed_values.append(float(text_value))
            except ValueError as error:
                raise ValueError(f"Only numeric values are allowed for {column_name}.") from error
            continue

        if encoding == "one_hot":
            selected_value = text_value or transformer["default_category"]
            if selected_value not in transformer["categories"]:
                selected_value = transformer["default_category"]
            transformed_values.extend([1.0 if selected_value == category else 0.0 for category in transformer["categories"]])
            continue

        if encoding == "label":
            selected_value = text_value or transformer["default_category"]
            mapping = transformer["mapping"]
            transformed_values.append(float(mapping.get(selected_value, transformer["default_value"])))
            continue

    return transformed_values

def compute_raw_score(saved_model: dict, feature_vector: list[float]) -> tuple[float, str]:
    transformed_feature_names = saved_model.get("transformed_feature_names") or []
    coefficients = saved_model.get("cpp_result", {}).get("model_coefficients") or []

    if len(coefficients) == len(feature_vector) + 1:
        raw_score = float(coefficients[0] + sum(weight * value for weight, value in zip(coefficients[1:], feature_vector)))
        return raw_score, "cpp"

    if len(coefficients) == len(feature_vector):
        raw_score = float(sum(weight * value for weight, value in zip(coefficients, feature_vector)))
        return raw_score, "cpp"

    fallback_model = saved_model.get("fallback_model") or {}
    model_type = fallback_model.get("type")

    if model_type == "linear":
        fallback_coefficients = fallback_model.get("coefficients") or [0.0]
        raw_score = float(fallback_coefficients[0] + sum(weight * value for weight, value in zip(fallback_coefficients[1:], feature_vector)))
        return raw_score, "python_fallback"

    if model_type == "logistic":
        weights = np.array(fallback_model.get("weights") or [0.0], dtype=float)
        feature_means = np.array(fallback_model.get("feature_means") or [0.0] * len(feature_vector), dtype=float)
        feature_stds = np.array(fallback_model.get("feature_stds") or [1.0] * len(feature_vector), dtype=float)
        scaled_vector = (np.array(feature_vector, dtype=float) - feature_means) / np.where(feature_stds == 0.0, 1.0, feature_stds)
        design = np.concatenate(([1.0], scaled_vector))
        raw_score = float(design @ weights)
        return raw_score, "python_fallback"

    if transformed_feature_names:
        raise ValueError(f"Prediction needs exactly {len(transformed_feature_names)} feature values after encoding.")

    return 0.0, "empty"