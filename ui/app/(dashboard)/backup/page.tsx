"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Database, Check, X } from "lucide-react";
import type { BackupResult } from "@/lib/types";

const TARGETS = [
  { value: "queue", label: "queue.db (job queue)" },
  { value: "gallery", label: "gallery.db (images)" },
  { value: "costs", label: "costs.db (spend records)" },
  { value: "events", label: "events.db (event log)" },
  { value: "presets", label: "presets.db (preset packs)" },
];

export default function BackupPage() {
  const [db, setDb] = useState("queue");
  const [result, setResult] = useState<BackupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
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
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Backup</h2>
        <p className="text-sm text-fg-muted">
          Hot-copy a database with integrity verification
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Database className="h-4 w-4" /> Create backup
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-sm font-medium text-fg-muted mb-1.5 block">
              Database
            </label>
            <Select value={db} onChange={(e) => setDb(e.target.value)}>
              {TARGETS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>
          <Button onClick={run} disabled={loading}>
            {loading ? "Backing up…" : "Create backup"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Card>
          <CardContent className="p-4 text-sm text-danger flex items-center gap-2">
            <X className="h-4 w-4" /> {error}
          </CardContent>
        </Card>
      )}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Check className="h-4 w-4 text-success" />
              Backup complete
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Path" value={result.path} mono />
            <Row
              label="Size"
              value={`${result.size_bytes.toLocaleString()} bytes`}
            />
            <Row
              label="Verified"
              value={result.verified ? "✓ yes" : "✗ no"}
            />
            <Row
              label="Duration"
              value={`${result.duration_ms.toFixed(1)} ms`}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-fg-muted">{label}</span>
      <Badge variant="default" className={mono ? "font-mono text-xs" : ""}>
        {value}
      </Badge>
    </div>
  );
}
