# Worked example: a real Rust delivery under the acceptance protocol

This directory is a complete, real run of `acceptance-protocol/0`
(`protocol_acceptance/spec/protocol.md`) over a small, real deliverable: `iban-check`, a hand-rolled IBAN
syntax + ISO 7064 mod-97-10 checksum validator, zero dependencies. Nothing here is illustrative
prose dressed as a manifest — every transcript in `evidence/` is the real output of a real command
run against the real crate at `iban-check/`, including five genuinely-applied-and-reverted mutation
controls, one per requirement that needed one (R1/R2/R3/R4/R6).

## Who wrote what

| document | author | role |
|---|---|---|
| `acceptance-contract.toml` | Acme Payments Ltd (the consumer) | states what it needs, before seeing any code |
| `iban-check/` + `acceptance.toml` (via `gen_package.py`) | ivmat (the producer) | delivers the crate and the package certifying it |
| `acceptance-decision.toml` (via `make_decision.py`) | Acme Payments Ltd (the consumer, `platform-lead`) | re-executes and judges |

Three files, three authors, each bound to the previous by content hash (M11, `protocol.md` §7) —
the contract's hash is embedded in the package's `[contract]` table, and the package's hash is
embedded in the decision's `[binds]` table. Nobody hand-typed a hash: `gen_package.py` and
`make_decision.py` both compute them via `protocol_acceptance/tools/m11.py`.

## The core floor vs. the profile floor — where "Rust" enters

Every item requirement in `acceptance-contract.toml` carries two floors, and they answer two
different questions. `[requirement.evidence]` — `min_tier`, `weighted_required`,
`control_required`, `recipe_required`, `freshness`, `independence` — is the CORE floor
(`protocol.md` §6.1–§6.2): it is artifact-agnostic, and a consumer of a Lean proof, a hardware
design, or a spreadsheet macro would write the same five fields with the same meanings. Nothing in
that table names Rust, Kani, or a test.
`[requirement.evidence.profile."acceptance/verification/code/rust"]` — `min_grade`, `min_band`,
`families` — is where the profile-specific vocabulary enters: the floor MECHANISM is generic
(`../../../format_acceptance/profiles/verification/PROFILE.md` §3, R5-lifted 2026-09-24 off the
Rust leaf, which used to be the sole document, `spec/profiles/rust-code.md`), and the Rust-only
evidence tokens this crate's evidence carries (`kani-harness`, `unit-test`, …) are defined by
`../../../format_acceptance/profiles/verification/code/rust.md` §2 — neither means anything to the
core, which reads them only through the profile's own `floor_check` function (P11,
profile-blindness). Swap the profile id and floor sub-table for a different artifact kind, and
every other line of the contract is unchanged.

**The profile id carries the binding path, not just the meaning (0.3 migration, P2.5).**
`[format].profile` in `acceptance.toml` (and `profile`/`profiles_required`/the floor-table keys in
`acceptance-contract.toml`) read `acceptance/verification/code/rust`, not the bare
`acceptance/verification` this example used to write. The suffix is what makes the FORMAT's own
binding dispatch (`check_core.py`, core.md B12/B14) load the `code`/`code/rust` binding chain and
admit `[subject].kind = "rust-crate"` at all — without it, no binding loads, and `rust-crate` is an
unrecognized kind (core.md B14; this is exactly the error a pre-migration copy of this package
used to show). The PROTOCOL tool's own profile registry (`protocol_acceptance/tools/profiles.py`)
still keys its grade/band/tier vocabulary by the bare meaning id for every other example in this
repo; this leaf id is registered there as an alias onto the identical binding, so `check-contract`
/ `check-package` / `coverage` / `check-decision` all resolve it exactly as before.

## The six requirements and their floors

| id | statement | mandatory | core floor | profile floor |
|---|---|---|---|---|
| R1 | malformed IBANs rejected, right `IbanError` variant | yes | T3, weighted, control, recipe, delivered-revision | test-only / A1 / dynamic,bmc,kernel |
| R2 | ISO 7064 mod-97-10 checksum correct | yes | T3, weighted, control, recipe | test-only / A1 / dynamic,bmc,kernel |
| R3 | `validate` never panics on any input | yes | T2, weighted, recipe (no control demanded) | probe / A1 / bmc,dynamic |
| R4 | no `unsafe` code | yes | T4, weighted, control, recipe | mechanical / A1 / mechanical |
| R5 | R1–R3's verification is **unbounded** (cross-cutting over R1,R2,R3) | yes, waivable | `demands.fields.bounds = "unbounded"` | — |
| R6 | `cargo doc` builds with zero warnings | **no** (optional) | T4, weighted, recipe | mechanical / A0 / mechanical |

