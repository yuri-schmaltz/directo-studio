// Typed FastAPI client.
// Server-side fetches go through Next.js rewrites (/api/proxy/* -> FastAPI).
// Client-side fetches call the FastAPI directly using NEXT_PUBLIC_DIRECTO_API_URL.

import type {
  BackupResult,
  CinemaReport,
  Event,
  HealthResponse,
  ImageRecord,
  Job,
  JobCreatePayload,
  MediaJob,
  Preset,
  ProjectRecord,
  QueueStats,
  Scene,
  StyleBible,
  StyleBibleSummary,
  StyleDirective,
} from "./types";

const isServer = typeof window === "undefined";

function apiBase(): string {
  if (isServer) {
    return process.env.DIRECTO_API_URL || "http://localhost:8000";
  }
  return (
    process.env.NEXT_PUBLIC_DIRECTO_API_URL ||
    process.env.NEXT_PUBLIC_DIRECTO_WS_URL?.replace(/^ws/, "http") ||
    "http://localhost:8000"
  );
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = isServer
    ? `${apiBase()}${path}`
    : `/api/proxy${path.replace(/^\/api/, "")}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
    cache: init.cache ?? "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text || path}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Health & metrics
  health: () => request<HealthResponse>("/health"),
  metrics: () => request<string>("/metrics"),

  // Gallery
  gallery: {
    list: (params: {
      project?: string;
      min_rating?: number;
      favorites_only?: boolean;
      limit?: number;
      offset?: number;
    } = {}) => {
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
          .map(([k, v]) => [k, String(v)]),
      );
      return request<{ items: ImageRecord[]; count: number }>(
        `/api/gallery?${qs.toString()}`,
      );
    },
    get: (id: string) => request<ImageRecord>(`/api/gallery/${id}`),
    create: (data: Partial<ImageRecord>) =>
      request<{ id: string }>(`/api/gallery`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, fields: Partial<ImageRecord>) =>
      request<{ updated: boolean }>(`/api/gallery/${id}`, {
        method: "PATCH",
        body: JSON.stringify(fields),
      }),
  },

  // Queue / Jobs
  jobs: {
    list: (params: { state?: string; limit?: number } = {}) => {
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
          .map(([k, v]) => [k, String(v)]),
      );
      return request<{ items: Job[]; stats: QueueStats }>(
        `/api/jobs?${qs.toString()}`,
      );
    },
    get: (id: string) => request<Job>(`/api/jobs/${id}`),
    submit: (data: JobCreatePayload) =>
      request<{ id: string }>(`/api/jobs`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    cancel: (id: string) =>
      request<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, {
        method: "POST",
      }),
  },

  // Presets
  presets: {
    list: (params: { kind?: string; era?: string } = {}) => {
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
          .map(([k, v]) => [k, String(v)]),
      );
      return request<{ items: Preset[]; count: number }>(
        `/api/presets?${qs.toString()}`,
      );
    },
    get: (id: string) => request<Preset>(`/api/presets/${id}`),
    enhance: (
      id: string,
      payload: {
        prompt: string;
        target?: string;
        enhance?: boolean;
      },
    ) =>
      request<{
        preset: string;
        user_prompt: string;
        rendered: string;
        enhanced: string;
      }>(`/api/presets/${id}/enhance`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // Cinema
  cinema: {
    evaluate: (data: { prompt: string; context?: Record<string, unknown> }) =>
      request<CinemaReport>(`/api/cinema/evaluate`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    parseScript: (data: { text: string; hint?: string }) =>
      request<{ scenes: Scene[]; count: number }>(
        `/api/cinema/parse-script`,
        {
          method: "POST",
          body: JSON.stringify(data),
        },
      ),
  },

  // Projects
  projects: {
    list: () =>
      request<{ items: ProjectRecord[] }>(`/api/projects`).catch(() => ({
        items: [],
      })),
    get: (id: string) => request<ProjectRecord>(`/api/projects/${id}`),
    create: (data: {
      name: string;
      concept?: string;
      logline?: string;
    }) =>
      request<{ id: string }>(`/api/projects`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  // Backup
  backup: {
    create: (data: { db?: string; output_dir?: string } = {}) =>
      request<BackupResult>(`/api/backup`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    list: (db: string) =>
      request<{ items: { path: string; size: number; ts: number }[] }>(
        `/api/backup/list?db=${encodeURIComponent(db)}`,
      ).catch(() => ({ items: [] })),
  },

  // Style Bible
  styleBible: {
    /** Returns metadata summaries — no characters/environments/directives arrays. */
    list: () =>
      request<{ items: StyleBibleSummary[] }>("/api/style-bible"),
    /** Returns full StyleBible with characters[], environments[], directives[]. */
    get: (id: string) =>
      request<StyleBible>(`/api/style-bible/${id}`),
    create: (data: Omit<StyleBible, "version"> & { version?: string }) =>
      request<{ id: string }>("/api/style-bible", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: StyleBible) =>
      request<{ id: string }>(`/api/style-bible/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<{ deleted: boolean }>(`/api/style-bible/${id}`, {
        method: "DELETE",
      }),
    /** Export raw YAML or JSON string. Use exportFile() for blob download. */
    exportRaw: (id: string, format: "yaml" | "json" = "yaml") =>
      fetch(
        `/api/proxy/style-bible/${id}/export?format=${format}`,
      ).then((r) => r.text()),
    import: (content: string, format: "json" | "yaml" = "json") =>
      request<{ id: string; name: string }>("/api/style-bible/import", {
        method: "POST",
        body: JSON.stringify({ content, format }),
      }),
  },

  // Media Hub
  mediaHub: {
    generate: (payload: {
      prompt: string;
      duration?: number;
      aspect_ratio?: string;
      bible_id?: string | null;
      character_ids?: string[];
      environment_id?: string | null;
    }) =>
      request<{ job_id: string; status: string; message: string }>(
        "/api/media-hub/generate",
        { method: "POST", body: JSON.stringify(payload) },
      ),
    getJob: (jobId: string) =>
      request<MediaJob>(`/api/media-hub/jobs/${jobId}`),
  },
};

// SWR fetcher that goes through the Next.js proxy
export const swrFetcher = <T = unknown>(url: string): Promise<T> =>
  fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json() as Promise<T>;
  });
