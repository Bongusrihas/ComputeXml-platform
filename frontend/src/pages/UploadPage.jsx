import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Papa from "papaparse";
import api from "../lib/api";
import { countNulls, guessType } from "../lib/csvUtils";

const TYPE_OPTIONS = {
  int: ["int", "float", "string"],
  float: ["float", "int", "string"],
  string: ["string", "int", "float"]
};

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [csvRows, setCsvRows] = useState([]);
  const [columns, setColumns] = useState([]);
  const [parseProgress, setParseProgress] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState("");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [modelType, setModelType] = useState("linear_regression");

  const fallbackProgressTickerRef = useRef(null);
  const navigate = useNavigate();

  const [globalSettings, setGlobalSettings] = useState({
    fillNulls: "yes",
    numericFill: "mean",
    stringFill: "mode",
    removeNulls: "keep"
  });

  const tablePreview = useMemo(() => csvRows.slice(0, 5), [csvRows]);

  const effectiveProgress = useMemo(() => {
    if (submitting) return uploadProgress;
    return parseProgress;
  }, [submitting, uploadProgress, parseProgress]);

  const updateColumn = (index, patch) => {
    setColumns((prev) => prev.map((col, i) => (i === index ? { ...col, ...patch } : col)));
  };

  const stopFallbackTicker = () => {
    if (fallbackProgressTickerRef.current) {
      clearInterval(fallbackProgressTickerRef.current);
      fallbackProgressTickerRef.current = null;
    }
  };

  const parseFile = (selectedFile) => {
    setError("");
    setParseProgress(0);
    setUploadProgress(0);
    setProgressLabel("Parsing CSV...");

    const rows = [];
    let headers = [];

    Papa.parse(selectedFile, {
      header: true,
      skipEmptyLines: true,
      worker: true,
      step: (row) => {
        rows.push(row.data);
        if (!headers.length && row.meta.fields?.length) headers = row.meta.fields;
        if (row.meta.cursor && selectedFile.size > 0) {
          const pct = Math.min(100, Math.round((row.meta.cursor / selectedFile.size) * 100));
          setParseProgress(pct);
        }
      },
      complete: () => {
        const fields = headers.length ? headers : Object.keys(rows[0] || {});
        const metadata = fields.map((header) => {
          const values = rows.map((r) => r[header]);
          const inferred = guessType(values);
          return {
            name: header,
            inferredType: inferred,
            selectedType: inferred,
            role: "independent",
            nulls: countNulls(values)
          };
        });

        setCsvRows(rows);
        setColumns(metadata);
        setParseProgress(100);
        setProgressLabel("CSV ready");
      },
      error: (parseError) => {
        setError(`CSV parse failed: ${parseError?.message || "unknown error"}`);
        setParseProgress(0);
        setProgressLabel("");
      }
    });
  };

  const onFile = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setError("Only CSV files are allowed.");
      return;
    }
    setFile(selected);
    parseFile(selected);
  };

  const submit = async () => {
    if (!file || columns.length === 0) {
      setError("Upload and parse a CSV file first.");
      return;
    }

    const activeColumns = columns.filter((c) => c.role !== "remove");
    if (activeColumns.length < 2) {
      setError("Keep at least two columns (one independent and one dependent).");
      return;
    }

    const dependentCount = activeColumns.filter((c) => c.role === "dependent").length;
    if (dependentCount !== 1) {
      setError("Select exactly one dependent column among non-removed columns.");
      return;
    }

    const payload = {
      columns: columns.reduce((acc, col) => {
        acc[col.name] = {
          data_type: col.selectedType,
          type: col.role
        };
        return acc;
      }, {}),
      global: {
        nulls: globalSettings.fillNulls,
        fill: globalSettings.numericFill,
        remove_nulls: globalSettings.removeNulls,
        string_fill: globalSettings.stringFill
      },
      file_name: file.name,
      data_size: [csvRows.length, activeColumns.length],
      model: modelType
    };

    const formData = new FormData();
    formData.append("file", file);
    formData.append("payload", JSON.stringify(payload));

    setSubmitting(true);
    setUploadProgress(1);
    setProgressLabel("Uploading + training...");
    setError("");

    fallbackProgressTickerRef.current = setInterval(() => {
      setUploadProgress((prev) => Math.min(95, prev + 2));
    }, 500);

    try {
      const res = await api.post("/pipeline/submit", formData, {
        onUploadProgress: (evt) => {
          if (evt.total) {
            const p = Math.round((evt.loaded / evt.total) * 100);
            setUploadProgress(Math.max(10, p));
          }
        }
      });
      setUploadProgress(100);
      setProgressLabel("Completed");

      const resultsState = {
        submission: res.data,
        columns,
        modelType,
        fileName: file.name
      };
      sessionStorage.setItem("computex_results", JSON.stringify(resultsState));
      navigate("/results", { state: resultsState });
    } catch (err) {
      setError(err.response?.data?.error || "Submit failed.");
      setProgressLabel("");
    } finally {
      stopFallbackTicker();
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <div className="top-row">
          <div>
            <h2>Upload CSV</h2>
            <p className="note">All CSV metadata extraction happens in your browser.</p>
          </div>
          <div className="settings">
            <button type="button" className="secondary-btn" onClick={() => setIsSettingsOpen((s) => !s)}>
              Settings
            </button>
            {isSettingsOpen && (
              <div className="settings-panel grid">
                <label>
                  Fill nulls
                  <select value={globalSettings.fillNulls} onChange={(e) => setGlobalSettings((s) => ({ ...s, fillNulls: e.target.value }))}>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </label>
                <label>
                  Numeric fill (default mean)
                  <select value={globalSettings.numericFill} onChange={(e) => setGlobalSettings((s) => ({ ...s, numericFill: e.target.value }))}>
                    <option value="mean">Mean</option>
                    <option value="median">Median</option>
                  </select>
                </label>
                <label>
                  Null rows
                  <select value={globalSettings.removeNulls} onChange={(e) => setGlobalSettings((s) => ({ ...s, removeNulls: e.target.value }))}>
                    <option value="keep">Keep nulls</option>
                    <option value="remove">Remove null rows</option>
                  </select>
                </label>
                <label>
                  String fill
                  <select value={globalSettings.stringFill} disabled>
                    <option value="mode">Mode</option>
                  </select>
                </label>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-2">
          <label>
            Select CSV file
            <input type="file" accept=".csv" onChange={onFile} />
          </label>
          <div className="metrics-box">
            <p className="note" style={{ margin: 0 }}>
              Rows: <strong>{csvRows.length || 0}</strong> | Columns: <strong>{columns.length || 0}</strong>
            </p>
          </div>
        </div>

        {!!effectiveProgress && (
          <div style={{ marginTop: 12 }}>
            <div className="progress"><div style={{ width: `${effectiveProgress}%` }} /></div>
            <p className="note">{progressLabel} ({effectiveProgress}%)</p>
          </div>
        )}

        {tablePreview.length > 0 && (
          <>
            <h3 style={{ marginTop: 22 }}>First 5 Rows</h3>
            <div className="table-wrap">
              <table>
                <thead><tr>{Object.keys(tablePreview[0]).map((k) => <th key={k}>{k}</th>)}</tr></thead>
                <tbody>
                  {tablePreview.map((row, i) => (
                    <tr key={i}>
                      {Object.keys(tablePreview[0]).map((k) => <td key={`${i}-${k}`}>{String(row[k] ?? "")}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3>Column Info</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Detected Type</th>
                    <th>Nulls</th>
                    <th>Datatype (editable)</th>
                    <th>Role</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map((col, i) => (
                    <tr key={col.name}>
                      <td>{col.name}</td>
                      <td>{col.inferredType}</td>
                      <td>{col.nulls}</td>
                      <td>
                        <select value={col.selectedType} onChange={(e) => updateColumn(i, { selectedType: e.target.value })}>
                          {TYPE_OPTIONS[col.inferredType].map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                        </select>
                      </td>
                      <td>
                        <select value={col.role} onChange={(e) => updateColumn(i, { role: e.target.value })}>
                          <option value="independent">Independent</option>
                          <option value="dependent">Dependent</option>
                          <option value="remove">Remove</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="submit-block grid">
              <label>
                Model
                <select value={modelType} onChange={(e) => setModelType(e.target.value)}>
                  <option value="linear_regression">Linear Regression</option>
                  <option value="multilinear_regression">Multilinear Regression</option>
                  <option value="logistic_regression">Logistic Regression</option>
                </select>
              </label>
              <button disabled={submitting} type="button" onClick={submit}>{submitting ? "Submitting..." : "Submit"}</button>
            </div>
          </>
        )}

        {error && <p style={{ color: "#bf1f2f" }}>{error}</p>}
      </div>
    </div>
  );
}
