---
type: reference
digest: Adoption guide for a Rust/Kani repo producing a 0.3.2 acceptance file — what to pin (public release commit + CLOSURE.json), the manifest header, subject identity (two-commit re-stamp), claims/bands/tiers for Kani vs tests vs Lean, typed record: hashes, B20 toolchain/build_inputs identity for a tool with no commit, spec inventory, rerun_location, the protocol contract/package/check-package flow, exact validator commands and exit codes, a pre-0.3 migration checklist, and known limits in 0.3.x. Includes commands for a clean public checkout and consumer templates.
---

# Adopting acceptance 0.3.2 in a Rust/Kani repo

**Audience.** A session (human or agent) in a Rust crate's own repository — outside this one — that
needs to produce a stable acceptance package against a formal-verification (Kani, and optionally
Lean+Aeneas) delivery, targeting acceptance **0.3.2 — locked, not ratified**.
Use the public repository's release commit. Nothing below assumes your crate shares a
filesystem, remote, or CI system with the public checkout. Commands containing consumer paths
or placeholders must be filled in for your repository; the recorded example results below
are historical validation evidence, not claims that your crate has already been verified.

Two documents you will want open beside this one:
[`../../format_acceptance/spec/core.md`](../../format_acceptance/spec/core.md) (the base format's
B-rules — B1, B12, B16, B19, B20 are cited by number throughout) and
[`../../format_acceptance/profiles/verification/code/rust.md`](../../format_acceptance/profiles/verification/code/rust.md)
(the Rust/Kani leaf — vocabulary, requirement patterns, mutation-control discipline, the four
"traps" a prior worked instance hit). This guide does not repeat their content; it is the path
through them for a first delivery. The shipped specifications and `CLASS-LOCK.toml` identify
the current family version; [`../../CHANGELOG.md`](../../CHANGELOG.md) records release history.

## 1. What to pin

Pin the public release commit and its exported closure together:

1. **The full 40-hex public release commit for 0.3.2.** Obtain it from the public release,
   check it out, and record it in your CI configuration. From that clean public checkout:

   ```sh
   PUBLIC_COMMIT=$(git rev-parse HEAD)
   export PYTHONDONTWRITEBYTECODE=1
   python3 gates/check_class_lock.py
   ```

   The public lock carries the same versioned Class file hashes as the source lock, with
   public release descriptions and `ratified = false`. The exporter reads this shipped lock.
   Its commit and cleanliness readers use this public checkout's git metadata, not the
   upstream commit recorded in `EXPORT-PROVENANCE.json`.

2. **A `CLOSURE.json`-manifested copy of the two consumer CLIs' full dependency closure**, produced
   by this repo's own exporter, `protocol_acceptance/tools/export_closure.py`
   (deliverable path, relative to this repo's root; see [`../tools/export_closure.py`](../tools/export_closure.py)):

   ```sh
   python3 protocol_acceptance/tools/export_closure.py export --dest ../your-crate/vendor/acceptance-format
   ```

   Run from the clean public checkout at the pinned release commit, with **`--dest` pointing OUTSIDE this
   checkout** — into your crate's own repository (a sibling directory works from any cwd; an
   absolute path also works). `export` REFUSES a destination inside this checkout, on purpose: an
   export written into `vendor/` here would itself show up in `git status`, so `source_dirty` would
   read `true` even from a clean tagged commit — provenance is captured before any file is written,
   from a `git` call with every inherited `GIT_*` override scrubbed, and it must describe THIS
   repository's own state, never be perturbed by where you chose to put the copy.

   **The destination must not already exist**, even as an empty directory or dangling symlink.
   Export to a fresh path when updating a vendor copy. The exporter copies into a uniquely created
   sibling staging directory, scans it, and renames it into place only after the scan passes.
   A hygiene refusal removes only that staging directory; existing destination contents survive.

   Output shape (the file count is measured by discovery; the commit is your public pin
   and `source_dirty` must be `False`):

   ```
   EXPORT OK: 20 files -> /path/outside/this/checkout
     export_closure.py
     format_acceptance/profiles/bindings/code.md
     format_acceptance/profiles/bindings/code/rust.md
     format_acceptance/tools/acceptance_grammar.py
     format_acceptance/tools/bindings/__init__.py
     format_acceptance/tools/bindings/code.py
     format_acceptance/tools/bindings/code_rust.py
     format_acceptance/tools/check_acceptance.py
     format_acceptance/tools/check_core.py
     format_acceptance/tools/hashdomains.py
     format_acceptance/tools/profiles/__init__.py
     format_acceptance/tools/profiles/conformance.py
     format_acceptance/tools/profiles/troubleshooting.py
     format_acceptance/tools/profiles/verification.py
     format_acceptance/tools/spec_inventory.py
     protocol_acceptance/spec/assurance-classes.toml
     protocol_acceptance/spec/states.toml
     protocol_acceptance/tools/acceptance_protocol.py
     protocol_acceptance/tools/m11.py
     protocol_acceptance/tools/profiles.py
     family_version=0.3.2 source_commit=<public-40-hex> source_dirty=False
   ```

   `export_closure.py` itself is now ONE of the 20 manifested files (not a bare, unverified
   convenience copy) — a hand-edited or corrupted copy of the exporter/verifier is caught by
   `verify` the same as any other file. Files are copied byte-for-byte and scanned for home-relative
   paths and other apparatus tokens; export never rewrites them. Python files use their declared
   PEP 263 encoding (`tokenize.detect_encoding`); other text files use UTF-8. Undecodable files
   and NUL bytes are hygiene failures. Commit the whole exported directory as-is.

   Commit that directory (including its `CLOSURE.json`) into your crate's own repo. This REPLACES
   the old three-file vendor pattern (pinning `check_acceptance.py`, `acceptance_grammar.py`, and
   `check_core.py` by hand): that pattern silently drifts the moment a fourth file becomes
   load-bearing, which is exactly what happened once B20/B21 and the Rust binding's own admission
   documents entered the picture (§12 below has the receipts). One measured, mechanically-derived
   manifest — not a hand-maintained list — is the whole point of `export_closure.py`.

