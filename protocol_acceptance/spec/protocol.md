---
type: reference
digest: Living draft specification of the generic acceptance protocol and its contract, package, and decision rules.
---

# The acceptance protocol — `acceptance-protocol/0` (Class text locked 0.3.2, 2026-09-27) — GENERIC CORE

**Status: CANDIDATE — Class text LOCKED at 0.3.2 (2026-09-27); not yet ratified.** This document defines the producer ↔ consumer
protocol that the acceptance *format* (`acceptance/0`, `spec/format.md`) becomes when a second
party appears. It adds two documents around the existing manifest and a lifecycle over the three.

**This core is artifact-agnostic and tool-agnostic.** Nothing below names a
language, a toolchain, a verification technique or an evidence kind. Everything that does is a
**profile** — a projection of this core into one kind of production. The first projection is
*Rust code delivery*: `../../format_acceptance/profiles/verification/code/rust.md` (illustrative; profile
vocabulary). The core defines the objects, the
rules, the computed coverage and the lifecycles; a profile supplies the vocabulary the floors
compare against, the recipe carriers, and the input sets for change impact. A core rule never
mentions a profile token; a profile never adds a rule, only vocabulary and bindings.

The rules below are self-contained; `protocol_acceptance/spec/states.toml` carries the
machine-checkable lifecycle this prose restates.

## Glossary

Four terms this spec and its sibling format spec use with one meaning each, so a reader never has
to guess which sense is meant:

- **profile** — an acceptance meaning only (what acceptance says about the artifact; e.g.
  verification, conformance). A profile is never a criticality level and never a party-boundary
  declaration.
- **assurance class** — the criticality a contract declares for the delivery it accepts (blast
  radius × irreversibility), which selects a target floor set. The class table and the maturity
  rule that scales it live in the protocol contract, not the format.
- **party boundary** — the declared internal-vs-cross-org parameter set on a contract (party
  identity, document integrity, transport, disclosure, where re-runs happen, legal standing). The
  core never branches on it except where a boundary parameter itself says so.
- **readiness level** — a separate maturity-tier ladder for a subsystem or artifact, recorded
  outside this protocol, distinct from both the assurance class and the contract `phase`.

## 0. Class → Instance → Run

Every acceptance protocol or format declares which of the three ladder rungs it occupies, so
profile vocabulary cannot silently become core vocabulary again (its sibling `spec/format.md`
declares the same ladder for the format).

| rung | what | carrier |
|---|---|---|
| **Class** | §1-§11 below: roles, P1-P12, the three document shapes, the state lifecycle, `coverage()` — profile-blind by design (P11) | this file, `protocol_acceptance/spec/states.toml`, `protocol_acceptance/spec/assurance-classes.toml` (§3.7 — the assurance-class table; data, read generically), `protocol_acceptance/tools/acceptance_protocol.py` |
| **Instance** | the core bound to a validation profile: real subject kinds, evidence vocabulary, floor tables, recipe carriers — a binding, never a new rule | `../../format_acceptance/profiles/verification/code/rust.md` (`acceptance/verification`) is the only profile with its own prose Instance doc (illustrative; profile vocabulary); `acceptance/conformance` and `acceptance/troubleshooting` are also bound, in code only (`protocol_acceptance/tools/profiles.py`), reading their vocabulary from the format side's own `profiles/conformance/` and `profiles/troubleshooting/PROFILE.md` |
| **Run** | one delivery at a time: a ratified contract + a real package (real evidence transcripts from actual verification runs) + a decision, hash-bound to each other | `protocol_acceptance/examples/rust-delivery/` (`acceptance-contract.toml` + `acceptance.toml` + `acceptance-decision.toml`) (illustrative; profile vocabulary) |

### 0.1 One paragraph

A **consumer** writes a **contract**: the requirements it needs met, which are mandatory, what
warrant each needs, and who may decide. A **producer** delivers the artifact with a **package**:
the existing acceptance manifest, whose claims now attach to the contract's requirement ids,
bound to the contract by hash, with every unmet mandatory requirement carried as a declared
deviation. The consumer (or its named verifier) computes **coverage** — a deterministic function
of contract and package that no judgment is needed for — re-runs what it chooses to re-run, and
issues a **decision**: per-requirement dispositions, explicit waivers, conditions that become
obligations, and one of four verdicts. A decision is bound to the exact contract, package and
artifact it judged, and is void the moment any of the three changes. The producer never decides
acceptance; the consumer never silently overrides its own contract.

## 1. Roles

| role | does | may be |
|---|---|---|
| **consumer** | authors or ratifies the contract; issues the decision (or names who may) | a person, a team, a company, a governing subsystem, a gate |
| **producer** | delivers the artifact and the package; declares deviations | a person, a team, a company, an agent session, a generator |
| **verifier** (optional) | fills part of the package for a profile, or re-executes recipes on the consumer's behalf and reports | a lab, a validator subsystem, a second lineage, a committee |
| **authority** | the party or rule the contract names as entitled to issue a decision | the consumer itself, a named seat, a deterministic oracle for auto-acceptance |

Roles are fields on documents (§3–§5), not a role model of their own. One organisation may hold
producer and verifier roles for different profiles; it may never hold producer and authority for
the same decision (P5). Neither side must be a machine; neither side must be a person.

## 2. Design rules (binding for `acceptance-protocol/0`)

- **P1 — The contract is the spec.** The contract's requirement ids ARE the `clause` ids the
  package's claims attach to, and the contract IS the `[spec]` document the package cites. The
  consumer chose the axis, so the axis cannot flatter the producer. This dissolves the format's
  adoption risk B1 (spec discipline mostly does not exist) for every subject that has a consumer.
- **P2 — Three documents, each bound to the previous by content hash.** Contract, package,
  decision are separate files with separate authors (plus the amendment, §3.6, which edits a
  contract and is bound to the version it edits). A filled-in-place single file cannot record
  who authored the criteria; three bound files can. A rendered single "acceptance file" is a
  view over the three, never the source.
- **P3 — Coverage is computed, never asserted.** `coverage(contract, package)` (§6) is a total,
  deterministic function. Producer statuses and consumer dispositions are both held to it: a
  producer cannot claim a requirement satisfied below its floor; a consumer cannot disposition a
  requirement `satisfied` that coverage does not compute as satisfied.
- **P4 — Every override is a waiver with a reason and an authority.** The consumer may accept
  despite the contract only through an explicit `waived` disposition carrying `waiver.reason`,
  `waiver.code` and `waiver.authority`, and only on a requirement the contract marked
  `waivable = true`. Mirror of the format's design rule 5 (producer never self-overrides): *the
  consumer never silently overrides its own contract.*
- **P5 — The authority is not the producer.** The decision's `issuer` must resolve to the
  contract's `[acceptance].authority` and must not be the package's producer. A contract the
  producer drafted binds only after the consumer **ratifies** it (§3.4): the seller may draft the
  criteria it will be judged by; the buyer's recorded ratification is what makes them criteria.
- **P6 — Deviations are declared, never inferred.** Every mandatory requirement that coverage does
  not compute as `satisfied` MUST have a `[[deviation]]` in the package stating cause, impact and
  remedy. Omission of a requirement from the claim table is already forbidden by the format
  (design rule 1); omission of a deviation for an unmet mandatory requirement is forbidden here.
- **P7 — A decision is void on any change to what it judged.** It binds contract hash, package
  hash and subject identity; a mismatch with what is presented makes it `stale`, never quietly
  still valid. Re-acceptance is a new decision; a new artifact is a new package; a new criterion
  is a new contract version. Hash mismatch is the whole mechanism; no revocation service is
  needed for the base case.
- **P8 — Conditions are obligations.** A condition on an `accepted-with-conditions` decision is
  minted into a shared obligation format (`protocol/format_obligation`), producer as
  debtor, consumer as creditor, discharged by a superseding package that satisfies the named
  requirement. The protocol defines no second obligation lifecycle.
- **P9 — Nothing about truth.** As with the format: the protocol enforces structure, binding,
  coherence and the computed coverage. That a recipe is the right recipe, that a waiver was wise,
  that a verifier is independent in fact — reviewer work, named as such.
- **P10 — Reuse the envelope, invent only the predicates.** For cross-organisation exchange each
  document is carried as the payload of an in-toto Statement in a DSSE envelope (Sigstore bundle
  or SCITT receipt for transparency where needed). Inside one party boundary, git is transport
  and signature. The protocol defines three document shapes and their rules; no cryptography,
  transport, identity or transparency mechanism of its own.
- **P11 — The core is profile-blind.** A core check reads only core fields. Profile floors live
  under `[requirement.evidence.profile."<profile-id>"]` and are evaluated by that profile's
  binding (§6.6); a package's claim vocabulary (grades, bands, kinds, families, tool names) is
  profile vocabulary the core never interprets except through the profile's published mapping to
  the core warrant axis (§6.1).
- **P12 — Rigor tightens monotonically across iterations.** A buyer rarely knows what it wants
  on day one. The protocol therefore allows a contract to start with LOW floors and a
  non-final `phase`, and to be superseded by tighter versions as the product crystallizes; it
  forbids the floors from silently loosening. Across a `supersedes` chain, every carried-over
  requirement's floor may only rise (or stay) unless the consumer records an explicit
  `relaxed = {reason, by}`; a decision under a non-final contract is **provisional** and unlocks
  nothing outside its iteration. Fast cycles early, tightened verification at the end, and the
  tightening is on the record (§3.5).

## 3. The contract

File: `acceptance-contract.toml`, authored by the consumer (or drafted by the producer and
ratified, §3.4). One contract per requested artifact; versions supersede by id.

