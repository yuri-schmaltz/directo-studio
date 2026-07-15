"use client";

import Link from "next/link";
import { Menu, Target, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { LiveIndicator } from "@/components/live-indicator";
import { useEventStream } from "@/lib/ws";
import { cn } from "@/lib/utils";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/gallery": "Gallery",
  "/jobs": "Jobs",
  "/jobs/new": "Submit Job",
  "/presets": "Presets",
  "/cinema": "Cinema Engine",
  "/projects": "Projects",
  "/costs": "Costs",
  "/backup": "Backup",
  "/events": "Live Events",
  "/about": "About",
};

export function Header({ onMenuClick }: { onMenuClick?: () => void }) {
  const pathname = usePathname();
  const [dark, setDark] = useState(true);
  const { state } = useEventStream({ enabled: false }); // peek without subscribing

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (dark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [dark]);

  // Find title
  const title =
    TITLES[pathname] ??
    Object.entries(TITLES).find(
      ([k]) => k !== "/" && pathname.startsWith(k + "/"),
    )?.[1] ??
    "Directo";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg/80 backdrop-blur px-4 md:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={onMenuClick}
      >
        <Menu className="h-5 w-5" />
      </Button>
      <Link href="/" className="flex items-center gap-2 md:hidden">
        <Target className="h-5 w-5 text-brand-500" />
        <span className="font-semibold">Directo</span>
      </Link>
      <h1 className="text-base font-semibold hidden md:block">{title}</h1>
      <div className="ml-auto flex items-center gap-3">
        <div className="hidden sm:block">
          <LiveIndicator state={state} />
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setDark(!dark)}
          title="Toggle theme"
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
