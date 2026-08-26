/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#0A0B14",
          900: "#0F1120",
          800: "#161A2E",
          700: "#1E2338",
        },
        violet: {
          400: "#9B8CFF",
          500: "#7C5CFC",
          600: "#6A45F0",
        },
        accent: {
          green: "#34D399",
          blue: "#38BDF8",
          amber: "#FBBF24",
          orange: "#FB923C",
          red: "#F87171",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
        glow: "0 0 24px 0 rgba(124, 92, 252, 0.35)",
      },
      backdropBlur: {
        xs: "2px",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [],
};
