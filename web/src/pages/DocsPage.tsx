import { useLayoutEffect } from "react";
import { ExternalLink } from "lucide-react";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";
import { PluginSlot } from "@/plugins";

export const HERMES_DOCS_URL = "https://hermes-agent.nousresearch.com/docs/";

export default function DocsPage() {
  const { t } = useI18n();
  const { setTitle, setAfterTitle, setEnd } = usePageHeader();

  // Sentence-case header + one-line description + primary action (design 2.3).
  useLayoutEffect(() => {
    setTitle("Documentation");
    setAfterTitle(
      <span className="hidden whitespace-nowrap text-xs text-[var(--fg-faint)] sm:inline">
        The full muse agent manual, embedded.
      </span>,
    );
    setEnd(
      <a
        href={HERMES_DOCS_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-elev)] px-2.5 py-1 text-xs text-[var(--fg-dim)] transition-colors hover:bg-[var(--bg-mute)] hover:text-[var(--fg)]"
      >
        <ExternalLink className="size-3.5" />
        {t.app.openDocumentation}
      </a>,
    );
    return () => {
      setTitle(null);
      setAfterTitle(null);
      setEnd(null);
    };
  }, [setTitle, setAfterTitle, setEnd, t]);

  return (
    <div
      className={cn(
        "flex min-h-0 w-full min-w-0 flex-1 flex-col",
        "pt-1 sm:pt-2",
      )}
    >
      <PluginSlot name="docs:top" />
      <iframe
        title={t.app.nav.documentation}
        src={HERMES_DOCS_URL}
        className={cn(
          "min-h-0 w-full min-w-0 flex-1",
          // Frame chrome: Singularity border token + 12px radius (design 2.3).
          "rounded-xl border border-[var(--border)]",
          // Docusaurus paints over a transparent <html> / <body> and
          // relies on the browser's canvas color (light by default) to
          // fill the viewport. Inheriting the dashboard's dark color
          // scheme makes that canvas dark, so the docs body text — which
          // is tuned for a light canvas — becomes near-invisible. Force a
          // light color scheme + white background on the iframe element so
          // the docs render cleanly regardless of the active dashboard
          // theme or the user's prefers-color-scheme.
          "[color-scheme:light] bg-white",
        )}
        sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
        referrerPolicy="no-referrer-when-downgrade"
      />
      <PluginSlot name="docs:bottom" />
    </div>
  );
}
