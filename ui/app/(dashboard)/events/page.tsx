"use client";

import { EventFeed } from "@/components/event-feed";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEventStream } from "@/lib/ws";
import { formatCost } from "@/lib/utils";
import { useMemo } from "react";

export default function EventsPage() {
  const { events, state } = useEventStream();

  const summary = useMemo(() => {
    const byKind: Record<string, number> = {};
    for (const e of events) {
      byKind[e.kind] = (byKind[e.kind] ?? 0) + 1;
    }
    const last5min = events.filter(
      (e) => Date.now() / 1000 - e.timestamp < 300,
    );
    return { byKind, last5min: last5min.length };
  }, [events]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Live Events</h2>
        <p className="text-sm text-fg-muted">
          Real-time stream from the EventBus via WebSocket
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-fg-muted">
              State
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold capitalize">{state}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-fg-muted">
              Total captured
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">
              {events.length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-fg-muted">
              Last 5 min
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">
              {summary.last5min}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <EventFeed limit={100} showHeader={true} />
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">By kind</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(summary.byKind).length === 0 ? (
              <p className="text-sm text-fg-muted">No events yet</p>
            ) : (
              <ul className="space-y-1.5">
                {Object.entries(summary.byKind)
                  .sort((a, b) => b[1] - a[1])
                  .map(([kind, count]) => (
                    <li
                      key={kind}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="font-mono text-xs">{kind}</span>
                      <span className="font-mono tabular-nums text-fg-muted">
                        {count}
                      </span>
                    </li>
                  ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
