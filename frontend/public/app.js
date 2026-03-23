const TYPE_OPTIONS = {
  int: ["int", "float", "string"],
  float: ["float", "int", "string"],
  string: ["string", "int", "float"]
};

const STORAGE_KEY = "computex_auth";
const DEFAULT_LOGISTIC_THRESHOLD = 0.5;

const state = {
  token: "",
  user: null,
  file: null,
  csvRows: [],
  columns: [],
  history: [],
  currentHistory: null
};

const refs = {
  authView: document.getElementById("auth-view"),
  appView: document.getElementById("app-view"),
  authError: document.getElementById("auth-error"),
  uploadError: document.getElementById("upload-error"),
  registerForm: document.getElementById("register-form"),
  loginForm: document.getElementById("login-form"),
  registerTab: document.getElementById("show-register"),
  loginTab: document.getElementById("show-login"),
  sessionBar: document.getElementById("session-bar"),
  sessionUser: document.getElementById("session-user"),
  logoutBtn: document.getElementById("logout-btn"),
  fileInput: document.getElementById("file-input"),
  rowCount: document.getElementById("row-count"),
  columnCount: document.getElementById("column-count"),
  fillNulls: document.getElementById("fill-nulls"),
  numericFill: document.getElementById("numeric-fill"),
  removeNulls: document.getElementById("remove-nulls"),
  stringFill: document.getElementById("string-fill"),
  modelSelect: document.getElementById("model-select"),
  progressWrap: document.getElementById("progress-wrap"),
  progressBar: document.getElementById("progress-bar"),
  progressText: document.getElementById("progress-text"),
  previewWrap: document.getElementById("preview-wrap"),
  previewTable: document.getElementById("preview-table"),
  columnsTable: document.getElementById("columns-table"),
  submitBtn: document.getElementById("submit-btn"),
  historyList: document.getElementById("history-list"),
  resultView: document.getElementById("result-view")
};

function safeJsonParse(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function showMessage(node, message) {
  if (!message) {
    node.textContent = "";
    node.classList.add("hidden");
    return;
  }

  node.textContent = message;
  node.classList.remove("hidden");
}

function setProgress(value, text) {
  if (!value && !text) {
    refs.progressWrap.classList.add("hidden");
    refs.progressBar.style.width = "0%";
    refs.progressText.textContent = "";
    return;
  }

  refs.progressWrap.classList.remove("hidden");
  refs.progressBar.style.width = `${value}%`;
  refs.progressText.textContent = `${text} (${value}%)`;
}

async function apiFetch(url, options = {}) {
  const config = {
    method: options.method || "GET",
    credentials: "include",
    headers: { ...(options.headers || {}) }
  };

  if (state.token) {
    config.headers.Authorization = `Bearer ${state.token}`;
  }

  if (options.body instanceof FormData) {
    config.body = options.body;
  } else if (options.body !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, config);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    throw new Error(data.error || data.detail || data || "Request failed");
  }

  return data;
}

function guessType(values) {
  const present = values.filter((value) => value !== "" && value !== null && value !== undefined);
  if (!present.length) return "string";

  const isInt = present.every((value) => /^-?\d+$/.test(String(value).trim()));
  if (isInt) return "int";

  const isFloat = present.every((value) => /^-?\d+(\.\d+)?$/.test(String(value).trim()));
  if (isFloat) return "float";

  return "string";
}

function countNulls(values) {
  return values.filter((value) => value === "" || value === null || value === undefined).length;
}

function normalizeCellValue(value, selectedType) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";

  if (selectedType === "int" || selectedType === "float") {
    const numericValue = Number(raw);
    return Number.isFinite(numericValue) ? String(numericValue) : raw;
  }

  return raw;
}

function setAuthState(payload) {
  state.user = payload.user;
  state.token = payload.token || state.token || "";

  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      token: state.token
    })
  );

  refs.authView.classList.add("hidden");
  refs.appView.classList.remove("hidden");
  refs.sessionBar.classList.remove("hidden");
  refs.sessionUser.textContent = `${state.user.name} (${state.user.email})`;
  resetWorkspaceState();
  loadHistory();
}

