---
type: proposal
digest: The acceptance class hash-domain registry — one domain-separated SHA-512 construction, seven registered format-core prefixes (plus five protocol-folded prefixes below), wire forms and producer/verifier responsibilities (B16); this table is authoritative and MUST agree with `tools/hashdomains.py`'s `DOMAINS` set exactly.
---

# Hash domains (B16)

**Class text LOCKED at 0.3.2 (2026-09-27).** This text is frozen: a change needs a new `[[lock]]` entry
(new version + reason) in `CLASS-LOCK.toml`, enforced by `gates/check_class_lock.py`. Locked is not
ratified: the status below stays CANDIDATE until the owning authority ratifies the class.

This is the class registry. The registry and `tools/hashdomains.py` MUST agree. All domains MUST use the same
construction, stated here once:

`sha512(prefix || bytes)`

Here `prefix` is the literal registered prefix including its trailing colon, and
`bytes` is the content bound by that row. The wire form MUST be
`<prefix>sha-512:<128-hex>`. A digest binds exact bytes, not an independently reformatted
or interpreted version of the same document. Helpers MUST share the implementation in
`tools/hashdomains.py`; a different domain is not interchangeable merely because the
payload bytes are equal.

| prefix | construction | wire form | who writes it | who verifies it |
|---|---|---|---|---|
| `normative-reference:` | shared construction over the governing document bytes; for an external conformance standard, over the local clause-inventory bytes, not the standard's bytes | `normative-reference:sha-512:<128-hex>` | manifest producer writes `[spec].version` using the F2 helper | `check_core.check_spec` checks F2 form and recomputes external governing-document identity under every profile; a paired private repository's pin verifier additionally checks mirror equals canonical |
| `manifest:` | shared construction over the complete source manifest bytes (M11) | `manifest:sha-512:<128-hex>` | referencing manifest producer writes `manifest_hash` | `check_core.check_reference_evidence` hashes before parsing; a reference entry's `record_hash` equals `manifest_hash` in this domain, verified by `check_core.check_record_hashes`; B8 `records` cites only native `record:` hashes, never `manifest:` hashes; `protocol_acceptance/tools/m11.py` uses the shared domain module |
| `applicability-record:` | shared construction over the applicability-record bytes (R-7) | `applicability-record:sha-512:<128-hex>` | conformance producer writes `applicability_hash` | `tools/profiles/conformance.py`, through `hashdomains.py` |
| `subject:` | shared construction over subject content bytes (B1) | `subject:sha-512:<128-hex>` | manifest producer writes the content-digest locator or pinned read-at digest | `check_core.check_subject` checks the typed locator and always recomputes components serialization; other subject byte recomputation depends on a binding-declared resolvable subject payload |
| `record:` | shared construction over the raw evidence-record bytes | `record:sha-512:<128-hex>` | evidence producer / manifest producer writes `record_hash` | `check_core.check_record_hashes` on every applicable validation path, including B8's native-source-record admission, using `hashdomains.py` |
| `inventory:` | shared construction over the complete spec-inventory document bytes (B19) | `inventory:sha-512:<128-hex>` | spec-inventory producer writes `[spec].inventory_digest`, or `tools/spec_inventory.py digest` computes it | `check_core.check_inventory` recomputes it, under every profile, whenever `[spec].inventory` is present |
| `artifact:` | shared construction over one identified build artifact's bytes — a toolchain component (when its install method exposes a digestible binary) or a resolved build-input file (B20) | `artifact:sha-512:<128-hex>` | evidence producer writes `claim.evidence.toolchain[].digest` (shape-checked only, not recomputed — the referenced binary is not repository-contained) and `claim.evidence.build_inputs[].digest` (repository-contained, always recomputed) | `check_core.check_evidence_record` checks the wire form on both; `check_core.check_build_input_hashes` recomputes every resolvable `build_inputs` digest, on every validation path |

