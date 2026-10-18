/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Backgrounds & Surfaces
        canvas: '#F5F7FB',
        surface: {
          DEFAULT: '#FFFFFF',
          muted: '#F8FAFC',
        },
        // Sidebar
        sidebar: {
          DEFAULT: '#101929',
          raised: '#172238',
        },
        // Typography (Ink)
        ink: {
          DEFAULT: '#18243B',
          secondary: '#5B6980',
          soft: '#8691A4',
        },
        // Borders & Dividers
        line: {
          DEFAULT: '#E7EBF2',
          soft: '#F0F2F6',
        },
        // Accents
        accent: {
          DEFAULT: '#4F6DF5',
          soft: '#EDF1FF',
        },
        // Status Colors (with their soft fills)
        status: {
          success: { DEFAULT: '#168768', bg: '#E9F7F2' },
          warning: { DEFAULT: '#B97519', bg: '#FFF5E6' },
          error: { DEFAULT: '#BD4A67', bg: '#FFF0F3' },
          info: { DEFAULT: '#4F6DF5', bg: '#EDF1FF' },
          violet: { DEFAULT: '#765AC9', bg: '#F1EDFF' },
        }
      }
    },
  },
  plugins: [],
}