/**
 * SectionHeader — the standard section header per the Singularity design language.
 *
 * eyebrow (uppercase, muted) + title (signal weight) + trailing pills/actions.
 */
import type { ReactNode } from "react";

export interface SectionHeaderProps {
  /** Small uppercase label (e.g. "Welcome to muse", "Studio pipeline"). */
  eyebrow: string;
  /** Main title in signal weight. */
  title: string;
  /** Optional trailing content (pills, status dots, actions). */
  trailing?: ReactNode;
}

export function SectionHeader({
  eyebrow,
  title,
  trailing,
}: SectionHeaderProps) {
  return (
    <div className="section-header">
      <div className="heads">
        <span className="eyebrow">{eyebrow}</span>
        <h2 className="section-title">{title}</h2>
      </div>
      {trailing && <div className="trailing">{trailing}</div>}
    </div>
  );
}

export default SectionHeader;