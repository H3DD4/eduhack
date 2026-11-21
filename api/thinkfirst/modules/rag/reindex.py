"""(Re)build the Qdrant collections from Postgres — run after adding HF_TOKEN or switching embedding model.

    python -m thinkfirst.modules.rag.reindex

Runs with MIGRATION_DATABASE_URL when set (the owner role can read every student's chunks to index them; the
search side still filters by owner_id + subject_id).
"""

from __future__ import annotations

import os

from sqlalchemy import select

from thinkfirst.core.db import configure, session_factory
from thinkfirst.modules.rag import service as rag


def main() -> None:
    configure(os.environ.get("MIGRATION_DATABASE_URL") or None)
    import thinkfirst.models  # noqa: F401
    from thinkfirst.modules.rag.ingestion.models import SourceChunk
    from thinkfirst.modules.rag.library.models import LicensedContent, SharedChunk

    if not rag.qdrant_active():
        raise SystemExit("Qdrant is not reachable (set QDRANT_URL and start the qdrant service).")
    print("stack:", rag.stack())
    with session_factory()() as db:
        chunks = list(db.scalars(select(SourceChunk)).all())
        n_course = sum(rag.index_course_chunks(db, chunks[i:i + 64]) for i in range(0, len(chunks), 64))
        n_lib = 0
        for item in db.scalars(select(LicensedContent)).all():
            rows = list(db.scalars(select(SharedChunk).where(SharedChunk.licensed_content_id == item.id)).all())
            n_lib += rag.index_library_chunks(db, item, rows)
    print(f"indexed {n_course}/{len(chunks)} course chunks and {n_lib} open-library chunks")


if __name__ == "__main__":
    main()
