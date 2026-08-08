/**
 * Cookie-based dashboard sessions.
 *
 * The dashboard password and the bot's API token live only in Vercel's
 * server-side environment. The browser gets an HMAC-signed session cookie and
 * nothing else — no token is ever shipped to the client, so a stolen browser
 * session cannot be replayed against the bot's API directly.
 */
import { createHmac, timingSafeEqual } from "node:crypto";

import { SESSION_TTL_SECONDS } from "./constants";

export { SESSION_COOKIE } from "./constants";

function sessionSecret(): string {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 24) {
    throw new Error(
      "SESSION_SECRET must be set to at least 24 characters. Generate one with: openssl rand -base64 32",
    );
  }
  return secret;
}

function sign(payload: string): string {
  return createHmac("sha256", sessionSecret()).update(payload).digest("base64url");
}

/** Issue a signed session value that expires SESSION_TTL_SECONDS from now. */
export function createSession(): { value: string; maxAge: number } {
  const expiresAt = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  const payload = String(expiresAt);
  return { value: `${payload}.${sign(payload)}`, maxAge: SESSION_TTL_SECONDS };
}

/** True when the cookie is well-formed, correctly signed, and unexpired. */
export function verifySession(value: string | undefined): boolean {
  if (!value) return false;
  const [payload, signature] = value.split(".");
  if (!payload || !signature) return false;

  const expected = Buffer.from(sign(payload));
  const presented = Buffer.from(signature);
  if (expected.length !== presented.length) return false;
  if (!timingSafeEqual(expected, presented)) return false;

  const expiresAt = Number(payload);
  return Number.isFinite(expiresAt) && expiresAt > Math.floor(Date.now() / 1000);
}

/** Constant-time password check against the configured dashboard password. */
export function passwordMatches(presented: string): boolean {
  const expected = process.env.DASHBOARD_PASSWORD;
  if (!expected || expected.length < 8) {
    throw new Error("DASHBOARD_PASSWORD must be set to at least 8 characters");
  }
  const a = Buffer.from(expected);
  const b = Buffer.from(presented ?? "");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}
