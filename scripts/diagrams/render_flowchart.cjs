#!/usr/bin/env node
/*
 * Render the generated M.U.S.E architecture flow-chart HTML to a single-page,
 * vector PDF using Playwright's bundled Chromium. Vector output stays crisp at
 * any zoom (well beyond 4K). The page is auto-sized to the content so the whole
 * poster lands on one page.
 *
 * Usage:  node render_flowchart.cjs <input.html> <output.pdf>
 *
 * Requires the `playwright` npm package (with a Chromium browser installed).
 * Honors PLAYWRIGHT_CHROMIUM (path to a Chromium binary) if Playwright cannot
 * locate its own.
 */
const path = require("path");

let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (_e) {
  ({ chromium } = require("playwright-core"));
}

(async () => {
  const [htmlPath, pdfPath] = process.argv.slice(2);
  if (!htmlPath || !pdfPath) {
    console.error("usage: node render_flowchart.cjs <input.html> <output.pdf>");
    process.exit(2);
  }
  const launchOpts = {
    args: ["--no-sandbox", "--font-render-hinting=none", "--force-color-profile=srgb"],
  };
  if (process.env.PLAYWRIGHT_CHROMIUM) launchOpts.executablePath = process.env.PLAYWRIGHT_CHROMIUM;

  const browser = await chromium.launch(launchOpts);
  const page = await browser.newPage();
  await page.goto("file://" + path.resolve(htmlPath), { waitUntil: "networkidle" });

  const dims = await page.evaluate(() => ({
    w: Math.ceil(document.body.scrollWidth),
    h: Math.ceil(document.body.scrollHeight),
  }));
  console.log("content px:", dims.w, "x", dims.h);

  await page.emulateMedia({ media: "screen" });
  await page.pdf({
    path: pdfPath,
    width: dims.w + "px",
    height: dims.h + 4 + "px", // +4px slack avoids a sliver second page
    printBackground: true,
    pageRanges: "1",
    margin: { top: "0", bottom: "0", left: "0", right: "0" },
  });
  await browser.close();
  console.log("WROTE", pdfPath);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
