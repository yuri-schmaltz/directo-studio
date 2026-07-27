"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Bell, Check, Trash2, ExternalLink, Radio, Circle } from "lucide-react";
import { useNotifications } from "@/components/notifications-provider";
import { LiveIndicator } from "@/components/live-indicator";
import { cn } from "@/lib/utils";

export function ConnectionWidget() {
  const { state, notifications, unreadCount, markAllRead, clearNotifications } =
    useNotifications();
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  const handleToggle = () => {
    if (!open && unreadCount > 0) {
      markAllRead();
    }
    setOpen(!open);
  };

  return (
    <div className="relative flex items-center gap-2" ref={popoverRef}>
      {/* Live Status Pill */}
      <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded-full bg-bg-muted/80 border border-border/60">
        <LiveIndicator state={state} className="text-[11px]" />
      </div>

      {/* Bell Button */}
      <button
        onClick={handleToggle}
        className={cn(
          "relative p-1.5 rounded-md text-fg-muted hover:text-fg hover:bg-bg-muted transition-colors",
          open && "bg-bg-muted text-fg"
        )}
        title="Event & Job Notifications"
        aria-label="Open notification center"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-accent text-[9px] font-bold text-black animate-pulse">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Popover */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-lg border border-border bg-bg-subtle shadow-2xl z-50 overflow-hidden font-sans text-xs animate-fade-in">
          {/* Header */}
          <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-border bg-bg-muted/40">
            <div className="flex items-center gap-2 font-semibold text-fg">
              <Radio className="h-3.5 w-3.5 text-accent" />
              <span>Events & Jobs</span>
            </div>
            <div className="flex items-center gap-2">
              <LiveIndicator state={state} className="text-[10px]" />
              {notifications.length > 0 && (
                <button
                  onClick={clearNotifications}
                  className="p-1 rounded text-fg-subtle hover:text-danger hover:bg-bg-muted transition-colors"
                  title="Clear notifications"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Notification List */}
          <div className="max-h-80 overflow-y-auto divide-y divide-border/40 scrollbar-thin">
            {notifications.length === 0 ? (
              <div className="py-8 px-4 text-center text-fg-subtle">
                <p className="font-medium text-xs">No recent notifications</p>
                <p className="text-[11px] text-fg-subtle/80 mt-0.5">
                  Job events and status updates will appear here in real time.
                </p>
              </div>
            ) : (
              notifications.map((item) => {
                const dateStr = new Date(
                  item.timestamp * 1000
                ).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                });
                return (
                  <div
                    key={item.id}
                    className="p-3 hover:bg-bg-muted/30 transition-colors flex items-start gap-2.5"
                  >
                    <div className="mt-0.5 shrink-0">
                      {item.type === "success" && (
                        <Circle className="h-2.5 w-2.5 fill-emerald-500 text-emerald-500" />
                      )}
                      {item.type === "error" && (
                        <Circle className="h-2.5 w-2.5 fill-red-500 text-red-500" />
                      )}
                      {item.type === "warning" && (
                        <Circle className="h-2.5 w-2.5 fill-amber-500 text-amber-500" />
                      )}
                      {item.type === "info" && (
                        <Circle className="h-2.5 w-2.5 fill-blue-500 text-blue-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-semibold text-fg truncate">
                          {item.title}
                        </span>
                        <span className="font-mono text-[10px] text-fg-subtle shrink-0">
                          {dateStr}
                        </span>
                      </div>
                      <p className="text-[11px] text-fg-muted mt-0.5 truncate">
                        {item.description}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="px-3.5 py-2 border-t border-border bg-bg-muted/30 flex items-center justify-between text-[11px]">
            <Link
              href="/jobs"
              onClick={() => setOpen(false)}
              className="flex items-center gap-1 font-medium text-accent hover:underline"
            >
              <span>Manage Jobs Queue</span>
              <ExternalLink className="h-3 w-3" />
            </Link>
            <span className="font-mono text-fg-subtle text-[10px]">
              {notifications.length} {notifications.length === 1 ? "item" : "items"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
