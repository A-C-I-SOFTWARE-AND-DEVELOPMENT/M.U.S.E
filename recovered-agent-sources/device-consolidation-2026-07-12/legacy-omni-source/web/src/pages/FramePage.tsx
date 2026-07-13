import { ExternalLink } from "lucide-react";
import { usePageHeader } from "@/contexts/usePageHeader";
import { useEffect } from "react";

interface FramePageProps {
  title: string;
  subtitle: string;
  src: string;
  openLabel?: string;
}

export default function FramePage({ title, subtitle, src, openLabel = "Open standalone" }: FramePageProps) {
  const { setTitle, setAfterTitle, setEnd } = usePageHeader();

  useEffect(() => {
    setTitle(title);
    setAfterTitle(<span className="text-xs normal-case text-midground/55">{subtitle}</span>);
    setEnd(
      <a
        className="inline-flex items-center gap-2 rounded border border-current/20 px-3 py-1.5 text-xs text-midground/80 hover:bg-midground/5 hover:text-midground"
        href={src}
        target="_blank"
        rel="noreferrer"
      >
        <ExternalLink className="h-3.5 w-3.5" />
        {openLabel}
      </a>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
      setTitle(null);
    };
  }, [openLabel, setAfterTitle, setEnd, setTitle, src, subtitle, title]);

  return (
    <section className="flex min-h-[calc(100dvh-8rem)] min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-current/20 bg-black/35 shadow-[0_0_80px_rgba(122,224,255,0.06)]">
      <iframe
        title={title}
        src={src}
        className="min-h-0 w-full flex-1 border-0 bg-black"
        allow="clipboard-read; clipboard-write; fullscreen; web-share"
      />
    </section>
  );
}
