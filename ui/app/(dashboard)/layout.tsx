"use client";

import { Sidebar } from "@/components/nav/sidebar";
import { Header } from "@/components/nav/header";
import { StatusBar } from "@/components/status-bar";
import { CommandPalette } from "@/components/command-palette";
import { NotificationsProvider } from "@/components/notifications-provider";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Target, X } from "lucide-react";
import { cn } from "@/lib/utils";

const MOBILE_NAV_GROUPS = [
  {
    title: "Project & Concept",
    items: [
      { href: "/projects", label: "Projects" },
    ],
  },
  {
    title: "Production & Generation",
    items: [
      { href: "/cinema", label: "Cinema Engine" },
      { href: "/animatics", label: "Animatics" },
      { href: "/media-hub", label: "Media Hub" },
    ],
  },
  {
    title: "Assets & Execution",
    items: [
      { href: "/jobs", label: "Render Queue" },
    ],
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.key >= "1" && e.key <= "9") {
        e.preventDefault();
        const index = parseInt(e.key, 10) - 1;
        const routes = [
          "/projects",
          "/gallery",
          "/jobs",
          "/presets",
          "/cinema",
          "/",
          "/animatics",
          "/style-bible",
          "/media-hub",
        ];
        if (routes[index]) {
          router.push(routes[index]);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [router]);

  return (
    <NotificationsProvider>
      <div className="min-h-screen flex flex-col justify-between">
        <CommandPalette />
        <Sidebar />
        <div className="md:pl-60 flex flex-col flex-1 min-h-[calc(100vh-28px)]">
          <Header onMenuClick={() => setMobileOpen(true)} />
          <main className="flex-1 p-3.5 md:p-4.5 w-full max-w-[1840px] mx-auto animate-fade-in pb-8">
            {children}
          </main>
        </div>
        <div className="w-full fixed bottom-0 left-0 right-0 z-50">
          <StatusBar />
        </div>

        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <div
              className="absolute inset-0 bg-black/50"
              onClick={() => setMobileOpen(false)}
            />
            <div className="absolute inset-y-0 left-0 w-64 bg-bg border-r border-border p-4 flex flex-col gap-4 overflow-y-auto">
              <div className="flex items-center justify-between">
                <Link href="/projects" className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-accent" />
                  <span className="font-semibold text-fg font-sans">Directo Studio</span>
                </Link>
                <button
                  onClick={() => setMobileOpen(false)}
                  className="p-1 rounded hover:bg-bg-muted"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <nav className="flex flex-col gap-3 font-sans">
                {MOBILE_NAV_GROUPS.map((group, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="text-[10px] font-mono uppercase text-fg-subtle tracking-wider px-1">
                      {group.title}
                    </div>
                    <div className="flex flex-col gap-0.5">
                      {group.items.map(({ href, label }) => (
                        <Link
                          key={href}
                          href={href}
                          onClick={() => setMobileOpen(false)}
                          className="rounded px-2.5 py-1.5 text-xs font-medium text-fg-muted hover:text-fg hover:bg-bg-muted"
                        >
                          {label}
                        </Link>
                      ))}
                    </div>
                  </div>
                ))}
              </nav>
            </div>
          </div>
        )}
      </div>
    </NotificationsProvider>
  );
}