function resetWorkspaceState() {
  state.file = null;
  state.csvRows = [];
  state.columns = [];
  state.history = [];
  state.currentHistory = null;

  refs.fileInput.value = "";
  refs.registerForm.reset();
  refs.loginForm.reset();
  updateCounts();
  renderPreviewTable();
  setProgress(0, "");
  showMessage(refs.authError, "");
  showMessage(refs.uploadError, "");
  refs.historyList.innerHTML = '<p class="muted">No history yet. Submit a CSV to create the first entry.</p>';
  refs.resultView.innerHTML = '<p class="muted">Pick a history item or submit a new CSV to see the graphs and prediction section.</p>';
}

function clearAuthState() {
  state.user = null;
  state.token = "";

  localStorage.removeItem(STORAGE_KEY);
  resetWorkspaceState();
  refs.authView.classList.remove("hidden");
  refs.appView.classList.add("hidden");
  refs.sessionBar.classList.add("hidden");
}

async function restoreSession() {
  const saved = safeJsonParse(localStorage.getItem(STORAGE_KEY)) || {};
  state.token = saved.token || "";

  try {
    const session = await apiFetch("/api/auth/session");
    setAuthState({
      user: session.user,
      token: state.token
    });
  } catch {
    clearAuthState();
  }
}

function switchAuthTab(tabName) {
  const isRegister = tabName === "register";
  refs.registerTab.classList.toggle("active", isRegister);
  refs.loginTab.classList.toggle("active", !isRegister);
  refs.registerForm.classList.toggle("hidden", !isRegister);
  refs.loginForm.classList.toggle("hidden", isRegister);
  showMessage(refs.authError, "");
}

async function handleRegister(event) {
  event.preventDefault();
  showMessage(refs.authError, "");

  try {
    const payload = await apiFetch("/api/auth/register", {
      method: "POST",
      body: {
        name: document.getElementById("register-name").value,
        email: document.getElementById("register-email").value,
        password: document.getElementById("register-password").value
      }
    });
    refs.registerForm.reset();
    setAuthState(payload);
  } catch (error) {
    showMessage(refs.authError, error.message);
  }
}

async function handleLogin(event) {
  event.preventDefault();
  showMessage(refs.authError, "");

  try {
    const payload = await apiFetch("/api/auth/login", {
      method: "POST",
      body: {
        email: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value
      }
    });
    refs.loginForm.reset();
    setAuthState(payload);
  } catch (error) {
    showMessage(refs.authError, error.message);
  }
}

async function handleLogout() {
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } catch {
    // Ignore logout cleanup failures.
  }

  clearAuthState();
}

function renderPreviewTable() {
  if (!state.csvRows.length) {
    refs.previewWrap.classList.add("hidden");
    refs.previewTable.innerHTML = "";
    refs.columnsTable.innerHTML = "";
    return;
  }

  const previewRows = state.csvRows.slice(0, 5);
  const headers = Object.keys(previewRows[0] || {});

  refs.previewTable.innerHTML = `
    <thead>
      <tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>
    </thead>
    <tbody>
      ${previewRows
        .map(
          (row) =>
            `<tr>${headers
              .map((header) => `<td>${escapeHtml(row[header] ?? "")}</td>`)
              .join("")}</tr>`
        )
        .join("")}
    </tbody>
  `;

  refs.columnsTable.innerHTML = `
    <thead>
      <tr>
        <th>Column</th>
        <th>Detected Type</th>
        <th>Nulls</th>
        <th>Selected Type</th>
        <th>Role</th>
      </tr>
    </thead>
    <tbody>
      ${state.columns
        .map((column, index) => {
          const typeOptions = TYPE_OPTIONS[column.selectedType] || TYPE_OPTIONS[column.inferredType] || TYPE_OPTIONS.string;
          return `
            <tr>
              <td>${escapeHtml(column.name)}</td>
              <td>${escapeHtml(column.inferredType)}</td>
              <td>${column.nulls}</td>
              <td>
                <select class="column-type-select" data-index="${index}">
                  ${typeOptions
                    .map(
                      (option) =>
                        `<option value="${option}" ${option === column.selectedType ? "selected" : ""}>${option}</option>`
                    )
                    .join("")}
                </select>
              </td>
              <td>
                <select class="column-role-select" data-index="${index}">
                  <option value="independent" ${column.role === "independent" ? "selected" : ""}>Independent</option>
                  <option value="dependent" ${column.role === "dependent" ? "selected" : ""}>Dependent</option>
                  <option value="remove" ${column.role === "remove" ? "selected" : ""}>Remove</option>
                </select>
              </td>
            </tr>
          `;
        })
        .join("")}
    </tbody>
  `;

  refs.previewWrap.classList.remove("hidden");
}

