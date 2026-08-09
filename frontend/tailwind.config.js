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
        dark: {
          bg: '#060E0A',        // Very dark forest green background
          panel: '#0D1912',     // Dark olive panel
          elevated: '#14251B',  // Dark olive elevated card surface
          hover: '#1A2E22',     // Dark olive hover state
          border: 'rgba(245, 239, 230, 0.12)', // Cream hairline border
        },
        accent: {
          DEFAULT: '#3D7A56',   // Olive emerald accent
          hover: '#2E5E41',
          light: 'rgba(61, 122, 86, 0.2)',
        },
        cream: {
          DEFAULT: '#F5EFE6',   // Primary warm cream text
          muted: '#C4BCAD',     // Secondary muted text
          dim: '#9E9686',       // Dim helper labels
        },
        semantic: {
          green: '#4ADE80',     // Bright mint green for gain
          red: '#F87171',       // Muted soft red for loss
          amber: '#FBBF24',     // Muted warm amber for warning
        },
      },
      fontFamily: {
        sans: ['Söhne', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        serif: ['Fraunces', 'Georgia', 'serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};
