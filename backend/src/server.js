import "dotenv/config";
import express from "express";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";
import rateLimit from "express-rate-limit";
import client from "prom-client";
import { connectDb } from "./services/db.js";
import authRoutes from "./routes/auth.routes.js";
import pipelineRoutes from "./routes/pipeline.routes.js";

const app = express();
const port = process.env.PORT || 4000;

await connectDb();

app.use(helmet());
app.use(cors());
app.use(express.json({ limit: "2mb" }));
app.use(morgan("tiny"));

const limiter = rateLimit({
  windowMs: Number(process.env.RATE_LIMIT_WINDOW_MS || 60000),
  max: Number(process.env.RATE_LIMIT_MAX || 100)
});
app.use(limiter);

client.collectDefaultMetrics();
const httpRequests = new client.Counter({
  name: "http_requests_total",
  help: "Total number of HTTP requests",
  labelNames: ["method", "route", "status"]
});

app.use((req, res, next) => {
  res.on("finish", () => {
    httpRequests.inc({
      method: req.method,
      route: req.path,
      status: String(res.statusCode)
    });
  });
  next();
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "backend", timestamp: new Date().toISOString() });
});

app.get("/metrics", async (_req, res) => {
  res.set("Content-Type", client.register.contentType);
  res.end(await client.register.metrics());
});

app.use("/auth", authRoutes);
app.use("/pipeline", pipelineRoutes);

app.listen(port, () => {
  console.log(`Backend listening on ${port}`);
});