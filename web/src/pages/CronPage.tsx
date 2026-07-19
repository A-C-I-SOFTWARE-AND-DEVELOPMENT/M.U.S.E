import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import {
  AlertCircle,
  Clock,
  Plus,
  RefreshCw,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Select, SelectOption } from "@nous-research/ui/ui/components/select";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Switch } from "@nous-research/ui/ui/components/switch";
import { api } from "@/lib/api";
import type { CronJob, ProfileInfo } from "@/lib/api";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { useToast } from "@/hooks/useToast";
import { useConfirmDelete } from "@/hooks/useConfirmDelete";
import { useModalBehavior } from "@/hooks/useModalBehavior";
import { Toast } from "@/components/Toast";
import { EmptyStateCard } from "@/components/EmptyStateCard";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function truncateText(value: string, maxLength: number): string {
  return value.length > maxLength
    ? value.slice(0, maxLength) + "..."
    : value;
}

function getJobPrompt(job: CronJob): string {
  return asText(job.prompt);
}

function getJobName(job: CronJob): string {
  return asText(job.name).trim();
}

function getJobTitle(job: CronJob): string {
  const name = getJobName(job);
  if (name) return name;

  const prompt = getJobPrompt(job);
  if (prompt) return truncateText(prompt, 60);

  const script = asText(job.script);
  if (script) return truncateText(script, 60);

  return job.id || "Cron job";
}

function getJobScheduleDisplay(job: CronJob): string {
  return (
    asText(job.schedule_display) ||
    asText(job.schedule?.display) ||
    asText(job.schedule?.expr) ||
    "—"
  );
}

function getJobState(job: CronJob): string {
  return asText(job.state) || (job.enabled === false ? "disabled" : "scheduled");
}

function getJobProfile(job: CronJob): string {
  return asText(job.profile) || asText(job.profile_name) || "default";
}

function getJobKey(job: CronJob): string {
  return `${getJobProfile(job)}:${job.id}`;
}

function splitJobKey(key: string): { profile: string; id: string } {
  const idx = key.indexOf(":");
  if (idx === -1) return { profile: "default", id: key };
  return { profile: key.slice(0, idx) || "default", id: key.slice(idx + 1) };
}

function profileLabel(profile: string): string {
  return profile === "default" ? "default" : profile;
}

/** Last-run status chip routed through Singularity semantic tokens. */
function LastStatusChip({ job }: { job: CronJob }) {
  if (job.last_error) {
    return (
      <span
        className="rounded-full border border-[var(--err)]/40 bg-[var(--err)]/10 px-2 py-0.5 text-[0.65rem] text-[var(--err)]"
        title={job.last_error}
      >
        error
      </span>
    );
  }
  const state = getJobState(job);
  if (state === "paused") {
    return (
      <span className="rounded-full border border-[var(--warn)]/40 bg-[var(--warn)]/10 px-2 py-0.5 text-[0.65rem] text-[var(--warn)]">
        paused
      </span>
    );
  }
  if (state === "disabled") {
    return (
      <span className="rounded-full border border-[var(--border)] bg-[var(--bg-mute)] px-2 py-0.5 text-[0.65rem] text-[var(--fg-faint)]">
        disabled
      </span>
    );
  }
  if (job.last_run_at) {
    return (
      <span className="rounded-full border border-[var(--ok)]/40 bg-[var(--ok)]/10 px-2 py-0.5 text-[0.65rem] text-[var(--ok)]">
        ok
      </span>
    );
  }
  return (
    <span className="rounded-full border border-[var(--border)] bg-[var(--bg-mute)] px-2 py-0.5 text-[0.65rem] text-[var(--fg-faint)]">
      scheduled
    </span>
  );
}

