/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Design tokens for PrivacyGuard — a "classified document" theme.
        // Not the generic light SaaS look: dark, technical, terminal-adjacent.
        ink: "#0A0C0E",        // page background — near-black, not pure black
        panel: "#14181C",      // card/surface background
        panel2: "#1C2126",     // slightly lifted surface (hover states, headers)
        line: "#2A3138",       // borders/dividers
        text: "#DCE1E6",       // primary text
        muted: "#7C8894",      // secondary text
        safe: "#4ADE80",       // protected / passed
        risk: "#F87171",       // PII found / blocked
        risk_mid: "#FBBF24",   // medium risk
        accent: "#38BDF8",     // interactive accent (links, active states)
      },
      fontFamily: {
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}
