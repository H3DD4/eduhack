import type { Config } from "tailwindcss";

// Atlas Studio tokens (blueprint "Visual and motion system") are CSS variables in globals.css.
const v = (name: string) => `var(--${name})`;
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: v("canvas"), surface: v("surface"), ink: v("ink"), "ink-muted": v("ink-muted"),
        border: v("border"), stroke: v("control-stroke"), action: v("action"), "action-hover": v("action-hover"),
        "action-base": v("action-base"), help: v("help"), "help-surface": v("help-surface"), discovery: v("discovery"),
        success: v("success"), "success-surface": v("success-surface"), review: v("needs-review"),
        "review-surface": v("review-surface"), focus: v("focus"),
      },
      borderRadius: { detail: "8px", control: "14px", card: "20px", pill: "999px" },
      fontSize: {
        meta: ["0.875rem", "1.25rem"], body: ["1rem", "1.625rem"], problem: ["1.125rem", "1.8125rem"],
        section: ["1.5rem", "1.9375rem"], page: ["2rem", "2.5rem"], "page-compact": ["1.75rem", "2.25rem"],
      },
      maxWidth: { overview: "1200px", prose: "48rem", form: "480px", modal: "560px", panel: "320px" },
      transitionTimingFunction: { atlas: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
      fontFamily: { sans: ["Nunito Sans", "Noto Sans Arabic", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
} satisfies Config;