export default function CronPage() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [profiles, setProfiles] = useState<ProfileInfo[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("all");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { toast, showToast } = useToast();
  const { t } = useI18n();
  const { setTitle, setAfterTitle, setEnd } = usePageHeader();

  // New job modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [schedule, setSchedule] = useState("");
  const [name, setName] = useState("");
  const closeCreateModal = useCallback(() => setCreateModalOpen(false), []);
  const createModalRef = useModalBehavior({
    open: createModalOpen,
    onClose: closeCreateModal,
  });
  const [deliver, setDeliver] = useState("local");
  const [creating, setCreating] = useState(false);
  const createProfile = selectedProfile === "all" ? "default" : selectedProfile;

  const loadJobs = useCallback(() => {
    setLoadError(null);
    api
      .getCronJobs(selectedProfile)
      .then(setJobs)
      .catch((e) => {
        setLoadError(e instanceof Error ? e.message : t.common.loading);
        showToast(t.common.loading, "error");
      })
      .finally(() => setLoading(false));
  }, [selectedProfile, showToast, t.common.loading]);

  useEffect(() => {
    api
      .getProfiles()
      .then((res) => setProfiles(res.profiles))
      .catch(() => setProfiles([]));
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const handleCreate = async () => {
    if (!prompt.trim() || !schedule.trim()) {
      showToast(`${t.cron.prompt} & ${t.cron.schedule} required`, "error");
      return;
    }
    setCreating(true);
    try {
      await api.createCronJob(
        {
          prompt: prompt.trim(),
          schedule: schedule.trim(),
          name: name.trim() || undefined,
          deliver,
        },
        createProfile,
      );
      showToast(t.common.create + " ✓", "success");
      setPrompt("");
      setSchedule("");
      setName("");
      setDeliver("local");
      setCreateModalOpen(false);
      loadJobs();
    } catch (e) {
      showToast(`${t.config.failedToSave}: ${e}`, "error");
    } finally {
      setCreating(false);
    }
  };

  const handleSetEnabled = async (job: CronJob, enabled: boolean) => {
    const profile = getJobProfile(job);
    const patch = (j: CronJob, on: boolean): CronJob => ({
      ...j,
      enabled: on,
      // getJobState() prefers `state` over `enabled` — keep both in sync.
      state: on ? "scheduled" : "paused",
    });
    // Optimistic switch flip; revert on failure.
    setJobs((prev) =>
      prev.map((j) => (getJobKey(j) === getJobKey(job) ? patch(j, enabled) : j)),
    );
    try {
      if (enabled) {
        await api.resumeCronJob(job.id, profile);
      } else {
        await api.pauseCronJob(job.id, profile);
      }
      showToast(
        `${enabled ? t.cron.resume : t.cron.pause}: "${truncateText(getJobTitle(job), 30)}"`,
        "success",
      );
      loadJobs();
    } catch (e) {
      setJobs((prev) =>
        prev.map((j) =>
          getJobKey(j) === getJobKey(job) ? patch(j, !enabled) : j,
        ),
      );
      showToast(`${t.status.error}: ${e}`, "error");
    }
  };

  const handleTrigger = async (job: CronJob) => {
    try {
      await api.triggerCronJob(job.id, getJobProfile(job));
      showToast(
        `${t.cron.triggerNow}: "${truncateText(getJobTitle(job), 30)}"`,
        "success",
      );
      loadJobs();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    }
  };

  const jobDelete = useConfirmDelete({
    onDelete: useCallback(
      async (key: string) => {
        const { profile, id } = splitJobKey(key);
        const job = jobs.find((j) => getJobKey(j) === key);
        try {
          await api.deleteCronJob(id, profile);
          showToast(
            `${t.common.delete}: "${job ? truncateText(getJobTitle(job), 30) : id}"`,
            "success",
          );
          loadJobs();
        } catch (e) {
          showToast(`${t.status.error}: ${e}`, "error");
          throw e;
        }
      },
      [jobs, loadJobs, showToast, t.common.delete, t.status.error],
    ),
  });

  // Sentence-case header + description + primary action (design 2.3).
  useLayoutEffect(() => {
    setTitle("Cron jobs");
    setAfterTitle(
      <span className="whitespace-nowrap text-xs text-[var(--fg-faint)]">
        Scheduled prompts that run automatically across profiles.
      </span>,
    );
    setEnd(
      <Button size="sm" onClick={() => setCreateModalOpen(true)}>
        <Plus className="h-3 w-3" />
        {t.common.create}
      </Button>,
    );
    return () => {
      setTitle(null);
      setAfterTitle(null);
      setEnd(null);
    };
  }, [setTitle, setAfterTitle, setEnd, t.common.create]);

  const pendingJob = jobDelete.pendingId
    ? jobs.find((j) => getJobKey(j) === jobDelete.pendingId)
    : null;

  return (
    <div className="flex flex-col gap-6">
      <PluginSlot name="cron:top" />
      <Toast toast={toast} />

      <DeleteConfirmDialog
        open={jobDelete.isOpen}
        onCancel={jobDelete.cancel}
        onConfirm={jobDelete.confirm}
        title={t.cron.confirmDeleteTitle}
        description={
          pendingJob
            ? `"${truncateText(getJobTitle(pendingJob), 40)}" — ${
                t.cron.confirmDeleteMessage
              }`
            : t.cron.confirmDeleteMessage
        }
        loading={jobDelete.isDeleting}
      />

      {/* Create job modal */}
      {createModalOpen && (
        <div
          ref={createModalRef}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-background/85 backdrop-blur-sm p-4"
          onClick={(e) => e.target === e.currentTarget && setCreateModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-cron-title"
        >
          <div className="relative flex w-full max-w-lg flex-col rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] shadow-2xl">
            <Button
              ghost
              size="icon"
              onClick={() => setCreateModalOpen(false)}
              className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X />
            </Button>

            <header className="border-b border-[var(--border)] p-5 pb-3">
              <h2
                id="create-cron-title"
                className="font-display text-base tracking-wider"
              >
                {t.cron.newJob}
              </h2>
            </header>

            <div className="grid gap-4 p-5">
              <div className="grid gap-2">
                <Label htmlFor="cron-profile">Profile</Label>
                <Select
                  id="cron-profile"
                  value={createProfile}
                  onValueChange={(v) => setSelectedProfile(v)}
                >
                  {profiles.map((profile) => (
                    <SelectOption key={profile.name} value={profile.name}>
                      {profileLabel(profile.name)}
                    </SelectOption>
                  ))}
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="cron-name">{t.cron.nameOptional}</Label>
                <Input
                  id="cron-name"
                  autoFocus
                  placeholder={t.cron.namePlaceholder}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="cron-prompt">{t.cron.prompt}</Label>
                <textarea
                  id="cron-prompt"
                  className="flex min-h-[80px] w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-sm text-[var(--fg)] shadow-sm placeholder:text-[var(--fg-faint)] focus-visible:border-[var(--accent-dim)] focus-visible:outline-none"
                  placeholder={t.cron.promptPlaceholder}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="cron-schedule">{t.cron.schedule}</Label>
                  <Input
                    id="cron-schedule"
                    placeholder={t.cron.schedulePlaceholder}
                    value={schedule}
                    onChange={(e) => setSchedule(e.target.value)}
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="cron-deliver">{t.cron.deliverTo}</Label>
                  <Select
                    id="cron-deliver"
                    value={deliver}
                    onValueChange={(v) => setDeliver(v)}
                  >
                    <SelectOption value="local">
                      {t.cron.delivery.local}
                    </SelectOption>
                    <SelectOption value="telegram">
                      {t.cron.delivery.telegram}
                    </SelectOption>
                    <SelectOption value="discord">
                      {t.cron.delivery.discord}
                    </SelectOption>
                    <SelectOption value="slack">
                      {t.cron.delivery.slack}
                    </SelectOption>
                    <SelectOption value="email">
                      {t.cron.delivery.email}
                    </SelectOption>
                  </Select>
                </div>
              </div>

              <div className="flex justify-end">
                <Button
                  size="sm"
                  onClick={handleCreate}
                  disabled={creating}
                  prefix={creating ? <Spinner /> : <Plus />}
                >
                  {creating ? t.common.creating : t.common.create}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h2 className="flex items-center gap-2 text-sm font-medium text-[var(--fg-dim)]">
            <Clock className="h-4 w-4" />
            {t.cron.scheduledJobs} ({jobs.length})
          </h2>

          <div className="grid min-w-[220px] gap-1">
            <Label htmlFor="cron-profile-filter">Profile</Label>
            <Select
              id="cron-profile-filter"
              value={selectedProfile}
              onValueChange={(v) => setSelectedProfile(v)}
            >
              <SelectOption value="all">All profiles</SelectOption>
              {profiles.map((profile) => (
                <SelectOption key={profile.name} value={profile.name}>
                  {profileLabel(profile.name)}
                </SelectOption>
              ))}
            </Select>
          </div>
        </div>

        {/* Inline error banner with retry (design 2.3) */}
        {loadError && (
          <div className="flex items-center gap-2 rounded-xl border border-[var(--err)]/30 bg-[var(--err)]/5 px-3 py-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-[var(--err)]" />
            <span className="flex-1 text-xs text-[var(--err)]">{loadError}</span>
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                loadJobs();
              }}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--err)]/40 px-2 py-0.5 text-xs text-[var(--err)] transition-colors hover:bg-[var(--err)]/10"
            >
              <RefreshCw className="h-3 w-3" />
              {t.common.retry}
            </button>
          </div>
        )}

        {/* Skeleton rows while loading (design 2.3 — no spinner storms) */}
        {loading &&
          Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="flex animate-pulse items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] px-4 py-4"
            >
              <div className="h-5 w-9 rounded-full bg-[var(--bg-mute)]" />
              <div className="flex-1">
                <div className="mb-2 h-3.5 w-48 rounded bg-[var(--bg-mute)]" />
                <div className="h-3 w-72 rounded bg-[var(--bg-mute)]" />
              </div>
              <div className="h-6 w-16 rounded-full bg-[var(--bg-mute)]" />
            </div>
          ))}

        {!loading && jobs.length === 0 && !loadError && (
          <EmptyStateCard
            icon={Clock}
            title={t.cron.noJobs}
            action={
              <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                <Plus className="h-3 w-3" />
                {t.common.create}
              </Button>
            }
          />
        )}

        {!loading &&
          jobs.map((job) => {
            const state = getJobState(job);
            const promptText = getJobPrompt(job);
            const title = getJobTitle(job);
            const hasName = Boolean(getJobName(job));
            const deliver = asText(job.deliver);
            const profile = getJobProfile(job);
            const jobKey = getJobKey(job);
            const enabled = state !== "paused" && state !== "disabled";

            return (
              <div
                key={jobKey}
                className="flex items-start gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] px-4 py-4 transition-colors hover:border-[var(--accent-dim)]"
              >
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium text-[var(--fg)]">
                      {title}
                    </span>
                    <LastStatusChip job={job} />
                    <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[0.65rem] text-[var(--fg-faint)]">
                      {profileLabel(profile)}
                    </span>
                    {deliver && deliver !== "local" && (
                      <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[0.65rem] text-[var(--fg-faint)]">
                        {deliver}
                      </span>
                    )}
                  </div>
                  {hasName && promptText && (
                    <p className="mb-1 truncate text-xs text-[var(--fg-dim)]">
                      {truncateText(promptText, 100)}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                    <span className="font-mono text-[var(--fg-dim)]">
                      {getJobScheduleDisplay(job)}
                    </span>
                    <span className="text-[var(--fg-faint)]">
                      {t.cron.last}: {formatTime(job.last_run_at)}
                    </span>
                    <span className="text-[var(--fg-faint)]">
                      {t.cron.next}: {formatTime(job.next_run_at)}
                    </span>
                  </div>
                  {job.last_error && (
                    <p className="mt-1 text-xs text-[var(--err)]">
                      {job.last_error}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  {/* Enabled switch — pause/resume via existing endpoints */}
                  <Switch
                    checked={enabled}
                    onCheckedChange={(v) => handleSetEnabled(job, v)}
                    aria-label={
                      enabled ? t.cron.pause : t.cron.resume
                    }
                  />
                  <Button
                    ghost
                    size="icon"
                    title={t.cron.triggerNow}
                    aria-label={t.cron.triggerNow}
                    onClick={() => handleTrigger(job)}
                  >
                    <Zap />
                  </Button>
                  <Button
                    ghost
                    destructive
                    size="icon"
                    title={t.common.delete}
                    aria-label={t.common.delete}
                    onClick={() => jobDelete.requestDelete(jobKey)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </div>
            );
          })}
      </div>

      <PluginSlot name="cron:bottom" />
    </div>
  );
}
