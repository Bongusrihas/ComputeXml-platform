import numpy as np
import pandas as pd 
from .cleaner import to_clean_text,sanitize_name

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