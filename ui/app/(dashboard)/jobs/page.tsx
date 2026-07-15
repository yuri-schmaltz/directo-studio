"use client";

import useSWR from "swr";
import { useState } from "react";
import Link from "next/link";
import { swrFetcher, api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Skeleton, EmptyState } from "@/components/ui/empty-state";
import { Plus, Workflow, X } from "lucide-react";
import { shortId, truncate, formatRelativeTime } from "@/lib/utils";
import type { Job, JobState, QueueStats } from "@/lib/types";
import { JOB_STATES } from "@/lib/types";

const STATE_VARIANT: Record<JobState, "default" | "success" | "warning" | "danger" | "brand"> = {
  pending: "warning",
  running: "brand",
  completed: "success",
  failed: "danger",
  cancelled: "default",
};

export default function JobsPage() {
  const [stateFilter, setStateFilter] = useState<JobState | "all">("all");
  const { data, isLoading, mutate } = useSWR<{ items: Job[]; stats: QueueStats }>(
    `/api/proxy/jobs${stateFilter !== "all" ? `?state=${stateFilter}` : ""}`,
    swrFetcher,
    { refreshInterval: 2_000 },
  );

  async function cancelJob(id: string) {
    try {
      await api.jobs.cancel(id);
      mutate();
    } catch (e) {
      console.error(e);
    }
  }

  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Jobs</h2>
          <p className="text-sm text-fg-muted">
            {data?.stats?.total ?? 0} jobs in queue
            {data?.stats?.running != null && data.stats.running > 0 && (
              <span className="ml-2">
                · <Badge variant="brand">{data.stats.running} running</Badge>
              </span>
            )}
          </p>
        </div>
        <Button onClick={() => (window.location.href = "/jobs/new")}>
          <Plus className="h-4 w-4" />
          Submit job
        </Button>
      </div>

      <Card>
        <CardContent className="p-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-fg-muted">Filter:</span>
          {(["all", ...JOB_STATES] as const).map((s) => (
            <Button
              key={s}
              size="sm"
              variant={stateFilter === s ? "primary" : "secondary"}
              onClick={() => setStateFilter(s as JobState | "all")}
            >
              {s}
            </Button>
          ))}
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Workflow className="h-12 w-12" />}
          title="No jobs"
          description="Submit a job to get started."
          action={
            <Button onClick={() => (window.location.href = "/jobs/new")}>
              <Plus className="h-4 w-4" />
              Submit
            </Button>
          }
        />
      ) : (
        <Card>
          <CardContent className="p-0 divide-y divide-border">
            {items.map((job) => (
              <div
                key={job.id}
                className="p-3 flex items-center gap-3 hover:bg-bg-muted/40 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={STATE_VARIANT[job.state]}>
                      {job.state}
                    </Badge>
                    <span className="font-mono text-xs text-fg">
                      {job.kind}
                    </span>
                    {job.project && (
                      <Badge variant="brand">{job.project}</Badge>
                    )}
                    <span className="text-xs text-fg-subtle font-mono">
                      {shortId(job.id)}
                    </span>
                  </div>
                  <p className="text-sm text-fg-muted truncate">
                    {truncate(
                      String(job.payload?.prompt ?? JSON.stringify(job.payload)),
                      120,
                    )}
                  </p>
                </div>
                <span className="text-xs text-fg-subtle shrink-0">
                  {formatRelativeTime(job.created_at)}
                </span>
                {(job.state === "pending" || job.state === "running") && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => cancelJob(job.id)}
                    title="Cancel job"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
