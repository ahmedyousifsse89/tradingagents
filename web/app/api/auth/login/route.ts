import { NextRequest, NextResponse } from "next/server";

import { checkRateLimit, clientKey, resetRateLimit } from "@/lib/rate-limit";
import { SESSION_COOKIE, createSession, passwordMatches } from "@/lib/session";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const key = clientKey(request);
  const retryAfter = checkRateLimit(key);
  if (retryAfter > 0) {
    return NextResponse.json(
      { detail: `too many attempts, try again in ${retryAfter}s` },
      { status: 429, headers: { "Retry-After": String(retryAfter) } },
    );
  }

  let password = "";
  try {
    ({ password } = await request.json());
  } catch {
    return NextResponse.json({ detail: "malformed request" }, { status: 400 });
  }

  let ok: boolean;
  try {
    ok = passwordMatches(password ?? "");
  } catch (error) {
    // Misconfiguration, not a failed login — say which, so the operator can fix it.
    return NextResponse.json({ detail: (error as Error).message }, { status: 500 });
  }

  if (!ok) {
    return NextResponse.json({ detail: "incorrect password" }, { status: 401 });
  }

  let session: ReturnType<typeof createSession>;
  try {
    session = createSession();
  } catch (error) {
    // Same reasoning as the passwordMatches catch above: a misconfigured
    // SESSION_SECRET must not look like a wrong password. Rate limit stays
    // un-reset here (the password check already passed, so consuming
    // another attempt on a config error is not the resource we're guarding).
    return NextResponse.json({ detail: (error as Error).message }, { status: 500 });
  }

  resetRateLimit(key);
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, session.value, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: session.maxAge,
  });
  return response;
}