```toml
[document]
protocol   = "acceptance-protocol/0"     # exact string; major in the id, breaking change bumps it
minor      = 0                           # additive changes only
kind       = "contract"
id         = "AC-2026-0007"              # stable, never reused; new version = new id + supersedes
version    = 1
issued_at  = "2026-09-16T10:00:00Z"
issued_by  = "consumer"                  # consumer | producer  (who DRAFTED it; see [ratification])
status     = "issued"                    # draft | issued | ratified | superseded | withdrawn
# supersedes = "AC-2026-0006"            # OPTIONAL
# dropped    = [{ id = "R4", reason = "folded into R2" }]   # REQUIRED for requirements absent from the successor (P12)
# amendments = ["AM-2026-0012"]                              # the accepted amendments this version applies (§3.6)
# reopened   = { reason = "…", by = "…" }                    # REQUIRED when phase moves backwards (P12)

[parties]
consumer = { name = "Acme Ltd", contact = "platform@acme.example" }
producer = { name = "supplier-x" }       # or { name = "open" } for a call for proposals
# boundary = "cross-org"                 # OPTIONAL: internal | cross-org (default internal; §3.4a)
# [parties.boundary_terms]               # REQUIRED fields disclosure/integrity iff boundary = cross-org
# identity_scheme = "…"; integrity = "…"; transport = "…"; disclosure = "…";
# rerun_location  = "…"; legal_ref = "…"   # free strings; the closed key set is §3.4a's

# [ratification]                         # REQUIRED iff issued_by = "producer" and status = "ratified"
# by   = "Acme Ltd"                      # must equal parties.consumer.name
# at   = "2026-09-16T12:00:00Z"
# note = "criteria reviewed against RFP-441 §3"

[subject]
kind         = "other"                   # any [subject].kind the format knows; a profile may narrow it
name         = "component-x"
description  = "what is being requested, in the consumer's words"
deliverables = ["the artifact at an identified revision", "acceptance.toml package", "evidence/"]
constraints  = ["licence: …", "delivery by: …"]   # free strings; a profile may type them
profile      = "acceptance/verification" # the projection this contract is written under (§6.6)

[policy]                                 # OPTIONAL: the consumer's standing acceptance policy
ref  = "https://acme.example/supplier-policy/v3"
hash = "normative-reference:sha-512:…"   # M11 over the policy bytes, when the policy is a file
                                         #   (self-describing form, §7; bare = ERROR)

[[requirement]]
id            = "R1"                     # stable; the package's claim.clause
statement     = "what must be true, in one sentence a reader can falsify"
mandatory     = true
waivable      = false
domain        = "correctness"            # correctness | safety | security | performance |
                                         # compatibility | documentation | packaging | process |
                                         # legal | information-flow | availability | other
clause_source = "consumer-statement"     # consumer-statement | external-standard | spec-document
# external_ref = "ISO … §5"              # OPTIONAL
# parent       = "R0"                    # OPTIONAL grouping (a sub-obligation of R0)
# firmness     = "firm"                  # draft | firm (default firm; REQUIRED in phase crystallizing; §3.5)
# assurance_class = "baseline/3"         # OPTIONAL per-requirement override; may only RAISE the
                                         #   contract's own assurance_class, never lower it (§3.7)
# [requirement.relaxed]                  # OPTIONAL: this version LOWERS a floor on purpose (P12)
# reason = "…"; by = "Acme Ltd / platform-lead"   # by = [acceptance].authority
  [requirement.evidence]                 # the CORE floor a claim must meet — artifact-agnostic
  min_tier          = "T3"               # T1 (deductive) > T2 (sound decision over a declared
                                         #   domain) > T3 (empirical-sampled) > T4 (mechanical-
                                         #   syntactic) > T5 (judgment) — the format's closed
                                         #   `epistemic_tier` axis, the ONE artifact-agnostic
                                         #   warrant ordering the format defines
  weighted_required = true               # the claim must be one the format VOUCHES for (weighted)
  control_required  = true               # an observed-red witness on the claim (the format's G9)
  recipe_required   = true               # a runnable self_verify recipe (command + expect)
  freshness         = "delivered-revision"   # delivered-revision | any
  independence      = "none"             # none | author-not-producer | consumer-run | third-party
                                         #   (§3.7: a 4th value, independent of BOTH sides)
  # methods         = ["…"]              # OPTIONAL: profile-open method tokens; ≥1 must match
  # build_inputs_required       = true   # OPTIONAL, default false (§3.7): EVERY relied-on
                                         #   record PRODUCED BY RUNNING A TOOL (family !=
                                         #   "judgment") must carry a nonempty B20
                                         #   `build_inputs` list; a judgment-family record
                                         #   (human/llm review) names a reviewer, not a tool,
                                         #   and is exempt (§6.2 cond 9)
  # tool_qualification_required = true   # OPTIONAL, default false (§3.7): the SAME quantifier
                                         #   and exemption as build_inputs_required, for a B21
                                         #   `tool_qualification` table (§6.2 cond 10)
  # [requirement.evidence.coverage_min]  # OPTIONAL (§3.7): a structural/proof-coverage floor
  # metric = "decision"; value = 0.8     #   metric = the format's B21 registry; value = a fraction
  # [requirement.evidence.recipe]        # OPTIONAL: the consumer NAMES the check it will re-run
  # command = "…"; expect = "…"          #   (the adapter's mechanical recipe source); part of the
  # control_patch = "…"                  #   floor set — removing it is a weakening (§3.5)
  [requirement.evidence.profile."acceptance/verification"]   # OPTIONAL: profile floor, opaque here
  # … fields defined by the profile document (§6.6) …

[[requirement]]                          # a CROSS-CUTTING requirement constrains other claims
id        = "R5"
statement = "every covering claim of R1–R3 holds over the whole input domain"
mandatory = true
waivable  = true
domain    = "correctness"
kind      = "cross-cutting"              # DEFAULT "item"
over      = ["R1", "R2", "R3"]           # or "all"
  [requirement.demands]                  # what EACH covering claim of `over` must carry
  # min_tier = "T2"; weighted_required = true; control_required = true   (core demands)
  [requirement.demands.fields]           # claim-field ⇒ required LEADING TOKEN (generic mechanism)
  scope = "whole-domain"                 # ILLUSTRATIVE field name — the PROFILE names the real claim
                                         #   fields and tokens (the Rust profile uses `bounds`)
                                         #   (illustrative; profile vocabulary)

[acceptance]
rule                  = "all-mandatory-satisfied"   # the only rule in /0; a decision-table rule is reserved
consumer_verification = "re-execute-all"            # re-execute-all | spot-check | package-trusted
authority             = "Acme Ltd / platform-lead"  # who may issue the decision (§5)
# verifiers           = ["Lab X"]                   # OPTIONAL: who may fill/verify on our behalf
# decision_threshold  = 1                           # OPTIONAL: verifier reports a decision needs
profiles_required     = ["acceptance/verification"]
stale_after           = "P180D"                     # OPTIONAL ISO-8601 duration
phase                 = "final"                     # exploratory | crystallizing | final (default final; §3.5)
# assurance_class     = "baseline/3"                # OPTIONAL "<scheme>/<level>" (§3.7); absent =
                                                     #   no class floors, today's behavior

# [ext]                                   # OPTIONAL extension map; unknown critical ⇒ reject
# vendor_field = { value = "…", critical = false }
```

### 3.1 Requirement rules

1. `id` unique within the contract and **never reused across the whole `supersedes` chain**:
   every contract carries `[document].retired_ids` = the union of its predecessor's `retired_ids`
   and the ids it dropped, and no requirement may take an id in that list. A **floor-only revision**
   (a tighter or relaxed `[requirement.evidence]`, `demands`, `mandatory`, `waivable`) keeps the id;
   a **semantic replacement** (a changed `statement`, `kind` or `domain`, or an `over` that drops
   an id) is a NEW id whose requirement carries `replaces = "<old id>"` and whose predecessor is
   listed in `dropped`; adding ids to `over` is a floor-only tightening under the same id.
   `replaces` is **transition-local**: valid only in the version that introduces the id, stripped
   when a successor is derived (like `relaxed`), and an error on a carried-over requirement. An
   amendment `modify` op may only change the floor set; a statement change is an `add` + `drop`
   pair (§3.6).
2. `mandatory = true` requirements decide acceptability; optional ones are reported, never decisive.
3. `waivable = false` requirements can never be dispositioned `waived` (P4).
4. `kind = "cross-cutting"` requirements carry `over` and `[requirement.demands]`, and no
   `[requirement.evidence]`; item requirements carry `[requirement.evidence]` and no `demands`.
   `over` may name item requirements only — a cross-cutting requirement inside another's `over` is
   a contract error (no nesting in `/0`).
5. Core floor vocabularies: `min_tier ∈ {T1..T5}`; the rest booleans and the closed enums shown.
   A profile floor table's content is validated by the profile binding, not by the core. The five
   `[requirement.evidence]` floor booleans default, when absent, as follows: `weighted_required`
   defaults to **true**; `control_required`, `recipe_required`, `build_inputs_required` (§3.7) and
   `tool_qualification_required` (§3.7) each default to **false** — an undocumented default is the
   defect whichever key carries it, so all five are stated here together (reference tool:
   `acceptance_protocol.py`, §6.2 conditions 2/5/6/9/10).
6. `independence`: `author-not-producer` demands every evidence record relied on carries a
   **nonempty** `author` that differs from the package's producer identity (§4.1 rule 7) — a
   record with no `author` fails the demand, it does not pass it; `consumer-run` demands the decision's own verification run for
   the claim passed (§5.2); `third-party` (§3.7) demands BOTH — every relied-on record's `author`
   nonempty and outside the producer identity set, AND different from `[parties].consumer.name` —
   independent of both sides, not merely the producer, and also demands the decision's own
   verification run for the claim passed (§5.2, §6.2 cond 8). All three are checks of declared
   fields, not of fact (P9).
7. `[subject].profile` names the projection; it must appear in `[acceptance].profiles_required`.
   Membership is an exact-string match against that list — a meaning-only id and a more specific
   leaf under it are different ids for this purpose (§4.1 rule 6's exact-leaf rule applies
   identically here: no prefix matching).
8. `assurance_class` (§3.7), where present at `[acceptance]` level or on a requirement, MUST parse
   as `"<scheme>/<level>"` and resolve to a registered row of the class table
   (`spec/assurance-classes.toml`); a per-requirement `assurance_class` MUST NOT set a floor
   weaker, on any axis, than the contract's own `assurance_class` (the same "may only raise"
   direction the tightening rule uses within a `supersedes` chain, applied here within one
   version).

### 3.2 Contract lifecycle

`draft → issued → ratified → superseded | withdrawn` (states.toml `contract`). A consumer-issued
contract (`issued_by = "consumer"`) is binding at `issued`; a producer-drafted one
(`issued_by = "producer"`) is binding **only** at `ratified` — a producer-drafted contract in
`issued` status is a proposal, and a package bound to it is invalid (§4.1 rule 4). A package may
bind only to a BINDING contract. Superseding is a new contract carrying `supersedes`.

### 3.3 Contract validity (`check-contract`)

Structural: required tables and fields; closed vocabularies; ids unique and not in
`retired_ids`; `over` resolves to item requirements; every `[requirement.evidence.profile."<id>"]`
table is validated by that profile's **floor-schema validator** (§6.6 item 2: unknown keys and
out-of-vocabulary tokens are errors; a profile id with no binding available is an error, never a
silently-ignored floor);
`[ratification]` present iff `issued_by = "producer"` and `status = "ratified"`; consumer named;
≥ 1 mandatory requirement; `stale_after` is an ISO-8601 duration; `[ext]` entries carry a boolean
`critical`; `[subject].profile ∈ profiles_required`; a `draft` requirement in a `final`-phase
contract is an ERROR (§3.5 — unconditional, no `assurance_class` needed); when an
`assurance_class` is declared anywhere, the §3.7 maturity rule (a `firm` requirement of a `final`
contract must meet its effective class's floors; any requirement while the phase is not `final` —
the only phases a `draft` requirement may occur in, §3.5 — gets a NOTE instead of an ERROR), the
per-requirement override's "may only raise" check, and the class's
`required_meaning` list against `[acceptance].profiles_required`. A spec-clarity summary line
(firm vs draft requirement counts) is always emitted, class or no class. With `--previous OLD.toml`: the §3.5 tightening rule over the
`supersedes` chain (a hard error per weakened floor without `relaxed`, per dropped requirement not
listed, per backwards phase without `reopened`). **The chain is validated to its root:** every
predecessor is itself validated (structure, binding status, and its own `--previous` step) back
to a contract with no `supersedes`; an unavailable ancestor is an error, not a skipped link; a
cycle is an error; `retired_ids` must equal the union along the chain, recomputed, never trusted.
A caller passes the chain as `--previous OLD1 --previous OLD2 …` (newest first) or a directory.

