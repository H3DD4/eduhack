import type { Config } from "tailwindcss";

// ThinkFirst brand tokens live as CSS variables in globals.css; Tailwind only points at them.
const v = (name: string) => `var(--${name})`;
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: v("canvas"), surface: v("surface"), "surface-subtle": v("surface-subtle"), ink: v("ink"), "ink-muted": v("ink-muted"),
        border: v("border"), stroke: v("control-stroke"), action: v("action"), "action-hover": v("action-hover"),
        "action-base": v("action-base"), help: v("help"), "help-surface": v("help-surface"), discovery: v("discovery"),
        success: v("success"), "success-surface": v("success-surface"), review: v("needs-review"),
        "review-surface": v("review-surface"), focus: v("focus"),
        accent: v("tf-ink"), hl: v("tf-hl"), strong: v("tf-strong"), paper: v("tf-paper"), slate: v("tf-slate"),
        soft: v("tf-soft"), "soft-fg": v("tf-soft-fg"),
      },
      borderRadius: { detail: "8px", control: "14px", card: "20px", pill: "999px" },
      fontSize: {
        meta: ["0.875rem", "1.25rem"], body: ["1.0625rem", "1.65rem"], problem: ["1.1875rem", "1.875rem"],
        section: ["1.625rem", "2.0625rem"], page: ["2.5rem", "2.875rem"], "page-compact": ["2rem", "2.4rem"],
        hero: ["3.25rem", "3.6rem"],
      },
      maxWidth: { overview: "1240px", prose: "48rem", form: "520px", modal: "560px", panel: "320px" },
      boxShadow: { hard: "0 5px 0 var(--shadow)", "hard-lg": "0 8px 0 var(--shadow)", edge: "0 5px 0 var(--edge)" },
      transitionTimingFunction: { atlas: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
      fontFamily: {
        sans: ["Acme", "Noto Sans Arabic", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
