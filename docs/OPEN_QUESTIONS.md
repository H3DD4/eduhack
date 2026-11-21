# Open questions (privacy, permissions, licensing, destructive data)

Per the ambiguity policy, each item ships with the **safest restrictive behaviour** until a coordinator decides.

| ID | Question | Restrictive behaviour implemented now |
|---|---|---|
| Q-01 | Jurisdiction/legal basis for storing raw audio and transcripts; is a 7-day replay option acceptable? | Raw audio deleted at transcript confirmation by default; replay is opt-in and capped at 7 days from upload (unconfirmed uploads share the cap); purge job + lazy purge on read. |
| Q-02 | Minor students (under-18) handling. | No age-specific flows; no extra data collected; no marketing/analytics; no training on any student data. |
| Q-03 | Admin operating model (who may request access, approval process, admin UI). | Admins have no default access; `admin_access_check` requires an active, scoped, purpose-specific, expiring, revocable consent and audits every attempt (granted or denied). No admin routes are exposed in this run. |
| Q-04 | Rights flow for contributed past exams/exercise sheets. | Contributions model exists; `can_share` is false unless an explicit rights declaration **and** admin approval exist; no sharing path is built; uploads remain private. |
| Q-05 | Approved AI processors for production (data-processing agreements, retention, region). The user supplied Gemini and Groq keys for this local build. | Keys only in git-ignored `api/.env`. Only confirmed text goes to LLMs; raw audio goes only to the chosen STT processor and only when `STT_PROVIDER` is explicitly set; the UI names recipients before capture; logs are metadata-only. `.env.example` defaults to labelled demo adapters. **Production use needs a decision.** |
| Q-06 | Real quota sizes, bundle costs and pricing. | Mock provider, 30 units/period, no prices shown anywhere, no payment UI. |
| Q-07 | Backup/processor deletion guarantees for "Delete attempt"/"Delete audio". | Deletion removes content in the primary DB and object storage; the UI states that backups and processor copies are **not** covered in this build. |
| Q-08 | Full account deletion and data export semantics. | Not implemented; Settings says so (no false deletion claims). |
| Q-09 | Who verifies uploaded exercises to make them `verified-source`. | Uploads are always `unverified-source`; generated items `ai-generated`; nothing is auto-verified. |
| Q-10 | Disputes: what reviewer sees. | Disputes are M3; flagging will never share content automatically (separate consent), per override §3.9. |
| Q-11 | Demo transcription fixture: acceptable for a public demo? | It is labelled "Demo transcription (simulated) … this fixture text stands in for your recording. Edit it to match what you actually said." |
| Q-12 | Topic text and concept names are sent to Wikipedia's API to find open content (no identity, no student answers). Acceptable for production? | Only topic/concept names are sent; generic User-Agent without personal data; can be disabled with `RESOURCE_DISCOVERY=false`. |
| Q-13 | Governance of the shared open library (removal requests, licence updates, quality review, languages). | Only CC BY-SA Wikipedia text is stored; licence, URL and attribution kept per item; content labelled "unverified source"; no student data in the shared tables (no RLS needed there). |
| Q-14 | AI-generated packs/rubrics are not reviewed by domain experts. | Every pack, rubric and generated item is labelled AI-generated / not domain-approved; uncertain grading is unscored. |
| Q-15 | Course chunk text (from student uploads) is sent to Hugging Face Inference to compute embeddings. Approved processor for production? | Only when `HF_TOKEN` is set; only chunk text (no identity, no answers); vectors stored in our own Qdrant; disable with `EMBEDDING_PROVIDER=demo`. Upload screen should name the processor (to add with the UI rework). |
