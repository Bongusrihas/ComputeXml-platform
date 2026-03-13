# Computex ML Platform

Full-stack scalable pipeline:

- Frontend (React): browser-side CSV parsing + schema editing + model config
- Backend (Node.js + Express): JWT auth, MongoDB login logging, file storage/routing
- Orchestrator (Python + FastAPI): hardware scheduling, C++ execution, graphs, prediction
- Engine (C++): stream-style CSV processing, null handling, encoding, BLAS/CUDA model training
- Ops: Docker Compose, Nginx reverse proxy, Prometheus metrics, Grafana dashboard

## Architecture

`Frontend -> Node/Express -> Python scheduler -> C++ engine`

- No CSV computation in backend. Backend only routes, auths, stores file, forwards payload.
- CSV preprocessing is done in frontend and sent as metadata.
- C++ does parsing/fill/encoding/model steps in memory.

## Key Implementations

- Login page stores `name + JWT token` in MongoDB `computex_ml.login_auth`.
- Frontend uploader accepts only CSV and does first 5 rows preview + datatype/role edits + global null settings.
- Submit payload shape matches your required contract.
- Backend stores uploaded file with unique name in `backend/output/` and only routes to Python.
- Python selects CPU/GPU by data size (`<256x30 => CPU else GPU`), runs C++, creates Plotly/Bokeh artifacts, stores pickle model, supports prediction.
- Observability and reliability: JWT, rate limiting, circuit breaker, health checks, Prometheus, Grafana, Nginx.

## C++ Engine

- Parser library is now directly integrated from [vincentlaucsb/csv-parser](https://github.com/vincentlaucsb/csv-parser) via CMake `FetchContent`.
- `cpp_engine/src/parser.cpp` performs:
  - null handling (mean/median/mode) in a running single pass style
  - row drop/keep null mode
  - string encoding rule (unique > 7 => label encoding, else one-hot)
- `cpp_engine/src/openblas_models.cpp` uses real OpenBLAS/CBLAS (`cblas_dgemv`) for training loops.
- `cpp_engine/src/cublas_models.cpp` uses real cuBLAS (`cublasDgemv`) when CUDA toolkit is available.

## Build Notes (BLAS/CUDA)

- `cpp_engine/CMakeLists.txt` links:
  - required `BLAS::BLAS`
  - optional `CUDA::cublas` + `CUDA::cudart` when CUDA toolkit is detected
- If CUDA is unavailable, GPU training path automatically falls back to CPU in `main.cpp`.
- Docker GPU execution additionally requires NVIDIA Container Toolkit and compose GPU device mapping.

## Run with Docker Compose

1. Create `.env` in repo root:

```bash
JWT_SECRET=replace_with_secure_secret
```

2. Start stack:

```bash
docker compose up --build
```

3. Open:

- App: `http://localhost`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

## Local Dev

### Backend

```bash
cd backend
npm install
npm run dev
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Python service

```bash
cd python_service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### C++ engine

```bash
cd cpp_engine
cmake -S . -B build
cmake --build build --config Release
```

## Security/Scale Target

- JWT auth
- Rate limiting
- Circuit breaker
- Health checks
- Prometheus + Grafana dashboards
- Nginx reverse proxy
- Designed to support ~50 concurrent users with stateless web/API services and isolated compute worker stage
