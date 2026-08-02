"use client";

import { useState, useRef, ChangeEvent, DragEvent } from "react";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea, Label, Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Clapperboard,
  AlertTriangle,
  Lightbulb,
  CheckCircle2,
  FileText,
  Sparkles,
  Film,
  Play,
  Check,
  Video,
  Link,
  Cpu,
  DollarSign,
  Clock,
  Layers,
} from "lucide-react";
import type { CinemaReport, Scene } from "@/lib/types";

type Tab = "openmontage" | "reference_video" | "parse" | "evaluate";

export default function CinemaPage() {
  const [tab, setTab] = useState<Tab>("openmontage");

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/80 pb-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight font-sans flex items-center gap-2.5">
            <Clapperboard className="h-6 w-6 text-amber-400" />
            Cinema & Video Production Suite
          </h2>
          <p className="text-sm text-fg-muted">
            Pipelines de produção de vídeo generativo (OpenMontage Engine), deconstrução de referências e avaliação de câmeras
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs bg-bg-muted/80 px-3 py-1.5 rounded border border-border">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>VIRTUAL STAGE READY</span>
        </div>
      </div>

      {/* Mode Selector */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={tab === "openmontage" ? "primary" : "secondary"}
          onClick={() => setTab("openmontage")}
        >
          <Film className="h-4 w-4 mr-1.5 inline-block text-amber-400" />
          OpenMontage Pipelines
        </Button>

        <Button
          variant={tab === "reference_video" ? "primary" : "secondary"}
          onClick={() => setTab("reference_video")}
        >
          <Video className="h-4 w-4 mr-1.5 inline-block text-cyan-400" />
          Decompositor de Referência
        </Button>

        <Button
          variant={tab === "parse" ? "primary" : "secondary"}
          onClick={() => setTab("parse")}
        >
          <FileText className="h-4 w-4 mr-1.5 inline-block" />
          Processador de Roteiro
        </Button>

        <Button
          variant={tab === "evaluate" ? "primary" : "secondary"}
          onClick={() => setTab("evaluate")}
        >
          <Clapperboard className="h-4 w-4 mr-1.5 inline-block" />
          Avaliador de Prompts
        </Button>
      </div>

      {tab === "openmontage" && <OpenMontageTab />}
      {tab === "reference_video" && <ReferenceVideoTab />}
      {tab === "parse" && <ParseTab />}
      {tab === "evaluate" && <EvaluateTab />}
    </div>
  );
}

