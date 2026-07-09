#!/usr/bin/env node
// Build-time snapshot of the repo's GitHub releases for the public cockpit.
//
// Writes <out>/releases.json, which cockpit.dc.html fetches at runtime to
// refresh its Releases section (the baked releaseData in the page stays as
// the offline / gateway-served fallback). Never fails the build: on any
// network/API error it simply writes nothing and the page falls back.
//
// Usage: node scripts/deploy/gen_releases_json.mjs <out-dir>

import { writeFileSync } from 'node:fs';
import { join } from 'node:path';

const OUT = process.argv[2];
if (!OUT) {
  console.error('usage: gen_releases_json.mjs <out-dir>');
  process.exit(1);
}

const REPO = 'A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E';
const API = `https://api.github.com/repos/${REPO}/releases?per_page=30`;

// Tags the cockpit's platform cards bind to.
const PLATFORM_TAGS = { desktop: 'muse-desktop-latest', android: 'android-latest' };

function firstLine(body) {
  const line = String(body || '').split('\n').find((l) => l.trim());
  return line ? line.replace(/[*_#>]/g, '').trim().slice(0, 240) : '';
}

function versionFrom(body) {
  const m = String(body || '').match(/Version ([0-9][\w.]*)/);
  return m ? m[1] : '';
}

try {
  const res = await fetch(API, {
    headers: {
      Accept: 'application/vnd.github+json',
      'User-Agent': 'muse-cockpit-build',
      ...(process.env.GITHUB_TOKEN ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`GitHub API ${res.status}`);
  const releases = await res.json();
  if (!Array.isArray(releases) || releases.length === 0) throw new Error('no releases');

  const byTag = Object.fromEntries(releases.map((r) => [r.tag_name, r]));

  // Latest *versioned* release (vX.Y.Z tags) drives the "Latest" card.
  const tagged = releases
    .filter((r) => /^v\d+\.\d+\.\d+$/.test(r.tag_name) && !r.draft)
    .sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
  const latest = tagged[0];

  const out = {
    generated: new Date().toISOString(),
    url: `https://github.com/${REPO}/releases`,
    platforms: [],
  };

  if (latest) {
    out.tag = `${latest.tag_name} · rolling`;
    out.ver = `Latest tagged ${latest.tag_name} · desktop and Android publish rolling builds`;
    out.latestVer = latest.tag_name;
    out.latestName = (latest.name || '').replace(/^v[\d.]+\s*[-—:]?\s*/, '') || latest.tag_name;
    out.latestDate = new Date(latest.published_at).toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric',
    });
    const summary = firstLine((latest.body || '').split('\n').filter((l) => l.trim() && !l.startsWith('#')).join('\n'));
    if (summary) out.latestSummary = summary;
  }

  for (const [id, tag] of Object.entries(PLATFORM_TAGS)) {
    const rel = byTag[tag];
    if (!rel) continue;
    const entry = { id, url: rel.html_url, urlLabel: `Open ${tag} →` };
    const ver = versionFrom(rel.body);
    if (ver) entry.sub = id === 'desktop' ? `v${ver} · macOS · Windows · Linux` : `v${ver} · Android 8.0+ · arm64 / armv7`;
    out.platforms.push(entry);
  }
  out.platforms.push({ id: 'source', url: `https://github.com/${REPO}`, urlLabel: 'Open the repository →' });

  writeFileSync(join(OUT, 'releases.json'), JSON.stringify(out, null, 2));
  console.log(`releases.json written (${out.platforms.length} platform links, latest ${out.latestVer || 'n/a'})`);
} catch (err) {
  console.warn(`releases.json skipped (${err.message}) — page will use its baked fallback`);
}
