// Bundle the interactive 3D Systems Atlas into ONE portable, self-contained HTML
// file (three.js, app, styles and data all inlined) that opens by double-click —
// no server, no network. Output lands in the git-ignored docs/_generated tree.
//
// Usage:  node scripts/diagrams/bundle_atlas_singlefile.mjs
//
// Uses the esbuild already vendored under apps/nexus/node_modules.
import { createRequire } from 'module';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const esbuild = require(resolve(root, 'apps/nexus/node_modules/esbuild'));

const d = resolve(root, 'docs/3d-model');
const res = await esbuild.build({
  entryPoints: [resolve(d, 'app.js')],
  bundle: true,
  format: 'esm',
  minify: true,
  write: false,
  logLevel: 'warning',
});
const bundle = res.outputFiles[0].text;

let html = readFileSync(resolve(d, 'index.html'), 'utf8');
const css = readFileSync(resolve(d, 'style.css'), 'utf8');
const data = readFileSync(resolve(d, 'architecture_data.js'), 'utf8');

html = html
  .replace('<link rel="stylesheet" href="style.css">', `<style>\n${css}\n</style>`)
  .replace('<script src="architecture_data.js"></script>', `<script>\n${data}\n</script>`)
  .replace('<script type="module" src="app.js"></script>', `<script type="module">\n${bundle}\n</script>`);

for (const ref of ['src="app.js"', 'src="architecture_data.js"', 'href="style.css"']) {
  if (html.includes(ref)) throw new Error(`external reference remained: ${ref}`);
}

const outDir = resolve(root, 'docs/_generated/flowchart');
mkdirSync(outDir, { recursive: true });
const out = resolve(outDir, 'MUSE_3D_Systems_Atlas.html');
writeFileSync(out, html);
console.log('WROTE', out, `${Math.round(html.length / 1024)} KB`);