function handleColumnsTableChange(event) {
  const index = Number(event.target.dataset.index);
  if (!Number.isInteger(index)) return;

  if (event.target.classList.contains("column-type-select")) {
    state.columns[index].selectedType = event.target.value;
    return;
  }

  if (event.target.classList.contains("column-role-select")) {
    const nextRole = event.target.value;
    if (nextRole === "dependent") {
      state.columns = state.columns.map((column, columnIndex) => {
        if (columnIndex === index) return { ...column, role: "dependent" };
        if (column.role === "dependent") return { ...column, role: "independent" };
        return column;
      });
      renderPreviewTable();
      return;
    }

    state.columns[index].role = nextRole;
  }
}

function updateCounts() {
  refs.rowCount.textContent = String(state.csvRows.length);
  refs.columnCount.textContent = String(state.columns.length);
}

function buildColumns(rows, headers) {
  return headers.map((header, index) => {
    const values = rows.map((row) => row[header]);
    const inferredType = guessType(values);
    return {
      name: header,
      inferredType,
      selectedType: inferredType,
      role: index === headers.length - 1 ? "dependent" : "independent",
      nulls: countNulls(values)
    };
  });
}

function parseCsvFile(file) {
  showMessage(refs.uploadError, "");
  setProgress(1, "Parsing CSV");

  const rows = [];
  let headers = [];

  Papa.parse(file, {
    header: true,
    skipEmptyLines: true,
    worker: true,
    step: (stepRow) => {
      rows.push(stepRow.data);
      if (!headers.length && stepRow.meta.fields?.length) {
        headers = stepRow.meta.fields;
      }

      if (stepRow.meta.cursor && file.size > 0) {
        const percent = Math.min(100, Math.round((stepRow.meta.cursor / file.size) * 100));
        setProgress(percent, "Parsing CSV");
      }
    },
    complete: () => {
      const finalHeaders = headers.length ? headers : Object.keys(rows[0] || {});
      state.csvRows = rows;
      state.columns = buildColumns(rows, finalHeaders);
      updateCounts();
      renderPreviewTable();
      setProgress(100, "CSV ready");
    },
    error: (error) => {
      state.csvRows = [];
      state.columns = [];
      updateCounts();
      renderPreviewTable();
      setProgress(0, "");
      showMessage(refs.uploadError, `CSV parse failed: ${error.message || "unknown error"}`);
    }
  });
}

function getDependentColumn() {
  return state.columns.find((column) => column.role === "dependent") || null;
}

function getTargetClassSummary() {
  const dependentColumn = getDependentColumn();
  if (!dependentColumn) return null;

  const frequencies = new Map();
  for (const row of state.csvRows) {
    const normalizedValue = normalizeCellValue(row[dependentColumn.name], dependentColumn.selectedType);
    if (!normalizedValue) continue;
    frequencies.set(normalizedValue, (frequencies.get(normalizedValue) || 0) + 1);
  }

  const labels = [...frequencies.keys()];
  return {
    name: dependentColumn.name,
    labels,
    frequencies: Object.fromEntries(frequencies.entries()),
    uniqueCount: labels.length
  };
}

function buildLogisticConfig() {
  const summary = getTargetClassSummary();
  if (!summary || summary.uniqueCount !== 2) {
    const message =
      summary?.uniqueCount > 2
        ? `Logistic regression needs exactly 2 classes in "${summary.name}". This column currently has ${summary.uniqueCount} unique values.`
        : `Logistic regression needs exactly 2 classes in the dependent column before the pipeline can run.`;
    window.alert(message);
    throw new Error(message);
  }

  const sortedByFrequency = [...summary.labels].sort((left, right) => {
    const rightCount = summary.frequencies[right] || 0;
    const leftCount = summary.frequencies[left] || 0;
    if (rightCount !== leftCount) {
      return rightCount - leftCount;
    }
    return left.localeCompare(right);
  });

  return {
    class_labels: summary.labels,
    class_frequency: summary.frequencies,
    positive_label: sortedByFrequency[0],
    default_threshold: DEFAULT_LOGISTIC_THRESHOLD
  };
}

