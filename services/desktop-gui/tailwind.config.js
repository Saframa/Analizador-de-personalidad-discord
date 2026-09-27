/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      borderRadius: {
        none: '0px',
        xs: '1px',
        sm: '2px',
        DEFAULT: '2px',
        md: '2px',
        lg: '3px',
        xl: '4px',
        '2xl': '4px',
        '3xl': '4px',
        full: '2px',
      },
      colors: {
        dark: {
          950: '#07090e',
          900: '#0c1017',
          850: '#111722',
          800: '#161e2e',
          750: '#1c2538',
          700: '#232e42',
          650: '#2b3952',
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
