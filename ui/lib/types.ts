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
  url?: string;
  job_id?: string;
  params?: Record<string, any>;
};

export type Preset = {
  id: string;
  name: string;
  kind: string;
  era: string;
  description: string;
  image_url?: string;
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
  evaluation?: CinemaReport;
};

export type EvaluateScriptResponse = {
  scenes: Scene[];
  count: number;
  blocked_count: number;
  average_score: number;
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

// ─── Style Bible ─────────────────────────────────────────────────────────────

export type LoRAConfig = {
  name: string;
  path: string;
  weight: number;
  trigger_words: string[];
};

export type CharacterProfile = {
  id: string;
  name: string;
  base_prompt: string;
  visual_anchors: string[];
  loras: LoRAConfig[];
  seeds: Record<string, number>;
  reference_images: string[];
  negative_prompt: string;
};

export type EnvironmentAnchor = {
  id: string;
  name: string;
  scenario_prompt: string;
  lighting: string;
  color_palette: string[];
  style_tokens: string[];
  negative_prompt: string;
};

/** A single named style directive object — matches Python StyleDirective dataclass. */
export type StyleDirective = {
  id: string;
  name: string;
  global_prompt_prefix: string;
  global_prompt_suffix: string;
  negative_prompt: string;
  aspect_ratio: string;
  audio_voice_filters: Record<string, unknown>;
  directive_seed?: number | null;
};

/** Metadata summary returned by the list endpoint — no full objects. */
export type StyleBibleSummary = {
  id: string;
  name: string;
  version: string;
  character_count: number;
  environment_count: number;
  directive_count: number;
  created_at: number;
  updated_at: number;
};

/** Full bible object returned by GET /api/style-bible/{id} */
export type StyleBible = {
  id: string;
  name: string;
  version: string;
  characters: CharacterProfile[];
  environments: EnvironmentAnchor[];
  directives: StyleDirective[];
};

// ─── Media Hub ───────────────────────────────────────────────────────────────

export type MediaJob = {
  id: string;
  job_id: string;
  kind: string;
  state: string;
  status: string;
  progress: number;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
};

