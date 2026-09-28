#!/usr/bin/env python3
"""Domain-separated SHA-512 wire digests for acceptance/0 — THE single hash-domain registry
(core.md B16). Core, conformance, the F2 helper and `protocol_acceptance/tools/m11.py` all import
this module for the domain set and the shared construction; none of them may keep a private copy.

`DOMAINS` holds three groups: the seven B16-mandated format-core domains (`normative-reference:`,
`manifest:`, `applicability-record:`, `subject:`, `record:`, `inventory:`, `artifact:`, documented
with their wire form and writer/verifier in spec/hash-domains.md) plus five domains added here for
`m11.py`'s own registry (`bundle-root:`, `evidence-record:`, `claim:` — reserved, not computed by
m11 in this revision — `contract:`, `decision:`; protocol.md §7's additive-separator rule).
`manifest:` and `subject:` are shared by name and construction across both groups. Adding a domain
is an edit to this set (B16, "Adding a domain")."""
import hashlib
import re
import sys
from pathlib import Path

DOMAINS = {
    "normative-reference:", "manifest:", "applicability-record:", "subject:", "record:",
    "inventory:", "artifact:",
    "bundle-root:", "evidence-record:", "claim:", "contract:", "decision:",
}

# core.md B16: the registry TABLE in spec/hash-domains.md is
# the authoritative enumeration, not a second prose list repeated in core.md's own RULE text —
# avoiding a "which list wins" drift between the two. This module's `DOMAINS` set MUST agree with
# that table exactly; `registry_prefixes_from_markdown` + `registry_agreement_diff` below are the
# mechanical check, run by `selftest()` and by `gates/check_formats_selftests.py`'s discovery.
_HASH_DOMAINS_MD = Path(__file__).resolve().parent.parent / "spec" / "hash-domains.md"
_TABLE_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z-]*:)`\s*\|", re.MULTILINE)


def registry_prefixes_from_markdown(text: str) -> set[str]:
    """Every registered domain prefix cited as a first-column, backtick-quoted table cell across
    BOTH of hash-domains.md's registry tables (the format-core table and the protocol-folded
    table) — the authoritative source B16 points to."""
    return set(_TABLE_ROW_RE.findall(text))


def registry_agreement_diff(markdown_text: str | None = None) -> tuple[set[str], set[str]]:
    """`(missing_from_table, missing_from_domains)` — both empty means the registry table and
    `DOMAINS` agree exactly. `markdown_text` defaults to reading `spec/hash-domains.md` beside this
    module; a caller MAY pass synthetic text (the able-to-fail selftest control below does)."""
    text = markdown_text if markdown_text is not None else _HASH_DOMAINS_MD.read_text(encoding="utf-8")
    table = registry_prefixes_from_markdown(text)
    return DOMAINS - table, table - DOMAINS


def digest_hex(domain: str, data: bytes) -> str:
    """The bare hex digest for a registered domain, via the shared construction
    `sha512(prefix || bytes)`. This is the primitive `digest()` below builds its self-describing
    wire form on, and the one `m11.py` calls to build its OWN wire form (`sha-512:<hex>`, domain
    baked into the hash bytes but not repeated in the wire string)."""
    if domain not in DOMAINS:
        raise ValueError(f"B16: unregistered hash domain {domain!r}")
    return hashlib.sha512(domain.encode("ascii") + data).hexdigest()


def digest(domain: str, data: bytes) -> str:
    return domain + "sha-512:" + digest_hex(domain, data)


def parse(wire: str) -> tuple[str, str]:
    if not isinstance(wire, str):
        raise ValueError("B16: digest must be a wire string")
    match = re.fullmatch(r"([a-z-]+:)sha-512:([0-9a-f]{128})", wire)
    if match is None or match[1] not in DOMAINS:
        raise ValueError("B16: invalid or unregistered digest wire form")
    return match[1], match[2]


def selftest() -> int:
    for domain in sorted(DOMAINS):
        wire = digest(domain, b"fixture")
        assert parse(wire) == (domain, hashlib.sha512(domain.encode() + b"fixture").hexdigest())
        assert digest_hex(domain, b"fixture") == hashlib.sha512(domain.encode() + b"fixture").hexdigest()
        print(f"PASS b16-{domain[:-1]}-wire")
    for value in ("sha-512:" + "a" * 128, "unknown:sha-512:" + "a" * 128, "record:sha-512:" + "A" * 128):
        try:
            parse(value)
        except ValueError:
            continue
        raise AssertionError(value)

    # B16: the real registry table must agree with DOMAINS exactly.
    missing_from_table, missing_from_domains = registry_agreement_diff()
    if missing_from_table or missing_from_domains:
        raise AssertionError(
            f"b16-registry-agreement: missing_from_table={missing_from_table} "
            f"missing_from_domains={missing_from_domains}"
        )
    print("PASS b16-registry-agreement")

    # Able-to-fail control: a synthetic table text missing one domain must be CAUGHT.
    synthetic = "\n".join(f"| `{d}` | x | y | z | w |" for d in sorted(DOMAINS) if d != "record:")
    missing_from_table, missing_from_domains = registry_agreement_diff(synthetic)
    if "record:" not in missing_from_table:
        raise AssertionError("b16-registry-agreement-able-to-fail: did not catch a dropped domain")
    print("PASS b16-registry-agreement-able-to-fail")

    print(f"SELFTEST PASS: {len(DOMAINS) + 5} hash-domain fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else 2)
