/**
 * M.U.S.E Universe supporting dashboard panel.
 *
 * This is a health/inspection surface only. It reads the authenticated shared
 * plugin API and deliberately does not implement chat or durable client state.
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;

  const { React } = SDK;
  const h = React.createElement;
  const C = SDK.components || {};
  const { Card, CardContent, Badge, Button } = C;
  const { useCallback, useEffect, useState } = SDK.hooks;
  const fetchJSON = SDK.fetchJSON;
  const STATUS_URL = "/api/plugins/muse-universe/status";

  function metric(label, value) {
    return h(
      "div",
      {
        key: label,
        style: {
          minWidth: "8rem",
          padding: "0.8rem",
          border: "1px solid var(--border)",
          borderRadius: "0.6rem",
        },
      },
      h("div", { style: { opacity: 0.7, fontSize: "0.78rem" } }, label),
      h("div", { style: { fontSize: "1.5rem", fontWeight: 650 } }, String(value))
    );
  }

  function realmRow(realm) {
    return h(
      "div",
      {
        key: realm.id,
        style: {
          display: "flex",
          gap: "0.75rem",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0.65rem 0",
          borderBottom: "1px solid var(--border)",
        },
      },
      h(
        "div",
        null,
        h("div", { style: { fontWeight: 600 } }, realm.name || realm.id),
        h(
          "div",
          { style: { opacity: 0.7, fontSize: "0.78rem" } },
          realm.id + " · cursor " + String(realm.cursor || 0)
        )
      ),
      Badge
        ? h(Badge, { variant: "secondary" }, realm.mode || "local")
        : h("span", null, realm.mode || "local")
    );
  }

  function UniversePage() {
    const [status, setStatus] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const refresh = useCallback(function () {
      setLoading(true);
      fetchJSON(STATUS_URL)
        .then(function (payload) {
          setStatus(payload);
          setError(null);
          setLoading(false);
        })
        .catch(function (reason) {
          setError(String(reason && reason.message ? reason.message : reason));
          setLoading(false);
        });
    }, []);

    useEffect(function () {
      refresh();
    }, [refresh]);

    const content = h(
      "div",
      { style: { display: "grid", gap: "1rem" } },
      h(
        "div",
        {
          style: {
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
            alignItems: "center",
            justifyContent: "space-between",
          },
        },
        h(
          "div",
          null,
          h("h2", { style: { margin: 0 } }, "M.U.S.E Universe"),
          h(
            "p",
            { style: { margin: "0.25rem 0 0", opacity: 0.72 } },
            "Authoritative realms and reconnect health."
          )
        ),
        h(
          "div",
          { style: { display: "flex", gap: "0.5rem" } },
          Button
            ? h(
                Button,
                { variant: "outline", disabled: loading, onClick: refresh },
                loading ? "Refreshing…" : "Refresh"
              )
            : h("button", { disabled: loading, onClick: refresh }, "Refresh"),
          h(
            "a",
            {
              href: "/",
              style: { alignSelf: "center", textDecoration: "underline" },
            },
            "Open Muse Desktop"
          )
        )
      ),
      error
        ? h(
            "div",
            { role: "alert", style: { color: "var(--destructive)" } },
            "Universe status unavailable: " + error
          )
        : null,
      status
        ? h(
            React.Fragment,
            null,
            h(
              "div",
              { style: { display: "flex", flexWrap: "wrap", gap: "0.75rem" } },
              metric("Realms", status.realm_count || 0),
              metric("Events", status.event_count || 0),
              metric("Reconnect cursor", status.cursor || 0)
            ),
            h(
              "div",
              null,
              h("h3", { style: { marginBottom: "0.25rem" } }, "Realms"),
              (status.realms || []).length
                ? status.realms.map(realmRow)
                : h(
                    "p",
                    { style: { opacity: 0.7 } },
                    "No realms have been created on this profile."
                  )
            )
          )
        : null
    );

    return Card
      ? h(Card, null, CardContent ? h(CardContent, null, content) : content)
      : content;
  }

  if (
    window.__HERMES_PLUGINS__ &&
    typeof window.__HERMES_PLUGINS__.register === "function"
  ) {
    window.__HERMES_PLUGINS__.register("muse-universe", UniversePage);
  }
})();
