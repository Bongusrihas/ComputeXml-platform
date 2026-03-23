import json
import os
import pickle
import re
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from bokeh.layouts import column as bokeh_column
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, output_file, save
from fastapi import FastAPI, HTTPException
from plotly import express as px
from plotly import graph_objects as go
from plotly.subplots import make_subplots
from pydantic import BaseModel, ConfigDict, Field


#set CPLUS_ENGINE_PATH=C:\Users\Srihas\Desktop\mini_project_codex\cpp_engine\build_win32\Release\engine.exe
#uvicorn app.main:app --host 0.0.0.0 --port 8000

app = FastAPI(title="Computex Python Orchestrator")

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = REPO_ROOT / "backend" / "static"
UPLOAD_ROOT = STATIC_ROOT / "uploads"
ARTIFACT_ROOT = STATIC_ROOT / "artifacts"
DEFAULT_THRESHOLD = 0.5

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)


class SchedulePayload(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    columns: dict
    global_data: dict = Field(alias="global")
    file_name: str
    data_size: list[int]
    model: str
    stored_file: str
    stored_path: str
    uploaded_by: str | None = None


class PredictRequest(BaseModel):
    pickle_file: str
    features: list[float] | None = None
    inputs: dict | None = None
    threshold: float | None = DEFAULT_THRESHOLD
    positive_label: str | None = None


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value or "artifact")
    return cleaned.strip("_") or "artifact"


def make_artifact_path(prefix: str, original_name: str, suffix: str) -> Path:
    file_stem = sanitize_name(Path(original_name).stem)
    return ARTIFACT_ROOT / f"{prefix}_{file_stem}_{int(time.time() * 1000)}{suffix}"


def resolve_engine_path() -> Path | None:
    configured = os.environ.get("CPLUS_ENGINE_PATH")
    candidates: list[Path] = []

    if configured:
        candidates.append(Path(configured).expanduser())

    candidates.extend(
        [
            REPO_ROOT / "cpp_engine" / "build" / "Release" / "engine.exe",
            REPO_ROOT / "cpp_engine" / "build_win32" / "Release" / "engine.exe",
            REPO_ROOT / "cpp_engine" / "build" / "engine.exe",
            REPO_ROOT / "cpp_engine" / "build_win32" / "engine.exe",
            REPO_ROOT / "cpp_engine" / "build" / "engine",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0] if candidates else None


def resolve_uploaded_csv(stored_file: str, stored_path: str) -> Path:
    candidates = [
        UPLOAD_ROOT / Path(stored_file).name,
        Path(stored_path),
        REPO_ROOT / "backend" / "static" / "uploads" / Path(stored_file).name,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    tried = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Uploaded CSV not found. Checked: {tried}")


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -60.0, 60.0)))


def to_clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value).strip()


def coerce_feature_column(series: pd.Series, selected_type: str | None) -> pd.Series:
    if selected_type in {"int", "float"}:
        return pd.to_numeric(series, errors="coerce")

    return series.map(to_clean_text)


def normalize_target_column(
    frame: pd.DataFrame, dependent_col: str, model: str
) -> tuple[pd.Series, dict[str, float] | None, dict | None]:
    raw_target = frame[dependent_col].map(to_clean_text)
    present_mask = raw_target != ""
    numeric_target = pd.to_numeric(raw_target.where(present_mask, np.nan), errors="coerce")

    if model == "logistic_regression":
        counts = raw_target[present_mask].value_counts().to_dict()
        if len(counts) != 2:
            raise ValueError("Logistic regression needs exactly two target classes.")

        labels_by_frequency = sorted(counts.keys(), key=lambda label: (-counts[label], label))
        positive_label = labels_by_frequency[0]
        negative_label = next(label for label in counts.keys() if label != positive_label)
        mapping = {negative_label: 0.0, positive_label: 1.0}

        return (
            raw_target.map(lambda label: mapping.get(label, np.nan)),
            mapping,
            {
                "labels": [negative_label, positive_label],
                "class_frequency": {label: int(counts[label]) for label in counts},
                "positive_label": positive_label,
                "negative_label": negative_label,
                "default_threshold": DEFAULT_THRESHOLD,
                "target_mapping": mapping,
            },
        )

    if not numeric_target[present_mask].notna().all():
        raise ValueError("Linear regression needs a numeric dependent column.")

    return numeric_target, None, None


