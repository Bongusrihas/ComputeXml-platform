import mongoose from "mongoose";

mongoose.set("bufferCommands", false);

const dbState = {
  connected: false,
  uri: null,
  lastError: null
};

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
  dbState.uri = normalizedUri;

  try {
    await mongoose.connect(normalizedUri, {
      dbName: "computex_ml",
      serverSelectionTimeoutMS: 5000
    });

    dbState.connected = true;
    dbState.lastError = null;

    console.log(`MongoDB connected: ${mongoose.connection.host}/${mongoose.connection.name}`);
    return true;
  } catch (error) {
    dbState.connected = false;
    dbState.lastError = error.message;

    console.warn(`MongoDB unavailable at startup: ${error.message}`);
    return false;
  }
}

export function getDbStatus() {
  return {
    connected: dbState.connected && mongoose.connection.readyState === 1,
    readyState: mongoose.connection.readyState,
    uri: dbState.uri,
    lastError: dbState.lastError,
    host: mongoose.connection.host || null,
    name: mongoose.connection.name || null
  };
}
