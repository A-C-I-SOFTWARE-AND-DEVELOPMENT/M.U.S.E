#!/usr/bin/env node
// @muse/design-system — token contract test.
//
// PURE Node, zero dependencies. Asserts the GENERATED dist artifacts carry the
// exact canonical Singularity hex values, on both targets (CSS + Kotlin), so a
// drift in the generator or tokens.json can never silently ship a wrong color.
//
// Run `npm run build` first. Exits non-zero on any mismatch.

import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DIST = join(ROOT, "dist");

const failures = [];
function check(cond, msg) {
  if (cond) {
    console.log(`  ok  ${msg}`);
  } else {
    failures.push(msg);
    console.error(`FAIL  ${msg}`);
  }
}

// The canonical Singularity palette — the contract.
const HEX = {
  void: "#050507",
  "void-2": "#0b0d12",
  "void-3": "#12151d",
  edge: "#1c2030",
  core: "#ffffff",
  signal: "#e8ecf4",
  "signal-dim": "#aab2c4",
  "signal-mute": "#6b7388",
  "ring-1": "#7ae0ff",
  "ring-2": "#b388ff",
  ok: "#5be3a0",
  warn: "#f5c451",
  danger: "#ff5c63",
};

// ---- artifacts exist -------------------------------------------------------
const cssPath = join(DIST, "tokens.css");
const ktPath = join(DIST, "Tokens.kt");
check(existsSync(cssPath), "dist/tokens.css exists");
check(existsSync(ktPath), "dist/Tokens.kt exists");
if (failures.length) {
  console.error("\nrun `npm run build` first.");
  process.exit(1);
}

const css = readFileSync(cssPath, "utf8");
const kt = readFileSync(ktPath, "utf8");

// ---- every canonical hex appears in BOTH targets ---------------------------
for (const [name, hex] of Object.entries(HEX)) {
  check(css.includes(hex), `tokens.css contains ${name} ${hex}`);

  // Kotlin: "#aabbcc" -> "0xFFAABBCC"
  const composeLong = `0xFF${hex.replace("#", "").toUpperCase()}`;
  check(kt.includes(composeLong), `Tokens.kt contains ${name} ${composeLong}`);
}

// ---- ring gradient stops present -------------------------------------------
check(
  css.includes("linear-gradient(90deg, #7ae0ff, #b388ff)"),
  "tokens.css contains the ring gradient",
);
check(kt.includes("ringGradientStops"), "Tokens.kt exposes ringGradientStops");

// ---- scales wired through --------------------------------------------------
check(css.includes("--radius: 12px"), "tokens.css keeps --radius: 12px (md)");
check(css.includes("--space-1: 4px"), "tokens.css spacing 4/8 grid present");
check(css.includes("--space-16: 64px"), "tokens.css spacing tops out at 64px");
check(kt.includes("object MuseTokens"), "Tokens.kt defines object MuseTokens");
check(kt.includes("import androidx.compose.ui.graphics.Color"), "Tokens.kt imports Compose Color");

// ---- glyph geometry --------------------------------------------------------
check(css.includes("--glyph-rotate: -32deg"), "tokens.css glyph rotate -32deg");
check(kt.includes("rotate = -32f"), "Tokens.kt glyph rotate -32f");

// ---------------------------------------------------------------------------
if (failures.length) {
  console.error(`\n${failures.length} assertion(s) failed.`);
  process.exit(1);
}
console.log(`\nall ${Object.keys(HEX).length * 2 + 9} assertions passed.`);
