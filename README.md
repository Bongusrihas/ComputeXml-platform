# Computex ML Platform

This project is a polished  full-stack machine learning pipeline for the final submission.

The browser handles CSV preview and schema selection. Node.js handles auth, uploads, static files, and MongoDB history. Python is the orchestrator for graph generation and artifact storage. C++ performs the actual regression computation on CPU or GPU.

The backend now binds on the network as well, so devices on the same Wi-Fi or LAN can open the app using the laptop IP and port.

## Final Architecture

`Browser (HTML/CSS/JS) -> Node.js/Express -> Python/FastAPI -> C++ Engine`

MongoDB stores:

- users
- sessions
- history

## Active Project Folders

Only these folders are part of the final active project flow:

- `frontend/public`
- `backend/src`
- `backend/static`
- `python_service/app`
- `cpp_engine/include`
- `cpp_engine/src`

## Main Idea

The main intention of this project is:

1. Load the CSV into RAM once on the native side.
2. Fill missing values while the data is already in memory.
3. Encode the selected columns.
4. Train the selected regression model.
5. Save the final result, graph files, and history so the run can be reopened later without recomputing.

The browser does not compute the model. The backend does not compute the model. Python orchestrates. C++ computes.

## Frontend

Active frontend files:

- `frontend/public/index.html`
- `frontend/public/styles.css`
- `frontend/public/app.js`
- `frontend/public/papaparse.min.js`

The frontend is plain HTML, CSS, and JavaScript.

### Frontend Responsibilities

- register and login
- store JWT in `localStorage`
- keep the session until logout
- parse CSV in the browser
- show row count and column count
- show the first 5 rows
- infer datatypes
- let the user choose datatype and role for each column
- choose `linear_regression` or `logistic_regression`
- show history on the same page
- reopen old results
- delete history
- run manual prediction using saved numeric and string feature inputs

### Scroll Handling

The first 5 rows table and the lower column-selection table now both use horizontal and vertical scrolling.

This was added so wide CSV files and tall column lists stay inside the centered panel instead of breaking the layout.

## Backend

Important backend files:

- `backend/src/server.js`
- `backend/src/routes/auth.routes.js`
- `backend/src/routes/pipeline.routes.js`
- `backend/src/middleware/auth.js`
- `backend/src/services/db.js`
- `backend/src/services/user.model.js`
- `backend/src/services/history.model.js`
- `backend/src/services/python.service.js`

### Backend Responsibilities

- serve the HTML/CSS/JS frontend
- serve `/static/uploads` and `/static/artifacts`
- register/login/logout/session APIs
- keep JWT plus session support
- store sessions in MongoDB
- upload CSV files
- send jobs to Python
- store finished history in MongoDB
- delete history and related local files

## Request Handling Architecture

The current local implementation is the direct version:

1. The browser sends the request to Node.js.
2. Node.js validates auth, stores the uploaded CSV, and forwards the payload to Python.
3. Python prepares the frame, launches the C++ engine, creates graphs, and returns the final result.
4. Node.js stores the returned result in MongoDB history and sends it back to the browser.

This is the version that runs now on your laptop.

### Intended Queue-Based Architecture

The intended scalable architecture for the same project is:

1. Node.js receives the browser request.
2. Node.js creates a unique `jobId`.
3. Node.js stores a MongoDB job/history record with status such as `queued`.
4. Node.js places the job into a queue.
5. One available Python worker picks the next queued job.
6. That Python worker launches one dedicated C++ worker process for that job.
7. The Python worker writes prepared CSV, result JSON, graph HTML, and pickle files using the same `jobId`.
8. The Python worker marks the job as completed with that same `jobId`.
9. Node.js reads the completed job and returns or exposes the correct result to the browser.

### How Multiple Python And C++ Workers Fit

- Multiple Python workers are the orchestration layer.
- Each Python worker handles one queued job at a time.
- Each active Python worker can launch one native C++ worker process for its current job.
- So if there are 4 Python workers, there can be up to 4 C++ jobs running in parallel, depending on CPU, RAM, and GPU limits.

