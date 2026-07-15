"use client";

import useSWR from "swr";
import { useState } from "react";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/empty-state";
import { StatCard } from "@/components/stat-card";
import { formatCost } from "@/lib/utils";
import { DollarSign, Activity } from "lucide-react";
import type { CostSummary, TimeseriesPoint } from "@/lib/types";

export default function CostsPage() {
  const [project, setProject] = useState("");
  const [hours, setHours] = useState(0);

  const qs = new URLSearchParams();
  if (project) qs.set("project", project);
  if (hours > 0) qs.set("hours", String(hours));
  const url = `/api/proxy/costs${qs.toString() ? `?${qs.toString()}` : ""}`;

  const { data, isLoading } = useSWR<CostSummary>(url, swrFetcher, {
    refreshInterval: 15_000,
  });

  // Timeseries — bucket by hour
  const { data: ts } = useSWR<TimeseriesPoint[]>(
    `/api/proxy/costs/timeseries?bucket_seconds=3600${
      hours > 0 ? `&hours=${hours}` : ""
    }`,
    swrFetcher,
    { refreshInterval: 30_000 },
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Costs</h2>
        <p className="text-sm text-fg-muted">
          Track GPU, LLM, storage and bandwidth spend
        </p>
      </div>

      <Card>
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label>Project (optional)</Label>
            <Input
              value={project}
              onChange={(e) => setProject(e.target.value)}
              placeholder="all"
            />
          </div>
          <div>
            <Label>Window</Label>
            <Select
              value={String(hours)}
              onChange={(e) => setHours(Number(e.target.value))}
            >
              <option value="0">All time</option>
              <option value="1">Last 1h</option>
              <option value="24">Last 24h</option>
              <option value="168">Last 7d</option>
              <option value="720">Last 30d</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard
          label="Total spend"
          value={formatCost(data?.total_usd ?? 0)}
          icon={<DollarSign className="h-4 w-4" />}
          loading={isLoading}
        />
        <StatCard
          label="Projects"
          value={data?.by_project.length ?? 0}
          loading={isLoading}
        />
        <StatCard
          label="Cost kinds"
          value={data?.by_kind.length ?? 0}
          loading={isLoading}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">By project</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-32" />
          ) : data && data.by_project.length > 0 ? (
            <Table
              rows={data.by_project.map((r) => ({
                name: r.project,
                cost: r.total_cost,
                entries: r.entries,
              }))}
            />
          ) : (
            <p className="text-sm text-fg-muted">No cost records yet</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">By kind</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-32" />
          ) : data && data.by_kind.length > 0 ? (
            <Table
              rows={data.by_kind.map((r) => ({
                name: r.kind,
                cost: r.total_cost,
                entries: r.entries,
              }))}
            />
          ) : (
            <p className="text-sm text-fg-muted">No cost records yet</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Timeseries (hourly)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {ts && ts.length > 0 ? (
            <Timeseries points={ts} />
          ) : (
            <p className="text-sm text-fg-muted">No timeseries data yet</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Table({
  rows,
}: {
  rows: Array<{ name: string; cost: number; entries: number }>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase text-fg-subtle">
            <th className="py-2 pr-3">Name</th>
            <th className="py-2 pr-3 text-right">Cost (USD)</th>
            <th className="py-2 text-right">Entries</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-b border-border/40 last:border-0">
              <td className="py-2 pr-3 font-mono text-xs">{r.name}</td>
              <td className="py-2 pr-3 text-right font-mono tabular-nums">
                {formatCost(r.cost)}
              </td>
              <td className="py-2 text-right text-fg-muted tabular-nums">
                {r.entries}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Timeseries({ points }: { points: TimeseriesPoint[] }) {
  const max = Math.max(...points.map((p) => p.cost), 0.001);
  return (
    <div className="space-y-2">
      <div className="flex items-end gap-0.5 h-32">
        {points.map((p, i) => {
          const h = Math.max(2, (p.cost / max) * 100);
          return (
            <div
              key={i}
              className="flex-1 bg-brand-500/60 hover:bg-brand-500 rounded-t transition-colors"
              style={{ height: `${h}%` }}
              title={`${new Date(p.bucket * 1000).toLocaleString()}: ${formatCost(p.cost)}`}
            />
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-fg-subtle">
        <span>
          {points.length > 0
            ? new Date(points[0].bucket * 1000).toLocaleString()
            : ""}
        </span>
        <span>
          {points.length > 0
            ? new Date(points[points.length - 1].bucket * 1000).toLocaleString()
            : ""}
        </span>
      </div>
    </div>
  );
}
