export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Light, airy, low-saturation palette (mirrors the :root CSS variables
        // in styles.css). Concrete hex values keep Tailwind opacity utilities
        // (e.g. bg-primary/10) working.
        surface: "#fbfbfa", // --bg
        "surface-bright": "#ffffff",
        "surface-container-lowest": "#ffffff", // --surface
        "surface-container-low": "#f4f4f2", // --surface-2
        "surface-container": "#efefec",
        "surface-container-high": "#e9e9e5",
        "surface-container-highest": "#e3e3de",
        "surface-variant": "#e3e3de",
        "on-surface": "#1f1e1c", // --ink
        "on-surface-variant": "#6e6d67", // --muted
        outline: "#9a998f", // --faint
        "outline-variant": "#e7e6e1", // ≈ --border-strong on bg
        primary: "#c97f62", // --accent
        "primary-container": "#b96e51", // --accent-hover
        "on-primary": "#ffffff",
        secondary: "#5f8466", // --ok
        "secondary-container": "#c9dbcd",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#4a6b51",
        ok: "#5f8466",
        warn: "#b68a4a",
        danger: "#b0573f",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        ambient: "0 4px 16px rgba(60, 50, 35, 0.06)",
      },
    },
  },
  plugins: [],
}