The five rows below are the protocol's own domains, folded into this one registry (they were a
second, un-unified `PREFIXES` dict in `protocol_acceptance/tools/m11.py`, defined independently of
B16). `m11.py`'s wire form for every one of its five domains was `sha-512:<128-hex>` — the domain
baked into the hashed bytes (`sha512(prefix || bytes)`, the same shared construction) but not
repeated in the wire string.

**One wire form (2026-09-24).** `contract:` and `decision:`, and `manifest:` as `m11.py` writes
it for `package_hash`, now use the SAME self-describing wire form as every format-core domain,
`<prefix>sha-512:<128-hex>` (`hashdomains.digest`) — the bare `sha-512:<hex>` m11.py form is
RETIRED for these three fields; a protocol document carrying it there is an explicit ERROR naming
the expected form (no compatibility shim with pre-lock drafts). `bundle-root:`, `evidence-record:`
and `claim:` are UNCHANGED and still use the bare `sha-512:<128-hex>` m11.py wire form:
`bundle-root:` and `claim:` are unwritten/reserved either way, and `evidence-record:`'s bare form
is the SAME "untyped legacy wire" the Read-only legacy record wires section already accepts
read-only with a WARNING throughout 0.3.x — migrating it now would pre-empt the separately planned
retirement to ERROR (a 0.4 change), and is out of this change's narrower contract/package/decision
scope.

| prefix | construction | wire form | who writes it | who verifies it |
|---|---|---|---|---|
| `manifest:` | shared construction over the complete package bytes (M11); same domain/construction as the row above | `manifest:sha-512:<128-hex>` (self-describing) | protocol package producer writes `package_hash` (protocol.md §7) | `acceptance_protocol.py` check-package/check-decision, via `m11.py` |
| `bundle-root:` | shared construction over bundle-root bytes | `sha-512:<128-hex>` (m11.py legacy wire, unchanged) | reserved for a future protocol bundle artifact — not written or verified in this revision | — |
| `evidence-record:` | shared construction over raw evidence-record bytes | `sha-512:<128-hex>` (m11.py legacy wire, unchanged; accepted read-only with a WARNING throughout 0.3.x — retirement to ERROR is a 0.4 change) | none in 0.3.x for a claim's `record_hash` — legacy, read-only, producers write `record:` there instead (see below); the one remaining writer of this bare wire is the protocol's `[[derivation.evidence]].digest` (protocol.md §5.4), which carries no WARNING of its own | `acceptance_protocol.py`, via `m11.py` |
| `claim:` | shared construction over per-claim signing bytes | `sha-512:<128-hex>` (m11.py legacy wire, unchanged) | RESERVED — not computed in this revision | — |
| `contract:` | shared construction over the complete contract bytes (protocol.md §7, additive-separator rule) | `contract:sha-512:<128-hex>` (self-describing) | protocol contract producer writes `contract_hash` | `acceptance_protocol.py` check-contract/check-package/check-decision, via `m11.py` |
| `decision:` | shared construction over the complete decision bytes (protocol.md §7, additive-separator rule) | `decision:sha-512:<128-hex>` (self-describing) | protocol decision producer writes `decision_hash` | `acceptance_protocol.py` check-decision, via `m11.py` |

Writer roles above identify the artifact producer, not a new trusted authority. A consumer
MUST NOT infer that byte recomputation occurred from a wire-shape check alone.

Recomputation contract:
`check_core.check_record_hashes` MUST recompute every `record_hash` whose pointer
resolves, on every validation path, using `record:` for native evidence and
`manifest:` for an `acceptance-claim` entry. A mismatch MUST FAIL. A missing native
`record` pointer MUST produce a WARNING (error under `--strict`); an unresolvable B8
citation MUST set the referencing claim's evaluation state to `indeterminate`,
propagating through B11. Absolute or escaping pointers MUST FAIL. A dereferenced
document missing, unreadable or unparsable MUST yield INDETERMINATE; native payloads
are opaque bytes and follow B6's separate outcomes and stated open cases.

