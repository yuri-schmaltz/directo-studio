import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function AboutPage() {
  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">About</h2>
        <p className="text-sm text-fg-muted">
          Directo — production-ready creative AI platform
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
        {/* Left Column: Stack & Links */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Stack</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <Row label="Frontend" value="Next.js 14 + TypeScript + Tailwind" />
              <Row label="Backend" value="FastAPI (Python 3.11)" />
              <Row label="Storage" value="SQLite (WAL mode)" />
              <Row label="WebSocket" value="FastAPI native + reconnecting client" />
              <Row label="Optional deps" value="streamlit (legacy GUI), click (CLI)" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <a
                className="block text-fg-muted hover:text-fg transition-colors"
                href="https://github.com/yuri-schmaltz/directo"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub: yuri-schmaltz/directo →
              </a>
              <a
                className="block text-fg-muted hover:text-fg transition-colors"
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
              >
                FastAPI docs (when running) →
              </a>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: 5 Phases */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">5 phases</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Phase
              n={0}
              name="Stabilization"
              desc="Observability, vault, queue, gallery, storyboard PDF"
              tests={56}
            />
            <Phase
              n={1}
              name="Creative foundation"
              desc="Variants, references, image history, multi-view gallery"
              tests={25}
            />
            <Phase
              n={2}
              name="Technical scale"
              desc="Multi-node ComfyUI, VRAM profiling, presets, 13-provider LLM"
              tests={27}
            />
            <Phase
              n={3}
              name="Differentiation"
              desc="19 cinematic rules, storyboard canvas, script parser"
              tests={31}
            />
            <Phase
              n={4}
              name="Creative direction"
              desc="Director agent, moodboard, slerp, animatic"
              tests={22}
            />
            <Phase
              n={5}
              name="Production hardening"
              desc="Migrations, backup, cache, events, plugins, API, WS, CLI"
              tests={46}
            />
            <div className="pt-3 border-t border-border flex items-center justify-between">
              <span className="font-medium">Total</span>
              <Badge variant="brand">283/283 tests</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-fg-muted">{label}</span>
      <span className="font-mono text-xs text-right">{value}</span>
    </div>
  );
}

function Phase({
  n,
  name,
  desc,
  tests,
}: {
  n: number;
  name: string;
  desc: string;
  tests: number;
}) {
  return (
    <div className="flex items-center gap-3 py-1.5">
      <Badge variant="brand">P{n}</Badge>
      <div className="flex-1 min-w-0">
        <p className="font-medium">{name}</p>
        <p className="text-xs text-fg-subtle truncate">{desc}</p>
      </div>
      <Badge>{tests} tests</Badge>
    </div>
  );
}
