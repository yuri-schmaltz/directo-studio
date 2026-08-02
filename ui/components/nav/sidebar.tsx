"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Image,
  Workflow,
  Palette,
  Clapperboard,
  FolderKanban,
  DollarSign,
  Database,
  Radio,
  Info,
  Target,
  Film,
  Settings,
  BookOpen,
  Zap,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: any;
  shortcut?: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Projeto & Conceito",
    items: [
      { href: "/projects", label: "Projetos", icon: FolderKanban, shortcut: "Alt+1" },
      { href: "/style-bible", label: "Bíblia de Estilo", icon: BookOpen, shortcut: "Alt+8" },
      { href: "/presets", label: "Presets", icon: Palette, shortcut: "Alt+4" },
    ],
  },
  {
    title: "Produção & Geração",
    items: [
      { href: "/cinema", label: "Cinema Engine", icon: Clapperboard, shortcut: "Alt+5" },
      { href: "/animatics", label: "Animáticas", icon: Film, shortcut: "Alt+7" },
      { href: "/media-hub", label: "Media Hub", icon: Zap, shortcut: "Alt+9" },
    ],
  },
  {
    title: "Assets & Execução",
    items: [
      { href: "/gallery", label: "Galeria", icon: Image, shortcut: "Alt+2" },
      { href: "/jobs", label: "Fila de Render", icon: Workflow, shortcut: "Alt+3" },
    ],
  },
  {
    title: "Sistema",
    items: [
      { href: "/settings", label: "Configurações", icon: Settings },
      { href: "/about", label: "Sobre", icon: Info },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex md:flex-col md:w-60 md:fixed md:top-0 md:bottom-7 z-40 border-r border-border bg-bg-subtle select-none">
      {/* Header Brand */}
      <div className="flex items-center gap-2.5 px-4 h-12 border-b border-border shrink-0">
        <Target className="h-5 w-5 text-accent" />
        <span className="font-semibold text-fg tracking-tight text-base">Directo Studio</span>
        <span className="text-[10px] font-mono text-accent/80 ml-auto bg-accent/10 px-1.5 py-0.5 rounded border border-accent/20">
          v1.1.5
        </span>
      </div>

      {/* Nav Groups */}
      <nav className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-3">
        {NAV_GROUPS.map((group, groupIdx) => (
          <div key={groupIdx} className="space-y-1">
            <div className="px-2.5 pt-1.5 pb-0.5 text-[11px] font-mono font-bold uppercase tracking-wider text-fg-subtle">
              {group.title}
            </div>
            <div className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon, shortcut }) => {
                const active =
                  href === "/" ? pathname === "/" : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "flex items-center justify-between rounded px-3 py-2 text-sm font-medium transition-colors group",
                      active
                        ? "bg-bg-muted text-fg font-semibold border-l-2 border-accent pl-2.5"
                        : "text-fg-muted hover:text-fg hover:bg-bg-muted/60"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-accent" : "text-fg-subtle group-hover:text-fg")} />
                      <span>{label}</span>
                    </div>
                    {shortcut && (
                      <kbd className="hidden group-hover:inline-block text-[10px] font-mono text-fg-subtle bg-bg border border-border px-1.5 py-0.5 rounded">
                        {shortcut}
                      </kbd>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
