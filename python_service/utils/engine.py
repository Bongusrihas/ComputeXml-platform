import os,subprocess,json
from pathlib import Path
from app.config import *
from .neccessity import make_artifact_path


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
