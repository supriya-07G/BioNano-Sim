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
        void: '#050816',      // page background
        surface: '#0B1024',   // panels
        elevated: '#111936',  // cards
        raised: '#18213F',    // hover / nested cards
        hairline: '#1E2A4A',  // borders

        accent: {
          DEFAULT: '#38BDF8', // cyan
          soft: '#7DD3FC',
          deep: '#0EA5E9',
        },
        electric: '#6366F1',
        violet: '#8B5CF6',

        ok: '#22C55E',
        warn: '#F59E0B',
        danger: '#EF4444',

        ink: {
          DEFAULT: '#F8FAFC', // primary text
          muted: '#94A3B8',   // secondary text
          faint: '#64748B',   // tertiary / captions
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
        panel: '0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.6)',
        'glow-accent': '0 0 0 1px rgba(56,189,248,0.28), 0 0 28px -8px rgba(56,189,248,0.32)',
        'glow-violet': '0 0 0 1px rgba(139,92,246,0.28), 0 0 28px -8px rgba(139,92,246,0.30)',
        inset: 'inset 0 1px 0 rgba(255,255,255,0.04)',
      },
      backgroundImage: {
        'grid-fine':
          'linear-gradient(rgba(56,189,248,0.055) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.055) 1px, transparent 1px)',
        'orbit-glow':
          'radial-gradient(1100px 520px at 22% -12%, rgba(56,189,248,0.12), transparent 62%), radial-gradient(880px 420px at 88% 8%, rgba(139,92,246,0.11), transparent 60%)',
        'hairline-b':
          'linear-gradient(90deg, transparent, rgba(56,189,248,0.32), transparent)',
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
