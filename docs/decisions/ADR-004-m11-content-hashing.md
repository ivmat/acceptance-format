# ADR-004: M11 content hashing — SHA-512, input-side domain separation, one algorithm per revision

**Status:** Accepted (2026-08)

## Context

The format needs a tamper-evidence hash for three kinds of object — a whole manifest, a bundle
inventory, and a single evidence-record file — so a citation can be checked against the bytes it
names rather than trusted by name alone. Letting a producer pick their own algorithm per manifest
would let an attacker (or a careless toolchain) downgrade to a weaker one, and would split content
identity across manifests that happen to declare different algorithms for the same bytes.

## Decision

Exactly one canonical algorithm per format revision: SHA-512 over the raw bytes of the file as
emitted, never a decode-normalized or re-serialized form. Every use is domain-separated by a short
prefix fed into the hash **as input**, before the file bytes (`manifest:`, `evidence-record:`,
`bundle-root:`, `subject:`, and the reserved `claim:`), so the same bytes hashed for two purposes
never collide. Digest values are self-describing (`"sha-512:<128-hex>"`), and field names are
algorithm-neutral (`record_hash`, not `record_sha256`).

## Consequences

A hand-edited file simply gets a new identity — hashes are a tamper-evidence layer, not a
normalization layer. A future algorithm change is a new format revision, not a new field, because
the algorithm is a property of the revision, not of any one manifest. Self-describing values mean a
field name never needs to change again even if a later revision accepts a second algorithm.
