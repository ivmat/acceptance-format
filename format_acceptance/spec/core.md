---
type: proposal
digest: The profile-neutral acceptance base format — Class→Instance→Run, design rules 1–7, B1–B20, validator ownership, representation parity, ordered verdict composition, generic spec-inventory coverage, and generic typed toolchain/build-input identity; transcribed from the 2026-09-22 v2 design, pending owner ratification.
---

# Acceptance — the base format

**Class text LOCKED at 0.3.2 (2026-09-27).** This text is frozen: a change needs a new `[[lock]]` entry
(new version + reason) in `CLASS-LOCK.toml`, enforced by `gates/check_class_lock.py`. Generic-core and apparatus scans run in the upstream development repository. Locked is not
ratified: the status below stays CANDIDATE until the owning authority ratifies the class.

This CANDIDATE specification states the proposed contract. Its MUST and MUST NOT
statements do not claim ratification or completed implementation. Module names below identify their assigned owners.

## §0 Class→Instance→Run

| rung | what it fixes | carrier |
|---|---|---|
| Class | claim, evidence, deciding rule, identity, registries, verdicts, and representation parity | `spec/core.md`, `spec/format.md`, `spec/profiles.md`, `spec/hash-domains.md`; `tools/acceptance_grammar.py`, `tools/check_core.py`, `tools/check_ledger.py`, `tools/check_execute.py`, `tools/check_parity_selftest.py`, `tools/hashdomains.py` |
| Instance | a meaning, optionally projected onto a refine-only binding | `profiles/<meaning>/PROFILE.md`, `profiles/<meaning>/<binding path>.md`, `profiles/bindings/`; `tools/profiles/*.py`, `tools/bindings/*.py` |
| Run | one subject, one manifest, exact locators, and actual evidence records | `acceptance.toml` and its Markdown twin; `examples/` here and a subject inventory in a paired private repository |

The class lives in `format_acceptance/`. The protocol remains in
`protocol_acceptance/`; its profile documents are protocol projections of format leaves.
`tools/check_acceptance.py` remains the compatibility entry point (core + verification)
until every caller moves. A paired private repository keeps subjects, trials, review history,
publication staging and pinned local inventory mirrors. Its resolver MUST verify the pin closure
before running a validator; direct invocation of the class validator bypasses that repository's
pin.
## Glossary

Four terms this spec and the sibling protocol spec (`protocol_acceptance/spec/protocol.md`) use
with one meaning each:

- **profile** — an acceptance meaning only (what acceptance says about the artifact; e.g.
  verification, conformance — [profiles.md](profiles.md)). A profile is never a binding, never a
  leaf, and never a criticality level. The manifest field `[format].profile` (B12) is a legacy
  name that may carry a meaning alone or a meaning refined by a binding path; the field's stored
  value can name a leaf, but the vocabulary word "profile" still means the meaning half of that
  identifier.
- **assurance class** — the criticality a contract declares for the delivery this class accepts
  (blast radius × irreversibility); it selects a target floor set. The class table and the
  maturity rule that scales it live in the protocol contract, not here.
- **party boundary** — the declared internal-vs-cross-org parameter set on a protocol contract.
  This class never branches on it.
- **readiness level** — a separate maturity-tier ladder for a subsystem or artifact, recorded
  outside this class, distinct from both the assurance class and a profile's own build status
  (CANDIDATE, consumer-backed, …).

## §1 The unit: claim · evidence · the rule that decides

A claim names a subject item and a governing clause, states what is asserted, and carries
its evidence or an explicit gap. The deciding rule determines whether that evidence is
admissible for that claim under the selected meaning and binding. One manifest records
one subject; it states conformity under named assumptions and reproducible evidence,
never an unqualified assertion that the subject is correct.

Identity and provenance bind the assertion to exact content. The class checks shape,
registry membership, references, and rule composition; evidence truth and whether a
chosen clause or declared carrier is adequate remain review responsibilities. Weight MUST be
explicit: absent weight is unweighted. An assertion does not become evidence by receiving
a label. Class rules apply regardless of weight, including applicability and reference rules.

## §2 Design rules 1–7

1. **Gaps are first-class.** A governing clause with no admissible evidence MUST appear as
   a claim with `status = "gap"`, subject to B5's explicit applicability distinction
   and an allowance for zero claims per clause only under `denominator = "slice"`.
   Omission MUST NOT hide an obligation. `[coverage]` declares totals to make omission detectable.
2. **Evidence is admissible or it is nothing.** A record MUST carry its required provenance.
   Missing provenance is an assertion, not evidence, and MUST be rejected. The result records
   what was checked, under which semantics, by which identified tool. Recipe carriers are
   binding declarations; per-grade recipe requirements belong to verification.
3. **No trust numbers in `/0`.** Assurance bands are evidence floors, not probabilities.
   `alpha`, `beta`, and `lr` MUST NOT appear except on an evidence entry carrying a
   B6-contained `calibration = "<relative path>"` that exists and parses. This disclosure
   exempts only those keys on that entry; aggregate keys remain forbidden by B7.
   Trust arithmetic awaits measured calibration.
4. **The certificate binds to exact content.** A retrospective subject MUST carry exactly
   one certified typed identity (B1). A git identity MUST disclose a dirty tree with
   `dirty = true`. A prospective subject MUST carry a read-locator and has no certified
   identity. Its optional `commit`/`digest`, including an all-zero placeholder, is
   informational and MUST be excluded from certified-identity counting (B1).
5. **Producer never self-overrides.** A producer MUST record the reported result as-is.
   `fail` and `unsupported` MUST remain distinct: the former calls for investigation,
   the latter for parking, and neither may be rewritten as a pass.
6. **Claim ids are stable and never reused.** A published claim id MUST NOT be repurposed.
   Supersession MUST use a new id plus `supersedes = "<old>"`.
7. **A wholly prospective manifest is never plain PASS.** Zero `evidenced`/`partial`
   claims means nothing has been checked for F4. Such a manifest MUST receive
   `PASS-PROSPECTIVE` when it reaches that row of B11, rather than bare `PASS`.
   Earlier B11 rows still take precedence, including empty and all-not-applicable cases.

## §3 The B-rules

**Validation examples:** identifies the fixture prefixes and the failure scenarios in §2;
positive cases are explicitly labelled. These are specification obligations, not a claim
that this prose-only document added or ran validator fixtures.

Concrete fixture names are assigned by the implementer under the prefixes given here.

### B1 — Typed subject locators

