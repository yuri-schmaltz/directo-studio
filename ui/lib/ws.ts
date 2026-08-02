"use client";

// Reconnecting WebSocket for the live event stream.
// Auto-reconnects with exponential backoff (1s, 2s, 4s, max 30s).

import { useEffect, useRef, useState, useCallback } from "react";
import type { Event } from "./types";

export type ConnectionState = "connecting" | "open" | "closed" | "error";

export function wsUrl(path: string = "/ws/events"): string {
  const explicit = process.env.NEXT_PUBLIC_DIRECTO_WS_URL;
  if (explicit) {
    return explicit.replace(/\/$/, "") + path;
  }
  const backendUrl = process.env.NEXT_PUBLIC_DIRECTO_API_URL || "http://localhost:8000";
  try {
    const parsed = new URL(backendUrl, typeof window !== "undefined" ? window.location.href : "http://localhost:8000");
    const proto = parsed.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${parsed.host}${path}`;
  } catch {
    return `ws://localhost:8000${path}`;
  }
}

export function useEventStream(options: {
  onEvent?: (event: Event) => void;
  enabled?: boolean;
  path?: string;
} = {}) {
  const { onEvent, enabled = true, path = "/ws/events" } = options;
  const [state, setState] = useState<ConnectionState>("closed");
  const [events, setEvents] = useState<Event[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);

  // Keep the latest onEvent in a ref so we don't re-create the WebSocket on every render
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    if (!enabled) return;
    setState("connecting");
    const ws = new WebSocket(wsUrl(path));
    wsRef.current = ws;

    ws.onopen = () => {
      setState("open");
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (msg) => {
      try {
        const event: Event = JSON.parse(msg.data);
        setEvents((prev) => {
          // Cap at 500 to avoid memory bloat
          const next = [event, ...prev];
          return next.length > 500 ? next.slice(0, 500) : next;
        });
        onEventRef.current?.(event);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => setState("error");

    ws.onclose = () => {
      setState("closed");
      wsRef.current = null;
      if (!enabled) return;
      // Exponential backoff up to 30s
      const delay = Math.min(
        1000 * 2 ** reconnectAttemptsRef.current,
        30_000,
      );
      reconnectAttemptsRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    };
  }, [enabled, path]);

  useEffect(() => {
    if (enabled) connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect, enabled]);

  const clear = useCallback(() => setEvents([]), []);

  return { state, events, clear };
}
