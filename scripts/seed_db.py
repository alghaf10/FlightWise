"""Initialize SQLite tables and populate demo roster."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session

from app.db import engine, init_db
from app.seed_demo import populate_demo_database


def main() -> None:
    init_db()
    with Session(engine) as session:
        counts = populate_demo_database(session, truncate=True)
    print("FlightWise seed:", counts)


if __name__ == "__main__":
    main()
