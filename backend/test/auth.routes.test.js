import express from "express";
import request from "supertest";
import { beforeEach, describe, expect, it, vi } from "vitest";

const createMock = vi.fn();

vi.mock("../src/services/login.model.js", () => ({
  LoginAuth: {
    create: createMock
  }
}));

vi.mock("jsonwebtoken", () => ({
  default: {
    sign: vi.fn(() => "test-token")
  }
}));

const { default: authRoutes } = await import("../src/routes/auth.routes.js");

function makeApp() {
  const app = express();
  app.use(express.json());
  app.use("/auth", authRoutes);
  return app;
}

describe("auth login route", () => {
  beforeEach(() => {
    createMock.mockReset();
  });

  it("returns 400 for missing name", async () => {
    const app = makeApp();
    const res = await request(app).post("/auth/login").send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe("Name is required");
  });

  it("creates mongo login record and returns token", async () => {
    createMock.mockResolvedValue({ _id: "abc123" });
    const app = makeApp();

    const res = await request(app)
      .post("/auth/login")
      .set("User-Agent", "vitest")
      .send({ name: "Srihas" });

    expect(res.status).toBe(200);
    expect(res.body.token).toBe("test-token");
    expect(res.body.login_id).toBe("abc123");
    expect(createMock).toHaveBeenCalledTimes(1);
  });

  it("returns 500 when mongo write fails", async () => {
    createMock.mockRejectedValue(new Error("db down"));
    const app = makeApp();

    const res = await request(app).post("/auth/login").send({ name: "Srihas" });

    expect(res.status).toBe(500);
    expect(res.body.error).toContain("Login save failed");
  });
});
