"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface CollapsiblePanelProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  headerActions?: React.ReactNode;
}

export function CollapsiblePanel({
  title,
  children,
  defaultOpen = true,
  className,
  headerActions,
}: CollapsiblePanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={cn("border border-border rounded overflow-hidden bg-bg-subtle", className)}>
      {/* Header */}
      <div
        className={cn(
          "flex items-center justify-between px-3 py-1.5 bg-bg-muted/60 select-none cursor-pointer border-b border-border transition-colors hover:bg-bg-muted",
          !isOpen && "border-b-0"
        )}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5 text-fg-subtle shrink-0" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-fg-subtle shrink-0" />
          )}
          <span className="text-xs font-semibold tracking-wide uppercase text-fg-muted font-mono">
            {title}
          </span>
        </div>
        {headerActions && (
          <div onClick={(e) => e.stopPropagation()} className="flex items-center">
            {headerActions}
          </div>
        )}
      </div>

      {/* Content */}
      {isOpen && (
        <div className="p-3 bg-bg-subtle/40 animate-fade-in text-sm">
          {children}
        </div>
      )}
    </div>
  );
}
