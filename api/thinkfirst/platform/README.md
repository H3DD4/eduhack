# platform — support services (not a team focus)

| Folder | What it does |
|---|---|
| `identity/` | Accounts, login, settings, admin consent + access log |
| `billing/` | Usage allowance (mock, no real payments); reserves the AI checks before a session starts |
| `workspaces/` | Subjects (courses); its router also serves the roadmap, setup and resources endpoints |

Shared plumbing (database, events, background jobs, storage, errors) is in `../core/`.
