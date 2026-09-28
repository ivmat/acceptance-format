---
type: reference
digest: Draft adapter specification for projecting contracts into worker briefs and assembling packages from reports.
---

# Adapter: the orchestrator's two mechanical directions — contract → brief, report → package (DRAFT)

> **Publication note.** This file is not part of the Class text locked in `CLASS-LOCK.toml`; it
> specifies a public tool feature that `acceptance_protocol.py` implements and cites by name.
> It is maintained as a living, draft document.

**Why this exists.** In an agentic delivery workflow the producer is often an automated worker
session, dispatched by an orchestrator. A worker should not need to read the whole protocol, and
should not hand-type hashes, commits, record pointers, tier ceilings or coverage totals — those
are mechanical, and every field a worker types by hand is a field that can be wrong. So the
orchestrator (a Python reference implementation today, with a future compiled implementation kept
in parity) does two mechanical projections, and the worker fills only the semantic slice in
between.

## 1. Down: `project-brief` — contract (+ policy) → the minimal brief a worker receives

Input: the bound contract version and the touch-list / allowed writes the orchestrator chose.
Output: a brief in the tool's own `worker-brief/v1` shape — no new brief format per delivery —
with:

| brief field (existing) | filled from |
|---|---|
| `goal` | `[subject].description` (one sentence) |
| `scope` | `[subject]` + the orchestrator's `allowed_writes` |
| `plan` | one line per requirement: `R<id>: <statement>` — statements only, no floors, no hashes |
| `done_criteria` | per requirement: the recipe as a command + expect the worker must make pass. Source, in order: the contract's optional `[requirement.evidence.recipe] {command, expect, control_patch?}` (the consumer names the check it will re-run — the mechanical source); else the profile's recipe carrier for the requirement's pattern (a template the projector fills with the subject's paths); else the brief says `recipe: proposed by worker` and the worker's `fill.toml` must supply it, which the assembler records and the consumer sees as producer-chosen. `recipe_required` alone (a boolean) is never enough to project a command. Cross-cutting demands rendered as one line each |
| `oracle` | the list of commands the worker must run and capture as transcripts for the report (§2) — the brief is invalid without one; the assembler does not run them |
| `decisions_collected` | the contract's `phase`, and which requirements are `draft` (the worker may propose `requirement-defect` deviations on those) |
| `allowed_writes` | the orchestrator's choice; never the contract, package or decision files |
| `provenance` | `authority-ruled` iff the contract is consumer-issued or ratified |

What is deliberately **not** in the brief: floors (`min_tier`, profile floors), hashes, the
authority, the disposition vocabulary, the lifecycle. The worker sees *what must be true* and
*what command must pass*; the floor is the consumer's business and the assembler's job to verify.
This follows a general local-goal-only principle applied to the protocol: the worker's contract
is the brief; the wider system's contract is the document.

Context cost: for the Rust example, the six-requirement contract (≈ 120 lines of TOML) projects
to a brief of ≈ 15 lines.

## 2. Up: `assemble-package` — worker report → `acceptance.toml`

Input: the brief, the worker's report directory (transcripts named per `done_criteria` line,
the exact file list, self-flagged deviations), the repo at the delivered commit. Output: a
protocol package. Mechanical fields (never typed by the worker):

| package field | assembled from |
|---|---|
| `[format]`, `[contract] {id, hash, requirements_total}`, `[spec]`, `[coverage]` totals | the contract file |
| `[subject].commit`, `dirty` | `git rev-parse HEAD`, `git status` |
| `[[claim]].id`, `clause`, `item` | brief line ↔ requirement id; `item` from the touch-list |
| `[[claim.evidence]] kind/method/family/epistemic_tier` | the recipe's command class (profile table: `cargo test` → unit-test/T3, `cargo kani` → kani-harness/T2, `cargo clippy`/`doc` → lint/T4) |
| `record`, `record_hash`, `captured_at_commit`, `tool`, `semantics` | the transcript file, its typed `record:` hash, the tool's `--version` line captured in the transcript; `captured_at_commit` is the commit **at execution time**, taken from the report manifest's `[report].commit` field — the worker must record it when the transcript is captured. Re-running a transcript on the worker's behalf is not implemented: `assemble-package` refuses (raises an error) a report manifest with no `[report].commit`, rather than re-executing anything or stamping the current HEAD in its place |
| `[[claim.evidence.inputs]]` | digests of the files the transcript's command read (the profile's declared input set) |
| `result`, `cases` | parsed from the transcript (`test result: ok. N passed`) |
| `self_verify.command/expect` | the brief's `done_criteria` line verbatim |
| `[claim.evidence.control]` / `watched_fail` | the mutation step the brief asked for, derived from the report's captured control transcript: the worker (or orchestrator) applies the patch, runs the recipe, observes red and restores the subject before reporting; the assembler only reads that recorded run — it does not apply patches, execute, or check restoration itself |
| `status` | evidenced iff the recipe passed at HEAD; else partial/gap |

Semantic fields the **worker** (or a validator seat) supplies, in a small `fill.toml` beside the
report — the only thing the agent writes by hand:

| field | who | why not mechanical |
|---|---|---|
| `claim.statement` | worker | what the evidence shows, in words a reviewer can falsify |
| `grade` | worker proposes, reviewer confirms | "does this evidence decide the item" is judgment, not mechanically decidable |
| `bounds` (contract/probe) | worker, from the harness | the assembler can read `unwind=` but not what the fixture covers |
| `watched_fail.perturbed/observed` narrative | worker | the patch is mechanical, the sentence is not |
| `[[deviation]]` text (`statement`, `cause`, `impact`, `remedy`) | worker | judgment; the assembler only knows *which* requirement is unmet |
| `weight` | assembler proposes `weighted` when every W2 condition is present; the worker may downgrade, never upgrade | fail-closed |

After assembly the orchestrator runs `check_acceptance.py --strict --strict-weight`,
`check-package` and `coverage`; the worker's report is not the verdict — the assembled package
plus the consumer's re-run is.

## 3. Staging and parity

- **Now:** both directions as verbs of `protocol_acceptance/tools/acceptance_protocol.py` (Python, stdlib),
  exercised by `acceptance_protocol.py --selftest` on a synthetic chain (`fixtures/verification_chain.py`).
  `examples/rust-delivery/`'s own `gen_package.py` does the "up" half by hand today and does not
  yet call `assemble-package`; making it a thin caller is future work.
- **Then:** a compiled orchestrator implementation performs the same two projections;
  the protocol's consumer-parity discipline applies (one format, two consumers, verdicts must agree
  on a corpus before the compiled side takes over) — the parity corpus is the set of briefs and
  reports the Python side has processed.
- **Workers fill manually only `fill.toml`**, from day one. Nothing else in the package is
  hand-typed — the same anti-hand-typing discipline the format applies to evidence records,
  applied here to the protocol.
