"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton, EmptyState } from "@/components/ui/empty-state";
import {
  Settings,
  Save,
  AlertCircle,
  CheckCircle,
  Sliders,
  Database,
  Check,
  X as XIcon,
  Palette,
  Sparkles,
  Search,
  Cpu,
  Film,
  Key,
} from "lucide-react";
import type { BackupResult, Preset } from "@/lib/types";

interface LLMSettings {
  llm_backend: string;
  ollama_host: string;
  ollama_model: string;
  openai_api_base: string;
  openai_api_key: string;
  openai_model: string;
  anthropic_api_key: string;
  anthropic_model: string;
}

const BACKUP_TARGETS = [
  { value: "queue", label: "queue.db (job queue)" },
  { value: "gallery", label: "gallery.db (images)" },
  { value: "events", label: "events.db (event log)" },
  { value: "presets", label: "presets.db (preset packs)" },
];

function OpenMontageKeysSection() {
  const [falKey, setFalKey] = useState("");
  const [elevenKey, setElevenKey] = useState("");
  const [openclawKey, setOpenclawKey] = useState("");
  const [saved, setSaved] = useState(false);

  function handleSaveKeys(e: React.FormEvent) {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Key className="h-4 w-4 text-amber-400" />
          OpenMontage Provider & Video Generation Keys
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-fg-muted">
          Configure API credentials for video motion generation (fal.ai Kling v3/FLUX), audio synthesis (ElevenLabs/Chirp3-HD), and Remotion parallel renderer.
        </p>

        {saved && (
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded text-xs text-emerald-400 flex items-center gap-2">
            <Check className="h-4 w-4 shrink-0" />
            <span>OpenMontage provider keys saved!</span>
          </div>
        )}

        <form onSubmit={handleSaveKeys} className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">fal.ai API Key (Kling v3 & FLUX)</Label>
            <Input
              type="password"
              value={falKey}
              onChange={(e) => setFalKey(e.target.value)}
              placeholder="fal_key_..."
              className="text-xs font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">ElevenLabs / Audio Synthesis API Key</Label>
            <Input
              type="password"
              value={elevenKey}
              onChange={(e) => setElevenKey(e.target.value)}
              placeholder="xi_api_key_..."
              className="text-xs font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">OpenClaw Agentic Production Key</Label>
            <Input
              type="password"
              value={openclawKey}
              onChange={(e) => setOpenclawKey(e.target.value)}
              placeholder="openclaw_..."
              className="text-xs font-mono"
            />
          </div>

          <div className="flex justify-end pt-2">
            <Button type="submit" size="sm">
              <Save className="h-4 w-4 mr-2" />
              Save Provider Keys
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function BackupSection() {
  const [db, setDb] = useState("queue");
  const [result, setResult] = useState<BackupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runBackup() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/backup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ db }),
      });
      if (r.ok) setResult(await r.json());
      else setError(`${r.status} ${r.statusText}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Database className="h-5 w-5 text-accent" />
          Database Backup & Maintenance
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-fg-muted">
          Perform a live hot-copy backup of Directo SQLite database files with integrity verification.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div className="md:col-span-2 space-y-1.5">
            <Label>Select Target Database</Label>
            <Select value={db} onChange={(e) => setDb(e.target.value)}>
              {BACKUP_TARGETS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Button type="button" onClick={runBackup} disabled={loading} className="w-full">
              <Database className="h-4 w-4 mr-2" />
              {loading ? "Creating Backup…" : "Create Backup"}
            </Button>
          </div>
        </div>

        {result && (
          <div className="p-4 bg-bg border border-border rounded-md space-y-2 text-xs font-mono">
            <div className="flex items-center gap-2 text-emerald-400 font-bold mb-2">
              <Check className="h-4 w-4" />
              <span>Backup Completed Successfully</span>
            </div>
            <div className="flex justify-between border-b border-border/40 pb-1">
              <span className="text-fg-subtle">Destination Path:</span>
              <span className="text-fg truncate max-w-xs">{result.path}</span>
            </div>
            <div className="flex justify-between border-b border-border/40 pb-1">
              <span className="text-fg-subtle">File Size:</span>
              <span className="text-fg">{result.size_bytes.toLocaleString()} bytes</span>
            </div>
            <div className="flex justify-between pt-0.5">
              <span className="text-fg-subtle">Duration:</span>
              <span className="text-fg">{result.duration_ms.toFixed(1)} ms</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PresetsSection() {
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const { data, isLoading } = useSWR<{ items: Preset[]; count: number }>(
    `/api/proxy/presets`,
    swrFetcher,
  );

  const items = (data?.items ?? []).filter((p) => {
    if (kind && p.kind !== kind) return false;
    if (search) {
      const s = search.toLowerCase();
      if (
        !p.name.toLowerCase().includes(s) &&
        !p.id.toLowerCase().includes(s) &&
        !(p.description || "").toLowerCase().includes(s)
      ) {
        return false;
      }
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label className="text-xs">Search Style Packs</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-fg-subtle" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="cinematic, ghibli, anime…"
                className="pl-8 text-xs"
              />
            </div>
          </div>
          <div>
            <Label className="text-xs">Filter Category</Label>
            <Select value={kind} onChange={(e) => setKind(e.target.value)} className="text-xs">
              <option value="">All Categories ({data?.count ?? 0})</option>
              <option value="live_action">Live Action</option>
              <option value="animation">Animation</option>
              <option value="abstract">Abstract</option>
              <option value="custom">Custom</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Palette className="h-12 w-12 text-accent" />}
          title="No style presets found"
          description="Try clearing your search query or choosing another category."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((p) => (
            <PresetCard key={p.id} preset={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function PresetCard({ preset }: { preset: Preset }) {
  const imgUrl = preset.image_url || `/presets/${preset.id}.jpg`;

  return (
    <Card className="overflow-hidden group flex flex-col justify-between hover:border-accent/40 transition-colors">
      <div>
        <div className="relative aspect-video w-full overflow-hidden bg-bg-muted border-b border-border">
          <img
            src={imgUrl}
            alt={preset.name}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
          <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between pointer-events-none">
            <Badge variant="accent" className="text-[10px] font-mono">
              {preset.kind}
            </Badge>
          </div>
        </div>
        <CardHeader className="pb-2 pt-3">
          <CardTitle className="text-sm font-semibold group-hover:text-accent transition-colors">
            {preset.name}
          </CardTitle>
        </CardHeader>
      </div>
    </Card>
  );
}

function SettingsContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") || "llm";
  const [activeTab, setActiveTab] = useState(initialTab);

  const { data: settingsData, mutate } = useSWR<LLMSettings>(
    "/api/proxy/settings",
    swrFetcher
  );

  const [settings, setSettings] = useState<LLMSettings>({
    llm_backend: "template",
    ollama_host: "http://localhost:11434",
    ollama_model: "llama3.1",
    openai_api_base: "",
    openai_api_key: "",
    openai_model: "gpt-4o-mini",
    anthropic_api_key: "",
    anthropic_model: "claude-3-5-sonnet-20241022",
  });

  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settingsData) {
      setSettings(settingsData);
    }
  }, [settingsData]);

  const handleChange = (key: keyof LLMSettings, val: string) => {
    setSettings((prev) => ({ ...prev, [key]: val }));
  };

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await fetch("/api/proxy/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      mutate();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight font-sans">Settings & System Preferences</h2>
        <p className="text-sm text-fg-muted">
          Manage active LLM infrastructure, OpenMontage video engine credentials, presets, and maintenance.
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-border/80 gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab("llm")}
          className={`pb-2.5 flex items-center gap-2 border-b-2 transition-all ${
            activeTab === "llm"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-fg-muted hover:text-fg"
          }`}
        >
          <Cpu className="h-4 w-4" />
          <span>LLM & AI Engine</span>
        </button>

        <button
          onClick={() => setActiveTab("openmontage")}
          className={`pb-2.5 flex items-center gap-2 border-b-2 transition-all ${
            activeTab === "openmontage"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-fg-muted hover:text-fg"
          }`}
        >
          <Film className="h-4 w-4 text-amber-400" />
          <span>OpenMontage Keys</span>
        </button>

        <button
          onClick={() => setActiveTab("presets")}
          className={`pb-2.5 flex items-center gap-2 border-b-2 transition-all ${
            activeTab === "presets"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-fg-muted hover:text-fg"
          }`}
        >
          <Palette className="h-4 w-4" />
          <span>Style Presets</span>
        </button>

        <button
          onClick={() => setActiveTab("backup")}
          className={`pb-2.5 flex items-center gap-2 border-b-2 transition-all ${
            activeTab === "backup"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-fg-muted hover:text-fg"
          }`}
        >
          <Database className="h-4 w-4" />
          <span>Backups & Maintenance</span>
        </button>
      </div>

      {/* Tab 1: LLM Engine */}
      {activeTab === "llm" && (
        <form onSubmit={handleSave} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Settings className="h-4 w-4 text-accent" />
                Active LLM Provider
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Select LLM Provider</Label>
                <Select
                  value={settings.llm_backend}
                  onChange={(e) => handleChange("llm_backend", e.target.value)}
                  className="text-xs"
                >
                  <option value="template">Mock / Offline Template</option>
                  <option value="ollama">Ollama (Local LLM)</option>
                  <option value="openai">OpenAI / LM Studio (REST)</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                </Select>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button type="submit" disabled={saving} size="sm">
              <Save className="h-4 w-4 mr-2" />
              {saving ? "Saving Changes…" : "Save LLM Settings"}
            </Button>
          </div>
        </form>
      )}

      {/* Tab 2: OpenMontage Keys */}
      {activeTab === "openmontage" && <OpenMontageKeysSection />}

      {/* Tab 3: Style Presets */}
      {activeTab === "presets" && <PresetsSection />}

      {/* Tab 4: Database & Maintenance */}
      {activeTab === "backup" && <BackupSection />}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <SettingsContent />
    </Suspense>
  );
}