RULE: A subject MUST default to `mode = "retrospective"` and carry exactly one certified
identity of a registered kind: `git-revision` (`commit`, 40 hexadecimal characters,
with its `dirty` marker), `content-digest` (`digest = "subject:sha-512:<hex>"`), or
`components` (`[[subject.components]]`, each with `name` and one typed locator).
The component subject's digest MUST be `[subject].digest = "subject:sha-512:<hex>"` over this
canonical serialization: one line per component, `<name>=<locator wire form>`, where the wire form is
`git-revision:<40-hex>` or `content-digest:subject:sha-512:<hex>`; names MUST be unique and
match `[a-z0-9][a-z0-9._-]*` (no `=`, whitespace or newline). Locator hex MUST be lowercase;
digest hex MUST be compared case-insensitively and written lowercase;
lines MUST be sorted by name bytewise and joined by `\n` with a trailing `\n`, UTF-8; the validator
MUST recompute it and FAIL on mismatch. This aggregate `subject:`
digest IS the components identity, not a second identity. Its serialization is always
recomputable from the manifest's component table, exempt from the subject-payload condition.
`commit` MUST retain its exact meaning as the git-revision shorthand; existing manifests
need no change. A `prospective` subject MUST NOT carry a certified identity and MUST
carry a typed read-locator: `read_at_commit` for git or `read_at_digest` for digest kinds.
It MAY also carry informational `commit`/`digest`, including the all-zero placeholder of
the check-manifest pattern; these MUST be excluded from certified-identity counting
and their presence is not an error. They MUST NOT replace the required read-locator.
A read-locator MAY be `"unpinned"`; the prospective subject's verdict MUST be at most
`PASS-PROSPECTIVE`. Bindings MUST narrow admitted locator kinds; meanings MUST NOT alter
identity. The design assigns git-revision to the code binding, content-digest to tool,
content-digest or git-revision to document, and components or git-revision to estate-element.

A retrospective subject generated from inside the very repository the manifest certifies
cannot name a commit that already contains that manifest: the manifest's own bytes are not
yet part of the tree being certified when the certifying commit is made. This is not a
defect in the identity rule and gets no new mechanism: the resolution is a two-commit
workflow — commit the subject first, regenerate the manifest against that now-clean,
already-committed tree, then commit the resulting manifest as a second, later, disjoint
commit. `dirty = false` holds by construction because the manifest's own commit is
chronologically after, and outside, the commit it certifies. A cross-organisation delivery
already behaves this way (the release is tagged before the package that certifies it exists)
and so never meets this case at all.

WHY: Identity must name the content certified while allowing a subject with no certified content yet to disclose what was read. Typed locators make that distinction usable across artifact types.

CHECKED BY: `check_core.check_subject`; binding identity narrowing also belongs to `check_core.check_binding_chain` (B17).

**Validation examples:** `b1-*`: two retrospective identities; none; code binding with digest identity; prospective with `commit` and no read-locator. Positive cases: prospective unpinned and retrospective document digest. Components beyond shape have only git-revision/content-digest fixture coverage.

**Representation:** The ledger header MUST parse typed locators, `digest`, and `read_at_*`; both representations MUST preserve the distinction between certified and read identity.

### B2 — Assurance-band mechanism

RULE: A `ladder_id` MUST be registered once in the class ladder registry,
`tools/profiles/__init__.py` `LADDERS`, with its authoritative token order. A meaning
MAY declare which one registered ladder it uses and a `control_free_ceiling` per
evidence shape. Two meanings share a ladder iff they name the same registered id.
A claim's `band`, when present, MUST belong to that meaning's ladder. Above the control-free ceiling, the claim MUST have an observed-red control
whose `of_claim` resolves to THIS claim. A control MUST attest only the claim it names
and MUST NOT lift a judgment-only claim. If the meaning declares no ladder, `band`
MUST be absent and every floor comparison MUST treat the claim as at the ladder floor.
A band-less claim under a ladder-bearing meaning (B8 step 7) MUST be treated at that
ladder's floor, its first token, for every floor comparison and MUST say so in `statement`:
concretely, that floor token MUST appear in `statement` as a whole word (case-sensitive,
word-boundary match on the ladder's own token spelling — no separate marker, field or
vocabulary). A floor token that appears only as a substring of a longer word (e.g. `A0x`)
does NOT satisfy this; the exact token, bounded by non-word characters or string edges,
is what "say so" checks. This is the entire disclosure grammar: it borrows no vocabulary
beyond the ladder's already-registered token order (`tools/profiles/__init__.py` `LADDERS`).
Species ceilings, carrier-family compatibility and per-band control-kind whitelists
belong to the meaning's declaration; the verification table lives in
`assurance-bands.md`.

WHY: The class can enforce ordering and control binding without imposing one meaning’s evidence ladder on every other meaning. Defining disclosure as a word-boundary match on the ladder's own floor token, rather than a new field or free-form marker, keeps the requirement mechanically checkable without inventing vocabulary a meaning has not already registered.

CHECKED BY: `check_core.check_band_mechanism` (fires for every claim, including a B8
referencing claim once it is band-less); species tables: `profiles/verification.py`.

**Validation examples:** `b2-*`: unknown band token; band under a meaning with no ladder; lifted band with a control naming another claim; `b2-bandless-floor-disclosure-red` (missing disclosure); `b2-floor-substring-is-not-disclosure-red` / `b2-floor-word-disclosure-ok` (word-boundary precision — a substring match does not count); `b8-cross-ladder-floor-undisclosed-red` (the same disclosure requirement reached through a B8 referencing claim).

**Representation:** The ledger `band` column MUST use the same declaring ladder and control-binding mechanism, including absence for band-less claims.

### B3 — Meaning-declared evidence families

RULE: `epistemic_tier` MUST use the class-shared closed ordinal T1 > T2 > T3 > T4 > T5,
from strongest to weakest, under every meaning; tier minima MUST compare on this ordinal.
Every evidence record MUST name a `family` declared by its meaning or a class family.
The class families are `judgment` (ceiling T5) and `reference` (derived); a meaning MUST
NOT redefine them. Each meaning-declared family MUST have an `epistemic_tier` ceiling
and a record's tier MUST NOT exceed it. The tier of a `reference` record MUST equal
the minimum tier of its referenced records (B8); it MUST NOT use a static ceiling row.
Verification owns its remaining family rows; conformance declares its own rows by citation.