function getPayload() {
  const activeColumns = state.columns.filter((column) => column.role !== "remove");
  const dependentColumns = activeColumns.filter((column) => column.role === "dependent");

  if (!state.file || !state.csvRows.length || !state.columns.length) {
    throw new Error("Upload and parse a CSV file first.");
  }

  if (activeColumns.length < 2) {
    throw new Error("Keep at least one independent column and one dependent column.");
  }

  if (dependentColumns.length !== 1) {
    throw new Error("Choose exactly one dependent column.");
  }

  const payload = {
    columns: state.columns.reduce((result, column) => {
      result[column.name] = {
        data_type: column.selectedType,
        type: column.role
      };
      return result;
    }, {}),
    global: {
      nulls: refs.fillNulls.value,
      fill: refs.numericFill.value,
      remove_nulls: refs.removeNulls.value,
      string_fill: refs.stringFill.value
    },
    file_name: state.file.name,
    data_size: [state.csvRows.length, activeColumns.length],
    model: refs.modelSelect.value
  };

  if (refs.modelSelect.value === "logistic_regression") {
    payload.logistic = buildLogisticConfig();
  }

  return payload;
}

async function submitPipeline() {
  showMessage(refs.uploadError, "");

  try {
    const payload = getPayload();
    const formData = new FormData();
    formData.append("file", state.file);
    formData.append("payload", JSON.stringify(payload));

    refs.submitBtn.disabled = true;
    setProgress(10, "Uploading and running pipeline");

    const result = await apiFetch("/api/pipeline/submit", {
      method: "POST",
      body: formData
    });

    setProgress(100, "Completed");
    refs.submitBtn.disabled = false;

    state.history.unshift(result.history);
    state.currentHistory = result.history;
    renderHistory();
    renderResultView();
  } catch (error) {
    refs.submitBtn.disabled = false;
    setProgress(0, "");
    showMessage(refs.uploadError, error.message);
  }
}

