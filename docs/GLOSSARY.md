# Glossary

*Role: term definitions — indexed from README §12.*

One or two plain sentences per term. Alphabetical. Each entry links the spec section where the
term is defined normatively; read that section for the exact rule, not this page.

---

## attestation (reserved)

A signed statement that an identity vouches for a claim. The format reserves the block
(`[[attestation]]`) and its fields today; no engine reads one for a verdict, and standing can never
raise a claim's `epistemic_tier`. See `spec/format.md` §"Reserved hooks", hook H3.

## band

The minimum evidence species behind a claim, capped by whether its check was ever watched to fail
on purpose (an "assurance floor," A0 through A4). A band is not a trust score: two claims at the
same band are not necessarily equally trustworthy. See `spec/assurance-bands.md`.

## bundle — see **thin index / bundle**

## certificate — see **illustrative vs certificate**

## claim

The unit the format certifies: one item, one grade, one tier. A `[[claim]]` in a TOML manifest and
a row in a rendered Markdown ledger are the same thing in two representations. See `spec/core.md`
§0.5 and `spec/format.md` §"Overview" (the opening definition).

## control

An optional `control` sub-table any evidence record may carry, recording that its oracle was
deliberately perturbed (a mutation, an ablation, or a planted-twin) and what was observed. A
control only lifts a band when the perturbation was observed **red** — passing and band-lifting are
different things. See `spec/evidence-types.md` §"Control block" and `spec/assurance-bands.md`
rule 6.

## coverage

The `[coverage]` block's counts (`claims_total`, `clauses_total`, `weight-pending`, and similar)
computed from the claims in a manifest or ledger, never typed by hand. A stated count that
disagrees with the computed one is an error, because a wrong count is the number a reader quotes.
See `spec/core.md` §W5 and `spec/coverage-ledger.md`.

## defeater (reserved)

A recorded reason to doubt a claim (rebutting, undercutting, or undermining it). The format
reserves the block (`[[defeater]]`) and its closed effect algebra; no engine computes an effect
from it in this revision. See `spec/format.md` §"Reserved hooks", hook H4.

## domain separator

A short prefix (`manifest:`, `evidence-record:`, `bundle-root:`, `subject:`, and the reserved
`claim:`) fed into a content hash alongside the file's raw bytes, so the same bytes hashed for two
different purposes never produce the same digest. See `spec/format.md` §"Content-hashing (M11)".

## envelope

The legacy Markdown document that bundles a witness/identity table with a rendered coverage
ledger — see `docs/CASE-STUDY.md` §"What an envelope is". `examples/rs-verified-der/ENVELOPE.md`
is the one shipped example. Distinct from a bare **ledger** (the row table alone) and from the
**manifest** (the TOML source of truth) — README §1 defines all three together, at first use.

## epistemic_tier (T1–T5)

The wire key for the closed, core, artifact-agnostic strength of the *method* that produced one
evidence record — `T1` (kernel-checked) through `T5` (human judgment). It is a different axis from
the weighted/unweighted tier in `spec/core.md` §0, and the two are never spelled the same way in
TOML. See `spec/evidence-types.md` §"Epistemic tier".

## evidence record

One `[[claim.evidence]]` entry: a reproducible, attributable record of one check — its kind,
family, epistemic tier, method, result, tool, and a pointer to the raw output. A record missing a
required field is an assertion, not evidence. See `spec/evidence-types.md`.

## gap

A `status` value meaning the item is in scope for the declared axis and nothing checks it. A gap is
visible and countable; it is not the same as `out-of-scope` (deliberately not claimed) or
`unspecified` (no governing text exists at all). See `spec/core.md` §7.1.

## grade (probe / contract)

The closed token stating whether a claim's evidence *decides* the item it is attached to. `contract`
means the item is decided on the shipped path over a symbolic domain with an independent oracle;
`probe` means the evidence is bounded, monomorphic, or fixture-shaped. Grade attaches to the
(item, evidence) pair, not to the evidence alone — the same proof can be `contract` for one claim and
`probe` for another. See `spec/core.md` §1 for the full nine-token vocabulary.

## illustrative vs certificate

A manifest carries `[format].illustrative = true` (a teaching example, checked shape-only) or it is
a certificate for a real subject (checked in full) — there is no third state, and every rendering
must label which one it is. See `spec/core.md` §0.6.

## ledger

The rendered table projected from a manifest's claims, one row per specification rule — checked by
`tools/check_ledger.py`. A ledger is a *rendering*, not a second source of truth; the manifest
(below) is. See `spec/coverage-ledger.md`.

## manifest

The TOML file (`acceptance.toml`) that is the format's actual source of truth: every `[[claim]]`
lives here, and any rendering — a ledger, an envelope — is a projection of it, never the reverse.
See `docs/decisions/ADR-001-toml-source-of-truth.md`.

## method

The open, profile-defined token naming the concrete technique an evidence record used
(`kani-harness`, `lean-theorem`, …). A profile's `method → epistemic_tier` table sets the
strongest permitted `epistemic_tier` (a ceiling) for each `method` it declares — a record may
declare that tier or any weaker one; a stronger declared tier is a validator error. See
`spec/evidence-types.md` §"`method`".

## record_hash / subject_hash

`record_hash` is the content-hash of the file an evidence record's `record` field points at, so a
cited record cannot be silently swapped after the fact. `subject_hash` is the content-hash of the
subject artifact itself, so evidence cannot be bound to the wrong object. Both are self-describing
M11 values (`"sha-512:<128-hex>"`). See `spec/format.md` §"Content-hashing (M11)" and design rule
4a.

## self_verify

The mandatory recipe on a claim that asserts a check was performed: a `command` a third party can
run and an `expect` string stating what a passing run must show. A claim without a runnable recipe
cannot carry weight. See `spec/core.md` §3.

## thin index / bundle

`shape = "single-file"` means the manifest is complete in one file; `shape = "bundle"` means it is a
thin index into a closed set of linked files under one root, validated today only as far as the
index file itself reaches. See `spec/format.md` §"`shape` — single-file vs bundle".

## tri-state (valid / invalid / indeterminate)

The validator's three mutually exclusive exit states: `valid` (0, everything checked holds),
`invalid` (1, a structural obligation is violated), and `indeterminate` (2, the validator cannot
decide — an unresolved extension or an unprofiled token). `indeterminate` is never treated as
passable. See `spec/core.md` §8.3.

## watched-fail

The witness that a weighted claim's recipe has actually been seen to report the claim false — a
perturbation, an observation, and a date. A recipe nobody has watched fail is not a deciding recipe,
however plausible it reads. See `spec/core.md` §4.1.

## weighted / unweighted

The two tiers a claim can carry. **Weighted** means the format itself vouches for the claim: the
claim's class is fully expressible and mechanically decidable, and every required obligation
(grade, bounds, recipe, watched-fail witness) is met. **Unweighted** means the claim is admitted as
an assertion; the format promises nothing about it — the same evidentiary level as "it was
reviewed." A claim is unweighted unless it explicitly claims weight and earns it. See
`spec/core.md` §0 and §W1–W5.
