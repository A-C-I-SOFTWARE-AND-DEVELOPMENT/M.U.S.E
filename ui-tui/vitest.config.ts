import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    // Colour depth is latched by chalk / supports-color when they are first
    // imported, from these vars. A vitest run has no TTY, so without them the
    // level latches at 0, ink emits no SGR at all, and any test asserting on
    // rendered colour compares against an empty list — passing or failing for
    // reasons that have nothing to do with the palette. Setting them here is
    // the only place guaranteed to run before the import graph.
    env: {
      COLORTERM: 'truecolor',
      FORCE_COLOR: '3'
    },
    exclude: ['dist/**', 'node_modules/**']
  }
})
