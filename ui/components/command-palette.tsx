"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  LayoutDashboard,
  Image,
  Workflow,
  Palette,
  Clapperboard,
  FolderKanban,
  DollarSign,
  Database,
  Radio,
  Settings,
  PlusCircle,
  X,
  Command,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandItem {
  id: string;
  title: string;
  category: string;
  icon: any;
  href?: string;
  action?: () => void;
  shortcut?: string;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const items: CommandItem[] = [
    { id: "dash", title: "Go to Dashboard", category: "Navigation", icon: LayoutDashboard, href: "/", shortcut: "Alt+1" },
    { id: "gal", title: "Open Gallery", category: "Navigation", icon: Image, href: "/gallery", shortcut: "Alt+2" },
    { id: "jobs", title: "View Jobs Queue", category: "Navigation", icon: Workflow, href: "/jobs", shortcut: "Alt+3" },
    { id: "new-job", title: "Submit New Job", category: "Actions", icon: PlusCircle, href: "/jobs/new" },
    { id: "preset", title: "Browse Presets", category: "Navigation", icon: Palette, href: "/presets", shortcut: "Alt+4" },
    { id: "cinema", title: "Launch Cinema Engine", category: "Tools", icon: Clapperboard, href: "/cinema", shortcut: "Alt+5" },
    { id: "proj", title: "Manage Projects", category: "Navigation", icon: FolderKanban, href: "/projects", shortcut: "Alt+6" },
    { id: "back", title: "Database Backup", category: "System", icon: Database, href: "/settings" },
    { id: "set", title: "Settings & Maintenance", category: "System", icon: Settings, href: "/settings" },
  ];

  const filtered = items.filter(
    (item) =>
      item.title.toLowerCase().includes(query.toLowerCase()) ||
      item.category.toLowerCase().includes(query.toLowerCase())
  );

  function execute(item: CommandItem) {
    setOpen(false);
    setQuery("");
    if (item.href) {
      router.push(item.href);
    } else if (item.action) {
      item.action();
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-xl bg-bg-subtle border border-border rounded-lg shadow-2xl overflow-hidden font-sans">
        {/* Search Bar */}
        <div className="flex items-center px-3.5 border-b border-border bg-bg-muted/40">
          <Search className="h-4 w-4 text-accent shrink-0 mr-2.5" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search route... (e.g. Cinema, Jobs, Submit)"
            className="w-full h-11 bg-transparent text-sm text-fg placeholder:text-fg-subtle outline-none"
          />
          <button
            onClick={() => setOpen(false)}
            className="p-1 rounded text-fg-subtle hover:text-fg hover:bg-bg-muted"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Command Items List */}
        <div className="max-h-80 overflow-y-auto p-1.5 scrollbar-thin divide-y divide-border/20">
          {filtered.length === 0 ? (
            <div className="p-6 text-center text-xs text-fg-muted">
              No matching commands found.
            </div>
          ) : (
            filtered.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => execute(item)}
                  className="w-full flex items-center justify-between px-3 py-2 text-left rounded text-sm text-fg-muted hover:text-fg hover:bg-bg-muted transition-colors group"
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="h-4 w-4 text-fg-subtle group-hover:text-accent transition-colors" />
                    <span>{item.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-fg-subtle uppercase tracking-wider font-mono">
                      {item.category}
                    </span>
                    {item.shortcut && (
                      <kbd className="px-1.5 py-0.5 bg-bg-muted border border-border rounded text-[10px] font-mono text-fg">
                        {item.shortcut}
                      </kbd>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer info */}
        <div className="px-3.5 py-2 border-t border-border bg-bg-muted/30 flex items-center justify-between text-[11px] text-fg-subtle font-mono">
          <div className="flex items-center gap-1.5">
            <Command className="h-3 w-3 text-accent" />
            <span>Directo Command Palette</span>
          </div>
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>ESC Close</span>
          </div>
        </div>
      </div>
    </div>
  );
}
