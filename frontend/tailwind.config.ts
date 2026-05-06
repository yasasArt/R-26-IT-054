import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surface hierarchy
        bg: "var(--bg)",
        surface: "var(--surface)",
        card: "var(--card)",
        "card-border": "var(--card-border)",
        dim: "var(--dim)",

        // Text
        "text-primary": "var(--text)",
        "text-muted": "var(--muted)",
        "text-dim": "var(--dim)",

        // Status / accent
        accent: "var(--accent)",
        success: "var(--green)",
        warning: "var(--yellow)",
        danger: "var(--red)",
        orange: "var(--orange)",

        // Mode colors
        "sewing-primary": "#22C55E",
        "sewing-muted": "rgba(34,197,94,0.12)",
        "quality-primary": "#3B82F6",
        "quality-muted": "rgba(59,130,246,0.12)",
      },
      fontFamily: {
        display: ["var(--font-space-grotesk)", "sans-serif"],
        mono: ["var(--font-ibm-plex-mono)", "monospace"],
      },
      borderRadius: {
        card: "12px",
        badge: "6px",
      },
      boxShadow: {
        "glow-green": "0 0 12px rgba(34,197,94,0.35)",
        "glow-blue": "0 0 12px rgba(59,130,246,0.35)",
        "glow-red": "0 0 12px rgba(239,68,68,0.35)",
        "glow-yellow": "0 0 12px rgba(250,204,21,0.35)",
        card: "0 2px 16px rgba(0,0,0,0.4)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-in-right": "slideInRight 0.3s ease-out",
        "count-up": "countUp 0.4s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideInRight: {
          "0%": { opacity: "0", transform: "translateX(20px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        countUp: {
          "0%": { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
