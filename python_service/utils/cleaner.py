import numpy as np
import re
import pandas as pd
from app.config import *

def to_clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value).strip()

def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value or "artifact")
    return cleaned.strip("_") or "artifact"

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

def coerce_feature_column(series: pd.Series, selected_type: str | None) -> pd.Series:
    if selected_type in {"int", "float"}:
        return pd.to_numeric(series, errors="coerce")

    return series.map(to_clean_text)