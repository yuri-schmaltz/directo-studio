import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-[50vh] flex items-center justify-center p-6">
      <Card className="max-w-md w-full text-center">
        <CardContent className="py-12 space-y-3">
          <p className="text-5xl font-bold text-fg-subtle">404</p>
          <h1 className="text-xl font-semibold">Page not found</h1>
          <p className="text-sm text-fg-muted">
            The page you&apos;re looking for doesn&apos;t exist.
          </p>
          <Link href="/">
            <Button>Back to dashboard</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
