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
} from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/gallery", label: "Gallery", icon: Image },
  { href: "/jobs", label: "Jobs", icon: Workflow },
  { href: "/presets", label: "Presets", icon: Palette },
  { href: "/cinema", label: "Cinema", icon: Clapperboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/costs", label: "Costs", icon: DollarSign },
  { href: "/backup", label: "Backup", icon: Database },
  { href: "/events", label: "Live Events", icon: Radio },
  { href: "/about", label: "About", icon: Info },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:flex-col md:w-56 md:fixed md:inset-y-0 z-40 border-r border-border bg-bg-subtle">
      <div className="flex items-center gap-2 px-4 h-14 border-b border-border">
        <Target className="h-5 w-5 text-brand-500" />
        <span className="font-semibold text-fg">Directo</span>
        <span className="text-xs text-fg-subtle ml-auto">v1.0</span>
      </div>
      <nav className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-bg-muted text-fg"
                  : "text-fg-muted hover:text-fg hover:bg-bg-muted/50",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-3 text-xs text-fg-subtle">
        <a
          href="https://github.com/yuri-schmaltz/directo"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-fg"
        >
          GitHub →
        </a>
      </div>
    </aside>
  );
}