async function loadHistory() {
  try {
    const response = await apiFetch("/api/pipeline/history");
    state.history = response.items || [];
    renderHistory();
    renderResultView();
  } catch (error) {
    refs.historyList.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

async function deleteHistoryItem(historyId) {
  const selected = state.history.find((item) => item.id === historyId);
  if (!selected) {
    return;
  }

  const confirmed = window.confirm(`Delete the saved history for "${selected.originalFileName}"?`);
  if (!confirmed) {
    return;
  }

  try {
    await apiFetch(`/api/pipeline/history/${historyId}`, { method: "DELETE" });
    state.history = state.history.filter((item) => item.id !== historyId);

    if (state.currentHistory?.id === historyId) {
      state.currentHistory = state.history[0] || null;
    }

    renderHistory();
    renderResultView();
  } catch (error) {
    showMessage(refs.uploadError, error.message);
  }
}

function renderHistory() {
  if (!state.history.length) {
    refs.historyList.innerHTML = '<p class="muted">No history yet. Submit a CSV to create the first entry.</p>';
    return;
  }

  refs.historyList.innerHTML = state.history
    .map(
      (item) => `
        <div class="history-card">
          <div class="history-card-head">
            <div>
              <h3>${escapeHtml(item.originalFileName)}</h3>
              <p class="muted">${escapeHtml(new Date(item.createdAt).toLocaleString())}</p>
            </div>
            <div class="history-actions">
              <button class="history-btn" type="button" data-history-action="open" data-history-id="${escapeHtml(item.id)}">Open</button>
              <button class="history-btn" type="button" data-history-action="delete" data-history-id="${escapeHtml(item.id)}">Delete</button>
            </div>
          </div>
          <div class="history-meta">
            <span>Model: ${escapeHtml(item.modelType)}</span>
            <span>Rows: ${escapeHtml(item.rowCount)}</span>
            <span>Columns: ${escapeHtml(item.columnCount)}</span>
            <span>Hardware: ${escapeHtml(item.result?.hardware || "n/a")}</span>
          </div>
          <div class="history-meta">
            <a href="${escapeHtml(item.csvUrl)}" target="_blank" rel="noreferrer">Open CSV</a>
            ${item.result?.plotly_html ? `<a href="${escapeHtml(item.result.plotly_html)}" target="_blank" rel="noreferrer">Open Plotly</a>` : ""}
            ${item.result?.bokeh_html ? `<a href="${escapeHtml(item.result.bokeh_html)}" target="_blank" rel="noreferrer">Open Bokeh</a>` : ""}
          </div>
        </div>
      `
    )
    .join("");
}

function getIndependentColumns(historyItem) {
  return Object.entries(historyItem.columns || {})
    .filter(([, value]) => value.type === "independent")
    .map(([name, value]) => ({ name, ...value }));
}

function getPredictionSchema(historyItem) {
  const storedSchema = historyItem.result?.input_schema;
  if (Array.isArray(storedSchema) && storedSchema.length) {
    return storedSchema;
  }

  return getIndependentColumns(historyItem).map((column) => ({
    name: column.name,
    data_type: column.data_type,
    input_type: ["int", "float"].includes(String(column.data_type || "").toLowerCase()) ? "number" : "text",
    placeholder: ["int", "float"].includes(String(column.data_type || "").toLowerCase())
      ? "Enter a double value"
      : "Enter a category value",
    options: []
  }));
}

function resolveLogisticInfo(historyItem) {
  const result = historyItem.result || {};
  const targetInfo = result.target_info || {};
  const targetMapping = result.target_mapping || targetInfo.target_mapping || {};
  const labels = targetInfo.labels || Object.keys(targetMapping);
  const positiveLabel =
    targetInfo.positive_label ||
    labels.find((label) => Number(targetMapping[label]) === 1) ||
    labels[0] ||
    "";

  return {
    labels,
    classFrequency: targetInfo.class_frequency || {},
    positiveLabel,
    defaultThreshold: targetInfo.default_threshold ?? DEFAULT_LOGISTIC_THRESHOLD
  };
}

function formatMetricValue(value) {
  if (value === undefined || value === null || value === "") {
    return "n/a";
  }

  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  return numericValue.toFixed(4);
}

function renderMetricStrip(historyItem) {
  const metrics = historyItem.result?.metrics;
  const cpp = historyItem.result?.cpp || {};

  if (metrics?.metric_order?.length) {
    return metrics.metric_order
      .map((metricName) => {
        const label = metricName.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
        return `<span><strong>${escapeHtml(label)}:</strong> ${escapeHtml(formatMetricValue(metrics.values?.[metricName]))}</span>`;
      })
      .join("");
  }

  if (historyItem.modelType === "logistic_regression") {
    return `<span><strong>Accuracy:</strong> ${escapeHtml(formatMetricValue(cpp.accuracy))}</span>`;
  }

  return `<span><strong>RMSE:</strong> ${escapeHtml(formatMetricValue(cpp.rmse))}</span>`;
}

function renderPredictionField(field, value) {
  const safeName = escapeHtml(field.name);
  const safeValue = escapeHtml(value ?? "");
  const inputType = String(field.input_type || "").toLowerCase();

  if (inputType === "select" && Array.isArray(field.options) && field.options.length) {
    return `
      <label class="prediction-field">
        <span class="prediction-field-name">${safeName}</span>
        <select class="prediction-input" data-feature-name="${safeName}">
          <option value="">Choose</option>
          ${field.options
            .map(
              (option) => `
                <option value="${escapeHtml(option)}" ${option === value ? "selected" : ""}>${escapeHtml(option)}</option>
              `
            )
            .join("")}
        </select>
      </label>
    `;
  }

  if (inputType === "number") {
    return `
      <label class="prediction-field">
        <span class="prediction-field-name">${safeName}</span>
        <input
          class="prediction-input"
          data-feature-name="${safeName}"
          type="number"
          step="any"
          inputmode="decimal"
          placeholder="${escapeHtml(field.placeholder || "Enter a double value")}"
          value="${safeValue}"
        />
      </label>
    `;
  }

  return `
    <label class="prediction-field">
      <span class="prediction-field-name">${safeName}</span>
      <input
        class="prediction-input"
        data-feature-name="${safeName}"
        type="text"
        placeholder="${escapeHtml(field.placeholder || "Enter a category value")}"
        value="${safeValue}"
      />
    </label>
  `;
}

function getCurrentPredictionFormState() {
  const values = {};
  document.querySelectorAll(".prediction-input").forEach((input) => {
    values[input.dataset.featureName] = input.value;
  });

  return {
    values,
    threshold: document.getElementById("logistic-threshold")?.value || "",
    positiveLabel: document.getElementById("positive-label")?.value || ""
  };
}

function renderPredictionSummary(prediction) {
  if (!prediction) return "";

  if (prediction.model === "logistic_regression") {
    return `
      <div class="meta-strip">
        <span><strong>Prediction:</strong> <span class="prediction-summary-value">${escapeHtml(prediction.predicted_label || "n/a")}</span></span>
        <span><strong>Probability:</strong> <span class="prediction-summary-value">${escapeHtml(Number(prediction.class_probability || 0).toFixed(4))}</span></span>
        <span><strong>Threshold:</strong> <span class="prediction-summary-value">${escapeHtml(prediction.threshold ?? DEFAULT_LOGISTIC_THRESHOLD)}</span></span>
        <span><strong>Positive Label:</strong> <span class="prediction-summary-value">${escapeHtml(prediction.positive_label || "n/a")}</span></span>
      </div>
    `;
  }

  return `
    <div class="meta-strip">
      <span><strong>Prediction:</strong> <span class="prediction-summary-value">${escapeHtml(prediction.prediction ?? "n/a")}</span></span>
    </div>
  `;
}

function renderResultView(prediction = null, predictionError = "", formState = null) {
  if (!state.currentHistory) {
    refs.resultView.innerHTML =
      '<p class="muted">Pick a history item or submit a new CSV to see the graphs and prediction section.</p>';
    return;
  }

  const item = state.currentHistory;
  const predictionSchema = getPredictionSchema(item);
  const isLogistic = item.modelType === "logistic_regression";
  const logisticInfo = resolveLogisticInfo(item);
  const activeFormState = formState || {
    values: {},
    threshold: String(logisticInfo.defaultThreshold),
    positiveLabel: logisticInfo.positiveLabel
  };
  const graphFrames = [
    item.result?.plotly_html
      ? `<div class="graph-frame"><iframe src="${escapeHtml(item.result.plotly_html)}" title="Plotly graph"></iframe></div>`
      : "",
    item.result?.bokeh_html
      ? `<div class="graph-frame"><iframe src="${escapeHtml(item.result.bokeh_html)}" title="Bokeh graph"></iframe></div>`
      : ""
  ]
    .filter(Boolean)
    .join("");

  const classSummary =
    isLogistic && logisticInfo.labels.length
      ? `<p class="muted prediction-note">Dependent classes: ${logisticInfo.labels
          .map((label) => `${escapeHtml(label)} (${escapeHtml(logisticInfo.classFrequency[label] ?? 0)})`)
          .join(", ")}</p>`
      : "";

  const inputGrid =
    predictionSchema.length
      ? `
        <div class="prediction-scroll">
          <div class="prediction-grid">
            ${predictionSchema
              .map((field) => renderPredictionField(field, activeFormState.values?.[field.name] ?? ""))
              .join("")}
          </div>
        </div>
      `
      : '<p class="muted">Prediction fields will appear here when a saved run is selected.</p>';

  const logisticControls =
    isLogistic && predictionSchema.length
      ? `
        <div class="prediction-grid">
          <label class="prediction-field">
            <span class="prediction-field-name">Threshold</span>
            <input
              id="logistic-threshold"
              type="number"
              step="0.01"
              min="0"
              max="1"
              value="${escapeHtml(activeFormState.threshold || String(logisticInfo.defaultThreshold))}"
            />
          </label>
          <label class="prediction-field">
            <span class="prediction-field-name">Positive Label</span>
            <select id="positive-label">
              ${logisticInfo.labels
                .map(
                  (label) => `
                    <option value="${escapeHtml(label)}" ${
                      label === (activeFormState.positiveLabel || logisticInfo.positiveLabel) ? "selected" : ""
                    }>
                      ${escapeHtml(label)}
                    </option>
                  `
                )
                .join("")}
            </select>
          </label>
        </div>
      `
      : "";

  refs.resultView.innerHTML = `
    <div class="meta-strip">
      <span><strong>File:</strong> ${escapeHtml(item.originalFileName)}</span>
      <span><strong>Model:</strong> ${escapeHtml(item.modelType)}</span>
      <span><strong>Hardware:</strong> ${escapeHtml(item.result?.hardware || "n/a")}</span>
      ${renderMetricStrip(item)}
    </div>

    ${graphFrames ? `<div class="graph-grid">${graphFrames}</div>` : '<p class="muted">Graphs were not generated for this run.</p>'}

    <div class="prediction-box">
      <h3>Prediction</h3>
      <p class="muted">Enter the saved independent-column values and call the stored model. Numeric fields use doubles, and string fields use the saved category encoding.</p>
      ${classSummary}
      ${inputGrid}
      ${logisticControls}
      <div class="action-row">
        <button id="predict-btn" type="button" ${!predictionSchema.length ? "disabled" : ""}>
          Run Prediction
        </button>
      </div>
      ${predictionError ? `<p class="error">${escapeHtml(predictionError)}</p>` : ""}
      ${renderPredictionSummary(prediction)}
    </div>
  `;

  const predictButton = document.getElementById("predict-btn");
  if (predictButton) {
    predictButton.addEventListener("click", runPrediction);
  }
}

async function runPrediction() {
  const item = state.currentHistory;
  const currentFormState = getCurrentPredictionFormState();
  const predictionSchema = getPredictionSchema(item);

  if (!item?.result?.pickle_file) {
    renderResultView(null, "Pickle file is missing for this history item.", currentFormState);
    return;
  }

  const inputs = [...document.querySelectorAll(".prediction-input")];
  if (!inputs.length || inputs.length !== predictionSchema.length) {
    renderResultView(null, "Prediction inputs are not ready for this history item.", currentFormState);
    return;
  }

  const inputMap = new Map(inputs.map((node) => [node.dataset.featureName, node]));
  const rawInputs = {};
  for (const field of predictionSchema) {
    const input = inputMap.get(field.name);
    const rawValue = input?.value?.trim() || "";
    currentFormState.values[field.name] = rawValue;

    if (!rawValue) {
      renderResultView(null, `Enter a value for ${field.name}.`, currentFormState);
      return;
    }

    if (String(field.input_type || "").toLowerCase() === "number") {
      const numericValue = Number(rawValue);
      if (!Number.isFinite(numericValue)) {
        renderResultView(null, `Only numeric double values are allowed for ${field.name}.`, currentFormState);
        return;
      }
      rawInputs[field.name] = numericValue;
    } else {
      rawInputs[field.name] = rawValue;
    }
  }

  const requestBody = {
    pickle_file: item.result.pickle_file,
    inputs: rawInputs
  };

  if (item.modelType === "logistic_regression") {
    const thresholdInput = document.getElementById("logistic-threshold");
    const positiveLabelSelect = document.getElementById("positive-label");
    const thresholdValue = Number(thresholdInput?.value ?? DEFAULT_LOGISTIC_THRESHOLD);

    if (!Number.isFinite(thresholdValue) || thresholdValue < 0 || thresholdValue > 1) {
      renderResultView(null, "Threshold must be a number between 0 and 1.", currentFormState);
      return;
    }

    requestBody.threshold = thresholdValue;
    requestBody.positive_label = positiveLabelSelect?.value || resolveLogisticInfo(item).positiveLabel;
    currentFormState.threshold = String(thresholdValue);
    currentFormState.positiveLabel = requestBody.positive_label;
  }

  try {
    const prediction = await apiFetch("/api/pipeline/predict", {
      method: "POST",
      body: requestBody
    });

    renderResultView(prediction, "", currentFormState);
  } catch (error) {
    renderResultView(null, error.message, currentFormState);
  }
}

refs.registerTab.addEventListener("click", () => switchAuthTab("register"));
refs.loginTab.addEventListener("click", () => switchAuthTab("login"));
refs.registerForm.addEventListener("submit", handleRegister);
refs.loginForm.addEventListener("submit", handleLogin);
refs.logoutBtn.addEventListener("click", handleLogout);
refs.fileInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  if (!file.name.toLowerCase().endsWith(".csv")) {
    showMessage(refs.uploadError, "Only CSV files are allowed.");
    return;
  }

  state.file = file;
  parseCsvFile(file);
});
refs.columnsTable.addEventListener("change", handleColumnsTableChange);
refs.submitBtn.addEventListener("click", submitPipeline);
refs.historyList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-history-id]");
  if (!button) return;

  if (button.dataset.historyAction === "delete") {
    deleteHistoryItem(button.dataset.historyId);
    return;
  }

  const selected = state.history.find((item) => item.id === button.dataset.historyId);
  if (!selected) return;
  state.currentHistory = selected;
  renderResultView();
});

switchAuthTab("login");
restoreSession();
