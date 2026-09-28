---
type: proposal
digest: Binding: estate-element — SKELETON (empty; bindings deferred) (frontmatter added 2026-09-22 for the protocol gate)
---

# Binding: `estate-element` — SKELETON (empty; bindings deferred)

binding path: `estate-element` · parent: `generic` (the core) · status: **candidate; wanted by an
orchestration layer** (orchestration layer → built subsystem, orchestrator → worker)

<!-- TODO(producer): structurally complete, semantically empty. Fill from the first
     orchestration-layer subject — a subsystem delivered against an orchestration-layer contract. -->

## What this binding is

A subsystem, repository, service or seat treated as ONE thing: the unit an orchestration layer's
registry rows, plans and contracts name. It is identified by its registry identity plus the
revision of its repo(s), and its recipe carriers are its own gates. It is the binding for
the "interface between system elements" idea; the same meaning across a company
boundary is a party-boundary matter for the protocol (P10), not a different binding.

## Subject kinds

<!-- TODO(producer): no base token exists. Declare via `[format].kind_registry` (F1): candidates
     `estate-element`, or finer `subsystem` | `repo` | `service` | `seat`. Decide one. -->

## Subject identity

<!-- TODO(producer): registry row id (an orchestration-layer registry) + repo commit(s) (an element may
     span repos, so `commit` may be a table, not a string — the same core/profile split concern as
     elsewhere, in the multi-repo form the format's own "no cross-file/workspace aggregation" note
     in spec/format.md declines today). -->

## Recipe carriers

<!-- TODO(producer): the element's gate suite (`gates/run_all.sh`, `tools/gate.py`), its selftests,
     `check_session_defaults.py`-shaped policy checks; the observed-red control is the gate's own
     seeded-bad fixture (evidence-types.md: `mechanical` family, planted-twin as disclosure only). -->

## Declared input sets (change impact)

<!-- TODO(producer): the element's repo tree(s), its gate manifest, the FORMAT-PIN digests it
     depends on. -->

## `constraints` typing

<!-- TODO(producer): e.g. `tier: <capability-tier string>` (a consumer's own routing scheme),
     `gates: green@<sha>`, `policy: <consumer's own governance record ids>`. -->

## Admissibility check (item 8b, this node's contribution)

<!-- TODO(producer): the binding-side admissibility check the core CALLS (protocol.md §6.6 item 8,
     D1 amendment A1). Slots this node owns: identity shape (the registry row id plus repo
     commit(s) — possibly a table, not a string, for a multi-repo element); admitted
     `[subject].kind` set (declared via `[format].kind_registry`, F1 — no base token exists yet);
     the package-level constraints declared above (`gates: green@<sha>`, `policy:`). This node has
     no single `dirty` flag; its nearest analogue is "every repo in the element's set is clean at
     its declared commit." The core supplies the entry point and orchestration (item 8a); the
     meaning supplies its own check (item 8b, meaning half); a leaf is evaluable only when both
     checks are available, else `indeterminate`. -->

## Leaves that exist on this node

None.
The first candidate is `acceptance/deliverable/estate-element`: a subsystem whose acceptance is discharged by referenced component acceptance records.
Contract binding and criterion coverage belong to the protocol.
The second is `acceptance/documentation/estate-element`: a repo's README / NOW / AGENTS against what the repo actually does.

## What this binding does not define

- No governance: what a passing record lets a downstream gate act on is the protocol's effect
  eligibility (§5.0a) and the orchestration layer's decisions, never this binding.
- No mapping from native orchestration-layer records (a decision's frontmatter, a gate-manifest
  gate, a finding) to an acceptance CLAIM — that mapping is absent; this binding does not invent it.

## Open questions

- Whether a system element's identity needs a multi-repo `commit` table (class change) or the
  element is always cut to one repo per manifest.
- Which publication tier a record on this node may occupy. This question remains open for the
  general core and is sharper here.
