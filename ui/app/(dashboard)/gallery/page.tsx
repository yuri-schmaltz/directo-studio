"use client";

import useSWR from "swr";
import { useState } from "react";
import { swrFetcher, api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton, EmptyState } from "@/components/ui/empty-state";
import { Star, Search, Image as ImageIcon } from "lucide-react";
import { cn, formatRelativeTime, shortId, truncate } from "@/lib/utils";
import type { ImageRecord } from "@/lib/types";

export default function GalleryPage() {
  const [project, setProject] = useState("");
  const [minRating, setMinRating] = useState(0);
  const [favorites, setFavorites] = useState(false);
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(48);

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
          {items.map((rec) => (
            <Card key={rec.id} className="overflow-hidden group">
              <div className="aspect-square bg-bg-muted flex items-center justify-center text-fg-subtle">
                <ImageIcon className="h-12 w-12" />
              </div>
              <CardContent className="p-3 space-y-2">
                <p
                  className="text-xs text-fg line-clamp-2"
                  title={rec.prompt}
                >
                  {truncate(rec.prompt, 100)}
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-0.5">
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
                  <span className="text-xs text-fg-subtle">
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
                {rec.tags && rec.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {rec.tags.slice(0, 3).map((t) => (
                      <Badge key={t}>{t}</Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
