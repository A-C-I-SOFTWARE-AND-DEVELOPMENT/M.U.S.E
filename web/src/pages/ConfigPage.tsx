import { useCallback, useEffect, useLayoutEffect, useRef, useState, useMemo } from "react";
import {
  ChevronDown,
  ChevronRight,
  Code,
  Download,
  FormInput,
  RotateCcw,
  Save,
  Search,
  Upload,
  X,
  Settings2,
  FileText,
  Settings,
  Bot,
  Monitor,
  Palette,
  Users,
  Brain,
  Package,
  Lock,
  Globe,
  Mic,
  Volume2,
  Ear,
  ClipboardList,
  MessageCircle,
  Wrench,
  FileQuestion,
  Filter,
  Cloud,
  Sparkles,
  LayoutDashboard,
  BookOpen,
  Route,
  History,
  Shield,
  FileOutput,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import { getNestedValue, setNestedValue } from "@/lib/nested";
import { useToast } from "@/hooks/useToast";
import { Toast } from "@/components/Toast";
import { AutoField } from "@/components/AutoField";
import { Button } from "@nous-research/ui/ui/components/button";
import { ListItem } from "@nous-research/ui/ui/components/list-item";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const CATEGORY_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  general: Settings,
  agent: Bot,
  terminal: Monitor,
  display: Palette,
  delegation: Users,
  memory: Brain,
  compression: Package,
  security: Lock,
  browser: Globe,
  voice: Mic,
  tts: Volume2,
  stt: Ear,
  logging: ClipboardList,
  discord: MessageCircle,
  auxiliary: Wrench,
  bedrock: Cloud,
  curator: Sparkles,
  kanban: LayoutDashboard,
  model_catalog: BookOpen,
  openrouter: Route,
  sessions: History,
  tool_loop_guardrails: Shield,
  tool_output: FileOutput,
  updates: RefreshCw,
};

function CategoryIcon({
  category,
  className,
}: {
  category: string;
  className?: string;
}) {
  const Icon = CATEGORY_ICONS[category] ?? FileQuestion;
  return <Icon className={className ?? "h-4 w-4"} />;
}

