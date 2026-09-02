export default {
  // Tailwind was here for its base reset only; that reset now lives in
  // src/index.css, transcribed. Autoprefixer stays — it is what adds the
  // vendor prefixes the reset and the design system rely on.
  plugins: {
    autoprefixer: {},
  },
}
