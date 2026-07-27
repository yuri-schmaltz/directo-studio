"use client";

import { useState, useRef, ChangeEvent, DragEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea, Label, Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Clapperboard,
  AlertTriangle,
  Lightbulb,
  CheckCircle2,
  Upload,
  FileText,
  Download,
  RotateCcw,
  Sparkles,
  FileCode,
} from "lucide-react";
import type { CinemaReport, Scene, EvaluateScriptResponse } from "@/lib/types";

type Tab = "evaluate" | "parse";

export default function CinemaPage() {
  const [tab, setTab] = useState<Tab>("parse");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Cinema Engine</h2>
        <p className="text-sm text-fg-muted">
          19 cinematic rules to load, process, and evaluate script prompts and screenplay files
        </p>
      </div>

      <div className="flex gap-2">
        <Button
          variant={tab === "parse" ? "primary" : "secondary"}
          onClick={() => setTab("parse")}
        >
          <FileText className="h-4 w-4 mr-1.5 inline-block" />
          Script processor & evaluator
        </Button>
        <Button
          variant={tab === "evaluate" ? "primary" : "secondary"}
          onClick={() => setTab("evaluate")}
        >
          <Clapperboard className="h-4 w-4 mr-1.5 inline-block" />
          Evaluate single prompt
        </Button>
      </div>

      {tab === "evaluate" ? <EvaluateTab /> : <ParseTab />}
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
            {report && (
              <span className="text-xs font-mono text-fg-subtle">
                Authenticity Rating
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!report ? (
            <p className="text-sm text-fg-muted">
              Run an evaluation to see authenticity results & cinematic warnings.
            </p>
          ) : (
            <div className="space-y-4">
              {/* Score HUD Bar */}
              <div className="p-3 bg-bg border border-border rounded space-y-2 font-mono">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-fg-subtle">CINEMATIC AUTHENTICITY SCORE</span>
                  <span className="text-fg font-bold text-sm">
                    {(report.score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full h-2.5 bg-bg-muted rounded-full overflow-hidden p-0.5 border border-border">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      report.blocked
                        ? "bg-rose-500"
                        : report.score >= 0.8
                        ? "bg-emerald-500"
                        : "bg-amber-500"
                    }`}
                    style={{ width: `${Math.max(5, Math.min(100, report.score * 100))}%` }}
                  />
                </div>
              </div>
              {report.warnings.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wide text-fg-subtle mb-1.5 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" /> Warnings
                  </p>
                  <ul className="space-y-1 text-sm">
                    {report.warnings.map((w, i) => (
                      <li key={i} className="text-warning">
                        • {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {report.suggestions.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wide text-fg-subtle mb-1.5 flex items-center gap-1">
                    <Lightbulb className="h-3 w-3" /> Suggestions
                  </p>
                  <ul className="space-y-1 text-sm">
                    {report.suggestions.map((s, i) => (
                      <li key={i} className="text-fg-muted">
                        → {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {report.warnings.length === 0 &&
                report.suggestions.length === 0 && (
                  <p className="text-sm text-success flex items-center gap-1">
                    <CheckCircle2 className="h-4 w-4" />
                    No issues found
                  </p>
                )}
              {report.augmented_prompt && (
                <div>
                  <p className="text-xs uppercase tracking-wide text-fg-subtle mb-1.5">
                    Augmented prompt
                  </p>
                  <pre className="bg-bg-muted p-3 rounded text-xs font-mono whitespace-pre-wrap break-words">
                    {report.augmented_prompt}
                  </pre>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const SAMPLE_MARKDOWN_SCRIPT = `# INT. KITCHEN - DAY

ALICE stands near the window preparing morning tea.
A vintage clock ticks softly on the wall.

ALICE
(smiling)
It's going to be a quiet day.

## EXT. SALOON STREET - DUSK

A MAN ON HORSEBACK arrives in town, holding a modern smartphone in his hand.
Dust blows across the empty wooden walkway.

MAN
(looking around)
Where is everyone?`;

const SAMPLE_FOUNTAIN_SCRIPT = `Title: Neo-Western Demo

INT. KITCHEN - DAY

ALICE looks out the window. Steam rises from the hot kettle.

ALICE
It's a beautiful day.

EXT. PARK - NIGHT

BOB walks by with a dog under golden street lights.`;

function ParseTab() {
  const [text, setText] = useState(SAMPLE_MARKDOWN_SCRIPT);
  const [era, setEra] = useState("1920-1930");
  const [fileMeta, setFileMeta] = useState<{ name: string; size: number } | null>(null);
  const [scenes, setScenes] = useState<Scene[] | null>(null);
  const [evalResult, setEvalResult] = useState<EvaluateScriptResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileRead(file: File) {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    setFileMeta({ name: file.name, size: file.size });
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      if (content) {
        setText(content);
        setScenes(null);
        setEvalResult(null);
      }
    };
    reader.readAsText(file);
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      handleFileRead(e.target.files[0]);
    }
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(true);
  }

  function onDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileRead(e.dataTransfer.files[0]);
    }
  }

  function loadSample(sampleText: string, sampleName: string) {
    setText(sampleText);
    setFileMeta({ name: sampleName, size: sampleText.length });
    setScenes(null);
    setEvalResult(null);
  }

  async function parseScriptOnly() {
    setLoading(true);
    setEvalResult(null);
    try {
      const hint = fileMeta?.name
        ? fileMeta.name.substring(fileMeta.name.lastIndexOf(".")).toLowerCase()
        : ".md";
      const r = await fetch("/api/proxy/cinema/parse-script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, hint }),
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

  async function evaluateFullScript() {
    setLoading(true);
    try {
      const hint = fileMeta?.name
        ? fileMeta.name.substring(fileMeta.name.lastIndexOf(".")).toLowerCase()
        : ".md";
      const r = await fetch("/api/proxy/cinema/evaluate-script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          hint,
          context: era ? { era } : {},
        }),
      });
      if (r.ok) {
        const data: EvaluateScriptResponse = await r.json();
        setEvalResult(data);
        setScenes(data.scenes);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function downloadReportJSON() {
    const dataToSave = evalResult || { scenes };
    const blob = new Blob([JSON.stringify(dataToSave, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `script_evaluation_${fileMeta?.name || "report"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Input & Upload Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4 text-brand-400" />
            Script File & Text Editor
          </CardTitle>
          {fileMeta && (
            <Badge variant="default" className="font-mono text-xs">
              {fileMeta.name} ({(fileMeta.size / 1024).toFixed(1)} KB)
            </Badge>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Hidden File Input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={onFileChange}
            accept=".txt,.md,.markdown,.fountain,.spmd"
            className="hidden"
          />

          {/* Drag & Drop Zone */}
          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
              isDragging
                ? "border-brand-500 bg-brand-500/10"
                : "border-border hover:border-brand-400/50 bg-bg-subtle"
            }`}
          >
            <div className="flex flex-col items-center gap-1.5">
              <Upload className="h-6 w-6 text-fg-subtle" />
              <p className="text-xs font-medium text-fg">
                Click to load file or drag & drop script here
              </p>
              <p className="text-[11px] text-fg-subtle">
                Supports <code className="text-brand-300">.txt</code>,{" "}
                <code className="text-brand-300">.md</code>,{" "}
                <code className="text-brand-300">.fountain</code>,{" "}
                <code className="text-brand-300">.spmd</code>
              </p>
            </div>
          </div>

          {/* Sample preset buttons */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-fg-subtle">Presets:</span>
            <Button
              variant="secondary"
              className="text-xs py-1 px-2.5 h-auto"
              onClick={() => loadSample(SAMPLE_MARKDOWN_SCRIPT, "sample_script.md")}
            >
              <FileCode className="h-3 w-3 mr-1 inline" /> Markdown
            </Button>
            <Button
              variant="secondary"
              className="text-xs py-1 px-2.5 h-auto"
              onClick={() => loadSample(SAMPLE_FOUNTAIN_SCRIPT, "sample_script.fountain")}
            >
              <FileText className="h-3 w-3 mr-1 inline" /> Fountain
            </Button>
          </div>

          <div>
            <Label className="text-xs mb-1 block">Script Content</Label>
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={12}
              spellCheck={false}
              className="font-mono text-xs"
            />
          </div>

          <div>
            <Label className="text-xs mb-1 block">Era Context (optional for rule checks)</Label>
            <Input
              value={era}
              onChange={(e) => setEra(e.target.value)}
              placeholder="e.g. '1920-1930', 'pre-1973', '1980s'"
              className="text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-2 pt-1">
            <Button onClick={parseScriptOnly} disabled={loading} variant="secondary">
              <FileText className="h-4 w-4 mr-1.5" />
              {loading ? "Processing…" : "Parse scenes"}
            </Button>

            <Button onClick={evaluateFullScript} disabled={loading} variant="primary">
              <Clapperboard className="h-4 w-4 mr-1.5" />
              {loading ? "Evaluating…" : "Evaluate script"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results & HUD Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-emerald-400" />
            {scenes ? `${scenes.length} scene(s) extracted` : "Parsed & Evaluated Output"}
          </CardTitle>
          {scenes && scenes.length > 0 && (
            <Button
              variant="secondary"
              className="text-xs py-1 px-2.5 h-auto flex items-center gap-1"
              onClick={downloadReportJSON}
            >
              <Download className="h-3.5 w-3.5" /> Export JSON
            </Button>
          )}
        </CardHeader>

        <CardContent>
          {/* Summary HUD when script evaluation is available */}
          {evalResult && (
            <div className="mb-4 p-3 bg-bg border border-border rounded space-y-2 font-mono">
              <div className="flex items-center justify-between text-xs">
                <span className="text-fg-subtle">AVERAGE AUTHENTICITY SCORE</span>
                <span className="text-fg font-bold text-sm">
                  {(evalResult.average_score * 100).toFixed(0)}%
                </span>
              </div>
              <div className="w-full h-2.5 bg-bg-muted rounded-full overflow-hidden p-0.5 border border-border">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    evalResult.blocked_count > 0
                      ? "bg-amber-500"
                      : evalResult.average_score >= 0.8
                      ? "bg-emerald-500"
                      : "bg-rose-500"
                  }`}
                  style={{
                    width: `${Math.max(5, Math.min(100, evalResult.average_score * 100))}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-fg-subtle pt-1">
                <span>Total scenes: {evalResult.count}</span>
                <span className={evalResult.blocked_count > 0 ? "text-rose-400 font-semibold" : "text-emerald-400"}>
                  Blocked scenes: {evalResult.blocked_count}
                </span>
              </div>
            </div>
          )}

          {!scenes ? (
            <div className="py-12 text-center text-fg-muted space-y-2">
              <FileText className="h-8 w-8 mx-auto text-fg-subtle opacity-50" />
              <p className="text-sm">Load or paste a script file and click "Parse" or "Evaluate".</p>
            </div>
          ) : scenes.length === 0 ? (
            <p className="text-sm text-fg-muted">No scenes found in script text.</p>
          ) : (
            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
              {scenes.map((s) => {
                const evalData = s.evaluation;
                return (
                  <div
                    key={s.number}
                    className="rounded-md border border-border bg-bg-subtle p-3.5 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="brand">Scene {s.number}</Badge>
                        {evalData && (
                          <Badge variant={evalData.blocked ? "danger" : "success"}>
                            {evalData.blocked ? "BLOCKED" : "PASSED"}
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-fg-subtle font-mono">
                        {s.time_of_day || "DAY"}
                      </span>
                    </div>

                    <p className="text-sm font-semibold text-fg tracking-wide">
                      {s.heading}
                    </p>

                    {s.action && (
                      <p className="text-xs text-fg-muted leading-relaxed line-clamp-3">
                        {s.action}
                      </p>
                    )}

                    {s.characters.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[11px] text-fg-subtle">Characters:</span>
                        {s.characters.map((c) => (
                          <span
                            key={c}
                            className="px-1.5 py-0.5 text-[10px] font-mono bg-bg-muted rounded border border-border text-fg-subtle"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    )}

                    {s.prompt && (
                      <div>
                        <span className="text-[10px] uppercase font-mono text-fg-subtle block mb-1">
                          Generated Prompt
                        </span>
                        <pre className="text-xs font-mono bg-bg-muted p-2 rounded whitespace-pre-wrap break-words border border-border/50 text-fg">
                          {s.prompt}
                        </pre>
                      </div>
                    )}

                    {/* Evaluation Details for this Scene */}
                    {evalData && (
                      <div className="mt-2 pt-2 border-t border-border/60 space-y-2">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-fg-subtle">Authenticity Score</span>
                          <span
                            className={
                              evalData.blocked
                                ? "text-rose-400 font-bold"
                                : evalData.score >= 0.8
                                ? "text-emerald-400 font-bold"
                                : "text-amber-400 font-bold"
                            }
                          >
                            {(evalData.score * 100).toFixed(0)}%
                          </span>
                        </div>

                        {evalData.warnings.length > 0 && (
                          <div className="space-y-1">
                            <span className="text-[10px] uppercase tracking-wide text-rose-400 flex items-center gap-1 font-semibold">
                              <AlertTriangle className="h-3 w-3" /> Warnings
                            </span>
                            <ul className="text-xs space-y-0.5">
                              {evalData.warnings.map((w, idx) => (
                                <li key={idx} className="text-rose-300">
                                  • {w}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {evalData.suggestions.length > 0 && (
                          <div className="space-y-1">
                            <span className="text-[10px] uppercase tracking-wide text-amber-400 flex items-center gap-1 font-semibold">
                              <Lightbulb className="h-3 w-3" /> Suggestions
                            </span>
                            <ul className="text-xs space-y-0.5">
                              {evalData.suggestions.map((sug, idx) => (
                                <li key={idx} className="text-fg-muted">
                                  → {sug}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {evalData.augmented_prompt && (
                          <div>
                            <span className="text-[10px] uppercase font-mono text-fg-subtle block mb-1">
                              Augmented Prompt
                            </span>
                            <pre className="text-xs font-mono bg-bg-muted p-2 rounded whitespace-pre-wrap break-words text-emerald-300/90 border border-emerald-500/20">
                              {evalData.augmented_prompt}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

