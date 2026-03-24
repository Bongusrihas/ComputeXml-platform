import pickle,time
from pathlib import Path
import numpy as np
from fastapi import APIRouter, HTTPException
from app.config import *
from utils.dao import SchedulePayload,PredictRequest
from utils.engine import choose_hardware,invoke_cpp_engine
from utils.training_frame import prepare_training_frame
from utils.build_bundle import *
from utils.neccessity import make_artifact_path,sigmoid
from utils.normalize_tranform import *


router = APIRouter()
@router.get("/health")
def health():
    return {"ok": True, "service": "python", "timestamp": time.time()}


@router.post("/schedule")
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


@router.post("/predict")
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