3. **Re-verify in CI**, every run, from your consumer repository. Set `PUBLIC_COMMIT` to
   the public release commit recorded in step 1 (CI must read the pin, not derive it from
   the consumer repository's HEAD). No access to the public source checkout is needed:

   ```sh
   python3 vendor/acceptance-format/export_closure.py verify --dest vendor/acceptance-format \
     --expect-commit "$PUBLIC_COMMIT" --require-clean --expect-family-version 0.3.2
   ```

   This recomputes every listed file's sha256 against `CLOSURE.json` (including the exporter's own
   copy), checks that its `source_commit` is your pin and `source_dirty` is `false`, and fails on
   any mismatch, drift, a missing file, an extra untracked `.py`/`.toml`/`.md` file, or ANY
   `.pyc`/`__pycache__` present anywhere under the export (an interpreter can silently load cached
   bytecode instead of the verified source it shadows — a vendored closure ships source only) —
   catching bit rot, a bad merge, a half-applied vendor update, or a stale bytecode cache before any
   of them silently changes what your validator run means. Then run your validator commands (§10)
   from your consumer repo's own root, with the vendored tool paths as prefixes.

   **Run every vendored tool with bytecode writing disabled** (`PYTHONDONTWRITEBYTECODE=1` in the
   environment, or `python3 -B ...`) — since `verify` rejects ANY `.pyc`/`__pycache__` found
   anywhere under the export, a CI job that runs the validators and then `verify` in the SAME
   checkout, without disabling bytecode writes first, would see its own run's cache flagged as a
   false positive. Disabling it costs nothing and keeps `verify` meaningful at any point in a CI
   job, not only immediately after a fresh checkout.

   `python3 protocol_acceptance/tools/export_closure.py --selftest` (this repo) proves the whole
   chain mechanically: exports to a temp dir OUTSIDE this repo; smoke-runs every consumer verb from
   that export under Python's isolated mode (`-I -B`) with an audit hook that FAILS the run the
   moment it observes an `open()` or a loaded module resolving back into this repo's checkout
   (clearing `PYTHONPATH` alone does not prove that — this asserts it, per run) and asserts the
   EXACT expected exit code (not merely "no traceback"); reproduces the exact regression a prior
   review round found (delete the Rust binding's admission document from an export and confirm the
   resulting INDETERMINATE/exit-2 is CAUGHT, not silently accepted); and runs missing-file,
   extra-file, one-byte-corruption, exporter-self-tamper, and stray-bytecode able-to-fail controls
   against `verify`. See this repo's own `gates/check_export_closure.py`.

### Source hygiene

The exported tools' comments, docstrings and output strings (refusal messages, selftest labels)
use neutral behavioral descriptions rather than references to internal review or development
history; `export_closure.hygiene_violations()` scans for, and rejects, home-relative paths and
similar internal-only tokens. Predicates, exit codes, hash construction, and validation logic are
unaffected by that wording.

Regression controls exercise existing-destination preservation, a compilable Latin-1
Python payload containing a forbidden token, undecodable Python/Markdown/TOML files, and NUL bytes
in each text type. The exported inventory tool's `make`, `check`, and `digest` verbs all run under
the denying audit-hook harness; `check` consumes the actual `make` output and `digest` is compared
with an independently computed inventory digest.

## 2. The manifest header

Every manifest ([format].profile) names the EXACT leaf, not the meaning alone (0.3.1 ruling A1):

```toml
[format]
id       = "acceptance/0"
protocol = "acceptance-protocol/0"       # RECOMMENDED: says this is a protocol package (§9 below)
profile  = "acceptance/verification/code/rust"
```

`[format].profile` is REQUIRED at 0.3.0+ (core.md B12) — a manifest that omits it is an ERROR
naming the field, not a silently-assumed default. If your contract's `profiles_required` names the
meaning-only id (`acceptance/verification`) rather than this exact leaf, your package will be
refused (protocol.md §4.1 rule 6): a contract written for a Kani delivery should name
`acceptance/verification/code/rust` explicitly (see the contract template, §9 and §13).

## 3. Subject identity — the two-commit re-stamp

`[subject]` for a `rust-crate`/`rust-workspace` carries the format's B1 git-revision identity:

```toml
[subject]
name   = "your-crate"
kind   = "rust-crate"
commit = "<40-hex git sha of the ALREADY-COMMITTED crate>"
dirty  = false
```

`dirty` MUST be `false` for a package a decision may accept (the Rust leaf's own package
constraint, enforced at decision time by `acceptance_protocol.py`). If your crate and
your package generator live in the SAME repository, you will hit the same one-commit
self-reference lag the worked example did, and there is one documented fix, not a mechanism change
(core.md B1's own note; verified end-to-end in
[`../examples/rust-delivery/README.md`](../examples/rust-delivery/README.md) "The one-commit
self-reference lag — resolved by the two-commit re-stamp"):

1. Commit your crate (`src/`, `Cargo.lock`, `rust-toolchain.toml`, tests, benches) **on its own**,
   with nothing else pending under that path (`git status --short -- your-crate/` empty).
2. Generate `acceptance.toml` (and `evidence/`) against that now-clean, already-committed HEAD.
   `[subject].commit` names that commit; `dirty = false` holds by construction, because the
   manifest's own commit is chronologically AFTER, and disjoint from, the commit it certifies.
3. Commit the generated `acceptance.toml` + `evidence/` as a SECOND, later commit.

A real cross-organisation delivery never hits this at all — the producer's tagged release commit is
already clean before the package that certifies it is even generated. This two-commit order is a
workflow discipline your generator script must repeat on every regeneration that touches the crate,
not something the tooling enforces for you.

## 4. Claims, bands and tiers — Kani vs tests vs Lean

The format's ONE artifact-agnostic warrant ordering is `T1 > T2 > T3 > T4 > T5` (deductive >
mechanically-sound-decision > empirical-sampled > mechanical-syntactic > judgment). The Rust
binding's tokens (core.md B3/B4 kinds, rust.md §2):

| your evidence | `kind` | `family` | ceiling `epistemic_tier` |
|---|---|---|---|
| a `cargo test`/`proptest` run | `unit-test` / `property-test` | `dynamic` | T3 |
| a Kani bounded-model-check harness | `kani-harness` | `bmc` | T2 |
| Miri (UB/memory-safety under the interpreter) | `miri` | `dynamic` | T3 |
| a Lean theorem (via Aeneas extraction) | `lean-theorem` | `kernel` | T1 |
| `cargo clippy` / lint attributes | `lint` | `mechanical` | T4 |
| `cargo semver-checks` | `semver-check` | `mechanical` | T4 |