### 3.4 Ratification

A recorded act by the consumer over a producer-drafted contract: the `[ratification]` table whose
`by` equals the consumer party. Drafting is free; binding requires the buyer's word. Internally the word is a
recorded decision id in `note`; externally it is the consumer's signature over the contract.

### 3.4a Party boundary

`[parties].boundary = "internal" | "cross-org"` (OPTIONAL; absent means `"internal"`) declares,
once per contract, whether the consumer and producer sit inside one governance boundary (an
a company, a single organisation) or across two. It is a DECLARED FACT, not a rule of its own: the
Class rung — roles (§1), the three document shapes, the state lifecycles, `coverage()` (§6),
tightening (§3.5), binding by hash (§7) — is IDENTICAL for both boundaries. `[parties.boundary_terms]`
carries the boundary's own parameters, one declared value per contract, replacing what the
an earlier design's §4c table listed as seven separate rows: `identity_scheme` (what each side
accepts as identity), `integrity` (how document integrity is carried — git commits, a DSSE
envelope, …), `transport` (how the three documents travel), `disclosure` (what evidence disclosure
the parties agreed — full, referenced, redacted), `rerun_location` (where the consumer re-runs),
and `legal_ref` (where legal standing is recorded, outside the format). Every field is a free
string; the key set itself is closed (an unknown key is an error), so a boundary_terms table cannot
silently carry a typo'd parameter no check will ever read.

**The only two core branches on `boundary`, both in `check-contract`:**

1. `boundary = "cross-org"` REQUIRES `[parties.boundary_terms].disclosure` and `.integrity` to be
   stated (nonempty strings) — an ERROR, not a warning, when either is missing. A
   cross-organisation exchange with no stated disclosure or integrity term is not a contract a
   consumer can rely on; every other boundary parameter (`identity_scheme`, `transport`,
   `rerun_location`, `legal_ref`) is carried for a reader, never read by a core check in `/0`.
2. Ratification (§3.3, §3.4) already covers the producer-drafted case: `[ratification]` is
   REQUIRED whenever `issued_by = "producer"` and `status = "ratified"`, **regardless of
   boundary** — a producer-drafted cross-org contract binds only once ratified, exactly as an
   internal one does. No second, boundary-specific ratification rule is added; the general one
   already reaches this case (verified against `check_contract`, §3.3).

P10's declared cross-organisation wrap (§7) and the work-contract layer (`spec/stack.md`) are
where `transport`/`identity_scheme` become load-bearing, once built; `/0` only carries them.

### 3.5 Iteration and tightening (crystallization) — P12

**Phase.** `[acceptance].phase ∈ {exploratory, crystallizing, final}`; absent means `final`.

| phase | what the consumer knows | floors | decision |
|---|---|---|---|
| `exploratory` | the intent, not the requirements | anything, typically `min_tier = "T5"`, `weighted_required = false`, `recipe_required = false` — "show me it runs, let me look" | **provisional**: `verdict` as usual, `[document].provisional = true` (derived from the phase, must be present and true); unlocks no effect outside the iteration; expires when the contract is superseded |
| `crystallizing` | most requirements, some still forming | mixed; every requirement carries `firmness = "draft" \| "firm"`; draft requirements may be `mandatory` but their floors are expected to rise | provisional, as above |
| `final` | what it wants | the full floors | definitive; the only phase whose `accepted*` decision an effect gate (publish, pay, deploy) may act on |

**Firmness.** `[[requirement]].firmness = "draft" | "firm"` (default `firm`; REQUIRED in
`crystallizing`). A `draft` requirement announces that its statement or floor is expected to
change; the tightening rule still binds it, so a draft requirement's floor never drops silently.
A contract may be in phase `final` only if every requirement is `firm` (an absent firmness
defaults to firm, as above): a `draft` requirement in a `final`-phase contract is an ERROR
(`check-contract`) — `final` states what the consumer wants, and a requirement still marked
expected-to-change is not that.

**Tightening rule (checked by `check-contract --previous OLD.toml`).** The **floor set** of a
requirement is everything that restricts what satisfies it: `mandatory`, `waivable`, `kind`,
`over` (for cross-cutting), every key of `[requirement.evidence]` (`min_tier`, `weighted_required`,
`control_required`, `recipe_required`, `freshness`, `independence`, `methods`,
`build_inputs_required`, `tool_qualification_required`, `[requirement.evidence.coverage_min]`
(§3.7), the `[requirement.evidence.recipe]` table), every key of every
`[requirement.evidence.profile."<id>"]` table, and every key of `[requirement.demands]` and
`[requirement.demands.fields]`. For every requirement id present in both predecessor and
successor, **no element of the floor set may weaken**, where weakening means: a lower `min_tier`;
any boolean restriction going true → false; `freshness` going `delivered-revision` → `any`;
`independence` moving down `none < author-not-producer < consumer-run < third-party` (§3.7);
`coverage_min` (§3.7) removed, its `metric` changed (incomparable, treated as a weakening) or its
`value` lowered; `mandatory` true → false;
`waivable` false → true; **removing** a restriction (a `methods` list, a `kinds`/`families` list,
a profile floor table, a `demands` key, a `fields` entry) or emptying a list;
and, for profile keys, anything the profile's own comparator (§6.6 item 7) calls weaker — a
profile id with no comparator available makes the comparison an **error**, never a pass. A shrunk
`over` is not a weakening — it is a §3.1 rule 1 identity violation (semantic replacement: new id +
`replaces`, predecessor in `dropped`); adding ids to `over` remains a floor-only tightening under
the same id. The only
exception is an explicit `[requirement.relaxed] {reason, by}` on the successor's requirement,
where `by` is the contract's `[acceptance].authority` — **the one identity that relaxes, accepts
amendments and issues decisions** (never `parties.consumer.name` as a separate rule) — which
authorises exactly that one version's relaxations and is **never inherited**: the tool strips
`relaxed`, `replaces`, `reopened`, the `[ratification]` table and `amendments` when deriving a
successor, so an old relaxation cannot excuse a later weakening. Dropped requirements MUST be listed in
`[document].dropped` and their ids join `retired_ids`; new requirements may appear at any phase;
`phase` may not move backwards without `[document].reopened = {reason, by}`. A chain is therefore
an auditable record of how the spec crystallized.

**Projection pinning.** Across a `supersedes` chain `[subject].profile` is INVARIANT: a differing
successor is a hard error, excusable by nothing — `relaxed` is per-requirement, `reopened` is
phase only, and neither touches the projection. `[acceptance].profiles_required` may only GAIN
entries and never lose them across the chain; a removed entry is a hard error. A different
projection means a NEW contract (new id, no `supersedes`), never a tightening step. Amendment
`change` ops (§3.6) are requirement-scoped, so there is no amendment bypass of this pin.

**The feedback channel (both directions).** Iteration needs the spec itself to be correctable:
- the consumer (or a party it engages to attack its own spec) records, in the decision,
  `[[requirement_feedback]] {requirement, kind ∈ {ambiguous, wrong, missing, over-constrained,
  under-constrained, malicious-compliance}, statement, proposed}` — what the next contract version
  should say. `malicious-compliance` names a package that satisfies the letter of a requirement
  and violates its evident intent; it is feedback on the requirement, never a disposition against
  the producer, because the requirement was the defect;
- the producer records, in the package, a `[[deviation]]` with `kind = "requirement-defect"`
  (contradictory, unimplementable, or ambiguous as written) — a deviation that asks for a
  contract change rather than a waiver.
Both feed the successor contract; neither changes the current iteration's coverage.

**What does not change.** The document shapes, the coverage function, the dispositions and the
verdicts are the same in every phase. Only the floors, the `phase`, the `provisional` flag and
the tightening check vary. An exploratory contract with judgment-tier floors is a legitimate
contract; its provisional acceptance is a legitimate decision about that iteration and nothing
more.

### 3.6 The spec-update process — amendments, live or offline (P12)

Iteration only works if changing the spec is itself a protocol step, cheap enough to run many
times a day and safe enough to run across a week of silence. The **amendment** is that step.

**The amendment document** (`acceptance-amendment.toml`), the one document either side may author:

```toml
[document]
protocol  = "acceptance-protocol/0"
minor     = 0
kind      = "amendment"
id        = "AM-2026-0012"
issued_at = "2026-09-17T09:00:00Z"
issued_by = "producer"                   # consumer | producer | verifier
status    = "proposed"                   # proposed | accepted | rejected | stale | superseded
# from_decision = "AD-2026-0031"         # OPTIONAL: the decision whose feedback this carries

[binds]
contract = { id = "AC-2026-0007", hash = "contract:sha-512:…" }   # the BASE version this amends

[[feedback]]                             # same shape as a decision's requirement_feedback (§3.5)
requirement = "R3"
kind        = "ambiguous"
statement   = "R3 does not say whether whitespace inside the IBAN is accepted"
proposed    = "R3': whitespace is stripped before validation; internal whitespace is not an error"

[[change]]                               # the concrete edit to the requirement set
op          = "modify"                   # add | modify | drop | tighten | relax
                                         # modify/tighten/relax change the FLOOR SET only (§3.1 rule 1);
                                         # a statement change is add (new id, replaces = old) + drop
requirement = "R3"                       # existing id for modify/drop/tighten/relax; NEW id for add
reason      = "resolves the ambiguity above"
  [change.proposed]                      # a full [[requirement]] table for add/modify;
  id = "R3"                              #   only [requirement.evidence] for tighten/relax
  statement = "…"
  mandatory = true
  # …
```

**Rules.**

1. **Base binding — validity is not applicability.** An amendment is *valid* when it is
   well-formed and its `[binds].contract.hash` recomputes over the version it names (any version,
   historical or current). It is *applicable* only when, at the moment of application, its status
   is `proposed` AND its bound hash equals the hash of the consumer's **current** contract version.
   An amendment whose base is not current is `stale`; a `stale` or `rejected` amendment is never
   applied, whatever its own status field says. Application is atomic per base. The consumer keeps a **current pointer** — a small record
   (`acceptance-contract.current`, `{id, hash}`) that names its current version; `apply-amendment`
   reads it, refuses unless the amendment's base equals it, writes the successor, and advances the
   pointer with an atomic replace in that order. Within a consumer applying amendments
   SEQUENTIALLY, two applications against the same base cannot both succeed: the second finds the
   pointer moved and must rebase against the successor. `/0`'s reference tool guarantees this per
   sequential consumer process only (read → check → write → atomic replace); concurrent appliers
   require an exclusive-creation lock on the current pointer — a booked build item, not a `/0`
   claim (restore the strong, appliers-agnostic sentence once the `O_EXCL` lock lands). A
   stateless "compare against a file the caller chose" is not this rule. Two pending amendments touching the same requirement are ordered by the
   consumer; the later one rebases.
