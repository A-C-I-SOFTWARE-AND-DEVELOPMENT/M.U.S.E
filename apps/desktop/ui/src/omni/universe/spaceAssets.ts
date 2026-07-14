/**
 * Real-photography space plates layered into the universe backdrop.
 *
 * Paths are relative to the served document root (Vite `public/`), so they
 * resolve identically in the Tauri shell, `vite dev`, and when the cockpit
 * gateway serves the built UI at `/`. Full provenance and licensing live in
 * `public/space/ATTRIBUTION.md` — keep that file in sync with this manifest.
 */

export interface SpacePlate {
  /** Root-relative URL the renderer loads. */
  readonly path: string;
  /** Human-readable credit line (surfaced in diagnostics/docs, not rendered). */
  readonly credit: string;
  /** Equirectangular size the plate ships at. */
  readonly width: number;
  readonly height: number;
}

export const SPACE_PLATES = {
  /** Deep starfield: backdrop sphere + PMREM reflection environment. */
  starmap: {
    path: './space/starmap-4k.jpg',
    credit: 'Tycho-2 catalogue all-sky render (globe.gl distribution)',
    width: 4096,
    height: 2048,
  },
  /** NASA Blue Marble day-side surface. */
  earthDay: {
    path: './space/earth-day-2k.jpg',
    credit: 'NASA Visible Earth — Blue Marble: Next Generation',
    width: 2048,
    height: 1024,
  },
  /** NASA Black Marble night-side city lights. */
  earthNight: {
    path: './space/earth-night-2k.jpg',
    credit: 'NASA Earth Observatory — Black Marble (Suomi NPP VIIRS)',
    width: 2048,
    height: 1024,
  },
  /** NASA cloud-fraction plate, sampled as coverage. */
  earthClouds: {
    path: './space/earth-clouds-2k.jpg',
    credit: 'NASA Visible Earth — Blue Marble cloud fraction (Terra/MODIS)',
    width: 2048,
    height: 1024,
  },
} as const satisfies Record<string, SpacePlate>;

export const SPACE_ATTRIBUTION_DOC = './space/ATTRIBUTION.md';

/** Every plate the renderer may fetch — used by tests and preloaders. */
export function listSpacePlates(): readonly SpacePlate[] {
  return Object.values(SPACE_PLATES);
}
