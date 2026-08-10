/**
 * Server-side proxy to the bot's control API.
 *
 * Every dashboard request goes through here. Two things happen that could not
 * happen in the browser: the session cookie is verified, and the bot's bearer
 * token is attached. The token is a server-only environment variable, so it is
 * never present in the client bundle or in devtools.
 *
 * Only paths under /api/ on the backend are reachable, so this cannot be used
 * as an open relay to arbitrary hosts.
 */
import { NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE, verifySession } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function backend(): { url: string; token: string } {
  const url = process.env.TRADINGAGENTS_API_URL;
  const token = process.env.TRADINGAGENTS_API_TOKEN;
  if (!url) throw new Error("TRADINGAGENTS_API_URL is not set");
  if (!token) throw new Error("TRADINGAGENTS_API_TOKEN is not set");
  return { url: url.replace(/\/$/, ""), token };
}

async function forward(request: NextRequest, path: string[], method: string) {
  if (!verifySession(request.cookies.get(SESSION_COOKIE)?.value)) {
    return NextResponse.json({ detail: "not signed in" }, { status: 401 });
  }

  let target: { url: string; token: string };
  try {
    target = backend();
  } catch (error) {
    return NextResponse.json(
      { detail: (error as Error).message },
      { status: 500 },
    );
  }

  const search = request.nextUrl.search;
  const endpoint = `${target.url}/api/${path.join("/")}${search}`;

  const init: RequestInit = {
    method,
    headers: {
      Authorization: `Bearer ${target.token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  };

  if (method !== "GET" && method !== "DELETE") {
    init.body = await request.text();
  }

  try {
    const response = await fetch(endpoint, init);
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    // A sleeping or redeploying Railway service shows up here. Say so plainly
    // rather than surfacing an opaque 500 in the dashboard.
    return NextResponse.json(
      { detail: `bot unreachable: ${(error as Error).message}` },
      { status: 502 },
    );
  }
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: Context) {
  return forward(request, (await context.params).path, "GET");
}

export async function POST(request: NextRequest, context: Context) {
  return forward(request, (await context.params).path, "POST");
}

export async function PUT(request: NextRequest, context: Context) {
  return forward(request, (await context.params).path, "PUT");
}

export async function DELETE(request: NextRequest, context: Context) {
  return forward(request, (await context.params).path, "DELETE");
}
