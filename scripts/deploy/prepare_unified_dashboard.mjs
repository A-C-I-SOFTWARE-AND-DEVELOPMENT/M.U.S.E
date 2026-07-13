#!/usr/bin/env node
import { existsSync, rmSync, mkdirSync, cpSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

const root = process.cwd().endsWith(`${join('', 'web')}`) ? join(process.cwd(), '..') : process.cwd();
const webPublic = join(root, 'web', 'public');
const cockpitStatic = join(root, 'gateway', 'cockpit', 'static');

function run(cmd, args, opts = {}) {
  console.log(`$ ${cmd} ${args.join(' ')}`);
  execFileSync(cmd, args, { cwd: root, stdio: 'inherit', env: { ...process.env, ...opts.env } });
}

function npmInstallIfNeeded(dir) {
  if (existsSync(join(root, dir, 'node_modules'))) {
    console.log(`deps already present for ${dir}`);
    return;
  }
  const lock = existsSync(join(root, dir, 'package-lock.json'));
  const args = lock ? ['--prefix', dir, 'ci', '--no-audit', '--no-fund'] : ['--prefix', dir, 'install', '--no-audit', '--no-fund'];
  run('npm', args);
}

function resetDir(dir) {
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
}

mkdirSync(webPublic, { recursive: true });

// MuseHQ: the OpenCode-layout MUSE cockpit, served inside the Hermes dashboard at /musehq/.
npmInstallIfNeeded('web/musehq');
run('npm', ['--prefix', 'web/musehq', 'run', 'build'], { env: { MUSEHQ_BASE: '/musehq/' } });
const museOut = join(webPublic, 'musehq');
resetDir(museOut);
cpSync(join(root, 'web', 'musehq', 'dist'), museOut, { recursive: true });

// NEXUS: the unified command console PWA, served inside the Hermes dashboard at /nexus/.
npmInstallIfNeeded('apps/nexus');
run('npm', ['--prefix', 'apps/nexus', 'run', 'build'], { env: { NEXUS_BASE: '/nexus/', NEXUS_NO_PWA: '1' } });
const nexusOut = join(webPublic, 'nexus');
resetDir(nexusOut);
cpSync(join(root, 'apps', 'nexus', 'dist'), nexusOut, { recursive: true });

// Muse Studio + cockpit static surfaces. Vite copies web/public into hermes_cli/web_dist.
const staticFiles = [
  'studio.html', 'studio-support.js',
  'observatory.html', 'observatory.css', 'observatory.js', 'observatory-demo.html', 'observatory-demo.json',
  'manifest.webmanifest', 'icon.svg', 'icon-180.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png',
  'terms.html', 'privacy.html', 'og.png', 'sitemap.xml',
  'tokens.css', 'cockpit.css',
];
for (const file of staticFiles) {
  const src = join(cockpitStatic, file);
  if (existsSync(src)) cpSync(src, join(webPublic, file));
}
for (const dir of ['atlas', 'vendor', 'styles']) {
  const src = join(cockpitStatic, dir);
  if (existsSync(src)) {
    const dst = join(webPublic, dir);
    resetDir(dst);
    cpSync(src, dst, { recursive: true });
  }
}
mkdirSync(join(webPublic, 'styles'), { recursive: true });
for (const file of ['tokens.css', 'cockpit.css']) {
  const src = join(cockpitStatic, file);
  if (existsSync(src)) cpSync(src, join(webPublic, 'styles', file));
}
if (existsSync(join(cockpitStatic, 'cockpit.dc.html'))) {
  cpSync(join(cockpitStatic, 'cockpit.dc.html'), join(webPublic, 'legacy.html'));
}

console.log('Unified dashboard assets staged in web/public: /musehq, /nexus, /studio.html, /atlas, /legacy.html');
