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

## Revision 2 (2026-09-07)

Revision 1 (2026-08-29) described PR head `e7b1bc12`. Revision 2 describes the branch as pushed to the
PR on 2026-09-07, `cf5fd23c45cb38273a314d6229a9b214a16ebf3c`: the same head plus four commits that
answer the maintainer review of 2026-08-16. The 15 per-intrinsic evidence records were captured at
`e7b1bc12` and say so (`captured_at_commit`); every harness they name was re-executed and passed in
the whole-module run at `c35c201b` (`intrinsics::verify`, CI mode, 374/374) and in the repository's
own sharded suite at `cf5fd23c` (4 Linux shards, 1436 harnesses, 0 failures). `cf5fd23c` differs
from `c35c201b` by comments only.

## What it covers

- 15 claims, one per verified intrinsic (`typed_swap`, `vtable_size`, `vtable_align`, `copy`,
  `copy_nonoverlapping`, `write_bytes`, `size_of_val`, `arith_offset`, `volatile_load`,
  `volatile_store`, `ptr_offset_from`, `ptr_offset_from_unsigned`, `compare_bytes`,
  `read_via_copy`, `write_via_move`).
- 1 explicit gap claim (`CH2-016`) naming the 5 intrinsics the pinned Kani toolchain cannot
  currently verify — a disclosed tool limitation (fixed upstream in kani#4672/#4673, not yet at the
  repository's pin), not a claim of impossibility.
- 1 additive claim (`CH2-029`, band **A3**) about the `copy_wrapper` byte-value oracle: one fixed
  overlapping non-uniform `u32` fixture, proved in both dependency-contract modes, with an
  implementation mutation (the wrapper's forwarding call replaced by `write_bytes`) observed red on
  the postcondition itself. It is scoped to the wrapper predicate — `core::intrinsics::copy` itself
  (`CH2-004`) stays at A0 — so the manifest's A3 count is stated partitioned: **0 production-intrinsic,
  1 wrapper/model-predicate**.
- Every other claim is `weight = "unweighted"` and `band = "A0"`: each is a `kani-harness` proof
  with the right evidence species for a stronger band, but no mutation/ablation control is filed
  against it as a citable machine record. The header comment explains why A0 is the honest floor per
  `spec/assurance-bands.md` rule 2/5 — not a shortfall in the proof work itself. Further controls
  exist in the private control repo and lift nothing here until transcribed.
- Verified on `kani@d4df833c8f8f` (0.67.0), CBMC 6.8.0.

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
