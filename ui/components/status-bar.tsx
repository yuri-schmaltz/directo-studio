"use client";

import { useNotifications } from "@/components/notifications-provider";
import { LiveIndicator } from "@/components/live-indicator";
import { Terminal, ShieldCheck } from "lucide-react";

export function StatusBar() {
  const { state } = useNotifications();

  return (
    <footer className="h-7 w-full border-t border-border bg-bg-subtle text-[11px] font-mono text-fg-subtle select-none flex items-center justify-between px-3 z-30 shrink-0">
      {/* Left side: Shortcuts and Hints */}
      <div className="flex items-center gap-4 overflow-hidden whitespace-nowrap">
        <div className="flex items-center gap-1 text-fg-muted font-semibold mr-2 shrink-0">
          <Terminal className="h-3 w-3 text-accent" />
          <span>Directo Studio</span>
        </div>
        <div className="hidden sm:flex items-center gap-3">
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 bg-bg-muted border border-border rounded text-[10px] text-fg font-sans font-medium uppercase">Alt+1..9</kbd>
            <span>Navigation</span>
          </span>
          <span className="h-2 w-px bg-border" />
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 bg-bg-muted border border-border rounded text-[10px] text-fg font-sans font-medium uppercase">Tab</kbd>
            <span>Focus</span>
          </span>
          <span className="h-2 w-px bg-border" />
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 bg-bg-muted border border-border rounded text-[10px] text-fg font-sans font-medium uppercase">Esc</kbd>
            <span>Back</span>
          </span>
        </div>
      </div>

      {/* Right side: System Status */}
      <div className="flex items-center gap-3 shrink-0 font-mono">
        {/* System Active Engine */}
        <div className="hidden md:flex items-center gap-1.5 text-[10px] text-fg-subtle">
          <ShieldCheck className="h-3 w-3 text-emerald-400" />
          <span>Backend Ready</span>
        </div>

        <span className="hidden md:inline h-3 w-px bg-border" />

        {/* Live Status Indicator */}
        <LiveIndicator state={state} className="text-[11px]" />
      </div>
    </footer>
  );
}
