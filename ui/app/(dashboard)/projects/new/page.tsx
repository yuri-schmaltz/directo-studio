"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowLeft, FolderKanban } from "lucide-react";
import Link from "next/link";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [concept, setConcept] = useState("");
  const [logline, setLogline] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, concept, logline }),
      });
      if (r.ok) {
        const data = await r.json();
        router.push(`/projects?created=${data.id}`);
      } else {
        setError(`${r.status} ${r.statusText}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Link
        href="/projects"
        className="text-fg-muted hover:text-fg flex items-center gap-1 text-sm"
      >
        <ArrowLeft className="h-4 w-4" /> Back
      </Link>

      <div>
        <h2 className="text-2xl font-bold tracking-tight">New project</h2>
        <p className="text-sm text-fg-muted">
          Bundle characters, style guides, and storyboards
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FolderKanban className="h-4 w-4" /> Details
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Name *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="The Last Dragon"
            />
          </div>
          <div>
            <Label>Concept</Label>
            <Textarea
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              rows={3}
              placeholder="A short description of the project, themes, mood, etc."
            />
          </div>
          <div>
            <Label>Logline</Label>
            <Input
              value={logline}
              onChange={(e) => setLogline(e.target.value)}
              placeholder="One-sentence summary of the story"
            />
          </div>
          {error && (
            <div className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
              {error}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Link href="/projects">
              <Button variant="secondary">Cancel</Button>
            </Link>
            <Button onClick={submit} disabled={submitting}>
              {submitting ? "Creating…" : "Create"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
