import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api from "../lib/api";

function getSavedResultState() {
  const raw = sessionStorage.getItem("computex_results");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export default function ResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state || getSavedResultState();

  const [featureMap, setFeatureMap] = useState({});
  const [prediction, setPrediction] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submission = state?.submission;

  const independentCols = useMemo(() => {
    const cols = state?.columns || [];
    return cols.filter((c) => c.role === "independent");
  }, [state?.columns]);

  if (!submission) {
    return (
      <div className="page">
        <div className="card" style={{ maxWidth: 720 }}>
          <h2>No result context</h2>
          <p className="note">Please upload and submit a dataset first.</p>
          <button type="button" onClick={() => navigate("/upload")}>Go To Upload</button>
        </div>
      </div>
    );
  }

  const runPrediction = async () => {
    if (!submission?.python?.pickle_file) {
      setError("Pickle file missing from model output.");
      return;
    }

    const features = independentCols.map((col) => {
      const value = featureMap[col.name];
      const num = Number(value);
      return Number.isFinite(num) ? num : 0;
    });

    setLoading(true);
    setError("");
    setPrediction(null);

    try {
      const res = await api.post("/pipeline/predict", {
        pickle_file: submission.python.pickle_file,
        features
      });
      setPrediction(res.data);
    } catch (err) {
      setError(err.response?.data?.error || "Prediction failed.");
    } finally {
      setLoading(false);
    }
  };

  const resolvedModel = submission.model_selected || submission.python?.cpp?.model || "linear_regression";

  return (
    <div className="page">
      <div className="card">
        <div className="top-row">
          <div>
            <h2>Training Results</h2>
            <p className="note">Model: {resolvedModel} | File: {state?.fileName || "n/a"}</p>
          </div>
          <button type="button" className="secondary-btn" onClick={() => navigate("/upload")}>Back To Upload</button>
        </div>

        <div className="result-meta grid grid-2">
          <div className="meta-card"><strong>Status:</strong> {submission.python?.status || "unknown"}</div>
          <div className="meta-card"><strong>Hardware:</strong> {submission.python?.hardware || "n/a"}</div>
        </div>

        <h3 style={{ marginTop: 16 }}>Graphs</h3>
        {!submission.python?.plotly_html && !submission.python?.bokeh_html && (
          <p className="note">No graphs were generated. This happens when no numeric columns are found.</p>
        )}

        {submission.python?.plotly_html && (
          <div className="graph-card">
            <iframe title="plotly" src={submission.python.plotly_html} style={{ width: "100%", height: 430, border: "none" }} />
          </div>
        )}

        {submission.python?.bokeh_html && (
          <div className="graph-card" style={{ marginTop: 10 }}>
            <iframe title="bokeh" src={submission.python.bokeh_html} style={{ width: "100%", height: 430, border: "none" }} />
          </div>
        )}

        <h3 style={{ marginTop: 18 }}>Prediction Input</h3>
        <p className="note">Fill each independent feature value, then submit prediction.</p>

        <div className="grid grid-2">
          {independentCols.map((col) => (
            <label key={col.name}>
              {col.name}
              <input
                value={featureMap[col.name] || ""}
                onChange={(e) => setFeatureMap((prev) => ({ ...prev, [col.name]: e.target.value }))}
                placeholder={`Enter ${col.selectedType} value`}
              />
            </label>
          ))}
        </div>

        <div style={{ marginTop: 12 }}>
          <button type="button" onClick={runPrediction} disabled={loading}>
            {loading ? "Predicting..." : "Submit Prediction"}
          </button>
        </div>

        {error && <p style={{ color: "#bf1f2f" }}>{error}</p>}

        {prediction && (
          <div className="prediction-box">
            <h3 style={{ marginBottom: 6 }}>Prediction Result</h3>
            <p className="note" style={{ margin: 0 }}>
              Prediction: <strong>{String(prediction.prediction)}</strong>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
