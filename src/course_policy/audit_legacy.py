"""CLI entry point for the legacy workbook audit."""

from __future__ import annotations

from .legacy_audit import main


if __name__ == "__main__":
    raise SystemExit(main())
