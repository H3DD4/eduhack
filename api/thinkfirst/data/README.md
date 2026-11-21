# data — the stores from the diagram

Not process modules: they **store** what the 4 modules produce and read.

| Folder | Diagram box | What it stores |
|---|---|---|
| `student_profile/` | Profil élève (PostgreSQL) | Evidence receipts per concept (Introduced → Practised with support → Explained back → Applied independently → Recalled later), review dates, progress counts. Filled by the `assessment.accepted` event. |
| `memory/` | Historique & mémoire | Append-only history of answers, errors, misconceptions, hints used. Filled by events; read by `modules/adaptation`. |

The vector database (Base vectorielle) lives in `modules/rag/vector_store.py`.
