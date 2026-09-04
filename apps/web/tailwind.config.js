/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0b1f2a",
          soft: "#1c3644",
        },
        sea: {
          DEFAULT: "#1a6b6b",
          bright: "#218a8a",
        },
        mist: "#e6eef2",
        foam: "#f4f8fa",
      },
      fontFamily: {
        display: ['"Sora"', "system-ui", "sans-serif"],
        sans: ['"Figtree"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
