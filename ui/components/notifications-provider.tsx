"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Toaster, toast } from "sonner";
import { useEventStream, ConnectionState } from "@/lib/ws";
import type { Event } from "@/lib/types";

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  description: string;
  timestamp: number;
  read: boolean;
  type: "success" | "error" | "info" | "warning";
  payload?: Record<string, unknown>;
}

interface NotificationsContextType {
  state: ConnectionState;
  notifications: NotificationItem[];
  unreadCount: number;
  markAllRead: () => void;
  clearNotifications: () => void;
}

const NotificationsContext = createContext<NotificationsContextType>({
  state: "closed",
  notifications: [],
  unreadCount: 0,
  markAllRead: () => {},
  clearNotifications: () => {},
});

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  const handleEvent = useCallback((event: Event) => {
    const eventId = event.id || `${event.kind}-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    let notifType: "success" | "error" | "info" | "warning" = "info";
    let title = "";
    let description = "";
    let shouldToast = false;

    const payload = event.payload || {};

    switch (event.kind) {
      case "job.completed":
        notifType = "success";
        title = "Job Completed";
        description = String(payload.kind || payload.job_id || "Processing completed successfully");
        shouldToast = true;
        break;
      case "job.failed":
        notifType = "error";
        title = "Job Failed";
        description = String(payload.error || payload.job_id || "An error occurred during processing");
        shouldToast = true;
        break;
      case "job.started":
        notifType = "info";
        title = "Job Running";
        description = String(payload.kind || payload.job_id || "Processing started");
        shouldToast = true;
        break;
      case "job.enqueued":
        notifType = "info";
        title = "Job Enqueued";
        description = String(payload.kind || payload.job_id || "Job added to queue");
        shouldToast = true;
        break;
      case "job.cancelled":
        notifType = "warning";
        title = "Job Cancelled";
        description = String(payload.job_id || "Job was cancelled");
        shouldToast = true;
        break;
      case "project.created":
        notifType = "success";
        title = "New Project";
        description = String(payload.name || "Project created");
        shouldToast = true;
        break;
      case "canvas.saved":
      case "panel.added":
        notifType = "info";
        title = "Animatic Updated";
        description = String(payload.name || "Panel modified");
        shouldToast = false; // Add to panel list without annoying toast
        break;
      default:
        // Handle generic custom/system events if important
        if (event.kind.startsWith("job.")) {
          title = "Job Event";
          description = `${event.kind}: ${JSON.stringify(payload)}`;
          shouldToast = true;
        }
        break;
    }

    if (title) {
      const newItem: NotificationItem = {
        id: eventId,
        kind: event.kind,
        title,
        description,
        timestamp: event.timestamp || Date.now() / 1000,
        read: false,
        type: notifType,
        payload,
      };

      setNotifications((prev) => [newItem, ...prev].slice(0, 50));

      if (shouldToast) {
        if (notifType === "success") {
          toast.success(title, { description });
        } else if (notifType === "error") {
          toast.error(title, { description });
        } else if (notifType === "warning") {
          toast.warning(title, { description });
        } else {
          toast.info(title, { description });
        }
      }
    }
  }, []);

  const { state } = useEventStream({
    enabled: true,
    onEvent: handleEvent,
  });

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  return (
    <NotificationsContext.Provider
      value={{
        state,
        notifications,
        unreadCount,
        markAllRead,
        clearNotifications,
      }}
    >
      {children}
      <Toaster position="top-right" theme="dark" richColors closeButton />
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationsContext);
}