WHY: Family ceilings describe what a meaning can infer from a carrier; borrowing records cannot manufacture stronger warrant than its sources.

CHECKED BY: `check_core.check_family_mechanism`; verification rows in `profiles/verification.py`.

**Validation examples:** `b3-*`: undeclared family; tier above family ceiling; reference tier above its sources.

**Representation:** The ledger `family` MUST use the same registry and derived-reference rule.

### B4 — Evidence kinds and provenance

RULE: The class MUST retain the universal evidence fields `kind`, `family`, `ref`,
`result`, `tool`, `record`, and optional `record_hash`. A kind MUST be declared and its
required extra fields MUST be present; missing required provenance MUST be rejected as
assertion rather than evidence. `human-review`, `llm-review`, and `acceptance-claim`
are class registry rows whose admission MUST be owned by `check_core.check_evidence_record`;
a meaning MUST NOT redefine them. Other `KIND_REGISTRY` rows move to the verification profile.

| class kind | family | extra-required provenance |
|---|---|---|
| `human-review` | `judgment` | `reviewer` |
| `llm-review` | `judgment` | `reviewer` identifying the model id |
| `acceptance-claim` | `reference` | `manifest`, `manifest_hash`, `claim`, nonempty `records` (B8) |

WHY: A shared record shape permits profile-specific carriers without allowing an undeclared kind or missing provenance to masquerade as admissible evidence.

CHECKED BY: `check_core.check_evidence_record` (universal fields and authoritative class-kind admission), plus the profile registry for other kinds.

**Validation examples:** Existing `KIND_REGISTRY` fixtures: undeclared kind and missing kind-specific extra field; no `b4-*` prefix is assigned.

**Representation:** B18 requires the same class vocabulary and provenance obligations in the ledger; no additional B4-specific twin is assigned.

### B5 — Applicability, exclusion and status

RULE: `not-applicable` MUST be a class status. It MUST have nonempty
`applicability_reason`, MUST NOT carry evidence or weighted weight, and MUST have
`grade = "out-of-scope"` or no grade. Weight MUST be absent or `"unweighted"`.
It MUST count in coverage totals, appear in its own reporting column, and MUST NOT
count in F4's checked-anything set. `applicability` and `applicability_reason` MUST be
class fields preserved by every representation. `applicability` is optional and admits
`applicable`, `not-applicable`, or `excluded`. The valid pairings MUST be:

| applicability | status |
|---|---|
| `applicable` (or omitted, except the inference below) | any status except `not-applicable` |
| `not-applicable` | `not-applicable` |
| `excluded` | `gap` |

Omitted applicability MUST infer `not-applicable` when status is `not-applicable`,
and MUST otherwise default to `applicable`. Any other mismatch MUST be an error.

