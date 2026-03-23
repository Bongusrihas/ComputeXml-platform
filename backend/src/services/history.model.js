import mongoose from "mongoose";

const historySchema = new mongoose.Schema(
  {
    userId: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true, index: true },
    userName: { type: String, required: true },
    originalFileName: { type: String, required: true },
    storedFileName: { type: String, required: true },
    csvUrl: { type: String, required: true },
    rowCount: { type: Number, required: true },
    columnCount: { type: Number, required: true },
    modelType: { type: String, required: true },
    columns: { type: mongoose.Schema.Types.Mixed, required: true },
    globalOptions: { type: mongoose.Schema.Types.Mixed, required: true },
    result: { type: mongoose.Schema.Types.Mixed, required: true },
    createdAt: { type: Date, default: Date.now }
  },
  {
    collection: "history"
  }
);

export const HistoryRecord = mongoose.model("HistoryRecord", historySchema);
