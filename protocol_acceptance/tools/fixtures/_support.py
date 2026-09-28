"""fixtures/_support.py — shared helpers every per-profile selftest chain module uses.

Profile-neutral: nothing here names a profile, a grade, a band or a tool. Pulled out once (revision)
so each chain module (`verification_chain.py`, `conformance_chain.py`, `troubleshooting_chain.py`,
...) shares one `Cases` collector and one temp-file writer instead of redefining its own.
"""
from __future__ import annotations

from pathlib import Path


class Cases:
    """Collects `(name, ok, detail)` selftest results. Mirrors `acceptance_protocol.Reporter`'s
    shape closely enough that callers can pass a Reporter's `.ok()`/`.errors` straight through."""

    def __init__(self):
        self.items: list[tuple[str, bool, object]] = []

    def check(self, name: str, ok: bool, detail=None) -> None:
        self.items.append((name, ok, detail))

    def expect_fail(self, name: str, rep, needle: str | None = None) -> None:
        ok = not rep.ok() and (needle is None or any(needle in e for e in rep.errors))
        self.items.append((name, ok, rep.errors))


def write(td: Path, name: str, text: str) -> Path:
    p = td / name
    p.write_text(text, encoding="utf-8")
    return p
