/**
 * Feature route registration for the DESK client surfaces.
 *
 * This module is imported once for its side effect (from main.tsx) and PUSHES
 * the desktop client's feature routes onto the append-only registry
 * (src/routes.ts). Per the registry contract, a feature grain registers from
 * its OWN module rather than editing a shared switch/dispatcher — so this file,
 * not routes.register.ts, owns these registrations and there is no conflict with
 * the scaffold's built-in Home route (order 0).
 *
 * Nav order: Home (0, scaffold) · Chat (10) · Jobs (20) · Approvals (30) ·
 * Autonomy (40) · Observatory (50) · Settings (90, last).
 */
import { createElement } from "react";
import { registerRoute } from "../routes";
import { Chat } from "./Chat";
import { Jobs } from "./Jobs";
import { Approvals } from "./Approvals";
import { Autonomy } from "./Autonomy";
import { Observatory } from "./Observatory";
import { Settings } from "./Settings";
import { AgentWorkshop } from "./AgentWorkshop";
import { Omni } from "./Omni";

registerRoute({ id: "omni", label: "Atlas", order: 1, render: () => createElement(Omni) });
registerRoute({ id: "chat", label: "Chat", order: 10, render: () => createElement(Chat) });
registerRoute({ id: "workshop", label: "Workshop", order: 15, render: () => createElement(AgentWorkshop) });
registerRoute({ id: "jobs", label: "Jobs", order: 20, render: () => createElement(Jobs) });
registerRoute({
  id: "approvals",
  label: "Approvals",
  order: 30,
  render: () => createElement(Approvals),
});
registerRoute({
  id: "autonomy",
  label: "Autonomy",
  order: 40,
  render: () => createElement(Autonomy),
});
registerRoute({
  id: "observatory",
  label: "Observatory",
  order: 50,
  render: () => createElement(Observatory),
});
registerRoute({
  id: "settings",
  label: "Settings",
  order: 90,
  render: () => createElement(Settings),
});