In a deployed version, Python workers can be created by:

- running FastAPI/Uvicorn with multiple workers
- or running separate Python queue-consumer processes

The C++ workers are created per job by the Python worker that owns that job.

### How Node.js Knows Which Output Belongs To Which Request

Node.js should not guess based on worker number. It should match by `jobId`.

The matching flow is:

- Node.js creates a unique `jobId`
- Node.js stores that `jobId` in MongoDB
- Node.js sends the same `jobId` to Python
- Python uses the same `jobId` in prepared CSV, result JSON, graph, and pickle filenames
- Python reports completion using the same `jobId`
- Node.js updates the exact MongoDB record for that `jobId`

So even if multiple Python workers and multiple C++ worker processes run at the same time, the result belongs to the request whose `jobId` matches.

## Python Orchestrator

Important file:

- `python_service/app/main.py`

### Python Responsibilities

- read the uploaded CSV from backend static storage
- apply the selected independent/dependent/remove column roles
- keep the dependent column as the last column before native computation
- validate linear and logistic targets
- create Plotly and Bokeh graph files
- build saved input schemas for manual prediction
- save pickle artifacts in `backend/static/artifacts`
- call the C++ engine
- reopen saved models for prediction

### Manual Prediction

Manual prediction now supports:

- numeric inputs as doubles
- string inputs 

Python saves the feature encoding rules when the pipeline runs. During prediction it applies the same saved encoding rules again before scoring the model.

If the C++ coefficient count does not match the saved transformed feature count, Python falls back to the saved local analysis model so the prediction form still works.

## Graphs

### Linear Regression Graphs

Common linear-regression graphs are now generated:

- regression line plot
- residual plot

### Logistic Regression Graphs

Common logistic-regression graphs are now generated:

- probability curve
- ROC curve

Graph files are written to:

- `backend/static/artifacts`

and are saved in MongoDB history using URLs like:

- `/static/artifacts/plotly_...html`
- `/static/artifacts/bokeh_...html`

## Model-Specific Metrics

The project now uses different metrics for the two model types.

### Linear Regression Metrics

- RMSE
- MAE
- MSE
- R²

### Logistic Regression Metrics

- Accuracy
- Precision
- Recall
- F1
- ROC AUC
- Log Loss

Python returns these metrics to the frontend so the results panel shows model-appropriate values instead of one mixed strip for every model.

## C++ Engine

Important native source files:

- `cpp_engine/src/main.cpp`
- `cpp_engine/src/parser.cpp`
- `cpp_engine/src/metric_linear.cpp`
- `cpp_engine/src/metric_logistic.cpp`
- `cpp_engine/src/linear_open.cpp`
- `cpp_engine/src/linear_cublas.cu`
- `cpp_engine/src/logistic_open.cpp`
- `cpp_engine/src/logistic_cublas.cu`

Important headers:

- `cpp_engine/include/parser.hpp`
- `cpp_engine/include/metric_linear.hpp`
- `cpp_engine/include/metric_logistic.hpp`
- `cpp_engine/include/linear_open.hpp`
- `cpp_engine/include/linear_cublas.hpp`
- `cpp_engine/include/logistic_open.hpp`
- `cpp_engine/include/logistic_cublas.hpp`

### One-Time RAM Loading

The native flow is:

1. `parseCsvStream()` reads the CSV.
2. The rows stay in memory inside `RawTable`.
3. `fillNullsInPlace()` fills missing values in memory.
4. `toNumericDataset()` converts the in-memory table to `X` and `y`.
5. Training runs from that in-memory numeric dataset.

This keeps the intention of the project clear: load once, clean once, encode once, compute once.

### Missing Value Handling

Missing-value filling in `parser.cpp` is done row by row using only values already seen earlier in that column.

That means:

- if the 5th value is missing and the first 4 values are present, the replacement uses only the first 4
- after the replacement is inserted, that replacement becomes part of the running column state
- if the first numeric value is missing, it becomes `0`
- the same row-wise idea is used for mean, median, and mode filling