`check_core.check_spec` MUST recompute `normative-reference:` for
`provenance = "external"` under EVERY profile. `check_execute.py` retains only recipe
execution; record recomputation MUST NOT depend on invoking it. `manifest:`,
`applicability-record:` and external `normative-reference:` MUST always be recomputed
by their verifiers. All pointers use the declaring manifest's directory and root (B6).

`check_core.check_inventory` MUST recompute `inventory:` whenever `[spec].inventory` is
present, under every profile (B19). This domain is independent of `normative-reference:`:
the spec inventory pins the generic item-coverage document, never the external standard's
own bytes.

`check_core.check_build_input_hashes` MUST recompute `artifact:` for every `build_inputs[].digest`
whose `path` resolves, on every validation path (B20). A mismatch MUST FAIL. An unresolvable
`path` MUST follow the same treatment as an unresolvable native `record` pointer: WARNING,
error under `--strict`. A `toolchain[].digest` uses the same domain and wire form but names a
build tool, not a repository-contained file; it is shape-checked only and is never recomputed.

`subject:` MUST be recomputed when the binding declares a resolvable payload
(`[subject].path`; document and tool bindings); otherwise it is shape-checked and
the validator MUST warn "subject digest not recomputed". Components serialization
is ALWAYS recomputable from the manifest's own component table and MUST be recomputed;
it is explicitly exempt from this payload condition.

B1's components identity is the `subject:` digest over the canonical serialization defined in core.md B1
(sorted `<name>=<locator wire form>` lines, trailing newline, UTF-8). Component names
MUST be unique and match `[a-z0-9][a-z0-9._-]*`, excluding `=`, whitespace and newline.
Locator hex MUST be lowercase; digest hex MUST be compared case-insensitively and
written lowercase. The aggregate `subject:` digest is the components identity, not
a second identity.

## Read-only legacy record wires

Two untyped `sha-512:<128-hex>` constructions are accepted read-only: SHA-512 over
raw record bytes (bare), and SHA-512 over `b"evidence-record:" + raw`. The verifier
recomputes both; a match emits `B16: untyped record_hash (legacy wire: bare|evidence-record); use record:sha-512`
with the matching wire name. Matching neither is an ERROR, as is any unsupported
shape or domain on a native record. These legacy constructions are accepted read-only,
with a WARNING, on every profile throughout 0.3.x, for a claim's `record_hash`; producers
MUST emit the registered `record:` construction there. Retirement (WARNING → ERROR) is a
0.4 change. The protocol's `[[derivation.evidence]].digest` (protocol.md §5.4) is a
DIFFERENT field that also carries the bare `evidence-record:` form, deliberately, with no
WARNING of its own — it is not `record_hash` and this section's WARNING does not cover it.

## Adding a domain

A new domain MUST be an explicit edit to this registry and `tools/hashdomains.py`.
The edit MUST name its prefix, bound payload, wire form, writer and verifier, use the
shared construction, and receive domain wire-form coverage in the `b16-*` fixtures.
Core, conformance, the F2 helper and `protocol_acceptance/tools/m11.py` MUST call the
shared module instead of defining independent constructions. The M11 migration (2026-09-24)
is done: `protocol_acceptance/tools/m11.py` no longer carries its own hash
construction; it imports `hashdomains.digest_hex` for `sha512(prefix || bytes)` and keeps only
its own domain-name list and its `claim` reservation. A later change (2026-09-24) removed the SEPARATE
`sha-512:<hex>` wire-form assembly for `contract`, `decision` and `manifest`: those three now
call `hashdomains.digest` directly for the self-describing form, matching every format-core
domain; `bundle-root`, `evidence-record` and `claim` keep the bare m11.py wire form: `bundle-root`
and `claim` are unwritten/reserved; `evidence-record` is read-only with a WARNING throughout
0.3.x for a claim's `record_hash` (see above) — EXCEPT the protocol's `[[derivation.evidence]]
.digest`, which writes the SAME bare `evidence-record:` form deliberately and carries no WARNING
of its own (a different field, not `record_hash`; see above).
