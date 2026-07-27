"use client";

import useSWR from "swr";
import { useState } from "react";
import { swrFetcher, api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton, EmptyState } from "@/components/ui/empty-state";
import { NPanel } from "@/components/n-panel";
import { SplitViewport } from "@/components/split-viewport";
import { Star, Search, Image as ImageIcon, Eye, SlidersHorizontal } from "lucide-react";
import { cn, formatRelativeTime, shortId, truncate } from "@/lib/utils";
import type { ImageRecord } from "@/lib/types";

export default function GalleryPage() {
  const [project, setProject] = useState("");
  const [minRating, setMinRating] = useState(0);
  const [favorites, setFavorites] = useState(false);
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(48);

  const [selectedItem, setSelectedItem] = useState<ImageRecord | null>(null);
  const [compareItems, setCompareItems] = useState<ImageRecord[]>([]);

  const params = new URLSearchParams({
    project,
    min_rating: String(minRating),
    favorites_only: String(favorites),
    limit: String(limit),
  });
  const { data, isLoading, mutate } = useSWR<{ items: ImageRecord[]; count: number }>(
    `/api/proxy/gallery?${params.toString()}`,
    swrFetcher,
    { refreshInterval: 5_000 },
  );

  const items = (data?.items ?? []).filter((r) => {
    if (search && !r.prompt.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  async function rateImage(id: string, rating: number) {
    try {
      await api.gallery.update(id, { rating } as any);
      mutate();
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Gallery</h2>
          <p className="text-sm text-fg-muted">
            {data?.count ?? 0} images total
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
          <div className="md:col-span-2">
            <Label>Search prompt</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-fg-subtle" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="cinematic, dragon, sunset…"
                className="pl-8"
              />
            </div>
          </div>
          <div>
            <Label>Project</Label>
            <Input
              value={project}
              onChange={(e) => setProject(e.target.value)}
              placeholder="all"
            />
          </div>
          <div>
            <Label>Min rating</Label>
            <Select
              value={String(minRating)}
              onChange={(e) => setMinRating(Number(e.target.value))}
            >
              <option value="0">Any</option>
              <option value="1">1+ ★</option>
              <option value="2">2+ ★★</option>
              <option value="3">3+ ★★★</option>
              <option value="4">4+ ★★★★</option>
              <option value="5">5 ★★★★★</option>
            </Select>
          </div>
          <div>
            <Label>Limit</Label>
            <Select
              value={String(limit)}
              onChange={(e) => setLimit(Number(e.target.value))}
            >
              <option value="24">24</option>
              <option value="48">48</option>
              <option value="96">96</option>
              <option value="200">200</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<ImageIcon className="h-12 w-12" />}
          title="No images match"
          description="Try a different filter, or submit a job to generate some."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {items.map((rec) => {
            const isCompared = compareItems.some((c) => c.id === rec.id);
            return (
              <Card
                key={rec.id}
                className="overflow-hidden group hover:border-accent/50 transition-colors cursor-pointer"
                onClick={() => setSelectedItem(rec)}
              >
                <div className="relative aspect-square bg-bg-muted flex items-center justify-center text-fg-subtle overflow-hidden">
                  {rec.url ? (
                    <img
                      src={rec.url}
                      alt={rec.prompt}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <ImageIcon className="h-12 w-12" />
                  )}

                  {/* Hover Quick Actions Overlay */}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <Button
                      variant="secondary"
                      className="h-8 px-2 text-xs bg-bg/80 backdrop-blur-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedItem(rec);
                      }}
                    >
                      <Eye className="h-3.5 w-3.5 mr-1 text-accent" />
                      Inspect (N)
                    </Button>
                    <Button
                      variant={isCompared ? "primary" : "secondary"}
                      className="h-8 px-2 text-xs bg-bg/80 backdrop-blur-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (isCompared) {
                          setCompareItems(compareItems.filter((c) => c.id !== rec.id));
                        } else {
                          if (compareItems.length >= 2) {
                            setCompareItems([compareItems[1], rec]);
                          } else {
                            setCompareItems([...compareItems, rec]);
                          }
                        }
                      }}
                    >
                      <SlidersHorizontal className="h-3.5 w-3.5 mr-1" />
                      {isCompared ? "Selected" : "Compare"}
                    </Button>
                  </div>
                </div>

                <CardContent className="p-3 space-y-2">
                  <p
                    className="text-xs text-fg line-clamp-2"
                    title={rec.prompt}
                  >
                    {truncate(rec.prompt, 100)}
                  </p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <button
                          key={n}
                          onClick={() => rateImage(rec.id, n === rec.rating ? 0 : n)}
                          className="p-0.5 rounded hover:bg-bg-muted"
                          title={`Rate ${n}`}
                        >
                          <Star
                            className={cn(
                              "h-3.5 w-3.5",
                              n <= rec.rating
                                ? "fill-warning text-warning"
                                : "text-fg-subtle",
                            )}
                          />
                        </button>
                      ))}
                    </div>
                    <span className="text-xs text-fg-subtle font-mono">
                      {formatRelativeTime(rec.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    {rec.project && (
                      <Badge variant="brand">{rec.project}</Badge>
                    )}
                    <span className="text-fg-subtle font-mono">
                      {shortId(rec.id)}
                    </span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Floating Compare Bar */}
      {compareItems.length > 0 && (
        <div className="fixed bottom-10 right-6 z-30 bg-bg-subtle border border-border p-3 rounded-lg shadow-2xl flex items-center gap-3 animate-fade-in font-mono text-xs">
          <span>Comparing {compareItems.length}/2 images</span>
          {compareItems.length === 2 && (
            <Button
              variant="primary"
              className="h-7 text-xs"
              onClick={() => {}}
            >
              Open Split Viewport
            </Button>
          )}
          <Button
            variant="ghost"
            className="h-7 text-xs"
            onClick={() => setCompareItems([])}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Modals */}
      <NPanel
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        onRate={(id, r) => rateImage(id, r)}
      />

      {compareItems.length === 2 && (
        <SplitViewport
          itemA={compareItems[0]}
          itemB={compareItems[1]}
          onClose={() => setCompareItems([])}
        />
      )}
    </div>
  );
}
