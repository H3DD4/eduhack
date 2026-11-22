import { describe, expect, it } from "vitest";
import { contrastRatio, READING_THEMES } from "./themes";

const foregroundBackgroundPairs = [
  ["--ink", "--canvas"],
  ["--ink", "--surface"],
  ["--ink-muted", "--canvas"],
  ["--ink-muted", "--surface"],
  ["#ffffff", "--action"],
  ["#ffffff", "--action-hover"],
  ["--help", "--help-surface"],
  ["--success", "--success-surface"],
  ["--needs-review", "--review-surface"],
  ["--tf-ink", "--tf-hl"],
  ["--action-base", "--canvas"],
  ["--tf-soft-fg", "--tf-soft"],
] as const;

describe("reading aid theme contrast", () => {
  it.each(Object.entries(READING_THEMES))("%s meets WCAG AA for text pairs", (_name, theme) => {
    for (const [foreground, background] of foregroundBackgroundPairs) {
      expect(contrastRatio(theme[foreground] || foreground, theme[background] || background))
        .toBeGreaterThanOrEqual(4.5);
    }
  });
});
