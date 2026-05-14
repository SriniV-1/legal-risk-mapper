/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Playfair Display'", "Georgia", "serif"],
        sans: ["'DM Sans'", "system-ui", "sans-serif"],
      },
      colors: {
        warm: {
          50:  "#F9F9F8",
          100: "#F2F1EF",
          200: "#E0DED9",
          300: "#CCCAC5",
          400: "#A9A7A2",
          500: "#84827D",
          600: "#5C5A55",
          700: "#3B3935",
          800: "#232119",
          900: "#131210",
          950: "#0A0908",
        },
      },
    },
  },
  plugins: [],
};
