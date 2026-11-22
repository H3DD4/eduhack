export const READING_THEMES: Record<string, Record<string, string>> = {
  cream: { "--canvas": "#fbf5e9", "--surface": "#fffdf8", "--ink": "#252525", "--ink-muted": "#4c4c4c",
    "--border": "#776f61", "--control-stroke": "#252525", "--action": "#252525", "--action-hover": "#333333",
    "--action-base": "#174d3d", "--soft-fg": "#174d3d", "--help": "#344054", "--help-surface": "#e9e3d8",
    "--success": "#174d3d", "--success-surface": "#e1eddf", "--review-surface": "#f8e6e1", "--focus": "#173e32",
    "--tf-hl": "#b9e5c7", "--tf-strong": "#174d3d", "--tf-ink": "#252525", "--tf-slate": "#344054",
    "--tf-paper": "#fbf5e9", "--tf-soft": "#e1eddf", "--tf-soft-fg": "#174d3d", "--discovery": "#174d3d",
    "--needs-review": "#9b1c16", "--shadow": "#252525", "--edge": "#174d3d" },
  pastel: { "--canvas": "#f2f7fc", "--surface": "#ffffff", "--ink": "#1e293b", "--ink-muted": "#475569",
    "--border": "#64748b", "--control-stroke": "#1e293b", "--action": "#1e293b", "--action-hover": "#334155",
    "--action-base": "#174d3d", "--soft-fg": "#174d3d", "--help": "#334155", "--help-surface": "#e7edf5",
    "--success": "#17553b", "--success-surface": "#dff1e8", "--review-surface": "#f9e5e3", "--focus": "#1e293b",
    "--tf-hl": "#c5e5d3", "--tf-strong": "#17553b", "--tf-ink": "#1e293b", "--tf-slate": "#334155",
    "--tf-paper": "#f2f7fc", "--tf-soft": "#e7edf5", "--tf-soft-fg": "#174d3d", "--discovery": "#17553b",
    "--needs-review": "#9b1c16", "--shadow": "#1e293b", "--edge": "#17553b" },
  dark: { "--canvas": "#111827", "--surface": "#1f2937", "--ink": "#f9fafb", "--ink-muted": "#d1d5db",
    "--border": "#9ca3af", "--control-stroke": "#f9fafb", "--action": "#111827", "--action-hover": "#1f2937",
    "--action-base": "#86efac", "--soft-fg": "#d1fae5", "--help": "#e5e7eb", "--help-surface": "#374151",
    "--success": "#d1fae5", "--success-surface": "#174d3d", "--review-surface": "#552c2a", "--focus": "#fde68a",
    "--tf-hl": "#fde68a", "--tf-strong": "#34d399", "--tf-ink": "#111827", "--tf-slate": "#374151",
    "--tf-paper": "#111827", "--tf-soft": "#374151", "--tf-soft-fg": "#d1fae5", "--discovery": "#86efac",
    "--needs-review": "#fecaca", "--shadow": "#030712", "--edge": "#34d399" },
  "high-contrast": { "--canvas": "#ffffff", "--surface": "#ffffff", "--ink": "#000000", "--ink-muted": "#222222",
    "--border": "#000000", "--control-stroke": "#000000", "--action": "#000000", "--action-hover": "#222222",
    "--action-base": "#000000", "--soft-fg": "#000000", "--help": "#000000", "--help-surface": "#eeeeee",
    "--success": "#000000", "--success-surface": "#e5ffe5", "--review-surface": "#ffe5e5", "--focus": "#000000",
    "--tf-hl": "#ffff00", "--tf-strong": "#000000", "--tf-ink": "#000000", "--tf-slate": "#000000",
    "--tf-paper": "#ffffff", "--tf-soft": "#eeeeee", "--tf-soft-fg": "#000000", "--discovery": "#000000",
    "--needs-review": "#8b0000", "--shadow": "#000000", "--edge": "#000000" },
};

function luminance(hex: string): number {
  const channels = hex.slice(1).match(/.{2}/g)?.map((part) => parseInt(part, 16) / 255) || [];
  const [r, g, b] = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(foreground: string, background: string): number {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}
