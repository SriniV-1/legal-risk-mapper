/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Menlo", "monospace"],
      },
      colors: {
        // Severity palette — reused everywhere for consistency
        high:   { DEFAULT: "#dc2626", bg: "#fef2f2", border: "#fecaca", ink: "#7f1d1d" },
        med:    { DEFAULT: "#d97706", bg: "#fffbeb", border: "#fde68a", ink: "#78350f" },
        low:    { DEFAULT: "#059669", bg: "#ecfdf5", border: "#a7f3d0", ink: "#064e3b" },
        // Detection source palette
        srcRegex: "#2563eb",
        srcSem:   "#8b5cf6",
        srcBoth:  "#0891b2",
      },
      keyframes: {
        "fade-in": { from: { opacity: 0, transform: "translateY(4px)" }, to: { opacity: 1, transform: "translateY(0)" } },
      },
      animation: {
        "fade-in": "fade-in .25s ease-out",
      },
    },
  },
  plugins: [],
};
