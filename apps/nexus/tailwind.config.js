/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Anchored on near-black HUD backgrounds; signal palette = vertex accents.
        base: '#0A0E14',
        panel: 'rgba(18,24,33,0.72)',
        'panel-solid': '#121821',
        hairline: 'rgba(120,150,180,0.16)',
        ink: '#E6EDF3',
        'ink-dim': '#8499AD',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 24px var(--octa-glow), 0 0 4px var(--octa-glow)',
      },
    },
  },
  plugins: [],
};
