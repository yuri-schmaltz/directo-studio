// Expose the UI version so that local-mode tooling (./start.sh, ./stop.sh)
// can detect when a running dev server is stale relative to the source tree.
//
// Returns a small JSON object: { "name": "directo-ui", "version": "1.x.y" }.
// The version is read from package.json at module load (in dev mode, the dev
// server re-evaluates modules on file change, so this stays in sync).
//
// Note: in production builds the version is also inlined into the JS bundle
// by Next.js's build step. Here we deliberately read the source-of-truth file
// at request time, which is what ./start.sh needs.

import { NextResponse } from "next/server";
import { readFileSync } from "node:fs";
import { join } from "node:path";

let cached: { name: string; version: string } | null = null;
let cachedAt = 0;

function readVersion(): { name: string; version: string } {
    // Cache for 1s — process-level state, no need to re-read the file on
    // every request. Cheap and avoids disk thrash under heavy polling.
    const now = Date.now();
    if (cached && now - cachedAt < 1000) return cached;

    try {
        const pkgPath = join(process.cwd(), "package.json");
        const raw = JSON.parse(readFileSync(pkgPath, "utf-8")) as {
            name?: string;
            version?: string;
        };
        cached = {
            name: raw.name ?? "directo-ui",
            version: raw.version ?? "0.0.0",
        };
        cachedAt = now;
        return cached;
    } catch {
        // Fall back to a sentinel so callers can still detect a mismatch.
        return { name: "directo-ui", version: "0.0.0-unknown" };
    }
}

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
    return NextResponse.json(readVersion());
}