**Bounded vs unbounded.** A Kani harness proves a property up to a declared bound
(`KANI_BOUND`/`unwind`); it is a `bmc`-family, T2 record, never T1 — the class-shared tier ordinal
does not let a bounded proof borrow an unbounded one's strength. Declare the bound honestly on the
CLAIM (`bounds = "bounded: KANI_BOUND=32 bytes"`, rust.md §1) and, if your contract carries the
cross-cutting "every claim holds over the whole input domain" requirement (rust.md §1's
`demands.fields.bounds = "unbounded"`, modelled in the contract template, §13), a bounded harness
computes that cross-cutting requirement as `partial` with a `[[deviation]]` — the HONEST row, not a
failure (rust.md §5a trap 1). A Lean theorem (`kernel` family, T1) is the only Rust-binding token
that can satisfy an `unbounded` demand outright.

**Two SEPARATE obligations, easy to conflate: a band-lift
CONTROL and a weight WITNESS are not the same requirement, and freedom-claim relief from the first
does not relieve the second.**

1. **The band-lift control** (core.md B2's `control_free_ceiling`: A1 for
   `kani-harness`/`miri`/`fuzz`, A3.5 for `flux-refinement`, A0 by default) is what lets a claim's
   `band` sit ABOVE the ceiling at all: an observed-red control on one of the claim's own records —
   apply a source patch (a real mutation), re-run the SAME command, require red, restore the file
   byte-exactly, record the transcript (rust.md §5). rust.md's one named exemption from THIS
   obligation is explicit and narrow: **a panic/UB-freedom claim reaches band A1 with no band-lift
   control** ("kani-harness panic-freedom (A1 needs no control for freedom claims)").
2. **The weight witness** (format design rule 5 / the "WEIGHT REFUSED" check) is a DIFFERENT,
   independent obligation that applies to every `weight = "weighted"` claim regardless of band or
   species: a `[claim.self_verify.watched_fail]` table (or an observed-red control naming the same
   claim, or a `positive_control` on a `not-covered`-grade record) — something that demonstrates the
   claim COULD have failed and did not. The freedom-claim exemption above relieves obligation 1
   ONLY. Verified: taking this guide's own filled `K-001` claim (§13 — a band-A1, `kani-harness`,
   UNWEIGHTED panic-freedom claim, exactly as shipped) and adding nothing but `weight = "weighted"`
   reproduces a hard failure:

   ```
   ERROR ...: claim 'K-001': WEIGHT REFUSED (transitional): no watched-fail witness (W2.5, P2) —
   needs a [claim.self_verify.watched_fail] table, an observed-red control naming this claim, or
   (not-covered) a positive_control (0.1-DRAFT §8.1)
   FAIL acceptance.toml (1 error) [weighted: 0, unweighted: 1, weight-pending: 1]
   ```

   Adding a witness makes the SAME weighted claim pass — this exact snippet, verified against the
   template's own `K-001`:

   ```toml
     [claim.self_verify]
     command = "cargo kani --harness never_panics"
     expect  = "VERIFICATION:- SUCCESSFUL"

     [claim.self_verify.watched_fail]
     of_command = "cargo kani --harness never_panics"
     perturbed  = "removed the bounds check before the panic-free operation, so an out-of-range index is reachable"
     observed   = "VERIFICATION:- FAILED\nindex out of bounds panic reachable in never_panics"
     date       = "2026-01-01"
   ```

   ```
   PASS acceptance.toml [weighted: 1, unweighted: 1]
   ```

   **The shipped starter template's `K-001` is UNWEIGHTED BY DESIGN** (no `weight` field at all) —
   precisely so a first-cut skeleton never needs a witness to validate. Add `weight = "weighted"`
   only once you also add its own witness; both halves are exercised as automated controls in
   [`templates/selftest_templates.py`](templates/selftest_templates.py) (`check_weighted_claim_needs_witness`).

For a FUNCTIONAL claim that is not a freedom claim, obligation 1 also applies at A1 even though it
is `dynamic`-family; the honest band-lift witness there is usually a *different, fast* command that
goes red against the same claim (rust.md §5a trap 2) — a seven-minute Kani re-run bought as "the
control" for a claim a two-second mutated `cargo test` already falsifies is not the cheap, honest
form.

**Band-less claims must disclose the floor.** If a claim carries no `band`, core.md B2 requires the
claim to be treated at the verification ladder's floor (`A0`) for every floor comparison, AND
requires the exact word `A0` to appear in the claim's `statement` (a word-boundary match — `A0`
inside a longer token like `A0x` does not count). Verified: the package template's own gap claim
for its cross-cutting requirement (`K-002`, §13) needed exactly this fix during this guide's own
testing — `check_acceptance.py --strict` refused it with `B2: band-less claim is treated at ladder
floor A0; statement must disclose A0` until the word `A0` was added to its statement. Simplest
practical rule: just set `band = "..."` explicitly on every claim (as this guide's templates and
the worked example both do) and skip the disclosure dance entirely.

## 5. Evidence records and typed `record:` hashes

**0.3.1 ruling B1-wording**: writers MUST emit typed `record:sha-512:<128-hex>` record hashes; the
untyped legacy bare `sha-512:<hex>` wire is READ-ONLY (WARNING, not an error) on every profile in
0.3.x, retirement to ERROR is a 0.4 change. The worked example's own generator
(`../examples/rust-delivery/gen_package.py`) was itself carrying the untyped legacy wire until the
0.3.1 tool-fix round regenerated it to call `hashdomains.digest("record:", ...)`
directly — copy ITS current `record_hash(...)` helper (`gen_package.py`'s own function of that
name), not an older recollection of it; a validated real package now shows ZERO B16 warnings for
this field (§10).

Compute a typed hash with `hashdomains.py`'s own API (never re-implement the construction):

```python
import sys
sys.path.insert(0, "vendor/acceptance-format/format_acceptance/tools")  # or wherever you vendored it
import hashdomains

record_bytes = open("evidence/kani-never-panics.txt", "rb").read()
record_hash = hashdomains.digest("record:", record_bytes)
# -> "record:sha-512:<128 lowercase hex characters>"
```

