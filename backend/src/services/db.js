import mongoose from "mongoose";

function normalizeMongoUri(rawUri) {
  const fallback = "mongodb://localhost:27017/computex_ml";
  if (!rawUri) return fallback;

  try {
    const url = new URL(rawUri);
    if (!url.pathname || url.pathname === "/") {
      url.pathname = "/computex_ml";
    }
    return url.toString();
  } catch {
    return fallback;
  }
}

export async function connectDb() {
  const normalizedUri = normalizeMongoUri(process.env.MONGO_URI);
  await mongoose.connect(normalizedUri, {
    dbName: "computex_ml",
    serverSelectionTimeoutMS: 5000
  });

  console.log(`MongoDB connected: ${mongoose.connection.host}/${mongoose.connection.name}`);
}
