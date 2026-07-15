"use client";

import { cn } from "@/lib/utils";
import { Circle } from "lucide-react";

interface LiveIndicatorProps {
  state: "connecting" | "open" | "closed" | "error";
  className?: string;
}

export function LiveIndicator({ state, className }: LiveIndicatorProps) {
  const map = {
    open: { color: "text-success", label: "Live", dot: "bg-success" },
    connecting: { color: "text-warning", label: "Connecting", dot: "bg-warning" },
    closed: { color: "text-fg-subtle", label: "Offline", dot: "bg-fg-subtle" },
    error: { color: "text-danger", label: "Error", dot: "bg-danger" },
  } as const;
  const m = map[state];
  return (
    <div className={cn("flex items-center gap-1.5 text-xs", m.color, className)}>
      <Circle
        className={cn("h-2 w-2 fill-current", m.dot, state === "open" && "animate-pulse-slow")}
      />
      <span className="font-medium">{m.label}</span>
    </div>
  );
}
