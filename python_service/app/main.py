import json
import os
import pickle
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, output_file, save
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from plotly import express as px
from pydantic import BaseModel, ConfigDict, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = FastAPI(title="Computex Python Orchestrator")

REQUESTS = Counter("python_requests_total", "Total python service requests", ["route"])
LATENCY = Histogram("python_request_latency_seconds", "Request latency", ["route"])

BUSY_STATE = {"cpu": False, "gpu": False}

ARTIFACT_DIR = Path("/app/artifacts")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACT_DIR)), name="artifacts")


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
    features: list[float]


@app.get("/health")
def health():
    REQUESTS.labels(route="health").inc()
    return {"ok": True, "service": "python", "timestamp": time.time()}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def choose_hardware(rows: int, cols: int):
    requested = "cpu" if rows < 256 and cols < 30 else "gpu"
    if not BUSY_STATE[requested]:
        return requested

    alternate = "gpu" if requested == "cpu" else "cpu"
    if not BUSY_STATE[alternate]:
        return alternate

    return requested


def invoke_cpp_engine(payload: dict, hardware: str):
    engine_path = os.environ.get("CPLUS_ENGINE_PATH", "/app/cpp_engine/build/engine")

    work_input = ARTIFACT_DIR / f"job_{int(time.time()*1000)}.json"
    work_output = ARTIFACT_DIR / f"out_{int(time.time()*1000)}.json"

    with open(work_input, "w", encoding="utf-8") as f:
        json.dump({"hardware": hardware, "payload": payload}, f)

    if Path(engine_path).exists():
        subprocess.run([engine_path, str(work_input), str(work_output)], check=True)
    else:
        with open(work_output, "w", encoding="utf-8") as fw:
            json.dump(
                {
                    "status": "ok",
                    "message": "Engine placeholder executed",
                    "model_coefficients": [0.34, -0.12, 0.91],
                    "rmse": 0.87,
                    "accuracy": 0.79,
                },
                fw,
            )

    with open(work_output, "r", encoding="utf-8") as f:
        return json.load(f)


def create_numeric_graphs(df: pd.DataFrame):
    numeric_df = pd.DataFrame()
    for col in df.columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        if coerced.notna().sum() > 0:
            numeric_df[col] = coerced

    numeric_cols = list(numeric_df.columns)
    if not numeric_cols:
        return None

    x = numeric_cols[0]
    y = numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0]
    graph_df = numeric_df[[x, y]].dropna().head(500)
    if graph_df.empty:
        return None

    plotly_path = ARTIFACT_DIR / f"plotly_{int(time.time()*1000)}.html"
    fig = px.scatter(graph_df, x=x, y=y, title="Computex ML: Numeric Preview")
    fig.write_html(str(plotly_path), full_html=True)

    bokeh_path = ARTIFACT_DIR / f"bokeh_{int(time.time()*1000)}.html"
    output_file(str(bokeh_path))
    p = figure(title="Computex ML Bokeh View", width=900, height=380)
    p.line(np.arange(len(graph_df)), graph_df[y].fillna(0), line_width=2)
    save(p)

    return {
        "plotly": f"/artifacts/{plotly_path.name}",
        "bokeh": f"/artifacts/{bokeh_path.name}",
        "mode": "numeric",
    }


def create_categorical_graphs(df: pd.DataFrame):
    if df.empty:
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": "empty dataframe"}

    first_col = str(df.columns[0])
    counts = df[first_col].astype(str).fillna("NA").value_counts().head(25)
    if counts.empty:
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": "empty categorical counts"}

    cat_df = pd.DataFrame({"category": counts.index.tolist(), "count": counts.values.tolist()})

    plotly_path = ARTIFACT_DIR / f"plotly_{int(time.time()*1000)}.html"
    fig = px.bar(cat_df, x="category", y="count", title=f"Category Distribution: {first_col}")
    fig.write_html(str(plotly_path), full_html=True)

    bokeh_path = ARTIFACT_DIR / f"bokeh_{int(time.time()*1000)}.html"
    output_file(str(bokeh_path))
    source = ColumnDataSource(cat_df)
    p = figure(x_range=cat_df["category"].tolist(), title=f"Category Distribution: {first_col}", width=900, height=380)
    p.vbar(x="category", top="count", width=0.8, source=source)
    p.xaxis.major_label_orientation = 1.0
    save(p)

    return {
        "plotly": f"/artifacts/{plotly_path.name}",
        "bokeh": f"/artifacts/{bokeh_path.name}",
        "mode": "categorical",
    }


def create_graphs(stored_csv: str):
    csv_path = Path("/app/input_output") / stored_csv
    if not csv_path.exists():
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": f"csv not found: {csv_path}"}

    df = pd.read_csv(csv_path)
    if df.empty:
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": "csv empty"}

    numeric_graphs = create_numeric_graphs(df)
    if numeric_graphs:
        return numeric_graphs

    return create_categorical_graphs(df)


@app.post("/schedule")
def schedule(payload: SchedulePayload):
    REQUESTS.labels(route="schedule").inc()

    with LATENCY.labels(route="schedule").time():
        print(f"[SCHEDULE] file={payload.stored_file} model={payload.model} size={payload.data_size}")
        rows, cols = payload.data_size
        hardware = choose_hardware(rows, cols)
        BUSY_STATE[hardware] = True

        try:
            cpp_result = invoke_cpp_engine(payload.model_dump(by_alias=True), hardware)

            model_path = ARTIFACT_DIR / f"model_{int(time.time()*1000)}.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(
                    {
                        "model": payload.model,
                        "hardware": hardware,
                        "cpp_result": cpp_result,
                    },
                    f,
                )

            graphs = create_graphs(payload.stored_file)
            print(f"[GRAPH] mode={graphs.get('mode')} plotly={graphs.get('plotly')} bokeh={graphs.get('bokeh')} reason={graphs.get('reason')}")

            return {
                "status": "ok",
                "hardware": hardware,
                "cpp": cpp_result,
                "pickle_file": f"/artifacts/{model_path.name}",
                "plotly_html": graphs["plotly"],
                "bokeh_html": graphs["bokeh"],
                "graph_mode": graphs.get("mode"),
                "graph_reason": graphs.get("reason"),
            }
        finally:
            BUSY_STATE[hardware] = False


@app.post("/predict")
def predict(req: PredictRequest):
    REQUESTS.labels(route="predict").inc()

    pkl_name = Path(req.pickle_file).name
    pkl_path = ARTIFACT_DIR / pkl_name

    if not pkl_path.exists():
        return {"error": "Pickle file not found"}

    with open(pkl_path, "rb") as f:
        model = pickle.load(f)

    coeffs = model.get("cpp_result", {}).get("model_coefficients", [0.0])

    features = list(req.features)
    if len(coeffs) == len(features) + 1:
        prediction = float(coeffs[0] + sum(c * x for c, x in zip(coeffs[1:], features)))
    else:
        features = features[: len(coeffs)]
        while len(features) < len(coeffs):
            features.append(0.0)
        prediction = float(sum(c * x for c, x in zip(coeffs, features)))

    if model.get("model") == "logistic_regression":
        prediction = float(1.0 / (1.0 + np.exp(-prediction)))

    return {
        "model": model.get("model"),
        "hardware": model.get("hardware"),
        "prediction": prediction,
    }
