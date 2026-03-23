import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";
import express from "express";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";
import rateLimit from "express-rate-limit";
import session from "express-session";
import MongoStore from "connect-mongo";
import { SESSION_TTL_MS } from "./middleware/auth.js";
import { connectDb, getDbStatus } from "./services/db.js";
import authRoutes from "./routes/auth.routes.js";
import pipelineRoutes from "./routes/pipeline.routes.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "../../frontend/public");
const staticDir = path.resolve(__dirname, "../static");

dotenv.config({ path: path.resolve(__dirname, "../../.env") });
dotenv.config({ path: path.resolve(__dirname, "../.env"), override: false });

const app = express();
const port = process.env.PORT || 4000;
const mongoUri = process.env.MONGO_URI || "mongodb://localhost:27017/computex_ml";

if (!fs.existsSync(staticDir)) {
  fs.mkdirSync(staticDir, { recursive: true });
}

await connectDb();

app.use(helmet({ contentSecurityPolicy: false }));
app.use(cors({ credentials: true, origin: true }));
app.use(express.json({ limit: "5mb" }));
app.use(express.urlencoded({ extended: true }));
app.use(morgan("tiny"));

app.use(
  session({
    secret: process.env.JWT_SECRET || "change_me",
    resave: false,
    rolling: true,
    saveUninitialized: false,
    store: MongoStore.create({
      mongoUrl: mongoUri,
      dbName: "computex_ml",
      collectionName: "sessions"
    }),
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      maxAge: SESSION_TTL_MS
    }
  })
);

const limiter = rateLimit({
  windowMs: Number(process.env.RATE_LIMIT_WINDOW_MS || 60000),
  max: Number(process.env.RATE_LIMIT_MAX || 100)
});
app.use("/api", limiter);

app.use("/static", express.static(staticDir));

app.get("/health", (_req, res) => {
  const db = getDbStatus();
  return res.status(db.connected ? 200 : 503).json({
    ok: db.connected,
    service: "backend",
    timestamp: new Date().toISOString(),
    db
  });
});

app.use("/api/auth", authRoutes);
app.use("/api/pipeline", pipelineRoutes);

app.use(express.static(frontendDir));
app.get("*", (_req, res) => {
  res.sendFile(path.join(frontendDir, "index.html"));
});

app.listen(port, () => {
  console.log(`Backend listening on http://localhost:${port}`);
});
