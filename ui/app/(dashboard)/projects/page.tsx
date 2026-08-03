"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
  Loader2,
  Upload,
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

// Procedural / AI Cover Artwork Component
function AICoverPlaceholder({
  name,
  concept,
  presetId,
  coverUrl,
}: {
  name: string;
  concept: string;
  presetId?: string;
  coverUrl?: string;
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
    <div className="relative aspect-video w-full overflow-hidden rounded-t-xl bg-slate-950 select-none group">
      {coverUrl ? (
        <img
          src={coverUrl}
          alt={name}
          className="absolute inset-0 h-full w-full object-cover object-center group-hover:scale-105 transition-transform duration-500 ease-out"
        />
      ) : (
        <>
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
        </>
      )}

      {/* Badge Overlay */}
      <div className="absolute top-2.5 left-2.5 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur border border-white/10 text-[10px] font-mono tracking-wide text-white/90">
        <Icon className="h-3 w-3" style={{ color: config.accent }} />
        <span>{config.label.toUpperCase()}</span>
      </div>

      {/* Project Initial Big Watermark */}
      {!coverUrl && (
        <div className="absolute -bottom-4 left-3 text-5xl font-black font-mono tracking-tighter text-white/5 pointer-events-none select-none">
          {name.slice(0, 3).toUpperCase() || "PRJ"}
        </div>
      )}
    </div>
  );
}

