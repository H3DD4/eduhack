# ThinkFirst web: brand redesign

This is the `web/` frontend from `H3DD4/eduhack`, restyled to the ThinkFirst "Mind print" brand. The API calls, routes and data shapes are unchanged, so it drops into the repo in place of `web/`.

## Run it

```bash
npm install
npm run dev        # http://localhost:3000, expects the API at API_URL (default http://127.0.0.1:8000)
npm run typecheck && npm run build
```

Fonts load from Google Fonts (Acme for text, JetBrains Mono for math). Arabic keeps Noto Sans Arabic.

## What changed

| Area | Change |
| --- | --- |
| Theme (`src/app/globals.css`, `tailwind.config.ts`) | WhatsApp green (`#25D366`) and yellow on navy, warm paper background. Every color is a CSS variable (`--tf-hl`, `--tf-strong`, `--tf-ink`, `--tf-slate`, `--tf-paper`, `--tf-soft`, `--tf-soft-fg`). The old token names still work and now point at the brand colors. |
| Interaction | Buttons, cards, chips, options and map nodes lift with a hard shadow on hover and press down on click. Fields glow yellow on focus. Pages fade in on navigation. Reduced motion is respected. |
| Logo (`src/components/Logo.tsx`, `src/app/icon.svg`, `public/brand/`) | "Mind print" mark and wordmark, favicon and logo files. |
| App shell (`src/components/AppShell.tsx`) | Floating pill navigation with icons, a mobile bottom bar, menus that close on outside click or Escape, and a Ctrl/Cmd+K "jump to" menu (`src/components/CommandPalette.tsx`). |
| Welcome | Brand hero beside the sign-in form, scrolling band of subjects. |
| Onboarding | One question per screen with progress, time left, Back/Next, number-key shortcuts. Same payload to `PATCH /me/onboarding`. "Skip the rest and continue" saves immediately, as the old single "Continue" did. |
| Today | Adaptive banner (resume, next concept, roadmap ready, add subject) with one primary action and a coach card. |
| Diagnostic | Progress bar, styled confidence chips with a visible selected state, answer tiles, branded result card. |
| Session | Step bar in the header; `alert()` and `confirm()` replaced with an in-page error box and a dialog. |
| Subject tabs | Pill tabs with an active state. |
| Copy | Internal terms and build-milestone codes (M3, M4, M5, M7) removed from what students see. |

## Fixed bugs

- `input`, `badge`, `bg-surface-subtle` and `border-accent` were used but not defined, so the onboarding and diagnostic fields were unstyled and the chosen confidence level was barely visible.
- Color opacity classes such as `bg-ink/40` don't work with CSS-variable colors in Tailwind 3; replaced with explicit values.

## Not verified

The redesign was written without `node_modules`, so `npm run build`, lint and the Playwright tests have not been run. Every file passes a TypeScript syntax check. The e2e onboarding step clicks the button named "Continue", which now matches "Skip the rest and continue".
