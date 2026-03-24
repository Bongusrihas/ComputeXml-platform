import numpy as np
import pandas as pd
from app.config import *
from .cleaner import to_clean_text,resolve_uploaded_csv,coerce_feature_column
from .neccessity import make_artifact_path
from .dao import SchedulePayload

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