# The acceptance manifest — format v0 (`acceptance/0`)

## Overview — orientation only; every rule below is stated in its own section

**Normative for the manifest itself:** the `acceptance.toml` data model — tables, fields, types,
closed vocabularies — plus the design rules binding v0, the M11 content-hash construction, and the
reserved hooks. What a claim must carry to be *weighted* is `core.md`; evidence-record
admissibility is `evidence-types.md`.

**Map.** Design rules 1–7 · stability of `acceptance/0` · the schema block (the whole data model in
one listing) · the generated schema artifact · `shape` · `[subject].kind` · `[subject].record_root`
· tagged number-XOR-null values · `[format]` self-location · content-hashing (M11) · reserved hooks
H1–H8 · what v0 deliberately does not do.

**Read first:** the design rules, then the schema block. Each section after them does one of five
things: constrains a single field, states a construction over several (the M11 content-hash), rules
how the schema artifact is generated from the validator, reserves a slot no engine in this revision
reads, or records what v0 deliberately does not do.

The unit of the format is the **claim**: *(spec clause, code item, evidence, assumptions)*. A
manifest is the complete set of claims made about one subject artifact, with gaps listed
explicitly. A manifest never says "correct"; it says *conforms to spec S, under assumptions A,
checked by evidence E, reproducible with toolchain T* — and where it doesn't, it says that too.

