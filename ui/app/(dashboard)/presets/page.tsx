"use client";

import useSWR from "swr";
import { useState } from "react";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton, EmptyState } from "@/components/ui/empty-state";
import { Search, Palette, Sparkles } from "lucide-react";
import type { Preset } from "@/lib/types";

export default function PresetsPage() {
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
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Presets</h2>
        <p className="text-sm text-fg-muted">
          {data?.count ?? 0} style packs
        </p>
      </div>

      <Card>
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label>Search</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-fg-subtle" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="cinematic, ghibli, …"
                className="pl-8"
              />
            </div>
          </div>
          <div>
            <Label>Kind</Label>
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">All</option>
              <option value="live_action">live_action</option>
              <option value="animation">animation</option>
              <option value="abstract">abstract</option>
              <option value="custom">custom</option>
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
          icon={<Palette className="h-12 w-12" />}
          title="No presets match"
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
  const [open, setOpen] = useState(false);
  const [userPrompt, setUserPrompt] = useState("a beautiful scene");
  const [result, setResult] = useState<{
    rendered: string;
    enhanced: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  async function enhance() {
    setLoading(true);
    try {
      const r = await fetch(`/api/proxy/presets/${preset.id}/enhance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: userPrompt, enhance: true }),
      });
      if (r.ok) setResult(await r.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const imgUrl = preset.image_url || `/presets/${preset.id}.jpg`;

  return (
    <Card className="overflow-hidden group flex flex-col justify-between hover:border-brand/40 transition-colors">
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
          <div className="absolute inset-0 bg-gradient-to-t from-bg-surface/90 via-transparent to-transparent opacity-80" />
          <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between pointer-events-none">
            <Badge variant="brand" className="backdrop-blur-md bg-brand/80 text-white font-medium shadow-sm">
              {preset.kind}
            </Badge>
            {preset.era && (
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-black/60 backdrop-blur-md text-fg-muted border border-white/10">
                {preset.era}
              </span>
            )}
          </div>
        </div>
        <CardHeader className="pb-2 pt-3">
          <CardTitle className="text-base font-semibold group-hover:text-brand transition-colors">
            {preset.name}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pb-4">
          {preset.description && (
            <p className="text-sm text-fg-muted line-clamp-2 leading-relaxed">
              {preset.description}
            </p>
          )}
          <div className="flex flex-wrap gap-1.5 text-xs">
            <Badge>{preset.model || "any model"}</Badge>
            <Badge>{preset.steps} steps</Badge>
            <Badge>cfg {preset.cfg_scale}</Badge>
            <Badge>{preset.width}×{preset.height}</Badge>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setOpen(!open)}
            className="w-full"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {open ? "Hide enhancer" : "Enhance a prompt"}
          </Button>
          {open && (
            <div className="space-y-2 pt-2 border-t border-border">
              <Label>Your prompt</Label>
              <Textarea
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                rows={2}
              />
              <Button onClick={enhance} size="sm" disabled={loading} className="w-full">
                {loading ? "Enhancing…" : "Run enhancement"}
              </Button>
              {result && (
                <div className="space-y-2 text-xs">
                  <div>
                    <p className="text-fg-subtle mb-1">rendered:</p>
                    <pre className="bg-bg-muted p-2 rounded font-mono whitespace-pre-wrap break-words">
                      {result.rendered}
                    </pre>
                  </div>
                  {result.enhanced && result.enhanced !== result.rendered && (
                    <div>
                      <p className="text-fg-subtle mb-1">enhanced:</p>
                      <pre className="bg-bg-muted p-2 rounded font-mono whitespace-pre-wrap break-words">
                        {result.enhanced}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </div>
    </Card>
  );
}
