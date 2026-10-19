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

## Acceptance family — load-bearing assumptions of the Class rung (0.4.0)

Each row is anchored in the core spec text by its tag (`[A-nn]`) in `format_acceptance/spec/core.md` §5 or
`protocol_acceptance/spec/protocol.md` §11. `gates/check_assumptions.py` checks that every bullet in those two
sections carries a tag, that every tag has a row here, and that every row is cited there.
The public suite ships and runs this check and `gates/check_class_lock.py`, which checks
the latest public lock against the shipped Class text. The public lock retains each version's
file hashes; the upstream development repository gates their equality with its source lock.
Generic-core and process-vocabulary scans run in the upstream development repository; the public
suite does not ship `check_core_generic.py`. Locking and passing checks do not ratify the class.

| id | assumption (what the core trusts and does not check) | external gate we rely on | residual |
|---|---|---|---|
| A-01 | No signing, identity, transport or transparency of its own (planned; P10) | git object integrity within one party boundary; cross-organisation signing and transparency are planned | a party with write access can rewrite unsigned files; cross-org use needs the planned path first |
| A-02 | A declared clause total is what the producer says; the core does not derive it from prose | the spec inventory (B19) when present | without an inventory, a total can under-count silently |
| A-03 | No trust arithmetic and no aggregate across manifests | none — out of scope by design | a consumer must not read several manifests as one verdict |
| A-04 | Evidence content is true as recorded; external tools (provers, test runners, fuzzers) report correctly | each tool's own test suite and qualification; observed-red controls catch vacuous passes | a tool bug that reports success wrongly passes every field check |
| A-05 | A spec inventory faithfully represents its spec document | the inventory generator's drift check (`spec_inventory.py check`) run by the producer | an inventory that omits a real requirement hides it from coverage |
| A-06 | Deferred mechanisms (claim-discharge by reference, the intent meaning, the built-artifact node's leaves, carrier additivity) are absent, not partial | none — declared out of scope for the lock | a consumer needing them must not infer them from other rules |
| A-07 | Declared `coverage` values and `tool_qualification` arguments are true | the tool that measured coverage; the qualification basis document | a false coverage number satisfies a `coverage_min` floor |
| A-08 | An id is never reused across a subject's publication history | producer discipline; version control history | a single-file check sees only in-file uniqueness |
| A-09 | Validation publishes, signs and ratifies nothing | the class's owning authority ratifies separately | a PASS is not a ratification |
| A-10 | One acceptance rule (`all-mandatory-satisfied`) is enough | pilot use; a decision-table rule is reserved | domains needing weighted or partial acceptance must wait for it |
| A-11 | Chains mean accepted by named issuers under their own specifications; no assurance levels combine | pinned decisions and qualified stack rendering | without min_class/profiles a listed issuer’s weak specification still counts |
| A-12 | No negotiation messages (offer, counter-offer) | the `supersedes` chain is the only record of how a specification changed; messaging between parties is outside this protocol | no offer / counter-offer record inside this protocol |
| A-13 | Tiers and floors are never summed into a score | format rule 3; core checks refuse aggregates | none inside the core |
| A-14 | Declared inputs are trusted as declared; undeclared inputs are unknown, never unchanged | producer declaration; change-impact treats undeclared as possibly invalidated | an input declared with a wrong digest is caught only when recomputed |
| A-15 | No profile vocabulary in the core | Upstream development repository: `gates/check_core_generic.py` scans language / tool / ecosystem and process-vocabulary tokens in all 14 Class carriers, with able-to-fail controls; this scanner is not shipped in the public release | tokens outside the scan list |
| A-16 | A profile binding's floor comparator judges honestly | review of each profile binding | a comparator answering "equal" everywhere neuters tightening for its keys |
| A-17 | Declared independence is true, and the independence order `none < author-not-producer < consumer-run < third-party` is read as stated | reviewer work (P9); the recorded runs' identities; for the order, none: it is a known 0.4.0 limit, to be fixed in a later version | a producer can declare `consumer-run` falsely; nothing proves who ran. The order is not one of nested demands: `consumer-run` carries no author condition. So the tightening check, an assurance-class target of `author-not-producer`, and the class table between `baseline/2` and `baseline/3` all accept a step that drops the author-not-producer coverage condition |
| A-18 | The consumer's authority assigns the right assurance class | the authority's own policy (internally: blast radius × irreversibility) | a wrongly low class lowers every floor legitimately |
| A-19 | A class table's floors are adequate for the domain's real risk | the table owner's review; the safety-standard schemes it was derived from (some cells from secondary sources) | adequate-looking floors may still under-protect a domain |
| A-20 | A revision identity is what version control reports | the version-control system's object model; content digests (B1) for stronger identity | revision identity inherits the VCS hash's strength |
| A-21 | Declared timestamps (`issued_at`, `validity.stale_after`, condition `due`) are true, and the evaluating gate's clock is honest | host clock discipline; operational discipline | a skewed or lied-about clock can make a stale decision effect-eligible, or the reverse |
| A-22 | Built 2026-10-07: exclusive-creation lock covers pointer initialization/read through successor write and atomic advance; as specified in §3.6 and §11 | `O_EXCL` on the resolved pointer’s sibling `.lock`; [process controls](gates/check_amendment_lock.py) | cooperating appliers must share one stable resolved pointer on a filesystem honoring exclusive creation/atomic rename; hard-link aliases, external writers and concurrent manual lock removal are outside the guard. SIGKILL/power loss can leave a stale lock (refused, manual recovery only); successor write plus pointer advance is not a crash-durable transaction and can leave an unreferenced successor |
| A-27 | Presented bytes equal the named commit only when a checkout’s checked files equal it; undigested files are uncovered | the checkout check compares file bytes with the commit's blobs; it does not trust the checkout's index, attributes or configuration; B20 and reader digest recomputation; supported Cargo member/lock and edge checks | Cargo resolution and nearest-ancestor workspace discovery are not rerun; a checkout lacking the named commit (every clone of this repository) is treated as a non-checkout; only the recorded digests are checked, with a mandatory NOTE; archives also rely on recorded digests |
| A-28 | Store writers and consumer mappings are authority | frozen directory view, listed issuers, hash pins and informational listing digest | no authorship proof; writers may backdate or remove/restore undetected; omitted files can hide superseders or removals |
| A-29 | Revocation outside the presented documents is not observed | historical pins and effect eligibility of the current presented view | no external revocation or transparency index |
| A-30 | Source acceptance does not prove semantic preservation across compilation or copying | binding is rendered as declared | build-time copies and delivered behavior require their own evidence |
| A-31 | Named boundaries are the trusted base | boundary identity matching and explicit rendering | boundary quality remains assumed; effect checks do not discover newer versions of a child’s specification |