2. **Only the authority accepts.** Either party proposes; the contract's `[acceptance].authority`
   accepts or rejects (the same identity that may issue a decision, P5). Acceptance IS the issue of
   the successor contract: `supersedes = <base id>`, `[document].amendments = ["AM-…"]`, `dropped`
   filled from `drop` ops, `retired_ids` extended, `[requirement.relaxed]` filled **only** from this
   amendment's `relax` ops (nothing inherited, §3.5), and the successor is then fully validated
   (`check-contract`, including `--previous` against the base) **before** it is issued; a successor
   that fails validation is not issued and the amendment stays `proposed`. A producer-authored
   amendment therefore never binds by itself, and a consumer-authored one binds the moment the
   successor is issued. The successor is always **authority-issued**: `issued_by = "consumer"`,
   `status = "issued"`, no `[ratification]` table — whatever the base's `issued_by` was, because
   the authority's application IS the buyer's word.
3. **Spec-only iterations are legal.** A contract may be superseded by amendment with no package or
   decision in between — the buyer refining its requirements with its own reviewers before or
   between deliveries. The chain records every step either way.
4. **Feedback with a decision is an implicit amendment.** A decision's `[[requirement_feedback]]`
   entries are treated as a proposed amendment authored by the consumer (`from_decision` set);
   the tool can materialise it (`amend --from-decision`).
5. **Live or offline is a transport property, not a protocol one.** Live: both parties in one
   session; amendments are proposed, accepted and the successor issued within the conversation, and
   a new package can follow in minutes. Offline: amendments travel as files (git, DSSE), each keyed
   by its own hash (idempotent: the same bytes twice are one amendment), the consumer batches and
   orders them, and base-hash binding is what makes a late-arriving amendment safe. Same document,
   same rules, same checker.
6. **Nothing in an amendment changes a running iteration.** Coverage and decisions are computed
   against the bound contract version; an accepted amendment starts the next iteration.
7. **A class change is a successor contract, not an amendment.** `[[change]]` ops are
   requirement-scoped (§3.1 rule 1, §3.5's floor set); none of `add`, `modify`, `drop`, `tighten`
   or `relax` names or reaches `[acceptance].assurance_class`, which lives at the CONTRACT level,
   not on any one requirement. Raising or lowering a contract's own assurance class is done by
   directly authoring the next successor contract (a new contract id, `supersedes` the current
   one, validated by `check-contract --previous` as usual) — never by proposing and accepting an
   amendment, since no `[[change]]` op carries that field.

**Lifecycle** (states.toml `amendment`): `proposed → accepted | rejected | stale → superseded`.

### 3.7 Assurance class and spec maturity

**Placement.** Strictness = assurance class × spec maturity, and it is a protocol concern.
The format stays generic (identity, evidence, the warrant axis); the
protocol contract is where a consumer states HOW MUCH of that generic mechanism a given delivery
must clear, and WHEN — the class sets the target, the contract's own maturity (phase + per-
requirement firmness, §3.5) decides how much of that target already applies. One format and
protocol serve a game and an avionics supplier alike; only the contract's declared class differs.

**The class table is data, read generically.** `[acceptance].assurance_class = "<scheme>/<level>"`
names a row of `spec/assurance-classes.toml` (§0's Class-rung table): `<scheme>` is the table's
own name (`/0` ships one scheme, `baseline`, levels 0..4 — see that file's header for the level
definitions and the anchor: `baseline/1` is the radio-app/game reference bottom, `baseline/4` is
the investing-app/money reference top); `<level>` is that scheme's
ordinal. The field is OPTIONAL — absent means no class floors apply, today's behavior unchanged.
A level row states the MINIMUM value, for this class, of every axis in `_CLASS_AXES`
(`min_tier`, `weighted_required`, `control_required`, `recipe_required`, `independence`,
`freshness`, `build_inputs_required`, `tool_qualification_required`, `coverage_min`), plus
`required_meaning` (profiles the class demands, optionally scoped by `[subject].kind`) and a
documentary `bounds` value (RESIDUAL — not mechanically compared in `/0`, §6.4's profile-carried
`bounds` claim field is the only generic mechanism that reaches it today; see the table's own
header). The core never hard-codes a scheme, a level or a floor number — only the table's SHAPE.

**Per-requirement override.** `[[requirement]].assurance_class = "<scheme>/<level>"` sets that
ONE requirement's effective class instead of the contract's. It MUST NOT be weaker, on any axis,
than the contract's own `assurance_class` — an ERROR names the axis and both values, the same
"may only raise" direction §3.5's tightening rule uses across a `supersedes` chain, applied here
WITHIN one contract version. A requirement with no override and a contract with no
`assurance_class` at all carries no class floors — the mechanism never applies itself silently.

**The maturity rule.** For every `item` requirement (kind = cross-cutting carries no
`[requirement.evidence]`, §3.1 rule 4, and is out of this rule's scope) whose effective class
resolves:

- **`firm` (the default) in a `final`-phase contract**: `[requirement.evidence]` MUST meet or
  exceed the class's floor on every axis in `_CLASS_AXES` — a shortfall is an ERROR naming the
  requirement id, the failing axis, its actual value and the class's target.
- **the contract's phase is `exploratory`/`crystallizing`** (the only phases a `draft` requirement
  may occur in — §3.5 makes `draft` an ERROR in a `final` contract): a shortfall on the same
  axes gets a NOTE (a warning, never an error) listing the gap — spec-clarity visibility, not a
  blocker. §3.5 already holds a decision under a non-final contract PROVISIONAL; this rule adds
  no new consequence, only earlier legibility of how far a draft area sits from its eventual
  target. A clean spec (every requirement `firm`) can go `final` at once and take the FULL class
  floors from its first package.

**`required_meaning`.** Unlike the nine per-axis floors, `required_meaning` is a CONTRACT-level
check, not a per-requirement one — `[acceptance].profiles_required` has no per-requirement
counterpart. Whenever the CONTRACT's own `assurance_class` resolves, every `{profile, when_kind?}`
entry the class declares is checked: if `when_kind` is present, the entry applies only when
`[subject].kind` is a member; if it applies and `profile` is absent from
`[acceptance].profiles_required`, that is an ERROR in a `final`-phase contract and a NOTE
otherwise (the same phase gate as the maturity rule above). Application-delivery
troubleshooting scoping is the worked case: `baseline/3` and `baseline/4` both require
`acceptance/troubleshooting` `when_kind` names a deployed-artifact kind.

**Spec-clarity summary.** `check-contract` always emits one NOTE line counting firm vs draft
requirements in the presented contract, class or no class — the maturity rule's visibility is
useful even before a class is assigned. A B19 spec inventory pinned by the FORMAT package is a
separate document this protocol-level check does not read (0.3 residual: the parenthetical
firm-vs-draft INVENTORY-item count belongs at package-check time, where a B19 inventory can
actually be present — §4's package check already runs the format's own B19 checks; this protocol
document does not duplicate them).

**Independence's 4th value.** `third-party` (§3.1 rule 6, §6.2 cond 8) extends the ordering to
`none < author-not-producer < consumer-run < third-party` — independent of BOTH the producer AND
the consumer (DO-178C/ISO 26262's separate-organisation independence tier). It is
STRICTER than `consumer-run`, never a substitute: it demands the same decision-level verification
run §5.2 already requires for `consumer-run`, plus the author exclusion on both sides.

**The two new format-evidence floors.** `build_inputs_required` and `tool_qualification_required`
are core-readable because `build_inputs` (B20) and `tool_qualification` (B21) are GENERIC
evidence-record fields, not profile vocabulary — the same reasoning that already lets the core
read `epistemic_tier`, `author` and `captured_at_revision` directly (P11 is about profile
vocabulary, `grades`/`bands`/`kinds`/`families`/tool names — not every field a claim may carry).
**Both floors share ONE quantifier: EVERY relied-on
evidence record that is PRODUCED BY RUNNING A TOOL — `family != "judgment"` (B3) — MUST carry the
field; a `judgment`-family record (`human-review`, `llm-review`, B4) names a `reviewer`, never a
tool, and is exempt from both (§6.2 conds 9-10).** This resolves an earlier draft's contradiction
between "every" (§3, §3.7) and "at least one" (§6.2 conds 9-10, now corrected): "at least one"
would let a single trivially-compliant record vouch for the whole claim while the actual deciding
tool-produced evidence carries neither field — near-vacuous at exactly the class this floor exists
to tighten.
`build_inputs_required` addresses the format-level limitation that B20's own `required_build_inputs`
guard only fires once a claim already declares a `build_inputs` list; this floor is what makes
declaring one MANDATORY at the class that sets it (`baseline/4`, the top class, in the shipped
table). `coverage_min = { metric, value }` compares a relied-on evidence record's own
`coverage.metric`/`coverage.value` (B21) against the floor: an unmet floor, a metric mismatch (an
`incomparable` case, never a pass by coincidence) or no `coverage` record at all are equally "not
met" (§6.2 cond 11).

## 4. The package

File: `acceptance.toml` — the existing `acceptance/0` manifest, validated through the package's
declared `[format].profile` by the format core's profile dispatcher (`check_core.py`, §6.6 item 8)
exactly as today for `acceptance/verification`, and identically for any other profile the format
core knows — with these protocol additions:

```toml
[format]
id       = "acceptance/0"
# protocol = "acceptance-protocol/0"     # RECOMMENDED: says this manifest is a protocol package
profile  = "acceptance/verification"    # REQUIRED per format B12; a package omitting it is
                                         #   invalid at the format layer (no compatibility default)

[contract]                               # REQUIRED for a package (absent = producer-only manifest)
id                 = "AC-2026-0007"
hash               = "contract:sha-512:…"  # M11 domain `contract:` over the contract file bytes (self-describing form)
requirements_total = 6                   # must equal the contract's requirement count

[spec]                                   # P1: the contract IS the spec
path    = "acceptance-contract.toml"
version = "AC-2026-0007@v1"
axis    = "the requirements of contract AC-2026-0007"
# upstream_status = "Under Review"       # OPTIONAL, non-normative: the pinned spec's own
                                         #   maturity/lifecycle label (e.g. an RFC's own status
                                         #   field) at the moment it was pinned — carried and
                                         #   displayed (§10), NEVER read by coverage() or any
                                         #   gating check (P9)

[coverage]
clauses_total = 6                        # = [contract].requirements_total (checked)
claims_total  = 7

[[claim]]
clause = "R1"                            # MUST be a requirement id of the bound contract
# … every field the format defines, unchanged …
  [[claim.evidence]]
  # epistemic_tier = "T3"                # the core warrant axis (public 0.2 field; transitional);
                                         #   when absent, the profile's method/kind ⇒ tier CEILING
                                         #   table supplies it, and a record the profile cannot
                                         #   place is INDETERMINATE — it meets no floor (fail-closed)
  # author = "Lab X"                     # OPTIONAL: who produced this record (independence)
  # captured_at_revision = "<id>"        # OPTIONAL: the subject revision the record was produced
                                         #   against (a profile may alias it, e.g. captured_at_commit)
  # [[claim.evidence.inputs]]            # OPTIONAL: declared input set for change impact (§8)
  # path = "…"; digest = "subject:sha-512:…"   # M11 domain `subject:` per input (self-describing
                                         #   form, §7; bare = ERROR)

[[deviation]]                            # REQUIRED for every mandatory requirement not satisfied
requirement      = "R5"
kind             = "unmet"               # unmet | partial | alternative | not-applicable |
                                         # requirement-defect (asks for a contract change, §3.5)
statement        = "what is not met, plainly"
cause            = "why"
impact           = "what the consumer is exposed to as a result"
remedy           = "what would close it, and when"
waiver_requested = true

[[filler]]                               # OPTIONAL: who filled which profile (accountability role)
profile = "acceptance/verification"
party   = "supplier-x"
role    = "producer"                     # producer | validator
```

### 4.1 Package rules (`check-package`, after the bound profile's package validator passes)

1. `[contract]` present; `hash` recomputes over the presented contract file; `requirements_total`
   equals the contract's count and `[coverage].clauses_total`.
2. Every `[[claim]].clause` is a requirement id of the contract; every item requirement has ≥ 1
   claim (gap, parked and blocked claims count — omission is the only forbidden state).
3. Every mandatory requirement whose computed coverage is not `satisfied` has a `[[deviation]]`
   (P6); its `requirement` resolves; `kind` closed; `statement`, `cause`, `impact`, `remedy`
   nonempty.
4. The bound contract is itself **valid** (`check-contract` passes, including `--previous` when
   it supersedes another) and **binding** (§3.2: `issued` with `issued_by = "consumer"`, or
   `ratified`). A package bound to a valid-but-not-binding contract is invalid.
5. `[subject]` carries exactly one B1 certified identity — git-revision (`commit`), content-digest
   or components (both `digest`) — not `commit` alone; `freshness = "delivered-revision"`
   compares each record's `captured_at_revision` (or the profile's alias) against it, which is only
   ever satisfiable for a git-revision identity (§7). This rule has no independent guard of its
   own in `check-package`: it is enforced upstream by the format's B1 (`check_subject_locator`),
   which every bound profile's package validator already runs before `check-package`'s own rules
   evaluate — a malformed or absent certified identity fails there first, demonstrated by that
   check's own mutation entry (a `'B1'` guard, disabled-then-restored, red-then-green; mutation
   audit in the upstream development repository).
