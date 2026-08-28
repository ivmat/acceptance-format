#!/usr/bin/env python3
"""m11.py — the shared M11 content-hashing helper (spec/format.md, "Content-hashing (M11)",
ratified 2026-08-28).

Pure stdlib, no dependencies. Domain-separated SHA-512 over the RAW bytes of a file as emitted:

    digest = sha512(prefix_bytes || file_bytes)
    wire value = "sha-512:" + hex(digest)          # self-describing, lower-case hex, 128 chars

`prefix_bytes` is the UTF-8 bytes of the literal domain-separator string, including its trailing
colon, concatenated directly onto the file bytes with no added delimiter. Exactly ONE canonical
algorithm is defined per format revision (ratified 2026-08-28: SHA-512, superseding an earlier
sha-256 draft that was never published) — this module hard-codes that one algorithm; there is no
per-call or per-manifest choice to make, by design (a per-manifest choice would be a downgrade
attack and would split content identity across manifests hashed under different algorithms).

Imported by `tools/check_acceptance.py` (manifest-side `record_hash`/`subject_hash` checks) and
`tools/check_execute.py` (P9's record-binding check, `--execute` mode).

`subject` domain (added 2026-08-28, post-ratification, under the ratification's own
additive-separator rule — format.md "`subject:` domain"): the M11 hash `[subject].subject_hash` /
`[[claim.evidence]].subject_hash` (design rule 4a) refer to. This module computes the single-file
case (`digest_file("subject", path)`, no different from `manifest`/`evidence-record`); the
multi-file (bundle-root-over-the-subject-tree) case's concrete pre-hash serialization is PENDING
the same P12 canonical-emit work `bundle-root` itself is deferred to (format.md), so it is not
implemented here.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ALGORITHM = "sha-512"

# The five M11 domain-separator prefixes (format.md, "Content-hashing (M11)" +
# "`subject:` domain"). `claim` is RESERVED — not computed in this revision ("Reserved hooks" H3,
# the per-claim signing slot). Listed here so the reservation has one source of truth; nothing in
# this module computes under it (digest_bytes/digest_file both refuse it, below).
PREFIXES: dict[str, bytes] = {
    "manifest": b"manifest:",
    "bundle-root": b"bundle-root:",
    "evidence-record": b"evidence-record:",
    "claim": b"claim:",  # RESERVED — see module docstring
    "subject": b"subject:",  # added post-ratification, additive-separator rule — see module docstring
}

_RESERVED_DOMAINS = {"claim"}

_HEXDIGITS = set("0123456789abcdef")


def digest_bytes(domain: str, data: bytes) -> str:
    """Return the self-describing M11 digest of `data`, domain-separated by `domain`'s prefix.

    Raises ValueError if `domain` is not one of PREFIXES' keys, or is a RESERVED domain (`claim`
    is reserved, not computed in this revision — calling this with "claim" is a caller bug, not a
    normal validator path)."""
    if domain not in PREFIXES:
        raise ValueError(f"m11: unknown hash domain {domain!r} (known: {sorted(PREFIXES)})")
    if domain in _RESERVED_DOMAINS:
        raise ValueError(
            f"m11: domain {domain!r} is RESERVED, not computed in this revision "
            f"(format.md 'Reserved hooks' H3)"
        )
    h = hashlib.sha512(PREFIXES[domain] + data).hexdigest()
    return f"{ALGORITHM}:{h}"


def digest_file(domain: str, path: str | Path) -> str:
    """digest_bytes over a file's raw bytes as emitted — no decoding, no re-serialization, no
    canonicalization. A hand-edited file simply gets a new identity (format.md, by design)."""
    return digest_bytes(domain, Path(path).read_bytes())


def is_well_formed(value) -> bool:
    """Shape check only: `"sha-512:" + 128 lower-case hex chars`, exactly. Does not verify
    anything against a file's actual bytes — callers that need that call digest_file/digest_bytes
    and compare the result against `value` themselves."""
    if not isinstance(value, str):
        return False
    prefix = f"{ALGORITHM}:"
    if not value.startswith(prefix):
        return False
    hexpart = value[len(prefix):]
    return len(hexpart) == 128 and all(c in _HEXDIGITS for c in hexpart)


# --------------------------------------------------------------------------
# CLI (walkthrough C1: this module was import-only — `python3 tools/m11.py <file>` ran, printed
# nothing, and exited 0, a silent no-op that looked like success. A manifest author has no other
# way to compute `record_hash` (evidence-types.md) than this module, so a no-op here is the single
# biggest blocker to writing a first weighted claim.)
# --------------------------------------------------------------------------

_COMPUTABLE_DOMAINS = sorted(d for d in PREFIXES if d not in _RESERVED_DOMAINS)


def _print_usage(f=sys.stderr) -> None:
    print("usage: m11.py DOMAIN FILE       print the self-describing M11 digest of FILE under DOMAIN", file=f)
    print("       m11.py --selftest        run embedded self-checks", file=f)
    print("       m11.py --help            show this help", file=f)
    print(f"valid domains: {', '.join(_COMPUTABLE_DOMAINS)}", file=f)
    print(f"reserved, not computed (format.md 'Reserved hooks' H3): {', '.join(sorted(_RESERVED_DOMAINS))}",
          file=f)


def _selftest() -> int:
    """Embedded self-checks: the library functions AND the CLI (via subprocess, exercising this
    exact file as `__main__`) — including the no-args case (walkthrough C1: this must never be a
    silent, zero-exit success)."""
    import subprocess
    import tempfile

    checks = 0
    failures: list[str] = []

    def check(desc: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(desc)

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "f.txt"
        p.write_bytes(b"hello world")

        want = digest_bytes("evidence-record", b"hello world")
        check("digest_file matches digest_bytes over the same content", digest_file("evidence-record", p) == want)
        check("is_well_formed accepts a real digest", is_well_formed(want))
        check("is_well_formed rejects a wrong-algorithm value", not is_well_formed("sha-256:" + "a" * 64))
        try:
            digest_bytes("claim", b"x")
            check("digest_bytes refuses the RESERVED 'claim' domain", False)
        except ValueError:
            check("digest_bytes refuses the RESERVED 'claim' domain", True)

        proc = subprocess.run([sys.executable, __file__, "evidence-record", str(p)],
                               capture_output=True, text=True)
        check("CLI 'evidence-record <file>' exits 0 and prints the digest",
              proc.returncode == 0 and proc.stdout.strip() == want)

        proc = subprocess.run([sys.executable, __file__], capture_output=True, text=True)
        check("CLI with NO ARGS exits nonzero and prints nothing to stdout (never a silent success)",
              proc.returncode != 0 and proc.stdout == "")

        proc = subprocess.run([sys.executable, __file__, "--help"], capture_output=True, text=True)
        check("CLI --help exits 0 and lists the valid domains",
              proc.returncode == 0 and all(d in proc.stdout for d in _COMPUTABLE_DOMAINS))

        proc = subprocess.run([sys.executable, __file__, "bogus-domain", str(p)],
                               capture_output=True, text=True)
        check("CLI with an unknown domain exits nonzero", proc.returncode != 0)

        proc = subprocess.run([sys.executable, __file__, "claim", str(p)], capture_output=True, text=True)
        check("CLI with the RESERVED 'claim' domain exits nonzero", proc.returncode != 0)

        proc = subprocess.run([sys.executable, __file__, "evidence-record", str(Path(td) / "missing.txt")],
                               capture_output=True, text=True)
        check("CLI on a missing file exits nonzero", proc.returncode != 0)

    if failures:
        for f in failures:
            print(f"SELFTEST FAIL: {f}", file=sys.stderr)
        print(f"SELFTEST FAILED: {len(failures)}/{checks} checks", file=sys.stderr)
        return 1

    print(f"SELFTEST PASS: {checks} checks")
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args:
        _print_usage()
        return 2
    if args == ["--help"]:
        _print_usage(sys.stdout)
        return 0
    if args == ["--selftest"]:
        return _selftest()
    if len(args) != 2:
        print(f"usage error: expected DOMAIN FILE, got {len(args)} argument(s)", file=sys.stderr)
        _print_usage()
        return 2

    domain, path = args
    if domain not in PREFIXES:
        print(f"error: unknown hash domain {domain!r} (known: {', '.join(_COMPUTABLE_DOMAINS)})",
              file=sys.stderr)
        return 2
    if domain in _RESERVED_DOMAINS:
        print(f"error: domain {domain!r} is RESERVED, not computed in this revision "
              f"(format.md 'Reserved hooks' H3)", file=sys.stderr)
        return 2

    p = Path(path)
    if not p.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 2

    print(digest_file(domain, p))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
