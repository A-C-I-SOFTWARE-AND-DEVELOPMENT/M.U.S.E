/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Mapped to the Singularity CSS vars (tokens.css is the source of
        // truth) so Tailwind utilities re-skin with the theme. White is the
        // hero; the cyan→violet ring is the sparing spectral accent.
        base: 'var(--bg-base)',
        elev: 'var(--bg-elev)',
        panel: 'var(--panel)',
        'panel-solid': 'var(--panel-solid)',
        hairline: 'var(--hairline)',
        ink: 'var(--ink)',
        'ink-dim': 'var(--ink-dim)',
        'ink-faint': 'var(--ink-faint)',
        // Raw Singularity tokens for new utilities.
        void: 'var(--void)',
        'void-2': 'var(--void-2)',
        'void-3': 'var(--void-3)',
        edge: 'var(--edge)',
        core: 'var(--core)',
        signal: 'var(--signal)',
        'signal-dim': 'var(--signal-dim)',
        'signal-mute': 'var(--signal-mute)',
        'ring-1': 'var(--ring-1)',
        'ring-2': 'var(--ring-2)',
        ok: 'var(--ok)',
        warn: 'var(--warn)',
        danger: 'var(--danger)',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
      },
      backgroundImage: {
        // The matte spectral ring as a usable gradient (never bloomed).
        'ring-grad': 'var(--ring-grad)',
      },
      boxShadow: {
        // Tonal elevation, not a glow — a hairline ring in the live octa colour.
        glow: '0 0 0 1px var(--octa-glow)',
      },
    },
  },
  plugins: [],
};
