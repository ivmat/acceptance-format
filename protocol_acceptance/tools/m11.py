#!/usr/bin/env python3
"""m11.py — the shared M11 content-hashing helper (spec/format.md, "Content-hashing (M11)",
ratified 2026-08-28).

COPIED from the acceptance-format product repository's `tools/m11.py` @ git sha
aeac93f22f15f72d787970135d61ac97e19f4a8a (2026-08-28), and EXTENDED here for the acceptance
protocol (`protocol_acceptance/spec/protocol.md` §7): two new domain-separator prefixes, `contract:` (the
contract hash) and `decision:` (the decision hash), added under the ratified construction's own
additive-separator rule (new prefixes may be added; no existing prefix's meaning changes). The
`manifest:` domain is unchanged and is the package hash; `subject:` is used for per-file input
digests (`[[claim.evidence.inputs]]`, protocol.md §4/§8) and now writes the self-describing form
too (2026-09-24 — see the revision L3 note below). `normative-reference:`
is exposed here for `[policy].hash` (protocol.md §3): it was already a registered
`hashdomains.DOMAINS` entry (the format core's own governing-document domain), just not
previously reachable through this module's own PREFIXES. Everything else in this
file is verbatim from the public copy — do not hand-diverge it; re-copy and re-extend instead.

Revision L2 (2026-09-24, core.md B16): this module no longer defines its own hash construction. Every
domain name it uses is registered in `format_acceptance/tools/hashdomains.py` (the single B16
registry: format core's five domains plus the five added there for this module), and this module
calls `hashdomains` for the shared `sha512(prefix || bytes)` construction instead of hashing
locally.

Revision L3 (2026-09-24, "one wire form"): `contract`, `decision` and
`manifest` now use `hashdomains.digest`'s self-describing wire form, `<domain>:sha-512:<hex>` —
the SAME form the format core writes for its own five domains — instead of this module's earlier
own wire form. `bundle-root` and `claim` are UNCHANGED (unwritten/reserved). `evidence-record`'s
bare form is the pre-existing "untyped legacy" wire `hash-domains.md`'s Read-only legacy record
wires section already tracks for retirement at conformance 0.2 — out of revision L3's narrower
contract/package/decision scope, and still out of scope below (a claim's OWN evidence
`record_hash`, not a change-impact input digest). A bare `sha-512:<hex>` value read back from a
`contract`/`manifest`/`decision`-domain field is no longer valid input for those three fields;
callers reject it explicitly (`acceptance_protocol.py`, no compatibility shim with pre-lock
drafts, decision L).

As of 2026-09-24, `subject` now ALSO writes the self-describing
`subject:sha-512:<hex>` form, matching the format core's own convention for this domain (B1
certified subject identity already writes it self-describing; only this module's own
`[[claim.evidence.inputs]]` computation lagged) — `acceptance_protocol.py` rejects the retired
bare form on that field the same way it does for contract/package/decision.

Pure stdlib, no dependencies. Domain-separated SHA-512 over the RAW bytes of a file as emitted:

    digest = sha512(prefix_bytes || file_bytes)
    # self-describing domains (contract, decision, manifest — revision L3):
    wire value = prefix + "sha-512:" + hex(digest)     # e.g. "contract:sha-512:<128-hex>"
    # legacy domains (bundle-root, evidence-record, claim — unchanged):
    wire value = "sha-512:" + hex(digest)              # domain not repeated in the wire string

`prefix_bytes` is the UTF-8 bytes of the literal domain-separator string, including its trailing
colon, concatenated directly onto the file bytes with no added delimiter. Exactly ONE canonical
algorithm is defined per format revision (ratified 2026-08-28: SHA-512, superseding an earlier
sha-256 draft that was never published) — this module hard-codes that one algorithm; there is no
per-call or per-manifest choice to make, by design (a per-manifest choice would be a downgrade
attack and would split content identity across manifests hashed under different algorithms).

Imported by `protocol_acceptance/tools/acceptance_protocol.py` (contract/package/decision hash checks).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# append, not insert(0): format_acceptance/tools/profiles/ is a PACKAGE named "profiles" that
# would shadow protocol_acceptance/tools/profiles.py (imported right after this module by
# acceptance_protocol.py) if placed ahead of it on sys.path. hashdomains is a unique name, so
# appending still finds it, without reordering resolution for any name this module's importers use.
sys.path.append(str(_HERE.parent.parent / "format_acceptance" / "tools"))  # hashdomains (B16)

import hashdomains  # noqa: E402

ALGORITHM = "sha-512"

# The M11 domain-separator prefixes. `manifest`, `bundle-root`, `evidence-record`, `claim` and
# `subject` are the public format's own (format.md, "Content-hashing (M11)" + "`subject:`
# domain"); `claim` is RESERVED — not computed in this revision ("Reserved hooks" H3, the
# per-claim signing slot). `contract` and `decision` are the protocol's own additions
# (protocol.md §7), added under the ratified construction's additive-separator rule.
# `normative-reference` (as of 2026-09-24) is a format-core domain this
# module now ALSO exposes, for `[policy].hash` (protocol.md §3) — the policy document is a
# governing document over which the consumer states a standing acceptance policy, exactly the
# domain's existing meaning at the format core (`hash-domains.md`: "shared construction over the
# governing document bytes"); no new domain was registered (`hashdomains.DOMAINS` already carries
# it) — this module only widens which of the registry's domains it re-exposes.
#
# Revision L2: the domain NAMES and their hash CONSTRUCTION now live in `hashdomains.DOMAINS`
# (format_acceptance/tools/hashdomains.py, core.md B16) — this dict only re-derives the byte
# prefixes this module's own callers key on; it is a thin, non-authoritative mirror.
_M11_DOMAIN_NAMES = (
    "manifest", "bundle-root", "evidence-record", "claim", "subject", "contract", "decision",
    "normative-reference",
)
for _name in _M11_DOMAIN_NAMES:
    if f"{_name}:" not in hashdomains.DOMAINS:
        raise RuntimeError(f"m11: domain {_name!r} is missing from hashdomains.DOMAINS (B16 registry)")
PREFIXES: dict[str, bytes] = {_name: f"{_name}:".encode("ascii") for _name in _M11_DOMAIN_NAMES}
del _name

_RESERVED_DOMAINS = {"claim"}

# Revision L3 (2026-09-24, "one wire form"): these domains write the
# self-describing `<domain>:sha-512:<hex>` wire form (`hashdomains.digest`), matching the format
# core's own convention, instead of this module's earlier bare `sha-512:<hex>` form. `subject`
# (`[[claim.evidence.inputs]]` digests) and `normative-reference` (`[policy].hash`) join
# `contract`/`decision`/`manifest` (revision L3) here. The remaining domains (`bundle-root`,
# `evidence-record`, `claim`) are UNCHANGED — see the module docstring and `hash-domains.md`'s
# See the revision L3 note for why (a claim's own `record_hash` is separately tracked legacy).
_SELF_DESCRIBING_DOMAINS = {"contract", "decision", "manifest", "subject", "normative-reference"}

_HEXDIGITS = set("0123456789abcdef")


def digest_bytes(domain: str, data: bytes) -> str:
    """Return the M11 digest of `data`, domain-separated by `domain`'s prefix — the
    self-describing `<domain>:sha-512:<hex>` wire form for `contract`/`decision`/`manifest`
    (revision L3), the legacy bare `sha-512:<hex>` form (domain baked into the hash bytes, not repeated
    in the wire string) for every other domain this module computes.

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
    if domain in _SELF_DESCRIBING_DOMAINS:
        return hashdomains.digest(f"{domain}:", data)
    h = hashdomains.digest_hex(f"{domain}:", data)
    return f"{ALGORITHM}:{h}"


