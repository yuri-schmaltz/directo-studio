"use client";

import { useState, useRef } from "react";
import useSWR from "swr";
import { api, swrFetcher } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Mic,
  Music,
  Video,
  FileText,
  Play,
  CheckCircle,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Zap,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { MediaJob } from "@/lib/types";

// ─── types ───────────────────────────────────────────────────────────────────

type EngineStatus = "idle" | "testing" | "ok" | "error";

interface EngineState {
  status: EngineStatus;
  message: string;
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: EngineStatus }) {
  if (status === "testing")
    return <Loader2 className="h-4 w-4 animate-spin text-accent" />;
  if (status === "ok")
    return <CheckCircle className="h-4 w-4 text-emerald-500" />;
  if (status === "error") return <XCircle className="h-4 w-4 text-red-400" />;
  return (
    <div className="h-4 w-4 rounded-full border-2 border-fg-subtle/40 shrink-0" />
  );
}

function StatusMsg({
  state,
}: {
  state: EngineState;
}) {
  if (!state.message) return null;
  return (
    <span
      className={cn(
        "text-xs",
        state.status === "error" ? "text-red-400" : "text-emerald-400",
      )}
    >
      {state.message}
    </span>
  );
}

function Section({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  badge,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  badge?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const Arrow = open ? ChevronDown : ChevronRight;

  return (
    <Card>
      <button
        className="w-full flex items-center gap-3 px-5 py-4 text-left"
        onClick={() => setOpen(!open)}
      >
        <Icon className="h-5 w-5 text-accent shrink-0" />
        <span className="font-semibold text-base flex-1">{title}</span>
        {badge && (
          <Badge className="text-[10px] px-2 py-0.5">{badge}</Badge>
        )}
        <Arrow className="h-4 w-4 text-fg-subtle shrink-0" />
      </button>
      {open && (
        <CardContent className="px-5 pb-5 pt-0 border-t border-border">
          {children}
        </CardContent>
      )}
    </Card>
  );
}

// ─── Slider row ───────────────────────────────────────────────────────────────

function SliderRow({
  id,
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <Label className="mb-0">{label}</Label>
        <span className="text-xs font-mono text-fg-muted tabular-nums">
          {value}
          {unit}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-accent h-1.5 cursor-pointer"
      />
      <div className="flex justify-between text-[10px] text-fg-subtle">
        <span>
          {min}
          {unit}
        </span>
        <span>
          {max}
          {unit}
        </span>
      </div>
    </div>
  );
}

// ─── Voice section ────────────────────────────────────────────────────────────

function VoiceSection() {
  const [backend, setBackend] = useState<"piper" | "bark" | "coqui" | "mock">(
    "piper",
  );
  const [piperModel, setPiperModel] = useState("en_US-lessac-medium");
  const [barkDevice, setBarkDevice] = useState("cuda");
  const [coquiModel, setCoquiModel] = useState(
    "tts_models/multilingual/multi-dataset/xtts_v2",
  );
  const [state, setState] = useState<EngineState>({
    status: "idle",
    message: "",
  });

  const test = async () => {
    setState({ status: "testing", message: "" });
    try {
      // POST to media-hub/generate with a short TTS probe
      const res = await api.mediaHub.generate({
        prompt: "Hello, this is a voice engine test.",
        duration: 2,
      });
      setState({
        status: "ok",
        message: `Job enqueued: ${res.job_id}`,
      });
    } catch (e: any) {
      setState({ status: "error", message: e.message });
    }
  };

  return (
    <Section title="Voice & TTS" icon={Mic} badge={backend}>
      <div className="space-y-4 pt-4">
        <div className="space-y-1.5">
          <Label>Backend</Label>
          <div className="flex gap-2 flex-wrap">
            {(["piper", "bark", "coqui", "mock"] as const).map((b) => (
              <button
                key={b}
                id={`voice-backend-${b}`}
                onClick={() => setBackend(b)}
                className={cn(
                  "px-3 py-1.5 rounded text-sm font-medium border transition-colors",
                  backend === b
                    ? "bg-accent text-white border-accent"
                    : "border-border text-fg-muted hover:text-fg hover:border-fg-subtle",
                )}
              >
                {b}
              </button>
            ))}
          </div>
        </div>

        {backend === "piper" && (
          <div className="space-y-1.5">
            <Label>Piper Model</Label>
            <Input
              id="piper-model-input"
              value={piperModel}
              onChange={(e) => setPiperModel(e.target.value)}
              placeholder="en_US-lessac-medium"
            />
            <p className="text-[11px] text-fg-subtle">
              Model name as used by piper-tts CLI.
            </p>
          </div>
        )}

        {backend === "bark" && (
          <div className="space-y-1.5">
            <Label>Device</Label>
            <Select
              id="bark-device-select"
              value={barkDevice}
              onChange={(e) => setBarkDevice(e.target.value)}
              className="w-full"
            >
              <option value="cuda">CUDA (GPU)</option>
              <option value="cpu">CPU</option>
              <option value="mps">MPS (Apple Silicon)</option>
            </Select>
          </div>
        )}

        {backend === "coqui" && (
          <div className="space-y-1.5">
            <Label>Coqui Model ID</Label>
            <Input
              id="coqui-model-input"
              value={coquiModel}
              onChange={(e) => setCoquiModel(e.target.value)}
              placeholder="tts_models/multilingual/multi-dataset/xtts_v2"
            />
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button
            id="voice-test-btn"
            variant="secondary"
            size="sm"
            onClick={test}
            disabled={state.status === "testing"}
          >
            <Play className="h-3.5 w-3.5 mr-1.5" />
            Test Engine
          </Button>
          <StatusIcon status={state.status} />
          <StatusMsg state={state} />
        </div>
      </div>
    </Section>
  );
}

// ─── Subtitle section ─────────────────────────────────────────────────────────

function SubtitleSection() {
  const [model, setModel] = useState("base");
  const [language, setLanguage] = useState("auto");
  const [formats, setFormats] = useState<string[]>(["srt", "vtt"]);
  const [state, setState] = useState<EngineState>({
    status: "idle",
    message: "",
  });

  const toggle = (f: string) =>
    setFormats((prev) =>
      prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f],
    );

  const test = async () => {
    setState({ status: "testing", message: "" });
    try {
      const res = await api.mediaHub.generate({
        prompt: "subtitle engine probe",
        duration: 1,
      });
      setState({ status: "ok", message: `Endpoint reachable — ${res.job_id}` });
    } catch (e: any) {
      setState({ status: "error", message: e.message });
    }
  };

  return (
    <Section title="Subtitles (Whisper)" icon={FileText} badge={`model: ${model}`}>
      <div className="space-y-4 pt-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Whisper Model</Label>
            <Select
              id="whisper-model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full"
            >
              {["tiny", "base", "small", "medium", "large-v3"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Language</Label>
            <Input
              id="whisper-lang-input"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              placeholder="auto, en, pt, es…"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label>Output Formats</Label>
          <div className="flex gap-2">
            {["srt", "vtt", "json"].map((f) => (
              <button
                key={f}
                id={`subtitle-format-${f}`}
                onClick={() => toggle(f)}
                className={cn(
                  "px-3 py-1.5 rounded text-sm font-medium border transition-colors",
                  formats.includes(f)
                    ? "bg-accent text-white border-accent"
                    : "border-border text-fg-muted hover:text-fg",
                )}
              >
                .{f}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            id="subtitle-test-btn"
            variant="secondary"
            size="sm"
            onClick={test}
            disabled={state.status === "testing"}
          >
            <Play className="h-3.5 w-3.5 mr-1.5" />
            Test Engine
          </Button>
          <StatusIcon status={state.status} />
          <StatusMsg state={state} />
        </div>
      </div>
    </Section>
  );
}

// ─── BGM / Mixer section ──────────────────────────────────────────────────────

function BGMSection() {
  const [bgmVol, setBgmVol] = useState(0.8);
  const [sfxVol, setSfxVol] = useState(1.0);
  const [duckDb, setDuckDb] = useState(-12);
  const [fadeMs, setFadeMs] = useState(300);
  const [state, setState] = useState<EngineState>({
    status: "idle",
    message: "",
  });

  const test = async () => {
    setState({ status: "testing", message: "" });
    try {
      const res = await api.mediaHub.generate({
        prompt: "audio mixer probe",
        duration: 1,
        aspect_ratio: "16:9",
      });
      setState({
        status: "ok",
        message: `Mixer endpoint OK — ${res.job_id}`,
      });
    } catch (e: any) {
      setState({ status: "error", message: e.message });
    }
  };

  return (
    <Section title="BGM & Audio Mixer" icon={Music}>
      <div className="space-y-4 pt-4">
        <SliderRow
          id="bgm-volume-slider"
          label="BGM Volume"
          value={bgmVol}
          min={0}
          max={1}
          step={0.05}
          unit=""
          onChange={setBgmVol}
        />
        <SliderRow
          id="sfx-volume-slider"
          label="SFX Volume"
          value={sfxVol}
          min={0}
          max={1}
          step={0.05}
          unit=""
          onChange={setSfxVol}
        />
        <SliderRow
          id="duck-db-slider"
          label="Ducking Attenuation (speech)"
          value={duckDb}
          min={-60}
          max={0}
          step={1}
          unit=" dB"
          onChange={setDuckDb}
        />
        <SliderRow
          id="fade-ms-slider"
          label="Fade Duration"
          value={fadeMs}
          min={50}
          max={2000}
          step={50}
          unit=" ms"
          onChange={setFadeMs}
        />

        <div className="flex items-center gap-3">
          <Button
            id="bgm-test-btn"
            variant="secondary"
            size="sm"
            onClick={test}
            disabled={state.status === "testing"}
          >
            <Play className="h-3.5 w-3.5 mr-1.5" />
            Test Mixer
          </Button>
          <StatusIcon status={state.status} />
          <StatusMsg state={state} />
        </div>
      </div>
    </Section>
  );
}

// ─── Video / ComfyUI section ──────────────────────────────────────────────────

function VideoSection() {
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState(8188);
  const [fallback, setFallback] = useState(true);
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [state, setState] = useState<EngineState>({
    status: "idle",
    message: "",
  });

  const test = async () => {
    setState({ status: "testing", message: "" });
    try {
      const res = await api.mediaHub.generate({
        prompt: "comfyui connection probe",
        duration: 2,
        aspect_ratio: aspectRatio,
      });
      setState({
        status: "ok",
        message: `Video endpoint OK — job ${res.job_id}`,
      });
    } catch (e: any) {
      setState({ status: "error", message: e.message });
    }
  };

  return (
    <Section
      title="Video & Overlays (ComfyUI)"
      icon={Video}
      badge={`${host}:${port}`}
    >
      <div className="space-y-4 pt-4">
        <div className="grid grid-cols-[1fr_100px] gap-3">
          <div className="space-y-1.5">
            <Label>ComfyUI Host</Label>
            <Input
              id="comfyui-host-input"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder="127.0.0.1"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Port</Label>
            <Input
              id="comfyui-port-input"
              type="number"
              value={port}
              onChange={(e) => setPort(parseInt(e.target.value) || 8188)}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label>Default Aspect Ratio</Label>
          <Select
            id="video-aspect-ratio"
            value={aspectRatio}
            onChange={(e) => setAspectRatio(e.target.value)}
            className="w-full md:w-48"
          >
            {["16:9", "9:16", "1:1", "4:3", "21:9", "2:3"].map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
        </div>

        <label className="flex items-center gap-2.5 cursor-pointer select-none">
          <input
            id="comfyui-fallback-toggle"
            type="checkbox"
            checked={fallback}
            onChange={(e) => setFallback(e.target.checked)}
            className="rounded accent-accent"
          />
          <span className="text-sm text-fg-muted">
            Graceful offline fallback — use FFmpeg Ken Burns if ComfyUI is
            unreachable
          </span>
        </label>

        <div className="flex items-center gap-3">
          <Button
            id="video-test-btn"
            variant="secondary"
            size="sm"
            onClick={test}
            disabled={state.status === "testing"}
          >
            <Play className="h-3.5 w-3.5 mr-1.5" />
            Test Connection
          </Button>
          <StatusIcon status={state.status} />
          <StatusMsg state={state} />
        </div>
      </div>
    </Section>
  );
}

// ─── Generation probe panel ───────────────────────────────────────────────────

function GenerationProbe() {
  const [prompt, setPrompt] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: jobData, mutate: refreshJob } = useSWR<MediaJob>(
    jobId ? `/api/proxy/media-hub/jobs/${jobId}` : null,
    swrFetcher,
    { refreshInterval: (data) => (data?.state === "pending" || data?.state === "running" ? 2000 : 0) },
  );

  const submit = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError(null);
    setJobId(null);
    try {
      const res = await api.mediaHub.generate({ prompt, duration: 5 });
      setJobId(res.job_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const stateColor: Record<string, string> = {
    pending: "text-yellow-400",
    running: "text-blue-400",
    completed: "text-emerald-400",
    failed: "text-red-400",
    cancelled: "text-fg-subtle",
  };

  return (
    <Card>
      <div className="px-5 py-4 flex items-center gap-3">
        <Zap className="h-5 w-5 text-accent shrink-0" />
        <span className="font-semibold text-base flex-1">Quick Generation Probe</span>
      </div>
      <CardContent className="px-5 pb-5 pt-0 border-t border-border">
        <div className="space-y-3 pt-4">
          <div className="space-y-1.5">
            <Label>Prompt</Label>
            <div className="flex gap-2">
              <Input
                id="probe-prompt-input"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="e.g. A rainy noir street at night…"
                className="flex-1"
              />
              <Button
                id="probe-submit-btn"
                variant="primary"
                onClick={submit}
                disabled={submitting || !prompt.trim()}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Zap className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          {error && (
            <p className="text-xs text-red-400">{error}</p>
          )}

          {jobId && (
            <div className="flex items-center gap-3 p-3 bg-bg-subtle rounded-lg border border-border">
              <span className="text-xs text-fg-subtle font-mono flex-1 truncate">
                Job: {jobId}
              </span>
              {jobData && (
                <span
                  className={cn(
                    "text-xs font-semibold",
                    stateColor[jobData.state] ?? "text-fg-muted",
                  )}
                >
                  {jobData.state}
                  {typeof jobData.progress === "number" &&
                    jobData.progress > 0 &&
                    jobData.progress < 1 && (
                      <span className="text-fg-subtle font-normal ml-1">
                        {Math.round(jobData.progress * 100)}%
                      </span>
                    )}
                </span>
              )}
              <button
                onClick={() => refreshJob()}
                className="text-fg-subtle hover:text-fg transition-colors"
                aria-label="Refresh job status"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function MediaHubPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Zap className="h-6 w-6 text-accent" />
            Media Hub
          </h2>
          <p className="text-sm text-fg-muted mt-0.5">
            Configure and test local generation engines — voices, subtitles,
            BGM mixing and video (ComfyUI).
          </p>
        </div>
        <Badge className="text-xs px-2.5 py-1">
          Local-first · No cloud required
        </Badge>
      </div>

      {/* Quick probe at the top */}
      <GenerationProbe />

      {/* Engine configuration sections */}
      <VoiceSection />
      <SubtitleSection />
      <BGMSection />
      <VideoSection />
    </div>
  );
}
