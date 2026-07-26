"use client";

import useSWR from "swr";
import Link from "next/link";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { FolderKanban, Plus, Trash2 } from "lucide-react";

export default function ProjectsPage() {
  const { data, mutate } = useSWR<{ items: Array<{ id: string; name: string; concept: string }> }>(
    "/api/proxy/projects",
    swrFetcher
  );
  const projects = data?.items || [];

  async function handleDelete(projectId: string) {
    if (!confirm("Are you sure you want to delete this project?")) return;
    try {
      const res = await fetch(`/api/proxy/projects/${projectId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        mutate();
      }
    } catch (err) {
      console.error("Failed to delete project", err);
    }
  }

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
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-base font-semibold">{p.name}</CardTitle>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-fg-muted hover:text-danger hover:bg-danger/10"
                  onClick={() => handleDelete(p.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
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