/** Sentence-case title for a config section (first segment of a dotted key). */
function sectionTitle(section: string): string {
  if (!section) return "General";
  const words = section.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function ConfigPage() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [schema, setSchema] = useState<Record<
    string,
    Record<string, unknown>
  > | null>(null);
  const [categoryOrder, setCategoryOrder] = useState<string[]>([]);
  const [defaults, setDefaults] = useState<Record<string, unknown> | null>(
    null,
  );
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [yamlMode, setYamlMode] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlLoading, setYamlLoading] = useState(false);
  const [yamlSaving, setYamlSaving] = useState(false);
  const [configPath, setConfigPath] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Snapshot of the last saved/loaded config, used for dirty detection.
  const [savedSnapshot, setSavedSnapshot] = useState<string | null>(null);
  // Collapsed state per "category:section" group; default = first group open.
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const { toast, showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { t } = useI18n();
  const { setEnd } = usePageHeader();

  useLayoutEffect(() => {
    if (!config || !schema) {
      setEnd(null);
      return;
    }
    setEnd(
      <div className="flex w-full min-w-0 items-center justify-start gap-2 sm:justify-end">
        <div className="relative w-full min-w-0 sm:max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            className="h-8 pl-8 pr-7 text-xs"
            placeholder={t.common.search}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <Button
              ghost
              size="xs"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setSearchQuery("")}
              aria-label={t.common.clear}
            >
              <X />
            </Button>
          )}
        </div>
        <Button
          size="sm"
          outlined={!yamlMode}
          onClick={() => setYamlMode(!yamlMode)}
          prefix={yamlMode ? <FormInput /> : <Code />}
        >
          {yamlMode ? t.common.form : "YAML"}
        </Button>
      </div>,
    );
    return () => setEnd(null);
  }, [config, schema, searchQuery, yamlMode, setEnd, t.common.clear, t.common.search, t.common.form]);

  function prettyCategoryName(cat: string): string {
    const key = cat as keyof typeof t.config.categories;
    if (t.config.categories[key]) return t.config.categories[key];
    return cat.charAt(0).toUpperCase() + cat.slice(1);
  }

  const loadAll = useCallback(() => {
    setLoadError(null);
    // config + schema are required; defaults/status are best-effort.
    Promise.all([
      api.getConfig(),
      api.getSchema(),
      api.getDefaults().catch(() => null),
      api.getStatus().catch(() => null),
    ])
      .then(([cfg, schemaResp, defaultsResp, statusResp]) => {
        setConfig(cfg);
        setSavedSnapshot(JSON.stringify(cfg));
        setSchema(schemaResp.fields as Record<string, Record<string, unknown>>);
        setCategoryOrder(schemaResp.category_order ?? []);
        if (defaultsResp) setDefaults(defaultsResp);
        if (statusResp) setConfigPath(statusResp.config_path);
      })
      .catch((e) => setLoadError(String(e)));
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Dirty = form state differs from the last saved/loaded snapshot.
  const isDirty = useMemo(() => {
    if (!config || savedSnapshot === null) return false;
    return JSON.stringify(config) !== savedSnapshot;
  }, [config, savedSnapshot]);

  const handleDiscard = () => {
    if (savedSnapshot === null) return;
    setConfig(JSON.parse(savedSnapshot) as Record<string, unknown>);
    showToast("Changes discarded", "success");
  };

  // Set active category when categories load
  useEffect(() => {
    if (categoryOrder.length > 0 && !activeCategory) {
      setActiveCategory(categoryOrder[0]);
    }
  }, [categoryOrder, activeCategory]);

  // Load YAML when switching to YAML mode
  useEffect(() => {
    if (yamlMode) {
      setYamlLoading(true);
      api
        .getConfigRaw()
        .then((resp) => setYamlText(resp.yaml))
        .catch(() => showToast(t.config.failedToLoadRaw, "error"))
        .finally(() => setYamlLoading(false));
    }
  }, [yamlMode]);

  /* ---- Categories ---- */
  const categories = useMemo(() => {
    if (!schema) return [];
    const allCats = [
      ...new Set(
        Object.values(schema).map((s) => String(s.category ?? "general")),
      ),
    ];
    const ordered = categoryOrder.filter((c) => allCats.includes(c));
    const extra = allCats.filter((c) => !categoryOrder.includes(c)).sort();
    return [...ordered, ...extra];
  }, [schema, categoryOrder]);

  /* ---- Category field counts ---- */
  const categoryCounts = useMemo(() => {
    if (!schema) return {};
    const counts: Record<string, number> = {};
    for (const s of Object.values(schema)) {
      const cat = String(s.category ?? "general");
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return counts;
  }, [schema]);

  /* ---- Search ---- */
  const isSearching = searchQuery.trim().length > 0;
  const lowerSearch = searchQuery.toLowerCase();

  const searchMatchedFields = useMemo(() => {
    if (!isSearching || !schema) return [];
    return Object.entries(schema).filter(([key, s]) => {
      const label = key.split(".").pop() ?? key;
      const humanLabel = label.replace(/_/g, " ");
      return (
        key.toLowerCase().includes(lowerSearch) ||
        humanLabel.toLowerCase().includes(lowerSearch) ||
        String(s.category ?? "")
          .toLowerCase()
          .includes(lowerSearch) ||
        String(s.description ?? "")
          .toLowerCase()
          .includes(lowerSearch)
      );
    });
  }, [isSearching, lowerSearch, schema]);

  /* ---- Active tab fields ---- */
  const activeFields = useMemo(() => {
    if (!schema || isSearching) return [];
    return Object.entries(schema).filter(
      ([, s]) => String(s.category ?? "general") === activeCategory,
    );
  }, [schema, activeCategory, isSearching]);

  /* ---- Section groups within the active category (collapsible cards) ---- */
  const sectionGroups = useMemo(() => {
    const groups: {
      section: string;
      fields: [string, Record<string, unknown>][];
    }[] = [];
    const bySection = new Map<string, [string, Record<string, unknown>][]>();
    for (const entry of activeFields) {
      const parts = entry[0].split(".");
      const section = parts.length > 1 ? parts[0] : "";
      if (!bySection.has(section)) bySection.set(section, []);
      bySection.get(section)!.push(entry);
    }
    for (const [section, fields] of bySection) {
      groups.push({ section, fields });
    }
    return groups;
  }, [activeFields]);

  /* ---- Handlers ---- */
  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await api.saveConfig(config);
      setSavedSnapshot(JSON.stringify(config));
      showToast(t.config.configSaved, "success");
    } catch (e) {
      showToast(`${t.config.failedToSave}: ${e}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleYamlSave = async () => {
    setYamlSaving(true);
    try {
      await api.saveConfigRaw(yamlText);
      showToast(t.config.yamlConfigSaved, "success");
      api
        .getConfig()
        .then((cfg) => {
          setConfig(cfg);
          setSavedSnapshot(JSON.stringify(cfg));
        })
        .catch(() => {});
    } catch (e) {
      showToast(`${t.config.failedToSaveYaml}: ${e}`, "error");
    } finally {
      setYamlSaving(false);
    }
  };

  const handleReset = () => {
    if (!defaults || !config) return;
    // Scope the reset to what the user is currently looking at:
    //   - search mode → the matched fields
    //   - form mode   → the active category's fields
    // Resetting the whole config here was a footgun (issue reported by @ykmfb001):
    // the button sits next to the category tabs and users reasonably assumed
    // "reset this tab", not "wipe my entire config.yaml".
    const scopedFields = isSearching ? searchMatchedFields : activeFields;
    if (scopedFields.length === 0) return;
    setConfirmReset(true);
  };

  const executeReset = () => {
    if (!defaults || !config) return;
    setConfirmReset(false);
    const scopedFields = isSearching ? searchMatchedFields : activeFields;
    if (scopedFields.length === 0) return;
    const scopeLabel = isSearching
      ? t.config.searchResults
      : prettyCategoryName(activeCategory);
    let next: Record<string, unknown> = config;
    for (const [key] of scopedFields) {
      next = setNestedValue(next, key, getNestedValue(defaults, key));
    }
    setConfig(next);
    showToast(
      t.config.resetScopeToast.replace("{scope}", scopeLabel),
      "success",
    );
  };

  const handleExport = () => {
    if (!config) return;
    const blob = new Blob([JSON.stringify(config, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "muse-config.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const imported = JSON.parse(reader.result as string);
        setConfig(imported);
        showToast(t.config.configImported, "success");
      } catch {
        showToast(t.config.invalidJson, "error");
      }
    };
    reader.readAsText(file);
  };

  /* ---- Loading: skeleton rows / error banner ---- */
  if (!config || !schema) {
    if (loadError) {
      return (
        <div className="flex flex-col gap-4">
          <div
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--err)]/40 px-4 py-3"
            style={{
              backgroundColor:
                "color-mix(in srgb, var(--err) 8%, var(--bg-elev))",
            }}
            role="alert"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-[var(--err)]">
                Failed to load configuration
              </p>
              <p className="mt-0.5 break-words text-xs text-[var(--fg-dim)]">
                {loadError}
              </p>
            </div>
            <Button size="sm" outlined onClick={loadAll} prefix={<RefreshCw />}>
              {t.common.retry}
            </Button>
          </div>
        </div>
      );
    }
    return (
      <div className="flex flex-col gap-4" aria-busy="true">
        <div className="h-8 w-72 animate-pulse rounded bg-[var(--bg-mute)]" />
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="rounded-xl border border-[var(--border)] p-4"
            style={{ backgroundColor: "var(--bg-elev)" }}
          >
            <div className="h-4 w-44 animate-pulse rounded bg-[var(--bg-mute)]" />
            <div className="mt-4 grid gap-3">
              <div className="h-3 w-full animate-pulse rounded bg-[var(--bg-mute)]/70" />
              <div className="h-3 w-3/4 animate-pulse rounded bg-[var(--bg-mute)]/70" />
              <div className="h-3 w-5/6 animate-pulse rounded bg-[var(--bg-mute)]/70" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  /* ---- Search results (flat list with category badges) ---- */
  const renderSearchFields = (
    fields: [string, Record<string, unknown>][],
  ) => {
    let lastCat = "";
    return fields.map(([key, s]) => {
      const cat = String(s.category ?? "general");
      const showCatBadge = cat !== lastCat;
      lastCat = cat;

      return (
        <div key={key}>
          {showCatBadge && (
            <div className="flex items-center gap-2 pt-4 pb-2 first:pt-0">
              <CategoryIcon
                category={cat}
                className="h-4 w-4 text-[var(--fg-faint)]"
              />
              <span className="text-xs font-semibold text-[var(--fg-dim)]">
                {prettyCategoryName(cat)}
              </span>
              <div className="flex-1 border-t border-[var(--border)]" />
            </div>
          )}
          <div className="py-1">
            <AutoField
              schemaKey={key}
              schema={s}
              value={getNestedValue(config, key)}
              onChange={(v) => setConfig(setNestedValue(config, key, v))}
            />
          </div>
        </div>
      );
    });
  };

  /* ---- Collapsible section cards for the active category ---- */
  const renderSectionCards = () => (
    <div className="grid gap-3">
      {sectionGroups.map((g, gi) => {
        const collapseKey = `${activeCategory}:${g.section}`;
        // Default-open the first group of each category.
        const isCollapsed = collapsed[collapseKey] ?? gi !== 0;
        return (
          <section
            key={g.section || "general"}
            className="rounded-xl border border-[var(--border)]"
            style={{ backgroundColor: "var(--bg-elev)" }}
          >
            <button
              type="button"
              onClick={() =>
                setCollapsed((prev) => ({
                  ...prev,
                  [collapseKey]: !isCollapsed,
                }))
              }
              aria-expanded={!isCollapsed}
              className="flex w-full items-center gap-2 px-4 py-3 text-left"
            >
              {isCollapsed ? (
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--fg-faint)]" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--fg-dim)]" />
              )}
              <span className="text-sm font-medium">
                {sectionTitle(g.section)}
              </span>
              <span className="text-[10px] tabular-nums text-[var(--fg-faint)]">
                {g.fields.length}{" "}
                {t.config.fields.replace(
                  "{s}",
                  g.fields.length !== 1 ? "s" : "",
                )}
              </span>
            </button>
            {!isCollapsed && (
              <div className="grid gap-2 border-t border-[var(--border)] px-4 pb-4 pt-2">
                {g.fields.map(([key, s]) => (
                  <div className="py-1" key={key}>
                    <AutoField
                      schemaKey={key}
                      schema={s}
                      value={getNestedValue(config, key)}
                      onChange={(v) =>
                        setConfig(setNestedValue(config, key, v))
                      }
                    />
                  </div>
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <PluginSlot name="config:top" />
      <Toast toast={toast} />

      <p className="text-sm text-[var(--fg-dim)]">
        Schema-driven settings grouped by section — nothing is written to your
        config file until you save.
      </p>

      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="flex min-w-0 items-center gap-2 sm:flex-1">
          <Settings2 className="h-4 w-4 shrink-0 text-muted-foreground" />
          <code className="min-w-0 flex-1 break-words text-xs text-muted-foreground bg-muted/50 px-2 py-0.5">
            {configPath ?? t.config.configPath}
          </code>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 sm:shrink-0">
          <Button
            ghost
            size="icon"
            onClick={handleExport}
            title={t.config.exportConfig}
            aria-label={t.config.exportConfig}
          >
            <Download />
          </Button>
          <Button
            ghost
            size="icon"
            onClick={() => fileInputRef.current?.click()}
            title={t.config.importConfig}
            aria-label={t.config.importConfig}
          >
            <Upload />
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleImport}
          />
          {!yamlMode &&
            (() => {
              const resetScopeLabel = isSearching
                ? t.config.searchResults
                : prettyCategoryName(activeCategory);
              const resetTitle = t.config.resetScopeTooltip.replace(
                "{scope}",
                resetScopeLabel,
              );
              return (
                <Button
                  ghost
                  size="icon"
                  onClick={handleReset}
                  title={resetTitle}
                  aria-label={resetTitle}
                >
                  <RotateCcw />
                </Button>
              );
            })()}

          {yamlMode && (
            <>
              <div className="w-px h-5 bg-border mx-1" />
              <Button
                size="sm"
                onClick={handleYamlSave}
                disabled={yamlSaving}
                prefix={<Save />}
              >
                {yamlSaving ? t.common.saving : t.common.save}
              </Button>
            </>
          )}
        </div>
      </div>

      {yamlMode ? (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="h-4 w-4" />
              {t.config.rawYaml}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {yamlLoading ? (
              <div className="flex items-center justify-center py-12">
                <Spinner className="text-xl text-primary" />
              </div>
            ) : (
              <textarea
                className="flex min-h-[600px] w-full bg-transparent px-4 py-3 text-sm font-mono leading-relaxed placeholder:text-muted-foreground focus-visible:outline-none border-t border-border"
                value={yamlText}
                onChange={(e) => setYamlText(e.target.value)}
                spellCheck={false}
              />
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col sm:flex-row gap-4">
          <aside aria-label={t.config.filters} className="sm:w-56 sm:shrink-0">
            <div className="sm:sticky sm:top-4">
              <div className="flex flex-col border border-[var(--border)] rounded-xl" style={{ backgroundColor: "var(--bg-elev)" }}>
                <div className="hidden sm:flex items-center gap-2 px-3 py-2 border-b border-[var(--border)]">
                  <Filter className="h-3 w-3 text-[var(--fg-faint)]" />
                  <span className="text-[0.65rem] font-medium text-[var(--fg-dim)]">
                    {t.config.filters}
                  </span>
                </div>

                <div className="hidden sm:block px-3 pt-2 pb-1 text-[0.6rem] text-[var(--fg-faint)]">
                  {t.config.sections}
                </div>

                <div className="flex sm:flex-col gap-1 sm:gap-px p-2 sm:pt-1 overflow-x-auto sm:overflow-x-visible scrollbar-none sm:max-h-[calc(100vh-260px)] sm:overflow-y-auto">
                  {categories.map((cat) => {
                    const isActive = !isSearching && activeCategory === cat;

                    return (
                      <ListItem
                        key={cat}
                        active={isActive}
                        onClick={() => {
                          setSearchQuery("");
                          setActiveCategory(cat);
                        }}
                        className="rounded-sm whitespace-nowrap px-2 py-1 text-[11px]"
                      >
                        <CategoryIcon
                          category={cat}
                          className="h-3.5 w-3.5 shrink-0"
                        />
                        <span className="flex-1 truncate">
                          {prettyCategoryName(cat)}
                        </span>
                        <span
                          className={`text-[10px] tabular-nums ${
                            isActive
                              ? "text-foreground/60"
                              : "text-muted-foreground/50"
                          }`}
                        >
                          {categoryCounts[cat] || 0}
                        </span>
                      </ListItem>
                    );
                  })}
                </div>
              </div>
            </div>
          </aside>

          <div className="flex-1 min-w-0">
            {isSearching ? (
              <section
                className="rounded-xl border border-[var(--border)]"
                style={{ backgroundColor: "var(--bg-elev)" }}
              >
                <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
                  <span className="flex items-center gap-2 text-sm font-medium">
                    <Search className="h-4 w-4 text-[var(--fg-dim)]" />
                    {t.config.searchResults}
                  </span>
                  <span className="text-[10px] tabular-nums text-[var(--fg-faint)]">
                    {searchMatchedFields.length}{" "}
                    {t.config.fields.replace(
                      "{s}",
                      searchMatchedFields.length !== 1 ? "s" : "",
                    )}
                  </span>
                </div>
                <div className="grid gap-2 px-4 py-3">
                  {searchMatchedFields.length === 0 ? (
                    <p className="py-8 text-center text-sm text-[var(--fg-dim)]">
                      {t.config.noFieldsMatch.replace("{query}", searchQuery)}
                    </p>
                  ) : (
                    renderSearchFields(searchMatchedFields)
                  )}
                </div>
              </section>
            ) : (
              /* Active category → collapsible section cards */
              renderSectionCards()
            )}
          </div>
        </div>
      )}
      <PluginSlot name="config:bottom" />

      {/* Sticky save bar — visible only while the form has unsaved edits */}
      {isDirty && !yamlMode && (
        <div className="sticky bottom-3 z-20">
          <div
            className="flex items-center gap-3 rounded-xl border border-[var(--border)] px-4 py-2.5 shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
            style={{ backgroundColor: "var(--bg-elev)" }}
          >
            <span
              className="h-2 w-2 shrink-0 rounded-full bg-[var(--accent)]"
              aria-hidden="true"
            />
            <span className="text-xs text-[var(--fg-dim)]">
              Unsaved changes
            </span>
            <div className="flex-1" />
            <Button
              size="sm"
              outlined
              onClick={handleDiscard}
              prefix={<RotateCcw />}
              title="Revert to the last saved config"
            >
              Reset
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving}
              prefix={<Save />}
              className="bg-[var(--accent)] text-[var(--bg)] shadow-none hover:bg-[var(--accent)]/90"
            >
              {saving ? t.common.saving : t.common.save}
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmReset}
        onCancel={() => setConfirmReset(false)}
        onConfirm={executeReset}
        title={t.config.confirmResetScope.replace(
          "{scope}",
          isSearching
            ? t.config.searchResults
            : prettyCategoryName(activeCategory),
        )}
        description={`This will reset ${
          (isSearching ? searchMatchedFields : activeFields).length
        } field(s) to their default values.`}
        destructive
        confirmLabel={t.config.resetDefaults}
      />
    </div>
  );
}
