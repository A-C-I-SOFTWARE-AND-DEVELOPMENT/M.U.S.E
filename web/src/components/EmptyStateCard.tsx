import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Zero-data placeholder, per the muse design language's EmptyState spec
 * (docs/brand/muse-design-language.md §EmptyState): a centered stack with
 * generous negative space — dimmed icon, title, helper line, optional CTA.
 *
 * The icon sits inside a subtle 1px hairline circle (matte — tonal border
 * only, no glow, no shadow). All colors route through the existing theme
 * vars (`border-border`, `text-muted-foreground`) so every theme — not just
 * Singularity — renders it correctly.
 */
interface EmptyStateCardProps {
  /** Lucide icon rendered inside the hairline circle. */
  icon: LucideIcon;
  /** Short headline — what's empty. */
  title: string;
  /** Optional helper line — how to get data here. */
  description?: string;
  /** Optional call-to-action (a Button, a Link, …). */
  action?: ReactNode;
  className?: string;
}

export function EmptyStateCard({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateCardProps) {
  return (
    <Card className={cn("border-border/60", className)}>
      <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <span
          aria-hidden
          className="flex h-12 w-12 items-center justify-center rounded-full border border-border"
        >
          <Icon className="h-5 w-5 text-muted-foreground opacity-60" />
        </span>
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        {description && (
          <p className="-mt-1.5 text-xs text-muted-foreground/60">
            {description}
          </p>
        )}
        {action && <div className="mt-1">{action}</div>}
      </CardContent>
    </Card>
  );
}