def prepare_training_frame(payload: SchedulePayload) -> tuple[pd.DataFrame, Path, dict[str, float] | None, dict | None]:
    source_path = resolve_uploaded_csv(payload.stored_file, payload.stored_path)
    frame = pd.read_csv(source_path)
    if frame.empty:
        raise ValueError("Uploaded CSV is empty.")

    column_config = payload.columns or {}
    active_columns = [
        name for name, config in column_config.items() if config.get("type") != "remove" and name in frame.columns
    ]
    if not active_columns:
        active_columns = list(frame.columns)

    dependent_columns = [
        name for name, config in column_config.items() if config.get("type") == "dependent" and name in active_columns
    ]
    if len(dependent_columns) != 1:
        raise ValueError("Exactly one dependent column is required.")

    dependent_col = dependent_columns[0]
    independent_cols = [name for name in active_columns if name != dependent_col]
    if not independent_cols:
        raise ValueError("At least one independent column is required.")

    prepared = frame.loc[:, independent_cols + [dependent_col]].copy()

    for column_name in independent_cols:
        selected_type = str(column_config.get(column_name, {}).get("data_type", "")).lower() or None
        prepared[column_name] = coerce_feature_column(prepared[column_name], selected_type)

    prepared[dependent_col], target_mapping, target_info = normalize_target_column(prepared, dependent_col, payload.model)

    prepared_path = make_artifact_path("prepared", payload.file_name, ".csv")
    prepared.to_csv(prepared_path, index=False, na_rep="")
    return prepared, prepared_path, target_mapping, target_info


def choose_hardware(rows: int, cols: int) -> str:
    return "cpu" if rows < 256 and cols < 30 else "gpu"


def invoke_cpp_engine(payload: dict, hardware: str, original_name: str) -> dict:
    engine_path = resolve_engine_path()
    work_input = make_artifact_path("job", original_name, ".json")
    work_output = make_artifact_path("result", original_name, ".json")

    with open(work_input, "w", encoding="utf-8") as file:
        json.dump({"hardware": hardware, "payload": payload}, file)

    if engine_path and engine_path.exists():
        subprocess.run([str(engine_path), str(work_input), str(work_output)], check=True)
    else:
        with open(work_output, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "status": "ok",
                    "message": "Engine placeholder executed",
                    "model": payload.get("model"),
                    "variant": "simple_linear" if payload.get("data_size", [0, 0])[1] <= 2 else "multilinear",
                    "hardware": hardware,
                    "rows": payload.get("data_size", [0, 0])[0],
                    "cols": payload.get("data_size", [0, 0])[1],
                    "rmse": 0.87,
                    "accuracy": 0.79,
                    "model_coefficients": [0.34, -0.12, 0.91],
                },
                file,
            )

    with open(work_output, "r", encoding="utf-8") as file:
        return json.load(file)


