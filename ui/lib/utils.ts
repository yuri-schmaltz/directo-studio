import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(timestamp: number | string): string {
  const ts = typeof timestamp === "string" ? parseFloat(timestamp) : timestamp;
  if (!ts || isNaN(ts)) return "—";
  return new Date(ts * 1000).toLocaleString();
}

export function formatRelativeTime(timestamp: number | string): string {
  const ts = typeof timestamp === "string" ? parseFloat(timestamp) : timestamp;
  if (!ts || isNaN(ts)) return "—";
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`;
}

export function truncate(s: string, n: number = 60): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export function shortId(id: string, len: number = 8): string {
  if (!id) return "—";
  return id.length > len ? id.slice(0, len) : id;
}
