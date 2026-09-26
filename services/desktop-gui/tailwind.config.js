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
          950: '#07090e',
          900: '#0c1017',
          850: '#111722',
          800: '#161e2e',
          700: '#232e42',
          600: '#334155',
        },
        accent: {
          blue: '#3b82f6',
          indigo: '#6366f1',
          slate: '#64748b',
          muted: '#94a3b8',
        }
      }
    },
  },
  plugins: [],
}
