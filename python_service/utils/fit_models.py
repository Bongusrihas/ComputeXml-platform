import numpy as np
from .neccessity import sigmoid

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