# data — the stores from the diagram

Not process modules: they **store** what the 4 modules produce and read.

| Folder | Diagram box | What it stores |
|---|---|---|
| `student_profile/` | Profil élève (PostgreSQL) | Evidence receipts per concept (Introduced → Practised with support → Explained back → Applied independently → Recalled later), review dates, per-skill BKT/Elo mastery (`skill_mastery`), and calibrated diagnostic initial profiles (`initial_profiles`). Filled by `assessment.accepted` and `diagnostic.completed`; publishes `mastery.updated` and `profile.ready`. |
| `memory/` | Historique & mémoire | Append-only learning timeline (`learning_events`), pseudonymous consent-redacted xAPI behavioral events (`behavioral_events`), and Layer 3 derived learning-analytics indicators (`behavior_indicators`). Publishes `indicator.updated`; read by `modules/adaptation` and `modules/diagnostic`. |

The vector database (Base vectorielle) lives in `modules/rag/qdrant.py` (Qdrant + Hugging Face multilingual embedder) with fallback in `modules/rag/vector_store.py`. Pure mastery and tracking algorithms live in `domain/mastery/` and `domain/tracking/`.