Verified (this repo, illustrative bytes — your own record's bytes will differ):

```
$ python3 -c "
import sys; sys.path.insert(0, 'format_acceptance/tools')
import hashdomains
print(hashdomains.digest('record:', b'illustrative-binary-bytes'))
"
record:sha-512:3a3bfdb48a6aae61fa9401ffe980950562a3d2bd2763d85dd8d8d1698300d06dc468d9f6670fd83e20dad752a18096e8bdb8ee6530f78603101d20c38c7b8115
```

`check_acceptance.py`/`check_core.py` recompute this hash over the pointed-at file's bytes on every
validation path and FAIL on mismatch (core.md B6/B16); a present-but-unresolvable record pointer is
a WARNING that becomes an ERROR under `--strict`. Every `record` path is resolved relative to the
manifest's own directory and must stay inside the nearest `.git` ancestor (core.md B6) — an
acceptance package validated from a directory with no `.git` at all cannot resolve any record
pointer (this guide's own template selftest hit exactly this while testing outside a git checkout;
`git init` first).

## 6. B20 toolchain and `build_inputs` — Kani's missing commit

core.md B20 lets an evidence record carry a typed `toolchain` list (`{name, version?, commit?,
digest?}`, at least one of `commit`/`digest` required) and a typed `build_inputs` list (`{path,
digest}`, digest recomputed and checked on every validation path).

**Known Kani limit** (not Class text; a tool-behavior note, not a format rule): `cargo kani --version`
prints a bare semantic version (e.g. `cargo-kani 0.67.0`), never a build commit — there is no
`commit` value to write honestly. B20 accepts EITHER `commit` OR `digest`; for Kani, use `digest`.

**Launcher vs bundle — hash the bundle, not the proxy.** A
standard Kani install has TWO distinct artifacts, and hashing only the first identifies nothing
about the second: `~/.cargo/bin/cargo-kani` (and `~/.cargo/bin/kani`) are a small LAUNCHER
proxy binary that locates and invokes a separately-installed RELEASE BUNDLE — the actual verifier,
compiler and SAT/SMT solver payload — at `~/.kani/kani-<version>/`. Hashing only the launcher
leaves `kani-compiler`, `kani-driver`, `cbmc`, `kissat`, and every `.rlib` completely unbound: two
installs could share an identical launcher while running entirely different solvers underneath.
Verified real layout (this machine, Kani 0.67.0 — your own install will differ in exact file names
by platform/version, not in shape):

```
$ ls ~/.kani/kani-0.67.0
bin  lib  library  license-notes.txt  no_core  playback  rust-toolchain-version  rustc-version  scripts  toolchain
$ ls ~/.kani/kani-0.67.0/bin
cbmc  goto-analyzer  goto-cc  goto-instrument  kani-compiler  kani-cov  kani-driver  kissat
```

(`toolchain` is a symlink into `~/.rustup/toolchains/...` — that is a SEPARATE artifact, the Rust
toolchain itself, identified by its own `toolchain` entry per B20's existing `rustc`/`cargo`
guidance; exclude symlinks from the bundle's own manifest below, don't double-count it.)

**The recipe: a deterministic manifest of the bundle's own files, then one digest over that
manifest** — verified end to end on this machine, deterministic across repeated runs:

```python
import hashlib, pathlib, re, subprocess, sys
sys.path.insert(0, "vendor/acceptance-format/format_acceptance/tools")
import hashdomains

def kani_bundle_dir() -> tuple[pathlib.Path, str]:
    out = subprocess.run(["cargo", "kani", "--version"], capture_output=True, text=True, check=True).stdout
    version = re.search(r"(\d+\.\d+\.\d+)", out).group(1)
    bundle = pathlib.Path.home() / ".kani" / f"kani-{version}"
    if not bundle.is_dir():
        raise RuntimeError(f"expected Kani release bundle at {bundle}, not found")
    return bundle, version

def bundle_manifest_digest(bundle_dir: pathlib.Path) -> str:
    lines = []
    for p in sorted(bundle_dir.rglob("*")):
        if p.is_file() and not p.is_symlink():          # exclude the `toolchain` symlink
            rel = p.relative_to(bundle_dir).as_posix()
            lines.append(f"{rel}:{hashlib.sha256(p.read_bytes()).hexdigest()}")
    manifest_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    return hashdomains.digest("artifact:", manifest_bytes)

bundle_dir, version = kani_bundle_dir()
bundle_digest = bundle_manifest_digest(bundle_dir)      # binds kani-compiler, kani-driver, cbmc, kissat, every .rlib
launcher_digest = hashdomains.digest("artifact:", (pathlib.Path.home() / ".cargo/bin/cargo-kani").read_bytes())
```

Verified real digests (this machine — a 121-file bundle manifest, deterministic on re-run):

```
bundle:   artifact:sha-512:93e69f006c3136fddf621f5048ca6722ee985fdbc37b849f42da1a35e1b296d4c2a4c5673fe113d477a4d6306968498567cc353f76c2a529fa88b3186bb6ed8e
launcher: artifact:sha-512:9a10a7f0599181c6e6a103de5910e67c59843ce825420aa54a99549246e3097cc615cc4aefb2ddfde1520bf7e013f13e2461e362dfba867f75bf5e16679907d4
```

Write BOTH as distinct `toolchain` entries — they are different artifacts with different identity,
and collapsing them into one entry loses exactly the distinction this finding is about:

```toml
[[claim.evidence.toolchain]]
name    = "kani-bundle"
digest  = "artifact:sha-512:<128-hex, the deterministic manifest digest over ~/.kani/kani-<version>/'s own files>"
[[claim.evidence.toolchain]]
name    = "cargo-kani-launcher"
digest  = "artifact:sha-512:<128-hex, the ~/.cargo/bin/cargo-kani launcher binary's own bytes>"
# no `commit` on either entry -- cargo-kani reports none; do not invent one (rust.md §5a trap 4)
```

Also write the free-text `tool` string honestly rather than leaving the gap silent: `tool =
"kani@0.67.0 (commit unknown — cargo kani --version reports no commit; bundle+launcher digests in
toolchain[])"` (rust.md §5a trap 4). This leaf never invents a commit or a digest to manufacture a
`tool`-string component B20 does not ask for; the typed fields are simply written with what B20
DOES accept.

`build_inputs` SHOULD carry `Cargo.lock` and `rust-toolchain.toml` — the Rust binding's own
`required_build_inputs` declaration (`format_acceptance/profiles/bindings/code/rust.md`'s
machine-readable block; this is the SAME markdown document the closure exporter had to learn to
vendor, §12). Once ANY weighted claim's evidence declares a `build_inputs` list at all, the union of
declared paths across that claim's evidence MUST include both files (B20's opt-in-complete guard).
`baseline/4` (the top assurance-class level) makes this MANDATORY, not merely SHOULD
(`build_inputs_required`); below level 4 it is a recommendation your evidence can adopt early:

