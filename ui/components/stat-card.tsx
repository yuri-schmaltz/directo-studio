"use client";

import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  hint?: string;
  trend?: "up" | "down" | "flat";
  icon?: React.ReactNode;
  loading?: boolean;
  className?: string;
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  loading = false,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        "card card-pad flex flex-col gap-2 transition-colors hover:bg-bg-muted/50",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-fg-subtle font-medium">
          {label}
        </span>
        {icon && <div className="text-fg-subtle">{icon}</div>}
      </div>
      <div className="text-3xl font-semibold tabular-nums text-fg">
        {loading ? (
          <div className="h-9 w-20 animate-pulse rounded bg-bg-muted" />
        ) : (
          value
        )}
      </div>
      {hint && <div className="text-xs text-fg-muted">{hint}</div>}
    </div>
  );
}

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  format?: (n: number) => string;
  className?: string;
}

export function AnimatedNumber({
  value,
  duration = 600,
  format = (n) => n.toLocaleString(),
  className,
}: AnimatedNumberProps) {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    const start = display;
    const startTime = performance.now();
    let raf: number;
    const tick = (now: number) => {
      const t = Math.min(1, (now - startTime) / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(start + (value - start) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);
  return <span className={className}>{format(display)}</span>;
}
