"use client";

import { useState } from "react";
import { X, SlidersHorizontal, Layers } from "lucide-react";
import type { ImageRecord } from "@/lib/types";

interface SplitViewportProps {
  itemA: ImageRecord | null;
  itemB: ImageRecord | null;
  onClose: () => void;
}

export function SplitViewport({ itemA, itemB, onClose }: SplitViewportProps) {
  const [sliderPosition, setSliderPosition] = useState(50);

  if (!itemA || !itemB) return null;

  const srcA = itemA.url || `/api/proxy/gallery/${itemA.id}/file`;
  const srcB = itemB.url || `/api/proxy/gallery/${itemB.id}/file`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-4xl bg-bg-subtle border border-border rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-bg-muted/50">
          <div className="flex items-center gap-2 font-mono text-xs font-semibold text-fg">
            <SlidersHorizontal className="h-4 w-4 text-accent" />
            <span>Split Viewport Comparator</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-fg-subtle hover:text-fg hover:bg-bg-muted"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Viewport Comparison Canvas */}
        <div className="relative flex-1 min-h-[400px] max-h-[600px] overflow-hidden select-none bg-black flex items-center justify-center">
          {/* Base Image B (Right / Underneath) */}
          <img
            src={srcB}
            alt={itemB.prompt}
            className="absolute inset-0 w-full h-full object-contain pointer-events-none"
          />

          {/* Overlay Image A (Left / Clipped) */}
          <div
            className="absolute inset-0 overflow-hidden pointer-events-none"
            style={{ width: `${sliderPosition}%` }}
          >
            <img
              src={srcA}
              alt={itemA.prompt}
              className="absolute inset-0 w-full h-full object-contain max-w-none"
              style={{ width: "100%", height: "100%" }}
            />
          </div>

          {/* Vertical Slider Handle */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-accent z-20 cursor-ew-resize flex items-center justify-center shadow-lg"
            style={{ left: `${sliderPosition}%` }}
          >
            <div className="w-6 h-6 bg-accent text-white rounded-full flex items-center justify-center -ml-3 shadow-md">
              <Layers className="h-3.5 w-3.5" />
            </div>
          </div>

          {/* Interactive Range Input overlay */}
          <input
            type="range"
            min="0"
            max="100"
            value={sliderPosition}
            onChange={(e) => setSliderPosition(Number(e.target.value))}
            className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-30"
          />

          {/* Image Labels */}
          <div className="absolute bottom-3 left-3 bg-bg/80 border border-border rounded px-2.5 py-1 text-[11px] font-mono text-fg z-10 pointer-events-none backdrop-blur-xs">
            <span className="text-accent font-bold mr-1.5">A:</span>
            {itemA.prompt.slice(0, 30)}...
          </div>
          <div className="absolute bottom-3 right-3 bg-bg/80 border border-border rounded px-2.5 py-1 text-[11px] font-mono text-fg z-10 pointer-events-none backdrop-blur-xs">
            <span className="text-emerald-400 font-bold mr-1.5">B:</span>
            {itemB.prompt.slice(0, 30)}...
          </div>
        </div>

        {/* Footer info */}
        <div className="p-3 border-t border-border bg-bg-muted/30 flex items-center justify-between text-xs font-mono text-fg-subtle">
          <span>Drag horizontal slider to compare generations</span>
          <span>{sliderPosition}% Split</span>
        </div>
      </div>
    </div>
  );
}
