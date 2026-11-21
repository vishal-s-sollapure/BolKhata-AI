/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        kirana: {
          50: '#fef7ee',
          100: '#fdedd6',
          200: '#fbd7ac',
          500: '#f58220',
          600: '#e06611',
          700: '#ba4d0c',
          800: '#943e12',
          900: '#783512',
        },
        khata: {
          green: '#10b981',
          red: '#ef4444',
          blue: '#0284c7',
          dark: '#0f172a',
        }
      }
    },
  },
  plugins: [],
}
