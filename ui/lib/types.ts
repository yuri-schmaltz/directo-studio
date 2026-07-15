// TypeScript types mirroring the FastAPI response shapes.
// Kept manually (no code-gen) — small, stable, easy to read.

export type HealthResponse = {
  status: "ok";
  version: string;
  uptime: number;
  queue: QueueStats;
  gallery: { total: number };
};

export type QueueStats = {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
};

export type JobKind =
  | "image.generate"
  | "image.upscale"
  | "video.render"
  | "audio.synth"
  | "text.enhance"
  | (string & {}); // backend may have more

export type JobState =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type Job = {
  id: string;
  kind: JobKind;
  state: JobState;
  priority: number;
  project: string | null;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  attempts: number;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
};

export type JobCreatePayload = {
  kind: JobKind;
  payload: Record<string, unknown>;
  project?: string | null;
  priority?: number;
};

export type ImageRecord = {
  id: string;
  path: string;
  prompt: string;
  project: string | null;
  model: string | null;
  rating: number;
  favorite: boolean;
  tags: string[];
  notes: string;
  metadata: Record<string, unknown>;
  created_at: number;
};

export type Preset = {
  id: string;
  name: string;
  kind: string;
  era: string;
  description: string;
  model: string;
  prompt_template: string;
  prompt_prefix: string;
  prompt_suffix: string;
  negative_prompt: string;
  sampler: string;
  scheduler: string;
  steps: number;
  cfg_scale: number;
  width: number;
  height: number;
  loras: Array<Record<string, unknown>>;
};

export type CinemaReport = {
  blocked: boolean;
  score: number;
  warnings: string[];
  suggestions: string[];
  augmented_prompt: string;
  matched_rules: string[];
};

export type Scene = {
  number: number;
  heading: string;
  location: string;
  time_of_day: string;
  characters: string[];
  dialogue: Array<{
    character: string;
    line: string;
    parenthetical?: string;
  }>;
  action: string;
  prompt: string;
};

export type CostSummary = {
  total_usd: number;
  by_project: Array<{
    project: string;
    total_cost: number;
    entries: number;
  }>;
  by_kind: Array<{
    kind: string;
    total_cost: number;
    entries: number;
  }>;
};

export type TimeseriesPoint = {
  bucket: number;
  cost: number;
  entries: number;
};

export type BackupResult = {
  path: string;
  size_bytes: number;
  verified: boolean;
  duration_ms: number;
};

export type ProjectRecord = {
  id: string;
  name: string;
  concept: string;
  logline: string;
  style?: string;
  characters?: string[];
};

export type Event = {
  id?: string;
  kind: string;
  payload: Record<string, unknown>;
  timestamp: number;
  source: string;
};

export type EventKind =
  | "job.enqueued"
  | "job.started"
  | "job.completed"
  | "job.failed"
  | "job.cancelled"
  | "image.added"
  | "image.rated"
  | "image.removed"
  | "canvas.saved"
  | "project.created"
  | "project.updated"
  | "node.registered"
  | "node.health_changed"
  | "cost.recorded"
  | "plugin.loaded"
  | "plugin.unloaded"
  | "cache.hit"
  | "cache.miss"
  | "custom";

export const JOB_KINDS: JobKind[] = [
  "image.generate",
  "image.upscale",
  "video.render",
  "audio.synth",
  "text.enhance",
];

export const JOB_STATES: JobState[] = [
  "pending",
  "running",
  "completed",
  "failed",
  "cancelled",
];
