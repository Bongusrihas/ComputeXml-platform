import numpy as np
import pandas as pd
from app.config import *


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