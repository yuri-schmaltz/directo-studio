"use client";

import { useState, useCallback } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { api, swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton, EmptyState } from "@/components/ui/empty-state";
import {
  BookOpen,
  Plus,
  User,
  Trees,
  Sliders,
  Trash2,
  ChevronDown,
  ChevronRight,
  Save,
  Download,
  Wand2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  StyleBible,
  StyleBibleSummary,
  CharacterProfile,
  EnvironmentAnchor,
  StyleDirective,
  LoRAConfig,
} from "@/lib/types";

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function emptyCharacter(): CharacterProfile {
  return {
    id: uid(),
    name: "",
    base_prompt: "",
    visual_anchors: [],
    loras: [],
    seeds: {},
    reference_images: [],
    negative_prompt: "",
  };
}

function emptyEnvironment(): EnvironmentAnchor {
  return {
    id: uid(),
    name: "",
    scenario_prompt: "",
    lighting: "",
    color_palette: [],
    style_tokens: [],
    negative_prompt: "",
  };
}

function emptyDirective(): StyleDirective {
  return {
    id: uid(),
    name: "",
    global_prompt_prefix: "",
    global_prompt_suffix: "",
    negative_prompt: "",
    aspect_ratio: "16:9",
    audio_voice_filters: {},
    directive_seed: null,
  };
}

function emptyBible(): StyleBible {
  return {
    id: uid(),
    name: "Untitled Bible",
    version: "1.0.0",
    characters: [],
    environments: [],
    directives: [],
  };
}

