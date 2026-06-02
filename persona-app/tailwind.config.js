export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#f7f9fb",
        "surface-bright": "#f7f9fb",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f2f4f6",
        "surface-container": "#eceef0",
        "surface-container-high": "#e6e8ea",
        "surface-container-highest": "#e0e3e5",
        "surface-variant": "#e0e3e5",
        "on-surface": "#191c1e",
        "on-surface-variant": "#434655",
        outline: "#737686",
        "outline-variant": "#c3c6d7",
        primary: "#004ac6",
        "primary-container": "#2563eb",
        "on-primary": "#ffffff",
        secondary: "#006c49",
        "secondary-container": "#6cf8bb",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#00714d",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        ambient: "0 4px 12px rgba(15, 23, 42, 0.06)",
      },
    },
  },
  plugins: [],
}
