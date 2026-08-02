"use client";

import Link from "next/link";
import { Menu, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePathname } from "next/navigation";

import { ConnectionWidget } from "@/components/nav/connection-widget";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/gallery": "Gallery",
  "/jobs": "Jobs",
  "/jobs/new": "Submit Job",
  "/presets": "Presets",
  "/cinema": "Cinema Engine",
  "/projects": "Projects",
  "/backup": "Backup",
  "/about": "About",
};

export function Header({ onMenuClick }: { onMenuClick?: () => void }) {
  const pathname = usePathname();

  // Find title
  const title =
    TITLES[pathname] ??
    Object.entries(TITLES).find(
      ([k]) => k !== "/" && pathname.startsWith(k + "/"),
    )?.[1] ??
    "Directo";

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-border bg-bg/80 backdrop-blur px-4 md:px-6 select-none">
      <div className="flex items-center gap-3">
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
        <h1 className="text-xs font-semibold tracking-wide text-fg hidden md:block font-mono uppercase">
          {title}
        </h1>
      </div>
      <ConnectionWidget />
    </header>
  );
}
