# examples/verify-rust-std-ch25-vecdeque

This directory holds an **illustrative** manifest (`illustrative = true`, core.md §0.6) for a
submission being prepared: it records evidence for the Challenge 25 `VecDeque` ring-buffer
wraparound PROBE set being prepared from branch `ch25-vecdeque-probe` @
`9cd331421bbd0451b554de4f7572a7340d3962e9` in the same fork as the sibling `verify-rust-std-*`
examples in this directory. It has not been submitted yet; the manifest will be restamped if that
head moves before submission.

## Why `illustrative = true`

As `examples/verify-rust-std-pr664/README.md` explains, `illustrative = true` does not mean
"fictional" — it means "hand-authored, not generator-output" (core.md §0.6; see also each
manifest's own header comment for its specific rationale). This manifest's header gives the same
two-part reason as the sibling `ch7-atomic` example:

1. It is hand-built from receipts in the private control repo's campaign tree, no automated capture
   pipeline behind it.
2. Challenge 25's own success criteria require **unbounded** verification (arbitrary length) and
   **genericity over T** (no monomorphization) across 43 listed items (13 unsafe-contract functions
   + 30 safe abstractions). This manifest's 5 claims target 5 of those 43, all bounded at one
   concrete element type (`u32`) — a bounded PROBE does not count as criterion coverage. The
   manifest's own header says it plainly: *never read this manifest as satisfying Challenge 25.*

## What it covers

- 5 claims (`CH25-1`..`CH25-5`), all `status = "evidenced"`, `grade = "probe"`,
  `weight = "unweighted"`, targeting `as_slices`, `as_mut_slices`, `pop_front`, `swap`, and
  `handle_capacity_increase` (reached via `grow`) — all against the same hand-built, genuinely
  wrapped `VecDeque<u32>` fixture (capacity 4, built through real `push_back`/`pop_front` calls, not
  raw-field construction).
- `CH25-1`..`CH25-4` stand at `band = "A0"`: no mutation control of the production implementation
  exists for any of the four. A fixture-differentiation check did run (an out-of-tree, unshipped
  harness that removes the wraparound-inducing construction step and confirms the same assertion
  goes RED on an unwrapped fixture) — it corroborates that the fixture genuinely wraps, but it
  mutates no target function's own code, so per assurance-bands.md rule 2/6 it does not satisfy the
  A2/A3 control-kind gate. It is recorded as corroborating evidence, explicitly not as a
  band-lifting control.
- `CH25-5` (`grow` / `handle_capacity_increase`) stands at `band = "A3"`: it carries a dedicated
  mutation control against the real implementation (an off-by-one in the copy-destination
  arithmetic, `new_head = new_capacity - head_len - 1`), independently VM-confirmed RED. A second,
  earlier mutation on the same harness (weakening a branch-condition operator from `>` to `>=`) is
  also disclosed and explicitly **not** counted: at this fixture's symmetric `head_len == tail_len`
  boundary the two branches produce an identical correct result, so the mutation is
  non-discriminating there — a disclosed uninformative attempt, not a control failure to explain
  away.
- `[coverage]` uses `denominator = "slice"` against `clauses_total = 5` (matching `claims_total`)
  with a `slice_note` naming the other 38 of Challenge 25's 43 listed items this manifest does not
  touch — 12 remaining unsafe-contract functions and 26 remaining safe abstractions, named
  explicitly in the manifest.
- Every claim's own `statement` restates the same scope discipline: bounded at concrete capacity 4
  (growing to 8 for `CH25-5`), concrete element type `u32`, exactly one wraparound.

## The EXPERIMENTAL `[coverage].denominator = 'slice'` claim class

Per `spec/CLAIM-CLASSES-AWAITING-WEIGHT.md` C1, `denominator = "slice"` is admissible today as an
unweighted disclosure but is not yet weight-bearing format machinery: there is no criterion in the
format that distinguishes a principled slice boundary from a self-serving one, so the validator
checks it for shape only and flags it as EXPERIMENTAL. The actual validator line for this manifest
(see "Validate it yourself" below):

```
WARN examples/verify-rust-std-ch25-vecdeque/acceptance.toml: [coverage].denominator = 'slice' is EXPERIMENTAL (CLAIM-CLASSES-AWAITING-WEIGHT.md C1) — denominator/slice semantics are not yet frozen; validated for shape only
```

## Which sha this manifest describes

`[subject].commit` is `9cd331421bbd0451b554de4f7572a7340d3962e9` on branch
`ch25-vecdeque-probe` — the final, submitted state after an earlier revision on this branch was
reworked: an enabled, intentionally-failing control harness that had briefly shipped inside the
submittable module was removed (a real code change), module-label and positive-control claims were
reworded to match what the module actually proves, and residual provenance strings were scrubbed.
Because a harness was removed rather than merely reworded in comments, the surviving five
wraparound harnesses (plus a pre-existing `check_vecdeque_swap`) were re-confirmed GREEN at this
exact sha. The dedicated `CH25-5` mutation control ran one sha earlier
(`7b227b480ec43c2bb103c72549a127bd86854a3a`); the only difference between that sha and this one is
the later harness removal plus prose edits, neither of which touches
`check_wraparound_grow_preserves_order`'s own code, so the control's result carries forward — and
the confirm run's independent re-verification of that same (unmutated) harness at this sha
corroborates it was not disturbed in the process.

## A note on the pinned `spec_sha` / `validator_sha`

This copy repins `spec_sha` / `validator_sha` from the private working repo's coordinate
(`8849330e943446907a12f67c7d2c0cceb226ad05`) to the **public** commit
`2788bbfdb7b01c1fdd0013ce5bd4714166301ddf`, following the same ruling R-1 rationale as
`examples/verify-rust-std-pr664/`: a pin in a public artifact has to be resolvable by a public
reader. The repin was verified byte-identical first — `spec/core.md`, `spec/assurance-bands.md` and
`tools/check_acceptance.py` hash the same at both commits — so nothing about the spec or validator
version being cited changed, only the coordinate a reader can resolve it at.

## Why the `record` pointers do not resolve here

Each claim's `record` field points into the private control repo that produced this manifest (a
receipt file, not this repo). Those pointers will not resolve from this checkout or from any public
reader's clone — expected, and the validator flags it as a WARN, not a FAIL, the same shape as
`examples/verify-rust-std-pr664/`, `examples/verify-rust-std-pr618/`,
`examples/verify-rust-std-ch7-atomic/` and `examples/rs-verified-der/`.

## Validate it yourself

```sh
# from the repo root
python3 tools/check_acceptance.py --strict examples/verify-rust-std-ch25-vecdeque/acceptance.toml
```

Actual output from this checkout:

```
PASS ILLUSTRATIVE examples/verify-rust-std-ch25-vecdeque/acceptance.toml (9 warnings) [weighted: 0, unweighted: 5]
```

The 9 warnings are the 8 unresolvable `record` pointers (private-repo paths) plus the one
`[coverage].denominator = 'slice'` EXPERIMENTAL notice quoted above. No FAIL is expected.