def build_feature_bundle(frame: pd.DataFrame, column_config: dict) -> dict:
    feature_columns = list(frame.columns[:-1])
    if not feature_columns:
        return {
            "matrix": np.empty((len(frame), 0)),
            "original_feature_names": [],
            "transformed_feature_names": [],
            "encoding_summary": [],
            "transformers": [],
            "input_schema": [],
        }

    transformed_columns: list[np.ndarray] = []
    transformed_feature_names: list[str] = []
    encoding_summary: list[dict] = []
    transformers: list[dict] = []
    input_schema: list[dict] = []

    for column_name in feature_columns:
        selected_type = str(column_config.get(column_name, {}).get("data_type", "")).lower()
        series = frame[column_name]

        if selected_type in {"int", "float"}:
            numeric = pd.to_numeric(series, errors="coerce")
            fill_value = float(numeric.dropna().median()) if numeric.notna().any() else 0.0
            transformed_columns.append(numeric.fillna(fill_value).to_numpy(dtype=float))
            transformed_feature_names.append(column_name)
            encoding_summary.append(
                {
                    "column": column_name,
                    "encoding": "double",
                    "details": "Numeric column used directly as double values.",
                }
            )
            transformers.append(
                {
                    "column": column_name,
                    "data_type": selected_type,
                    "encoding": "double",
                    "fill_value": fill_value,
                    "transformed_features": [column_name],
                }
            )
            input_schema.append(
                {
                    "name": column_name,
                    "data_type": selected_type,
                    "input_type": "number",
                    "placeholder": "Enter a double value",
                    "options": [],
                }
            )
            continue

        labels = series.map(to_clean_text).replace("", "missing")
        counts = labels.value_counts().to_dict()
        ordered_options = sorted(counts.keys(), key=lambda label: (-counts[label], label))
        sorted_categories = sorted(counts.keys())
        default_category = "missing" if "missing" in sorted_categories else ordered_options[0]

        if len(sorted_categories) <= 8:
            transformed_names_for_column = []
            for index, category in enumerate(sorted_categories):
                feature_name = f"{column_name}__{index}_{sanitize_name(category)}"
                transformed_columns.append((labels == category).astype(float).to_numpy())
                transformed_feature_names.append(feature_name)
                transformed_names_for_column.append(feature_name)

            encoding_summary.append(
                {
                    "column": column_name,
                    "encoding": "one_hot",
                    "details": f"Expanded into {len(sorted_categories)} binary columns.",
                }
            )
            transformers.append(
                {
                    "column": column_name,
                    "data_type": "string",
                    "encoding": "one_hot",
                    "categories": sorted_categories,
                    "default_category": default_category,
                    "transformed_features": transformed_names_for_column,
                }
            )
            input_schema.append(
                {
                    "name": column_name,
                    "data_type": "string",
                    "input_type": "select",
                    "placeholder": "Choose a category",
                    "options": ordered_options,
                }
            )
            continue

        mapping = {category: float(index) for index, category in enumerate(sorted_categories)}
        encoded = labels.map(mapping).fillna(mapping.get(default_category, 0.0)).to_numpy(dtype=float)
        transformed_name = f"{column_name}__label"
        transformed_columns.append(encoded)
        transformed_feature_names.append(transformed_name)
        encoding_summary.append(
            {
                "column": column_name,
                "encoding": "label",
                "details": f"Mapped {len(sorted_categories)} categories to numeric ids.",
            }
        )
        transformers.append(
            {
                "column": column_name,
                "data_type": "string",
                "encoding": "label",
                "mapping": mapping,
                "known_categories": ordered_options,
                "default_category": default_category,
                "default_value": float(mapping.get(default_category, 0.0)),
                "transformed_features": [transformed_name],
            }
        )
        input_schema.append(
            {
                "name": column_name,
                "data_type": "string",
                "input_type": "select" if len(ordered_options) <= 20 else "text",
                "placeholder": "Enter a category value",
                "options": ordered_options[:20],
            }
        )

    return {
        "matrix": np.column_stack(transformed_columns),
        "original_feature_names": feature_columns,
        "transformed_feature_names": transformed_feature_names,
        "encoding_summary": encoding_summary,
        "transformers": transformers,
        "input_schema": input_schema,
    }


def get_numeric_original_series(frame: pd.DataFrame, column_name: str) -> pd.Series:
    return pd.to_numeric(frame[column_name], errors="coerce")