function TagsInput({
  label,
  tags,
  onChange,
  placeholder = "Type and press Enter",
}: {
  label?: string;
  tags: string[];
  onChange: (t: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  const add = () => {
    const v = draft.trim();
    if (v && !tags.includes(v)) onChange([...tags, v]);
    setDraft("");
  };

  return (
    <div className="space-y-1.5">
      {label && <Label>{label}</Label>}
      <div className="flex gap-1.5">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
          className="flex-1"
        />
        <Button variant="secondary" size="sm" onClick={add}>
          Add
        </Button>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.map((t) => (
            <Badge
              key={t}
              className="flex items-center gap-1 cursor-pointer select-none"
              onClick={() => onChange(tags.filter((x) => x !== t))}
            >
              {t} ×
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function LoRAList({
  loras,
  onChange,
}: {
  loras: LoRAConfig[];
  onChange: (l: LoRAConfig[]) => void;
}) {
  const add = () =>
    onChange([...loras, { name: "", path: "", weight: 1.0, trigger_words: [] }]);

  const update = (i: number, patch: Partial<LoRAConfig>) =>
    onChange(loras.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  const remove = (i: number) => onChange(loras.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>LoRAs</Label>
        <Button variant="ghost" size="sm" onClick={add}>
          <Plus className="h-3.5 w-3.5 mr-1" /> Add LoRA
        </Button>
      </div>
      {loras.length === 0 && (
        <p className="text-xs text-fg-subtle">No LoRAs defined.</p>
      )}
      {loras.map((l, i) => (
        <div key={i} className="border border-border rounded p-3 space-y-2">
          <div className="grid grid-cols-[1fr_1fr_80px_28px] gap-1.5 items-center">
            <Input
              value={l.name}
              onChange={(e) => update(i, { name: e.target.value })}
              placeholder="name"
            />
            <Input
              value={l.path}
              onChange={(e) => update(i, { path: e.target.value })}
              placeholder="path or URL"
            />
            <Input
              type="number"
              step="0.05"
              min={0}
              max={2}
              value={l.weight}
              onChange={(e) =>
                update(i, { weight: parseFloat(e.target.value) || 1 })
              }
            />
            <button
              onClick={() => remove(i)}
              className="p-1 rounded hover:bg-bg-muted text-fg-subtle hover:text-red-400 transition-colors"
              aria-label="Remove LoRA"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
          <TagsInput
            label="Trigger Words"
            tags={l.trigger_words}
            onChange={(t) => update(i, { trigger_words: t })}
            placeholder="Trigger word, press Enter"
          />
        </div>
      ))}
    </div>
  );
}

function CharacterCard({
  char,
  onChange,
  onRemove,
}: {
  char: CharacterProfile;
  onChange: (c: CharacterProfile) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const Icon = open ? ChevronDown : ChevronRight;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 bg-bg-subtle hover:bg-bg-muted transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <User className="h-4 w-4 text-accent shrink-0" />
        <span className="flex-1 font-medium text-sm">
          {char.name || (
            <span className="text-fg-subtle italic">Unnamed character</span>
          )}
        </span>
        <Badge className="text-[10px] shrink-0">{char.loras.length} LoRAs</Badge>
        <Icon className="h-4 w-4 text-fg-subtle shrink-0" />
      </button>

      {open && (
        <div className="p-4 space-y-4 border-t border-border">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input
                value={char.name}
                onChange={(e) => onChange({ ...char, name: e.target.value })}
                placeholder="e.g. Detective Marlowe"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Base Prompt</Label>
              <Input
                value={char.base_prompt}
                onChange={(e) =>
                  onChange({ ...char, base_prompt: e.target.value })
                }
                placeholder="e.g. man in trench coat, 1940s noir…"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Negative Prompt</Label>
            <Input
              value={char.negative_prompt}
              onChange={(e) =>
                onChange({ ...char, negative_prompt: e.target.value })
              }
              placeholder="Elements to exclude from this character…"
            />
          </div>

          <TagsInput
            label="Visual Anchors"
            tags={char.visual_anchors}
            onChange={(t) => onChange({ ...char, visual_anchors: t })}
            placeholder="Visual keyword, press Enter"
          />

          <LoRAList
            loras={char.loras}
            onChange={(l) => onChange({ ...char, loras: l })}
          />

          <div className="space-y-1.5">
            <Label>Fixed Seeds (JSON)</Label>
            <Textarea
              value={JSON.stringify(char.seeds ?? {}, null, 2)}
              onChange={(e) => {
                try {
                  onChange({ ...char, seeds: JSON.parse(e.target.value) });
                } catch {}
              }}
              rows={3}
              placeholder='{"face": 42, "lighting": 1337}'
              className="font-mono text-xs"
            />
          </div>

          <div className="flex justify-end">
            <Button variant="danger" size="sm" onClick={onRemove}>
              <Trash2 className="h-3.5 w-3.5 mr-1.5" />
              Remove Character
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function EnvCard({
  env,
  onChange,
  onRemove,
}: {
  env: EnvironmentAnchor;
  onChange: (e: EnvironmentAnchor) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const Icon = open ? ChevronDown : ChevronRight;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 bg-bg-subtle hover:bg-bg-muted transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <Trees className="h-4 w-4 text-emerald-500 shrink-0" />
        <span className="flex-1 font-medium text-sm">
          {env.name || (
            <span className="text-fg-subtle italic">Unnamed environment</span>
          )}
        </span>
        <Icon className="h-4 w-4 text-fg-subtle shrink-0" />
      </button>

      {open && (
        <div className="p-4 space-y-4 border-t border-border">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input
                value={env.name}
                onChange={(e) => onChange({ ...env, name: e.target.value })}
                placeholder="e.g. Rainy Alley"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Lighting</Label>
              <Input
                value={env.lighting}
                onChange={(e) =>
                  onChange({ ...env, lighting: e.target.value })
                }
                placeholder="e.g. neon-lit, deep shadows"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Scenario Prompt</Label>
            <Textarea
              value={env.scenario_prompt}
              onChange={(e) =>
                onChange({ ...env, scenario_prompt: e.target.value })
              }
              rows={3}
              placeholder="Detailed visual description of this environment…"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Negative Prompt</Label>
            <Input
              value={env.negative_prompt}
              onChange={(e) =>
                onChange({ ...env, negative_prompt: e.target.value })
              }
              placeholder="Elements to exclude…"
            />
          </div>

          <TagsInput
            label="Style Tokens"
            tags={env.style_tokens}
            onChange={(t) => onChange({ ...env, style_tokens: t })}
          />

          <TagsInput
            label="Color Palette (hex or name)"
            tags={env.color_palette}
            onChange={(t) => onChange({ ...env, color_palette: t })}
            placeholder="#1a1a2e, midnight blue…"
          />

          <div className="flex justify-end">
            <Button variant="danger" size="sm" onClick={onRemove}>
              <Trash2 className="h-3.5 w-3.5 mr-1.5" />
              Remove Environment
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function DirectiveCard({
  directive,
  onChange,
  onRemove,
}: {
  directive: StyleDirective;
  onChange: (d: StyleDirective) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const Icon = open ? ChevronDown : ChevronRight;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 bg-bg-subtle hover:bg-bg-muted transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <Sliders className="h-4 w-4 text-violet-400 shrink-0" />
        <span className="flex-1 font-medium text-sm">
          {directive.name || (
            <span className="text-fg-subtle italic">Unnamed directive</span>
          )}
        </span>
        <Badge className="text-[10px] shrink-0">{directive.aspect_ratio}</Badge>
        <Icon className="h-4 w-4 text-fg-subtle shrink-0" />
      </button>

      {open && (
        <div className="p-4 space-y-4 border-t border-border">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Directive Name</Label>
              <Input
                value={directive.name}
                onChange={(e) =>
                  onChange({ ...directive, name: e.target.value })
                }
                placeholder="e.g. Noir Global Style"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Aspect Ratio</Label>
              <select
                id={`directive-ratio-${directive.id}`}
                value={directive.aspect_ratio}
                onChange={(e) =>
                  onChange({ ...directive, aspect_ratio: e.target.value })
                }
                className="input w-full"
              >
                {["16:9", "9:16", "1:1", "4:3", "21:9", "2:3"].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Global Prompt Prefix</Label>
            <Textarea
              value={directive.global_prompt_prefix}
              onChange={(e) =>
                onChange({
                  ...directive,
                  global_prompt_prefix: e.target.value,
                })
              }
              rows={2}
              placeholder="Text prepended to every generated prompt…"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Global Prompt Suffix</Label>
            <Textarea
              value={directive.global_prompt_suffix}
              onChange={(e) =>
                onChange({
                  ...directive,
                  global_prompt_suffix: e.target.value,
                })
              }
              rows={2}
              placeholder="Text appended to every generated prompt…"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Negative Prompt</Label>
            <Input
              value={directive.negative_prompt}
              onChange={(e) =>
                onChange({ ...directive, negative_prompt: e.target.value })
              }
              placeholder="Global exclusions for all prompts…"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Directive Seed (optional)</Label>
              <Input
                type="number"
                value={directive.directive_seed ?? ""}
                onChange={(e) =>
                  onChange({
                    ...directive,
                    directive_seed: e.target.value
                      ? parseInt(e.target.value)
                      : null,
                  })
                }
                placeholder="Leave blank for random"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Audio Voice Filters (JSON)</Label>
              <Input
                value={JSON.stringify(directive.audio_voice_filters)}
                onChange={(e) => {
                  try {
                    onChange({
                      ...directive,
                      audio_voice_filters: JSON.parse(e.target.value),
                    });
                  } catch {}
                }}
                placeholder='{"warmth": 0.8}'
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button variant="danger" size="sm" onClick={onRemove}>
              <Trash2 className="h-3.5 w-3.5 mr-1.5" />
              Remove Directive
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

type Tab = "characters" | "environments" | "directives";

export default function StyleBibleView() {
  const { data: listData, isLoading: listLoading } = useSWR<{
    items: StyleBibleSummary[];
  }>("/api/proxy/style-bible", swrFetcher);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [localBible, setLocalBible] = useState<StyleBible | null>(null);
  const [isNewBible, setIsNewBible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("characters");
  const [loadingBible, setLoadingBible] = useState(false);

  const summaries = listData?.items ?? [];

  const selectBible = useCallback(async (id: string) => {
    setLoadingBible(true);
    setIsNewBible(false);
    setSaveError(null);
    try {
      const full = await api.styleBible.get(id);
      setLocalBible({
        ...full,
        characters: full.characters ?? [],
        environments: full.environments ?? [],
        directives: full.directives ?? [],
      });
      setSelectedId(id);
      setTab("characters");
    } catch (e: any) {
      setSaveError(`Failed to load bible: ${e.message}`);
    } finally {
      setLoadingBible(false);
    }
  }, []);

  const createNew = () => {
    const bible = emptyBible();
    setLocalBible(bible);
    setSelectedId(bible.id);
    setIsNewBible(true);
    setSaveError(null);
    setTab("characters");
  };

  const save = async () => {
    if (!localBible) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (isNewBible) {
        await api.styleBible.create(localBible);
        setIsNewBible(false);
      } else {
        await api.styleBible.update(localBible.id, localBible);
      }
      globalMutate("/api/proxy/style-bible");
    } catch (e: any) {
      setSaveError(e.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const exportYaml = async () => {
    if (!localBible || isNewBible) return;
    try {
      const yaml = await api.styleBible.exportRaw(localBible.id, "yaml");
      const blob = new Blob([yaml], { type: "application/yaml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${localBible.name.replace(/\s+/g, "_")}.yaml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setSaveError(`Export failed: ${e.message}`);
    }
  };

  const setCharacters = (characters: CharacterProfile[]) =>
    setLocalBible((b) => b && { ...b, characters });
  const setEnvironments = (environments: EnvironmentAnchor[]) =>
    setLocalBible((b) => b && { ...b, environments });
  const setDirectives = (directives: StyleDirective[]) =>
    setLocalBible((b) => b && { ...b, directives });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-accent" />
            Style Bible
          </h2>
          <p className="text-sm text-fg-muted mt-0.5">
            Manage characters, environments and visual directives for
            consistent production aesthetics.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={createNew}
          id="style-bible-new-btn"
        >
          <Plus className="h-4 w-4 mr-1.5" />
          New Bible
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Sidebar */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-fg-muted uppercase tracking-wider">
              Bibles ({summaries.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-2 space-y-1">
            {listLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 text-xs font-mono" />
              ))
            ) : summaries.length === 0 ? (
              <p className="text-xs text-fg-subtle px-2 py-4 text-center">
                No bibles yet.
              </p>
            ) : (
              summaries.map((b) => (
                <button
                  key={b.id}
                  id={`style-bible-item-${b.id}`}
                  onClick={() => selectBible(b.id)}
                  className={cn(
                    "w-full text-left rounded px-3 py-2.5 text-sm transition-colors",
                    selectedId === b.id && !isNewBible
                      ? "bg-accent/10 text-accent font-semibold border-l-2 border-accent pl-2.5"
                      : "hover:bg-bg-muted text-fg-muted hover:text-fg",
                  )}
                >
                  <div className="font-medium truncate">{b.name}</div>
                  <div className="text-[11px] text-fg-subtle mt-0.5">
                    {b.character_count} chars · {b.environment_count} envs ·{" "}
                    {b.directive_count} dirs
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        {/* Editor */}
        {loadingBible ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-6 w-6 animate-spin text-accent" />
          </div>
        ) : localBible ? (
          <div className="space-y-4">
            {/* Meta */}
            <Card>
              <CardContent className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>Bible Name</Label>
                  <Input
                    id="bible-name-input"
                    value={localBible.name}
                    onChange={(e) =>
                      setLocalBible((b) =>
                        b ? { ...b, name: e.target.value } : b,
                      )
                    }
                    placeholder="e.g. Noir Trilogy — Season 2"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Version</Label>
                  <Input
                    value={localBible.version}
                    onChange={(e) =>
                      setLocalBible((b) =>
                        b ? { ...b, version: e.target.value } : b,
                      )
                    }
                    placeholder="1.0.0"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-border">
              {(
                [
                  {
                    key: "characters",
                    label: "Characters",
                    icon: User,
                    count: localBible.characters.length,
                  },
                  {
                    key: "environments",
                    label: "Environments",
                    icon: Trees,
                    count: localBible.environments.length,
                  },
                  {
                    key: "directives",
                    label: "Directives",
                    icon: Sliders,
                    count: localBible.directives.length,
                  },
                ] as const
              ).map(({ key, label, icon: Icon, count }) => (
                <button
                  key={key}
                  id={`style-bible-tab-${key}`}
                  onClick={() => setTab(key)}
                  className={cn(
                    "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
                    tab === key
                      ? "border-accent text-accent"
                      : "border-transparent text-fg-muted hover:text-fg",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                  {count > 0 && (
                    <span className="text-[10px] bg-bg-muted rounded-full px-1.5 py-0.5 font-mono">
                      {count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Characters tab */}
            {tab === "characters" && (
              <div className="space-y-3">
                <div className="flex justify-end">
                  <Button
                    id="add-character-btn"
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      setCharacters([
                        ...localBible.characters,
                        emptyCharacter(),
                      ])
                    }
                  >
                    <Plus className="h-3.5 w-3.5 mr-1" />
                    Add Character
                  </Button>
                </div>
                {localBible.characters.length === 0 ? (
                  <EmptyState
                    icon={<User className="h-8 w-8" />}
                    title="No characters"
                    description="Add a character to define their visual identity, LoRAs and prompt anchors."
                  />
                ) : (
                  localBible.characters.map((c, i) => (
                    <CharacterCard
                      key={c.id}
                      char={c}
                      onChange={(updated) =>
                        setCharacters(
                          localBible.characters.map((x, idx) =>
                            idx === i ? updated : x,
                          ),
                        )
                      }
                      onRemove={() =>
                        setCharacters(
                          localBible.characters.filter((_, idx) => idx !== i),
                        )
                      }
                    />
                  ))
                )}
              </div>
            )}

            {/* Environments tab */}
            {tab === "environments" && (
              <div className="space-y-3">
                <div className="flex justify-end">
                  <Button
                    id="add-environment-btn"
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      setEnvironments([
                        ...localBible.environments,
                        emptyEnvironment(),
                      ])
                    }
                  >
                    <Plus className="h-3.5 w-3.5 mr-1" />
                    Add Environment
                  </Button>
                </div>
                {localBible.environments.length === 0 ? (
                  <EmptyState
                    icon={<Trees className="h-8 w-8" />}
                    title="No environments"
                    description="Define locations, moods, lighting and color anchors."
                  />
                ) : (
                  localBible.environments.map((env, i) => (
                    <EnvCard
                      key={env.id}
                      env={env}
                      onChange={(updated) =>
                        setEnvironments(
                          localBible.environments.map((x, idx) =>
                            idx === i ? updated : x,
                          ),
                        )
                      }
                      onRemove={() =>
                        setEnvironments(
                          localBible.environments.filter(
                            (_, idx) => idx !== i,
                          ),
                        )
                      }
                    />
                  ))
                )}
              </div>
            )}

            {/* Directives tab */}
            {tab === "directives" && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-fg-muted">
                    Each directive defines a named aesthetic rule set applied
                    to generation requests.
                  </p>
                  <Button
                    id="add-directive-btn"
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      setDirectives([
                        ...localBible.directives,
                        emptyDirective(),
                      ])
                    }
                  >
                    <Plus className="h-3.5 w-3.5 mr-1" />
                    Add Directive
                  </Button>
                </div>
                {localBible.directives.length === 0 ? (
                  <EmptyState
                    icon={<Sliders className="h-8 w-8" />}
                    title="No directives"
                    description="Add a directive to define global prompt prefixes, suffixes and aspect ratios."
                  />
                ) : (
                  localBible.directives.map((d, i) => (
                    <DirectiveCard
                      key={d.id}
                      directive={d}
                      onChange={(updated) =>
                        setDirectives(
                          localBible.directives.map((x, idx) =>
                            idx === i ? updated : x,
                          ),
                        )
                      }
                      onRemove={() =>
                        setDirectives(
                          localBible.directives.filter((_, idx) => idx !== i),
                        )
                      }
                    />
                  ))
                )}
              </div>
            )}

            {/* Error */}
            {saveError && (
              <div className="flex items-center gap-2 text-red-400 text-sm p-3 bg-red-400/10 rounded-lg border border-red-400/20">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {saveError}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex gap-2">
                {!isNewBible && (
                  <Button
                    id="style-bible-export-btn"
                    variant="ghost"
                    size="sm"
                    onClick={exportYaml}
                  >
                    <Download className="h-3.5 w-3.5 mr-1.5" />
                    Export YAML
                  </Button>
                )}
              </div>
              <Button
                id="style-bible-save-btn"
                variant="primary"
                onClick={save}
                disabled={saving}
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5 mr-1.5" />
                )}
                {saving ? "Saving…" : isNewBible ? "Create Bible" : "Save Bible"}
              </Button>
            </div>
          </div>
        ) : (
          <EmptyState
            icon={<Wand2 className="h-8 w-8" />}
            title="No bible selected"
            description="Select a bible from the list or create a new one to get started."
          />
        )}
      </div>
    </div>
  );
}
