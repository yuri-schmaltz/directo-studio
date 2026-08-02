"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import Link from "next/link";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Label, Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import {
  FolderKanban,
  Plus,
  Trash2,
  Edit3,
  Sparkles,
  Palette,
  Check,
  X,
  Sliders,
  Clapperboard,
  Wand2,
  Film,
  Zap,
  ShieldAlert,
} from "lucide-react";

interface Project {
  id: string;
  name: string;
  concept: string;
  logline?: string;
  style?: Record<string, any>;
  metadata?: Record<string, any>;
  updated_at?: number;
}

const PRESETS = [
  { id: "cinematic", label: "Cinematic Ultra", icon: Clapperboard, color: "from-amber-500/30 via-purple-900/40 to-slate-950", accent: "#f59e0b" },
  { id: "cyberpunk", label: "Cyberpunk Neon", icon: Zap, color: "from-cyan-500/30 via-fuchsia-900/40 to-slate-950", accent: "#06b6d4" },
  { id: "fantasy", label: "Dark Fantasy", icon: Wand2, color: "from-emerald-500/30 via-yellow-950/40 to-slate-950", accent: "#10b981" },
  { id: "sci-fi", label: "Deep Sci-Fi", icon: Film, color: "from-blue-500/30 via-indigo-950/40 to-slate-950", accent: "#3b82f6" },
  { id: "noir", label: "Atmospheric Noir", icon: Palette, color: "from-zinc-500/30 via-stone-900/40 to-slate-950", accent: "#a1a1aa" },
];

function getPresetConfig(presetId?: string) {
  return (
    PRESETS.find((p) => p.id === presetId) ||
    PRESETS[0]
  );
}

