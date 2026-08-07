/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9', // Trust/Care Blue
          600: '#0284c7',
          700: '#0369a1',
          teal: '#14b8a6', // Muted Teal
        }
      }
    },
  },
  plugins: [],
}
