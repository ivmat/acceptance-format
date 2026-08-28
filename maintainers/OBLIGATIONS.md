# Obligations inventory — every rule that gates the WEIGHTED tier

**This file is checked.** `tools/check_parity_selftest.py` parses it and fails if any row names a
parity case that does not exist, or omits one. It is gate step 6, so the inventory cannot drift
from the battery without the suite going red.

## Why it exists

Seven review rounds were closed by auditing *mechanisms* — the regexes, then the shared-module
wiring, then the separator classes. Round 8 found the limit of that method: the one obligation
implemented with a substring `in` rather than a regex (`positive_control`) was never looked at,
because the audit had enumerated regexes and it was not one. Auditing the mechanism finds every
instance of the mechanism, which is not the same as finding every obligation.

So this inventory is built the other way round: **walk the spec, list every MUST that affects
weight, and demand an enforcement site and a live parity case for each.** Completeness comes from
the spec side, where the obligations are defined, rather than from the implementation side, where
they happen to be implemented in whatever form.

## How to read a row

| column | meaning |
|---|---|
| **obligation** | the rule, in the spec's own terms |
| **spec** | the section that states it |
| **manifest** | enforcing function in `tools/check_acceptance.py`, or `n/a —` and the reason |
| **rendering** | enforcing function in `tools/check_ledger.py`, or `n/a —` and the reason |
| **parity case** | the `ParityCase.name` in `tools/check_parity_selftest.py` that pairs them, or `selftest:<fixture>` |

An obligation only ONE representation can carry cannot have a paired case, because the battery
asserts the two verdicts AGREE and here they correctly differ. Those rows cite
`selftest:<fixture>` — a fixture in the enforcing checker's own selftest — and the audit checks it
exists.

`n/a` is a claim that needs a reason, not a blank. A representation that structurally cannot carry
an obligation (a manifest has no tier markers; a rendering has no evidence records) says so.

## The inventory

