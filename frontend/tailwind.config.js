/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Warm Sophisticated Palette (Light Mode Default)
        bg: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          tertiary: 'var(--bg-tertiary)',
          hover: 'var(--bg-hover)',
          input: 'var(--bg-input)',
        },
        tx: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          light: 'var(--accent-light)',
          muted: 'var(--accent-muted)',
        },
        border: {
          DEFAULT: 'var(--border)',
          strong: 'var(--border-strong)',
        },
        semantic: {
          green: 'var(--semantic-green)',
          red: 'var(--semantic-red)',
          amber: 'var(--semantic-amber)',
          'green-bg': 'var(--semantic-green-bg)',
          'red-bg': 'var(--semantic-red-bg)',
          'amber-bg': 'var(--semantic-amber-bg)',
        },

        // Legacy aliases for backward compatibility during migration
        cream: {
          DEFAULT: 'var(--text-primary)',
          muted: 'var(--text-secondary)',
          dim: 'var(--text-tertiary)',
        },
      },
      fontFamily: {
        heading: ['Literata', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        serif: ['Literata', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'metric': ['2rem', { lineHeight: '1.2', fontWeight: '600' }],       // 32px for big metric values
        'metric-lg': ['2.5rem', { lineHeight: '1.1', fontWeight: '600' }],  // 40px for hero metrics
      },
      borderRadius: {
        'card': '12px',
      },
      boxShadow: {
        'card': '0 2px 8px rgba(0, 0, 0, 0.06)',
        'card-hover': '0 4px 16px rgba(0, 0, 0, 0.10)',
        'elevated': '0 8px 32px rgba(0, 0, 0, 0.12)',
        'glow': 'inset 0 0 0 2px var(--accent)',
        'glow-soft': '0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent)',
      },
      spacing: {
        'card': '24px',
        'card-gap': '20px',
        'section': '32px',
      },
      transitionDuration: {
        'micro': '150ms',
        'smooth': '200ms',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'value-flash': {
          '0%': { color: 'var(--accent)' },
          '100%': { color: 'var(--text-primary)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out',
        'value-flash': 'value-flash 0.2s ease-out',
      },
    },
  },
  plugins: [],
};
