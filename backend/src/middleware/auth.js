import jwt from "jsonwebtoken";

export const SESSION_TTL_MS = Number(process.env.SESSION_TTL_MS || 365 * 24 * 60 * 60 * 1000);

function getJwtSecret() {
  return process.env.JWT_SECRET || "change_me";
}

export function sanitizeUser(user) {
  return {
    id: String(user._id || user.id),
    name: user.name,
    email: user.email
  };
}

export function issueJwt(user) {
  return jwt.sign(
    {
      sub: String(user._id || user.id),
      name: user.name,
      email: user.email,
      scope: "user"
    },
    getJwtSecret(),
    { expiresIn: Math.floor(SESSION_TTL_MS / 1000) }
  );
}

export function createAuthResponse(user) {
  const safeUser = sanitizeUser(user);
  const expiresAt = new Date(Date.now() + SESSION_TTL_MS).toISOString();

  return {
    user: safeUser,
    token: issueJwt(safeUser),
    expiresAt
  };
}

export function saveSession(req, authResponse) {
  req.session.user = {
    ...authResponse.user,
    expiresAt: authResponse.expiresAt
  };
}

function getSessionUser(req) {
  return req.session?.user || null;
}

export function authGuard(req, res, next) {
  const sessionUser = getSessionUser(req);
  if (sessionUser) {
    req.user = sessionUser;
    return next();
  }

  const authHeader = req.headers.authorization || "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;
  if (!token) return res.status(401).json({ error: "Missing token" });

  try {
    const payload = jwt.verify(token, getJwtSecret());
    req.user = {
      id: payload.sub,
      name: payload.name,
      email: payload.email,
      expiresAt: new Date(payload.exp * 1000).toISOString()
    };
    return next();
  } catch {
    return res.status(401).json({ error: "Invalid token" });
  }
}
