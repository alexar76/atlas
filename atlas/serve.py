"""CLI entry points for the ATLAS map server."""

from __future__ import annotations

import argparse
import os


def main(argv: list[str] | None = None) -> None:
    """Run ATLAS (uvicorn) — `atlas` / `atlas-serve` console scripts."""
    parser = argparse.ArgumentParser(prog="atlas", description="ATLAS physical sensor map over GAIA")
    parser.add_argument("--host", default=os.environ.get("ATLAS_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ATLAS_PORT", "9330")))
    parser.add_argument("--reload", action="store_true", help="Dev auto-reload")
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(
        "atlas.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=1,
        limit_concurrency=200,
        timeout_keep_alive=30,
    )


if __name__ == "__main__":
    main()
