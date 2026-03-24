import pandas as pd
from .dao import SchedulePayload
from .feature_bundle import build_feature_bundle
from .analyse_regression import analyze_linear_regression,analyze_logistic_regression
from .graphs import create_linear_graphs,create_logistic_graphs,create_categorical_graphs

def build_analysis_bundle(frame: pd.DataFrame, payload: SchedulePayload, target_info: dict | None) -> dict:
    feature_bundle = build_feature_bundle(frame, payload.columns or {})

    if payload.model == "linear_regression":
        analysis = analyze_linear_regression(frame, payload.columns or {}, feature_bundle)
        graphs = create_linear_graphs(payload.file_name, analysis["plot_context"]) if analysis["metrics"] else create_categorical_graphs(frame, payload.file_name)
        return {
            "feature_bundle": feature_bundle,
            "metrics": analysis["metrics"],
            "graphs": graphs,
            "fallback_model": analysis["model_state"],
            "graph_notes": ["Regression line", "Residual plot"],
        }

    if payload.model == "logistic_regression":
        analysis = analyze_logistic_regression(frame, feature_bundle)
        has_metrics = bool(analysis["metrics"])
        metrics = dict(analysis["metrics"])
        if target_info and has_metrics:
            metrics["positive_label"] = target_info.get("positive_label")
            metrics["negative_label"] = target_info.get("negative_label")
        graphs = create_logistic_graphs(payload.file_name, analysis["plot_context"]) if has_metrics else create_categorical_graphs(frame, payload.file_name)
        return {
            "feature_bundle": feature_bundle,
            "metrics": metrics,
            "graphs": graphs,
            "fallback_model": analysis["model_state"],
            "graph_notes": ["Probability curve", "ROC curve"],
        }

    return {
        "feature_bundle": feature_bundle,
        "metrics": {},
        "graphs": create_categorical_graphs(frame, payload.file_name),
        "fallback_model": {},
        "graph_notes": [],
    }


def build_metric_response(payload: SchedulePayload, analysis_bundle: dict, cpp_result: dict, target_info: dict | None) -> dict:
    metrics = dict(analysis_bundle["metrics"])

    if payload.model == "linear_regression":
        if "rmse" not in metrics and cpp_result.get("rmse") is not None:
            metrics["rmse"] = cpp_result.get("rmse")
        metric_order = ["rmse", "mae", "mse", "r2"]
    else:
        if "accuracy" not in metrics and cpp_result.get("accuracy") is not None:
            metrics["accuracy"] = cpp_result.get("accuracy")
        metric_order = ["accuracy", "precision", "recall", "f1", "roc_auc", "log_loss"]

    return {
        "model": payload.model,
        "metric_order": metric_order,
        "values": metrics,
        "graph_notes": analysis_bundle["graph_notes"],
        "target_info": target_info,
    }