```toml
  [[claim.evidence.build_inputs]]
  path   = "Cargo.lock"
  digest = "artifact:sha-512:<128-hex, recomputed by the validator over Cargo.lock's own bytes>"
  [[claim.evidence.build_inputs]]
  path   = "rust-toolchain.toml"
  digest = "artifact:sha-512:<128-hex>"
```

**The `path` match is EXACT, not by basename (fixed at 0.3.1).** An
earlier 0.3.1 round matched `required_build_inputs` by basename alone, which let two unrelated
files that merely happened to be NAMED `Cargo.lock`/`rust-toolchain.toml` anywhere in the manifest's
declared inputs satisfy the guard — a correct digest establishes a file's bytes, not its
relationship to the actual build. This was reverted to EXACT path semantics, anchored to the
manifest's own directory (core.md B6): `path` must read exactly `"Cargo.lock"` /
`"rust-toolchain.toml"` (the bare names `code/rust.md` declares), resolved relative to WHERE THE
MANIFEST LIVES. Two ways to satisfy this:

1. **Put the manifest at your crate's own root**, beside its real `Cargo.lock` and
   `rust-toolchain.toml` — the simplest case, no extra step.
2. **If the manifest lives elsewhere** (a `reports/` directory, a monorepo's tooling directory,
   or — the worked example's own case — a manifest one level above the crate it certifies), add a
   same-directory, repository-CONTAINED relative symlink named exactly `Cargo.lock` /
   `rust-toolchain.toml` pointing at the real files, so `path = "Cargo.lock"` resolves next to the
   manifest. B6's containment rule still applies after symlink resolution — a symlink escaping
   the repository root fails, same as an absolute path. The public worked example ships
   **regular files** at those two manifest-relative paths, byte-identical to the matching
   `iban-check/` files. Its generator accepts either the relative symlinks or identical regular
   copies; a differing regular file is an error and is never silently overwritten. The public
   suite checks both accepted layouts and both drift refusals through `build_inputs_block()`,
   without running evidence commands.


## 7. Spec inventory (B19) — only if a governing document exists

If a standard, RFC, or your crate's own `SPEC.md` governs the property you are verifying, `[spec]`
can carry a B19-shaped inventory so every clause of that document is either cited by a claim or
visibly missing (never silently unaddressed). Generate it mechanically, never by hand:

```sh
python3 $VENDOR/format_acceptance/tools/spec_inventory.py make YOUR-SPEC.md > your-spec.inventory.toml
python3 $VENDOR/format_acceptance/tools/spec_inventory.py check YOUR-SPEC.md your-spec.inventory.toml
python3 $VENDOR/format_acceptance/tools/spec_inventory.py digest your-spec.inventory.toml
```

(`$VENDOR` is §9's convention: run from your consumer repo's own root, `$VENDOR=vendor/acceptance-format`.)

Verified (this repo, run from inside this checkout with `format_acceptance/spec/hash-domains.md`
standing in for "your own spec document" — the command shape and the `$VENDOR` prefix above are
identical either way, only the working directory in this specific transcript differs):

```
$ python3 format_acceptance/tools/spec_inventory.py make format_acceptance/spec/hash-domains.md
[inventory]
id = "hash-domains"
title = "Hash domains (B16)"
source = "format_acceptance/spec/hash-domains.md"
numbering = "S-<n> per top-level (level-2) heading in document order, ..."

[[item]]
id = "S-1"
title = "Read-only legacy record wires"
...

$ python3 format_acceptance/tools/spec_inventory.py check format_acceptance/spec/hash-domains.md hd-inventory.toml
CLEAN format_acceptance/spec/hash-domains.md matches hd-inventory.toml: 2 item(s)

$ python3 format_acceptance/tools/spec_inventory.py digest hd-inventory.toml
inventory:sha-512:be53b482405b0c51b1ffeb48b4a328b1f587a785a438d1ef488c499b763181d5f20e80432bb6c0120c7c6f8eba986e32c96f6aa9243e3b40ac8586424a7d4c21
```

`check` reports drift (`ADDED`/`REMOVED`/`RETITLED` lines, exit 1) whenever your spec document
changes and the inventory has not been regenerated — re-run `make`, never hand-edit the inventory
file. Put the `digest` output in `[spec].inventory_digest` and the inventory's path in
`[spec].inventory`; every declared `[[item]]` id must then be named by at least one claim's
`clause` (including a `not-applicable`/`excluded` claim) or B19 fails naming the missing ids. If you
have no governing document, skip this section entirely — `[spec].inventory`'s absence adds no
check (B19).

**This drift check is HEADING-LEVEL, not content-level — do not
oversell it as "the spec hasn't changed."** `spec_inventory.py check` compares only each item's
`id` (derived from the heading) and `title` (the heading text). Rewriting an entire clause's
NORMATIVE BODY while leaving its heading untouched reports **CLEAN**. Verified:

```
$ cat a.md              # "make"'s source: ## S-1 \n Original normative text.
$ cat b.md              # a LATER revision:  ## S-1 \n COMPLETELY DIFFERENT normative text with an inverted requirement.
$ python3 format_acceptance/tools/spec_inventory.py check b.md inv.toml   # inv.toml generated from a.md
CLEAN b.md matches inv.toml: 1 item(s)
```

If you need to know that the governing document's actual BYTES are unchanged (content freshness,
not merely "no headings were added or removed"), bind the document separately with core.md's
EXISTING `normative-reference:` mechanism (`check_core.check_spec`, B6): set `[spec].provenance =
"external"` and `[spec].version` to a `normative-reference:sha-512:<128-hex>` digest over the
governing document's own bytes (computed the same way as every other typed hash in this guide,
`hashdomains.digest("normative-reference:", ...)`) — the validator recomputes this digest over
`[spec].path`'s actual bytes on EVERY validation path and FAILs on any byte-level change, which the
heading-only B19 inventory cannot see. The two mechanisms answer different questions and are both
useful together: B19 (headings) answers "is every clause addressed, and is nothing extra silently
added"; `[spec].provenance = "external"` (bytes) answers "is this exactly the document version I
pinned."

