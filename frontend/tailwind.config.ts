import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#e02424",
          dark: "#c41f1f",
          darker: "#a81a1a",
          light: "#f03030",
        },
        surface: {
          DEFAULT: "#070709",
          elevated: "#0f0f12",
          card: "#131316",
          border: "#1e1e24",
          hover: "#1a1a1f",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.3)",
        "card-hover": "0 1px 3px rgba(0,0,0,0.4), 0 12px 32px rgba(0,0,0,0.4)",
        brand: "0 0 0 3px rgba(224,36,36,0.15)",
        "inner-top": "inset 0 1px 0 rgba(255,255,255,0.04)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #e02424 0%, #c41f1f 100%)",
        "surface-gradient": "linear-gradient(180deg, #171719 0%, #111114 100%)",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.25rem",
      },
    },
  },
  plugins: [],
};

export default config;
