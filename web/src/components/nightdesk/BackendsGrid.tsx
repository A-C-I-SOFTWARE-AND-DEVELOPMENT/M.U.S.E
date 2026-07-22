import {
  normalizeNdStatus,
  useNightdeskOverview,
} from "./useNightdesk";

/* ------------------------------------------------------------------ */
/* BackendsGrid — "Runs anywhere — terminal backends & gateways".      */
/* Execution backends + messaging platforms + the synthesized CLI/TUI  */
/* row as small tiles: name, one-line detail, status chip. Chip colors */
/* come from the nightdesk.css status scale.                           */
/* ------------------------------------------------------------------ */

interface TileSpec {
  key: string;
  name: string;
  detail: string;
  status: string;
  active: boolean;
}

function StatusChip({ status }: { status: string }) {
  const normalized = normalizeNdStatus(status);
  return (
    <span className="nd-chip" data-status={normalized}>
      {status || normalized}
    </span>
  );
}

function Tile({ tile }: { tile: TileSpec }) {
  return (
    <div className="nd-tile" data-active={tile.active} title={tile.detail}>
      <div className="nd-tile-top">
        <span className="nd-tile-name">{tile.name}</span>
        <StatusChip status={tile.status} />
      </div>
      <span className="nd-tile-detail">{tile.detail}</span>
    </div>
  );
}

export default function BackendsGrid() {
  const { data, error, loading } = useNightdeskOverview(30000);
  const backends = data?.backends ?? null;

  const execution: TileSpec[] = (backends?.execution ?? []).map((b) => ({
    key: `exec:${b.name}`,
    name: b.label || b.name,
    detail:
      b.detail ||
      (b.active ? "active execution backend" : "execution backend"),
    status: b.status,
    active:
      b.active ||
      (backends?.active_execution_backend != null &&
        backends.active_execution_backend === b.name),
  }));

  const messaging: TileSpec[] = (backends?.messaging ?? []).map((p) => ({
    key: `msg:${p.id}`,
    name: p.name || p.id,
    detail:
      p.error_message ||
      (p.configured === false
        ? "not configured"
        : p.enabled === false
          ? "disabled"
          : (p.raw_state ?? p.status)),
    status: p.status,
    active: false,
  }));

  const cliTui: TileSpec[] = backends?.cli_tui
    ? [
        {
          key: "cli_tui",
          name: backends.cli_tui.name || "CLI / TUI",
          detail: backends.cli_tui.detail || "terminal gateway",
          status: backends.cli_tui.status,
          active: false,
        },
      ]
    : [];

  const groups: { label: string; tiles: TileSpec[]; empty: string }[] = [
    { label: "Execution backends", tiles: execution, empty: "no execution backends reported" },
    { label: "Messaging gateways", tiles: messaging, empty: "no messaging platforms configured" },
    { label: "Local terminals", tiles: cliTui, empty: "CLI / TUI row unavailable" },
  ];

  return (
    <section className="nd-panel" aria-label="Backends and gateways">
      <div className="nd-panel-head">
        <span className="nd-label">Runs anywhere — terminal backends &amp; gateways</span>
        {loading && !backends && <span className="nd-sub">loading…</span>}
      </div>
      <div className="nd-panel-body">
        {error && !backends ? (
          <div className="nd-empty">backend status unavailable: {error}</div>
        ) : (
          groups.map((group) => (
            <div className="nd-backends-group" key={group.label}>
              <span className="nd-label">{group.label}</span>
              {group.tiles.length === 0 ? (
                <div className="nd-empty">{group.empty}</div>
              ) : (
                <div className="nd-tiles">
                  {group.tiles.map((tile) => (
                    <Tile key={tile.key} tile={tile} />
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
