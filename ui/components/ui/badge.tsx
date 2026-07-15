import { cn } from "@/lib/utils";
import * as React from "react";

type Variant = "default" | "success" | "warning" | "danger" | "brand";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

const variantClasses: Record<Variant, string> = {
  default: "badge",
  success: "badge badge-success",
  warning: "badge badge-warning",
  danger: "badge badge-danger",
  brand: "badge badge-brand",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  return <span className={cn(variantClasses[variant], className)} {...props} />;
}