## 8. Where evidence commands run (`rerun_location`)

The party boundary's `rerun_location` term (protocol.md §3.4a) states, once per contract, where the
consumer re-executes your recipes. **Recommendation for a Kani/Rust delivery: repo-checkout
relative, run from the package root** — the same convention `[claim.self_verify].command` already
uses in the worked example (`cargo test --test malformed`, `cargo kani --harness …`, both run from
the crate's own directory, matching the paths `[[claim.evidence.inputs]]` and `build_inputs`
declare). State it explicitly in `[parties.boundary_terms].rerun_location` when the boundary is
`cross-org` (REQUIRED fields there are only `disclosure` and `integrity`, but `rerun_location` is
exactly the free-text field this ambiguity belongs in): `rerun_location = "consumer clones the
tagged commit and runs every self_verify.command from the crate's own root, with the toolchain the
record's tool string names"`. This is carried and displayed, never mechanically checked (P9) — but
an undeclared `rerun_location` is the single most common way a re-execution disagrees with the
producer's transcript for a reason that has nothing to do with the code (a different working
directory changes every relative path the recipe reads).

## 9. The protocol side — contract, package, decision, all from YOUR repo's own root

**Every command below runs from your consumer/producer repo's own root** — never from inside the
vendored `vendor/acceptance-format/` directory, and never with
directory-hopping between steps. Set one shell variable once and use it as a prefix throughout; the
FILE arguments (your contract, your package, your decision) stay plain relative paths from that one
root the whole time:

```sh
cd your-crate/                              # your repo's own root — stay here for every command
VENDOR=vendor/acceptance-format             # wherever §1's export landed
```

**The contract is authored by the requester, not the producer** (protocol.md P1: "the contract IS
the spec"). In a larger organisation this may be a central platform/governance team holding
contracts for many crates, not the crate's own repository — but the mechanism is identical either
way; nothing below assumes a particular org shape. Copy
[`templates/kani-crate.contract.toml`](templates/kani-crate.contract.toml) (§13 — this template
ships in the public repository alongside this guide, not inside the exported tool closure; copy it
separately from your pinned checkout), fill it in as
`your-crate.contract.toml`, then:

```sh
python3 $VENDOR/protocol_acceptance/tools/acceptance_protocol.py check-contract your-crate.contract.toml
```

Once you have a package (`acceptance.toml`, generated from §13's `kani-crate.acceptance.toml`
skeleton filled in with real evidence — never hand-edited):

```sh
python3 $VENDOR/format_acceptance/tools/check_acceptance.py --strict --strict-weight acceptance.toml
python3 $VENDOR/protocol_acceptance/tools/acceptance_protocol.py check-package acceptance.toml --contract your-crate.contract.toml
python3 $VENDOR/protocol_acceptance/tools/acceptance_protocol.py coverage acceptance.toml --contract your-crate.contract.toml
```

`check-package` validates through the profile's own package validator (§4.1 rules 1-7: contract
hash recomputes, every claim's `clause` resolves, every unmet mandatory requirement carries a
`[[deviation]]`, the bound contract is itself valid and binding, subject identity, profile
membership, producer identity) — AFTER the format-level check already passed. That format-level
check IS `check_acceptance.py`'s own `validate` for `acceptance/verification*` profiles (§12: this
now runs the Rust binding's own checks too, not only the class-level ones).

### The decision: `decide` drafts, it does not itself re-run anything, then `check-decision`

**`decide` is a DRAFTING step, not a verification step** — it computes dispositions STRUCTURALLY
from `coverage(contract, package)` and writes a skeleton; it never executes a single command. Every
`[[verification.run]]` row in its output starts `result = "not-run"` — a placeholder naming what
MUST be re-run, not a claim that anything already was. Verified real output (this repo's own worked
example, `../examples/rust-delivery/`, run from that directory with plain relative paths — the
consumer-root convention above holds identically for your own repo):

```sh
python3 ../../tools/acceptance_protocol.py decide acceptance.toml --contract acceptance-contract.toml --issuer "your-team / lead" --out acceptance-decision.toml --mode re-execute-all
```
```
wrote decision skeleton to acceptance-decision.toml
```
```toml
[document]
...
verdict    = "rejected"
note       = "skeleton: 1 mandatory requirement status(es) not satisfied — edit waivers/conditions and re-run check-decision"
...
[[verification.run]]
claim   = "IB-001"
command = "cargo test --test malformed"
result  = "not-run"
...
```

**Consumer reruns (the actual verification step, P9: never trust the producer's transcript as
proof of its own truth).** For every `[[verification.run]]` row, run its `command` yourself (from
`rerun_location`, §8) and replace `result = "not-run"` with the REAL `result` (`pass` | `fail` |
`error`), the real `observed` output tail, and `at` (a timestamp). A generator script does this
mechanically — the worked example's own `../examples/rust-delivery/make_decision.py` is the
reference shape: it runs every basis claim's command for real, fills in the decision's
`[[verification.run]]` rows, adds any needed `[[condition]]`/waiver, and writes the completed
document. Never hand-edit a `result` field without actually having run the command.

**Completion.** The decision is complete once every basis claim's run reflects a REAL result and
`§5.1`'s verdict/disposition coherence table (protocol.md §5.1) is satisfied by what actually
happened — a `rejected` skeleton is not a failure of this tooling, it is the honest starting state
before anything has been re-verified. Then validate the completed document:

```sh
python3 $VENDOR/protocol_acceptance/tools/acceptance_protocol.py check-decision acceptance-decision.toml --contract your-crate.contract.toml --package acceptance.toml
```

An `accepted-with-conditions` decision is not the end of the lifecycle either: each condition mints
an obligation (protocol.md §5.3); a LATER, superseding package that discharges it gets its OWN new
decision (`discharge-conditions`, never an edit to the original one). That fuller lifecycle is
outside this getting-started guide's scope — protocol.md §5.3–§5.4 is the reference.

