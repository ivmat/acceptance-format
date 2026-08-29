# examples/verify-rust-std-pr618

This directory holds a **real** manifest, not a teaching fixture. `acceptance.toml` here is the
actual acceptance/0 manifest written for a real submission: `model-checking/verify-rust-std` pull
request [#618](https://github.com/model-checking/verify-rust-std/pull/618), "Challenge 2 (partial):
safety contracts + verification for 15 of 20 raw-pointer `core::intrinsics`".

## Why `illustrative = true` on a real manifest

The manifest is still marked `illustrative = true` (core.md §0.6). That flag does not mean
"fictional" — it means "hand-authored, not generator-output" (see the manifest's own header
comment). Nothing here is invented: every claim traces to a real Kani proof run against the PR's
actual head commit. The flag is honest about *how the manifest was produced*, not about whether the
subject is real.

## What it covers

- 15 claims, one per verified intrinsic (`typed_swap`, `vtable_size`, `vtable_align`, `copy`,
  `copy_nonoverlapping`, `write_bytes`, `size_of_val`, `arith_offset`, `volatile_load`,
  `volatile_store`, `ptr_offset_from`, `ptr_offset_from_unsigned`, `compare_bytes`,
  `read_via_copy`, `write_via_move`).
- 1 explicit gap claim (`CH2-016`) naming the 5 intrinsics the pinned Kani toolchain cannot
  currently verify — a disclosed tool limitation, not a claim of impossibility.
- Every claim is `weight = "unweighted"` and `band = "A0"`: each is a `kani-harness` proof with
  the right evidence species for a stronger band, but none has a mutation/ablation control filed
  as a citable machine record, so the manifest's own header comment explains why A0 is the honest
  floor per `spec/assurance-bands.md` rule 2/5 — not a shortfall in the proof work itself.
- Verified on `kani@d4df833c8f8f` (0.67.0), CBMC 6.8.0, whole-module run:
  `Complete - 370 successfully verified harnesses, 0 failures, 370 total.`

## Why the `record` pointers do not resolve here

Each claim's `record` field points into the private control repo that produced this manifest
(a receipt file, not this repo). Those pointers will not resolve from this checkout or from any
public reader's clone — expected, and the validator flags it as a WARN, not a FAIL (the same shape
as `examples/rs-verified-der/`). This is the honest-disclosure shape: the manifest states plainly
where its evidence lives, even though a reader here cannot fetch it directly.

## Validate it yourself

```sh
# from the repo root
python3 tools/check_acceptance.py --strict examples/verify-rust-std-pr618/acceptance.toml
```

Expect `PASS` with WARN lines for the unresolvable `record` pointers (private-repo paths) — no
FAIL is expected.
