"use client";

import { useEventStream } from "@/lib/ws";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LiveIndicator } from "@/components/live-indicator";
import { formatRelativeTime } from "@/lib/utils";
import { useMemo } from "react";

const KIND_VARIANT: Record<string, "default" | "success" | "warning" | "danger" | "brand"> = {
  "job.completed": "success",
  "job.failed": "danger",
  "job.cancelled": "warning",
  "job.enqueued": "brand",
  "image.added": "success",
  "image.rated": "brand",
  "project.created": "brand",
};

interface EventFeedProps {
  limit?: number;
  showHeader?: boolean;
  filterKinds?: string[];
  className?: string;
}

export function EventFeed({
  limit = 30,
  showHeader = true,
  filterKinds,
  className,
}: EventFeedProps) {
  const { state, events } = useEventStream();

  const filtered = useMemo(() => {
    const list = filterKinds
      ? events.filter((e) => filterKinds.includes(e.kind))
      : events;
    return list.slice(0, limit);
  }, [events, filterKinds, limit]);

  const content = (
    <div className="space-y-2">
      {filtered.length === 0 ? (
        <p className="text-sm text-fg-muted py-8 text-center">
          {state === "open"
            ? "Waiting for events…"
            : "Connecting to event stream…"}
        </p>
      ) : (
        filtered.map((ev, i) => {
          const variant = KIND_VARIANT[ev.kind] ?? "default";
          return (
            <div
              key={ev.id ?? `${ev.timestamp}-${i}`}
              className="rounded-md border border-border bg-bg-subtle p-3 hover:border-border/60 transition-colors"
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <Badge variant={variant}>{ev.kind}</Badge>
                <span className="text-xs text-fg-subtle tabular-nums">
                  {formatRelativeTime(ev.timestamp)}
                </span>
              </div>
              {Object.keys(ev.payload).length > 0 && (
                <pre className="text-xs text-fg-muted font-mono overflow-x-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(ev.payload, null, 0)}
                </pre>
              )}
            </div>
          );
        })
      )}
    </div>
  );

  if (!showHeader) return <div className={className}>{content}</div>;

  return (
    <Card className={className}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Live Events</CardTitle>
        <LiveIndicator state={state} />
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  );
}
