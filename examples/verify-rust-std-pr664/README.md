# examples/verify-rust-std-pr664

This directory holds a **real** manifest, not a teaching fixture. `acceptance.toml` here is the
actual acceptance/0 manifest written for a real submission: `model-checking/verify-rust-std` pull
request [#664](https://github.com/model-checking/verify-rust-std/pull/664), "Challenge 21 (focused
PROBE): `TwoWaySearcher::next_back` backward-search-loop coverage".

## Why `illustrative = true` on a real manifest

The manifest is still marked `illustrative = true` (core.md §0.6). That flag does not mean
"fictional" — it means "hand-authored, not generator-output" (see the manifest's own header
comment). Nothing here is invented: the claim traces to a real Kani proof run against the shipped
source, unmodified. The flag is honest about *how the manifest was produced*, not about whether the
subject is real.

## What it covers

- 1 submitted claim (`CH21-001`), a bounded **PROBE** (`band = "A3"`, `grade = "probe"`) of
  `TwoWaySearcher::next_back` — the real function, driven through the real `ReverseSearcher` API,
  with no `#[cfg(kani)]` body swap. One harness,
  `core::str::pattern::verify::check_twoway_search_back_arm_covers`, checks that `next_back`:
  - stays memory-safe at every step,
  - returns only sound `Match` slices,
  - matches an independently-computed expected match (no silent miss), and
  - reaches all five backward-search-loop arms.
- Fixed fixture, stated plainly rather than left to be discovered: one short-period needle
  (`"abab"`), one haystack length (5 bytes), a 3-symbol representative alphabet `{a,b,z}`,
  `#[kani::unwind(6)]`. Verified with `kani@d4df833c8f8f` (0.67.0), CBMC 6.8.0:
  `VERIFICATION SUCCESSFUL` — all 5 loop-arm cover properties satisfied.
- A negative control ships alongside the claim: the same harness re-run against a soundness
  mutant (an off-by-one `match_pos` in the `Match` arm) goes RED, caught directly by the
  adjacency/slice-equality oracle — the observed-red control the A3 band requires.
- Three structured, disclosed `assumes` blocks on the claim state exactly what it does **not**
  cover: only this one fixture size/alphabet (`AS-1`); the completeness oracle's own negative
  control is not discriminating at this exact fixture size, though it is VM-confirmed at a larger
  one on a sibling, unsubmitted harness (`AS-2`); only the `RejectAndMatch` searcher path is
  exercised, not `MatchOnly` (`AS-3`).
- 1 explicit gap claim (`CH21-002`), `band = "A0"`, `status = "gap"`: the `MatchOnly` backward
  path and a fully generic (symbolic needle/length) `next_back` contract are **not** proved in
  this submission — a disclosed tool/proof-effort limitation, not a claim of impossibility.
- Every claim is `weight = "unweighted"` — a reduced, honest manifest rather than an inflated one
  (see the manifest's own header comment).

## Why the `record` pointers do not resolve here

Each claim's `record` field points into the private control repo that produced this manifest
(a receipt file, not this repo). Those pointers will not resolve from this checkout or from any
public reader's clone — expected, and the validator flags it as a WARN, not a FAIL (the same shape
as `examples/rs-verified-der/` and `examples/verify-rust-std-pr618/`). This is the
honest-disclosure shape: the manifest states plainly where its evidence lives, even though a
reader here cannot fetch it directly.

## Validate it yourself

```sh
# from the repo root
python3 tools/check_acceptance.py --strict examples/verify-rust-std-pr664/acceptance.toml
```

Expect `PASS` with WARN lines for the two unresolvable `record` pointers (private-repo paths) — no
FAIL is expected.
