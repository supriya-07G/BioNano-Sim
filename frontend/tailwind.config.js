/**
 * BioNano-Sim design system.
 *
 * A space-research command centre, not a gaming dashboard: near-black navy
 * ground, fine borders, restrained cyan/violet illumination. Every surface
 * colour is opaque so text contrast is predictable — translucency is reserved
 * for accents and glows, never for card backgrounds carrying body text.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Grounds, darkest to lightest.
        void: 'rgb(var(--color-void) / <alpha-value>)',
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        elevated: 'rgb(var(--color-elevated) / <alpha-value>)',
        raised: 'rgb(var(--color-raised) / <alpha-value>)',
        hairline: 'rgb(var(--color-hairline) / <alpha-value>)',

        accent: {
          DEFAULT: 'rgb(var(--color-accent) / <alpha-value>)',
          soft: 'rgb(var(--color-accent-soft) / <alpha-value>)',
          deep: 'rgb(var(--color-accent-deep) / <alpha-value>)',
        },
        electric: 'rgb(var(--color-electric) / <alpha-value>)',
        violet: 'rgb(var(--color-violet) / <alpha-value>)',

        ok: 'rgb(var(--color-ok) / <alpha-value>)',
        warn: 'rgb(var(--color-warn) / <alpha-value>)',
        danger: 'rgb(var(--color-danger) / <alpha-value>)',

        ink: {
          DEFAULT: 'rgb(var(--color-ink) / <alpha-value>)',
          muted: 'rgb(var(--color-ink-muted) / <alpha-value>)',
          faint: 'rgb(var(--color-ink-faint) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        // Monospace is reserved for experiment ids, parameters and logs.
        mono: [
          'JetBrains Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Consolas',
          'Liberation Mono',
          'monospace',
        ],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        panel: 'var(--shadow-panel)',
        'glow-accent': '0 0 0 1px rgb(var(--color-accent) / 0.28), 0 0 28px -8px rgb(var(--color-accent) / 0.32)',
        'glow-violet': '0 0 0 1px rgb(var(--color-violet) / 0.28), 0 0 28px -8px rgb(var(--color-violet) / 0.30)',
        inset: 'var(--shadow-inset)',
      },
      backgroundImage: {
        'grid-fine':
          'linear-gradient(rgb(var(--color-grid) / 0.055) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--color-grid) / 0.055) 1px, transparent 1px)',
        'orbit-glow':
          'radial-gradient(1100px 520px at 22% -12%, rgb(var(--color-grid) / 0.12), transparent 62%), radial-gradient(880px 420px at 88% 8%, rgb(var(--color-orbit) / 0.11), transparent 60%)',
        'hairline-b':
          'linear-gradient(90deg, transparent, rgb(var(--color-grid) / 0.32), transparent)',
      },
      backgroundSize: { 'grid-fine': '44px 44px' },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'spin-slow': {
          to: { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.32s ease-out both',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        shimmer: 'shimmer 1.6s infinite',
        'spin-slow': 'spin-slow 22s linear infinite',
      },
      transitionTimingFunction: {
        crisp: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
      },
    },
  },
  plugins: [],
}
