import type { Config } from "tailwindcss";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: token("canvas"),
        surface: token("surface"),
        sunken: token("sunken"),
        line: token("line"),
        "line-strong": token("line-strong"),
        ink: token("ink"),
        "ink-2": token("ink-2"),
        "ink-3": token("ink-3"),
        brand: token("brand"),
        "brand-ink": token("brand-ink"),
        accent: token("accent"),
        "accent-soft": token("accent-soft"),
        good: token("good"),
        "good-soft": token("good-soft"),
        warn: token("warn"),
        "warn-soft": token("warn-soft"),
        bad: token("bad"),
        "bad-soft": token("bad-soft"),
        nav: token("nav"),
        "nav-ink": token("nav-ink"),
        "nav-active": token("nav-active"),
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      fontSize: { "2xs": ["0.6875rem", "1rem"] },
      boxShadow: { card: "0 1px 0 rgb(var(--shadow) / 0.04), 0 1px 2px rgb(var(--shadow) / 0.06)" },
    },
  },
  plugins: [],
} satisfies Config;
