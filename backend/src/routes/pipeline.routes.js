import fs from "fs";
import path from "path";
import { Router } from "express";
import multer from "multer";
import { authGuard } from "../middleware/auth.js";
import { HistoryRecord } from "../services/history.model.js";
import { callPythonPredict, callPythonService } from "../services/python.service.js";

const router = Router();
const uploadDir = path.resolve("static", "uploads");

if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

function sanitizeFileName(name) {
  return String(name || "dataset.csv")
    .replace(/[^a-zA-Z0-9._-]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase() || ".csv";
    const base = path.basename(file.originalname, ext);
    const safeBase = sanitizeFileName(base) || "dataset";
    cb(null, `${Date.now()}-${safeBase}${ext}`);
  }
});

const upload = multer({
  storage,
  fileFilter: (_req, file, cb) => {
    if (path.extname(file.originalname).toLowerCase() !== ".csv") {
      return cb(new Error("Only CSV files are allowed"));
    }
    cb(null, true);
  },
  limits: { fileSize: 50 * 1024 * 1024 }
});

function runUpload(req, res, next) {
  upload.single("file")(req, res, (error) => {
    if (!error) {
      return next();
    }

    if (error instanceof multer.MulterError && error.code === "LIMIT_FILE_SIZE") {
      return res.status(413).json({ error: "CSV file exceeds the 50MB upload limit" });
    }

    return res.status(400).json({ error: error.message || "File upload failed" });
  });
}

function extractServiceError(error, fallbackMessage) {
  return {
    status: error.response?.status || 500,
    message:
      error.response?.data?.detail ||
      error.response?.data?.error ||
      error.message ||
      fallbackMessage
  };
}

function removeStaticAsset(assetUrl) {
  if (!assetUrl || typeof assetUrl !== "string" || !assetUrl.startsWith("/static/")) {
    return;
  }

  const staticRoot = path.resolve("static");
  const relativeAssetPath = assetUrl.replace(/^\/static\//, "");
  const fullPath = path.resolve(staticRoot, relativeAssetPath);

  if (!fullPath.startsWith(staticRoot)) {
    return;
  }

  if (fs.existsSync(fullPath)) {
    fs.unlinkSync(fullPath);
  }
}

function removeHistoryAssets(history) {
  removeStaticAsset(history.csvUrl);
  removeStaticAsset(history.result?.plotly_html);
  removeStaticAsset(history.result?.bokeh_html);
  removeStaticAsset(history.result?.pickle_file);
}

function toHistoryResponse(record) {
  const history = record.toObject ? record.toObject() : record;
  return {
    id: String(history._id),
    userName: history.userName,
    originalFileName: history.originalFileName,
    storedFileName: history.storedFileName,
    csvUrl: history.csvUrl,
    rowCount: history.rowCount,
    columnCount: history.columnCount,
    modelType: history.modelType,
    columns: history.columns,
    globalOptions: history.globalOptions,
    result: history.result,
    createdAt: history.createdAt
  };
}

router.get("/history", authGuard, async (req, res) => {
  const records = await HistoryRecord.find({ userId: req.user.id }).sort({ createdAt: -1 }).lean();
  return res.json({ items: records.map(toHistoryResponse) });
});

router.delete("/history/:id", authGuard, async (req, res) => {
  const history = await HistoryRecord.findOne({ _id: req.params.id, userId: req.user.id });
  if (!history) {
    return res.status(404).json({ error: "History item not found" });
  }

  removeHistoryAssets(history);
  await history.deleteOne();
  return res.json({ ok: true, id: req.params.id });
});

router.post("/submit", authGuard, runUpload, async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "CSV file missing" });
    }

    if (!req.body.payload) {
      return res.status(400).json({ error: "Payload missing" });
    }

    let payload;
    try {
      payload = JSON.parse(req.body.payload);
    } catch {
      return res.status(400).json({ error: "Payload must be valid JSON" });
    }

    const finalPayload = {
      ...payload,
      uploaded_by: req.user.name,
      stored_file: req.file.filename,
      stored_path: req.file.path
    };

    const pythonResult = await callPythonService(finalPayload);
    const history = await HistoryRecord.create({
      userId: req.user.id,
      userName: req.user.name,
      originalFileName: req.file.originalname,
      storedFileName: req.file.filename,
      csvUrl: `/static/uploads/${req.file.filename}`,
      rowCount: payload.data_size?.[0] || 0,
      columnCount: payload.data_size?.[1] || 0,
      modelType: payload.model,
      columns: payload.columns,
      globalOptions: payload.global,
      result: pythonResult
    });

    return res.json({
      ok: true,
      history: toHistoryResponse(history)
    });
  } catch (error) {
    const serviceError = extractServiceError(error, "Submission failed");
    return res.status(serviceError.status).json({ error: serviceError.message });
  }
});

router.post("/predict", authGuard, async (req, res) => {
  try {
    const result = await callPythonPredict(req.body);
    return res.json(result);
  } catch (error) {
    const serviceError = extractServiceError(error, "Prediction failed");
    return res.status(serviceError.status).json({ error: serviceError.message });
  }
});

export default router;