One file per subject: `acceptance.toml`, TOML, checked by `tools/check_acceptance.py`. The
validator's general contract — three mutually exclusive states, `valid`/`invalid`/`indeterminate`,
each its own exit code — is stated once, normatively, at `core.md` §8.3; every
validator-obligation rule in this document (the bundle-shape rule, the kind-registry fail-closed
rule, design rule 4a's binding check) resolves into that same tri-state rather than restating it.

## Design rules (binding for v0)

1. **Gaps are first-class.** A spec clause with no admissible evidence appears as a claim with
   `status = "gap"`. Omission is the only forbidden state. The `[coverage]` block declares the
   total clause count so silent omission is detectable.
2. **Evidence is admissible or it is nothing.** A record missing its required provenance fields
   (see `evidence-types.md`) is an *assertion*, not evidence — the validator rejects it. This is
   the export-json discipline generalized: status alone is not a result; "what was checked, under
   which semantics, by which build" is the result.
3. **No trust numbers in v0.** Bands are *floors on evidence type* (see `assurance-bands.md`).
   The fields `alpha` / `beta` / `lr` are reserved and REJECTED unless they carry a
   `calibration` reference — asserted-not-measured numbers look precise and are worse than
   labels. Ledger arithmetic (correlation-discounted log-odds) is a later layer over the same
   records, added only when measured calibration exists.
4. **The certificate binds to exact content.** `subject.commit` is required; a dirty tree must
   say `dirty = true`. A manifest that cannot name what it certifies certifies nothing.
4a. **Evidence-subject binding is checked, and a mismatch is a hard error, unconditionally.**
   The manifest names its subject's own content identity once, as an OPTIONAL self-describing M11
   hash: `[subject].subject_hash` — computed under the `subject:` domain (Content-hashing (M11),
   below) — a distinct field from the git-domain `[subject].commit`
   (rule 4, above). Any `[[claim.evidence]]` record MAY carry its own `subject_hash`, naming which
   subject content that record's `result` was actually computed against; where a record's
   `subject_hash` is present, it MUST equal `[subject].subject_hash` exactly. **A
   present-but-unequal pair is an error at validation time, not a reviewer finding.** This is the
   one item in this document that ships as a *shipping* validator obligation rather than a
   reservation: `tools/check_acceptance.py` MUST refuse a manifest containing such a mismatch,
   exactly as it refuses a manifest with an out-of-vocabulary `grade` token. This closes the class
   of overclaim where evidence is bound to the wrong object by construction rather than by review
   (the demonstrated der `U1`/`E-1` 203-proofs-against-the-wrong-object case). `[subject].subject_hash`
   is **OPTIONAL** in this revision — absent, there is nothing for an evidence record's
   `subject_hash` to be checked against, and the check does not fire; when present, every evidence
   record naming a `subject_hash` is held to it.

   **`[subject].commit` is a separate, git-domain identity field and is NEVER compared against an
   M11 hash.** A git commit sha is SHA-1 over a different object (the repository tree) than an M11
   content-hash (SHA-512 over one artifact's own raw bytes, domain-separated, below) — comparing
   the two across algorithms and across objects is a category error, not a stronger check. An
   earlier draft of this rule compared an evidence record's content-hash directly against
   `[subject].commit`; that comparison is retracted for exactly this reason. `[subject].commit`
   remains required (design rule 4) and is checked exactly as before, independently of anything in
   this rule; `subject_hash` binding, where declared, is a second, dimensionally-consistent
   identity check over M11-domain hashes only. (Cross-referenced from `evidence-types.md`'s
   `record_hash`/`subject_hash` field descriptions.)
4b. **Label-binding — name↔statement correspondence — is a SHOULD, not a validator error.** A
   claim's `id` and its `statement` SHOULD name the same thing a reader would independently derive
   from its evidence's `ref` (the harness/theorem/test id) — a claim named `A-001` with statement
   *"decode rejects non-minimal integer encodings"* whose sole evidence `ref` is
   `verify_sequence_length` is a label-binding smell. This is **not** mechanically checkable in
   general (matching a claim id against a harness name by string similarity produces both false
   accusations and missed cases, the same shape §7.2's declarative-only detection already rejects
   for predicate items in `core.md`) — it is reviewer work, named here so it is reviewed for,
   not silently assumed.
5. **Producer never self-overrides.** A manifest records what gates said, it does not adjudicate
   them. `result = "fail"` and `result = "unsupported"` are recorded as-is (they demand opposite
   actions: investigate vs park — never conflate them).
6. **Claim ids are stable and never reused**, same law as spec clause ids. Supersession is a new
   id plus `supersedes = "<old>"`, never edit-in-place of a published id.
7. **No ledger, view, S, or independence property is stated as a property of the FORMAT until its
   machinery exists.** A stripped revision that imports a thesis's strongest claims without their
   checks is the exact defect this format polices. Where this document reserves a hook ("Reserved
   hooks", below), it is named **as a reservation, in so many words** — "reserved for a later
   engine," never "computes," "decides," "aggregates," or "guarantees." Concretely, this document
   must never say: that the format computes, aggregates, or discounts trust (rule 3 already
   forbids this for numbers; this extends it to every reserved hook); that a struck assumption
   (`[[claim.assumes]]`) is removed from a rendered view or a computed count today; that a
   `[[defeater]]`'s closed effect algebra describes current validator behaviour rather than a
   future dispatcher's obligations; that any claim is "independently corroborated" or
   "cross-verified" by a reserved independence edge; that a generated view or rendering is
   guaranteed complete or non-hallucinating; that an attestation (`[[attestation]]`) makes a claim
   "more verified" (standing can never raise the epistemic axis, `epistemic_tier`); that the
   `epistemic_tier`/grade coherence rule (`core.md` §2) ranks one claim's evidence against
   another's; or that the evidence-subject binding check (rule 4a) says anything about whether the
   evidence is a *good* check of the object it is bound to. A reserved hook is a slot name whose
   shape is fixed only as far as stated — never something a producer should populate expecting it
   to be read for a verdict.

## Stability: `acceptance/0` is UNSTABLE-UNTIL-FROZEN

The `[format].id` string does not bump its integer on every rule tightening (added 2026-08-22, F5
— the control gate, the per-band control-kind whitelist, the carrier-family check, and other
tightenings all landed under the SAME id, `"acceptance/0"`). This is deliberate, not
an oversight: while the format is a working draft (see the status banner), a manifest's producer
and the validator (`tools/check_acceptance.py`, this repo) are expected to move in
lockstep. A manifest is meaningful only **against the validator
sha recorded beside it** — not against "whatever `acceptance/0` meant on some other day." Bumping
the id integer on every tightening would launder that instability as if it were a stable public
contract — a lie in the opposite direction from silently tolerating drift. The id bumps only when
the format is deliberately declared FROZEN for external consumption; until then, `acceptance/0`
names an *evolving, validator-defined* contract, and pinning a manifest to the validator's git sha
at production time is the only real stability guarantee this format offers.

## Schema

```toml
[format]
id            = "acceptance/0"          # exact string; breaking change bumps the integer
shape         = "single-file"           # single-file | bundle. REQUIRED from this revision.
spec_id       = "acceptance-format"     # REQUIRED: which contract this manifest is written against
spec_sha      = "<40-hex>"              # REQUIRED: the spec commit/tag this manifest targets
validator_sha = "<40-hex>"              # REQUIRED: the validator commit that checked this manifest
generated_by  = "check_acceptance.py@<sha>"   # REQUIRED: generator id + version, or "hand-authored"
generated_at  = "2026-08-27T00:00:00Z"  # REQUIRED: ISO 8601
illustrative  = false                   # OPTIONAL, defaults to false (core.md §0.6): true =
                                         # a teaching example, not a certificate

[subject]
name   = "rs-verified-der"   # the artifact this manifest certifies
kind   = "rust-crate"        # rust-crate | rust-workspace | doc | tool | ml-model | dataset |
                              # spec | design | agent-output | other
commit = "<40-hex sha>"      # required; the exact content certified (git-domain identity —
                              # SHA-1 over the repository tree, NEVER compared against an M11
                              # hash; see design rule 4a)
dirty  = false               # true = uncommitted changes were present; say so
# subject_hash = "sha-512:<128-hex>"   # OPTIONAL (design rule 4a): the M11 content-hash of the
                              # subject artifact, under the `subject:` domain (Content-hashing
                              # (M11), "subject: domain", below). Single-file subject: hash of the
                              # file's raw bytes; multi-file subject: bundle-root-style inventory
                              # hash over the subject tree (not yet computed by this revision's
                              # tooling — see that section). When present, every
                              # [[claim.evidence]] record naming a `subject_hash` MUST equal this
                              # value exactly — a mismatch is a hard error.
# record_root = "../rs-verified-der"   # OPTIONAL (rs-verified-der migration audit): the base path
                              # every `record` pointer on THIS manifest resolves against, instead
                              # of the manifest file's own directory. Absent = manifest-relative
                              # (unchanged behaviour). Absolute or manifest-relative filesystem
                              # path. Exists because a manifest and its subject's evidence files
                              # routinely live in different repositories — without it, every
                              # `record` pointer in such a manifest is unresolvable by
                              # construction, independent of whether the cited evidence is
                              # otherwise real. A portable manifest SHOULD
                              # declare `record_root` repo-relative and rely on `repo`/`commit`
                              # below for the context a reader needs to make it absolute.
# repo = "github.com/example/rs-verified-der"   # OPTIONAL: an identifier for the subject's own
                              # repository, for a reader's context alongside `commit`/
                              # `record_root` — not validator-interpreted (no fetch, no clone, no
                              # resolution against it in this revision).

[spec]
path    = "SPEC.md"          # the governing spec document (repo-relative or absolute)
version = "<sha|tag>"        # the spec version the clause ids below refer to
# axis     = "..."           # REQUIRED once ANY claim in the file claims weight (core.md §6/W2);
#                            # optional in a wholly unweighted manifest. What the item list enumerates —
#                            # declared because the axis choice determines which gaps are even
#                            # expressible (a module-shaped axis has no row for a cross-cutting rule)
# external = ["RFC 5280"]    # OPTIONAL: normative references that are not in the tree

[coverage]
clauses_total = 17           # total clause count in spec@version — makes omission detectable
claims_total  = 17           # must equal the number of [[claim]] entries
# Where the subject has no clause-addressable specification, clauses_total equals claims_total
# by construction and the coverage figure carries no information beyond the claim count; such
# manifests SHOULD say so in this [coverage] comment.
# denominator = "complete"   # OPTIONAL (coverage-ledger.md): complete | slice. "slice" scopes the
#                            # omission-detection guarantee to inside the ledger, and requires
#                            # slice_note. Declaring a real total you do not have is worse than
#                            # saying it is a slice.

[[claim]]
id        = "A-001"          # stable, unique in file, never reused
clause    = "S-3.2"          # spec clause id
item      = "src/integer.rs::decode"   # code item the claim attaches to
statement = "decode rejects non-minimal integer encodings"
band      = "A3"             # asserted floor: A0..A4 (see assurance-bands.md)
status    = "evidenced"      # evidenced | partial | gap | parked | blocked
# parked requires:  parked_reason = "..."   (e.g. "kani unsupported_construct — tool change needed")
# blocked requires: blocked_by    = "..."   (core.md §7.3, P4 adopted 2026-08-25) — the item is
#                              # NOT REACHABLE with the tool at all, which is an escalation and not
#                              # a backlog entry. Like gap/parked it carries NO evidence records.
# status x grade must COHERE (core.md §7.1): gap/parked/blocked may not carry a grade that says a
#                              # check succeeded, and evidenced/partial may not carry not-covered or
#                              # out-of-scope. An error on a weighted claim, a warning otherwise.
# item_kind = "predicate"     # OPTIONAL, defaults to "item" (core.md §7.2, P3 adopted): an item
#                              # that ranges over a SECOND list, whose honest status is a fraction.
#   over    = "the 33 production harnesses in module X"   # REQUIRED with item_kind = "predicate"
#   covered = "0/33"                                      # REQUIRED, N/M with N <= M
#                              # A weighted predicate claim missing either is REFUSED WEIGHT.
weight    = "unweighted"     # OPTIONAL, DEFAULTS TO UNWEIGHTED (core.md W1): weighted |
                              # unweighted. "weighted" asks the format to vouch for this claim and
                              # switches on the whole anti-overclaim machinery below; omitted means
                              # unweighted, which promises nothing. The format never vouches by
                              # silence. Every "REQUIRED" in this schema below is required OF A
                              # WEIGHTED CLAIM — W3 puts no obligations on the unweighted tier.
grade     = "contract"       # REQUIRED on a weighted claim, OPTIONAL on an unweighted one
                              # (added 2026-08-22, M6; vocabulary closed at nine tokens 2026-08-25 —
                              # core.md §1 is normative):
                              #   contract | probe | test-only | mechanical | not-covered |
                              #   out-of-scope        — weight-eligible
                              #   inspection-argued | unspecified | ungraded   — never weight-eligible
                              # This list is CLOSED. A token outside it is an error, not a style
                              # choice, and so is a compound cell ("mechanical, gate-enforced").
                              # band = how good is the evidence; grade = does it decide the item.
                              # A high band with grade = "probe" is the most misreadable state in
                              # a manifest, and before this vocabulary it could not be written down.
# clause_source = "doc-comment"  # OPTIONAL in general, REQUIRED on a weighted claim (core.md W2):
                              # spec-document | external-standard | doc-comment | test-name | none.
                              # The last two are RESERVED TO MEAN UNWEIGHTABLE — a clause read off
                              # its own evidence, or off nothing, cannot carry weight because
                              # nothing could falsify it. They are warned rather than forbidden at
                              # the unweighted tier: forbidding them just produces invented prose
                              # (B1). See CLAIM-CLASSES-AWAITING-WEIGHT.md C5.

  # [claim.self_verify]      # REQUIRED, with a nonempty `command`, whenever grade is one of
                              # contract | probe | test-only | mechanical | not-covered
                              # (core.md §3) — every grade that asserts a check was, or was not,
                              # performed. Optional otherwise. The consumer-side recipe.
  # command = "cargo kani --harness sequence::proofs::no_over_read"
  # expect  = "VERIFICATION: SUCCESSFUL, and both kani::cover lines satisfied"  # required with command
  # precondition     = "..."  # optional freshness/environment guard
  # expect_stream = "stdout"  # OPTIONAL, DEFAULTS TO "stdout" (core.md §8.2): which stream
                              # --execute matches `expect` against. stdout | stderr | combined.
                              # A row that legitimately needs stderr says so ON THE ROW; matching a
                              # combined stream made every warning and backtrace a place for the
                              # expected string to turn up.
  # positive_control = "..."  # REQUIRED, unconditionally, when grade = "not-covered"
                              # (core.md §4) — a grep zero is a claim about your pattern, not the
                              # code. It also serves as THAT GRADE'S watched_fail witness (§4.1
                              # witness 3) — and no other grade's: on a contract row, "this command
                              # can match something" says nothing about whether the proof would
                              # notice a broken implementation.

  # [claim.self_verify.watched_fail]   # A TABLE (structured 2026-08-25 — it was free text, and
                              # `watched_fail = "x"` satisfied W2.5). REQUIRED on a WEIGHTED claim
                              # whose grade asserts a check was performed (core.md §4.1, P2).
                              # Satisfied instead by an observed-red [control] block on one of this
                              # claim's own evidence records, or (on not-covered) by
                              # positive_control. A recipe nobody has watched fail is not a
                              # deciding recipe.
  # of_command = "<the same command as self_verify.command>"  # REQUIRED. The binding: a control
                              # over a different check witnesses nothing about this one. Compared
                              # with WHITESPACE NORMALIZED (runs of spaces/newlines collapse), so
                              # a re-wrapped copy still binds; nothing else is normalized, and the
                              # quoting must stay literal -- `--harness a` and `--harness "a"` are
                              # different commands and do not bind.
  # perturbed  = "reverted the AtomicBool latch to an error-channel abort"   # REQUIRED, a phrase
  # observed   = "4 of 6 permutation tests fail, including a_genuine_error..."  # REQUIRED, a phrase
  # date       = "2026-08-24"  # REQUIRED, ISO — a recipe watched to fail last year may not
                              # discriminate today. Shape is all that is checked: that the
                              # perturbation was really made is reviewer work (core.md §4.1).
  # PERMITTED on status = "gap"/"parked", unlike [[claim.evidence]]: a recipe is not evidence, it
  # is the command that shows the gap is real. This is the one widening this facet makes.

  [[claim.evidence]]         # >=1 required for evidenced/partial; forbidden for gap/parked
  kind      = "kani-harness" # from the registry in evidence-types.md
  family    = "bmc"          # bmc | kernel | smt-refinement | dynamic | mechanical | judgment
  ref       = "verify_integer_minimal"       # harness/theorem/test id — the checkable name
  result    = "pass"         # pass | fail | unsupported
  tool      = "kani@d4df833c8f8f"            # tool identity AT BUILD GRANULARITY (commit, not version)
  bounds    = "bounded: unwind=16"    # REQUIRED to start with the token "bounded" or "unbounded"
                              # (core.md §5's boundedness declaration, extended to evidence
                              # records); free text naming the actual limit is welcome but, unlike
                              # the claim-level `bounds` field, not mandatory at this granularity
  semantics = "-Z function-contracts"        # flags/semantics in force; "" is an explicit claim
  record    = "evidence/kani-2026-08-18.json"  # pointer to the raw run record
  record_hash = "sha-512:<128-hex>"          # REQUIRED on a WEIGHTED claim's evidence (P9);
                              # OPTIONAL on unweighted. The evidence-record-domain M11 hash of the
                              # `record` file above; the validator recomputes and compares on any
                              # non-illustrative manifest. A present-but-mismatched value is
                              # ALWAYS an error (evidence-types.md); illustrative manifests stay
                              # shape-only (CS-21/22) and skip both the recomputation and the
                              # required-on-weighted obligation.
  # subject_hash = "sha-512:<128-hex>"       # OPTIONAL: which subject content this record's
                              # `result` was actually computed against (design rule 4a). When
                              # present, MUST equal [subject].subject_hash exactly.
  # per-kind extra requirements: evidence-types.md
  # control block (OPTIONAL, family-agnostic — assurance-bands.md rule 6 / evidence-types.md):
  #   [claim.evidence.control]
  #   kind        = "mutation"   # mutation | ablation | planted-twin
  #   expectation = "red"        # red | green | sat
  #   observed    = "red"        # only a literal red/red band-lifts (assurance-bands.md rule 6, F1)
  #   of_claim    = "A-001"      # MUST equal the id of the [[claim]] this record is under

  [[claim.assumes]]         # OPTIONAL, repeatable: the typed upgrade of the free-text
                              # "assumptions" element this file's opening paragraph names.
  id        = "AS-1"                 # stable, unique within the claim, never reused
  statement = "the input buffer is UTF-8 valid before decode() is called"
  void_if   = "a caller path is found that invokes decode() on non-UTF-8 input"  # REQUIRED
  # defeater = "D-4"                 # OPTIONAL: id of a [[defeater]] (Reserved hooks, H4) this
                              # assumption is coupled to
```

Each `[[claim.assumes]]` record states one assumption the claim's evidence depends on and a
`void_if` trigger — the condition under which the assumption is known false. No new parallel
element is created; this is the "assumptions" this file's opening paragraph already names, made
structured.

**The void-not-discount invariant (stated now; not enforced by any engine in this revision).** A
`[[claim.assumes]]` record whose `void_if` condition is known to hold **VOIDS** the claim it is
attached to — it does not discount, weaken, or lower a score. A claim resting on a voided
assumption has **no** evidence for the purposes any future ledger reads; design rule 3 (no trust
numbers without calibration) already refuses to compute a number here, so this invariant is
presently a naming and a promise, not a computation: **this revision reserves the field and states
the invariant; it ships no propagation engine.** A future engine that discounts rather than voids a
struck assumption is non-conforming, whenever it is built. (core.md §0.5's terms table
cross-references this paragraph.)

## The schema artifact

The `[format]`/`[subject]`/`[spec]`/`[coverage]`/`[[claim]]` schema shown in prose above also
ships as a machine-readable artifact: `schema/acceptance-0.1.0-draft.schema.json`, a JSON Schema
(draft 2020-12), **generated** by `tools/emit_schema.py` from live imports of
`tools/acceptance_grammar.py` and `tools/check_acceptance.py`'s registries — never hand-written,
so a closed vocabulary cannot say one thing in the schema file and another in the validator that
actually enforces it. `maintainers/OBLIGATIONS.md`'s own reason for existing ("a rule cannot drift
between checkers, because there is only one of it") extends to this artifact exactly as it does to
`acceptance_grammar.py` itself.

**Shape-normative vs semantics-normative, stated once, here.** The schema artifact is
**shape-normative**: table/field presence, field types, and closed-vocabulary membership. It is
**not** semantics-normative — every constraint spanning more than one field (status/grade
coherence, band reachability, a control's carrier-family compatibility, the F4 result/observed-red
contradiction guard, record/subject hash recomputation and binding equality, weight-conditioned
requiredness, phrase floors, cross-claim id uniqueness, filesystem existence of a `record`
pointer) is **semantics-normative**, stated in `core.md`/this document's prose, and enforced only
by `tools/check_acceptance.py`. The schema does not attempt these; each is instead named, by id,
in the schema's own `x-semantic-only-rules` array and in the affected field's `description` —
"semantic rule, enforced by the validator; see spec/&lt;file&gt; §X" is the schema's own wording for
every one of them. A reader or a third-party tool that validates only against the schema has
checked the shape contract, not the format's actual obligations.

**Drift is a gate failure, not a review note.** `gates/run_all.sh` re-emits the schema to a
temporary file and byte-compares it against the committed one; any mismatch fails the gate with
"schema drift: run tools/emit_schema.py" rather than merging a hand-edited or stale file. The
naming carries the spec version: `acceptance-0.1.0-draft.schema.json` while `core.md` is
UNSTABLE-UNTIL-FROZEN (see "Stability", above); at freeze the file is renamed
`acceptance-0.1.0.schema.json` (the `-draft` suffix dropped, no other change) — see
`docs/decisions/ADR-008-schema-as-generated-artifact.md`.

## `shape` — single-file vs bundle

`shape` states whether the manifest is complete in one file (`single-file`) or is a thin index
into a closed set of linked files under a bundle root (`bundle`). **Every subject shipped against
this revision ships `single-file`.** The token exists now, ratified, so the *definition* of
`bundle` is not underspecified later — the closed-inventory + tombstone + prev-root design (M11's
bundle-root hash construction, below) means `bundle`'s shape is already fixed; only its
*validation* is deferred:

**Validator-obligation: `bundle` returns `indeterminate`.** A manifest declaring
`shape = "bundle"` is validated **structurally only as far as its own file reaches** —
`tools/check_acceptance.py` returns `indeterminate` (core.md §8.3's tri-state contract;
nonzero, distinct exit code from `invalid`) for the file as a whole, unconditionally, until bundle
validation lands. This reserves the door with no later format-id break, without shipping unproven
multi-file machinery. `single-file` is unaffected by this rule.

## `[subject].kind` — five non-code artifact classes, and a fail-closed registry

Five kinds join the registry beside the original four: `ml-model`, `dataset`, `spec`, `design`,
`agent-output`. **This is `[subject].kind` — the artifact-class field — and is a distinct field
from `[[claim.evidence]].kind` (`evidence-types.md`'s registry column, now demoted to a hint).**
The two fields share a name and nothing else; a reader who conflates them will misapply that
demotion to this field, which is wrong — `[subject].kind` is not demoted by anything in this
revision, it is *extended*.

**Validator-obligation: the kind registry opens per profile, fail-closed.** The `[subject].kind`
registry opens **per profile**, under fail-closed rules: an unknown kind token with no profile
declaring it is `indeterminate` (core.md §8.3's tri-state contract), never silently accepted
and never silently rejected as a hard `invalid` — the format does not know whether the token names
a real, undeclared artifact class or a typo, and says so structurally rather than guessing either
way.

## `[subject].record_root` — where `record` pointers resolve

**`record_root` is OPTIONAL; its absence leaves current behaviour unchanged: every
`[[claim.evidence]].record` pointer on this manifest resolves relative to the manifest file's own
directory.** This is the fix for a gap the rs-verified-der migration audit surfaced:
`tools/check_acceptance.py` had no other mechanism to declare a separate base path for a manifest
whose subject's evidence files live in a different repository from the manifest itself — a manifest
that lives beside its own findings in one repo but cites evidence files that live in the subject's
repo has every `record` pointer unresolvable by construction, independent of whether the cited
evidence is otherwise real.

**When present, `record_root` is the base path every `record` pointer on this manifest resolves
against, instead of the manifest's own directory — nothing else changes.** `record_root` itself is
a filesystem path, either absolute or resolved relative to the manifest file's own directory (the
same directory it would otherwise default to); the validator resolves each `record` value as
`record_root / record`, both for the existence check and for `record_hash` recomputation
(evidence-types.md, P9) — the two are the same resolution, done once, not two separate mechanisms
that could drift apart. `record_root` is a per-manifest, not per-record, setting: a manifest citing
evidence across more than one external base path is not served by a single `record_root` and needs
none invented here.

**A portable manifest SHOULD declare `record_root` repo-relative, and rely on `[subject].repo` /
`[subject].commit` for the context a reader needs to make it absolute** — an absolute path bakes in
one machine's layout and is not portable across the manifest-repo/subject-repo boundary this field
exists to cross. `[subject].repo` (schema, above) is OPTIONAL and not validator-interpreted in this
revision (no fetch, no clone, no resolution against it) — it exists purely so a reader has
somewhere to look.

## Tagged values — the number-XOR-null shape

Any field whose value is either a measured number or an honestly-absent calibration
(number-XOR-null) MUST use a **tagged shape**, never a bare scalar that could be mistaken for a
low or zero measurement:

```toml
# measured:
independence_edge = { measured = 0.906, calibration = "corr-study-2026-08" }
# or, honestly unmeasured:
independence_edge = { null = "declared-null" }
```

A flat scalar (`independence_edge = 0.0`) is permitted **only** where ⊥ is structurally impossible
for that field — where every field this revision reserves under a number-XOR-null shape (the
independence edge, "Reserved hooks" H1; a calibration weight, H5) is concerned, ⊥ is always
possible, so the tagged shape is mandatory there without exception.

**Proposed canonical `⊥` wire token: `"declared-null"`.** Constraints: ASCII, greppable,
un-confusable with absent/0/low. `"declared-null"` is proposed because it is already the
vocabulary this spec's prose uses for exactly this state — `evidence-types.md`'s judgment-family
rule already reads "declared-null likelihood by convention." **This spelling is a proposal
pending owner ratification, not yet a ruled fact**; any ASCII, greppable alternative that is not
confusable with `null`/`0`/`""` satisfies the constraint equally, and it may be changed without
reopening the tagged-shape rule itself.

## `[format]` self-location — a frozen manifest must be answerable in isolation

`spec_id`, `spec_sha`, `validator_sha`, `generated_by`, and `generated_at` are REQUIRED from this
revision; their absence is a validator error, not a warning. A frozen manifest landing cold, with
no external context, MUST be answerable in isolation: which contract produced it, which validator
checked it, when, and by what. Self-location is cheap and its absence is exactly the "meaningful
only against the validator sha beside it" convention this document's stability section already
names as a convention **outside** the file — this entry brings it in-band.

**Self-certification convention — the one-commit lag.** A manifest that certifies the repository it
lives in cannot name the commit that contains itself. Such a manifest MUST set `[subject].commit` to
the clean commit at which every evidence transcript was captured, and MUST set `spec_sha` and
`validator_sha` to that same commit, because the spec and the validator were read there too. The
manifest and its evidence records MUST then land in the immediately following commit, whose diff is
exactly that manifest-and-evidence update and nothing else. `generated_at` MUST postdate every
transcript, and `dirty` is `false`, because the named commit carries a clean tree. The one-commit
lag is inherent to self-certification, not a defect. A self-certifying manifest MUST disclose the
lag in the file itself, so a reader never has to infer it.

**Partial re-certification.** When a later change alters the certified fact behind ONE claim, that
claim's transcript MAY be re-captured alone, at a later clean commit, without re-stamping the
manifest's identity fields — re-stamping them would falsely claim every other transcript was
re-verified. A partially re-certified record MUST name its own capture commit in its evidence
`tool` field and MUST disclose the exception in a comment on the record itself. `[subject].commit`
continues to name the last commit at which every transcript was captured together.

## Content-hashing (M11) — ratified 2026-08-28

No prior text in this document states a hash algorithm; `record_hash` (evidence-types.md) and
design rule 4a's evidence-subject binding both need one, so this section is the shared anchor for
both.

**Content-hash algorithm: SHA-512 over the RAW bytes of the file as emitted.** Not a
decode-normalized or re-serialized form — the literal bytes on disk. P12 canonical emit (stable
key order, stable array order — a future entry, not shipped here) is normative for **producers**,
so that two honest emitters of the same facts tend to produce the same bytes; the hash does not
itself require canonicalization to be well-defined, because it binds to bytes, not to semantics.
**A hand-edited file simply gets a new identity** — this is deliberate: hashes are not a
normalization layer, they are a tamper-evidence layer. (Ratified 2026-08-28, superseding an
earlier sha-256 draft that was never published: SHA-512 is faster on 64-bit hardware, carries a
larger security margin, and the interop case for sha-256 was weak since in-toto DigestSets already
accept sha512.)

**Exactly ONE canonical algorithm per format revision — no per-manifest choice.** A manifest never
declares which algorithm it used; the algorithm is a property of the format revision, fixed here,
the same for every manifest that revision accepts. This is a normative rule, not a convenience:
letting a producer pick an algorithm per manifest creates a **downgrade attack** (a producer, or an
attacker who can influence a producer's tooling, picks the weakest algorithm the validator still
accepts) and **splits content identity** (the same bytes would hash to two different,
non-comparable values depending on which algorithm a given manifest happened to declare, defeating
the whole point of a shared hash domain for retirement markers and provenance stamps, below). A
future algorithm change is a new format revision, not a new field — it rides the same format-id
break every other M11 change requires.

**Digest values are self-describing: `"sha-512:<128-hex>"`.** The algorithm name lives inside the
value string itself, lower-case hex — 128 characters, 512 bits — e.g.
`"sha-512:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08…"`. This is what makes
the field NAMES algorithm-neutral, next: a reader, or a future validator, can tell what algorithm
produced a given digest by reading the *value*, never by reading the *field name* — so the field
name never has to change again even if a later, separately-ruled format revision adds a second
accepted algorithm.

**Algorithm-baked field names are renamed algorithm-neutral.** `record_sha256` is renamed
`record_hash`; any other field of the shape `*_sha256` is `*_hash` (e.g. `subject_hash`, below).
This — not the algorithm choice — is the real future-proofing this ratification buys: a field
literally named `record_sha256` would need a rename (a format-id break) on every future algorithm
change; a field named `record_hash`, carrying a self-describing value, does not.

**Domain separation is a prefix, one per use**, so the same bytes hashed for two different
purposes never collide:
- `manifest:` — hashing a whole manifest file (self-reference, the `[format]` self-location
  fields above, a future signing target);
- `bundle-root:` — hashing the canonical bundle inventory (below);
- `evidence-record:` — hashing a `record` file `[[claim.evidence]].record` points at
  (`record_hash`, REQUIRED on weighted evidence per P9, evidence-types.md);
- `claim:` (RESERVED, not computed in this revision — see "Reserved hooks" H3) — per-claim
  signing needs its own domain so claim-level and manifest-level signatures over related bytes
  are never confusable. Reserving the prefix now costs nothing and avoids a format-id break when
  claim-level attestation lands;
- `subject:` (added post-ratification under the additive-separator rule; owner notified — see
  "`subject:` domain", below) — hashing the subject artifact `[subject].subject_hash` and
  `[[claim.evidence]].subject_hash` (design rule 4a) name.

**The prefix is hash input, not an output label.** Domain separation means the prefix is fed into
the hash function alongside the file bytes: `digest = sha512(prefix_bytes || file_bytes)`, where
`prefix_bytes` is the UTF-8 bytes of the literal prefix string above, including its trailing colon
(e.g. `"manifest:"`), concatenated directly onto the raw file bytes with no added delimiter — no
newline, no null byte, nothing else in between. "One per use" only prevents a collision if the
prefix changes what gets hashed; if the prefix were instead concatenated onto the *hex digest
output* (e.g. `"bundle-root:" + hexdigest(file_bytes)`), the underlying digest of the same bytes
would be identical across domains and only the display label would differ — that is not
domain separation, it is a display convention, and it would silently defeat the collision-avoidance
purpose this section states above. (The prefix is hash input, not an output label — output
labeling would not domain-separate.) The emitted wire VALUE wraps this digest in the
self-describing form above: `"sha-512:" + hex(digest)`.

One hash domain, specified here, is what makes retirement markers (`retired — authority is the
TOML at <hash>`) and provenance stamps (`derived — authority is the TOML at <hash>`) interoperable
across producers.

**Bundle root = `"sha-512:" + hex(sha512(b"bundle-root:" || canonical_inventory_bytes))`** — the
same input-side domain-separation construction as above, applied to a canonical inventory of
`(path, role, hash)` triples, one per file the bundle claims, sorted by `path` byte order. `role`
is a closed token (`index`, `claims`, `evidence`, `findings`, …, profile-extensible); `hash` is
that file's own `manifest:`- or `evidence-record:`-domain hash (above), in the same self-describing
form. Every file physically present under the bundle root MUST appear in the inventory (an
unlisted file is rejected, not ignored); an inventory entry naming a missing or hash-mismatched
file is rejected. This is the shape the `shape` section above points at and defers *validating*,
not defines-later — the definition is fixed now so `bundle` is settled shape by the time bundle
validation is built. The inventory's concrete pre-hash serialization is deferred to the same P12
canonical-emit work named above.

### `subject:` domain — added post-ratification under the additive-separator rule; owner notified

**Added 2026-08-28, after the ratification above, under that same ratification's own
additive-separator rule** — a hash domain is a prefix string; adding one changes nothing about the
four already ratified, and needs no format-id break, exactly as the `claim:` reservation already
demonstrated. This is the fix for a gap the rs-verified-der migration audit surfaced: design
rule 4a's schema comment promised `[subject].subject_hash` is "the M11
content-hash of the subject artifact's own bytes", but no section here ever named the domain that
computes it — `[subject].subject_hash` was uncomputable, for any subject, under the ratification as
first published. The owner was notified of this addition; the fix is additive, not a retraction of
anything above.

`subject:` is what `[subject].subject_hash` and `[[claim.evidence]].subject_hash` (design rule 4a)
both refer to. Two cases, by `[subject].kind`:

- **Single-file subject:** `digest = sha512(b"subject:" || <the subject file's raw bytes>)` — the
  identical input-side construction as `manifest:`/`evidence-record:` above, applied to the
  subject's own file instead of a manifest or evidence-record file.
- **Multi-file subject** (a crate, a workspace — anything `[subject].kind` names that is not one
  file): the subject artifact is the **bundle-root construction, above, applied to the subject
  tree** — a canonical inventory of `(path, role, hash)` triples, one per file in the subject's
  declared file set, `role = "subject-file"` for every entry (a closed token distinct from
  bundle-root's own `index`/`claims`/`evidence`/`findings` roles, since a subject-tree inventory
  and a manifest-bundle inventory are never the same inventory), sorted by `path` byte order
  exactly as the bundle-root inventory is, each entry's `hash` computed under the `subject:` domain
  itself (recursively consistent with the single-file case, above) — then
  `digest = sha512(b"subject:" || canonical_inventory_bytes)`, domain-separated with `subject:` in
  place of `bundle-root:`.

**The multi-file case's canonical pre-hash serialization is PENDING the same P12 canonical-emit
work the bundle-root inventory's own serialization is deferred to, above** — this section fixes the
*shape* of a multi-file `subject_hash` (what a triple is, what role it carries, what order it
sorts in, which domain wraps it) so it is not underspecified later, the same discipline the
`bundle` shape entry above already applies to itself, but it does not yet fix the exact bytes P12
will fix. Consequently: **this revision's tooling computes and verifies the single-file case only**
(`tools/m11.py`'s `subject` domain, selftested); a multi-file subject's `subject_hash` is
producer-supplied by hand today, or left absent, exactly as a `bundle-root` hash is today. This is
not a reservation in the "Reserved hooks" sense below (the domain is not RESERVED — `subject:` is
live, ratified, and computable for the case tooling supports) — it is the same
defined-shape-but-undefined-bytes state `bundle` itself is already in, named here so it is not
mistaken for a gap this fix left open by oversight.

## Reserved hooks — slot names only, no engine ships in this revision

**What "reserved" means here, stated once.** Every hook below names a slot (a field name, a block
name, a token) that this revision's schema/vocabulary makes room for, so that building the real
machinery later needs no format-id break. **None of these hooks ship machinery in this
revision.** No validator reads them for a verdict; no ledger sums them; no engine propagates them.
A manifest may populate one today and it is admissible exactly like any other unweighted,
undecided field — recorded, not acted on. Design rule 7, above, is the law that governs every
hook below; the two must never drift apart.

**H1 — edge-shaped independence + interest-conflict attestation slots.** `[claim.independence]`
(per-claim, or per-evidence-record where independence is claimed at that granularity); sub-fields
`produced_by`, `verified_by` (typed lineage-node references), `edge` (a tagged value — see "Tagged
values", above — never a flat enum, never a declared level: `measured` with a calibration
reference, `structural` for DAG-detected dependence, or `null`). Additive independence credit
exists **only** on a `measured` edge; `structural` can only cap, never add; `null` grants no
credit, ever. Interest-conflict attestation is a **separate** slot, never merged into the edge:
`[[claim.coi_attestation]]`, failing closed to `self` when absent. The edge's calibration-reference
shape and the node-typing contract are **PENDING** a future design pass; a prior flat independence
enum (`self / same-agent-lineage / same-org / arms-length / adversarially-independent`) is retired
as credit-bearing and MAY survive only as an optional, derived, display-only label — never
validator- or ledger-read.

**H2 — provenance-node correlation keys at the `(family × context)` unit.** The `family` and
`context` sub-fields inside `produced_by`/`verified_by` (H1) and, independently, any future
correlation-key table a calibration object (H5) references. The correlation unit is **`(family ×
context)`, never `family` alone** — context is a real but unreliable diversity axis, so
per-context slices get their own number or a conservative singleton fallback, never a shared
number smeared across contexts. The concrete node-typing contract is PENDING a future design pass.

**H3 — `[[attestation]]` + authority extension id + lease/revocation fields + the per-claim M11
domain separator.** The fail-closed extension id `"authority"`; the repeatable block
`[[attestation]]`; sub-fields `signer` (discriminated union), `basis` (closed vocabulary,
`basis = "delegated"` is the one mandatory token this revision states), `scope`, `subject_hash`
(bound at manifest | per-claim | bundle-root granularity — a RESERVED field on `[[attestation]]`,
distinct from the shipping `[subject].subject_hash` / `[[claim.evidence]].subject_hash` pair design
rule 4a defines above; same field name, three different tables, each naming "the M11 hash of the
thing this block is about"), `lease_expires`, `revocable`,
`revocation_ref`; and the `claim:` domain-separator prefix reserved inside the M11 hash spec
(above). **`basis = "delegated"` is mandatory wherever an attestation is recorded** — this token
exists so an attestation can never be silently read as epistemic weight. Lease/revocation fields
are reserved because a capability tag may be leased and revocable: self-asserted-and-unattested
MUST fail closed to the tagged-null value, the same discipline as every other unmeasured field.
Trust policy for what an attestation is *worth* lives **outside** the manifest; this revision
reserves nowhere for it to live inside the schema, deliberately. **The anti-conflation invariant,
stated now because it is cheap and is the whole point of H3 existing:** an attestation is itself a
claim with its own `basis_tier` (a distinct reserved field from `epistemic_tier`, naming the
attestation's own epistemic floor) — a bare "I certify this" is epistemically no higher than `T5`
(human-judgment territory), however accountable and revocable the identity behind it. **Standing
can NEVER raise the epistemic axis (`epistemic_tier`).** This sentence is normative in this
revision even though the ledger that would compute standing is not.

**H4 — `[[defeater]]` + the closed effect algebra + the `defeated` token.** `[[defeater]]`;
sub-fields `id`, `on` (claim id), `kind` (`rebutting` | `undercutting` | `undermining`), `status`
(`open` | `refuted`), `effect` (derived, not producer-set); the claim-level status token
`defeated`. **Shape, RULED, not pending:**
`{rebutting, undercutting, undermining} × {open, refuted} -> {caps, raises, voids}` — a closed
algebra a future ledger dispatches on: a defeater's `kind` and `status` together determine its
`effect`. A green-revert does not qualify as `refuted`, and an unrecognized observation counts as
a **failed control**, never as "unnoticed." **What ships now:** the block name, the vocabularies
above, and the `defeated` status token as reserved (not yet weight-eligible, not yet
status-cohering per §7.1). **What does not ship:** any engine computing `effect` from
`(kind, status)` — recording `effect` by hand today is honest but unchecked.

**H5 — calibration-object-with-validity-scope.** `calibration = { ref = "...", validity_scope =
{ ... } }` wherever a `calibration` reference already exists (design rule 3's `alpha`/`beta`/`lr`
reservation; the `method → epistemic_tier` profile mapping, `evidence-types.md`; H1's `measured`
edge). A calibration object carries a **validity scope**, not a decay constant — staleness is
loss-of-calibration-validity: drift outside the object's stated scope reverts the term it backs to
the tagged-null value, it does not decay it toward zero on a curve. The scope's own shape (which
dimensions it is scoped over — time, input distribution, tool version) is PENDING future
calibration-governance work.

**H6 — per-claim `revisit_trigger`.** `[[claim]].revisit_trigger` (string, or a small typed table —
shape open). An uncalibrated, defeasible claim — a `judgment`-family or `inspection-argued` claim
— that never expires by construction is a failure mode this hook exists to prevent later, the same
discipline H5 already gives calibrated numbers. PENDING: whether this is free-text-with-a-shape-
floor (matching `bounds`' explanatory-tail discipline) or a typed table with a machine-checkable
trigger condition.

**H7 — composition edge types `{necessary, corroborating}`.** `[[claim.relations]]`'s `type`
vocabulary gains two ledger-facing tokens, distinct from any display/impact-analysis relations
already in use: `necessary`, `corroborating`. A **necessary** chain is bounded by its **weakest
necessary link**; **corroborating** evidence adds credit only under demonstrated independence
(H1's `measured` edge) — a single point of failure gets no corroboration credit merely for being
cited twice. This recurses over a bundle root (the M11 bundle-root hash, above) for multi-artifact
rollups. PENDING: the actual combination rule — this revision reserves the two token names and the
one-sentence semantic distinction above; it computes nothing from them.

**H8 — the ignorance≠conflict sentence.** Not a field — a one-sentence reservation of intent:
**a future ledger MUST represent "no evidence," "balanced conflict," and "strong evidence both
ways" as three distinct states — never collapsed into one mid-scale number.** Dempster-Shafer's
conflict-hiding normalization is rejected as a model for this reason; subjective-logic-style
uncertainty mass, or an explicit belief/plausibility interval, are the shapes under consideration.
This revision reserves nothing structurally beyond the sentence itself.

**Cross-cutting note: none of H1–H8 is weight-eligible or status-cohering yet.** Every hook above,
if populated today, is admissible exactly as any other unweighted, free-shaped field is admissible
under `core.md`'s W3 ("unweighted claims carry no obligations... a claim whose entire content
is a free-text sentence validates cleanly"). None of them is read by `tools/check_acceptance.py`/
`tools/check_ledger.py` for a verdict; participates in §7.1's status×grade coherence table; feeds
the `epistemic_tier`/grade coherence rule (`core.md` §2); or is summed, discounted, or
otherwise arithmetic'd by anything. A producer who populates H1–H8 today is making an honest,
unweighted disclosure. Only a future engine that reads them would make anything depend on their
values — and that engine is, per design rule 7, explicitly build-later.

## What v0 deliberately does not do

- No cryptographic signing (multi-party trust is a later layer; single-producer use does not
  need it yet).
- No automatic spec-side check that `clauses_total` matches the spec document (declared, not
  derived — an honest v0 limitation, named as such in the format's own design assessment).
- No trust arithmetic (rule 3).
- No cross-file/workspace aggregation; one subject, one manifest. (A `shape = "bundle"` manifest
  may declare linked files under a bundle root; validating the bundle as a whole is deferred — see
  "`shape` — single-file vs bundle", above.)