## What `gen_package.py` actually ran

In order, all against the real crate at `iban-check/`, all transcripts saved verbatim under
`evidence/`:

1. `cargo test --test malformed` (9 fixtures, one per `IbanError` variant reachable) — baseline PASS.
2. `cargo test --test checksum` (10 known-valid IBANs, one corrupted-checksum fixture, and a
   200-trial hand-rolled-LCG property test that flipping one digit always breaks validation) —
   baseline PASS.
3. `cargo test --test no_panic` (a hand-rolled xorshift64 fuzz loop, 20,000 random byte strings up
   to 128 bytes, plus 123 adversarial near-miss-length trials, plus 5 edge cases) — baseline PASS.
4. `cargo clippy -- -D warnings` — baseline PASS, clean.
5. `cargo doc --no-deps` — baseline PASS, **zero** warnings (four broken/private intra-doc links
   were found and fixed as part of building this example — see Friction).
6. `cargo kani --harness validate_never_panics` — baseline PASS, `VERIFICATION:- SUCCESSFUL`. See
   "The Kani bound" below for the real number and the tuning story.
7. **Five mutation controls**, each: apply a targeted textual patch with Python, run the command,
   REQUIRE the run to go red, restore the file from the pre-patch bytes, verify the restored file's
   bytes are byte-identical to the original (not just "looks the same"):
   - **R1**: neutered the charset-rejection branch in `validate` (`if false && !is_iban_byte(...)`)
     → `cargo test --test malformed` → 3 of 9 fixtures FAIL.
   - **R2**: changed the ISO 7064 modulus in `checksum::mod97_is_valid` from 97 to 96 at all three
     reduction sites → `cargo test --test checksum` → 2 of 3 tests FAIL (real IBANs stop
     validating).
   - **R3**: shrank the `rearranged` buffer inside `validate` from 34 bytes to 2 →
     `cargo test --test checksum` → all 3 tests FAIL with a real Rust panic (`index out of bounds`).
     This is the fast, dynamic witness used in place of a second ~7-minute Kani run; see Friction.
   - **R4**: inserted an empty `unsafe {}` block → `cargo clippy -- -D warnings` → hard compile
     error (`#![forbid(unsafe_code)]` makes this uncompilable, not merely a lint warning).
   - **R6**: added a broken intra-doc link (`` [`totally::bogus::path`] ``) → `cargo doc --no-deps`
     → 1 warning.

   Every one of these is a genuine, reverted edit to the real source tree — `gen_package.py`
   refuses to write `acceptance.toml` at all if any control fails to go red, or if the
   post-restoration byte-check fails.
8. A final sanity pass (`cargo test`, `cargo clippy -- -D warnings`) over the fully-restored tree,
   to catch any restoration bug before certifying anything.

## The Kani bound — what it really is, and how it was found