6. Every profile in the contract's `profiles_required` appears in the package (as
   `[format].profile` or a `[[filler]].profile`), AND the package's own profile (`[format].profile`,
   REQUIRED per format B12; a package omitting it is invalid at the format layer) is one the
   contract requires — a package under a different profile is invalid, it is not evaluated under a
   looser floor. **Exact leaf.** Profile ids match as exact strings: a contract names the exact
   profile leaf it requires, and a meaning-only id (one that binding-specific leaves refine
   further) is satisfied only by a package declaring exactly that meaning id — never by a package
   declaring a more specific leaf under it. There is no prefix matching at this layer; B12's own
   prefix rule is about a validator's dispatch to a binding, not about what a contract's
   `profiles_required` accepts.
7. **Producer identity.** The package's producer identity is the set {`parties.producer.name` of
   the contract} ∪ {every `[[filler]].party` with `role = "producer"`}. When the contract's
   producer is `"open"`, the package MUST carry at least one `[[filler]]` with `role = "producer"`
   naming who produced it; otherwise it is invalid. P5 and `independence` compare against this
   whole set.

Failing rule 1, 2 or 4 makes the package **invalid**. Rule 3 failures are **errors** (refused as a
protocol package; still a valid producer-only manifest). Coverage is printed regardless, so the
producer sees exactly what the consumer will see.

## 5. The decision

File: `acceptance-decision.toml`, authored by the authority named in the contract.

```toml
[document]
protocol  = "acceptance-protocol/0"
minor     = 0
kind      = "decision"
id        = "AD-2026-0031"
issued_at = "2026-09-20T09:30:00Z"
issuer    = "Acme Ltd / platform-lead"   # must equal [acceptance].authority of the contract
verdict   = "accepted-with-conditions"   # accepted | accepted-with-conditions | rejected |
                                         #   evidence-requested | lapsed (§5.5: a condition's
                                         #   obligation expired, OR merits = false's
                                         #   close-without-merits path — never a merits judgment)
                                         # (a [document] field: a bare `verdict =` after a [[condition]]
                                         # table would bind to that table under TOML's rules)
# provisional = true                     # REQUIRED (and true) when the bound contract's phase ≠ final (§3.5)
# supersedes = "AD-2026-0030"
# merits       = false                    # OPTIONAL, default true (§5.5): false = this decision
                                         #   renders NO merits judgment (plan choice 1, §5.5)
# reason       = "…"                      # REQUIRED nonempty when merits = false
# recorded_by  = "…"                      # REQUIRED when [derivation] is present (§5.4,
                                         #   §5.4): who WROTE this document — distinct
                                         #   from issuer/authority, which is UNCHANGED (P5)

[binds]                                  # P7: what this decision judged, exactly
contract = { id = "AC-2026-0007", hash = "contract:sha-512:…" }
package  = { hash = "manifest:sha-512:…" } # M11 domain `manifest:` over the package file bytes (self-describing form)
subject  = { commit = "<40-hex>" }       # = package [subject] identity, SAME form: a
                                         #   git-revision subject binds { commit = "<40-hex>" };
                                         #   a content-digest or components subject binds
                                         #   { digest = "<subject:sha-512:hex>" } instead

[verification]
mode = "re-execute-all"                  # re-execute-all | spot-check | package-trusted
                                         # at least as strong as the contract's setting
[[verification.run]]                     # the consumer's OWN runs: what ran, not only that it passed
claim    = "X-001"
command  = "<the claim's recipe, or the consumer's own>"
observed = "<tail of the real output>"
result   = "pass"                        # pass | fail | not-run | error
at       = "2026-09-20T09:12:00Z"
# by     = "Lab X"                       # OPTIONAL: a verifier acting for the consumer

[[disposition]]                          # exactly one per contract requirement (mandatory AND optional)
requirement = "R1"
status      = "satisfied"                # satisfied | satisfied-with-conditions | unsatisfied |
                                         # waived | insufficient-evidence | not-applicable
basis       = ["X-001"]                  # claim ids relied on (must exist in the package)
# note       = "…"
# conditions = ["C1"]                    # REQUIRED when status = satisfied-with-conditions
# [disposition.waiver]                   # REQUIRED when status = waived (P4)
# reason    = "…"
# code      = "deferred"                 # risk-accepted | alternative-evidence | not-applicable |
#                                        # deferred | other
# authority = "Acme Ltd / platform-lead"

[[condition]]                            # REQUIRED ≥ 1 when verdict = accepted-with-conditions
id            = "C1"
requirement   = "R5"
statement     = "…"
due           = "2026-11-30"
owner         = "producer"               # producer | consumer | verifier
discharged_by = "a superseding package in which coverage(R5) = satisfied"

# [[requirement_feedback]]               # OPTIONAL, any phase: what the NEXT contract version should say (§3.5)
# requirement = "R3"
# kind        = "ambiguous"              # ambiguous | wrong | missing | over-constrained |
#                                        # under-constrained | malicious-compliance
# statement   = "R3 admits an implementation that … which is not what we meant"
# proposed    = "R3': …"

# [derivation]                            # OPTIONAL (§5.4): present only for a DERIVED
                                         #   decision — one recording an act taken by an
                                         #   EXTERNAL authority, never our own judgment
# authority_act = "merge"                 # what the external authority did: e.g. "merge",
                                         #   "approval", "close" — one short token or phrase
# rule          = "…"                     # the declared derivation rule mapping that act to
                                         #   this document's verdict/dispositions, stated in
                                         #   full, never implied
# [[derivation.evidence]]                 # REQUIRED, ≥ 1, when [derivation] is present
# ref    = "…"                            # what was checked (a command, a URL, a file)
# digest = "sha-512:…"                    # OPTIONAL: verified where the tool can resolve `ref`
                                         #   as a local file; carried as declared otherwise (P9).
                                         #   M11 domain `evidence-record:`, DELIBERATE READ-ONLY
                                         #   LEGACY bare wire form (§7) — the same
                                         #   citation kind as a claim's own `record_hash`, but
                                         #   accepted in the `evidence-record:` bare form throughout
                                         #   0.3.x with NO WARNING emitted for this field; migration
                                         #   to a typed form is a 0.4 change, never a bare-form
                                         #   ERROR unlike `[policy].hash`/`inputs[].digest`
# uri    = "…"                            # OPTIONAL

[validity]
stale_after = "2027-03-19"               # REQUIRED when the contract sets stale_after; MUST equal
                                         #   issued_at + the contract's duration (a ceiling: earlier
                                         #   is allowed, later or absent is an error)
# invalid_if is not a field: P7 fixes it — contract hash, package hash or subject identity change.
```

### 5.0 Decision validity is transitive (`check-decision`)

A decision is valid only if everything it decided about is valid: `check-decision` re-runs
`check-contract` (with `--previous` when the contract supersedes another) on the bound contract,
the format validator and `check-package` on the bound package, recomputes both hashes and the
subject identity from the presented files, and only then evaluates §5.1–§5.2 against the coverage
it computed itself. A decision whose bindings resolve to an invalid contract or package is invalid
even if its hashes match — hashing an invalid file does not launder it. Coverage output is a
diagnostic; it never establishes validity on its own.

**Verification runs.** Every `[[verification.run]]` MUST carry `claim`, `command`, `observed`,
`result` and `at`; an incomplete run is an error, not an absent run. Runs may only name claims that
are coverage witnesses (claims that met a floor in the computed coverage) or claims cited in a
`basis`. **Conflicting runs on one claim: the worst result wins** (`fail` > `error` > `not-run` >
`pass`). Under `mode = "re-execute-all"` every basis claim of every `satisfied` mandatory
disposition — including the witnesses of a cross-cutting requirement — needs a `pass` run; one
passing run never covers another claim.

**Basis.** A disposition's `basis` may list only claims that the computed coverage names as
witnesses for that requirement; an unrelated claim in `basis` is an error. The **basis claims of
R** are the claims the computed coverage names as witnesses for R (for a cross-cutting R, its
candidate claims meeting every demand) together with the claims cited in R's disposition `basis`;
the union is normative so the adverse rule can never be narrowed by citation (§5.2). Residual: an
unrecorded run is a falsification risk, out of scope (P9).

