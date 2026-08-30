# examples/verify-rust-std-ch4-btree-v2

This directory holds a **real** manifest, not a teaching fixture. `acceptance.toml` here is the
actual acceptance/0 manifest written for a real submission in progress: the Challenge 4
strengthened-v2 submission from branch `challenge-4-btree-v2` on the fork behind the earlier
Challenge 21 and Challenge 2 submissions in this directory's sibling examples. It has not been
opened as a pull request yet; the PR link lands in a follow-up sync once it is.

`illustrative` is **not** set on this manifest — it defaults to `false` (core.md §0.6). Unlike
`examples/verify-rust-std-pr664/` and `examples/verify-rust-std-pr618/`, both of which are marked
`illustrative = true`, this manifest claims to be the real thing end to end: hand-authored, yes,
but recording real one-run-one-sha verification evidence at a stated commit, not a teaching
example. The manifest's own header comment says so directly, and states the consequence: *"NOT
FINAL UNTIL --strict PASSES... check_acceptance.py --strict FAILS on dangling record pointers, and
that failure is the mechanical guard against this manifest asserting a pass before its run
happened."* See "Validate it yourself" below for what that means for a reader of this checkout.

## What it covers

- 13 claims total: 12 evidence-bearing (`status = "evidenced"`) and 1 explicit gap claim
  (`status = "gap"`).
- Four of the twelve evidence-bearing claims — `CH4-V2`, `CH4-V7`, `CH4-V8`, `CH4-V12` — stand at
  `band = "A3"`. Each carries a `[claim.evidence.control]` block: a mutation applied to the
  implementation only on the verification machine (never committed), independently re-run against
  the same harness, and observed RED as the A3 band requires (assurance-bands.md's one-sentence
  gate: an oracle-bearing claim cannot exceed A0 without an observed-red control naming it).
- The remaining eight evidence-bearing claims, plus the one gap claim, stand at `band = "A0"`.
- The gap claim, `CH4-V13`, targets `Handle::insert_recursing` — memory safety of the recursive
  insert path at unbounded tree height. Nothing is claimed here: the function's loop trip count is
  the tree's *height*, the one axis this node type does not bound (occupancy is bounded by
  `CAPACITY`, a compile-time constant; height is not). A bounded-height harness was run during
  development but does not discharge the unboundedness the challenge states for this function, so
  the manifest records the gap rather than a bound that would read stronger than it is.
- Verification evidence across the whole-set run at the stamped commit: 28/28 harnesses
  `VERIFICATION SUCCESSFUL`, 83/83 `kani::cover` properties satisfied, at `kani@d4df833c8f8f`
  (0.67.0) / CBMC 6.8.0 — the tool string every claim's evidence entry in `acceptance.toml` also
  states individually.
- Honest framing, stated the way the estate requires: this is a bounded **PROBE** set, not a
  discharge of Challenge 4. It harnesses seven of the eight functions the challenge doc's second
  success-criteria list names directly (`new_internal`, `do_merge`, `merge_tracking_child_edge`,
  `steal_left`, `steal_right`, `bulk_steal_left`, `bulk_steal_right`) — an improvement on an earlier
  revision of this manifest, which targeted none of the eight by name — but every claim is
  monomorphic at `K = V = i32` and bounded to a fixed node/tree shape (occupancy sampled at
  `{0, 1, CAPACITY}` or symbolic over the complete `0..=CAPACITY` domain, tree height fixed at 1 or
  2). None of that discharges the challenge's own unboundedness requirement, and the manifest does
  not claim it does. The eighth named function, `insert_recursing`, is the one this manifest cannot
  reach for exactly that reason, and it is recorded as the explicit gap claim above rather than left
  silent.

## Which sha this manifest describes

`[subject].commit` is `9a083f4bc124925f2fc0c447d688110dd3b89ac8` — the head of
`challenge-4-btree-v2` on the fork, based on a reviewed, formatting-clean base. That is the sha the
whole-set VM run above was gathered at; the manifest's own header notes this branch has not yet had
a PR number assigned.

## A note on the pinned `spec_sha` / `validator_sha`

This manifest pins the **public** spec/validator commit `2788bbfdb7b01c1fdd0013ce5bd4714166301ddf`
directly — no repin was needed to assemble this example, unlike the sibling `ch7-atomic` and
`ch25-vecdeque` examples in this directory. A pin in a public artifact has to be resolvable by a
public reader (ruling R-1, already cited in `examples/verify-rust-std-pr664/README.md`). Before
copying this manifest in, its private working-repo pin was checked for byte-identity against this
public commit's `spec/core.md`, `spec/assurance-bands.md` and `tools/check_acceptance.py`: all
three hash identically. The two name the same spec and the same validator; only the coordinate
system a reader can resolve differs.

## Why the `record` pointers do not resolve here — and why that makes `--strict` FAIL, not WARN

Each claim's `record` field points into the private control repo that produced this manifest, the
same as `examples/verify-rust-std-pr664/`, `examples/verify-rust-std-pr618/` and
`examples/rs-verified-der/`. Those pointers will not resolve from this checkout or from any public
reader's clone.

Unlike those three sibling examples, though, this manifest is **not** `illustrative`. The validator
treats that as a real difference (core.md §0.6, CS-22): an `illustrative` manifest gets a WARN for
an unresolved `record` pointer even under `--strict`, because it is explicitly a teaching example
that the format does not hold to full evidentiary account. A non-`illustrative` manifest gets no
such waiver — under `--strict`, a dangling `record` pointer is an ERROR, and the run FAILs. That is
by design, and it is exactly what this manifest's own header comment predicts and asks for: a
mechanical guard against the manifest asserting a pass before its evidence run actually happened.
From this checkout, with the private control repo's `logs/` tree absent, that guard fires. It
would resolve, and `--strict` would PASS, only from the private control repo this manifest was
authored in, where `record_root` and every `record` path actually exist on disk.

## Validate it yourself

```sh
# from the repo root
python3 tools/check_acceptance.py --strict examples/verify-rust-std-ch4-btree-v2/acceptance.toml
```

From this checkout, expect:

```
FAIL examples/verify-rust-std-ch4-btree-v2/acceptance.toml (23 errors) [weighted: 0, unweighted: 13]
```

— 23 dangling-`record`-pointer errors, one per evidence entry, all naming paths that live in the
private control repo, not here. That FAIL is expected and correct, per the note above; it is not a
defect in this example. Dropping `--strict` shows the same 23 findings downgraded to warnings and a
`PASS`:

```sh
python3 tools/check_acceptance.py examples/verify-rust-std-ch4-btree-v2/acceptance.toml
# PASS examples/verify-rust-std-ch4-btree-v2/acceptance.toml (23 warnings) [weighted: 0, unweighted: 13]
```