| obligation | spec | manifest | rendering | parity case |
|---|---|---|---|---|
| Weight is explicit and defaults to absent | W1 | `_is_weighted` | `tier_marker` | `W1-silence-is-unweighted` |
| A row states at most ONE tier | W4 | n/a — a manifest has one `weight` field, so two values cannot be written | `tier_tokens_of_row` | `W4-two-tier-markers-declare-nothing` |
| Grade present and weight-eligible | W2.1, §1 | `check_claims` | `check_grade` | `W2.1-unweightable-grade-cannot-carry-weight` |
| Grade is one token from the closed set | §1 | `check_claims` | `check_grade` | `grade-outside-the-closed-vocabulary` |
| `clause_source` recorded | W2.3, P1 | `check_claims` | `clause_sources_in` | `P1-clause_source-absent` |
| `clause_source` not a reserved-unweightable value | W2.3 | `check_claims` | `clause_sources_in` | `P1-clause_source-read-off-its-own-evidence` |
| `clause_source` names exactly one source | W2.3 | n/a — one TOML field holds one value | `clause_sources_in` | `clause-source-reserved-token-behind-a-separator` |
| A deciding recipe is required | §3 rule 1 | `check_self_verify` | `check_recipe` | `recipe-absent` |
| `expect` required whenever `command` is present | §3 rule 2 | `check_self_verify` | n/a — a rendering's verify cell states the recipe and its expectation as one cell; `--execute` reads the manifest | `selftest:self_verify.command without expect FAILS` |
| A recipe reference must parse as a recipe (letter form OR literal command) | §4.2 | n/a — a manifest's `command` is a literal shell string, not a letter-and-argument reference | `recipe_reference_kind` | `S4.2-recipe-reference-that-names-no-command` · `recipe-as-a-backticked-literal-command` |
| A watched-fail witness is required | W2.5, P2 | `_has_watched_fail_witness` | `watched_fail_witness` | `P2-no-watched-fail-witness` |
| The witness binds to THIS row's own recipe | §4.1 | `check_watched_fail_block` | `watched_fail_witness` | `P2-witness-bound-to-a-different-check` |
| The witness states a perturbation and an observation | §4.1 | `check_watched_fail_block` | `watched_fail_witness` | `P2-witness-states-no-observation-or-perturbation` |
| The witness states when it was observed | §4.1 | `check_watched_fail_block` | `watched_fail_witness` | `P2-witness-states-no-date` |
| `positive_control` required on every `not-covered` row (structured OR plain syntax) | §4 | `check_self_verify` | `check_positive_control` | `not-covered-without-a-positive-control` · `positive-control-plain-declaration-is-witness-3` |
| `positive_control` witnesses only `not-covered` | §4.1 witness 3 | `_has_watched_fail_witness` | `watched_fail_witness` | `positive-control-does-not-witness-a-contract` |
| `positive_control` names an input, not a token | §4 | `check_self_verify` | `check_positive_control` | `positive-control-plain-declaration-of-one-token-names-nothing` |
| `contract` requires a symbolic domain (a test is never `contract`) | §0.5, §1 | `check_claims` | n/a — a rendering cites evidence, it does not carry evidence records, and the recipe LETTERS that imply a family (`K`, `T`, `N`) are per-envelope conventions the format does not define | `selftest:requires a SYMBOLIC domain` |
| `contract` evidence scope covers the claim's declared domain | §2 (CS-4, conjunct 2) | `_check_contract_scope_coverage` | n/a — a rendering cites evidence, it does not carry evidence records, so a record's own `bounds` is not there to compare against the claim's | `selftest:CS-4 scope coverage` |
| `bounds` required on `contract`/`probe` | §5 | `check_grade_companions` | `check_bounds` | `bounds-absent` |
| `bounds` states the token AND the limit | §5 | `check_grade_companions` | `check_bounds` | `bounds-token-with-no-stated-limit` |
| `bounded`/`unbounded` matched as exact tokens | §5 | `bounds_token` | `bounds_token` | `bounds-token-prefix-smuggling` |
| `status` is one of the closed vocabulary | §7.1, §7.3 | `check_claims` | `normalize_status` | `status-outside-the-closed-vocabulary` |
| `status` is present | §7.1 | `check_claims` | `process_row` | `status-cell-present-but-empty` |
| `status` × `grade` cohere | §7.1 | `status_grade_incoherence` | `status_grade_incoherence` | `S7.1-gap-status-with-a-grade-that-asserts-a-check` |
| `scope_ref` is a locator, not prose | §1, §7.1 | `check_grade_companions` | `check_out_of_scope` | `S7.1-out-of-scope-with-a-locator-free-source` |
| A predicate row states what it ranges over | §7.2, P3 | `check_claims` | `OVER_RE` via `process_row` | `predicate-over-must-be-declared-not-narrated` |
| A predicate row states its fraction | §7.2, P3 | `check_claims` | `FRACTION_RE` via `process_row` | `P3-predicate-with-no-fraction` |
| `blocked` names what blocks it | §7.3, P4 | `check_claims` | `BLOCKED_BY_RE` via `process_row` | `P4-blocked-without-blocked_by` |
| `[spec].axis` declared when anything claims weight | §6, W2.4 | `check_spec` | n/a — a rendering's axis is stated in prose above the table, outside any row; §6 declares it unenforceable there | `selftest:[spec].axis is REQUIRED` |
| Statuses asserting no check carry no evidence | §7.1 | `check_claims` | n/a — a rendering has no evidence records; it cites them | `selftest:must have NO evidence entries` |
| Stated tier counts match the computed ones | W5 | n/a — a manifest states no tier counts; `claims_total` is its analogue and is checked by `check_coverage` | `run_file` | `W5-a-clean-row-is-counted-in-the-weighted-tier` |
| A refused row is counted in neither tier | §8.1 | `check_claims` | `_finalize` | `refused-row-is-counted-in-neither-tier` |

## Obligations with NO mechanical enforcement anywhere

Listed because a silent row is the defect this file exists to prevent. Each is stated as a limit in
its owning spec section; none is silently unchecked.

| obligation | spec | why it is not enforced |
|---|---|---|
| The recipe is the *most specific* command that decides the row | §3 rule 5 | Explicitly advisory in the spec ("Not mechanically enforced; a reviewer can see it at a glance"). No checker attempts it. |
| The declared axis actually enumerates the spec | §6 | Not decidable. §6 states it is declared and reviewable, and "this axis is complete" is an unweighted claim. |
| An UNDECLARED predicate item is a predicate item | §7.2 | Detection is declarative by ruling; §7.2 states the residual out loud. Guessing from prose is the alternative, and it produced false refusals when tried. |
| The witness describes something that really happened | §4.1 | Shape only. §4.1 says a producer who writes a plausible sentence defeats it, and that the residual is review. |
| The recipe is a genuine oracle for the claim | §8.2 | `--execute` proves the command ran and produced its expectation. §8.2 states in full that no execution mode can establish more, and refuses only the mechanically visible degenerate case. |
| The cited `scope_ref` section says the item is out of scope | §1, §7.1 | Shape only, stated at the rule. |
| The stated `bounds` limit is the real limit | §5 | Shape only, stated at the rule. |
