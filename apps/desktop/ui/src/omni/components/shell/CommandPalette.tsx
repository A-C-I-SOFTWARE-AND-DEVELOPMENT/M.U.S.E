import { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { CAPABILITIES } from '@/lib/capabilities';
import { cockpit } from '@/adapters/cockpit';
import { useNexusStore } from '@/store/useNexusStore';
import { applyUpdate, checkForUpdate } from '@/lib/appUpdate';
import { fetchMirror } from '@/lib/repoSync';

interface Cmd {
  id: string;
  label: string;
  hint: string;
  run: () => void;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const navigate = useNavigate();
  const setWallpaper = useNexusStore((s) => s.setWallpaper);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    const openEvt = () => setOpen(true);
    window.addEventListener('nexus:open-palette', openEvt);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('nexus:open-palette', openEvt);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setQ('');
      setSel(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const cmds = useMemo<Cmd[]>(() => {
    const nav: Cmd[] = [
      ['Atlas Crown', '/atlas'], ['Stations', '/stations'], ['Chat', '/'], ['Console', '/console'],
      ['Jobs', '/jobs'], ['Approvals', '/approvals'], ['Autonomy', '/autonomy'],
      ['Fusion', '/fusion'], ['Steer', '/steer'], ['Axiom Gate', '/axiom'],
      ['Shipyard', '/shipyard'], ['Forge', '/forge'], ['Fleet', '/fleet'], ['Agents', '/agents'],
      ['Studio', '/studio'], ['Fabrication', '/fabrication'], ['Game Foundry', '/game-foundry'],
      ['Cinema Stage', '/cinema'], ['Release Dock', '/release'], ['Repo', '/repo'],
      ['Models', '/models'], ['Second Brain', '/second-brain'], ['Observatory', '/observatory'],
      ['Championship', '/championship'], ['Civilizations', '/civilizations'], ['Council', '/council'],
      ['Federation', '/federation'], ['Activity', '/activity'], ['Share', '/share'], ['Settings', '/settings'],
    ].map(([label, to]) => ({ id: `nav-${to}`, label: `Go to ${label}`, hint: 'page', run: () => navigate(to) }));
    const actions: Cmd[] = [
      { id: 'wallpaper', label: 'Enter wallpaper mode', hint: 'observatory', run: () => { navigate('/observatory'); setWallpaper(true); } },
      { id: 'estop', label: 'Emergency stop', hint: 'halt all work', run: () => void cockpit.emergencyStop() },
      { id: 'connect', label: 'Install & connect everything', hint: 'setup', run: () => window.dispatchEvent(new CustomEvent('nexus:open-setup')) },
      { id: 'update', label: 'Update Muse (pull latest from main)', hint: 'sync', run: () => void applyUpdate() },
      { id: 'checkupdate', label: 'Check for Muse update', hint: 'sync', run: () => void checkForUpdate() },
      { id: 'syncrepo', label: 'Sync Muse repo mirror', hint: 'repo', run: () => { void fetchMirror(true); navigate('/repo'); } },
    ];
    const caps: Cmd[] = CAPABILITIES.map((c) => ({
      id: `cap-${c.id}`,
      label: c.title,
      hint: c.plane,
      run: () => {
        if (c.surface.kind === 'tab') navigate(c.surface.to);
        else navigate('/'); // capability drawers live on the Console
      },
    }));
    return [...nav, ...actions, ...caps];
  }, [navigate, setWallpaper]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (s ? cmds.filter((c) => (c.label + ' ' + c.hint).toLowerCase().includes(s)) : cmds).slice(0, 30);
  }, [q, cmds]);

  const choose = (c: Cmd) => {
    c.run();
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} className="fixed inset-0 z-[70] bg-black/60" />
          <motion.div
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 420, damping: 34 }}
            className="fixed inset-x-3 top-[12vh] z-[71] mx-auto max-w-md overflow-hidden rounded-2xl border border-[var(--hairline)] bg-[var(--bg-elev)] shadow-2xl"
            style={{ boxShadow: 'var(--shadow-3)' }}
          >
            <input
              ref={inputRef}
              value={q}
              onChange={(e) => { setQ(e.target.value); setSel(0); }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)); }
                else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
                else if (e.key === 'Enter' && filtered[sel]) choose(filtered[sel]);
              }}
              placeholder="Search commands, capabilities, pages…"
              className="w-full border-b border-[var(--hairline)] bg-transparent px-4 py-3.5 text-[14px] text-[var(--ink)] outline-none"
            />
            <div className="max-h-[52vh] overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <div className="px-4 py-6 text-center text-[12px] text-[var(--ink-dim)]">No matches</div>
              ) : (
                filtered.map((c, i) => (
                  <button
                    key={c.id}
                    onClick={() => choose(c)}
                    onMouseEnter={() => setSel(i)}
                    className="flex w-full items-center justify-between px-4 py-2.5 text-left"
                    style={{ background: i === sel ? 'color-mix(in oklab, var(--octa-glow) 12%, transparent)' : 'transparent' }}
                  >
                    <span className="text-[13px] text-[var(--ink)]">{c.label}</span>
                    <span className="mono text-[9px] uppercase text-[var(--ink-faint)]">{c.hint}</span>
                  </button>
                ))
              )}
            </div>
            <div className="mono flex items-center justify-between border-t border-[var(--hairline)] px-4 py-2 text-[9px] text-[var(--ink-faint)]">
              <span>↑↓ navigate · ↵ select · esc close</span>
              <span>⌘K</span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
