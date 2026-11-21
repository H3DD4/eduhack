# platform — support services (not a team focus)

| Folder | What it does |
|---|---|
| `identity/` | Accounts, login, settings, 10-step onboarding (`profile.seeded`, `goal.set`), birth-year age gate (`age.gated`), 4-tier behavioral tracking consent & minors gating (`student_consents`, `consent.updated`), admin consent + access log |
| `billing/` | Usage allowance (mock, no real payments); reserves the AI checks before a session starts |
| `workspaces/` | Subjects (courses, `workspace.created`); its router also serves the roadmap, setup and resources endpoints |

Shared plumbing (database, events + SysBrain event contracts, background jobs, storage, errors) is in `../core/`. Pure consent-tier rules live in `../domain/consent/`.
