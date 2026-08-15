import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0A100D',
        panel: '#111814',
        panelRaised: '#141D18',
        borderSoft: '#1A2420',
        borderStrong: '#223028',
        textMain: '#E7ECE7',
        textDim: '#8B9990',
        textFaint: '#58655E',
        brandGreen: '#3FE0A1',
        brandAmber: '#F5B24A',
        brandRed: '#FF6B5E',
        brandBlue: '#3E6FD8',
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      }
    },
  },
  plugins: [],
};
export default config;