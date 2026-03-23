import { Router } from "express";
import bcrypt from "bcryptjs";
import { authGuard, createAuthResponse, saveSession } from "../middleware/auth.js";
import { User } from "../services/user.model.js";

const router = Router();

function normalizeEmail(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeName(value) {
  return String(value || "").trim();
}

function validatePassword(value) {
  return String(value || "").trim();
}

router.post("/register", async (req, res) => {
  try {
    const name = normalizeName(req.body.name);
    const email = normalizeEmail(req.body.email);
    const password = validatePassword(req.body.password);

    if (!name || !email || !password) {
      return res.status(400).json({ error: "Name, email, and password are required" });
    }

    if (password.length < 6) {
      return res.status(400).json({ error: "Password must be at least 6 characters" });
    }

    const existingUser = await User.findOne({ email });
    if (existingUser) {
      return res.status(409).json({ error: "User already exists for this email" });
    }

    const passwordHash = await bcrypt.hash(password, 10);
    const user = await User.create({ name, email, passwordHash });
    const authResponse = createAuthResponse(user);
    saveSession(req, authResponse);

    return res.status(201).json(authResponse);
  } catch (error) {
    console.error("Register failed:", error.message);
    return res.status(500).json({ error: "Register failed. Check MongoDB connectivity." });
  }
});

router.post("/login", async (req, res) => {
  try {
    const email = normalizeEmail(req.body.email);
    const password = validatePassword(req.body.password);

    if (!email || !password) {
      return res.status(400).json({ error: "Email and password are required" });
    }

    const user = await User.findOne({ email });
    if (!user) {
      return res.status(401).json({ error: "Invalid email or password" });
    }

    const passwordMatches = await bcrypt.compare(password, user.passwordHash);
    if (!passwordMatches) {
      return res.status(401).json({ error: "Invalid email or password" });
    }

    const authResponse = createAuthResponse(user);
    saveSession(req, authResponse);

    return res.json(authResponse);
  } catch (error) {
    console.error("Login failed:", error.message);
    return res.status(500).json({ error: "Login failed. Check MongoDB connectivity." });
  }
});

router.get("/session", authGuard, async (req, res) => {
  return res.json({
    user: {
      id: req.user.id,
      name: req.user.name,
      email: req.user.email
    },
    expiresAt: req.user.expiresAt
  });
});

router.post("/logout", (req, res) => {
  req.session.destroy(() => {
    res.clearCookie("connect.sid");
    return res.json({ ok: true });
  });
});

export default router;
