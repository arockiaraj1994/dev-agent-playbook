#!/usr/bin/env python3
"""
dev.py — one-shot dev runner.

  uv run dev.py            # regen INDEX.md → validate → start server
  uv run dev.py --no-regen # skip regen, validate, start server
  uv run dev.py --no-check # skip validation (warns), start server
  uv run dev.py --no-serve # regen + validate, then exit (good for pre-commit)

Validation is delegated to scripts/validate-rules.py (the same script CI
runs). The server is invoked in-process via server.main(), so SIGINT
propagates cleanly to uvicorn.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MCP_DIR.parent
_VALIDATOR = _REPO_ROOT / "scripts" / "validate-rules.py"


def _banner(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def _ok(msg: str) -> None:
    print(f"\033[32m✓\033[0m {msg}", flush=True)


def _fail(msg: str) -> None:
    print(f"\033[31m✗\033[0m {msg}", file=sys.stderr, flush=True)


def _run_validator(*flags: str) -> int:
    return subprocess.run(
        [sys.executable, str(_VALIDATOR), *flags],
        cwd=_REPO_ROOT,
        check=False,
    ).returncode


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-regen", action="store_true",
        help="Skip the INDEX.md regeneration step.",
    )
    parser.add_argument(
        "--no-check", action="store_true",
        help="Skip the validator (will WARN — server may load a broken corpus).",
    )
    parser.add_argument(
        "--no-serve", action="store_true",
        help="Run regen + check, then exit. The MCP server is not started.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if not _VALIDATOR.is_file():
        _fail(f"Validator not found at {_VALIDATOR}")
        return 2

    if not args.no_regen:
        _banner("Regenerating INDEX.md…")
        rc = _run_validator("--regen-index")
        if rc != 0:
            _fail(f"INDEX regeneration failed (exit {rc}). Server not started.")
            return rc
        _ok("INDEX.md regenerated")

    if not args.no_check:
        _banner("Validating rule corpus…")
        rc = _run_validator("--check")
        if rc != 0:
            _fail("Server not started — fix the errors above and re-run.")
            return rc
        _ok("Validation passed")
    else:
        print("⚠  Skipping validation (--no-check). The server may load a broken corpus.",
              file=sys.stderr, flush=True)

    if args.no_serve:
        _ok("Done (--no-serve set; not starting the MCP server).")
        return 0

    _banner("Starting MCP server…")
    # Imported lazily so --no-serve users don't pay startup cost.
    import server
    server.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