`excluded` MUST map to `status = "gap"`, `applicability = "excluded"`, nonempty reason,
no evidence and unweighted weight; a profile's own `grade = "out-of-scope"` and nonempty
`scope_ref` constraints, where that profile declares them, remain (conformance names this
rule C4; the id is that profile's own, not a class id). Coverage reports and every projection MUST print excluded claims
as distinct rows from evidence gaps, never as not-applicable claims.

The legacy `gap` + `out-of-scope` + `scope_ref` + `applicability = "not-applicable"`
encoding MUST be read as `not-applicable` with a WARNING under conformance `0.1.0-draft`
and MUST be an ERROR from conformance `0.2`. Migration of existing conformance subjects is
outside this Class text.

WHY: An inapplicable obligation and an excluded obligation have different meanings. Keeping each visible prevents either from inflating checked coverage or disappearing into undifferentiated gaps.

CHECKED BY: `acceptance_grammar.STATUSES`, `check_core.check_claims`; `check_ledger` preserves applicability and reason; paired checks in `check_parity`, carried by `check_parity_selftest.py`.

**Validation examples:** `b5-*`: not-applicable with evidence, without reason, or weighted; excluded mapped to not-applicable; a ledger row dropping its reason. Legacy encoding becomes red at conformance 0.2.

**Representation:** The ledger MUST parse and preserve applicability and reason, display not-applicable separately, retain excluded rows separately from evidence gaps, and share coverage/F4 counts.

### B6 — Repository-contained document pointers

RULE: Every manifest-local pointer MUST resolve relative to the directory of the
manifest that declares it. After symlink resolution it MUST remain inside that
manifest's repository root (nearest `.git` ancestor of that manifest, or `--root`).
Absolute paths and escapes MUST fail. An unresolved root MUST yield INDETERMINATE.
`--root` MUST NOT widen containment to a second repository. A canonical
document owned elsewhere MUST be mirrored locally when needed: canonical inventories
live under `profiles/conformance/standards/`, paired private repository mirrors under
`standards/<id>.clauses.toml`. `[spec].version` MUST bind the mirror through its F2
digest; the pin gate MUST additionally assert mirror equals canonical bytes.

| pointer outcome | required result |
|---|---|
| absolute or escaping pointer, including symlink escape | FAIL |
| dereferenced document (manifest, inventory, applicability record, source manifest, binding declaration) missing, unreadable or unparsable | INDETERMINATE |
| native evidence `record` pointer missing | WARNING; error under `--strict` |
| present record whose hash mismatches | FAIL |
| cited record of a B8 reference missing | referencing claim evaluation state `indeterminate` (B8/B11) |

Native evidence payloads are opaque bytes, not documents to parse; the document row
in §4 MUST NOT override the native-record missing-pointer outcome. B8 separately
makes every unresolvable citation indeterminate.
A present-but-unreadable native record payload MUST be treated as missing (WARNING; error under `--strict`) because its hash cannot be recomputed; a malformed pointer value (not a nonempty string) MUST FAIL as a shape error.

WHY: Contained pointers make dereferencing reproducible within one repository; local mirrors preserve that boundary while digest and pin checks preserve external document identity.

CHECKED BY: `check_core._resolve_pointer` (base and containment), `check_core.check_record_hashes` (every resolvable record hash on every validation path), and `check_core.check_spec` (external normative-reference recomputation under every profile); a paired private repository's pin verifier supplies the additional mirror-equality check.

**Validation examples:** `b6-*`: parent-directory escape; absolute path; symlink out; mirror digest differs from `[spec].version`.

**Representation:** Ledger pointers MUST obey the same containment, root resolution and mirror identity rules.

### B7 — No aggregates on assertion surfaces

RULE: The class MUST reject `score`, `percent`, `percentage`, and `conformance_level`
unconditionally at every depth of the manifest, applicability record, clause inventories,
Markdown ledger and any document a profile declares an assertion surface. Reserved
`alpha`/`beta`/`lr` MUST also be rejected except on an evidence entry carrying
`calibration = "<relative path>"`. That path MUST be B6-contained, exist and parse;
it exempts ONLY `alpha`/`beta`/`lr` on THAT entry and never exempts aggregate keys.
`/0` defines no calibration record schema: its presence is a disclosure, not a score.
In `/0` a calibration reference ending in `.toml` MUST parse as TOML; any other calibration reference is checked for existence only. No calibration schema is defined in `/0`.

Opaque evidence payloads named by `record`
(transcripts, tool output, datasets) MUST be hashed, not key-scanned or interpreted by
this check. Profiles MAY extend the blocklist and MUST NOT shrink it.

WHY: Assertions must not imply unsupported quantitative trust. Raw evidence may legitimately contain the same words as measured output, so scanning it would confuse evidence with the claim made about it.

CHECKED BY: `check_core.check_no_aggregates` on assertion surfaces only.

**Validation examples:** `b7-*`: nested manifest `score`. Positive case: `score` inside a record file.

**Representation:** The ledger is an assertion surface and MUST apply the same nested aggregate restriction.

### B8 — Cross-manifest evidence by reference

RULE: The only cross-manifest borrowing mechanism admitted in `/0` MUST be
records-mode evidence of `kind = "acceptance-claim"`, `family = "reference"`.
On such an entry the universal fields (B4) MUST read: `kind = "acceptance-claim"`,
`family = "reference"`, `ref = "<manifest>#<claim>"`, `result = "pass"`, `tool` = the referencing
validator's id and version, `record` = the `manifest` path, `record_hash` = `manifest_hash`.
The kind's extra-required fields MUST be `manifest` (relative, B6),
`manifest_hash` (`manifest:sha-512:<hex>`), `claim` (source id), and REQUIRED nonempty `records`
(a list of `record_hash` values). Each cited hash MUST be checked for membership against the source
claim's declared `record_hash` values AND recomputed over the source record file's bytes when that
pointer resolves inside the source's root; an unresolvable cited record MUST make the referencing
claim's evaluation state `indeterminate`. The class MUST maintain a
per-claim evaluation state in `{ok, error, indeterminate}`, distinct from persisted
claim `status`. Unresolvable cited records, INDETERMINATE sources, cycles and excessive
depth MUST set that state to `indeterminate`; B11 propagates it to the manifest verdict.
During recursion, source pointers MUST resolve relative to the source manifest's
directory and remain contained in that source manifest's repository root (B6).
Admission MUST proceed in this order:

1. Hash the source bytes before parsing; mismatch with `manifest_hash` MUST FAIL.

   **1b. Before recursive descent**, guard the active path: a source `manifest_hash`
   already on that path MUST set the referencing claim's evaluation state to
   `indeterminate` (cycle). Count path length in manifests, including the root and
   proposed source; a length greater than 5 MUST set the state to `indeterminate`.
   Either guard MUST stop descent.

2. Validate the source under core (8a), and under its profile (8b) if evaluable here.
   A source whose profile is not evaluable here (an unrecognized meaning prefix, an
   unrecognized binding suffix, or any other 8b half this validator cannot dispatch) is
   INDETERMINATE and propagates; it is never admitted on core (8a) validation alone —
   evaluability at 8b is not optional just because 8a passed.
   B8 recursion MUST validate the source with `strict = False`; cited record payloads MUST independently be present and readable.
   A failing source MUST be rejected; an INDETERMINATE source MUST make the
   referencing claim's evaluation state `indeterminate`.
3. The source claim MUST exist and have status `evidenced` or `partial`.
   `gap`, `parked`, `blocked`, and `not-applicable` MUST discharge nothing.
4. Each listed hash MUST identify a NATIVE, NON-control evidence entry of that claim
   with `result = "pass"`: any kind except `acceptance-claim`. Citing a reference
   entry MUST be an error. Every cited hash MUST use the `record:` domain;
   `manifest:` MUST NOT appear in `records`. An entry carrying a `control` table
   MUST NOT be cited.
5. The referencing claim MUST NOT carry its own control. Controls MUST NOT transfer.
6. Weight eligibility MUST be evaluated with every `acceptance-claim` record removed
   from the claim; the remaining native evidence MUST independently satisfy every
   applicable weight condition. A claim with no native evidence MUST be unweighted.
   References contribute to status and coverage, never to weight.
7. If both meanings name the same registered `ladder_id` and its authoritative order
   (B2), the referencing band MUST NOT exceed the minimum source-claim band or the referencing meaning's control-free ceiling.
   If ladders differ or the source is band-less, the referencing claim MUST be band-less;
   under a ladder-bearing meaning it MUST use that ladder's first token as the floor
   for every floor comparison and MUST disclose this in `statement` — the same
   word-boundary floor-token check B2 defines, applied here without exception because
   `check_core.check_band_mechanism` runs once per claim regardless of evidence kind.
8. Reference tier MUST equal the minimum tier of the listed records on the class-shared
   T1 > T2 > T3 > T4 > T5 ordinal (B3).
9. Visit sources by `manifest_hash`; the termination guard MUST run at step 1b, before
   source validation, using the active path and manifest-count depth defined there.

Claim-discharge mode (using a source verdict without named records) MUST NOT be admitted
in `/0`; its proposal waits for the first deliverable subject. Full-byte hashes make
a true cycle unconstructible, but the evaluator MUST still check it. The
`source_claim`, `source_claims_other`, and `[conformance].source_manifest{,_hash}`
fields remain accepted as conformance `0.1.0-draft`'s encoding and MUST be lowered to
`acceptance-claim` at conformance `0.2`. The implementation work for that lowering is
outside this Class text.

WHY: Borrowing must identify the exact passing records and preserve their limits. Neither a source verdict, a control nor a different ladder licenses stronger claims at the destination.

CHECKED BY: `check_core.check_reference_evidence` (admission, guarded recursion and evaluation state), with `check_core.check_record_hashes` recomputing cited native records on every applicable validation path through `hashdomains.py`.

**Validation examples:** `b8-*`: wrong manifest hash; source fails core; source claim is gap; cited entry has a control; referencing claim has a control; reference-only claim weighted; band above source minimum; cross-ladder band; `b8-cycle-two-manifests`; a Lean-only source cited as a Kani record (illustrative; profile vocabulary); `b8-source-unknown` (source profile not evaluable here — a known meaning with an unrecognized binding suffix — propagates INDETERMINATE to the referencing claim's evaluation state, never admitted on 8a alone); `b8-depth-six-manifests`.

**Representation:** The ledger MUST cite reference rows read-only, preserve named record hashes, and MUST NOT turn a reference into a transferred control or weight-bearing record.

### B9 — Cover-only metadata and binding over-claim guards

RULE: The verification profile MUST provide optional record metadata `cover_only = true`
and optional tally pair `cover_satisfied` / `cover_total`. The subject-specific
`_witnessed` naming convention MUST live only in that subject's generator, which emits
`cover_only = true`; it MUST NOT be a class name heuristic. A binding MAY declare its own
over-claim guard on this metadata: a weighted claim whose evidence records of a
binding-declared kind are ALL cover-only MUST FAIL under that guard; zero such records MUST
NOT trigger it. This class rule fixes the metadata shape and the guard's general form; the
concrete evidence kind and the guard's own rule id belong to the binding that declares it
(see that binding's own document). A tally MUST NOT lift weight in `/0`; it is recorded,
not scored.

WHY: Explicit metadata describes the evidence without elevating one producer’s naming convention into a universal rule. The nonempty guard avoids rejecting evidence to which a binding's guard does not apply.

CHECKED BY: `profiles/verification.py` (field); the declaring binding's own module (e.g. `bindings/code_rust.py`).

**Validation examples:** `b9-*`: weighted all-cover Kani claim (illustrative; profile vocabulary). Positive case: weighted Lean-only claim (illustrative; profile vocabulary) does not trip the guard.

**Representation:** No separate B9 twin is assigned; B18 still requires a ledger rendering to preserve class weight semantics. Cover metadata remains profile vocabulary, not a new class field.

### B10 — Explicit gaps

RULE: A claim MAY carry `gaps`, a list of own-words statements describing what its
evidence does not decide. Missing `gaps` on `partial` MUST produce a WARNING.
Gaps MUST NOT be scored and MUST be preserved by the Markdown ledger.

WHY: A partial result should disclose its undecided remainder without converting that disclosure into an assurance score.

CHECKED BY: `check_core.check_claims` (warning).

**Validation examples:** `b10-*`: partial claim missing `gaps` produces the specified WARNING, not a new class error; loss of gaps in the twin violates B18.

**Representation:** The ledger MUST parse and preserve the `gaps` list and the partial-without-gaps warning.

### B11 — Verdict vocabulary and composition

RULE: Verdicts MUST use `PASS`, `PASS-PROSPECTIVE`, `PASS-MEANING-ONLY`,
`PASS-BINDING-ONLY`, `FAIL`, or `INDETERMINATE`. The evaluator MUST apply the table in
§4 in its printed order. Any claim in evaluation state `indeterminate` (B8) MUST
propagate to INDETERMINATE, exit 2, after the root/document row and before the
unknown-profile row; evaluation state MUST NOT be confused with claim `status`.
`PASS-PROSPECTIVE` MUST win over scoped PASS when F4 applies,
with the scope printed as a note. Across multiple files, precedence MUST be
FAIL > INDETERMINATE > any PASS.

WHY: A successful structural check, a scoped evaluation and actual checked evidence are different outcomes. Ordered composition prevents a profile result from masking a class error or an unavailable check.

CHECKED BY: `check_core.verdict`.

**Validation examples:** `b11-*`: one case per §4 row, including empty manifest, mismatched coverage and all-not-applicable retrospective manifest. Expected verdicts and exits are exactly those in §4.

**Representation:** The ledger MUST use identical verdict labels, ordering and scope notes.

### B12 — Profile-field identifiers and prefix interpretation

RULE: `[format].profile` is REQUIRED at 0.3.0 and MUST have the form
`acceptance/<meaning>[/<binding path>]`. There is no compatibility default: the
0.2-era fallback (a single named constant a manifest could omit the field and still
resolve against) is REMOVED from `/0`. A manifest omitting `[format].profile` MUST
be an ERROR naming the field (`B12: [format].profile is REQUIRED at 0.3.0 ...`), not
a silently-assumed meaning. A validator knowing the meaning but not the suffix MUST
validate at that prefix and report INDETERMINATE regardless of scoping flags; the
unknown suffix MUST NOT itself make the record invalid. Scoping flags MUST apply only
to a KNOWN leaf id whose 8b half is missing. `acceptance/core` is reserved and MUST
NOT be written into a manifest.

WHY: The prefix carries a readable meaning even when a consumer lacks the binding implementation; a reserved core name cannot pretend to be a concrete meaning. A REQUIRED field, with no fallback meaning to silently assume, makes every manifest self-describing: a reader never has to know which validator revision's default applied to know what this manifest claims.

CHECKED BY: `check_core.dispatch`; `check_core.parse_profile` (the REQUIRED-field check).

**Validation examples:** `b12-*`: `b12-profile-required` (omitted field is an ERROR naming it); unknown prefix or suffix yields exit 2; reserved core identifier is not an admissible `[format].profile` value. Dispatch coverage is grouped with B13.

**Representation:** No distinct dispatch twin is assigned; a ledger MUST retain the profile declaration and MUST NOT claim fuller evaluation than the available prefix.

### B13 — Core and leaf composition

RULE: The core MUST supply the entry point, orchestration and all class checks (8a),
then dispatch by meaning prefix to the meaning module and by binding path to the binding
module (8b). A leaf MUST compose `check_meaning ∧ check_binding ∧ leaf delta`.
A meaning or binding check MUST only ADD errors and MUST NOT suppress a class error; class errors
MUST be evaluated first under B11. A leaf missing an 8b half without an explicit scoping
flag MUST be INDETERMINATE. Scoping MUST apply only to a KNOWN leaf id with a
missing 8b half; an unknown suffix MUST remain INDETERMINATE regardless of flags.
Every applicable validation path MUST invoke `check_core.check_record_hashes` for
resolvable record hashes and `check_core.check_spec` for external normative-reference
recomputation; `check_execute.py` retains only recipe execution.

WHY: The shared format remains a lower bound on every instance, and a leaf cannot report full acceptance after evaluating only one of its two axes.

CHECKED BY: `check_core.dispatch`.

**Validation examples:** `b13-*`: missing half yields exit 2; explicit scope on a known leaf with a missing half produces the corresponding scoped verdict if all available checks pass; unknown suffix plus any scoping flag remains INDETERMINATE, exit 2; class errors remain FAIL.

**Representation:** No separate dispatch twin is assigned; ledger verdicts MUST preserve the same evaluation scope and class errors.

### B14 — Base kind recognition and binding admission

RULE: The base registry MUST recognize exactly these base tokens: `doc`, `tool`,
`prospective-feature`, `other`, `ml-model`, `dataset`, `spec`, `design`, `agent-output`.
`[format].kind_registry` MAY extend recognition (F1). Each binding document MUST carry a
machine-readable fenced `toml` block containing `admits = [...]`, and the binding check
MUST enforce it. A manifest's declared binding chain MAY additionally admit a
binding-specific kind not in the base registry, read from that same `admits = [...]`
declaration — the Class validator recognizes such a kind only because the binding it
belongs to says so, never because the base registry names it. Base recognition MUST NOT
imply admission under a binding.

WHY: An open shared vocabulary allows new subject shapes while a binding retains the ability to constrain the subjects it can actually evaluate; a binding-specific artifact shape lives in that binding's own declaration, not in the shared base.

CHECKED BY: `bindings/*.py`, `check_core.load_bindings`, `check_core._binding_admitted_kinds`.

**Validation examples:** `b14-*`: `kind = "doc"` under a code/rust leaf (illustrative; profile vocabulary).

**Representation:** No separate admission twin is assigned; the ledger header MUST preserve subject kind for the same binding admission check.

### B15 — Unpinned reads and slice disclosure

RULE: A prospective read-locator MAY be `read_at_commit = "unpinned"` or
`read_at_digest = "unpinned"` (B1). For `[coverage].denominator = "slice"`, missing
`slice_boundary` MUST produce a WARNING in `/0` and an error from `/1`. The slice
mechanism remains EXPERIMENTAL; its existing `slice_note` requirement is retained.

WHY: An unpinned read states the absence of a fixed tree honestly, and a declared slice must make its boundary visible rather than imply complete coverage.

CHECKED BY: `check_core`.

**Validation examples:** `b15-*`: slice without `slice_boundary` MUST warn in `/0` and fail from `/1`; positive cases include unpinned read-locators.

**Representation:** The ledger MUST parse unpinned read-locators and preserve `slice_boundary` alongside denominator and slice note.

### B16 — Hash domains

RULE: [hash-domains.md](hash-domains.md)'s registry table is the authoritative list of every
registered hash domain; it MUST use the one construction and wire form stated there. A separate
enumeration is not repeated in this rule, so the two can never disagree about which domains are
registered — `tools/hashdomains.py`'s `DOMAINS` set MUST agree with that table exactly, and
`hashdomains.registry_agreement_diff` is the mechanical check. Core, conformance, the F2 helper and
`protocol_acceptance/tools/m11.py` MUST use that module. Adding a domain MUST be an edit to the registry table
and to `DOMAINS` together.

WHY: Domain separation binds bytes to their intended role; a shared construction prevents helpers from silently disagreeing about content identity. A single authoritative table, checked against the module that implements it, prevents a normative prose list from drifting out of step with either.

CHECKED BY: `hashdomains.py` supplies the construction and `registry_agreement_diff` (table-vs-`DOMAINS` agreement, run by its own `--selftest`); `check_core.check_record_hashes` recomputes every resolvable record hash on every validation path, and `check_core.check_spec` recomputes external `normative-reference:` digests under every profile. `check_core.check_reference_evidence` owns manifest admission and `check_core.check_subject` owns components recomputation. Core, conformance and `protocol_acceptance/tools/m11.py` use the shared module (the M11 switch (2026-09-24) — m11.py's own construction was removed, its domain-name list and `sha-512:<hex>` wire form stayed); `check_execute.py` retains only recipe execution.

**Validation examples:** `b16-*`: wire-form validation for every registered domain; `b16-registry-agreement` (table
matches `DOMAINS`) and its able-to-fail control (a dropped domain is caught).

**Representation:** No separate domain twin is assigned; a ledger MUST preserve each digest with its domain and wire form unchanged.

### B17 — Refine-only bindings

RULE: For every loaded binding chain, `admits(child) ⊆ admits(parent)` MUST hold.
Identity kinds MUST narrow and MUST NOT substitute for their parent's kinds. Carriers,
inputs and constraint forms MUST be additive; this requirement is documented but is
NOT mechanically checked in `/0`. Binding modules MUST construct
`check_child = check_parent ∧ delta`. Meanings MUST NOT inherit. A leaf MAY add a
cross-product constraint (D1/A1 6c). A binding-declared over-claim guard (B9) MUST be
inherited by every leaf under that binding's node.

WHY: A child binding must remain interpretable under its parent’s contract; another meaning is a sibling, not an opportunity to weaken inherited artifact constraints.

CHECKED BY: `check_core.check_binding_chain` (admission subset and identity narrowing); child-check composition by binding-module construction. Carrier/input/constraint-form additivity is a stated residual.

**Validation examples:** `b17-*`: child widens admitted kinds or substitutes identity kinds; no mechanical additive-carrier/input fixture is assigned.

**Representation:** No distinct inheritance twin is assigned; a ledger MUST retain the binding path and obey the same loaded chain.

### B18 — One grammar, two representations

RULE: `acceptance_grammar.py` MUST be the class vocabulary module consumed by both
`check_core.py` (TOML) and `check_ledger.py` (Markdown). BOTH representations MUST parse
and preserve `applicability`, `applicability_reason`, `gaps`, `read_at_digest`,
`slice_boundary`, and typed locators in their respective claim, header or coverage
positions. The parity harness MUST add one paired case per new field. Grammar and both
class-checking halves MUST move together, as one module consumed by both representations.

WHY: A human-readable twin must not grant a claim that the structured representation refuses, or silently discard a class field that changes its interpretation.

CHECKED BY: `check_parity_selftest` with `acceptance_grammar.py`, `check_core.py`, and `check_ledger.py`.

**Validation examples:** One paired case per new field (no concrete B18 fixture names supplied): applicability, applicability reason, gaps, read-at digest, slice boundary and typed locators. Dropping or changing any of these in the twin violates parity.

**Representation:** This rule is the twin contract: the shared grammar and paired checks MUST preserve the class field set and verdict meaning.

### B19 — Spec inventory coverage

RULE: When `[spec].inventory` is present, it MUST name a repository-contained (B6) TOML
document, and `[spec].inventory_digest` MUST be a registered `inventory:sha-512:<128-hex>`
digest (B16), recomputed over that document's bytes; a mismatch MUST FAIL. The document
MUST declare `[inventory]` with nonempty `id`, `title` and `source` (the spec document's
path or URI; `source_digest` and `numbering` MAY also be present as free text), and one or
more `[[item]]` rows, each with a stable `id` matching `[A-Za-z0-9][A-Za-z0-9._-]*` unique
within the document, a nonempty `title`, and optional `ref`, `firmness` (`"draft"` or
`"firm"`, default `"firm"`) and `parent`. Every declared item id MUST be named by the
`clause` of at least one claim in this manifest — including a `not-applicable` or
`excluded` claim under B5 — and an item id absent from every claim MUST FAIL, naming the
missing ids. A claim's `clause` MUST name a declared item id UNLESS the claim carries
`addition = true`, in which case its `clause` MUST NOT match a declared item id; such an
addition claim MUST be counted and reported separately from inventory coverage, never
silently merged into it. When `[spec].inventory` is absent, this rule adds no check —
existing manifests need no change; the acceptance protocol's contracts require it later
(`protocol_acceptance/spec/protocol.md`).

A conformance `<standard-id>.clauses.toml` (profiles/conformance/standards/) is expressible
as this shape without migrating it: `[standard]` corresponds to `[inventory]` (`id`↔`id`,
`title`↔`title`, its `edition`/`provenance`/`slice`/`slice_note` folding into `source`/
`numbering` free text), and each `[[clause]]` corresponds to an `[[item]]` (`id`↔`id`,
`ref`↔`ref`, `title`↔`title`); `force` and `side` have no B19 equivalent and remain
conformance's own vocabulary. This is a documented mapping, not a migration: conformance
keeps its own C1 bijection and its own inventory loader unchanged in `/0`.

WHY: A spec with no inventory cannot show that everything asked for was addressed, or that
nothing unasked was silently added. Pinning the inventory by digest and requiring every
item, and every addition, to appear as a named row makes both omission and unrequested
extension visible instead of implicit.

CHECKED BY: `check_core.check_inventory`; digest construction and wire form by
`hashdomains.py` (B16, domain `inventory:`); generator and drift report by
`tools/spec_inventory.py`.

**Validation examples:** `b19-*`: missing digest, malformed digest, digest mismatch, missing `[inventory]`
header field, zero items, duplicate item id, invalid item id grammar, invalid firmness
token, malformed optional field, an item with no citing claim, a claim citing an id
outside the inventory without `addition`, `addition = true` on a claim whose `clause`
names a declared item id. Positive cases: full coverage with no additions, full coverage
plus a reported addition row, optional `ref`/`parent`/`firmness` fields parsed, and a
manifest with no `[spec].inventory` at all (unaffected).

**Representation:** No separate B19 twin is assigned. `[spec].inventory` and `[spec].inventory_digest`
are `[spec]`-level fields, like the pre-existing `axis` and `external`, and are not part of
B18's claim/header field list; a claim's `addition` field is likewise not added to that
list.

### B20 — Typed toolchain and build-input identity

RULE: An evidence record MAY carry `toolchain`, a nonempty list of tables
`{ name, version?, commit?, digest? }`: `name` MUST be a nonempty string; `version`, when
present, MUST be a nonempty string; `commit`, when present, MUST be 40 lowercase
hexadecimal characters; `digest`, when present, MUST be a registered
`artifact:sha-512:<128-hex>` wire digest (B16); at least one of `commit` or `digest` MUST
be present on every entry. An evidence record MAY carry `build_inputs`, a nonempty list of
tables `{ path, digest }`: `path` MUST be a nonempty, B6-contained pointer, and `digest`
MUST be a registered `artifact:sha-512:<128-hex>` wire digest. The validator MUST recompute
that digest over the pointed-at file's bytes when the pointer resolves and MUST FAIL on
mismatch; an unresolvable `path` MUST receive the same treatment B6/B16 already give an
unresolvable native `record` pointer — WARNING, error under `--strict`. `captured_at_commit`,
when present on an evidence record, MUST be 40 lowercase hexadecimal characters; a shorter
value MUST be an ERROR — 0.3.0 admits no compatibility shim for a prior shorter form. A
binding MAY declare `required_build_inputs`, a list of repository-relative paths, through
the same machine-readable declaration mechanism as `admits`/`identity` (B14/B17); for a
weighted claim under that binding, once any evidence record on the claim carries a
`build_inputs` list, the union of declared paths across that claim's evidence MUST include
every required path. A weighted claim declaring no `build_inputs` at all MUST NOT trigger
this guard — mirroring B9's nonempty-guard shape. This class rule fixes the metadata shapes
and the required-build-input guard's general form; the concrete required paths and the
guard's own rule id belong to the binding that declares them (see that binding's own
document).

WHY: A free-text tool string and a declared-but-undigested input set cannot show that a
weighted claim was checked against the exact toolchain and dependency graph a producer
names; typed, digested entries make that identity checkable without inventing trust
arithmetic the class does not otherwise carry. A full commit is the same identity
granularity B1 already requires for the certified subject itself — a shorter form names an
ambiguous, non-unique prefix, not a fixed point in the tree. An opt-in-complete guard lets
an artifact-kind's own required inputs live where that kind is understood, without
retroactively failing a manifest that has not adopted the new fields.

CHECKED BY: `check_core.check_evidence_record` (shape, via `check_core.check_code_identity_shape`);
digest construction and wire form by `hashdomains.py` (B16, domain `artifact:`);
`check_core.check_build_input_hashes` recomputes every resolvable `build_inputs` digest, on
every validation path; the declaring binding's own module (e.g. `bindings/code_rust.py`)
owns the `required_build_inputs` guard.

**Validation examples:** `b20-*`: toolchain missing `name`; toolchain entry with neither `commit` nor `digest`;
toolchain malformed `commit`; toolchain malformed `digest`; empty `toolchain` list;
build_inputs entry missing `path`; build_inputs entry with a malformed `digest`;
build_inputs digest mismatch against the pointed file; empty `build_inputs` list;
`captured_at_commit` shorter than 40 hex. Positive cases: a full `toolchain` entry using
`commit` only, one using `digest` only, a resolvable `build_inputs` digest match, and a
full 40-hex `captured_at_commit`. The binding-declared `required_build_inputs` guard's own
coverage is that binding's fixture set (e.g. `bindings/code_rust.py`'s selftest).

**Representation:** No B20 twin is assigned; these evidence-record fields are not added to B18's
claim/header field list.

### B21 — Evidence-only assurance metadata: coverage metric and tool qualification

RULE: An evidence record MAY carry `coverage`, a table `{ metric, value, of? }`: `metric` MUST
be one of the registry `statement`, `branch`, `decision`, `mcdc`, `proof-obligation` (roughly
DO-178C-inspired, weakest to strongest, plus a fifth token for a fully deductive proof
obligation); `value` MUST be a number in the closed interval `[0, 1]` — a FRACTION, never a
percent: B7 already bans the field name `percent`/`percentage` unconditionally, and this rule
deliberately never introduces a second spelling of the same forbidden shape; `of`, when present,
MUST be a nonempty string naming what was counted (free text, e.g. "decisions in fn parse_der"),
a disclosure never a second score. An evidence record MAY carry `tool_qualification`, a table
`{ level?, basis }`: `basis` MUST be a nonempty string; `level`, when present, MUST be a nonempty
string. Both tables are closed to exactly their named keys; an extra key is an error. Neither
field is validated for truth or for whether the qualification argument holds — 0.3 declares shape
only, matching the class's standing refusal to prove evidence truth (§5, "It does not prove
evidence truth, clause-inventory faithfulness, recipe adequacy...").

WHY: A consumer demanding structural or proof-grade assurance (DO-178C's
statement/decision/MC-DC ladder, DO-333's formal-method substitution) has no way today
to see what fraction of what was actually exercised, or whether the tool that produced or checked
the evidence is itself qualified for the job — two clean format gaps (structural/proof-
coverage metric floor; tool/verifier-qualification floor). A closed metric registry and a bounded
fraction make the coverage claim checkable in shape without inventing trust arithmetic the class
does not otherwise carry (B7); a free-text qualification `basis` records the argument without the
class adjudicating it, the same disclosure-not-score pattern `calibration` (B7) already uses.

CHECKED BY: `check_core.check_evidence_assurance_shape`, called from `check_evidence_record` on
every evidence record.

**Validation examples:** `b21-*`: `coverage` not a table; `coverage.metric` outside the registry; `coverage.value`
outside `[0, 1]` (over one, negative, non-numeric, a boolean); `coverage.of` present but empty;
`coverage` carrying an unknown field; `tool_qualification` not a table; `tool_qualification.basis`
missing or empty; `tool_qualification.level` present but empty; `tool_qualification` carrying an
unknown field. Positive cases: a full `coverage` entry with and without `of`, a `tool_qualification`
entry with and without `level`, both fields present on the same record, and a record carrying
neither (unaffected).

**Representation:** No B21 twin is assigned; `coverage` and `tool_qualification` are not added to B18's
claim/header field list — they are evidence-record fields only.

## §4 Verdict table (B11, verbatim)

| condition | verdict | exit |
|---|---|---|
| any class (8a) error | FAIL | 1 |
| zero `[[claim]]`, or `claims_total ≠ len(claims)` | FAIL | 1 |
| root unresolvable / a dereferenced document missing, unreadable or unparsable (native evidence payloads follow B6) | INDETERMINATE | 2 |
| any claim in evaluation state `indeterminate` | INDETERMINATE | 2 |
| profile prefix unknown, or unknown suffix regardless of scoping flags | INDETERMINATE | 2 |
| known leaf id with a missing 8b half and no scoping flag | INDETERMINATE | 2 |
| any 8b error (meaning or binding) | FAIL | 1 |
| every claim `not-applicable` (retrospective) | INDETERMINATE ("nothing applicable") | 2 |
| `[subject].mode = "prospective"` (any claim counts — the subject is not certified) | PASS-PROSPECTIVE | 0 |
| zero `evidenced`/`partial` claims (F4) | PASS-PROSPECTIVE | 0 |
| scoping flag used for a known leaf id with a missing 8b half, all available checks pass | PASS-MEANING-ONLY / PASS-BINDING-ONLY | 0 |
| otherwise | PASS | 0 |

A scoped verdict keeps the prospective qualifier when F4 applies (`PASS-PROSPECTIVE` wins over a scoped
PASS; the scope is printed as a note). Multiple files: FAIL > INDETERMINATE > any PASS.

The prospective row resolves B1's ceiling: a prospective subject's manifest never reads as plain PASS, whatever its claim counts.

## §5 What the class deliberately does not do

- It does not cryptographically sign records; signing is a separate substrate. [A-01]
- It does not automatically derive `clauses_total` from arbitrary governing prose.
  A meaning may check a structured inventory, but the generic declared-total limitation remains. [A-02]
- It does not supply trust arithmetic or aggregate cross-file/workspace certification.
  One subject has one manifest; B8 borrows exact records without adding an aggregate verdict. [A-03]
- It does not prove evidence truth, clause-inventory faithfulness, recipe adequacy or the
  reality of a reported perturbation merely by checking their fields. [A-04]
- B19 does not generate a spec inventory from prose, require exactly one claim per item
  (a meaning MAY narrow that, as conformance's C1 already does for clause inventories), or
  prove that the inventory faithfully represents the spec document it is pinned to —
  `tools/spec_inventory.py` is a producer-side generator run out of band, not a class check. [A-05]
- It does not admit B8 claim-discharge mode, create the parked intent meaning or the
  pending built-artifact node, or mechanically check carrier/input/constraint-form additivity. [A-06]
- B21 does not validate that a declared `coverage.value` is true, that the counted `of` set is
  complete, or that a declared `tool_qualification` argument actually holds — shape and registry
  membership only; a consumer floor comparing against these fields (the protocol contract's
  `coverage_min`) is a protocol-side concern, not a class check. [A-07]
- Design rule 6's "never reused across publication history" (§2) is checkable by a
  single-manifest validator only as in-file uniqueness — no id ever repeats within the ONE
  manifest under validation. Whether the same id is later reused in a DIFFERENT, later
  manifest, across the subject's whole publication history, is not something a single-file
  check can see; that cross-manifest guarantee rests on the producer, not a mechanical class
  check in `/0`. [A-08]
- Validating a manifest against this text publishes nothing, signs nothing and ratifies nothing.
  Ratification of the class is an act of the class's owning authority, outside any check here. [A-09]
- It does not strengthen subject identity beyond what the subject declares: a revision identity is
  trusted as the version-control system reports it; a content digest or components identity (B1)
  is the stronger form where a consumer needs one. [A-20]