### 5.0a Effect eligibility (what a downstream gate may act on)

A gate that unlocks an effect (publish, deploy, pay, merge) may act only on a decision that is
**valid** (§5.0), **current** (its bindings match the contract, package and subject presented to
the gate), **unexpired** (`validity.stale_after` has not passed — and it is required, and capped at
`issued_at` + the contract's `stale_after`, whenever the contract sets one), **not lapsed** (no
`[[condition]].due` is in the past; every `due` is an ISO date, else invalid), issued under a
contract whose `phase` is `final`, with `provisional` absent or false, and whose verdict is
`accepted` — or `accepted-with-conditions` only where the gate's own policy says conditions may be
outstanding. `check-decision --effect` evaluates exactly this and fails closed; a decision that is
valid as a historical record can still be ineligible for effect.

### 5.1 Verdict ↔ disposition coherence (`check-decision`)

The verdict is a function of the **mandatory** dispositions only (optional requirements never
change it; their dispositions are reported), evaluated top-down, first row that matches:

| row | when (mandatory dispositions) | conditions | verdict |
|---|---|---|---|
| 1 | any is `unsatisfied` | any | `rejected` |
| 2 | none `unsatisfied`, any is `insufficient-evidence` | ≥ 1 with `owner = "producer"` per insufficient-evidence requirement | `evidence-requested` |
| 3 | all in {satisfied, satisfied-with-conditions, waived}, not all `satisfied` | ≥ 1 | `accepted-with-conditions` |
| 4 | all `satisfied` | none | `accepted` |

Every other combination is invalid (all-satisfied with conditions; conditional/waived rows with
zero conditions; a `not-applicable` disposition on a mandatory requirement). **Conditions bind to
requirements:** every `[[condition]]` names a requirement whose disposition is
`satisfied-with-conditions`, `waived` or `insufficient-evidence`; a condition on a `satisfied` or
optional requirement is an error (so an optional requirement can never be
`satisfied-with-conditions`). Reverse: every `satisfied-with-conditions` disposition cites ≥ 1
condition naming it, under EVERY verdict; when the verdict is `accepted-with-conditions`, every
MANDATORY `waived` disposition cites ≥ 1 condition naming it; when the verdict is
`evidence-requested`, every MANDATORY `insufficient-evidence` disposition cites ≥ 1 condition
naming it with `owner = "producer"`. Optional `waived` and `insufficient-evidence` cite no
condition. This table is the executable rule. `states.toml`'s `[[verdict_rule]]` rows carry it as **structured
predicates** (`mandatory_any`, `mandatory_all_in`, `mandatory_not_all`, `conditions`), the
decision checker evaluates THOSE rows (first match wins), and `check-states` enumerates every
input combination — mandatory statuses × optional statuses × condition count — against expected
outcomes written independently of the evaluator, so a tampered row or a tampered evaluator is
caught.

### 5.2 Disposition ↔ coverage coherence (P3, P4)

Let `cov(R)` be the computed coverage status (§6). Then:

- **Adverse runs bind every mode and every disposition.** If the worst-result run on ANY of R's
  **basis claims** (§5.0: `witnesses(R) ∪ cited basis` — the union is normative here so the
  adverse rule can never be narrowed by citation) is `fail`, R may be dispositioned only
  `unsatisfied` or (if `waivable`) `waived`; if it is `error` or `not-run` under `re-execute-all`,
  only `insufficient-evidence`, `unsatisfied` or `waived`. A consumer that watched a check fail
  cannot call the requirement satisfied under any mode, including `spot-check` and
  `package-trusted`, and cannot route around it with a condition. The **positive** pass-run
  obligation below (`satisfied`, `satisfied-with-conditions`) is unaffected by this widening: it
  ranges over the cited `basis` only.
