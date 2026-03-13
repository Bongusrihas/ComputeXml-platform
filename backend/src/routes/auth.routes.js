import { Router } from "express";
import jwt from "jsonwebtoken";
import { LoginAuth } from "../services/login.model.js";

const router = Router();

router.post("/login", async (req, res) => {
  try {
    const { name } = req.body;
    if (!name || !String(name).trim()) {
      return res.status(400).json({ error: "Name is required" });
    }

    const cleanName = String(name).trim();
    const token = jwt.sign(
      { name: cleanName, scope: "user" },
      process.env.JWT_SECRET || "change_me",
      { expiresIn: "12h" }
    );

    const record = await LoginAuth.create({
      name: cleanName,
      token,
      ip: req.ip,
      userAgent: req.get("user-agent")
    });

    return res.json({ name: cleanName, token, login_id: record._id });
  } catch (error) {
    console.error("Login failed:", error.message);
    return res.status(500).json({ error: "Login save failed. Check MongoDB connectivity." });
  }
});

export default router;