def fit_linear_model(features: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    design = np.column_stack([np.ones(len(features)), features])
    coefficients, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
    predictions = design @ coefficients
    return coefficients, predictions


def fit_logistic_model(features: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    feature_means = features.mean(axis=0) if features.size else np.array([])
    feature_stds = features.std(axis=0) if features.size else np.array([])
    feature_stds = np.where(feature_stds == 0.0, 1.0, feature_stds)
    scaled_features = (features - feature_means) / feature_stds if features.size else features
    design = np.column_stack([np.ones(len(scaled_features)), scaled_features])

    weights = np.zeros(design.shape[1], dtype=float)
    learning_rate = 0.2
    for _ in range(3000):
        probabilities = sigmoid(design @ weights)
        gradient = (design.T @ (probabilities - target)) / len(target)
        weights -= learning_rate * gradient

    final_probabilities = sigmoid(design @ weights)
    return weights, final_probabilities, feature_means, feature_stds


def compute_roc_curve(target: np.ndarray, probabilities: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    thresholds = np.linspace(1.0, 0.0, 101)
    roc_points = []

    for threshold in thresholds:
        predictions = probabilities >= threshold
        true_positive = np.sum((predictions == 1) & (target == 1))
        false_positive = np.sum((predictions == 1) & (target == 0))
        true_negative = np.sum((predictions == 0) & (target == 0))
        false_negative = np.sum((predictions == 0) & (target == 1))

        tpr = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
        fpr = false_positive / (false_positive + true_negative) if (false_positive + true_negative) else 0.0
        roc_points.append((fpr, tpr))

    roc_frame = pd.DataFrame(roc_points, columns=["fpr", "tpr"]).drop_duplicates().sort_values(["fpr", "tpr"])
    auc = float(np.trapezoid(roc_frame["tpr"].to_numpy(), roc_frame["fpr"].to_numpy()))
    return roc_frame["fpr"].to_numpy(), roc_frame["tpr"].to_numpy(), auc


def compute_linear_metrics(target: np.ndarray, predictions: np.ndarray) -> dict:
    residuals = target - predictions
    mse = float(np.mean(residuals**2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(residuals)))
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((target - np.mean(target)) ** 2))
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot else 1.0

    return {
        "rmse": rmse,
        "mae": mae,
        "mse": mse,
        "r2": r2,
    }


def compute_logistic_metrics(target: np.ndarray, probabilities: np.ndarray, auc: float) -> dict:
    predictions = probabilities >= DEFAULT_THRESHOLD
    true_positive = int(np.sum((predictions == 1) & (target == 1)))
    false_positive = int(np.sum((predictions == 1) & (target == 0)))
    true_negative = int(np.sum((predictions == 0) & (target == 0)))
    false_negative = int(np.sum((predictions == 0) & (target == 1)))

    accuracy = float((true_positive + true_negative) / len(target)) if len(target) else 0.0
    precision = float(true_positive / (true_positive + false_positive)) if (true_positive + false_positive) else 0.0
    recall = float(true_positive / (true_positive + false_negative)) if (true_positive + false_negative) else 0.0
    f1 = float((2 * precision * recall) / (precision + recall)) if (precision + recall) else 0.0
    clipped_probabilities = np.clip(probabilities, 1e-9, 1 - 1e-9)
    log_loss = float(-np.mean(target * np.log(clipped_probabilities) + (1 - target) * np.log(1 - clipped_probabilities)))

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": auc,
        "log_loss": log_loss,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
    }


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


def create_linear_graphs(original_name: str, plot_context: dict) -> dict:
    plotly_path = make_artifact_path("plotly", original_name, ".html")
    plotly_figure = make_subplots(rows=1, cols=2, subplot_titles=(plot_context["title"], "Residual Plot"))
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["x_values"],
            y=plot_context["y_values"],
            mode="markers",
            name="Observed data",
            marker=dict(color="#2563eb", size=8, opacity=0.72),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["line_x"],
            y=plot_context["line_y"],
            mode="lines",
            name="Regression line",
            line=dict(color="#dc2626", width=3),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["residual_x"],
            y=plot_context["residual_y"],
            mode="markers",
            name="Residuals",
            marker=dict(color="#059669", size=8, opacity=0.72),
        ),
        row=1,
        col=2,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=[float(np.min(plot_context["residual_x"])), float(np.max(plot_context["residual_x"]))],
            y=[0, 0],
            mode="lines",
            name="Zero residual",
            line=dict(color="#94a3b8", dash="dash"),
        ),
        row=1,
        col=2,
    )
    plotly_figure.update_xaxes(title_text=plot_context["x_label"], row=1, col=1)
    plotly_figure.update_yaxes(title_text=plot_context["y_label"], row=1, col=1)
    plotly_figure.update_xaxes(title_text="Predicted / Feature", row=1, col=2)
    plotly_figure.update_yaxes(title_text="Residual", row=1, col=2)
    plotly_figure.update_layout(title="Linear Regression Graphs")
    plotly_figure.write_html(str(plotly_path), full_html=True)

    bokeh_path = make_artifact_path("bokeh", original_name, ".html")
    output_file(str(bokeh_path))
    main_figure = figure(title=plot_context["title"], width=980, height=360, x_axis_label=plot_context["x_label"], y_axis_label=plot_context["y_label"])
    main_figure.scatter(plot_context["x_values"], plot_context["y_values"], size=8, alpha=0.65, color="#2563eb")
    main_figure.line(plot_context["line_x"], plot_context["line_y"], line_width=3, color="#dc2626")

    residual_figure = figure(title="Residual Plot", width=980, height=320, x_axis_label="Predicted / Feature", y_axis_label="Residual")
    residual_figure.scatter(plot_context["residual_x"], plot_context["residual_y"], size=8, alpha=0.65, color="#059669")
    residual_figure.line(
        [float(np.min(plot_context["residual_x"])), float(np.max(plot_context["residual_x"]))],
        [0, 0],
        line_dash="dashed",
        color="#94a3b8",
    )
    save(bokeh_column(main_figure, residual_figure))

    return {
        "plotly": f"/static/artifacts/{plotly_path.name}",
        "bokeh": f"/static/artifacts/{bokeh_path.name}",
        "mode": "linear",
    }


