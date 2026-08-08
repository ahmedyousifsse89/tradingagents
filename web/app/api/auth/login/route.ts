import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE, createSession, passwordMatches } from "@/lib/session";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
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

  const session = createSession();
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