// Procedural AI Cover Artwork Placeholder Generator Component
function AICoverPlaceholder({
  name,
  concept,
  presetId,
}: {
  name: string;
  concept: string;
  presetId?: string;
}) {
  const config = getPresetConfig(presetId);
  const Icon = config.icon;

  // Generate deterministic gradient accents from text seed
  const seedHex = useMemo(() => {
    let hash = 0;
    const str = `${name}-${concept}-${presetId}`;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return Math.abs(hash).toString(16).padStart(6, "0").slice(0, 6);
  }, [name, concept, presetId]);

  return (
    <div className="relative h-32 w-full overflow-hidden rounded-t-xl bg-slate-950 select-none group">
      {/* Background Gradient Mesh */}
      <div
        className={`absolute inset-0 bg-gradient-to-br ${config.color} opacity-80 group-hover:scale-105 transition-transform duration-500 ease-out`}
      />

      {/* Decorative Grid SVG Overlay */}
      <svg
        className="absolute inset-0 h-full w-full opacity-20 stroke-white/10"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern id={`grid-${seedHex}`} width="16" height="16" patternUnits="userSpaceOnUse">
            <path d="M 16 0 L 0 0 0 16" fill="none" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#grid-${seedHex})`} />
      </svg>

      {/* Glowing Orb */}
      <div
        className="absolute -top-6 -right-6 h-28 w-28 rounded-full blur-2xl opacity-40 group-hover:opacity-70 transition-opacity duration-500"
        style={{ backgroundColor: config.accent }}
      />

      {/* Badge Overlay */}
      <div className="absolute top-2.5 left-2.5 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur border border-white/10 text-[10px] font-mono tracking-wide text-white/90">
        <Icon className="h-3 w-3" style={{ color: config.accent }} />
        <span>{config.label.toUpperCase()}</span>
      </div>

      {/* AI Prompt Icon */}
      <div className="absolute bottom-2.5 right-2.5 flex items-center gap-1 text-[10px] font-mono text-white/60 bg-black/40 px-1.5 py-0.5 rounded backdrop-blur">
        <Sparkles className="h-3 w-3 text-amber-400 animate-pulse" />
        <span>AI Generated</span>
      </div>

      {/* Project Initial Big Watermark */}
      <div className="absolute -bottom-4 left-3 text-5xl font-black font-mono tracking-tighter text-white/5 pointer-events-none select-none">
        {name.slice(0, 3).toUpperCase() || "PRJ"}
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const { data, mutate } = useSWR<{ items: Project[] }>(
    "/api/proxy/projects",
    swrFetcher
  );
  const projects = data?.items || [];

  // Selected project state for viewing/editing parameters
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editConcept, setEditConcept] = useState("");
  const [editLogline, setEditLogline] = useState("");
  const [editPreset, setEditPreset] = useState("cinematic");
  const [saving, setSaving] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedId),
    [projects, selectedId]
  );

  function handleSelect(p: Project) {
    if (selectedId === p.id) {
      setSelectedId(null);
      return;
    }
    setSelectedId(p.id);
    setEditName(p.name || "");
    setEditConcept(p.concept || "");
    setEditLogline(p.logline || "");
    setEditPreset(p.style?.preset || p.metadata?.preset || "cinematic");
    setSaveSuccess(false);
  }

  async function handleSave() {
    if (!selectedId) return;
    setSaving(true);
    setSaveSuccess(false);
    try {
      const res = await fetch(`/api/proxy/projects/${selectedId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName,
          concept: editConcept,
          logline: editLogline,
          style: { ...(selectedProject?.style || {}), preset: editPreset },
          metadata: { ...(selectedProject?.metadata || {}), preset: editPreset },
        }),
      });
      if (res.ok) {
        await mutate();
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      console.error("Failed to update project", err);
    } finally {
      setSaving(false);
    }
  }

  async function handleEnrichPrompt() {
    if (!selectedId) return;
    setEnriching(true);
    try {
      const res = await fetch(`/api/proxy/projects/${selectedId}/enrich-prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: editConcept || editName, target: "flux-dev" }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.enriched) {
          setEditConcept(data.enriched);
        }
      }
    } catch (err) {
      console.error("Failed to enrich prompt", err);
    } finally {
      setEnriching(false);
    }
  }

  async function handleDelete(projectId: string) {
    if (!confirm("Are you sure you want to delete this project?")) return;
    try {
      const res = await fetch(`/api/proxy/projects/${projectId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        if (selectedId === projectId) setSelectedId(null);
        mutate();
      }
    } catch (err) {
      console.error("Failed to delete project", err);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Projects</h2>
          <p className="text-sm text-fg-muted">
            Creative projects with director agents & AI visual presets
          </p>
        </div>
        <Link href="/projects/new">
          <Button>
            <Plus className="h-4 w-4" />
            New project
          </Button>
        </Link>
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon={<FolderKanban className="h-12 w-12 text-accent" />}
          title="No projects yet"
          description="Create your first creative project to bundle characters, style guides, and AI storyboards."
          action={
            <Link href="/projects/new">
              <Button>
                <Plus className="h-4 w-4" />
                Create Project
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main Grid Viewport (4 columns x 3 rows initial view, scrollable vertically) */}
          <div className="lg:col-span-3 space-y-3">
            <div className="flex items-center justify-between text-xs text-fg-subtle font-mono uppercase tracking-wider px-1">
              <span>Project Library ({projects.length})</span>
              <span>Click card to select & edit parameters</span>
            </div>

            {/* 4 columns x 3 rows scrollable grid container */}
            <div className="max-h-[calc(100vh-14rem)] overflow-y-auto pr-1.5 scrollbar-thin scrollbar-thumb-border hover:scrollbar-thumb-accent/40 rounded-xl">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 pb-2">
                {projects.map((p) => {
                  const isSelected = p.id === selectedId;
                  const currentPreset = p.style?.preset || p.metadata?.preset || "cinematic";

                  return (
                    <div
                      key={p.id}
                      onClick={() => handleSelect(p)}
                      className={`group relative cursor-pointer rounded-xl border transition-all duration-200 bg-card overflow-hidden flex flex-col justify-between ${
                        isSelected
                          ? "border-accent ring-2 ring-accent/30 shadow-[0_0_20px_rgba(234,179,8,0.15)] bg-bg-muted/40"
                          : "border-border hover:border-fg-subtle/50 hover:shadow-lg"
                      }`}
                    >
                      {/* Top AI Placeholder Cover */}
                      <AICoverPlaceholder
                        name={p.name}
                        concept={p.concept}
                        presetId={currentPreset}
                      />

                      {/* Card Body */}
                      <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
                        <div>
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-sm truncate text-fg group-hover:text-accent transition-colors">
                              {p.name}
                            </h3>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDelete(p.id);
                              }}
                              className="text-fg-subtle hover:text-danger p-1 rounded hover:bg-danger/10 transition-colors"
                              title="Delete project"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <p className="text-xs text-fg-muted line-clamp-2 mt-1 min-h-[2rem]">
                            {p.concept || p.logline || "No description provided."}
                          </p>
                        </div>

                        {/* Card Footer Badge */}
                        <div className="flex items-center justify-between pt-2 border-t border-border/40 text-[11px]">
                          <Badge variant={isSelected ? "accent" : "outline"} className="font-mono text-[10px]">
                            {p.id.slice(0, 8)}
                          </Badge>
                          <span className="text-[10px] text-fg-subtle font-mono">
                            {isSelected ? "● Selected" : "Click to edit"}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Project Parameter Editor Side Panel */}
          <div className="lg:col-span-1">
            {selectedProject ? (
              <Card className="sticky top-16 border-accent/40 bg-card/95 shadow-xl backdrop-blur">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3 border-b border-border/60">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Sliders className="h-4 w-4 text-accent" />
                    <span>Edit Parameters</span>
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => setSelectedId(null)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardHeader>

                <CardContent className="space-y-4 pt-4">
                  {/* Name Input */}
                  <div className="space-y-1.5">
                    <Label className="text-xs">Project Name</Label>
                    <Input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="Project Title"
                      className="text-xs font-semibold"
                    />
                  </div>

                  {/* Visual Preset Selector */}
                  <div className="space-y-1.5">
                    <Label className="text-xs flex items-center justify-between">
                      <span>AI Visual Preset</span>
                      <Sparkles className="h-3 w-3 text-amber-400" />
                    </Label>
                    <div className="grid grid-cols-1 gap-1.5">
                      {PRESETS.map((pr) => {
                        const Icon = pr.icon;
                        const isChosen = editPreset === pr.id;
                        return (
                          <button
                            key={pr.id}
                            type="button"
                            onClick={() => setEditPreset(pr.id)}
                            className={`flex items-center gap-2 p-2 rounded-lg border text-left text-xs transition-all ${
                              isChosen
                                ? "border-accent bg-accent/10 text-fg font-medium"
                                : "border-border/60 bg-bg-muted/30 text-fg-muted hover:border-fg-subtle"
                            }`}
                          >
                            <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: pr.accent }} />
                            <span className="flex-1 truncate">{pr.label}</span>
                            {isChosen && <Check className="h-3.5 w-3.5 text-accent" />}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Concept Input */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">Concept & Prompt</Label>
                      <button
                        type="button"
                        onClick={handleEnrichPrompt}
                        disabled={enriching}
                        className="text-[10px] font-mono text-accent hover:underline flex items-center gap-1"
                      >
                        <Sparkles className="h-3 w-3" />
                        {enriching ? "Enriching…" : "AI Enrich"}
                      </button>
                    </div>
                    <Textarea
                      value={editConcept}
                      onChange={(e) => setEditConcept(e.target.value)}
                      rows={3}
                      placeholder="Themes, worldbuilding, lighting..."
                      className="text-xs"
                    />
                  </div>

                  {/* Logline Input */}
                  <div className="space-y-1.5">
                    <Label className="text-xs">Logline Summary</Label>
                    <Input
                      value={editLogline}
                      onChange={(e) => setEditLogline(e.target.value)}
                      placeholder="One-line synopsis"
                      className="text-xs"
                    />
                  </div>

                  {/* Action Buttons */}
                  {saveSuccess && (
                    <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5" />
                      <span>Parameters saved successfully!</span>
                    </div>
                  )}

                  <div className="pt-2 flex flex-col gap-2">
                    <Button onClick={handleSave} disabled={saving} size="sm" className="w-full">
                      {saving ? "Saving…" : "Save Parameters"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="border-border/60 bg-card/50 p-6 text-center text-fg-muted space-y-3">
                <FolderKanban className="h-8 w-8 mx-auto text-fg-subtle/50" />
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-fg">No Project Selected</p>
                  <p className="text-[11px] text-fg-subtle">
                    Click any card on the grid to inspect and adjust its parameters in real time.
                  </p>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