export default function ProjectsPage() {
  const router = useRouter();
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
  const [editCoverUrl, setEditCoverUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [generatingCover, setGeneratingCover] = useState(false);
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
    setEditCoverUrl(p.style?.cover_image_url || p.metadata?.cover_image_url || "");
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
          style: {
            ...(selectedProject?.style || {}),
            preset: editPreset,
            cover_image_url: editCoverUrl,
          },
          metadata: {
            ...(selectedProject?.metadata || {}),
            preset: editPreset,
            cover_image_url: editCoverUrl,
          },
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

  async function handleGenerateCover() {
    if (!selectedId) return;
    setGeneratingCover(true);
    try {
      // 1. Submit background job to queue
      fetch("/api/proxy/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "image.generate",
          payload: {
            project_id: selectedId,
            prompt: `Cinematic movie art for "${editName}". ${editConcept || editLogline}. Visual style: ${editPreset}`,
            aspect_ratio: "16:9",
          },
        }),
      }).catch(() => {});

      // 2. Generate prompt-tailored AI cover art URL
      const presetObj = getPresetConfig(editPreset);
      const promptSlug = encodeURIComponent(
        `masterpiece cinematic movie poster still, ${editName}, ${editConcept || "key epic scene"}, ${presetObj.label} style, 8k resolution, photorealistic concept art`
      );
      const newUrl = `https://image.pollinations.ai/prompt/${promptSlug}?width=640&height=360&seed=${Math.floor(Math.random() * 1000000)}&nologo=true`;

      setEditCoverUrl(newUrl);

      // Save to project immediately
      await fetch(`/api/proxy/projects/${selectedId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName,
          concept: editConcept,
          logline: editLogline,
          style: {
            ...(selectedProject?.style || {}),
            preset: editPreset,
            cover_image_url: newUrl,
          },
          metadata: {
            ...(selectedProject?.metadata || {}),
            preset: editPreset,
            cover_image_url: newUrl,
          },
        }),
      });

      await mutate();
    } catch (err) {
      console.error("Failed to generate AI cover artwork", err);
    } finally {
      setGeneratingCover(false);
    }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const result = reader.result as string;
      setEditCoverUrl(result);
      if (selectedId) {
        await fetch(`/api/proxy/projects/${selectedId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: editName,
            concept: editConcept,
            logline: editLogline,
            style: {
              ...(selectedProject?.style || {}),
              preset: editPreset,
              cover_image_url: result,
            },
            metadata: {
              ...(selectedProject?.metadata || {}),
              preset: editPreset,
              cover_image_url: result,
            },
          }),
        });
        mutate();
      }
    };
    reader.readAsDataURL(file);
  }

  function handleLoadInCinema() {
    if (!selectedId) return;
    localStorage.setItem("directo_active_project", selectedId);
    window.dispatchEvent(new Event("storage"));
    router.push("/cinema");
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
    <div className="space-y-4">


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
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
          {/* Main Grid Viewport */}
          <div className="lg:col-span-3">
            {/* 3 columns per row scrollable grid container */}
            <div className="max-h-[calc(100vh-9.5rem)] overflow-y-auto pr-1.5 scrollbar-thin scrollbar-thumb-border hover:scrollbar-thumb-accent/40 rounded-xl">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pb-2">
                {projects.map((p) => {
                  const isSelected = p.id === selectedId;
                  const currentPreset = p.style?.preset || p.metadata?.preset || "cinematic";
                  const currentCoverUrl = p.style?.cover_image_url || p.metadata?.cover_image_url;

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
                        coverUrl={currentCoverUrl}
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

          {/* Fixed Project Parameter Editor Side Panel */}
          <div className="lg:col-span-1">
            <Card className="h-[calc(100vh-9.5rem)] flex flex-col border-accent/40 bg-card/95 shadow-xl backdrop-blur overflow-hidden transition-none">

              {selectedProject ? (
                <CardContent className="flex flex-col gap-2 p-3 overflow-hidden flex-1">
                  {/* Name Input */}
                  <div className="space-y-1 shrink-0">
                    <Label className="text-[11px]">Project Name</Label>
                    <Input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="Project Title"
                      className="text-xs font-semibold h-7"
                    />
                  </div>

                  {/* Visual Preset Selector */}
                  <div className="space-y-1 shrink-0">
                    <Label className="text-[11px] flex items-center justify-between">
                      <span>AI Visual Preset</span>
                      <Sparkles className="h-3 w-3 text-amber-400" />
                    </Label>
                    <select
                      value={editPreset}
                      onChange={(e) => setEditPreset(e.target.value)}
                      className="w-full h-7 rounded-md border border-border/80 bg-bg-muted/40 text-xs text-fg px-2 focus:outline-none focus:ring-1 focus:ring-accent/50 cursor-pointer"
                    >
                      <option value="">— Select a preset —</option>
                      {PRESETS.map((pr) => (
                        <option key={pr.id} value={pr.id} className="bg-slate-900 text-fg">
                          {pr.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Card Cover Art Action Buttons */}
                  <div className="space-y-1 shrink-0">
                    <div className="flex items-center justify-between">
                      <Label className="text-[11px] font-medium">Card Cover Art</Label>
                      {editCoverUrl && (
                        <button
                          type="button"
                          onClick={() => setEditCoverUrl("")}
                          className="text-[10px] text-fg-subtle hover:text-danger"
                        >
                          Remove Art
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={handleGenerateCover}
                        disabled={generatingCover}
                        className="h-7 bg-gradient-to-r from-amber-500/20 to-purple-500/20 hover:from-amber-500/30 hover:to-purple-500/30 border border-amber-500/40 text-amber-300 font-medium flex items-center justify-center gap-1 text-[11px] px-2"
                      >
                        {generatingCover ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-400" />
                        ) : (
                          <Wand2 className="h-3.5 w-3.5 text-amber-400" />
                        )}
                        <span className="truncate">Generate with AI</span>
                      </Button>
                      <label className="h-7 rounded-md bg-bg-muted/70 hover:bg-bg-muted border border-border/80 text-fg-muted hover:text-fg font-medium flex items-center justify-center gap-1.5 text-[11px] px-2 cursor-pointer transition-colors">
                        <Upload className="h-3.5 w-3.5 text-cyan-400" />
                        <span className="truncate">Upload Image</span>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleFileUpload}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </div>

                  {/* Concept Input */}
                  <div className="flex flex-col gap-1 flex-1 min-h-0">
                    <div className="flex items-center justify-between shrink-0">
                      <Label className="text-[11px]">Concept & Prompt</Label>
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
                      placeholder="Themes, worldbuilding, lighting..."
                      className="text-xs flex-1 resize-none min-h-0"
                    />
                  </div>

                  {/* Logline Input */}
                  <div className="space-y-1 shrink-0">
                    <Label className="text-[11px]">Logline Summary</Label>
                    <Input
                      value={editLogline}
                      onChange={(e) => setEditLogline(e.target.value)}
                      placeholder="One-line synopsis"
                      className="text-xs h-7"
                    />
                  </div>

                  {/* Save Status & Action */}
                  {saveSuccess && (
                    <div className="p-1.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[11px] flex items-center gap-1.5 shrink-0">
                      <Check className="h-3.5 w-3.5" />
                      <span>Parameters saved successfully!</span>
                    </div>
                  )}

                  <div className="space-y-1.5 shrink-0">
                    <Button onClick={handleSave} disabled={saving} size="sm" className="w-full h-7 text-xs">
                      {saving ? "Saving…" : "Save Parameters"}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={handleLoadInCinema}
                      className="w-full h-7 text-xs border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 font-medium flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Clapperboard className="h-3.5 w-3.5 text-amber-400" />
                      <span>Open in Cinema Engine</span>
                    </Button>
                  </div>
                </CardContent>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-fg-muted space-y-3">
                  <FolderKanban className="h-10 w-10 text-fg-subtle/40" />
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-fg">No Project Selected</p>
                    <p className="text-[11px] text-fg-subtle max-w-[200px] mx-auto">
                      Click any card on the grid to inspect and adjust its parameters in real time.
                    </p>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
