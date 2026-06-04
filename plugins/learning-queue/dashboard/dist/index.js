/**
 * Hermes Learning Queue — Dashboard Plugin
 *
 * Owner review surface for the JARVIS learning dataset. Calls the plugin's
 * backend at /api/plugins/learning-queue/ which wraps the same DatasetStore
 * the `jarvis_prime learning` CLI and the cockpit use, so all surfaces stay
 * in sync.
 *
 * Plain IIFE, no build step. Uses window.__HERMES_PLUGIN_SDK__ for React +
 * shadcn primitives and SDK.fetchJSON for authenticated calls (mirrors the
 * bundled kanban plugin).
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;

  const { React } = SDK;
  const h = React.createElement;
  const C = SDK.components || {};
  const { Card, CardContent, Badge, Button, Select, SelectOption } = C;
  const { useState, useEffect, useCallback } = SDK.hooks;
  const fetchJSON = SDK.fetchJSON;

  const API = "/api/plugins/learning-queue";

  // The exact owner-authorization phrase the backend requires for approve.
  // Kept in sync with hermes_cli.jarvis_prime.owner_auth.AUTHORIZATION_PHRASE.
  const OWNER_PHRASE = "Yes, with authorization.";

  const STATUSES = ["", "pending", "approved", "rejected"];

  function gateBadges(quality) {
    const gates = [
      ["tests", quality.tests_passed],
      ["citations", quality.citations_verified],
      ["owner", quality.owner_approved],
      ["reviewer", quality.reviewer_passed],
      ["rollback", quality.rollback_available],
    ];
    return h(
      "span",
      { className: "hermes-lq-gates" },
      gates
        .filter(function (g) { return g[1]; })
        .map(function (g) {
          return Badge
            ? h(Badge, { key: g[0], variant: "secondary", className: "hermes-lq-gate" }, g[0])
            : h("span", { key: g[0], className: "hermes-lq-gate" }, g[0]);
        })
    );
  }

  function statusBadge(status) {
    const cls = "hermes-lq-status hermes-lq-status--" + status;
    return Badge
      ? h(Badge, { className: cls }, status)
      : h("span", { className: cls }, status);
  }

  function CandidateRow(props) {
    const c = props.candidate;
    const prov = c.provenance || {};
    const onDecide = props.onDecide;
    const busy = props.busy;
    return h(
      "div",
      { className: "hermes-lq-row" },
      h(
        "div",
        { className: "hermes-lq-row-main" },
        h("div", { className: "hermes-lq-row-head" },
          statusBadge(c.status),
          h("span", { className: "hermes-lq-trace" }, c.trace_type),
          (c.labels || []).map(function (l) {
            return h("span", { key: l, className: "hermes-lq-label" }, l);
          })
        ),
        h("div", { className: "hermes-lq-prov" },
          h("span", { className: "hermes-lq-prov-kind" }, prov.source_kind || "?"),
          prov.source_uri
            ? h("a", { href: prov.source_uri, target: "_blank", rel: "noreferrer", className: "hermes-lq-prov-uri" }, prov.source_uri)
            : null,
          (prov.citations || []).length
            ? h("span", { className: "hermes-lq-cites" }, (prov.citations.length) + " citation(s)")
            : null
        ),
        gateBadges(c.quality || {}),
        h("div", { className: "hermes-lq-id" }, c.id)
      ),
      c.status === "pending"
        ? h(
            "div",
            { className: "hermes-lq-actions" },
            h(Button, {
              size: "sm",
              disabled: busy,
              onClick: function () { onDecide(c.id, "approve"); },
            }, "Approve"),
            h(Button, {
              size: "sm",
              variant: "outline",
              disabled: busy,
              onClick: function () { onDecide(c.id, "reject"); },
            }, "Reject")
          )
        : null
    );
  }

  function LearningPage() {
    const [items, setItems] = useState([]);
    const [stats, setStats] = useState(null);
    const [status, setStatus] = useState("pending");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);

    const load = useCallback(function () {
      const qs = status ? "?status=" + encodeURIComponent(status) : "";
      Promise.all([
        fetchJSON(API + "/queue" + qs),
        fetchJSON(API + "/stats"),
      ]).then(function (res) {
        setItems((res[0] && res[0].learning) || []);
        setStats(res[1] || null);
        setError(null);
      }).catch(function (e) {
        setError(String(e && e.message ? e.message : e));
      });
    }, [status]);

    useEffect(function () { load(); }, [load]);

    const decide = useCallback(function (id, decision) {
      const body = { decision: decision };
      if (decision === "approve") {
        // Owner gate: confirm the exact authorization phrase before promoting
        // a candidate into training data. The backend re-checks it.
        const entered = window.prompt(
          "Approving promotes this trace into the learning dataset.\n" +
          "Type the owner authorization phrase to confirm:",
          ""
        );
        if (entered == null) return;
        if (entered.trim() !== OWNER_PHRASE) {
          setError("Approval cancelled: phrase must be exactly " + JSON.stringify(OWNER_PHRASE));
          return;
        }
        body.authorization = entered.trim();
      }
      setBusy(true);
      fetchJSON(API + "/candidate/" + encodeURIComponent(id) + "/decide", {
        method: "POST",
        body: JSON.stringify(body),
      }).then(function () {
        setBusy(false);
        load();
      }).catch(function (e) {
        setBusy(false);
        setError(String(e && e.message ? e.message : e));
      });
    }, [load]);

    const exportApproved = useCallback(function (format) {
      const out = window.prompt(
        "Output file path for the " + format + " export:",
        format === "parquet" ? "learning_dataset.parquet" : "learning_dataset.jsonl"
      );
      if (!out) return;
      setBusy(true);
      fetchJSON(API + "/export", {
        method: "POST",
        body: JSON.stringify({ format: format, out: out }),
      }).then(function (r) {
        setBusy(false);
        window.alert("Exported " + (r && r.exported) + " record(s) to " + out);
      }).catch(function (e) {
        setBusy(false);
        setError(String(e && e.message ? e.message : e));
      });
    }, []);

    const header = h(
      "div",
      { className: "hermes-lq-header" },
      h("h2", null, "Learning Queue"),
      stats
        ? h("div", { className: "hermes-lq-stats" },
            h("span", null, "total: " + stats.total),
            h("span", null, "exportable: " + stats.exportable),
            Object.keys(stats.by_status || {}).map(function (k) {
              return h("span", { key: k }, k + ": " + stats.by_status[k]);
            })
          )
        : null,
      h(
        "div",
        { className: "hermes-lq-controls" },
        Select
          ? h(
              Select,
              { value: status, onValueChange: setStatus },
              STATUSES.map(function (s) {
                return h(SelectOption, { key: s || "all", value: s }, s || "all");
              })
            )
          : h(
              "select",
              {
                value: status,
                onChange: function (e) { setStatus(e.target.value); },
              },
              STATUSES.map(function (s) {
                return h("option", { key: s || "all", value: s }, s || "all");
              })
            ),
        h(Button, { size: "sm", variant: "outline", disabled: busy, onClick: load }, "Refresh"),
        h(Button, { size: "sm", variant: "outline", disabled: busy, onClick: function () { exportApproved("jsonl"); } }, "Export JSONL"),
        h(Button, { size: "sm", variant: "outline", disabled: busy, onClick: function () { exportApproved("parquet"); } }, "Export Parquet")
      )
    );

    const body = error
      ? h("div", { className: "hermes-lq-error" }, "Error: " + error)
      : items.length === 0
        ? h("div", { className: "hermes-lq-empty" }, "No candidates" + (status ? " (" + status + ")" : "") + ".")
        : items.map(function (c) {
            return h(CandidateRow, { key: c.id, candidate: c, onDecide: decide, busy: busy });
          });

    const inner = h("div", { className: "hermes-lq" }, header, h("div", { className: "hermes-lq-list" }, body));
    return Card
      ? h(Card, { className: "hermes-lq-card" }, CardContent ? h(CardContent, null, inner) : inner)
      : inner;
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("learning-queue", LearningPage);
  }
})();
