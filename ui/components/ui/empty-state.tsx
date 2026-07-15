"use client";

import { cn } from "@/lib/utils";
import * as React from "react";

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-bg-subtle p-12 text-center",
        className,
      )}
    >
      {icon && <div className="text-fg-subtle">{icon}</div>}
      <div>
        <h3 className="text-base font-semibold text-fg">{title}</h3>
        {description && (
          <p className="mt-1 text-sm text-fg-muted max-w-md">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-bg-muted",
        className,
      )}
      {...props}
    />
  );
}
