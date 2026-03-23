import express from "express";
import request from "supertest";
import { beforeEach, describe, expect, it, vi } from "vitest";

const findOneMock = vi.fn();
const createMock = vi.fn();
const hashMock = vi.fn(() => Promise.resolve("hashed-password"));
const compareMock = vi.fn();

vi.mock("../src/services/user.model.js", () => ({
  User: {
    findOne: findOneMock,
    create: createMock
  }
}));

vi.mock("bcryptjs", () => ({
  default: {
    hash: hashMock,
    compare: compareMock
  }
}));

const { default: authRoutes } = await import("../src/routes/auth.routes.js");

function makeApp() {
  const app = express();
  app.use(express.json());
  app.use((req, _res, next) => {
    req.session = {};
    req.session.destroy = (callback) => callback();
    next();
  });
  app.use("/auth", authRoutes);
  return app;
}

describe("auth routes", () => {
  beforeEach(() => {
    findOneMock.mockReset();
    createMock.mockReset();
    compareMock.mockReset();
    hashMock.mockClear();
  });

  it("rejects incomplete register payloads", async () => {
    const app = makeApp();
    const res = await request(app).post("/auth/register").send({ name: "Srihas" });

    expect(res.status).toBe(400);
    expect(res.body.error).toContain("required");
  });

  it("creates a user during register", async () => {
    findOneMock.mockResolvedValue(null);
    createMock.mockResolvedValue({
      _id: "user-1",
      name: "Srihas",
      email: "srihas@example.com"
    });

    const app = makeApp();
    const res = await request(app).post("/auth/register").send({
      name: "Srihas",
      email: "srihas@example.com",
      password: "secret12"
    });

    expect(res.status).toBe(201);
    expect(res.body.user.name).toBe("Srihas");
    expect(res.body.user.email).toBe("srihas@example.com");
    expect(res.body.token).toBeTruthy();
    expect(createMock).toHaveBeenCalledTimes(1);
  });

  it("rejects bad login credentials", async () => {
    findOneMock.mockResolvedValue({
      _id: "user-1",
      name: "Srihas",
      email: "srihas@example.com",
      passwordHash: "hashed-password"
    });
    compareMock.mockResolvedValue(false);

    const app = makeApp();
    const res = await request(app).post("/auth/login").send({
      email: "srihas@example.com",
      password: "wrongpass"
    });

    expect(res.status).toBe(401);
    expect(res.body.error).toContain("Invalid");
  });

  it("returns auth payload on login", async () => {
    findOneMock.mockResolvedValue({
      _id: "user-1",
      name: "Srihas",
      email: "srihas@example.com",
      passwordHash: "hashed-password"
    });
    compareMock.mockResolvedValue(true);

    const app = makeApp();
    const res = await request(app).post("/auth/login").send({
      email: "srihas@example.com",
      password: "secret12"
    });

    expect(res.status).toBe(200);
    expect(res.body.user.name).toBe("Srihas");
    expect(res.body.token).toBeTruthy();
    expect(res.body.expiresAt).toBeTruthy();
  });
});
