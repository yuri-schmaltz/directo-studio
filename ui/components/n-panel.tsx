"use client";

import { X, Copy, Star, Cpu, FileText, Check, Sparkles } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatRelativeTime, shortId } from "@/lib/utils";
import type { ImageRecord } from "@/lib/types";

interface NPanelProps {
  item: ImageRecord | null;
  onClose: () => void;
  onRate?: (id: string, rating: number) => void;
}

export function NPanel({ item, onClose, onRate }: NPanelProps) {
  const [copied, setCopied] = useState<string | null>(null);

  if (!item) return null;

  function copyText(text: string, label: string) {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  }

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-80 bg-bg-subtle border-l border-border shadow-2xl flex flex-col font-sans animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-border bg-bg-muted/50">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent shrink-0" />
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-fg">
            Inspector (N-Panel)
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-fg-subtle hover:text-fg hover:bg-bg-muted transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 scrollbar-thin text-xs">
        {/* Preview image */}
        <div className="rounded border border-border overflow-hidden bg-bg">
          <img
            src={item.url || `/api/proxy/gallery/${item.id}/file`}
            alt={item.prompt}
            className="w-full object-cover max-h-48"
          />
        </div>

        {/* Rating & Project */}
        <div className="flex items-center justify-between border-b border-border/40 pb-3">
          <div>
            <span className="text-fg-subtle block mb-1 font-mono">Rating</span>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => onRate?.(item.id, star)}
                  className="p-0.5 hover:scale-110 transition-transform"
                >
                  <Star
                    className={`h-4 w-4 ${
                      star <= (item.rating ?? 0)
                        ? "fill-accent text-accent"
                        : "text-fg-subtle hover:text-fg-muted"
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>
          <div className="text-right">
            <span className="text-fg-subtle block mb-1 font-mono">Project</span>
            <Badge variant="brand">{item.project || "default"}</Badge>
          </div>
        </div>

        {/* Prompt */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-fg-subtle font-mono flex items-center gap-1">
              <FileText className="h-3 w-3 text-accent" /> Prompt
            </span>
            <button
              onClick={() => copyText(item.prompt, "prompt")}
              className="text-[10px] text-fg-subtle hover:text-accent flex items-center gap-1 font-mono"
            >
              {copied === "prompt" ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
              {copied === "prompt" ? "Copied" : "Copy"}
            </button>
          </div>
          <div className="p-2.5 bg-bg border border-border rounded font-mono text-[11px] leading-relaxed text-fg break-words">
            {item.prompt}
          </div>
        </div>

        {/* Technical Parameters */}
        <div className="space-y-2 border-t border-border/40 pt-3">
          <span className="text-fg-subtle font-mono flex items-center gap-1">
            <Cpu className="h-3 w-3 text-accent" /> Execution Parameters
          </span>
          <div className="grid grid-cols-2 gap-2 font-mono">
            <div className="bg-bg p-2 rounded border border-border">
              <span className="text-fg-subtle block text-[10px]">Job ID</span>
              <span className="text-fg font-semibold">{shortId(item.job_id || item.id)}</span>
            </div>
            <div className="bg-bg p-2 rounded border border-border">
              <span className="text-fg-subtle block text-[10px]">Created</span>
              <span className="text-fg">{formatRelativeTime(item.created_at)}</span>
            </div>
            {item.params && (
              <>
                <div className="bg-bg p-2 rounded border border-border">
                  <span className="text-fg-subtle block text-[10px]">Width x Height</span>
                  <span className="text-fg">{item.params.width || 1024}x{item.params.height || 1024}</span>
                </div>
                <div className="bg-bg p-2 rounded border border-border">
                  <span className="text-fg-subtle block text-[10px]">Steps / CFG</span>
                  <span className="text-fg">{item.params.steps || 30} / {item.params.cfg_scale || 7.5}</span>
                </div>
              </>
            )}
          </div>
        </div>

      </div>

      {/* Footer Actions */}
      <div className="p-3 border-t border-border bg-bg-muted/30 flex gap-2">
        <Button
          variant="secondary"
          className="flex-1 text-xs h-8"
          onClick={() => copyText(JSON.stringify(item, null, 2), "json")}
        >
          {copied === "json" ? "JSON Copied!" : "Export JSON"}
        </Button>
      </div>
    </div>
  );
}
