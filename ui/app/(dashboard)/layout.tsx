"use client";

import { Sidebar } from "@/components/nav/sidebar";
import { Header } from "@/components/nav/header";
import { useState } from "react";
import Link from "next/link";
import { Target, X } from "lucide-react";
import { cn } from "@/lib/utils";

const MOBILE_NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/gallery", label: "Gallery" },
  { href: "/jobs", label: "Jobs" },
  { href: "/presets", label: "Presets" },
  { href: "/cinema", label: "Cinema" },
  { href: "/projects", label: "Projects" },
  { href: "/animatics", label: "Animatics" },
  { href: "/costs", label: "Costs" },
  { href: "/backup", label: "Backup" },
  { href: "/events", label: "Live Events" },
  { href: "/about", label: "About" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="md:pl-56 flex flex-col min-h-screen">
        <Header onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto animate-fade-in">
          {children}
        </main>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-64 bg-bg border-r border-border p-4 flex flex-col gap-2">
            <div className="flex items-center justify-between mb-2">
              <Link href="/" className="flex items-center gap-2">
                <Target className="h-5 w-5 text-brand-500" />
                <span className="font-semibold">Directo</span>
              </Link>
              <button
                onClick={() => setMobileOpen(false)}
                className="p-1 rounded hover:bg-bg-muted"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex flex-col gap-1">
              {MOBILE_NAV.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium hover:bg-bg-muted",
                  )}
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      )}
    </div>
  );
}
