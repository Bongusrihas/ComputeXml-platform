import fs from "fs";
import path from "path";
import { Router } from "express";
import multer from "multer";
import { authGuard } from "../middleware/auth.js";
import { callPythonPredict, callPythonService } from "../services/python.service.js";

const router = Router();
const outputDir = path.resolve("output");
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, outputDir),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    const unique = `${Date.now()}-${Math.floor(Math.random() * 1e6)}${ext}`;
    cb(null, unique);
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

router.post("/submit", authGuard, upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "CSV file missing" });
    }
    if (!req.body.payload) {
      return res.status(400).json({ error: "Payload missing" });
    }

    const payload = JSON.parse(req.body.payload);

    const finalPayload = {
      ...payload,
      uploaded_by: req.user?.name,
      stored_file: req.file.filename,
      stored_path: req.file.path
    };

    console.log("PIPELINE_PAYLOAD", JSON.stringify(finalPayload, null, 2));

    const pythonResult = await callPythonService(finalPayload);

    return res.json({
      ok: true,
      stored_file: req.file.filename,
      model_selected: payload.model,
      python: pythonResult
    });
  } catch (error) {
    return res.status(500).json({ error: error.message || "Submission failed" });
  }
});

router.post("/predict", authGuard, async (req, res) => {
  try {
    const result = await callPythonPredict(req.body);
    return res.json(result);
  } catch (error) {
    return res.status(500).json({ error: error.message || "Prediction failed" });
  }
});

export default router;
