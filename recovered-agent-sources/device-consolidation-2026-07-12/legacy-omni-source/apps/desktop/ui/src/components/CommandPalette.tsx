import { useEffect, useMemo, useRef, useState } from "react";
import type { RouteDef } from "../routes";

export type CommandPaletteProps = {
  routes: RouteDef[];
  onSelect: (id: string) => void;
};

const routeKeywords: Record<string, string> = {
  home: "today overview continue recent",
  chat: "ask conversation message new",
  jobs: "work agents tasks runs background",
  approvals: "needs you review permission decisions",
  autonomy: "control safety mode permissions",
  observatory: "health models tools memory status audit",
  settings: "preferences devices connection gateway updates",
};

export function CommandPalette({ routes, onSelect }: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return routes;
    return routes.filter((route) =>
      `${route.label} ${routeKeywords[route.id] || ""}`.toLowerCase().includes(q),
    );
  }, [query, routes]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  useEffect(() => setActive(0), [query]);

  const choose = (id: string) => {
    onSelect(id);
    setOpen(false);
  };

  return (
    <>
      <button
        className="command-trigger"
        onClick={() => setOpen(true)}
        aria-label="Open command palette"
      >
        <span aria-hidden="true">⌕</span>
        <span>Search Muse</span>
        <kbd>Ctrl K</kbd>
      </button>
      {open && (
        <div className="command-backdrop" role="presentation" onMouseDown={() => setOpen(false)}>
          <section
            className="command-palette"
            role="dialog"
            aria-modal="true"
            aria-label="Muse command palette"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="command-input-wrap">
              <span aria-hidden="true">⌕</span>
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    setActive((index) => Math.min(index + 1, Math.max(matches.length - 1, 0)));
                  } else if (event.key === "ArrowUp") {
                    event.preventDefault();
                    setActive((index) => Math.max(index - 1, 0));
                  } else if (event.key === "Enter" && matches[active]) {
                    event.preventDefault();
                    choose(matches[active].id);
                  }
                }}
                placeholder="Go to chat, work, approvals, settings…"
                aria-label="Search Muse destinations"
              />
              <kbd>Esc</kbd>
            </div>
            <div className="command-results" role="listbox">
              {matches.length === 0 ? (
                <div className="command-empty">No matching destination</div>
              ) : (
                matches.map((route, index) => (
                  <button
                    key={route.id}
                    className={"command-result" + (index === active ? " active" : "")}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => choose(route.id)}
                    role="option"
                    aria-selected={index === active}
                  >
                    <NavIcon id={route.id} />
                    <span>{route.label}</span>
                    <span className="command-arrow" aria-hidden="true">↵</span>
                  </button>
                ))
              )}
            </div>
            <footer className="command-footer">
              <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
              <span><kbd>↵</kbd> open</span>
            </footer>
          </section>
        </div>
      )}
    </>
  );
}

export function NavIcon({ id }: { id: string }) {
  const paths: Record<string, React.ReactNode> = {
    home: <><path d="M3.5 10.5 10 4l6.5 6.5"/><path d="M5.5 9.2V17h9V9.2"/></>,
    chat: <><path d="M4 5.5h12v8H9l-4 3v-3H4z"/><path d="M7 9.5h6"/></>,
    jobs: <><rect x="3.5" y="5.5" width="13" height="10" rx="2"/><path d="M7 5.5V4h6v1.5M3.5 9.5h13"/></>,
    approvals: <><path d="M10 3.5 16 6v4.5c0 3.3-2.3 5.5-6 6.5-3.7-1-6-3.2-6-6.5V6z"/><path d="m7.5 10 1.7 1.7 3.6-3.8"/></>,
    autonomy: <><circle cx="10" cy="10" r="6.5"/><path d="M10 6.5v3.8l2.4 1.4M10 2v1.5M10 16.5V18"/></>,
    observatory: <><path d="M3.5 15.5h13M5.5 13V9M10 13V5M14.5 13V7"/><circle cx="10" cy="5" r="1"/></>,
    settings: <><circle cx="10" cy="10" r="2.5"/><path d="M10 3.2v1.4M10 15.4v1.4M3.2 10h1.4M15.4 10h1.4M5.2 5.2l1 1M13.8 13.8l1 1M14.8 5.2l-1 1M6.2 13.8l-1 1"/></>,
  };
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      {paths[id] || paths.home}
    </svg>
  );
}
