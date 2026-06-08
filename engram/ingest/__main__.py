"""CLI: python -m engram.ingest owner/name [owner/name ...]"""

import sys

from ..db import connect, init_schema
from .pipeline import ingest_repo


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m engram.ingest owner/name [owner/name ...]", file=sys.stderr)
        return 2
    with connect() as conn:
        init_schema(conn)
        for slug in argv:
            print(f"indexing {slug} ...", flush=True)
            r = ingest_repo(slug, conn)
            print(f"  sha={r.sha[:8]} files={r.files_indexed} "
                  f"chunks+={r.chunks_inserted} unchanged={r.files_skipped_unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
