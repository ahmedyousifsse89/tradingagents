/**
 * Redirects signed-out visitors to /login.
 *
 * This is a UX guard only — it checks that a session cookie is present, not
 * that it is valid, because middleware runs on the Edge runtime without the
 * Node crypto used for signing. Real verification happens in the proxy route,
 * which is the only path to the bot's API.
 */
import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/constants";

export function middleware(request: NextRequest) {
  const hasCookie = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  const isLogin = request.nextUrl.pathname === "/login";

  if (!hasCookie && !isLogin) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (hasCookie && isLogin) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/login"],
};
