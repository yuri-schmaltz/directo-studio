"use client";

import Link from "next/link";
import { Menu, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePathname } from "next/navigation";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { Clapperboard, ChevronDown } from "lucide-react";
import { ConnectionWidget } from "@/components/nav/connection-widget";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/gallery": "Galeria de Ativos",
  "/jobs": "Fila de Execução (Jobs)",
  "/jobs/new": "Nova Tarefa",
  "/presets": "Biblioteca de Presets",
  "/cinema": "Cinema & Video Production Engine",
  "/projects": "Projetos & Loglines",
  "/style-bible": "Bíblia de Estilo Visual",
  "/animatics": "Estúdio de Animáticas & Storyboard",
  "/media-hub": "Media Hub & Ingestão",
  "/settings": "Configurações do Sistema",
  "/backup": "Backup & Restauração",
  "/about": "Sobre o Directo Studio",
};

export function Header({ onMenuClick }: { onMenuClick?: () => void }) {
  const pathname = usePathname();
  const { data: projectsData } = useSWR<{ items: any[] }>("/api/proxy/projects", swrFetcher);
  const projects = projectsData?.items || [];

  const [activeProject, setActiveProject] = useState<string>("");

  useEffect(() => {
    const saved = localStorage.getItem("directo_active_project");
    if (saved) {
      setActiveProject(saved);
    } else if (projects.length > 0) {
      setActiveProject(projects[0].id || projects[0].name);
    }
  }, [projects]);

  const handleSelectProject = (id: string) => {
    setActiveProject(id);
    localStorage.setItem("directo_active_project", id);
  };

  const currentProjectObj = projects.find((p) => p.id === activeProject || p.name === activeProject);

  // Find title
  const title =
    TITLES[pathname] ??
    Object.entries(TITLES).find(
      ([k]) => k !== "/" && pathname.startsWith(k + "/"),
    )?.[1] ??
    "Directo";

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-border bg-bg/85 backdrop-blur px-4 md:px-6 select-none">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden h-8 w-8"
          onClick={onMenuClick}
        >
          <Menu className="h-4 w-4" />
        </Button>
        <Link href="/projects" className="flex items-center gap-2 md:hidden">
          <Target className="h-4 w-4 text-accent" />
          <span className="font-semibold text-sm">Directo Studio</span>
        </Link>
        <div className="hidden md:flex items-center gap-3">
          <h1 className="text-xs font-semibold tracking-wide text-fg font-mono uppercase">
            {title}
          </h1>
          <span className="text-border">|</span>
          {/* Active Project Switcher */}
          <div className="relative group flex items-center gap-1.5 text-xs font-mono bg-bg-muted/70 hover:bg-bg-muted px-2.5 py-1 rounded border border-border/80 transition-colors cursor-pointer">
            <Clapperboard className="h-3.5 w-3.5 text-amber-400" />
            <span className="text-fg-subtle">PROJETO:</span>
            <select
              value={activeProject}
              onChange={(e) => handleSelectProject(e.target.value)}
              className="bg-transparent text-amber-400 font-semibold focus:outline-none cursor-pointer pr-1"
            >
              {projects.length === 0 ? (
                <option value="">Sem projeto ativo</option>
              ) : (
                projects.map((p) => (
                  <option key={p.id || p.name} value={p.id || p.name} className="bg-slate-900 text-fg">
                    {p.name}
                  </option>
                ))
              )}
            </select>
            <ChevronDown className="h-3 w-3 text-fg-subtle" />
          </div>
        </div>
      </div>
      <ConnectionWidget />
    </header>
  );
}