def digest_file(domain: str, path: str | Path) -> str:
    """digest_bytes over a file's raw bytes as emitted — no decoding, no re-serialization, no
    canonicalization. A hand-edited file simply gets a new identity (format.md, by design)."""
    return digest_bytes(domain, Path(path).read_bytes())


def is_well_formed(value) -> bool:
    """Shape check only, EITHER wire form this module produces (revision L3): the legacy bare
    `"sha-512:" + 128 lower-case hex chars` (still written for `bundle-root`/`evidence-record`/
    `claim`/`subject`), or the self-describing `<domain>:sha-512:<128-hex>` form
    (`hashdomains.parse`; written for `contract`/`decision`/`manifest`). Does not verify anything
    against a file's actual bytes — callers that need that call digest_file/digest_bytes and
    compare the result against `value` themselves."""
    if not isinstance(value, str):
        return False
    prefix = f"{ALGORITHM}:"
    if value.startswith(prefix):
        hexpart = value[len(prefix):]
        return len(hexpart) == 128 and all(c in _HEXDIGITS for c in hexpart)
    try:
        hashdomains.parse(value)
        return True
    except ValueError:
        return False


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
    silent, zero-exit success). Extended with the two protocol domains."""
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

        # protocol domains (added over the public copy)
        want_contract = digest_bytes("contract", b"hello world")
        want_decision = digest_bytes("decision", b"hello world")
        want_manifest = digest_bytes("manifest", b"hello world")
        check("digest_file('contract', ...) matches digest_bytes", digest_file("contract", p) == want_contract)
        check("digest_file('decision', ...) matches digest_bytes", digest_file("decision", p) == want_decision)
        check("contract and decision domains produce DIFFERENT digests over the same bytes",
              want_contract != want_decision and want_contract != want and want_decision != want)

        # Revision L3 "one wire form": contract/decision/manifest are now self-describing
        # (`<domain>:sha-512:<hex>`), matching `hashdomains.digest`'s own output exactly; the
        # unmigrated domains (evidence-record here) keep the bare `sha-512:<hex>` legacy form.
        check("contract digest uses the self-describing 'contract:sha-512:' wire form (revision L3)",
              want_contract.startswith("contract:sha-512:"))
        check("decision digest uses the self-describing 'decision:sha-512:' wire form (revision L3)",
              want_decision.startswith("decision:sha-512:"))
        check("manifest digest uses the self-describing 'manifest:sha-512:' wire form (revision L3)",
              want_manifest.startswith("manifest:sha-512:"))
        check("contract digest equals hashdomains.digest('contract:', ...) exactly (one wire form)",
              want_contract == hashdomains.digest("contract:", b"hello world"))
        check("evidence-record digest is UNCHANGED, still the bare legacy wire form (out of revision L3 scope)",
              want.startswith("sha-512:") and not want.startswith("evidence-record:"))
        check("is_well_formed accepts the self-describing wire form too (revision L3)", is_well_formed(want_contract))
        check("is_well_formed still accepts the bare legacy form (domain-agnostic shape check; a "
              "domain-specific rejection of the bare form for contract/decision/manifest fields is "
              "acceptance_protocol.py's job, not this shape check's)", is_well_formed(want))

        # As of 2026-09-24, `subject` (§4/§8 change-impact inputs) and
        # `normative-reference` (§3 [policy].hash) join the self-describing set.
        want_subject = digest_bytes("subject", b"hello world")
        want_normref = digest_bytes("normative-reference", b"hello world")
        check("subject digest uses the self-describing 'subject:sha-512:' wire form",
              want_subject.startswith("subject:sha-512:"))
        check("normative-reference digest uses the self-describing 'normative-reference:sha-512:' "
              "wire form", want_normref.startswith("normative-reference:sha-512:"))
        check("subject digest equals hashdomains.digest('subject:', ...) exactly (one wire form)",
              want_subject == hashdomains.digest("subject:", b"hello world"))
        check("normative-reference digest equals hashdomains.digest('normative-reference:', ...) "
              "exactly (one wire form)",
              want_normref == hashdomains.digest("normative-reference:", b"hello world"))
        check("digest_file('subject', ...) matches digest_bytes", digest_file("subject", p) == want_subject)
        check("digest_file('normative-reference', ...) matches digest_bytes",
              digest_file("normative-reference", p) == want_normref)

        proc = subprocess.run([sys.executable, __file__, "evidence-record", str(p)],
                               capture_output=True, text=True)
        check("CLI 'evidence-record <file>' exits 0 and prints the digest",
              proc.returncode == 0 and proc.stdout.strip() == want)

        proc = subprocess.run([sys.executable, __file__, "contract", str(p)],
                               capture_output=True, text=True)
        check("CLI 'contract <file>' exits 0 and prints the digest",
              proc.returncode == 0 and proc.stdout.strip() == want_contract)

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
