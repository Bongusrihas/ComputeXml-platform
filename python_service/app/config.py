from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = REPO_ROOT / "backend" / "static"
UPLOAD_ROOT = STATIC_ROOT / "uploads"
ARTIFACT_ROOT = STATIC_ROOT / "artifacts"
DEFAULT_THRESHOLD = 0.5

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)