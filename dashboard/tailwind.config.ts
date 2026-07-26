import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        artax: {
          navy: "#0a0e1a",
          "navy-light": "#111827",
          blue: "#3b82f6",
          "blue-glow": "#60a5fa",
          green: "#22d3ee",
          "green-glow": "#06b6d4",
          purple: "#a855f7",
          surface: "#1a1f2e",
          "surface-light": "#252b3b",
          border: "#2d3548",
        },
      },
      boxShadow: {
        glow: "0 0 15px rgba(59, 130, 246, 0.3)",
        "glow-green": "0 0 15px rgba(34, 211, 238, 0.3)",
      },
    },
  },
  plugins: [],
};

export default config;
