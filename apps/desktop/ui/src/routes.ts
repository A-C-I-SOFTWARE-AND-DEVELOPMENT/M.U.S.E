/**
 * Append-only route registry.
 *
 * This is the extension seam for the desktop app. Future feature grains add a
 * route by PUSHING onto `routes` from their own module — they MUST NOT edit a
 * shared switch/enum, so two grains can register routes in parallel without
 * touching the same lines (no merge conflict on a central dispatcher).
 *
 * Contract:
 *   - `id` is unique and stable (used as the hash and React key).
 *   - `label` is the nav text.
 *   - `element` is the rendered view (a React element, lazily evaluated by the
 *     router so registration order doesn't force eager imports).
 *   - `order` (optional) sorts the nav; lower = earlier. Home is 0.
 *
 * To add a route from a feature grain, in your own file:
 *
 *     import { registerRoute } from "../routes";
 *     registerRoute({ id: "jobs", label: "Jobs", order: 10, render: () => <JobsView /> });
 *
 * Then import that file once for its side effect (e.g. from routes.register.ts
 * or your feature's index). The Home route below is the single placeholder this
 * scaffold ships; everything else is additive.
 */
import type { ReactNode } from "react";

export type RouteDef = {
  /** Stable unique id; also the URL hash and React key. */
  id: string;
  /** Nav label. */
  label: string;
  /** Lazily rendered view. */
  render: () => ReactNode;
  /** Nav sort order; lower comes first. Defaults to 100. */
  order?: number;
};

/**
 * The live registry. Mutable on purpose — grains append to it. Consumers should
 * read it via `getRoutes()` (which returns a sorted copy) rather than relying on
 * insertion order.
 */
export const routes: RouteDef[] = [];

/**
 * Register a route. Idempotent on `id`: a duplicate id replaces the prior
 * definition (so hot-reload / re-import doesn't double-register). Returns the
 * registry for chaining.
 */
export function registerRoute(def: RouteDef): RouteDef[] {
  const existing = routes.findIndex((r) => r.id === def.id);
  if (existing >= 0) routes[existing] = def;
  else routes.push(def);
  return routes;
}

/** A nav-sorted copy of the registry (stable: order, then registration order). */
export function getRoutes(): RouteDef[] {
  return routes
    .map((r, i) => ({ r, i }))
    .sort((a, b) => (a.r.order ?? 100) - (b.r.order ?? 100) || a.i - b.i)
    .map(({ r }) => r);
}

/** Look up a route by id. */
export function findRoute(id: string): RouteDef | undefined {
  return routes.find((r) => r.id === id);
}
