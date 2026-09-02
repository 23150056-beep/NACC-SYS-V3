/** @type {import('tailwindcss').Config} */

/* Tailwind is here for its base reset (preflight) and almost nothing else.
 *
 * The app is built from the token-driven design system in src/ui/index.jsx and
 * the racco-* classes in src/index.css. Across the whole of src/ there is
 * exactly one Tailwind utility usage — "p-6 text-gray-500" in
 * ProtectedRoute.jsx. What earns Tailwind its place in the build is preflight:
 * it resets margins on headings and lists, sets box-sizing, and makes images
 * display:block, and every screen is laid out assuming that.
 *
 * So this file is nearly empty on purpose. It previously extended the theme
 * with a `brand` palette — a sky blue and a teal, used zero times, and not the
 * agency's colour anyway (the real one is --blue-600: #2236c4, in index.css).
 * Anything added here should be something the app actually uses; put colours in
 * index.css with the rest of the tokens.
 */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
}
