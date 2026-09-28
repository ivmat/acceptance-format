---
type: reference
---
# ASSUMPTIONS — acceptance assurance boundaries

Every dependency this leaf does NOT gate itself is STATED here with its external gate + residual. No third state.

| Dependency | External gate we rely on | Residual |
|---|---|---|
| Python 3 stdlib | CPython's own test suite | trust CPython |
| bash / git | OS vendor | POSIX behavior assumed |
| python toolchain | its own CI / test suite | pinned; not internalized |

## Acceptance family — load-bearing assumptions of the Class rung (0.3)

Each row is anchored in the core spec text by its tag (`[A-nn]`) in `format_acceptance/spec/core.md` §5 or
`protocol_acceptance/spec/protocol.md` §11. `gates/check_assumptions.py` checks that every bullet in those two
sections carries a tag, that every tag has a row here, and that every row is cited there.
The public suite ships and runs this check and `gates/check_class_lock.py`, which checks
the latest public lock against the shipped Class text. The public lock retains each version's
file hashes; the upstream development repository gates their equality with its source lock.
Generic-core and apparatus scans run in the upstream development repository; the public
suite does not ship `check_core_generic.py`. Locking and passing checks do not ratify the class.

| id | assumption (what the core trusts and does not check) | external gate we rely on | residual |
|---|---|---|---|
| A-01 | Records and documents are not signed; integrity within the repository set comes from git history | git object integrity; the cross-org wrap (in-toto / DSSE) is declared, not built | a party with write access can rewrite unsigned files; cross-org use needs the wrap first |
| A-02 | A declared clause total is what the producer says; the core does not derive it from prose | the spec inventory (B19) when present | without an inventory, a total can under-count silently |
| A-03 | No trust arithmetic and no aggregate across manifests | none — out of scope by design | a consumer must not read several manifests as one verdict |
| A-04 | Evidence content is true as recorded; external tools (provers, test runners, fuzzers) report correctly | each tool's own test suite and qualification; observed-red controls catch vacuous passes | a tool bug that reports success wrongly passes every field check |
| A-05 | A spec inventory faithfully represents its spec document | the inventory generator's drift check (`spec_inventory.py check`) run by the producer | an inventory that omits a real requirement hides it from coverage |
| A-06 | Deferred mechanisms (claim-discharge by reference, the intent meaning, the built-artifact node's leaves, carrier additivity) are absent, not partial | none — declared out of scope for the lock | a consumer needing them must not infer them from other rules |
| A-07 | Declared `coverage` values and `tool_qualification` arguments are true | the tool that measured coverage; the qualification basis document | a false coverage number satisfies a `coverage_min` floor |
| A-08 | An id is never reused across a subject's publication history | producer discipline; version control history | a single-file check sees only in-file uniqueness |
| A-09 | Validation publishes, signs and ratifies nothing | the class's owning authority ratifies separately | a PASS is not a ratification |
| A-10 | One acceptance rule (`all-mandatory-satisfied`) is enough | pilot use; a decision-table rule is reserved | domains needing weighted or partial acceptance must wait for it |
| A-11 | One contract, one package, one decision per artifact | none — bundles out of scope | multi-artifact deliveries need several chains |
| A-12 | Negotiation happens only through `supersedes` chains | the work-contract layer owns messages | no offer / counter-offer record inside this protocol |
| A-13 | Tiers and floors are never summed into a score | format rule 3; core checks refuse aggregates | none inside the core |
| A-14 | Declared inputs are trusted as declared; undeclared inputs are unknown, never unchanged | producer declaration; change-impact treats undeclared as possibly invalidated | an input declared with a wrong digest is caught only when recomputed |
| A-15 | No profile vocabulary in the core | Upstream development repository: `gates/check_core_generic.py` scans language / tool / ecosystem and apparatus tokens in all 14 Class carriers, with able-to-fail controls; this scanner is not shipped in the public release | tokens outside the scan list |
| A-16 | A profile binding's floor comparator judges honestly | review of each profile binding | a comparator answering "equal" everywhere neuters tightening for its keys |
| A-17 | Declared independence is true | reviewer work (P9); the recorded runs' identities | a producer can declare `consumer-run` falsely; nothing proves who ran |
| A-18 | The consumer's authority assigns the right assurance class | the authority's own policy (internally: blast radius × irreversibility) | a wrongly low class lowers every floor legitimately |
| A-19 | A class table's floors are adequate for the domain's real risk | the table owner's review; the safety-standard schemes it was derived from (some cells from secondary sources) | adequate-looking floors may still under-protect a domain |
| A-20 | A revision identity is what version control reports | the version-control system's object model; content digests (B1) for stronger identity | revision identity inherits the VCS hash's strength |
| A-21 | Declared timestamps (`issued_at`, `validity.stale_after`, condition `due`) are true, and the evaluating gate's clock is honest | host clock discipline; operational discipline | a skewed or lied-about clock can make a stale decision effect-eligible, or the reverse |
| A-22 | Amendments are applied by one sequential applier; the current-pointer race is excluded from `/0` by §3.6's own prose, not by a guard | operational discipline; the booked exclusive-creation-lock build item | two appliers racing the same base concurrently can both succeed against a stale pointer |