function OpenMontageTab() {
  const { data: pipelinesData } = useSWR<{ items: any[]; count: number }>(
    "/api/proxy/openmontage/pipelines",
    swrFetcher
  );
  const pipelines = pipelinesData?.items || [];

  const [selectedPipeline, setSelectedPipeline] = useState<string>("cyberpunk_trailer");
  const [prompt, setPrompt] = useState("A lone hacker navigating a neon-lit rain cityscape seeking quantum codes.");
  const [aspectRatio, setAspectRatio] = useState<"2.39:1" | "16:9" | "9:16">("2.39:1");
  const [showGuides, setShowGuides] = useState(true);
  const [running, setRunning] = useState(false);
  const [jobResult, setJobResult] = useState<any | null>(null);

  async function handleRunPipeline() {
    setRunning(true);
    setJobResult(null);
    try {
      const res = await fetch("/api/proxy/openmontage/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pipeline_id: selectedPipeline,
          prompt,
          aspect_ratio: aspectRatio,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setJobResult(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Pipeline Selection Cards */}
      <div className="space-y-2">
        <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-fg-subtle">
          1. Selecionar Pipeline de Produção (Preset)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {pipelines.map((p) => {
            const isSelected = p.id === selectedPipeline;
            return (
              <Card
                key={p.id}
                onClick={() => setSelectedPipeline(p.id)}
                className={`cursor-pointer transition-all border ${
                  isSelected
                    ? "border-amber-500 ring-2 ring-amber-500/20 bg-slate-900/90 shadow-lg"
                    : "border-border hover:border-fg-subtle/50 bg-card/60"
                }`}
              >
                <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0 p-3.5">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Film className={`h-4 w-4 ${isSelected ? "text-amber-400" : "text-fg-subtle"}`} />
                    <span>{p.name}</span>
                  </CardTitle>
                  <Badge variant={isSelected ? "brand" : "outline"} className="text-[10px] font-mono">
                    {p.estimated_duration}
                  </Badge>
                </CardHeader>

                <CardContent className="p-3.5 pt-0 space-y-2.5">
                  <p className="text-xs text-fg-muted leading-relaxed line-clamp-2">
                    {p.description}
                  </p>

                  <div className="flex flex-wrap gap-1 text-[10px]">
                    {p.tools.map((t: string) => (
                      <span
                        key={t}
                        className="px-1.5 py-0.5 rounded bg-bg-muted font-mono border border-border text-fg-subtle"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Director Console & Cinema Viewport */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: Control Deck (5 cols) */}
        <Card className="lg:col-span-5 border-border bg-slate-950/80 backdrop-blur">
          <CardHeader className="pb-3 border-b border-border/60">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-amber-400" />
                <span>Control Deck / Direção</span>
              </span>
              <span className="text-[10px] text-fg-subtle">PIPELINE: {selectedPipeline}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-mono text-fg-subtle flex justify-between">
                <span>CONCEITO DA CENA & DIRETRIZES DE CÂMERA</span>
                <span className="text-amber-400/80">PROMPT</span>
              </Label>
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={5}
                placeholder="Descreva a visão da cena, iluminação, movimento de câmera e atmosfera..."
                className="text-xs font-mono bg-bg/90 border-border focus:border-amber-500"
              />
            </div>

            {/* Controls */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-fg-subtle">ENQUADRAMENTO / ASPECT</Label>
                <select
                  value={aspectRatio}
                  onChange={(e: any) => setAspectRatio(e.target.value)}
                  className="w-full h-8 rounded border border-border bg-bg px-2 text-xs font-mono focus:outline-none focus:border-amber-500"
                >
                  <option value="2.39:1">2.39:1 Anamórfico</option>
                  <option value="16:9">16:9 Widescreen</option>
                  <option value="9:16">9:16 Vertical</option>
                </select>
              </div>

              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-fg-subtle">GUIAS DE CÂMERA</Label>
                <button
                  type="button"
                  onClick={() => setShowGuides(!showGuides)}
                  className={`w-full h-8 rounded border text-xs font-mono transition-colors ${
                    showGuides
                      ? "border-amber-500/50 bg-amber-500/10 text-amber-400"
                      : "border-border bg-bg text-fg-subtle"
                  }`}
                >
                  {showGuides ? "Regra dos Terços [ON]" : "Regra dos Terços [OFF]"}
                </button>
              </div>
            </div>

            <div className="pt-2">
              <Button
                onClick={handleRunPipeline}
                disabled={running}
                className="w-full bg-gradient-to-r from-amber-500 to-amber-600 text-black font-bold hover:from-amber-400 hover:to-amber-500 shadow-lg shadow-amber-500/20 py-2.5 h-auto text-xs font-mono uppercase tracking-wider"
              >
                <Play className="h-4 w-4 mr-2 fill-current" />
                {running ? "Renderizando Pipeline no Backlot…" : "Renderizar Pipeline de Vídeo"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Right: Cinema Viewport Monitor (7 cols) */}
        <Card className="lg:col-span-7 border-border bg-slate-950 flex flex-col justify-between overflow-hidden">
          <CardHeader className="py-2.5 px-4 border-b border-border/80 bg-slate-900/50 flex flex-row items-center justify-between space-y-0">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping" />
              <span className="text-xs font-mono font-bold text-fg uppercase tracking-widest">
                STAGE MONITOR 01
              </span>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-mono text-fg-subtle">
              <span className="text-amber-400 font-semibold">ASPECT: {aspectRatio}</span>
              <span>TIMECODE: <span className="text-emerald-400">00:00:04:18</span></span>
            </div>
          </CardHeader>

          <CardContent className="p-4 flex-1 flex flex-col justify-center">
            {jobResult ? (
              <div className="space-y-3">
                <div className="relative w-full rounded overflow-hidden border border-border bg-black monitor-frame">
                  <video
                    src={jobResult.data.output_video_url}
                    controls
                    autoPlay
                    className="w-full h-auto max-h-[380px] object-contain mx-auto"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono bg-slate-900/80 p-2.5 rounded border border-border/60">
                  <div className="text-fg-subtle">
                    CUSTO ESTIMADO: <span className="text-emerald-400">{jobResult.data.cost_estimate}</span>
                  </div>
                  <div className="text-right text-fg-subtle">
                    QUALIDADE: <span className="text-amber-400">{(jobResult.data.quality_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="relative w-full aspect-video rounded overflow-hidden border border-border/80 bg-black flex flex-col items-center justify-center p-6 text-center monitor-frame group">
                {/* Visual Guides overlay */}
                {showGuides && <div className="absolute inset-0 cinema-frame-guides opacity-30 pointer-events-none" />}

                {/* Corner Markers */}
                <div className="absolute top-2 left-2 text-[10px] font-mono text-amber-500/70">[ 2.39:1 CAM A ]</div>
                <div className="absolute top-2 right-2 text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> STBY
                </div>
                <div className="absolute bottom-2 left-2 text-[10px] font-mono text-fg-subtle">FPS: 24.00</div>
                <div className="absolute bottom-2 right-2 text-[10px] font-mono text-fg-subtle">LENS: 35mm Prime</div>

                <div className="space-y-3 max-w-sm z-10">
                  <div className="h-12 w-12 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400 group-hover:scale-110 transition-transform">
                    <Film className="h-6 w-6" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold font-sans text-fg">Viewport do Monitor de Gravação</p>
                    <p className="text-xs text-fg-subtle font-mono">
                      Configure o prompt no Control Deck e clique em "Renderizar Pipeline" para pré-visualizar a saída de vídeo em tempo real.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ReferenceVideoTab() {
  const [videoUrl, setVideoUrl] = useState("https://youtube.com/watch?v=quantum_demo");
  const [topic, setTopic] = useState("quantum computing");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  async function analyze() {
    setLoading(true);
    try {
      const res = await fetch("/api/proxy/openmontage/reference-video", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: videoUrl, topic }),
      });
      if (res.ok) {
        setResult(await res.json());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-accent/40">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Video className="h-4 w-4 text-brand-400" />
            <span>Start From A Video You Already Love</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-fg-muted">
            Paste a reference YouTube, Short, TikTok, or Reels video link. The agent will analyze transcript, pacing, and visual hook style, then generate 3 production proposals tailored to your topic.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs">Reference Video URL / Link</Label>
              <Input
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                className="text-xs font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Your Target Topic / Angle</Label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. quantum computing, AI agents"
                className="text-xs"
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button onClick={analyze} disabled={loading}>
              <Sparkles className="h-4 w-4 mr-1.5 text-amber-400" />
              {loading ? "Deconstructing Video…" : "Deconstruct & Generate Concepts"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Deconstruction Results & Proposals */}
      {result && (
        <div className="space-y-4">
          {/* Analysis Card */}
          <Card className="bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Layers className="h-4 w-4 text-accent" />
                <span>Reference Deconstruction Analysis</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-2.5 rounded bg-bg-subtle border border-border">
                <span className="text-[10px] text-fg-subtle block">PACING & CUTS</span>
                <span className="text-fg font-semibold">{result.analysis.detected_pacing}</span>
              </div>
              <div className="p-2.5 rounded bg-bg-subtle border border-border">
                <span className="text-[10px] text-fg-subtle block">AUDIO & VOICE</span>
                <span className="text-fg font-semibold">{result.analysis.audio_style}</span>
              </div>
              <div className="p-2.5 rounded bg-bg-subtle border border-border">
                <span className="text-[10px] text-fg-subtle block">VISUAL STYLE</span>
                <span className="text-fg font-semibold">{result.analysis.visual_style}</span>
              </div>
              <div className="p-2.5 rounded bg-bg-subtle border border-border">
                <span className="text-[10px] text-fg-subtle block">STORY STRUCTURE</span>
                <span className="text-fg font-semibold">{result.analysis.structure}</span>
              </div>
            </CardContent>
          </Card>

          {/* Generated Production Concepts */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {result.concepts.map((c: any, idx: number) => (
              <Card key={idx} className="border-border hover:border-accent/50 transition-colors">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-bold flex items-center justify-between">
                    <span>{c.title}</span>
                    <Badge variant="brand" className="text-[10px]">
                      {c.cost_estimate}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs text-fg-muted leading-relaxed line-clamp-3">
                    {c.logline}
                  </p>
                  <Button size="sm" variant="secondary" className="w-full text-xs">
                    <Play className="h-3.5 w-3.5 mr-1" />
                    Launch Concept Pipeline
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EvaluateTab() {
  const [prompt, setPrompt] = useState("a man on horseback with a smartphone");
  const [era, setEra] = useState("1920-1930");
  const [report, setReport] = useState<CinemaReport | null>(null);
  const [loading, setLoading] = useState(false);

  async function evaluate() {
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/cinema/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          context: era ? { era } : {},
        }),
      });
      if (r.ok) setReport(await r.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Input</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label>Prompt</Label>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={4}
            />
          </div>
          <div>
            <Label>Era (optional)</Label>
            <Input
              value={era}
              onChange={(e) => setEra(e.target.value)}
              placeholder="e.g. '1920-1930', 'pre-1973'"
            />
          </div>
          <Button onClick={evaluate} disabled={loading} className="w-full">
            <Clapperboard className="h-4 w-4" />
            {loading ? "Evaluating…" : "Evaluate"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span className="flex items-center gap-2">
              Verdict
              {report && (
                <Badge variant={report.blocked ? "danger" : "success"}>
                  {report.blocked ? "BLOCKED" : "PASSED"}
                </Badge>
              )}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!report ? (
            <p className="text-sm text-fg-muted">
              Run an evaluation to see authenticity results & cinematic warnings.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="p-3 bg-bg border border-border rounded space-y-2 font-mono">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-fg-subtle">CINEMATIC AUTHENTICITY SCORE</span>
                  <span className="text-fg font-bold text-sm">
                    {(report.score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const SAMPLE_MARKDOWN_SCRIPT = `# INT. KITCHEN - DAY

ALICE stands near the window preparing morning tea.
`;

function ParseTab() {
  const [text, setText] = useState(SAMPLE_MARKDOWN_SCRIPT);
  const [scenes, setScenes] = useState<Scene[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function parseScriptOnly() {
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/cinema/parse-script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, hint: ".md" }),
      });
      if (r.ok) {
        const data = await r.json();
        setScenes(data.scenes);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4 text-accent" />
            Script Text Editor
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className="font-mono text-xs"
          />
          <Button onClick={parseScriptOnly} disabled={loading} className="w-full">
            <FileText className="h-4 w-4 mr-1.5" />
            {loading ? "Processing…" : "Parse scenes"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-emerald-400" />
            {scenes ? `${scenes.length} scene(s) extracted` : "Parsed Output"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!scenes ? (
            <p className="text-sm text-fg-muted">Click "Parse scenes" to inspect script breakdown.</p>
          ) : (
            <div className="space-y-3 font-mono text-xs">
              {scenes.map((s) => (
                <div key={s.number} className="p-3 rounded border border-border bg-bg-subtle">
                  <span className="text-accent font-bold">Scene {s.number}: {s.heading}</span>
                  <p className="text-fg-muted mt-1">{s.action}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
