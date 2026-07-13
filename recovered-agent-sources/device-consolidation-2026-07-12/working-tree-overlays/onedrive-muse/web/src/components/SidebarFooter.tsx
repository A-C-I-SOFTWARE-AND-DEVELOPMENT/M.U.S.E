import { useState } from "react";
import { ChevronUp, Cpu } from "lucide-react";
import { Typography } from "@/components/NouiTypography";
import { ModelPickerDialog } from "@/components/ModelPickerDialog";
import { useModelStatus } from "@/hooks/useModelStatus";
import { useSidebarStatus } from "@/hooks/useSidebarStatus";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";

function shortModel(model: string | undefined): string {
  if (!model) return "—";
  const parts = model.split("/");
  return parts[parts.length - 1] || model;
}

export function SidebarFooter() {
  const status = useSidebarStatus();
  const { info, loading, refresh } = useModelStatus();
  const { t } = useI18n();
  const [pickerOpen, setPickerOpen] = useState(false);

  const modelLabel = shortModel(info?.model);
  const providerLabel = info?.provider || "";

  return (
    <div
      className={cn(
        "flex shrink-0 flex-col gap-1.5",
        "px-5 py-2.5",
        "border-t border-current/10",
      )}
    >
      <button
        type="button"
        onClick={() => setPickerOpen(true)}
        title={
          info?.model
            ? `${info.provider} · ${info.model} — click to switch`
            : "Switch model"
        }
        className={cn(
          "group flex w-full min-w-0 items-center gap-2 rounded-sm",
          "px-1.5 py-1 -mx-1.5",
          "text-left transition-colors",
          "hover:bg-current/5",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/40",
        )}
      >
        <Cpu className="h-3 w-3 shrink-0 text-muted-foreground/70 group-hover:text-midground" />
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono-ui text-[0.7rem] tracking-[0.04em] text-foreground/90">
            {loading && !info ? "…" : modelLabel}
          </div>
          {providerLabel ? (
            <div className="truncate text-[0.55rem] uppercase tracking-[0.12em] text-muted-foreground/60">
              {providerLabel}
            </div>
          ) : null}
        </div>
        <ChevronUp className="h-3 w-3 shrink-0 text-muted-foreground/50 opacity-0 transition-opacity group-hover:opacity-100" />
      </button>

      <div className="flex items-center justify-between gap-2">
        <Typography
          mondwest
          className="font-mono-ui text-[0.7rem] tabular-nums tracking-[0.1em] text-muted-foreground/70 lowercase"
        >
          {status?.version != null ? `v${status.version}` : "—"}
        </Typography>

        <a
          href="https://nousresearch.com"
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "font-mondwest text-[0.65rem] tracking-[0.15em] text-midground",
            "transition-opacity hover:opacity-90",
            "focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/40",
          )}
          style={{ mixBlendMode: "plus-lighter" }}
        >
          {t.app.footer.org}
        </a>
      </div>

      {pickerOpen && (
        <ModelPickerDialog
          loader={api.getModelOptions}
          alwaysGlobal
          title="Switch Model"
          onApply={async ({ provider, model }) => {
            await api.setModelAssignment({
              scope: "main",
              provider,
              model,
              task: "",
            });
            refresh();
          }}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
}