## 10. Exact validator commands and exit codes

Every command below was run against this repo's own worked example
(`../examples/rust-delivery/`) or this guide's own templates during the writing of this guide, from
INSIDE this repo (so the tool paths are relative to the example's own directory, `../../tools/...`)
— this section is verification evidence for the mechanism itself, not a layout recommendation. §9's
"from your consumer repo root, with a `$VENDOR` prefix" convention is what an external Rust/Kani
repo should actually follow; the verb names, flags, and exit codes below are identical either way.

| command | exit 0 | exit 1 | exit 2 | exit 99 |
|---|---|---|---|---|
| `check_acceptance.py [--strict] [--strict-weight] FILE` | PASS / PASS-PROSPECTIVE | FAIL (class or 8b error) | INDETERMINATE (unresolvable root, unknown profile, indeterminate reference) | — |
| `acceptance_protocol.py check-contract C.toml [--previous OLD]` | valid | validation error(s) | usage error, OR indeterminate validation (`Reporter.exit_code()`: an `unknowns` entry, e.g. an unresolved format evaluation, exits 2 the same as a usage error) | — |
| `acceptance_protocol.py check-package P.toml --contract C.toml` | valid | validation error(s) | usage error, OR indeterminate validation (same overload as `check-contract`) | — |
| `acceptance_protocol.py check-decision D.toml --contract C --package P` | valid | validation error(s) | usage error, OR indeterminate validation (same overload as `check-contract`) | — |
| `acceptance_protocol.py decide P.toml --contract C.toml --issuer NAME --out D.toml` | skeleton written (verdict inside may still be `rejected` — a DRAFT, §9) | — | usage/load error | — |
| `acceptance_protocol.py --selftest` | selftest green | — | — | mismatch |
| `spec_inventory.py check SPEC.md INV.toml` | clean | drift found | usage/unreadable | — |
| `export_closure.py verify --dest DIR` | closure matches | drift/missing/extra | — | — |

**Exit 2 is overloaded for `check-contract`/`check-package`/`check-decision`: it means either a CLI
usage error, or that validation itself is INDETERMINATE** (`acceptance_protocol.py`'s `Reporter`
class returns 2 whenever it recorded an `unknowns` entry, not only on a usage error). An
indeterminate result establishes neither package nor decision validity — it is not a lesser form
of PASS.

Verified real runs (this repo, `protocol_acceptance/examples/rust-delivery/`, run from that
directory):

```
$ python3 ../../../format_acceptance/tools/check_acceptance.py --strict --strict-weight acceptance.toml
PASS acceptance.toml [weighted: 5, unweighted: 1]
$ echo $?
0

$ python3 ../../tools/acceptance_protocol.py check-contract acceptance-contract.toml
WARN acceptance-contract.toml: NOTE (spec-clarity): 6 firm / 0 draft requirement(s)
PASS acceptance-contract.toml (1 warning)
$ echo $?
0

$ python3 ../../tools/acceptance_protocol.py check-package acceptance.toml --contract acceptance-contract.toml
WARN acceptance.toml: [check-contract] NOTE (spec-clarity): 6 firm / 0 draft requirement(s)
PASS acceptance.toml (1 warning)
coverage (profile: 'acceptance/verification/code/rust')
  R1: satisfied [mandatory] basis=['IB-001']
  ...
$ echo $?
0

$ python3 ../../tools/acceptance_protocol.py check-decision acceptance-decision.toml --contract acceptance-contract.toml --package acceptance.toml
WARN acceptance-decision.toml: [check-contract/check-package/package-validator transitively] [check-contract] NOTE (spec-clarity): 6 firm / 0 draft requirement(s)
PASS acceptance-decision.toml (1 warning)
$ echo $?
0

$ python3 ../../tools/acceptance_protocol.py check-states
PASS machine.amendment
PASS machine.contract
PASS machine.decision
PASS machine.package
PASS verdict_rule
PASS verdict_rule_exhaustive
$ echo $?
0

$ python3 ../../../format_acceptance/tools/check_core.py --strict --strict-weight acceptance.toml
PASS acceptance.toml [weighted: 5, unweighted: 1]
$ echo $?
0
```

(Re-run after a later fix: the worked example's own `record_hash` field is now
the typed `record:` wire — zero B16 warnings, where an earlier revision of this guide's evidence
showed 14/15 of them. `check_core.py` run directly now agrees EXACTLY with `check_acceptance.py`,
confirming the dispatch fix in §12.)

## 11. Migration checklist from pre-0.3 `acceptance/0` files

If you have an existing manifest from before this repo's 0.3 lock (2026-09-24):

1. **Add `[format].profile`.** Pre-0.3 had a compatibility default (a single named constant a
   manifest could omit the field and still resolve against); 0.3.0 REMOVED it (core.md B12). Add
   `profile = "acceptance/verification/code/rust"` explicitly — omission is now a named ERROR, not
   a silent default.
2. **Full commits everywhere.** `captured_at_commit` (B20) now requires the full 40 lowercase hex
   characters; a shorter form is an ERROR with no compatibility shim. Check every evidence record.
3. **Typed record hashes.** Re-emit every `record_hash` as `record:sha-512:<128-hex>` (§5); the old
   bare `sha-512:<hex>` form still parses (WARNING, 0.3.1 ruling B1-wording) but is tracked for
   retirement to ERROR at 0.4 — do not leave new writers emitting it.
4. **Re-vendor the FULL closure, not three files.** If you previously pinned
   `check_acceptance.py`/`acceptance_grammar.py`/`check_core.py` by hand, replace that with
   `export_closure.py`'s output (§1) — the three-file list was already stale before B20/B21 and the
   Rust binding's markdown admission documents (§12).
5. **Re-emit, never hand-edit.** Regenerate the whole package from your generator script after any
   of the above changes; do not patch individual fields in a committed `acceptance.toml` by hand
   (the worked example's own header: "GENERATED FILE — DO NOT HAND-EDIT").
6. **Contract profile id.** If an existing contract's `profiles_required` names the bare meaning
   (`acceptance/verification`), change it to the exact leaf (`acceptance/verification/code/rust`,
   0.3.1 ruling A1) or your package will be refused.
7. **`assurance_class`/`phase`, if you use them (0.3, §3.7).** A `final`-phase contract now requires
   EVERY requirement to be `firm` (0.3.1 ruling A4); a contract mixing `draft` requirements with
   `phase = "final"` is a hard error, not a note — move it to `crystallizing` or `exploratory` until
   every requirement is firm, or drop the draft ones.

## 12. Known limits in 0.3.x

**Known limits retained in 0.3.2** (deferred mechanisms, not features of this release):
claim-discharge mode (`discharged_by`, using a source verdict without named records); digest/
components freshness (freshness stays commit-only — a content-digest or components subject has no
`delivered-revision` freshness binding yet); multiple governing `[spec]` documents; `gap_reason`/
`spec_drift` claim fields; unregistered `when_kind` kinds (usable today only via `kind_registry`);
the fault-resolution protocol; the package-integrity leaf; signing/DSSE; retirement of the
conformance 0.1 legacy-field shim; retirement of the untyped legacy record wire (§5); the
`external_pilot` readiness level.

**Fixed since this guide was first written — a defect this guide originally reported, closed in a
0.3.1 tool fix, stated here for anyone reading an older copy of this guide:**

`check_acceptance.py` (and `acceptance_protocol.py check-package` for `acceptance/verification*`
profiles, whose package validator IS `check_acceptance.py`'s own `validate`) used to force
`bound_meaning = "verification"` and, in doing so, unconditionally discard the package's declared
BINDING suffix (`code/rust`) — so a `acceptance/verification/code/rust` package validated through
either documented entry point never ran the Rust binding's own extra checks (B20's
`required_build_inputs` guard, B9's cover-only over-claim guard). **`check_core.dispatch` now keeps
the declared binding suffix whenever the caller-forced meaning EQUALS the package's own declared
meaning** — the only case any `PROFILES[...]`-mediated protocol/format caller ever reaches, since
each such caller is keyed by, and forces `bound_meaning` to, the SAME meaning its own package
declares. Concretely: `check_acceptance.py --strict --strict-weight` and `check_core.py --strict
--strict-weight` now agree EXACTLY on a `code/rust` package (verified, §10) — there is no longer a
reason to run `check_core.py` as a separate "stricter" step; `check_acceptance.py` (and
`check-package`) already run the Rust binding's own checks. **A declared/bound meaning MISMATCH**
(reachable only by invoking a bound-meaning entry point directly on a manifest declaring a
DIFFERENT meaning — never through any `PROFILES[...]`-mediated call, so not a case an ordinary Kani
producer will hit) now returns **INDETERMINATE, exit 2**, naming both meanings and pointing at the
unbound `check_core.py` entry point, instead of an earlier round's silent, unqualified PASS under
the wrong meaning's rules.

**Still true, unaffected by the fix above:**

- **The Rust binding's kind-admission and `required_build_inputs` declarations live in a
  MACHINE-READABLE fenced TOML block inside a Markdown DOCUMENT**
  (`format_acceptance/profiles/bindings/code.md`, `code/rust.md`), not in the `.py` binding
  modules — `check_core.py`'s B14 check (`_binding_admitted_kinds`) `open()`s these `.md` files at
  runtime. A vendor closure built by hand-picking `.py`/`.toml` files by extension will miss them
  silently: `export_closure.py`'s own first draft did exactly this, and its smoke test caught it
  immediately (`[subject].kind` admission failed the moment the closure was validated with no
  access back to the source repo) — see `export_closure.py`'s own module docstring for the full
  account. This is why §1's exported closure includes two `.md` files alongside the `.py`/`.toml`
  ones; do not "clean up" a vendor list by dropping files that look like documentation.

## 13. Templates

[`templates/kani-crate.contract.toml`](templates/kani-crate.contract.toml) — a requester contract
skeleton: exact leaf (`acceptance/verification/code/rust`) in `profiles_required`, an
`assurance_class` example (`baseline/3`), `phase = "exploratory"` (so the low starter floors get
NOTEs, never ERRORs, per §3.7's maturity rule). Passes `check-contract` as shipped — verified
against 0.3.1. **Re-checked against A2 and A4 specifically:** A2 (0.3.1) dropped `acceptance/
conformance` from the class floor at levels 2 and 4 only — this template's `baseline/3` is
untouched by it, and the template names no conformance requirement anyway. A4 (0.3.1) requires
every requirement `firm` in a `final`-phase contract — this template's `phase = "exploratory"` with
both requirements `firmness = "draft"` sits outside A4's scope entirely (the maturity rule downgrades
a shortfall to a NOTE whenever the phase is not `final`, §3.7); tightening this template to
`phase = "final"` later means flipping both requirements to `firm` (or dropping `firmness`, whose
default is `firm`) first, per the migration checklist item 7 above.

[`templates/kani-crate.acceptance.toml`](templates/kani-crate.acceptance.toml) — a producer package
skeleton for a Kani-verified crate: one panic-freedom claim (`kani-harness`, band A1, no control
needed), one honestly-declared gap + deviation for the cross-cutting "unbounded" requirement.
Fails `check_acceptance.py --strict` AS SHIPPED, with clear, field-named errors pointing at every
`<FILL: ...>` marker (a placeholder in a commit/hash/record-pointer field cannot be made to pass —
that is deliberate; a silently-passing skeleton would be worse) — verified. Once every marker is
filled with real values (a real commit, a real evidence file, its real `record:` hash, a real
`artifact:` toolchain digest), it passes `check_acceptance.py --strict --strict-weight` cleanly —
verified by [`templates/selftest_templates.py`](templates/selftest_templates.py), which fills the
template mechanically (never by hand) and re-validates:

```sh
python3 protocol_acceptance/adoption/templates/selftest_templates.py
```

```
SELFTEST PASS: selftest_templates (4 controls: contract-as-shipped, package-skeleton-refuses-clearly, package-filled-passes, weighted-claim-needs-its-own-witness)
```

The fourth control (§4) proves the band-lift-control/weight-witness distinction mechanically: it
weights `K-001` with no witness (must FAIL, `WEIGHT REFUSED`) and then with a witness (must PASS).

For a complete, real, end-to-end chain (a real crate, real `cargo test`/`clippy`/`kani` transcripts,
real mutation controls, a consumer decision, a change-impact run), read
[`../examples/rust-delivery/README.md`](../examples/rust-delivery/README.md) start to finish — this
guide is the path IN; that README is the worked instance once you are there.
