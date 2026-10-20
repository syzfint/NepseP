/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#080B11",
        surface1: "#111622",
        surface2: "#1E2638",
      },
    },
  },
  plugins: [],
};
