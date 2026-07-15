"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { FolderKanban, Plus } from "lucide-react";

export default function ProjectsPage() {
  // For now we keep a client-side list (project creation not in the API
  // response list endpoint). The detail page still works via /api/projects/{id}.
  const [projects] = useState<Array<{ id: string; name: string; concept: string }>>(
    [],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Projects</h2>
          <p className="text-sm text-fg-muted">Creative projects with director agents</p>
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
          icon={<FolderKanban className="h-12 w-12" />}
          title="No projects yet"
          description="Create a project to bundle characters, style guides, and storyboards."
          action={
            <Link href="/projects/new">
              <Button>
                <Plus className="h-4 w-4" />
                Create
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Card key={p.id}>
              <CardHeader>
                <CardTitle className="text-base">{p.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-fg-muted">{p.concept}</p>
                <Badge variant="brand">{p.id.slice(0, 8)}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