def create_logistic_graphs(original_name: str, plot_context: dict) -> dict:
    plotly_path = make_artifact_path("plotly", original_name, ".html")
    plotly_figure = make_subplots(rows=1, cols=2, subplot_titles=(plot_context["title"], f"ROC Curve (AUC {plot_context['auc']:.3f})"))
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["actual_x"],
            y=plot_context["actual_y"],
            mode="markers",
            name="Actual class",
            marker=dict(color="#2563eb", size=8, opacity=0.72),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["curve_x"],
            y=plot_context["curve_y"],
            mode="lines",
            name="Predicted probability",
            line=dict(color="#dc2626", width=3),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["fpr"],
            y=plot_context["tpr"],
            mode="lines",
            name="ROC",
            line=dict(color="#059669", width=3),
        ),
        row=1,
        col=2,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="Baseline",
            line=dict(color="#94a3b8", dash="dash"),
        ),
        row=1,
        col=2,
    )
    plotly_figure.update_xaxes(title_text=plot_context["x_label"], row=1, col=1)
    plotly_figure.update_yaxes(title_text="Probability / Class", row=1, col=1)
    plotly_figure.update_xaxes(title_text="False Positive Rate", row=1, col=2)
    plotly_figure.update_yaxes(title_text="True Positive Rate", row=1, col=2)
    plotly_figure.update_layout(title="Logistic Regression Graphs")
    plotly_figure.write_html(str(plotly_path), full_html=True)

    bokeh_path = make_artifact_path("bokeh", original_name, ".html")
    output_file(str(bokeh_path))

    probability_figure = figure(title=plot_context["title"], width=980, height=360, x_axis_label=plot_context["x_label"], y_axis_label="Probability / Class")
    probability_figure.scatter(plot_context["actual_x"], plot_context["actual_y"], size=8, alpha=0.65, color="#2563eb")
    probability_figure.line(plot_context["curve_x"], plot_context["curve_y"], line_width=3, color="#dc2626")

    roc_source = ColumnDataSource({"fpr": plot_context["fpr"], "tpr": plot_context["tpr"]})
    roc_figure = figure(
        title=f"ROC Curve (AUC {plot_context['auc']:.3f})",
        width=980,
        height=320,
        x_axis_label="False Positive Rate",
        y_axis_label="True Positive Rate",
        x_range=(0, 1),
        y_range=(0, 1),
    )
    roc_figure.line("fpr", "tpr", source=roc_source, line_width=3, color="#059669")
    roc_figure.line([0, 1], [0, 1], line_dash="dashed", color="#94a3b8")
    save(bokeh_column(probability_figure, roc_figure))

    return {
        "plotly": f"/static/artifacts/{plotly_path.name}",
        "bokeh": f"/static/artifacts/{bokeh_path.name}",
        "mode": "logistic",
    }


def create_categorical_graphs(frame: pd.DataFrame, original_name: str) -> dict:
    if frame.empty:
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": "empty dataframe"}

    first_column = str(frame.columns[0])
    counts = frame[first_column].astype(str).fillna("NA").value_counts().head(25)
    if counts.empty:
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": "empty categorical counts"}

    category_frame = pd.DataFrame({"category": counts.index.tolist(), "count": counts.values.tolist()})

    plotly_path = make_artifact_path("plotly", original_name, ".html")
    plotly_figure = px.bar(category_frame, x="category", y="count", title=f"Category Distribution: {first_column}")
    plotly_figure.write_html(str(plotly_path), full_html=True)

    bokeh_path = make_artifact_path("bokeh", original_name, ".html")
    output_file(str(bokeh_path))
    source = ColumnDataSource(category_frame)
    bokeh_figure = figure(
        x_range=category_frame["category"].tolist(),
        title=f"Category Distribution: {first_column}",
        width=900,
        height=380,
    )
    bokeh_figure.vbar(x="category", top="count", width=0.8, source=source)
    bokeh_figure.xaxis.major_label_orientation = 1.0
    save(bokeh_figure)

    return {
        "plotly": f"/static/artifacts/{plotly_path.name}",
        "bokeh": f"/static/artifacts/{bokeh_path.name}",
        "mode": "categorical",
    }


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


@app.get("/health")
def health():
    return {"ok": True, "service": "python", "timestamp": time.time()}


