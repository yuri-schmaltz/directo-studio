"use client";

import { useState } from "react";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Film, Play, AlertCircle, CheckCircle, Clock } from "lucide-react";
import type { Job } from "@/lib/types";

interface Project {
  id: string;
  name: string;
  concept: string;
}

export default function AnimaticsPage() {
  const { data: jobsData, mutate: mutateJobs } = useSWR<{ items: Job[] }>(
    "/api/proxy/jobs?limit=50",
    swrFetcher,
    { refreshInterval: 5000 }
  );

  const { data: projectsData } = useSWR<{ items: Project[] }>(
    "/api/proxy/projects",
    swrFetcher
  );

  const [projectId, setProjectId] = useState("");
  const [title, setTitle] = useState("Animatic");
  const [backendType, setBackendType] = useState("mock");
  const [customModel, setCustomModel] = useState("wan2.1-i2v");
  const [customEndpoint, setCustomEndpoint] = useState("http://localhost:8001/generate");
  const [resolution, setResolution] = useState("1280x720");
  const [fps, setFps] = useState("24");
  const [musicPath, setMusicPath] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const projects = projectsData?.items || [];
  const animaticJobs = jobsData?.items.filter(j => j.kind === "animatic.generate") || [];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId) {
      setError("Please select a project.");
      return;
    }

    setError(null);
    setSuccess(null);
    setSubmitting(true);

    try {
      const backendVal = backendType === "custom" ? customModel : backendType;
      const endpointVal = backendType === "custom" ? customEndpoint : null;

      const res = await fetch("/api/proxy/animatics", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          project_id: projectId,
          title,
          backend: backendVal,
          backend_endpoint: endpointVal,
          fps: parseInt(fps),
          resolution: resolution.split("x").map(Number),
          music_path: musicPath || null,
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed: ${res.statusText}`);
      }

      const data = await res.json();
      setSuccess(`Job successfully enqueued: ID ${data.job_id}`);
      mutateJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to trigger generation");
    } finally {
      setSubmitting(false);
    }
  }

  function getStatusBadge(state: string) {
    switch (state) {
      case "completed":
        return <Badge variant="success">Completed</Badge>;
      case "failed":
        return <Badge variant="danger">Failed</Badge>;
      case "running":
        return <Badge variant="brand" className="animate-pulse">Running</Badge>;
      default:
        return <Badge variant="default">Pending</Badge>;
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/80 pb-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight font-sans flex items-center gap-2.5">
            <Film className="h-6 w-6 text-amber-400" />
            Estúdio de Animáticas & Storyboard
          </h2>
          <p className="text-sm text-fg-muted">
            Gere sequências de storyboards em movimento (animáticas) a partir dos quadros e painéis do projeto.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs bg-bg-muted/80 px-3 py-1.5 rounded border border-border">
          <span className="text-fg-subtle">SHOTS ATIVOS:</span>
          <span className="text-amber-400 font-bold">04 QUADROS</span>
        </div>
      </div>

      {/* Storyboard Filmstrip / Timeline Preview */}
      <Card className="border-border bg-slate-950 p-4 space-y-3">
        <div className="flex items-center justify-between font-mono text-xs border-b border-border/60 pb-2">
          <span className="text-fg-subtle flex items-center gap-2">
            <Film className="h-4 w-4 text-amber-400" />
            <span>SEQUÊNCIA DE CÂMERAS & FILMSTRIP DE SHOTS</span>
          </span>
          <span className="text-emerald-400">DURAÇÃO TOTAL: 00:12:00</span>
        </div>

        {/* Filmstrip Items */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { shot: "SHOT 01", title: "Establishing Rain City", dur: "3.0s", cam: "Wide Dolly In" },
            { shot: "SHOT 02", title: "Hacker Terminal Close", dur: "2.5s", cam: "Macro Steady" },
            { shot: "SHOT 03", title: "Neon Cyber Alley", dur: "3.5s", cam: "Pan Left Fast" },
            { shot: "SHOT 04", title: "Quantum Breach Reveal", dur: "3.0s", cam: "Zoom Out Extreme" },
          ].map((item, i) => (
            <div
              key={i}
              className="group relative rounded border border-border/80 bg-slate-900/90 p-2.5 space-y-2 hover:border-amber-500/80 transition-all cursor-pointer"
            >
              <div className="aspect-video w-full rounded bg-slate-950 border border-border/50 flex flex-col justify-between p-2 relative overflow-hidden group-hover:scale-[1.02] transition-transform">
                <div className="flex justify-between text-[10px] font-mono text-amber-400/90">
                  <span>{item.shot}</span>
                  <span>{item.dur}</span>
                </div>
                <div className="text-[10px] font-mono text-fg-subtle text-center">
                  [ {item.cam} ]
                </div>
              </div>
              <div className="text-xs font-semibold text-fg line-clamp-1">{item.title}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Creation Form */}
        <Card className="lg:col-span-1 border-border bg-slate-950/70">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 font-mono uppercase tracking-wider">
              <Film className="h-5 w-5 text-amber-400" />
              <span>Gerar Animática</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-md text-xs text-rose-400 flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {success && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-xs text-emerald-400 flex items-start gap-2">
                  <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{success}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <Label className="text-xs font-mono text-fg-subtle">PROJETO ALVO</Label>
                <Select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  className="text-xs font-mono bg-bg"
                >
                  <option value="">-- Selecionar Projeto --</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-mono text-fg-subtle">TÍTULO DA ANIMÁTICA</Label>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Título da Animática"
                  className="text-xs font-mono bg-bg"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-mono text-fg-subtle">BACKEND DE VÍDEO</Label>
                <Select
                  value={backendType}
                  onChange={(e) => setBackendType(e.target.value)}
                  className="text-xs font-mono bg-bg"
                >
                  <option value="mock">AI Video (Mock / Testes Rápidos)</option>
                  <option value="ken-burns">Ken Burns (Pan & Zoom Fallback)</option>
                  <option value="custom">Servidor AI Video Local Custom</option>
                </Select>
              </div>

              {backendType === "custom" && (
                <>
                  <div className="space-y-1.5 animate-fade-in">
                    <Label className="text-xs font-mono text-fg-subtle">ENDPOINT DA API</Label>
                    <Input
                      value={customEndpoint}
                      onChange={(e) => setCustomEndpoint(e.target.value)}
                      placeholder="ex: http://localhost:8001/generate"
                      className="text-xs font-mono bg-bg"
                    />
                  </div>
                  <div className="space-y-1.5 animate-fade-in">
                    <Label className="text-xs font-mono text-fg-subtle">MODELO DE VÍDEO</Label>
                    <Input
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="ex: wan2.1-i2v ou hunyuan-video"
                      className="text-xs font-mono bg-bg"
                    />
                  </div>
                </>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-mono text-fg-subtle">RESOLUÇÃO</Label>
                  <Select
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value)}
                    className="text-xs font-mono bg-bg"
                  >
                    <option value="1280x720">1280 x 720 (720p)</option>
                    <option value="1920x1080">1920 x 1080 (1080p)</option>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-mono text-fg-subtle">TAXA DE QUADROS</Label>
                  <Select
                    value={fps}
                    onChange={(e) => setFps(e.target.value)}
                    className="text-xs font-mono bg-bg"
                  >
                    <option value="24">24 FPS (Cinema)</option>
                    <option value="30">30 FPS (TV)</option>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-mono text-fg-subtle">TRILHA SONORA (OPCIONAL)</Label>
                <Input
                  value={musicPath}
                  onChange={(e) => setMusicPath(e.target.value)}
                  placeholder="ex: /path/to/soundtrack.mp3"
                  className="text-xs font-mono bg-bg"
                />
              </div>

              <Button
                type="submit"
                className="w-full bg-amber-500 hover:bg-amber-400 text-black font-bold font-mono text-xs uppercase"
                disabled={submitting}
              >
                <Play className="h-4 w-4 mr-2 fill-current" />
                {submitting ? "Enviando Tarefa..." : "Gerar Sequência de Animática"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Jobs List */}
        <Card className="lg:col-span-2 border-border bg-slate-950/70">
          <CardHeader>
            <CardTitle className="text-base font-mono uppercase tracking-wider">
              Histórico de Renders de Animática
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {animaticJobs.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-border/80 rounded-lg bg-bg-muted/30">
                <Clock className="h-8 w-8 text-fg-subtle mx-auto mb-2" />
                <p className="text-sm font-medium">Nenhum render de animática agendado</p>
                <p className="text-xs text-fg-subtle font-mono">
                  Configure o projeto e clique em "Gerar Sequência de Animática" para iniciar a fila.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border overflow-hidden rounded-md border border-border">
                {animaticJobs.map((job) => (
                  <div key={job.id} className="p-4 hover:bg-bg-muted/20 transition-colors">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-fg-muted">
                          #{job.id.substring(0, 8)}
                        </span>
                        <Badge variant="default">{String(job.payload["backend"] || "mock")}</Badge>
                      </div>
                      {getStatusBadge(job.state)}
                    </div>
                    <div className="text-sm font-medium mb-1">
                      Projeto: <span className="text-amber-400">{job.project || "N/A"}</span>
                    </div>
                    {Boolean(job.result && job.result["output_path"]) && (
                      <div className="text-xs text-fg-muted mt-2 p-2 bg-emerald-500/5 border border-emerald-500/10 rounded font-mono break-all">
                        Output: {job.result ? String(job.result["output_path"]) : ""}
                      </div>
                    )}
                    {job.error && (
                      <div className="text-xs text-rose-400 mt-2 p-2 bg-rose-500/5 border border-rose-500/10 rounded font-mono break-all">
                        Erro: {job.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
