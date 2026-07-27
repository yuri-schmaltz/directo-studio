"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { swrFetcher, api } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EventFeed } from "@/components/event-feed";
import { Badge } from "@/components/ui/badge";
import { formatBytes, shortId, formatRelativeTime } from "@/lib/utils";
import {
  Image,
  Workflow,
  CheckCircle,
  Database,
  Activity,
  Sparkles,
} from "lucide-react";
import { CollapsiblePanel } from "@/components/collapsible-panel";
import { LiveIndicator } from "@/components/live-indicator";
import { useEventStream } from "@/lib/ws";
import type { HealthResponse, QueueStats } from "@/lib/types";

export default function DashboardPage() {
  const { data: health, error: healthErr } = useSWR<HealthResponse>(
    "/api/proxy/health",
    swrFetcher,
    { refreshInterval: 5_000 },
  );
  const { state: wsState } = useEventStream({ enabled: false });

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
git fetch origin v1.1.2 && git checkout v1.1.2`}
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
        <div className="animate-fade-in stagger-1">
          <StatCard
            label="Pending Jobs"
            value={health?.queue.pending ?? 0}
            icon={<Workflow className="h-4 w-4" />}
            loading={!health}
          />
        </div>
        <div className="animate-fade-in stagger-2">
          <StatCard
            label="Running"
            value={health?.queue.running ?? 0}
            icon={<Activity className="h-4 w-4" />}
            loading={!health}
          />
        </div>
        <div className="animate-fade-in stagger-3">
          <StatCard
            label="Gallery"
            value={health?.gallery.total ?? 0}
            icon={<Image className="h-4 w-4" />}
            hint="images stored"
            loading={!health}
          />
        </div>
        <div className="animate-fade-in stagger-4">
          <StatCard
            label="Completed Jobs"
            value={health?.queue.completed ?? 0}
            icon={<CheckCircle className="h-4 w-4 text-emerald-500" />}
            loading={!health}
          />
        </div>
        <div className="animate-fade-in stagger-5">
          <StatCard
            label="Failed"
            value={health?.queue.failed ?? 0}
            icon={<Database className="h-4 w-4" />}
            loading={!health}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 animate-fade-in stagger-3">
        <CollapsiblePanel title="Queue">
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
        </CollapsiblePanel>

        <CollapsiblePanel 
          title="Live Events" 
          headerActions={<LiveIndicator state={wsState} />}
        >
          <EventFeed limit={8} showHeader={false} />
        </CollapsiblePanel>
      </div>
    </div>
  );
}
