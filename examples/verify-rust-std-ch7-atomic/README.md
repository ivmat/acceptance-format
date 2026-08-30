# examples/verify-rust-std-ch7-atomic

This directory holds an **illustrative** manifest (`illustrative = true`, core.md §0.6) for a
submission being prepared: it records evidence for the Challenge 7 atomic `from_ptr` PROBE set
being prepared from branch `ch7-atomic-probe` @ `c8494c66431256f6d903a47078d69939a929c499` in the
same fork as the sibling `verify-rust-std-*` examples in this directory. It has not been submitted
yet; the manifest will be restamped if that head moves before submission.

## Why `illustrative = true`

As `examples/verify-rust-std-pr664/README.md` explains, `illustrative = true` does not mean
"fictional" — it means "hand-authored, not generator-output" (core.md §0.6; see also each
manifest's own header comment for its specific rationale). This manifest's header gives two
reasons, both worth carrying forward honestly:

1. It is hand-built from receipts in the private control repo's campaign tree, not the output of a
   manifest generator.
2. Challenge 7's own Part 1 success criteria ask for a written **safety contract** on each of twelve
   listed `from_ptr` methods, then verification that each is safe for all pointee values under that
   contract. This manifest's six claims write no contract on any of the twelve — they are
   assume-based **PROBEs** over six concrete type instantiations. A PROBE does not count as
   criterion coverage, and Challenge 7's Part 2 (Safe Abstractions) and Part 3 (Atomic Intrinsics)
   are entirely absent from this manifest. The manifest's own header says it plainly: *never read
   this manifest as satisfying Challenge 7.*

## What it covers

- 6 claims (`CH7-1`..`CH7-6`) over 5 distinct methods — `AtomicBool::from_ptr`,
  `AtomicI8::from_ptr`, `AtomicI32::from_ptr`, `AtomicU64::from_ptr`, and `AtomicPtr::from_ptr`
  instantiated at two `T`s (`u8` and the non-power-of-two `[u8; 3]`), which the manifest itself
  flags as layout-identical to each other, not an additional layout case.
- Every claim is `grade = "probe"`, `status = "evidenced"`, `weight = "unweighted"`.
- `CH7-1` / `CH7-2` (`AtomicBool`, `AtomicI8`) stand at `band = "A0"`. Both types have
  `align_of::<T>() == 1` unconditionally, so an alignment-ablation control would exclude nothing —
  no control is possible for them, not merely unrun, and the one-sentence gate
  (assurance-bands.md) puts an oracle-bearing claim with no observed-red control at A0.
- `CH7-3`..`CH7-6` (`AtomicI32`, `AtomicU64`, `AtomicPtr<u8>`, `AtomicPtr<[u8; 3]>`) each carry a
  dedicated alignment requires-ablation control — the alignment `kani::assume` is dropped and the
  harness re-run, independently VM-confirmed RED — which matches assurance-bands.md's A2
  species-plus-control requirement (memory safety on an unsafe surface, control kind in
  `{mutation, ablation}`), so they stand at `band = "A2"`.
- `[coverage]` uses `denominator = "slice"` against `clauses_total = 12` (the twelve `from_ptr`
  methods Challenge 7 Part 1 lists) with `claims_total = 6`: six bounded PROBE claims spanning 5 of
  those 12 methods. The `slice_note` names what is not covered — the other seven listed methods,
  the fact no safety contract is written on any of the twelve, and that Challenge 7 Parts 2 and 3
  are entirely outside this manifest.
- Each claim also carries disclosed `assumes` blocks stating what it does not establish: lifetime
  validity of the returned reference is assumed, not verified (Kani does not track lifetimes);
  cross-thread data-race freedom is out of scope (Kani's proof model is single-execution); and
  uninitialized-memory checking is absent from the enabled check set, so these claims read as "no
  enabled Kani default-check violation," not "UB-free" in the full sense. The two `AtomicPtr`
  claims additionally disclose that their pointee value is `null_mut()`, not a symbolic `*mut T` —
  Challenge 7 asks for verification over *any* pointee address, and these harnesses do not range
  over that space.

## Which sha this manifest describes

`[subject].commit` is `c8494c66431256f6d903a47078d69939a929c499` on branch `ch7-atomic-probe` — a
formatting-only commit ahead of the sha the VM evidence itself was gathered at
(`2c43bd330d5...`), for the same reason `examples/verify-rust-std-pr664/` documents: the fork's
`upstream_test` CI job runs `./x fmt --check` inside a `rust-lang/rust` checkout, whose style config
`verify-rust-std` does not carry its own copy of. No harness, assertion, `kani::cover` expression,
target call or fixture bound differs between the two shas.

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
`examples/verify-rust-std-pr664/`, `examples/verify-rust-std-pr618/` and
`examples/rs-verified-der/`.

## Validate it yourself

```sh
# from the repo root
python3 tools/check_acceptance.py --strict examples/verify-rust-std-ch7-atomic/acceptance.toml
```

Actual output from this checkout:

```
PASS ILLUSTRATIVE examples/verify-rust-std-ch7-atomic/acceptance.toml (11 warnings) [weighted: 0, unweighted: 6]
```

The 11 warnings are the 10 unresolvable `record` pointers (private-repo paths) plus one
`[coverage].denominator = 'slice'` EXPERIMENTAL notice (`CLAIM-CLASSES-AWAITING-WEIGHT.md` C1: slice
denominators are not yet frozen and are validated for shape only). No FAIL is expected.
