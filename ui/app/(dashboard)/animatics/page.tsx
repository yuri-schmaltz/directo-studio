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
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Animatics</h2>
        <p className="text-sm text-fg-muted">
          Generate moving storyboards (animatics) from project panels asynchronously.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Creation Form */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Film className="h-5 w-5 text-brand-500" />
              Generate Animatic
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-xs text-destructive flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {success && (
                <div className="p-3 bg-success/10 border border-success/20 rounded-md text-xs text-success flex items-start gap-2">
                  <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{success}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <Label>Select Project</Label>
                <Select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                >
                  <option value="">-- Choose a project --</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label>Title</Label>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Animatic Title"
                />
              </div>

              <div className="space-y-1.5">
                <Label>Video Backend</Label>
                <Select
                  value={backendType}
                  onChange={(e) => setBackendType(e.target.value)}
                >
                  <option value="mock">AI Video (Mock / Quick testing)</option>
                  <option value="ken-burns">Ken Burns (Pan & Zoom Fallback)</option>
                  <option value="custom">Custom Local AI Video Server</option>
                </Select>
              </div>

              {backendType === "custom" && (
                <>
                  <div className="space-y-1.5 animate-fade-in">
                    <Label>API Server Endpoint URL</Label>
                    <Input
                      value={customEndpoint}
                      onChange={(e) => setCustomEndpoint(e.target.value)}
                      placeholder="e.g. http://localhost:8001/generate"
                    />
                  </div>
                  <div className="space-y-1.5 animate-fade-in">
                    <Label>Model Identifier</Label>
                    <Input
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="e.g. wan2.1-i2v or hunyuan-video"
                    />
                  </div>
                </>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>Resolution</Label>
                  <Select
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value)}
                  >
                    <option value="1280x720">1280 x 720 (720p)</option>
                    <option value="1920x1080">1920 x 1080 (1080p)</option>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label>FPS</Label>
                  <Select
                    value={fps}
                    onChange={(e) => setFps(e.target.value)}
                  >
                    <option value="24">24 FPS</option>
                    <option value="30">30 FPS</option>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label>Music File Path (Optional)</Label>
                <Input
                  value={musicPath}
                  onChange={(e) => setMusicPath(e.target.value)}
                  placeholder="e.g. /path/to/music.mp3"
                />
              </div>

              <Button type="submit" className="w-full" disabled={submitting}>
                <Play className="h-4 w-4 mr-2" />
                {submitting ? "Submitting..." : "Generate Animatic"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Jobs List */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Recent Animatic Jobs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {animaticJobs.length === 0 ? (
              <div className="text-center py-12 border border-dashed rounded-lg bg-bg-muted/30">
                <Clock className="h-8 w-8 text-fg-muted mx-auto mb-2" />
                <p className="text-sm font-medium">No animatic jobs yet</p>
                <p className="text-xs text-fg-muted">
                  Use the form on the left to trigger your first animatic render.
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
                      Project: <span className="text-brand-500">{job.project || "N/A"}</span>
                    </div>
                    {Boolean(job.result && job.result["output_path"]) && (
                      <div className="text-xs text-fg-muted mt-2 p-2 bg-success/5 border border-success/10 rounded font-mono break-all">
                        Output: {job.result ? String(job.result["output_path"]) : ""}
                      </div>
                    )}
                    {job.error && (
                      <div className="text-xs text-destructive mt-2 p-2 bg-destructive/5 border border-destructive/10 rounded font-mono break-all">
                        Error: {job.error}
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
