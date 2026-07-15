"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { ArrowLeft, Send } from "lucide-react";
import Link from "next/link";
import { JOB_KINDS } from "@/lib/types";

const KIND_TEMPLATES: Record<string, Record<string, unknown>> = {
  "image.generate": {
    prompt: "a beautiful sunset over the ocean, dramatic clouds, 8k",
    model: "flux-dev",
    steps: 28,
    cfg: 4.5,
  },
  "image.upscale": {
    image_id: "img-abc123",
    scale: 2,
  },
  "video.render": {
    project: "scene-001",
    duration: 5,
    fps: 24,
  },
  "audio.synth": {
    text: "ambient music, calm, 90bpm",
    duration: 30,
  },
  "text.enhance": {
    prompt: "a dragon on a mountain",
    target: "flux-dev",
  },
};

export default function NewJobPage() {
  const router = useRouter();
  const [kind, setKind] = useState<string>(JOB_KINDS[0]);
  const [project, setProject] = useState("");
  const [priority, setPriority] = useState(100);
  const [payload, setPayload] = useState(
    JSON.stringify(KIND_TEMPLATES[JOB_KINDS[0]], null, 2),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function onKindChange(newKind: string) {
    setKind(newKind);
    if (KIND_TEMPLATES[newKind]) {
      setPayload(JSON.stringify(KIND_TEMPLATES[newKind], null, 2));
    }
  }

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      const parsed = JSON.parse(payload);
      const res = await api.jobs.submit({
        kind,
        payload: parsed,
        project: project || null,
        priority,
      });
      router.push(`/jobs?new=${res.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Link
          href="/jobs"
          className="text-fg-muted hover:text-fg flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
      </div>

      <div>
        <h2 className="text-2xl font-bold tracking-tight">Submit Job</h2>
        <p className="text-sm text-fg-muted">
          Send a job to the Directo queue
        </p>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Job kind</Label>
              <Select value={kind} onChange={(e) => onKindChange(e.target.value)}>
                {JOB_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Project (optional)</Label>
              <Input
                value={project}
                onChange={(e) => setProject(e.target.value)}
                placeholder="alpha, beta, …"
              />
            </div>
          </div>

          <div>
            <Label>Priority</Label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={1000}
                step={10}
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="flex-1"
              />
              <span className="font-mono text-sm w-12 text-right">
                {priority}
              </span>
            </div>
            <p className="text-xs text-fg-subtle mt-1">
              Higher = sooner
            </p>
          </div>

          <div>
            <Label>Payload (JSON)</Label>
            <Textarea
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              rows={10}
              spellCheck={false}
            />
            <p className="text-xs text-fg-subtle mt-1">
              The shape of this object depends on the job kind.
            </p>
          </div>

          {error && (
            <div className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Link href="/jobs">
              <Button variant="secondary">Cancel</Button>
            </Link>
            <Button onClick={submit} disabled={submitting}>
              <Send className="h-4 w-4" />
              {submitting ? "Submitting…" : "Submit"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