@app.post("/schedule")
def schedule(payload: SchedulePayload):
    try:
        prepared_frame, prepared_path, target_mapping, target_info = prepare_training_frame(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    rows, cols = payload.data_size
    hardware = choose_hardware(rows, cols)

    engine_payload = payload.model_dump(by_alias=True)
    engine_payload["stored_file"] = prepared_path.name
    engine_payload["stored_path"] = str(prepared_path)

    cpp_result = invoke_cpp_engine(engine_payload, hardware, payload.file_name)
    analysis_bundle = build_analysis_bundle(prepared_frame, payload, target_info)
    feature_bundle = analysis_bundle["feature_bundle"]
    metrics_response = build_metric_response(payload, analysis_bundle, cpp_result, target_info)

    pickle_path = make_artifact_path("model", payload.file_name, ".pkl")
    with open(pickle_path, "wb") as file:
        pickle.dump(
            {
                "model": payload.model,
                "hardware": hardware,
                "target_mapping": target_mapping,
                "target_info": target_info,
                "feature_names": feature_bundle["original_feature_names"],
                "transformed_feature_names": feature_bundle["transformed_feature_names"],
                "transformers": feature_bundle["transformers"],
                "input_schema": feature_bundle["input_schema"],
                "encoding_summary": feature_bundle["encoding_summary"],
                "fallback_model": analysis_bundle["fallback_model"],
                "cpp_result": cpp_result,
            },
            file,
        )

    return {
        "status": "ok",
        "hardware": hardware,
        "cpp": cpp_result,
        "pickle_file": f"/static/artifacts/{pickle_path.name}",
        "plotly_html": analysis_bundle["graphs"]["plotly"],
        "bokeh_html": analysis_bundle["graphs"]["bokeh"],
        "graph_mode": analysis_bundle["graphs"].get("mode"),
        "graph_reason": analysis_bundle["graphs"].get("reason"),
        "target_mapping": target_mapping,
        "target_info": target_info,
        "encoding_summary": feature_bundle["encoding_summary"],
        "input_schema": feature_bundle["input_schema"],
        "metrics": metrics_response,
    }


@app.post("/predict")
def predict(request: PredictRequest):
    pickle_path = ARTIFACT_ROOT / Path(request.pickle_file).name
    if not pickle_path.exists():
        raise HTTPException(status_code=404, detail="Pickle file not found")

    with open(pickle_path, "rb") as file:
        saved_model = pickle.load(file)

    raw_inputs = normalize_raw_inputs(request)
    transformers = saved_model.get("transformers") or []
    transformed_feature_names = saved_model.get("transformed_feature_names") or []

    try:
        if raw_inputs:
            feature_vector = transform_prediction_inputs(raw_inputs, transformers)
        else:
            feature_vector = list(request.features or [])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if transformed_feature_names and len(feature_vector) != len(transformed_feature_names):
        raise HTTPException(
            status_code=400,
            detail=f"Prediction needs exactly {len(transformed_feature_names)} feature values after encoding.",
        )

    try:
        raw_prediction, prediction_source = compute_raw_score(saved_model, feature_vector)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    response = {
        "model": saved_model.get("model"),
        "hardware": saved_model.get("hardware"),
        "prediction": raw_prediction,
        "prediction_source": prediction_source,
    }

    if saved_model.get("model") == "logistic_regression":
        probability_class_one = float(sigmoid(np.array([raw_prediction]))[0])
        target_mapping = saved_model.get("target_mapping") or {}
        target_info = saved_model.get("target_info") or {}
        available_labels = target_info.get("labels") or list(target_mapping.keys())
        threshold = float(request.threshold if request.threshold is not None else DEFAULT_THRESHOLD)
        threshold = min(max(threshold, 0.0), 1.0)
        positive_label = request.positive_label or target_info.get("positive_label")

        if not positive_label:
            positive_label = next(
                (label for label in available_labels if float(target_mapping.get(label, 0.0)) == 1.0),
                available_labels[0] if available_labels else "1",
            )

        positive_numeric_value = float(target_mapping.get(positive_label, 1.0))
        positive_probability = probability_class_one if positive_numeric_value == 1.0 else 1.0 - probability_class_one
        negative_label = next((label for label in available_labels if label != positive_label), str(int(1 - positive_numeric_value)))
        predicted_label = positive_label if positive_probability >= threshold else negative_label

        response["prediction"] = positive_probability
        response["class_probability"] = positive_probability
        response["probability_class_one"] = probability_class_one
        response["threshold"] = threshold
        response["positive_label"] = positive_label
        response["predicted_label"] = predicted_label
        response["predicted_class"] = 1 if positive_probability >= threshold else 0
        response["available_labels"] = available_labels

    return response