- `satisfied` requires `cov(R) = satisfied`, AND, when `verification.mode = re-execute-all` (or
  the requirement's `independence = consumer-run`), a `[[verification.run]]` with `result = pass`
  for **every** `basis` claim (§5.0).
- `satisfied-with-conditions` requires ≥ 1 cited condition **whose `requirement` is R** (a
  condition naming another requirement never counts), the same run obligations as `satisfied`
  under `re-execute-all`/`consumer-run` when `cov(R) = satisfied`, and: `cov(R) = satisfied`
  (a condition on top of a met requirement — e.g. a documentation follow-up), OR `cov(R) ≠
  satisfied` AND `waivable = true` — because accepting a below-floor requirement on a promise IS a
  time-bounded waiver, and a non-waivable requirement cannot be waived by any name. In the second
  case the disposition MUST also carry `[disposition.waiver]` with `code = "deferred"`.
- `waived` requires `cov(R) ≠ satisfied` (or an adverse run, above), `waivable = true`, a full
  `[disposition.waiver]`, and — when the verdict is `accepted-with-conditions`, for a mandatory R
  — ≥ 1 condition whose `requirement` is R (a waiver without its own remedy condition is only
  legal under `rejected`/`evidence-requested`, never as part of an acceptance).
- `insufficient-evidence` requires `cov(R) ∈ {partial, deviation-declared, missing, gap}` or a
  verification run with `result ∈ {fail, error, not-run}` on every basis claim.
- `unsatisfied` requires `cov(R) ≠ satisfied` or a verification run with `result = fail`.
- `not-applicable` is admissible ONLY on an OPTIONAL requirement, and requires a `[[deviation]]` of
  kind `not-applicable` naming R (no waiver — the decorative ceremony is dropped; there is nothing
  to waive on a requirement that was never decisive). A MANDATORY not-applicable requirement is
  dispositioned `waived` instead, with `[disposition.waiver].code = "not-applicable"` (needs
  `waivable = true` and a full waiver). A NON-waivable mandatory requirement that is genuinely
  not-applicable is a CONTRACT DEFECT, not a disposition choice: it is routed via a `[[deviation]]`
  `kind = "requirement-defect"` and `[[requirement_feedback]]` (§3.5) asking the next contract
  version to drop or narrow it; until then the verdict stays `rejected`/`evidence-requested` on
  that requirement.

A decision violating any row is **invalid**; the tool refuses to emit it and says which row.

### 5.3 Decision lifecycle

Per states.toml `decision`: `accepted` is terminal until `stale` (P7) or `invalidated` (a
defeater: evidence shown false, an incident traced to a satisfied requirement); both lead to
`reassess` = a new decision. `accepted-with-conditions` becomes `accepted` only through a **new decision document** issued
when every condition's obligation is `discharged` — one that binds the superseding package that
discharged them and passes §5.0 in full (the tool's `discharge-conditions` transition names the
successor decision; nothing is promoted in place). It becomes `lapsed` when a condition's
obligation `expired`. `evidence-requested`
and `rejected` await a superseding package, which gets a new decision. Resubmission is never an
edit of the old package. The consumer records lifecycle events as new documents or as event lines
beside the decision (`acceptance-decision.events.jsonl`, the obligation format's JSONL discipline);
a published decision is never mutated in place (format design rule 6, generalised).

### 5.4 Derived decisions — a recorder, never a fourth role

Every decision in `/0` speaks in the contract's authority's name: `issuer` resolves to
`[acceptance].authority` (P5, §5, unchanged by anything below). Sometimes the decision is a
mechanical readout of an act a DIFFERENT party took — an external committee's merge, an external
review's approval, an external process's close — and the document is typed into
`acceptance-decision.toml` by someone who did not take that act. `[document].recorded_by` names
that someone, distinct from `issuer`:

- `issuer` still names the contract's authority (P5, unchanged) — nothing here creates a second
  issuer axis; the decision speaks in the authority's name exactly as every `/0` decision does.
- `[document].recorded_by` is REQUIRED whenever `[derivation]` is present: the party that actually
  wrote the bytes of this file. **A recorder TRANSCRIBES a decision it observed; it never DECIDES**
  — the rule this field exists to make visible, distinct from `issuer` (who the decision speaks
  for) and from `[acceptance].authority` (who the contract names as entitled to decide).
- `[derivation]` carries how the transcription was derived: `authority_act` (what the external
  authority did, one short token or phrase — `"merge"`, `"approval"`, `"close"`), `rule` (the
  declared mapping from that act to this decision's verdict/dispositions, stated in full, never
  implied — P9: the protocol states structure, never truth of judgment), and `evidence` (a
  nonempty list of `{ref, digest?, uri?}`: what was checked). `check-decision` validates the shape
  of `[derivation]` and, where a declared `evidence[].digest` names a `ref` the tool can read as a
  local file next to the decision, recomputes and compares it; an entry naming a remote resource
  the tool cannot fetch is carried as declared, never silently treated as verified.
- **`recorded_by` MAY equal the package's producer identity (§4.1 rule 7) ONLY when
  `[parties].boundary = "cross-org"` (§3.4a) AND the contract's authority is a genuine THIRD
  PARTY** — distinct from both the named consumer and every producer identity. Otherwise it is an
  ERROR. Reasoning: internally, or whenever the authority IS the consumer or the producer itself,
  the producer recording its own decision collapses the very role separation P5 exists to keep
  (the producer never decides). Only when a real outside party holds the authority, and the
  producer is merely the one who transcribed that outside party's act because the outside party
  will not itself operate this tool, does "recorder = producer" stop being a conflict of interest
  and start being an honest description of who typed the file.

### 5.5 Closed without a merits decision

Some deliveries end without the authority ever rendering a merits judgment: an external process
closes the item for a reason outside the delivered artifact (a policy change, a duplicate, a
process timeout), and recording that close as `rejected` would misrepresent it as a judgment on
the merits that never happened (never `rejected`, per §5.5).

`[document].merits = true | false` (OPTIONAL, default `true`) states whether this decision renders
a merits judgment at all. `merits = false` REQUIRES `[document].reason` (a nonempty string: what
closed it, plainly) and REQUIRES `[document].verdict = "lapsed"` — the SAME state name the decision
lifecycle already uses for an `accepted-with-conditions` decision whose condition obligation
expired (`states.toml`, `condition-expired`), reused here for a second, direct path:
`close-without-merits` (`states.toml`, `machine.decision`), `assessing → lapsed`, guarded on
`document.merits == false`, requiring `reason`.

**Why `lapsed` and not a new verdict (plan choice 1).** Both cases share the
shape a downstream reader needs: no effect may ever be taken on this decision's say-so (§5.0a), and
re-opening it is a `reassess`, exactly like every other `lapsed` decision. `DECISION_VERDICTS` and
`[[verdict_rule]]` (the 4-value, disposition-driven verdict axis, §5.1) are UNCHANGED — a
`merits = false` decision is never evaluated against them, because no merits judgment was made for
them to be computed from. This build did NOT find `lapsed` misleading enough to justify a new word;
that call may still be overturned and a distinct verdict added instead.

**Consequences:**

- A `merits = false` decision is NEVER effect-eligible (§5.0a: eligibility requires `verdict =
  "accepted"`, or `"accepted-with-conditions"` under the gate's own policy — `"lapsed"` is
  neither).
- It MUST NOT carry `[[condition]]` entries — no obligation arises from a decision that renders no
  merits judgment.
- It MAY still carry `[[disposition]]` entries the ordinary way, but the "every contract
  requirement needs a disposition" rule (§5, the decision-side sibling of §4.1 rule 2) is relaxed
  to a WARNING, never a hard error: since no merits judgment happened, a `merits = false` decision
  may omit per-requirement dispositions it never reached.
- `merits = false` is INCOMPATIBLE with `verdict ∈ {accepted, accepted-with-conditions, rejected,
  evidence-requested}` — an ERROR, because each of those verdicts asserts exactly the judgment
  `merits = false` says never happened.

## 6. Coverage — the computed function

`coverage(contract, package) → {requirements: {id → status, basis, reasons}, summary}`.

### 6.1 The one core ordering: the warrant axis

`T1 > T2 > T3 > T4 > T5` — the format's closed, artifact-agnostic `epistemic_tier`. A claim's
tier is the strongest tier among its **passing** evidence records; a record's tier is its declared
`epistemic_tier`, or, when absent, the CEILING the package's profile assigns to the record's
`method` (or `kind`) — and a record the profile cannot place is **indeterminate**: it contributes
no tier and satisfies no floor. The core orders nothing else; grades, bands, families and kinds
are profile vocabulary (§6.6, P11).

**Tier-ordering note.** One tier ordering exists (`T1 > T2 > T3 > T4 > T5`), and no
requirement compares against a second, different ordering. What is claim-relative, not universal,
is *which* tier a given requirement needs: `min_tier` is set per requirement, and the assurance
class a contract declares (Glossary, above) sets the floor that per-requirement `min_tier` values
must meet. "Evidence strength is claim-relative" names that the target moves with the requirement
and its class, not that the ordinal scale itself is more than one ordering.

### 6.2 A claim meets an item requirement's core floor iff

1. `claim.clause == R.id` and `claim.status == "evidenced"`;
2. `weighted_required` ⇒ the claim's weight is **granted by the format validator** — a claim
   the validator reports as weight-refused or weight-pending is unweighted here whatever its
   `weight` string says (the manifest requests weight; the validator grants it);
3. `tier(claim) ≥ min_tier` (T1 highest);
4. `methods` given ⇒ at least one passing record's `method` (or `kind`) is in `methods`;
5. `control_required` ⇒ the claim carries an observed-red control (`control.expectation ==
   control.observed == "red"` and `control.of_claim == claim.id` on one of its evidence records)
   or a `self_verify.watched_fail` table;
6. `recipe_required` ⇒ `[claim.self_verify]` with nonempty `command` and `expect`;
7. `freshness = "delivered-revision"` ⇒ every passing record relied on carries
   `captured_at_revision` (or the profile's alias) equal, in full, to the package's subject
   identity — a record without the field, with an abbreviated value, or with both the core name
   and the alias present and unequal, fails freshness. **Freshness changes requirement
   satisfaction only.** It never makes a record inadmissible, never changes its weight, band, tier
   or `subject_hash` binding — the format's rule that the capture revision is not a validity key
   stands; the consumer is merely declining to rely on a record captured elsewhere;
8. `independence = "author-not-producer"` ⇒ every record relied on carries a nonempty `author`
   outside the package's producer identity set (§4.1 rule 7); `independence = "third-party"`
   (§3.7) ⇒ the SAME check, PLUS every record relied on carries an `author` also different from
   `[parties].consumer.name` — independent of both sides, not the producer alone;
9. `build_inputs_required` (§3.7) ⇒ EVERY record relied on that is PRODUCED BY RUNNING A TOOL
   (`family != "judgment"`, B3) carries a nonempty `build_inputs` list (B20); a `judgment`-family
   record (`human-review`, `llm-review`, B4) names a `reviewer`, not a tool, and is exempt — met
   vacuously when no record relied on is tool-produced;
10. `tool_qualification_required` (§3.7) ⇒ EVERY record relied on that is PRODUCED BY RUNNING A
    TOOL (`family != "judgment"`, B3) carries a `tool_qualification` table with a nonempty
    `basis` (B21); the SAME judgment-family exemption as cond 9;
11. `coverage_min = { metric, value }` (§3.7), when declared, ⇒ at least one record relied on
    carries a `coverage` table (B21) whose `metric` equals the declared `metric` (a different
    metric is incomparable, never a pass) and whose `value` is `≥` the declared `value`;
12. every profile floor the contract declares for this requirement is met (§6.6). A declared floor
    is always evaluated: if the package's profile is not one the floor names, or no binding for that
    profile is available to the evaluator, the floor is **not met** — never skipped.

"Relied on" in 7–11 means the passing evidence records that establish the tier and family for this
claim, plus the record carrying the observed-red control when `control_required` is met by a
control, plus the carrier of `watched_fail` when `control_required` is met that way; conds 9-10
narrow this set further, to the `family != "judgment"` subset. Freshness
deliberately binds these carriers: a control demonstrates the delivered check only when produced
against the delivered revision. Exempting them would let a control captured against an old recipe
vouch for a changed check — fail-open on the very property the control exists for; the
per-requirement `freshness = "any"` valve already relieves toil where it is genuinely not needed.
A claim relying entirely on cross-manifest reference records (format B8) can never meet
`build_inputs_required` or `tool_qualification_required`: a reference record carries no
`build_inputs` list and no `tool_qualification` table of its own (it cites another manifest's
evidence, B8 step 2), so it is `family != "judgment"` yet structurally empty on both fields — this
is fail-closed by design, not a vacuous pass and not a defect.

### 6.3 Status per item requirement

- `satisfied` — ≥ 1 claim meets the floor;
- `partial` — none meets the floor, but ≥ 1 claim has `status ∈ {evidenced, partial}`;
- `deviation-declared` — none meets the floor and a `[[deviation]]` names R;
- `gap` — claims exist, all `gap`/`parked`/`blocked`, no deviation;
- `missing` — no claim names R at all (a package error, still reported).

`reasons` names, per claim, the FIRST floor condition it failed, worded so the producer knows what
to add.

### 6.4 Cross-cutting requirements

For `kind = "cross-cutting"`: the candidate set is every claim with `clause ∈ over` (or all
claims when `over = "all"`) and `status = evidenced`. **An empty candidate set never satisfies**:
the requirement is `partial` (there is nothing to constrain, so nothing has been shown). Otherwise
the requirement is `satisfied` iff every candidate meets every demand: the core demands
(`min_tier`, `weighted_required`, `control_required`, as in §6.2) and every
`[requirement.demands.fields]` entry, where `f = "tok"` holds iff the claim's field `f` exists, is
a string, and its **leading token** equals `tok` — leading token = the first whitespace-delimited
word with any trailing `:`, `;` or `,` removed (so `bounds = "bounded: unwind=8"` has leading
token `bounded`). `[requirement.demands.fields_exact]` entries require the whole string to be
equal. Failing that: `partial` with the offending claims listed, or `deviation-declared` if a
deviation names it. `over` never names a cross-cutting requirement (§3.1 rule 4).

### 6.5 Summary and acceptability

```
mandatory_total, mandatory_satisfied, optional_total, optional_satisfied,
acceptable = (mandatory_satisfied == mandatory_total)        # rule "all-mandatory-satisfied"
```

`acceptable` is a computed fact, not a decision: the decision may still be
`accepted-with-conditions` on an unacceptable package through waivers and conditions (P4), and
`rejected` on an acceptable one if the consumer's own runs failed (§5.2).

### 6.6 Profiles — the projection mechanism

A **profile** is an acceptance meaning (Glossary). The protocol projects a profile onto one kind of
production through a **profile binding**: a document plus code that supplies, for that kind of
production, ALL of:

1. the `method`/`kind` ⇒ `epistemic_tier` CEILING table (§6.1);
2. the fields of `[requirement.evidence.profile."<id>"]`, a **floor-schema validator** (closed
   vocabularies, unknown keys are errors) and the rule for how a claim meets the floor (an
   ADDITIONAL conjunct in §6.2 condition 12, never a substitute for the core floor);
3. the claim fields its cross-cutting `demands.fields` may name;
4. the alias of `captured_at_revision` and the subject identity it binds to for FRESHNESS purposes
   (in `/0`, fixed to `commit` for every bound profile — `captured_at_revision` is revision-shaped,
   so `freshness = "delivered-revision"` is only ever satisfiable against a git-revision subject;
   this stays unchanged, and holds identically for every profile it binds).
   The classification and value of a package's certified subject identity — which of B1's kinds
   (`git-revision` / `content-digest` / `components`) it carries, and the comparable wire value —
   is never a per-profile computation: every profile reaches it through the format core's own
   shared, profile-blind functions (`check_core.subject_identity_kind`/`subject_identity_value`),
   the SAME classification `check_binding_chain`'s B17 narrowing uses inside the format core
   itself. The `[binds].subject` identity BINDING (the field name and value a package presents) is
   not fixed to `commit`: it follows whichever B1 certified identity kind the package declares
   (§7);
5. the recipe carriers and the input sets change impact expects declared (§8);
6. any narrowing of `[subject].kind`, typing of `constraints`, and **every package-level
   constraint the profile imposes** (e.g. "`dirty` must be false"), exposed as a check the core
   calls — a constraint written only in the profile's prose is not a constraint;
7. a **floor comparator** for the tightening rule (§3.5): given two floor tables, "weaker /
   equal / tighter / incomparable"; incomparable is an error;
8. the **package validator** the core delegates to for the manifest's own admissibility rules.
   Every bound profile reaches this through the format's profile-neutral core validator
   (`check_core.py`'s `validate`/`dispatch`): the format
   core reads the package's own declared `[format].profile` and resolves the right meaning module
   itself, so `tools/check_acceptance.py` (the `acceptance/verification` profile's own entry point,
   predating this profile-neutral dispatch, and still the tool used directly for that profile) is no
   longer the only path in. A profile still needs a
   binding entry in `protocol_acceptance/tools/profiles.py` before the *protocol* evaluates it
   (P11: the protocol core never guesses a binding); `acceptance/verification`,
   `acceptance/conformance` and `acceptance/troubleshooting` are bound as of `/0`. A profile with
   neither a format-core meaning module nor a protocol-side binding still cannot be evaluated —
   fail-closed, never a silent default to another profile's rules.

A profile never adds a document, a state, a verdict, a disposition or a rule. The first profile
is `../../format_acceptance/profiles/verification/code/rust.md` (illustrative; profile vocabulary). A contract, package and decision that use no profile floor still pass
through a profile's package validator (item 8): `[format].profile` is REQUIRED per format B12 (a
package omitting it is invalid at the format layer, no compatibility default), and the core
delegates to the format's profile-neutral core validator bound to whichever meaning the package
declares (item 8). The protocol documents and rules are profile-blind (P11); package admissibility
now runs through the same profile-neutral core for every bound profile, not through a
verification-specific path.

## 7. Binding and hashing

- **One wire form (2026-09-24).** Contract hash: M11
  (sha-512, domain-separated) with prefix `contract:`, written and read as the self-describing
  `contract:sha-512:<hex>` (additive-separator rule). Package hash: the existing `manifest:`
  domain, `manifest:sha-512:<hex>`. Decision hash: `decision:`, `decision:sha-512:<hex>`. This is
  the SAME self-describing wire form `hashdomains.digest` writes for every format-core domain
  (core.md B16) — the earlier m11.py wire form for these three fields, bare `sha-512:<hex>` with
  the domain baked into the hash bytes but not repeated in the wire string, is RETIRED: a
  contract/package/decision document carrying it on `[contract].hash`, `[binds].contract.hash` or
  `[binds].package.hash` is an explicit ERROR naming the expected form, not merely a downstream
  mismatch (no compatibility shim with pre-lock drafts). `record_hash`'s separate
  `evidence-record:` wire is UNCHANGED by this change and stays accepted read-only with a
  WARNING throughout 0.3.x (`hash-domains.md`'s Read-only legacy record wires section;
  retirement to ERROR is a 0.4 change).
  **The self-describing set extends to two more
  fields, no new domain registered:** `[policy].hash` (§3) now writes and requires
  `normative-reference:sha-512:<hex>` — the format core's own governing-document domain, exposed
  through `m11.py` for the first time; a bare `[policy].hash` is the same explicit ERROR as
  above. `[[claim.evidence.inputs]].digest` (§4/§8) now writes and requires
  `subject:sha-512:<hex>` — `subject:` already registered (B1 certified identity uses it
  self-describing at the format core; only this module's own per-input computation lagged); a
  bare form there is likewise an explicit ERROR. `[[derivation.evidence]].digest` (§5.4) is
  DELIBERATE READ-ONLY LEGACY, staying on the SAME `evidence-record:` bare wire the recompute
  already uses (it is the same kind of citation `record_hash` is — a local evidence artifact's
  digest — accepted in the `evidence-record:` bare form throughout 0.3.x, with NO WARNING emitted
  for this field, never verified when the cited `ref` is unresolvable, P9; migration to a typed
  form is a 0.4 change); it is listed here, not silently left bare.
- **Subject identity = format identity.** A package's `[subject]` MAY
  carry any B1 certified identity kind the format core registers — git-revision (`commit`),
  content-digest (`digest`), or components (`digest` over the B1 canonical serialization; the
  aggregate `subject:` digest over components IS the components identity, not a second one) — the
  protocol no longer fixes it to `commit` alone. Classification and comparison reuse the format
  core's own functions (`check_core.subject_identity_kind`, `subject_identity_value`) rather than
  re-implementing them. A decision's `[binds].subject` MUST carry the SAME identity form the bound
  package declares: `{ commit = "<40-hex>" }` for git-revision, `{ digest =
  "<subject:sha-512:hex>" }` for content-digest or components. `check-decision` compares
  `[binds].subject` against the presented package's `[subject]` on that same field, with the digest
  form compared case-insensitively on its hex (B16); a form or value mismatch is staleness (P7),
  exactly as a commit mismatch always was. Multi-file subject hashing beyond B1's own components
  shape stays PENDING the format's P12 work.
- `/0`'s freshness alias mechanism (§6.2 cond 7, §6.6 item 4) is UNCHANGED and stays
  git-revision-scoped: `captured_at_revision` (or its profile alias) is a revision-shaped field, so
  `freshness = "delivered-revision"` is only ever satisfiable when the package's subject identity
  is git-revision. A package identified by content-digest or components has no
  `delivered-revision` freshness binding yet; the per-profile `subject_identity` binding of §6.6
  item 4 that would extend freshness to those identity kinds is declared but still lands with the
  item 8 extraction — this change leaves that scope exactly where it was.
- Cross-organisation wrap (P10): document bytes as the in-toto `predicate`, `predicateType`
  `https://acceptance-format.example/protocol/{contract|package|decision}/v0`, `subject[]`
  carrying the artifact's sha256 — dual-hashed with the M11 sha-512 inside the document (this also
  resolves a downstream verdict envelope's `sha256:` field mismatch by carrying both). DSSE for signing;
  Sigstore bundle or SCITT receipt for transparency. Declared path, not implemented in `/0`.

## 8. Change impact and re-verification

Given an `accepted*` decision and a new artifact state (new identity, or a list of changed inputs):

1. The decision is `stale` by P7. Nothing else is needed for that.
2. Per evidence record relied on by a `satisfied` disposition, classify:
   - `still-applicable` — the record declares `[[inputs]]`, every input carries a digest, every
     input's digest is unchanged, and the record's `tool` and `semantics` are unchanged;
   - `definitely-invalidated` — a declared input's digest changed, the claim's `item` changed, or
     `tool`/`semantics` changed;
   - `possibly-invalidated` — the record declares no inputs, or any declared input lacks a
     digest, or the changed set cannot be compared (a path list without digests can only prove
     change, never continuity). Undeclared or undigested inputs are never treated as unchanged.
   Any change to the subject state — a new commit OR a changed path at the same commit (a dirty
   tree) — makes the decision `stale`; "no listed path is in the declared set" is a statement
   about that path list, not about the subject.
3. Mint one obligation per invalidated claim in the obligation format's `minted{duty}` shape
   (`action = "re-verify"`, `target = <claim id>`, `trigger = subject-changed{from, to}`,
   `required_by` from the contract's `stale_after` or the consumer's policy, `discharge_predicate
   = coverage(<requirement id>) = satisfied in a superseding package` (requirement ids, never
   claim ids — coverage is keyed by requirement), `authority` = the contract's authority),
   plus one `stale_detected{context_hash_old, context_hash_new}` event for the decision.
4. The output object: `{evidence_id, class, reason, changed_inputs[], obligation_id?}` per record,
   and the requirements whose disposition is now unsupported.

Non-artifact inputs (tool identity, semantics/flags, environment) are already fields on every
evidence record (`tool`, `semantics`); a profile lists which of them belong in every declared input
set so the rule is sound for its production kind.

## 9. Composition with the rest of the stack

| protocol | how acceptance composes with it | status |
|---|---|---|
| obligation lifecycle | conditions → `minted` duties; discharge → `accepted`; expiry → `lapsed`; change impact → `stale_detected` + re-verify duties | composes with `format_obligation`; nothing new |
| work contract (request → deliver → verify → close) | the *verify* step IS this protocol; the request carries or references the contract; `deliver` carries the package; `close` follows the decision | `stack.md`; not implemented |
| authority / grant | `[acceptance].authority` and `decision.issuer` resolve to a grant or a governance class; the protocol only carries the reference | composes; closes an authority-reference gap for one artifact class once one contract names one |
| consequential-effect gate | an **effect-eligible** decision (§5.0a: valid, current, unexpired, final phase, not provisional) is an *input* to the publish/deploy gate; the gate is outside this protocol | composes |
| transaction / compensation | out of scope: a decision has no side effects to compensate | deferred |
| offline reconciliation | every document carries what the bundle rule needs: base hashes (`[binds]`), versions (`[document]`), validity (`[validity]`); mismatch on return ⇒ `stale`; matching bindings make the decision *valid*, effect still needs §5.0a | built in |
| version negotiation | `protocol` major in the id, `minor` additive, `[ext]` with `critical`; unknown critical ⇒ reject; unknown non-critical ⇒ ignore and preserve | built in |
| signing / transparency | P10 | declared path |

## 10. Rendering: the single "acceptance file" view

A renderer MAY produce one Markdown view over the three documents — per requirement: statement ·
mandatory · floor · producer's claims · computed coverage · disposition · conditions. It is a
projection (the format's ledger discipline: source of truth is the TOML; the view is regenerated,
never edited). This is the "one acceptance file" a consumer wants to see, produced from the three.

## 10a. About the TOML examples in this document

The fenced TOML blocks in §3–§5 are **fragments** that illustrate fields; they are not complete,
validating documents (the contract fragment shows six requirement ids and spells out two). The
complete, validated chain is `protocol_acceptance/examples/rust-delivery/` (illustrative; profile
vocabulary); the tool's selftest carries a second complete chain. A builder writes documents from
those, not from the fragments.

## 11. What `/0` deliberately does not do

- No acceptance rule beyond `all-mandatory-satisfied` (a decision-table rule is reserved). [A-10]
- No signing, identity, transport or transparency (P10 names the path). [A-01]
- No multi-artifact bundles; one contract, one package, one decision per artifact. [A-11]
- No negotiation messages (offer, counter-offer) — the `supersedes` chain is the only negotiation
  record; the work-contract protocol owns messaging. [A-12]
- No arithmetic over tiers into a score (the format's rule 3 binds here too). [A-13]
- No trust in declared inputs beyond "declared" — undeclared inputs are unknown, never unchanged. [A-14]
- No profile vocabulary in the core (P11). [A-15]
- No verification "score": iteration lowers and raises FLOORS on the record (P12); nothing is
  ever summed into a number (format rule 3). [A-13]
**Residual — comparator strength.** P12's tightening rule (§3.5) treats
a profile floor key as weakened, equal, or tightened entirely through that profile binding's OWN
comparator (§6.6 item 7 — "given two floor tables, weaker / equal / tighter / incomparable").
`/0`'s core enforces the STRUCTURE of that call (a profile id with no comparator available makes
the comparison an error, never a silent pass — §3.5, §6.6 item 7) but has no way to audit the
comparator's own JUDGMENT: a profile binding whose comparator answers `"equal"` for every pair of
floor values on some key neuters tightening for that key alone — the chain still validates, no
error is ever raised, and the key can be silently loosened in substance while `/0` reports the
step as tightening-clean. Fail-closed (the missing-comparator case) is the only failure mode this
core catches; a comparator that returns a wrong-but-well-formed verdict is reviewer work (P9),
same as every other claim this protocol carries structurally and never verifies for truth. [A-16]

- No proof that a declared `independence` value is true: `author-not-producer`, `consumer-run` and
  `third-party` are declared fields, checked for consistency, never for truth (P9). [A-17]
- No check that an assigned assurance class is the right one for the artifact: the consumer's
  authority assigns it, and the producer never does (§3.7). [A-18]
- No proof that a class table's floors are adequate for a domain's real risk: the table is data a
  domain owns and revises; the core only enforces whatever floors it states. [A-19]
- No proof that a declared timestamp is true, or that the evaluating gate's clock is honest:
  `issued_at`, `validity.stale_after`, condition `due`, and every `by = "clock"` transition
  (§5.0a's "unexpired"/"not lapsed" effect-eligibility tests among them) trust the declared value
  and trust "now" at the point of evaluation; nothing checks either. [A-21]
- No enforcement of the amendment current-pointer race beyond one sequential applier: §3.6 rule 1
  states the pointer discipline (read → check → write → atomic replace) holds only "per sequential
  consumer process"; concurrent appliers need an exclusive-creation lock the reference tool does
  not yet implement, so two appliers racing the SAME base outside that discipline is excluded from
  `/0` by prose, not by a guard. [A-22]
