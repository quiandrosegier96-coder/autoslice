import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#dc2626",
          dark: "#b91c1c",
          darker: "#991b1b",
          light: "#ef4444",
        },
        surface: {
          DEFAULT: "#080808",
          elevated: "#111111",
          card: "#191919",
          border: "#2a2a2a",
          hover: "#222222",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
