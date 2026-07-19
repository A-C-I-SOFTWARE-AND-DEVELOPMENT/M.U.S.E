import { useCallback, useEffect, useState } from "react";
import { ExternalLink, RefreshCw, Puzzle, Trash2, Eye, EyeOff } from "lucide-react";
import type { Translations } from "@/i18n/types";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { HubAgentPluginRow, PluginsHubResponse } from "@/lib/api";
import { Button } from "@nous-research/ui/ui/components/button";
import { EmptyStateCard } from "@/components/EmptyStateCard";
import { Select, SelectOption } from "@nous-research/ui/ui/components/select";
import { Switch } from "@nous-research/ui/ui/components/switch";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { CommandBlock } from "@nous-research/ui/ui/components/command-block";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/useToast";
import { Toast } from "@/components/Toast";
import { useI18n } from "@/i18n";
import { PluginSlot } from "@/plugins";
import { cn } from "@/lib/utils";
import { usePageHeader } from "@/contexts/usePageHeader";

/** Select value for built-in memory (`config` uses empty string). Never use `""` — UI Select maps empty value to an empty label. */
const MEMORY_PROVIDER_BUILTIN = "__hermes_memory_builtin__";

export default function PluginsPage() {
  const [hub, setHub] = useState<PluginsHubResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [installId, setInstallId] = useState("");
  const [installForce, setInstallForce] = useState(false);
  const [installEnable, setInstallEnable] = useState(true);
  const [installBusy, setInstallBusy] = useState(false);
  const [rescanBusy, setRescanBusy] = useState(false);
  const [memorySel, setMemorySel] = useState(MEMORY_PROVIDER_BUILTIN);
  const [contextSel, setContextSel] = useState("compressor");
  const [providerBusy, setProviderBusy] = useState(false);
  const [rowBusy, setRowBusy] = useState<string | null>(null);

  const { toast, showToast } = useToast();
  const { t } = useI18n();
  const { setEnd } = usePageHeader();

  const loadHub = useCallback(() => {
    return api
      .getPluginsHub()
      .then((h) => {
        setHub(h);
        setLoadError(null);
        const p = h.providers;
        setMemorySel(p.memory_provider ? p.memory_provider : MEMORY_PROVIDER_BUILTIN);
        setContextSel(p.context_engine || "compressor");
      })
      .catch((e) => {
        setLoadError(String(e));
        showToast(t.common.loading, "error");
      });
  }, [showToast, t.common.loading]);

  useEffect(() => {
    setLoading(true);
    void loadHub().finally(() => setLoading(false));
  }, [loadHub]);

  useEffect(() => {
    setEnd(
      <div className="flex w-full min-w-0 justify-start">
        <Button
          ghost
          size="sm"
          className="w-max max-w-full shrink-0 gap-2"
          disabled={loading || rescanBusy}
          onClick={() => void onRescan()}
        >
          {rescanBusy ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
          {t.pluginsPage.refreshDashboard}
        </Button>
      </div>,
    );
    return () => setEnd(null);
  }, [loading, rescanBusy, setEnd, t.pluginsPage.refreshDashboard]);

  const onInstall = async () => {
    const id = installId.trim();
    if (!id) {
      showToast(t.pluginsPage.installHint, "error");
      return;
    }
    setInstallBusy(true);
    try {
      const r = await api.installAgentPlugin({
        identifier: id,
        force: installForce,
        enable: installEnable,
      });
      showToast(`${r.plugin_name ?? id} installed`, "success");
      if ((r.warnings?.length ?? 0) > 0) showToast(r.warnings!.join(" "), "error");
      if ((r.missing_env?.length ?? 0) > 0)
        showToast(`${t.pluginsPage.missingEnvWarn} ${r.missing_env!.join(", ")}`, "error");
      setInstallId("");
      await loadHub();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Install failed", "error");
    } finally {
      setInstallBusy(false);
    }
  };

  const onRescan = async () => {
    setRescanBusy(true);
    try {
      const rc = await api.rescanPlugins();
      showToast(
        `${t.pluginsPage.refreshDashboard} (${rc.count})`,
        "success",
      );
      await loadHub();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Rescan failed", "error");
    } finally {
      setRescanBusy(false);
    }
  };

  const onSaveProviders = async () => {
    setProviderBusy(true);
    try {
      await api.savePluginProviders({
        memory_provider:
          memorySel === MEMORY_PROVIDER_BUILTIN ? "" : memorySel,
        context_engine: contextSel,
      });
      showToast(t.pluginsPage.savedProviders, "success");
      await loadHub();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Save failed", "error");
    } finally {
      setProviderBusy(false);
    }
  };

  const setRuntimeLoading = async (name: string, fn: () => Promise<unknown>) => {
    setRowBusy(name);
    try {
      await fn();
      await loadHub();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Failed", "error");
    } finally {
      setRowBusy(null);
    }
  };

  const rows = hub?.plugins ?? [];
  const providers = hub?.providers;

  return (
    <div className="flex flex-col gap-4">
      <PluginSlot name="plugins:top" />

      <p className="text-sm text-[var(--fg-dim)]">{t.pluginsPage.headline}</p>

      {loadError && !hub && (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--err)]/40 px-4 py-3"
          style={{
            backgroundColor: "color-mix(in srgb, var(--err) 8%, var(--bg-elev))",
          }}
          role="alert"
        >
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--err)]">
              Failed to load plugins
            </p>
            <p className="mt-0.5 break-words text-xs text-[var(--fg-dim)]">
              {loadError}
            </p>
          </div>
          <Button
            size="sm"
            outlined
            onClick={() => {
              setLoading(true);
              void loadHub().finally(() => setLoading(false));
            }}
            prefix={<RefreshCw className="h-3.5 w-3.5" />}
          >
            {t.common.retry}
          </Button>
        </div>
      )}

      <div className={cn("flex w-full flex-col gap-8")}>

        {providers && (
          <Card className="rounded-xl">
            <CardHeader>
              <CardTitle className="normal-case tracking-normal">{t.pluginsPage.providersHeading}</CardTitle>
              <p className="text-xs text-[var(--fg-dim)]">
                {t.pluginsPage.providersHint}
              </p>
            </CardHeader>

            <CardContent className="flex flex-col gap-6">

              <div className="grid gap-6 sm:grid-cols-2 max-w-full">
              <div className="grid gap-2 min-w-0">
                <Label htmlFor="mem-provider">{t.pluginsPage.memoryProviderLabel}</Label>

                <Select
                  id="mem-provider"
                  className="w-full"
                  value={memorySel}
                  onValueChange={setMemorySel}
                >
                  <SelectOption value={MEMORY_PROVIDER_BUILTIN}>
                    {`(${t.pluginsPage.providerDefaults})`}
                  </SelectOption>

                  {providers.memory_options.map((o) => (
                    <SelectOption key={o.name} value={o.name}>
                      {o.name}
                    </SelectOption>
                  ))}
                </Select>
              </div>

              <div className="grid gap-2 min-w-0">
                <Label htmlFor="ctx-engine">{t.pluginsPage.contextEngineLabel}</Label>

                <Select
                  id="ctx-engine"
                  className="w-full"
                  value={contextSel}
                  onValueChange={setContextSel}
                >
                  <SelectOption value="compressor">compressor</SelectOption>

                  {providers.context_options
                    .filter((o) => o.name !== "compressor")
                    .map((o) => (
                      <SelectOption key={o.name} value={o.name}>
                        {o.name}
                      </SelectOption>
                    ))}
                </Select>
              </div>
              </div>

              <Button
                className="w-fit gap-2"
                size="sm"
                disabled={providerBusy}
                onClick={() => void onSaveProviders()}
              >
                {providerBusy ? <Spinner /> : null}
                {t.pluginsPage.saveProviders}
              </Button>
            </CardContent>
          </Card>
        )}

        <Card className="rounded-xl">
          <CardHeader>
            <CardTitle className="normal-case tracking-normal">{t.pluginsPage.installHeading}</CardTitle>
            <p className="text-xs text-[var(--fg-dim)]">
              {t.pluginsPage.installHint}
            </p>
          </CardHeader>


          <CardContent className="flex flex-col gap-4">

            <div className="flex flex-col gap-2">

              <Label htmlFor="install-url">{t.pluginsPage.identifierLabel}</Label>

              <Input
                className="normal-case font-sans lowercase"
                id="install-url"
                placeholder="owner/repo or https://..."
                spellCheck={false}
                value={installId}
                onChange={(e) => setInstallId(e.target.value)}
              />
            </div>


            <div className="flex flex-wrap items-center gap-8">

              <div className="flex items-center gap-3">

                <Switch checked={installForce} onCheckedChange={setInstallForce} />

                <span className="text-xs text-[var(--fg-dim)]">
                  {t.pluginsPage.forceReinstall}
                </span>
              </div>

              <div className="flex items-center gap-3">

                <Switch checked={installEnable} onCheckedChange={setInstallEnable} />

                <span className="text-xs text-[var(--fg-dim)]">
                  {t.pluginsPage.enableAfterInstall}
                </span>
              </div>
            </div>

            <Button
              className="w-fit gap-2"
              size="sm"
              disabled={installBusy}
              onClick={() => void onInstall()}
            >
              {installBusy ? <Spinner /> : <Puzzle className="h-3.5 w-3.5" />}
              {t.pluginsPage.installBtn}
            </Button>

            <p className="text-[0.65rem] text-[var(--fg-faint)]">
              {t.pluginsPage.rescanHint}
            </p>

            <p className="text-[0.65rem] text-[var(--fg-faint)]">
              {t.pluginsPage.removeHint}
            </p>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-3">

          <h3 className="text-sm font-semibold text-[var(--fg-dim)]">
            {t.pluginsPage.pluginListHeading}
          </h3>

          {loading ? (
            <div className="grid gap-4 sm:grid-cols-2" aria-busy="true">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-xl border border-[var(--border)] p-4"
                  style={{ backgroundColor: "var(--bg-elev)" }}
                >
                  <div className="flex items-center gap-2">
                    <div className="h-4 w-32 animate-pulse rounded bg-[var(--bg-mute)]" />
                    <div className="h-4 w-12 animate-pulse rounded-full bg-[var(--bg-mute)]" />
                  </div>
                  <div className="mt-4 grid gap-2">
                    <div className="h-3 w-full animate-pulse rounded bg-[var(--bg-mute)]/70" />
                    <div className="h-3 w-2/3 animate-pulse rounded bg-[var(--bg-mute)]/70" />
                  </div>
                </div>
              ))}
            </div>
          ) : rows.length === 0 ? (
            <EmptyStateCard
              icon={Puzzle}
              title={t.common.noResults}
              description={t.pluginsPage.installHint}
            />
          ) : (

            <ul className="grid gap-4 sm:grid-cols-2">

              {rows.map((row: HubAgentPluginRow) => (

                <li key={row.name}>


                  <PluginRowCard
                    {...{ row, rowBusy, setRuntimeLoading, showToast, t }}
                  />

                </li>
              ))}
            </ul>
          )}
        </div>

        {(hub?.orphan_dashboard_plugins?.length ?? 0) > 0 ? (


          <div className="flex flex-col gap-3 opacity-95">

            <h3 className="text-sm font-semibold text-[var(--fg-dim)]">
              {t.pluginsPage.orphanHeading}
            </h3>

            <ul className="flex flex-col gap-2 rounded-xl border border-[var(--border)] p-4" style={{ backgroundColor: "var(--bg-elev)" }}>

              {hub!.orphan_dashboard_plugins.map((m) => (

                <li className="text-xs text-[var(--fg-dim)]" key={m.name}>


                  {m.label ?? m.name} — {m.description || m.tab?.path}


                  {!m.tab?.hidden ? (


                    <Link className="ml-3 inline-flex items-center gap-1 text-[var(--accent)] hover:underline" to={m.tab.path}>


                      <ExternalLink className="h-3 w-3 opacity-65" />

                      {t.pluginsPage.openTab}
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <Toast toast={toast} />
      <PluginSlot name="plugins:bottom" />
    </div>
  );
}

interface PluginRowCardProps {

  row: HubAgentPluginRow;
  rowBusy: string | null;
  setRuntimeLoading: (
    name: string,
    fn: () => Promise<unknown>,
  ) => Promise<void>;

  showToast: (msg: string, variant: "success" | "error") => void;
  t: Translations;
}

function PluginRowCard(props: PluginRowCardProps) {
  const {
    row,
    rowBusy,
    setRuntimeLoading,
    showToast,
    t,
  } = props;

  const dm = row.dashboard_manifest;

  const tabPath = dm?.tab && !dm.tab.hidden ? dm.tab.override ?? dm.tab.path : null;

  const busy = rowBusy === row.name;
  const [confirmRemove, setConfirmRemove] = useState(false);
  const enabled = row.runtime_status === "enabled";

  const chip =
    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium leading-4";

  const toggleEnabled = (checked: boolean) => {
    void setRuntimeLoading(row.name, async () => {
      if (checked) {
        await api.enableAgentPlugin(row.name);
        showToast(t.pluginsPage.enableRuntime, "success");
      } else {
        await api.disableAgentPlugin(row.name);
        showToast(t.pluginsPage.disableRuntime, "success");
      }
    });
  };

  return (

    <Card
      className={cn("rounded-xl", busy ? "opacity-70" : undefined)}
      style={{ backgroundColor: "var(--bg-elev)" }}
    >


      <CardContent className="flex flex-col gap-4 px-5 py-4">


        <div className="flex flex-wrap items-start justify-between gap-4">

          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">

            <span className="truncate font-semibold">{row.name}</span>

            {/* version chip — faint */}
            <span className={`${chip} font-mono-ui text-[var(--fg-faint)] border-[var(--border)] bg-transparent`}>
              v{row.version || "—"}
            </span>

            <span className={`${chip} text-[var(--fg-faint)] border-[var(--border)] bg-transparent`}>
              {t.pluginsPage.sourceBadge}: {row.source}
            </span>

            {enabled ? (
              <span className={`${chip} text-[var(--ok)] border-[var(--ok)]/30 bg-[var(--ok)]/10`}>
                {t.common.enabled}
              </span>
            ) : row.runtime_status === "disabled" ? (
              <span className={`${chip} text-[var(--fg-faint)] border-[var(--border)] bg-transparent`}>
                {t.common.disabled}
              </span>
            ) : (
              <span className={`${chip} text-[var(--warn)] border-[var(--warn)]/30 bg-[var(--warn)]/10`}>
                {row.runtime_status}
              </span>
            )}

            {row.auth_required ? (
              <span className={`${chip} text-[var(--err)] border-[var(--err)]/30 bg-[var(--err)]/10`}>
                {t.pluginsPage.authRequired}
              </span>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">

            {/* enabled switch — accent track when on */}
            <Switch
              checked={enabled}
              disabled={busy}
              onCheckedChange={toggleEnabled}
              aria-label={`${t.pluginsPage.enableRuntime} ${row.name}`}
              style={
                enabled
                  ? {
                      backgroundColor:
                        "color-mix(in srgb, var(--accent) 25%, transparent)",
                      borderColor:
                        "color-mix(in srgb, var(--accent) 55%, transparent)",
                    }
                  : undefined
              }
            />

            {tabPath ? (

              <Link
                className="inline-flex items-center gap-1 rounded border border-[var(--border)] px-2.5 py-1 text-[10px] text-[var(--accent)] hover:bg-[var(--accent)]/10"
                to={tabPath}
              >
                {t.pluginsPage.openTab}
              </Link>
            ) : null}

            {row.can_update_git ? (

              <Button
                disabled={busy}
                ghost
                size="sm"
                onClick={() => {
                  void setRuntimeLoading(row.name, async () => {
                    await api.updateAgentPlugin(row.name);
                    showToast(t.pluginsPage.updateGit, "success");
                  });
                }}
              >
                {busy ? <Spinner /> : null}
                {t.pluginsPage.updateGit}
              </Button>
            ) : null}

            {row.has_dashboard_manifest ? (
              <Button
                disabled={busy}
                ghost
                size="sm"
                title={row.user_hidden ? t.pluginsPage.showInSidebar : t.pluginsPage.hideFromSidebar}
                onClick={() => {
                  void setRuntimeLoading(row.name, async () => {
                    await api.setPluginVisibility(row.name, !row.user_hidden);
                  });
                }}
              >
                {row.user_hidden ? (
                  <EyeOff className="h-3.5 w-3.5" />
                ) : (
                  <Eye className="h-3.5 w-3.5" />
                )}
                {row.user_hidden ? t.pluginsPage.showInSidebar : t.pluginsPage.hideFromSidebar}
              </Button>
            ) : null}

            {row.can_remove ? (


              <Button
                destructive
                disabled={busy}
                ghost
                size="sm"
                onClick={() => setConfirmRemove(true)}
              >

                {busy ? <Spinner /> : <Trash2 className="h-3.5 w-3.5" />}
              </Button>
            ) : null}
          </div>
        </div>

        {row.description ? (
          <p className="min-w-0 w-full text-sm text-[var(--fg-dim)] break-words">
            {row.description}
          </p>
        ) : null}

        {dm?.slots?.length ? (

          <p className="text-[0.65rem] text-[var(--fg-faint)]">
            {t.pluginsPage.dashboardSlots}: {dm.slots.join(", ")}
          </p>
        ) : null}

        {row.auth_required ? (
          <CommandBlock
            label={t.pluginsPage.authRequiredHint}
            code={row.auth_command}
          />
        ) : null}

        {!row.has_dashboard_manifest && !dm ? (


          <p className="text-[0.65rem] italic text-[var(--fg-faint)]">
            {t.pluginsPage.noDashboardTab}
          </p>
        ) : null}
      </CardContent>

      <ConfirmDialog
        open={confirmRemove}
        onCancel={() => setConfirmRemove(false)}
        onConfirm={() => {
          setConfirmRemove(false);
          void setRuntimeLoading(row.name, async () => {
            await api.removeAgentPlugin(row.name);
            showToast(`${row.name} removed`, "success");
          });
        }}
        title={t.pluginsPage.removeConfirm}
        description={`This will remove the "${row.name}" plugin from your agent.`}
        destructive
        confirmLabel={t.common.delete}
      />
    </Card>
  );
}
