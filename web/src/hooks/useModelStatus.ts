import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ModelInfoResponse } from "@/lib/api";

const POLL_MS = 8_000;

/**
 * Polls /api/model/info for the currently active model + provider.
 *
 * Used by the SidebarFooter indicator so that model switches made via
 * the CLI, chat slash commands, or the Models page are reflected in
 * the dashboard sidebar within a few seconds.
 *
 * `refresh()` forces an immediate re-fetch (used after the user picks
 * a new model from the sidebar's ModelPickerDialog).
 */
export function useModelStatus() {
  const [info, setInfo] = useState<ModelInfoResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    api
      .getModelInfo()
      .then((d) => {
        setInfo(d);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const refresh = useCallback(() => {
    setLoading(true);
    load();
  }, [load]);

  return { info, loading, refresh };
}
