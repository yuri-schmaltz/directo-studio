"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea, Label, Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Clapperboard, AlertTriangle, Lightbulb, CheckCircle2 } from "lucide-react";
import type { CinemaReport, Scene } from "@/lib/types";

type Tab = "evaluate" | "parse";

export default function CinemaPage() {
  const [tab, setTab] = useState<Tab>("evaluate");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Cinema Engine</h2>
        <p className="text-sm text-fg-muted">
          19 cinematic rules to keep your prompts authentic
        </p>
      </div>

      <div className="flex gap-2">
        <Button
          variant={tab === "evaluate" ? "primary" : "secondary"}
          onClick={() => setTab("evaluate")}
        >
          Evaluate prompt
        </Button>
        <Button
          variant={tab === "parse" ? "primary" : "secondary"}
          onClick={() => setTab("parse")}
        >
          Parse script
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
          <CardTitle className="text-base flex items-center gap-2">
            Verdict
            {report && (
              <Badge variant={report.blocked ? "danger" : "success"}>
                {report.blocked ? "BLOCKED" : "OK"}
              </Badge>
            )}
            {report && (
              <span className="text-sm text-fg-muted ml-auto">
                score {report.score.toFixed(2)}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!report ? (
            <p className="text-sm text-fg-muted">
              Run an evaluation to see results.
            </p>
          ) : (
            <div className="space-y-3">
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

function ParseTab() {
  const [text, setText] = useState(
    "INT. KITCHEN - DAY\n\nALICE looks out the window.\n\nALICE\nIt's a beautiful day.\n\nEXT. PARK - DAY\n\nBOB walks by with a dog.",
  );
  const [scenes, setScenes] = useState<Scene[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function parse() {
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/cinema/parse-script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
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
          <CardTitle className="text-base">Script</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={14}
            spellCheck={false}
          />
          <Button onClick={parse} disabled={loading} className="w-full">
            {loading ? "Parsing…" : "Parse"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {scenes ? `${scenes.length} scene(s)` : "Output"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!scenes ? (
            <p className="text-sm text-fg-muted">Run a parse to see scenes.</p>
          ) : scenes.length === 0 ? (
            <p className="text-sm text-fg-muted">No scenes found.</p>
          ) : (
            <div className="space-y-3">
              {scenes.map((s) => (
                <div
                  key={s.number}
                  className="rounded-md border border-border bg-bg-subtle p-3"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <Badge variant="brand">Scene {s.number}</Badge>
                    <span className="text-xs text-fg-subtle">
                      {s.time_of_day}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-fg">{s.heading}</p>
                  {s.characters.length > 0 && (
                    <p className="text-xs text-fg-muted mt-1">
                      {s.characters.join(", ")}
                    </p>
                  )}
                  {s.prompt && (
                    <pre className="mt-2 text-xs font-mono bg-bg-muted p-2 rounded whitespace-pre-wrap break-words">
                      {s.prompt}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
