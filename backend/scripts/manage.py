"""Database management commands.

    python -m scripts.manage init      # create tables (idempotent)
    python -m scripts.manage seed      # create tables + insert any missing demo businesses (idempotent)
    python -m scripts.manage reset     # delete everything and restore the original demo data
    python -m scripts.manage samples   # regenerate the sample CSV files in data/samples/
    python -m scripts.manage schema    # print PostgreSQL DDL (for Supabase SQL editor)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, backend_label  # noqa: E402
from app.services.seed import init_db, reset_demo, seed_demo, write_sample_files  # noqa: E402


def postgres_ddl() -> str:
    out = ["-- CrediPath schema (generated from app/models.py). Run in the Supabase SQL editor if you prefer", "-- to create tables manually; the API also creates them automatically on startup.", ""]
    for table in Base.metadata.sorted_tables:
        out.append(str(CreateTable(table).compile(dialect=postgresql.dialect())).strip() + ";")
        for idx in table.indexes:
            out.append(str(CreateIndex(idx).compile(dialect=postgresql.dialect())).strip() + ";")
        out.append("")
    return "\n".join(out)


def main(cmd: str) -> None:
    if cmd == "schema":
        print(postgres_ddl())
        return
    if cmd == "samples":
        print("Wrote:", ", ".join(write_sample_files()))
        return
    print(f"Database: {backend_label()}")
    init_db()
    if cmd == "init":
        print("Tables ready.")
        return
    with SessionLocal() as db:
        if cmd == "seed":
            created = seed_demo(db)
            print("Seeded:", ", ".join(created) if created else "nothing new (demo data already present)")
        elif cmd == "reset":
            created = reset_demo(db)
            print("Restored demo data:", ", ".join(created))
        else:
            raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