The brief's original harness (`bytes: [u8; 34] = kani::any(); … core::str::from_utf8(...)`) did not
finish within a 10-minute time-box, even after `validate` was rewritten from `String`/`format!` to
fixed-size stack byte buffers (which was itself necessary — the `String`-based version ran out of
memory in CBMC's SAT-solving phase at a **2-byte** bound). The remaining cost was
`core::str::from_utf8`'s own UTF-8-boundary validation loop, run by the *harness* over a fully
symbolic 34-byte array — expensive for CBMC regardless of what `validate` does downstream.

The fix actually shipped: `src/lib.rs`'s `verification` module gives the harness its own
`KANI_BOUND = 20`, **separate from** the crate's real `MAX_LEN = 34`. `validate` itself is
unmodified and still has its full 34-byte capacity (confirmed: `cargo test` covers all ten
countries, including Italy/France at 27 bytes, after `MAX_LEN` was correctly kept at 34). The
harness's symbolic bytes are also constrained to the ASCII range (`< 0x80`) before
`core::str::from_utf8` — a real, disclosed narrowing of the *harness's* input domain, justified in
`src/lib.rs`'s doc comment: `validate` never performs a single char-boundary- or encoding-sensitive
operation (it reads `input.as_bytes()` once and never touches the string again), so panic-freedom
over ASCII bytes and panic-freedom over the full `&str` domain are the *same claim* for this
specific function — the narrowing costs no real coverage, only CBMC exploration time.

Measured growth in the harness's own bound (this machine, `iban-check/` real crate, ASCII-constrained,
`unwind` scaled to match): **8 bytes → 29s, 16 bytes → 206s, 20 bytes → 415s (6:55)**, unconstrained
34 bytes → did not finish in 10 minutes. `KANI_BOUND = 20` is the shipped, checked-in bound — it
fully covers Belgium (16) and Austria (20) end-to-end (valid and invalid inputs of every length up
to 20), and every other country's *rejection* paths for inputs up to 20 bytes, but not the *acceptance*
path for the six countries whose real length exceeds 20 (Germany/UK at 22 through Italy/France at
27). This is exactly what R5's cross-cutting requirement and the resulting deviation are about.

## What coverage computes

Running `protocol_acceptance/tools/acceptance_protocol.py coverage acceptance.toml --contract
acceptance-contract.toml` on the generated package computes:

- **R1, R2, R3, R4 → `satisfied`** — each claim meets its core floor (tier, weight, control/recipe,
  freshness) and its profile floor (grade/band/family).
- **R6 → `satisfied`** (optional; reported, never decisive).
- **R5 → `deviation-declared`** — none of IB-001/IB-002/IB-003 carries `bounds = "unbounded"` (all
  three are honestly `bounded: …`), so the cross-cutting demand fails for every candidate claim;
  the package's `[[deviation]]` names R5, so coverage reads this as a *declared* gap rather than a
  silent one.
- **`acceptable = false`** (5 of 5 mandatory requirements is NOT met — R5 is mandatory and not
  `satisfied`) — which is exactly what makes the consumer's waiver on the decision meaningful rather
  than decorative: `acceptable` is a computed fact (P3), and the decision's `accepted-with-conditions`
  verdict is reached *despite* it, through an explicit, authorized waiver (P4), not by coverage
  quietly recomputing to something more flattering.

## The decision

