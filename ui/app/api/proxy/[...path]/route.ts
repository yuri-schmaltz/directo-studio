// Server-side proxy to the FastAPI backend.
// Lets the browser stay same-origin, avoiding CORS issues.

import { NextRequest, NextResponse } from "next/server";

// NEXT_PUBLIC_ vars are inlined at build time → always present in the bundle.
const BACKEND =
  process.env.NEXT_PUBLIC_DIRECTO_API_URL || "http://127.0.0.1:18000";

export async function GET(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return forward(req, params.path, "GET");
}

export async function POST(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return forward(req, params.path, "POST");
}

export async function PUT(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return forward(req, params.path, "PUT");
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return forward(req, params.path, "DELETE");
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return forward(req, params.path, "PATCH");
}

async function forward(
  req: NextRequest,
  pathParts: string[],
  method: string,
) {
  const path = pathParts.join("/");
  // Pass-through: keep the original API path verbatim. The browser constructs
  // `/api/proxy${path}` (e.g. `/api/proxy/health`, `/api/proxy/api/projects`)
  // and we strip the proxy prefix below; do NOT add a hard-coded `/api/` here,
  // otherwise top-level routes like `/health` and `/metrics` 404.
  const url = `${BACKEND}/${path}${req.nextUrl.search}`;

  const headers = new Headers();
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  headers.set("accept", req.headers.get("accept") || "application/json");

  const body =
    method === "GET" || method === "DELETE" ? undefined : await req.text();

  try {
    const res = await fetch(url, {
      method,
      headers,
      body,
      cache: "no-store",
    });
    const resHeaders = new Headers();
    resHeaders.set(
      "content-type",
      res.headers.get("content-type") || "application/json",
    );
    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      statusText: res.statusText,
      headers: resHeaders,
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Backend unreachable", detail: String(e) },
      { status: 502 },
    );
  }
}
