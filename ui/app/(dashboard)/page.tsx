"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { swrFetcher, api } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EventFeed } from "@/components/event-feed";
import { Badge } from "@/components/ui/badge";
import { formatBytes, formatCost, shortId, formatRelativeTime } from "@/lib/utils";
import {
  Image,
  Workflow,
  DollarSign,
  Database,
  Activity,
  Sparkles,
} from "lucide-react";
import type { HealthResponse, QueueStats, CostSummary } from "@/lib/types";

export default function DashboardPage() {
  const { data: health, error: healthErr } = useSWR<HealthResponse>(
    "/api/proxy/health",
    swrFetcher,
    { refreshInterval: 5_000 },
  );
  const { data: costs } = useSWR<CostSummary>(
    "/api/proxy/costs",
    swrFetcher,
    { refreshInterval: 10_000 },
  );

  if (healthErr) {
    return (
      <Card className="card-pad">
        <CardTitle className="text-danger">Backend unreachable</CardTitle>
        <p className="text-sm text-fg-muted mt-2">
          Could not reach the Directo API. The easiest way to bring the whole
          stack up (venv, deps, backend, frontend) is:
        </p>
        <pre className="mt-3 rounded-md bg-bg-muted p-3 text-xs font-mono">
{`# From the repo root (creates .venv, installs deps, starts both):
./start.sh

# If that does not exist yet, you are on an old checkout — pull:
git fetch origin v1.1.1 && git checkout v1.1.1`}
        </pre>
        <p className="text-sm text-fg-muted mt-3">
          Manual fallback — single line, with <code>--db-dir</code> BEFORE the
          <code> server </code> subcommand (Click rejects it the other way):
        </p>
        <pre className="mt-3 rounded-md bg-bg-muted p-3 text-xs font-mono">
{`# Linux / macOS / WSL:
.venv/bin/python -m directo.platform.cli --db-dir ./directo_data server --port 8000

# Windows (cmd / PowerShell / native):
.venv\\Scripts\\python.exe -m directo.platform.cli --db-dir ./directo_data server --port 8000

# Then in another terminal:
cd ui && npm install && DIRECTO_API_URL=http://localhost:8000 npm run dev`}
        </pre>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-sm text-fg-muted">
            Live overview of your Directo instance
          </p>
        </div>
        {health && (
          <Badge variant="success">
            <Activity className="h-3 w-3 mr-1" />
            Connected
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard
          label="Pending Jobs"
          value={health?.queue.pending ?? 0}
          icon={<Workflow className="h-4 w-4" />}
          loading={!health}
        />
        <StatCard
          label="Running"
          value={health?.queue.running ?? 0}
          icon={<Activity className="h-4 w-4" />}
          loading={!health}
        />
        <StatCard
          label="Gallery"
          value={health?.gallery.total ?? 0}
          icon={<Image className="h-4 w-4" />}
          hint="images stored"
          loading={!health}
        />
        <StatCard
          label="Total Spend"
          value={formatCost(costs?.total_usd ?? 0)}
          icon={<DollarSign className="h-4 w-4" />}
          loading={!costs}
        />
        <StatCard
          label="Failed"
          value={health?.queue.failed ?? 0}
          icon={<Database className="h-4 w-4" />}
          loading={!health}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Queue</CardTitle>
          </CardHeader>
          <CardContent>
            {health ? (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                {Object.entries(health.queue).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <dt className="text-fg-muted capitalize">{k}</dt>
                    <dd className="font-mono tabular-nums">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-5 rounded bg-bg-muted animate-pulse"
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <EventFeed limit={8} showHeader={true} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top projects (cost)</CardTitle>
          </CardHeader>
          <CardContent>
            {costs && costs.by_project.length > 0 ? (
              <div className="space-y-2">
                {costs.by_project.slice(0, 5).map((row) => (
                  <div
                    key={row.project}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-fg">{row.project}</span>
                    <span className="font-mono tabular-nums text-fg-muted">
                      {formatCost(row.total_cost)}
                      <span className="text-fg-subtle text-xs ml-2">
                        ({row.entries})
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fg-muted">No cost data yet</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top cost kinds</CardTitle>
          </CardHeader>
          <CardContent>
            {costs && costs.by_kind.length > 0 ? (
              <div className="space-y-2">
                {costs.by_kind.slice(0, 5).map((row) => (
                  <div
                    key={row.kind}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-fg font-mono text-xs">
                      {row.kind}
                    </span>
                    <span className="font-mono tabular-nums text-fg-muted">
                      {formatCost(row.total_cost)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fg-muted">No cost data yet</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