So the fill is not based on looking ahead at future rows.

### Encoding Logic

String features are encoded in the native parser using this rule:

- if unique values are `<= 7`, use one-hot encoding
- if unique values are `> 7`, use label encoding

This rule keeps small categorical columns interpretable while stopping large columns from exploding the matrix width.

### Numeric Type

The numeric pipeline uses `double` throughout the computation path.

## CPU And GPU Files

### Linear Regression

- CPU: `cpp_engine/src/linear_open.cpp`
- GPU: `cpp_engine/src/linear_cublas.cu`

Internally:

- one independent feature becomes `simple_linear`
- multiple independent features become `multilinear`

### Logistic Regression

- CPU: `cpp_engine/src/logistic_open.cpp`
- GPU: `cpp_engine/src/logistic_cublas.cu`

This path is binary logistic regression.

The logistic dependent column must have exactly two classes.

## Native Metrics Split

The native metrics are now separated into:

- `cpp_engine/src/metric_linear.cpp`
- `cpp_engine/src/metric_logistic.cpp`

These files hold the model-specific metric calculations and keep the training files easier to read.

## History

History is shown on the same upload page.

Each saved record stores:

- original file name
- saved CSV URL
- row count
- column count
- selected model
- selected columns
- null-handling options
- graph URLs
- pickle URL
- Python/C++ result data
- metrics
- timestamp

The same page can:

- reopen old runs
- open the saved CSV
- open the saved Plotly file
- open the saved Bokeh file
- delete the saved history

## Auth

The project uses both JWT and server-side sessions.

- login/register returns a JWT
- the backend also keeps an Express session in MongoDB
- the frontend stores the token in `localStorage`
- the session stays active until logout or backend expiry
- the old session countdown timer has been removed



##  Storage Layout

- `backend/static/uploads`
  uploaded CSV files
- `backend/static/artifacts`
  prepared CSV files
  Plotly HTML
  Bokeh HTML
  pickle files
  temporary engine JSON files

## Local Setup

### Root `.env`

The real runtime file is the repo-root `.env`.

The backend loads:

1. root `.env`
2. `backend/.env` only as fallback for missing values


```

### Backend

```bash
cd backend
npm install
node src/server.js
```

By default the backend listens on:

- `http://localhost:4000` on the laptop
- `http://<laptop-ip>:4000` for other devices on the same network

### Python

```bash
cd python_service
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### C++ Engine

Use a Visual Studio developer terminal.

Visual Studio path:

`C:\Program Files\Microsoft Visual Studio\18\Community`

Example build:

```bash
set OPENBLAS_ROOT=C:\path\to\OpenBLAS
cd cpp_engine
cmake -S . -B build -G "Visual Studio 18 2026" -A x64
cmake --build build --config Release
```

If your installed OpenBLAS is Win32, build the engine as Win32 or rebuild OpenBLAS for x64.



## Use From Another Device On The Same Network

1. Start MongoDB, Python, and the backend on the laptop.
2. Keep the backend host as `0.0.0.0` in the root `.env`, or just use the default.
3. In the backend terminal, note the printed LAN URL such as `http://ip:4000`.
4. On another phone, tablet, or laptop connected to the same Wi-Fi, open that URL in the browser.
5. If the device cannot connect, allow Node.js through Windows Firewall on the laptop.

## Test Note

The source-level backend tests were removed from the final submission to keep the project lean.

During development, route tests were useful for checking:

- invalid register input
- valid register response shape
- invalid login rejection
- valid login token response

For the final project repo, the running application code is kept and the separate test files/tooling are removed.

## File-By-File Flow

For a detailed walkthrough of the files, diagrams, request flow, intended queue model, and the role of each file, see [overview.md](overview.md).

## One-Line Explanation

This project is a  ML pipeline where the browser prepares the schema, Node.js manages auth and history, Python orchestrates artifacts and prediction schemas, and C++ performs the real regression computation from data that is loaded once into RAM and computed natively.
