import pandas as pd
import numpy as np
from .fit_models import fit_linear_model,fit_logistic_model
from .neccessity import get_numeric_original_series
from .metrics import compute_linear_metrics,compute_logistic_metrics,compute_roc_curve


def analyze_linear_regression(frame: pd.DataFrame, column_config: dict, feature_bundle: dict) -> dict:
    features = feature_bundle["matrix"]
    target = pd.to_numeric(frame.iloc[:, -1], errors="coerce")
    valid_mask = target.notna()

    if not valid_mask.any() or features.shape[1] == 0:
        return {
            "metrics": {},
            "model_state": {"type": "linear", "coefficients": [0.0]},
            "plot_context": {},
        }

    filtered_features = features[valid_mask.to_numpy()]
    filtered_target = target[valid_mask].to_numpy(dtype=float)
    coefficients, predictions = fit_linear_model(filtered_features, filtered_target)
    residuals = filtered_target - predictions

    independent_columns = list(frame.columns[:-1])
    target_name = str(frame.columns[-1])
    plot_context = {
        "title": "Predicted vs Actual",
        "x_label": "Predicted Target",
        "y_label": target_name,
        "x_values": predictions,
        "y_values": filtered_target,
        "line_x": np.linspace(float(np.min(predictions)), float(np.max(predictions)), 100),
        "line_y": np.linspace(float(np.min(predictions)), float(np.max(predictions)), 100),
        "residual_x": predictions,
        "residual_y": residuals,
    }

    if len(independent_columns) == 1:
        first_feature = independent_columns[0]
        first_feature_type = str(column_config.get(first_feature, {}).get("data_type", "")).lower()
        if first_feature_type in {"int", "float"}:
            numeric_x = get_numeric_original_series(frame.loc[valid_mask], first_feature).to_numpy(dtype=float)
            if numeric_x.size:
                order = np.argsort(numeric_x)
                plot_context.update(
                    {
                        "title": f"{first_feature} vs {target_name}",
                        "x_label": first_feature,
                        "y_label": target_name,
                        "x_values": numeric_x,
                        "y_values": filtered_target,
                        "line_x": numeric_x[order],
                        "line_y": predictions[order],
                        "residual_x": numeric_x,
                        "residual_y": residuals,
                    }
                )

    return {
        "metrics": compute_linear_metrics(filtered_target, predictions),
        "model_state": {
            "type": "linear",
            "coefficients": coefficients.tolist(),
        },
        "plot_context": plot_context,
    }


def analyze_logistic_regression(frame: pd.DataFrame, feature_bundle: dict) -> dict:
    features = feature_bundle["matrix"]
    target = pd.to_numeric(frame.iloc[:, -1], errors="coerce")
    valid_mask = target.notna()

    if not valid_mask.any() or features.shape[1] == 0:
        return {
            "metrics": {},
            "model_state": {"type": "logistic", "weights": [0.0], "feature_means": [], "feature_stds": []},
            "plot_context": {},
        }

    filtered_features = features[valid_mask.to_numpy()]
    filtered_target = target[valid_mask].to_numpy(dtype=float)
    weights, probabilities, feature_means, feature_stds = fit_logistic_model(filtered_features, filtered_target)
    fpr, tpr, auc = compute_roc_curve(filtered_target, probabilities)

    independent_columns = list(frame.columns[:-1])
    sorted_order = np.argsort(probabilities)
    plot_context = {
        "title": "Sorted Probability Curve",
        "x_label": "Sorted Sample",
        "curve_x": np.arange(1, len(probabilities) + 1),
        "curve_y": probabilities[sorted_order],
        "actual_x": np.arange(1, len(probabilities) + 1),
        "actual_y": filtered_target[sorted_order],
        "fpr": fpr,
        "tpr": tpr,
        "auc": auc,
    }

    if len(independent_columns) == 1:
        first_feature = independent_columns[0]
        numeric_x = get_numeric_original_series(frame.loc[valid_mask], first_feature)
        if numeric_x.notna().all():
            sorted_x = numeric_x.to_numpy(dtype=float)
            order = np.argsort(sorted_x)
            plot_context.update(
                {
                    "title": f"Probability Curve: {first_feature}",
                    "x_label": first_feature,
                    "curve_x": sorted_x[order],
                    "curve_y": probabilities[order],
                    "actual_x": sorted_x,
                    "actual_y": filtered_target,
                }
            )

    return {
        "metrics": compute_logistic_metrics(filtered_target, probabilities, auc),
        "model_state": {
            "type": "logistic",
            "weights": weights.tolist(),
            "feature_means": feature_means.tolist(),
            "feature_stds": feature_stds.tolist(),
        },
        "plot_context": plot_context,
    }