`make_decision.py` re-executes every basis claim's `self_verify.command` for real
(`[verification].mode = "re-execute-all"`, matching the contract's demand) and records the real
observed tail in `[[verification.run]]` — including re-running the ~7-minute Kani proof a second
time, independently, because that is what "the consumer re-executes on its own machine" means and
this example does not fake it. Dispositions: R1/R2/R3/R4/R6 → `satisfied` (a passing re-run backs
each); R5 → `waived`, with `[disposition.waiver]` naming `code = "deferred"` and the authority; one
`[[condition]]` (`C1`, owner `producer`, due `2026-11-30`, discharged by a superseding package in
which `coverage(R5) = satisfied`). Verdict: **`accepted-with-conditions`** — computed by
`acceptance_protocol.py`'s own §5.1 partition over the *mandatory* disposition statuses
(`{satisfied, waived}`), not asserted.

## Transcript normalization

Before an evidence transcript is written, `gen_package.py` replaces the absolute crate root with
`<crate>`, the enclosing repository root with `<repo>`, a macOS-user Rustup-toolchain prefix with
`<rustup>/<toolchain>/`, every other macOS-user prefix with `<users>/<name>/`, and any remaining
current-home prefix with `~`. It performs the same transform on the decision generator's observed
tails. The package's typed `record:sha-512:` hashes are calculated over these normalized, delivered
bytes—not over the raw, machine-local command output—so independent checkers recompute the same
values.

## Change impact

`run_example.sh`'s final step simulates a future edit to `checksum.rs` (a new, hypothetical
commit) and runs `impact`, which classifies every evidence record relied on by a `satisfied`
disposition against the changed path. Every PRIMARY (passing) evidence record declared
`src/checksum.rs` as an input (the whole crate is one compiled unit, so every test/lint/doc/kani
run genuinely depends on it) — real measured result: IB-001, IB-002 (both records), IB-003 (both
records), IB-004 and IB-006's primary records all come back `definitely-invalidated`; the mutation
control records (which declare no inputs at all, honestly — they are not part of any `satisfied`
disposition's basis) come back `possibly-invalidated` for the same reason any undeclared-input
record does after a subject change (§8: "undeclared inputs are never treated as unchanged"). One
`re-verify` obligation is minted per invalidated claim (five: R1, R2, R3, R4, R6), plus one `stale_detected` event
for the decision — the decision itself is already `stale` by P7 the moment the subject commit
changes, before any of this classification runs. **Path convention note:** `--changed` is matched
against `[[claim.evidence.inputs]].path` by exact string; this example declares inputs relative to
`iban-check/` (every recipe's own cwd), so the demo passes `--changed src/checksum.rs`, not
`iban-check/src/checksum.rs`.

## The one-commit self-reference lag — resolved by the two-commit re-stamp (0.3, P2.5)

This crate and generator live *inside* the repository whose own tooling validates them.
`[subject].commit` in the generated package names `git rev-parse HEAD` of
this repository **at the moment `gen_package.py` runs**, and a manifest cannot name a
commit that already contains its own bytes — so a NAIVE single-commit workflow (edit the crate,
generate the package in the same breath, commit both together) always lands with
`[subject].dirty = true`, because the crate's own files are still untracked relative to the HEAD
`gen_package.py` just read.

core.md B1's own note names the fix, and this package now uses it: a **two-commit re-stamp**, not
a mechanism change. First commit `iban-check/` (source, `Cargo.lock`, `rust-toolchain.toml`) on
its own, with nothing else pending under that path — `git status --short -- iban-check` empty.
THEN run `gen_package.py` against that now-clean, already-committed HEAD: `[subject].commit` names
that commit, `[subject].dirty` reads `false` by construction, because the manifest's own commit is
chronologically *after*, and disjoint from, the commit it certifies. Only then commit the
generated `acceptance.toml` + `evidence/` + the two same-directory `Cargo.lock`/
`rust-toolchain.toml` build inputs (into `iban-check/`; B20's required build inputs are matched by
EXACT path, anchored to this manifest's own directory, not the crate's — see "Friction" below) as
a second, later commit. In this source repo `gen_package.py` creates these two as relative
symlinks into `iban-check/`; a published/exported copy of this example ships them as regular,
byte-identical files instead (an export step that copies bytes rather than preserving symlinks) —
`gen_package.py` accepts either form, verifying byte-equality before reusing an existing regular
copy, never overwriting one that differs. This package's own history
does exactly that (two adjacent commits on this branch: the clean `iban-check/` state, then the
regenerated package) — `check-decision` now passes with no dirty-package exception (`dirty` must
be false for a package a decision may accept, `format_acceptance/profiles/verification/code/rust.md`
§1, enforced as a hard error at decision time).

This is a **workflow discipline this example now follows, not a structural guarantee the tooling
enforces for you**: a future `gen_package.py` run against a working tree with uncommitted
`iban-check/` edits will show `dirty = true` again, honestly, for the same reason — the two-commit
order has to be repeated on every regeneration that touches the crate. A real cross-organisation
delivery never hits this at all, because the producer's tagged release commit is already clean
before the package that certifies it is even generated (see "How this maps to a real external
delivery" below).

## How this maps to a real external delivery

Nothing about this exchange assumes both sides share a filesystem. In a real cross-organisation
delivery: the consumer sends `acceptance-contract.toml` (§3.4's ratification path exists exactly
for the case where the producer drafts it and the consumer's word binds it). The producer runs its
own `gen_package.py`-equivalent, delivers the crate at a tagged commit plus `acceptance.toml` plus
`evidence/`. The consumer clones the delivered commit **on its own machine**, with its own
toolchain, and runs its own `make_decision.py`-equivalent — re-executing every basis claim's
`self_verify.command` itself, never trusting the producer's transcripts as evidence of their own
truth (P9). Everything this example's three documents carry — content hashes, subject commit,
tool/semantics strings per record — is exactly what a re-run on a different machine needs to either
reproduce the producer's result or catch a divergence.

## Running it

```
bash run_example.sh
```

Regenerates the package (`gen_package.py`, ~10 minutes — dominated by the Kani proof), validates it
(`check_acceptance.py --strict --strict-weight`), issues the decision (`make_decision.py`, another
~7 minutes for the Kani re-run), then — if `protocol_acceptance/tools/acceptance_protocol.py` is present —
runs `check-contract`, `check-package`, `coverage`, `check-decision`, and the change-impact demo.
Requires `cargo`, `clippy` and `cargo-kani` on `PATH`; steps that need them are skipped with a clear
message when they are absent, per this script's own design (see its header). `run_example.sh`
removes `iban-check/target` (the cargo build output) at the end of its own run; a manual
`gen_package.py`/`make_decision.py` invocation outside the script leaves it behind — remove it
yourself (`rm -rf iban-check/target`) before running the repo's own gate suite: `target/` is
gitignored, but this repo's frontmatter gate sweeps the filesystem directly (not `git ls-files`),
so a stray `cargo doc` output under it trips that gate.

**Regenerating for real, without a fresh `dirty = true`:** `run_example.sh` on its own does not
commit anything (this script only ever runs tools, never `git commit`), so running it
after editing `iban-check/` will honestly reproduce `dirty = true` again (see "The one-commit
self-reference lag" above) — commit `iban-check/` first (source + `Cargo.lock` +
`rust-toolchain.toml`, nothing else pending under that path), THEN run `gen_package.py` (directly,
or via this script), THEN commit the regenerated `acceptance.toml` + `evidence/` as a second,
later commit, to reproduce this example's own clean, non-dirty package.

## Friction — where the protocol/format made a real Rust delivery awkward

- **The self-reference one-commit lag structurally conflicted with the Rust leaf's own "dirty must
  be false" rule — resolved (0.3, P2.5) by the two-commit re-stamp, but only as a workflow
  discipline, not a mechanism the tooling enforces for you.** This example's crate lives *inside*
  this repository, the same repository whose tooling validates it — so `[subject].commit` names a
  commit that cannot yet contain the manifest naming it if the crate and the package are committed
  together.
  `../../../format_acceptance/profiles/verification/code/rust.md` §1 (renamed from
  `protocol_acceptance/spec/profiles/rust-code.md` 2026-09-24) separately says "`dirty` must
  be false for a package a decision may accept," and `check-decision` enforces this as a hard,
  unconditional error. core.md B1's own note gives the
  fix used here: commit `iban-check/` on its own first, regenerate the package against that
  already-clean commit (`[subject].dirty = false` by construction), commit the package second.
  **Verified**: `check-decision` against this package's real decision now reports no error at all
  (binds, verification runs, dispositions, the §5.1 verdict computation, and the dirty check all
  clean) — the migration this task performed is exactly committing `iban-check/` first, then
  regenerating. The residual is a workflow one, not a structural guarantee: re-running
  `gen_package.py` against a working tree that has uncommitted `iban-check/` edits will honestly
  show `dirty = true` again, for the same reason, until the two-commit order is repeated. A
  genuine cross-organisation delivery, where the producer's tagged release commit is already clean
  before the package is even generated, never has to think about this at all — it is specifically
  an artifact of building a real example *inside* the repository that owns the protocol.
- **B20's `required_build_inputs` names a bare file, but this crate does not sit at the manifest's
  own root.** `code/rust.md`'s binding declares `required_build_inputs = ["Cargo.lock",
  "rust-toolchain.toml"]` — bare names, with no build-context-root locator on `[subject]` or
  anywhere in the binding's own declaration to anchor a match against a crate one level below its
  manifest. A cross-vendor review (2026-09-26) correctly rejected an earlier basename-matching
  fix as a real weakening (two unrelated files with the right names, in unrelated directories,
  would have satisfied the guard). The fix kept here: EXACT path semantics, anchored to this
  manifest's own directory, and two same-directory `Cargo.lock`/`rust-toolchain.toml` build inputs
  pointing at `iban-check/`'s own files. In this source repo `gen_package.py` keeps these as
  relative symlinks — one source of truth, never a copy that could silently drift; a
  published/exported copy of this example ships them as regular, byte-identical files (export
  copies bytes rather than preserving symlinks), which `gen_package.py` also accepts, checking
  byte-equality against the crate's own file before ever reusing it.
- **Kani's cost dominates everything.** The single largest engineering effort in this example was
  not writing the contract or the generator — it was making a ~15-line panic-freedom harness
  verify at all within a human-scale time-box. Two rewrites (heap → fixed buffers; unconstrained
  UTF-8 → ASCII-constrained, separately-bounded harness) and roughly 40 minutes of `cargo kani`
  wall-clock across the tuning runs were needed before the *shipped* proof (20 bytes, not the real
  34) completed in under 7 minutes. A format section on "what to do when the strongest available
  proof tool cannot reach the real bound in a reasonable time" would have saved most of this by
  naming the pattern (decouple the harness bound from the real capacity; disclose the gap as a
  deviation) as a first-class move rather than something this example had to discover.
- **Kani's tool-identity field wants a commit, and a plain `cargo-kani` install doesn't have one —
  core.md B20 (0.3) now gives this trap a checked shape, but still can't manufacture the missing
  identity.** `evidence-types.md` asks for `tool` at "build granularity (commit, not version)" for
  `kani-harness` records; `cargo kani --version` on this install prints a bare semantic version
  with no commit. The free-text `tool` string still says so explicitly (`kani@0.67.0 (commit
  unknown — …)`) rather than inventing a sha, and B20's typed `toolchain` list (leaf trap 5a.4,
  `code/rust.md` §1a) makes the SAME move structural: this package's `kani-harness` record (IB-003)
  carries no typed `toolchain` entry at all, because neither a `commit` nor a `digest` is available
  for `kani` — B20 never requires a `tool`-string component to have a typed counterpart. The
  records that DO carry a typed `toolchain` (every `rustc`/`cargo`/clippy-adjacent record) use real
  40-hex commits read straight from `rustc -vV` / `cargo --version --verbose`, so the gap is
  isolated to exactly the one tool that cannot supply it, not smoothed over. The Kani-adoption
  guide has a recipe for exactly this gap (`protocol_acceptance/adoption/
  KANI-FV-ADOPTION.md` §6: a deterministic Kani-bundle manifest digest plus a `cargo-kani` launcher
  binary digest, both typed `toolchain` entries using `digest` rather than `commit`); this
  regeneration did NOT adopt that bundle+launcher recipe — it still uses the plain `tool`-string
  disclosure described above. A future regeneration should adopt the guide's recipe instead;
  the guide's path is the recommended one.
- **The witness-for-weight rule (W2 condition 5) and the band-control-gate rule are two genuinely
  separate mechanisms that happen to look like the same thing.** R3's Kani evidence reaches band A1
  *without* a control (assurance-bands.md's no-oracle-freedom exception), but still needs a
  watched-fail *witness* for weight (`coverage-ledger.md` §3) regardless. Re-running Kani a second time just
  to produce that witness would have cost another ~7 minutes for no proof-strength gain, so this
  example uses a *different*, fast command (`cargo test --test checksum` against a buffer-shrink
  mutant) as the witness — which the format allows (witness option 2 needs only an observed-red
  control block on one of the claim's own evidence records, with no requirement that its carrier
  match the claim's primary evidence kind), but nothing in the spec text flags this as the
  intended, efficient path; it took independently re-deriving the rule from the validator's source
  to notice it was even available.
- **`grep`-based positive controls for "no unsafe code" collide with the literal word `unsafe`
  appearing in `#![forbid(unsafe_code)]` itself.** An earlier draft of this brief's own R4 plan
  (`grep -rn "unsafe" src/` must be empty) does not survive contact with the very attribute that
  makes the claim true — the brief corrected itself to the `lint` + `watched_fail`-via-real-mutation
  shape used here, but the first instinct (a grep-based absence check for "no X") being wrong in
  exactly the case where X is also the name of the mechanism proving its own absence is a trap
  worth naming in the profile document.
- **Six requirements is already enough TOML that hand-authoring risks drift from what the checker
  actually enforces.** A generic `assemble-package` verb now exists (`acceptance_protocol.py
  assemble-package`, worker-brief.md §2 — most fields mechanical, only `statement`/`grade`/
  `bounds`/`watched_fail` narrative/`deviation` text hand-supplied) and is clearly the right shape
  for this at any scale beyond one example crate; this example's `gen_package.py` predates
  adopting it and still hand-builds the TOML string-by-string — a future regeneration should move
  onto `assemble-package` instead, which would remove most of the string-building code in this
  file.
