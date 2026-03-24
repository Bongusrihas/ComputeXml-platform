import numpy as np
import pandas as pd
from app.config import *
from .cleaner import sanitize_name
import time

#paths
def make_artifact_path(prefix: str, original_name: str, suffix: str) -> Path:
    file_stem = sanitize_name(Path(original_name).stem)
    return ARTIFACT_ROOT / f"{prefix}_{file_stem}_{int(time.time() * 1000)}{suffix}"

def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -60.0, 60.0)))


def get_numeric_original_series(frame: pd.DataFrame, column_name: str) -> pd.Series:
    return pd.to_numeric(frame[column_name], errors="coerce")
