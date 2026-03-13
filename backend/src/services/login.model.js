import mongoose from "mongoose";

const loginSchema = new mongoose.Schema(
  {
    name: { type: String, required: true },
    token: { type: String, required: true },
    createdAt: { type: Date, default: Date.now },
    ip: { type: String },
    userAgent: { type: String }
  },
  {
    collection: "login_auth"
  }
);

export const LoginAuth = mongoose.model("LoginAuth", loginSchema);