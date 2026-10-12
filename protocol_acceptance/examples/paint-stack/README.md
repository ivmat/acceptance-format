# Paint-stack: three crates, three consumer decisions

The accepted objects are the specification-bound edge packages. The intrinsic
`acceptance.toml` files describe each producer's claims and evidence; they are not
consumer acceptances. Library triples live under `<crate>/acceptance/<spec-id>/`;
paint-app's triple lives in `paint-app/`. The `store/ochre-accepted/` directory
contains decisions only.

| Crate | Producer | Accepted by (issuer) |
|---|---|---|
| geom-math | Ochre Geometry / maintainer | Ochre Raster / maintainer (`D_gm1`) |
| raster-draw | Ochre Raster / maintainer | Studio Ochre / tools-lead (`D_rd`) |
| paint-app | Ochre Paint / maintainer | Studio Ochre / tools-lead (`AD-PAINT-0001`) |

All parties are simulated. One author wrote the code, specifications, tests and
generators. Evidence independence is `none`. This example assumes internal,
low-consequence illustration work: a bad circle costs a redraw. Each consumer
uses `baseline/1` and re-executes every basis recipe.

The runtime inventory checks the Cargo workspace dependency closure. Paint-app
directly declares both raster-draw and geom-math; raster-draw also declares
geom-math. These are package dependencies:
`draw_circle` does not call the math primitives; the verification helper
`accuracy_ok` uses `geom_math::dist2`. Binding is declared as `build-time-copy`.
All three crates are released at one commit, in lockstep. A defect at the top
cannot be attributed to a layer by swapping versions.

Kani proves integer-square-root correctness and distance panic/overflow freedom
on the full integer domains. Distance arithmetic correctness has known-value
tests. Raster proofs cover octants up to radius 6; full circles have sampled
property tests. Paint geometry is checked independently on eight actual output
files, for circles fully inside the canvas. These bounds remain in the packages.

The frozen CLI output for `circle --cx 15 --cy 15 --r 10` is stored in
`paint-app/tests/fixtures/circle_cx15_cy15_r10.ppm.hex`: lowercase hex, 64 bytes
per line (128 hex characters), with a trailing newline. Tests decode it using
only the Rust standard library and compare the exact PPM bytes from both the
encoder and the compiled binary. The fixture preserves the original binary
output; normal generation never regenerates it.

From a clean, committed source checkout, generate the entire stack once:

```sh
python3 protocol_acceptance/examples/paint-stack/gen_stack.py
```

This runs Cargo tests, clippy, warning-fatal rustdoc, cargo-kani 0.67.0 and restored
mutation controls offline, then issues `D_gm1`, `D_rd` (pinning `D_gm1`), and
paint-app's decision (pinning both). Any failed run stops generation. Both `gen_stack.py` and `run_example.sh`
remove every `target/` directory under the example on success or failure. The geometry
decision expires after 30 days; the others after 180 days, allowing a separate
child-expiry control. Python 3.11+ and the Rust/Kani tools must be installed.

For a rehearsal without producing documents in the checkout:

```sh
python3 protocol_acceptance/examples/paint-stack/gen_stack.py --dry-run /tmp/paint-stack-rehearsal
```

The destination must not exist. A rehearsal uses the current generator sources
with Rust inputs read from HEAD, so pending source edits are not certified.

Check the generated stack from the repository root:

```sh
python3 protocol_acceptance/examples/paint-stack/selftest.py
```

This runs both strict format validators, all four protocol checks at every level,
then renders paint-app with its checked decision. It also checks missing-child,
changed-source and child-expiry failures, and every walkthrough failure stage.
The expected last lines are:

```text
stack accepted over inv-cargo for runtime at <issued_at>
not covered (trusted as the base, not checked): build-tool, language, platform, verification-tool
accepted by Ochre Raster / maintainer, Studio Ochre / tools-lead under their own specifications
raster-draw: declared binding: build-time-copy
geom-math: declared binding: build-time-copy
The label combines no assurance levels across the stack. Each element was accepted at its own floor; no failure bound for the whole stack follows.
```

The timestamp is the generated paint-app decision's `issued_at`. The label covers
runtime only. Toolchain and platform relations are trusted as the base and are
not checked; there is no manual tool inventory or toolchain boundary declaration.
Children are accepted under their issuers' own specifications.

To run the decision check and renderer directly, from this example's directory:

```sh
X=$(python3 -c 'import tomllib; print(tomllib.load(open("paint-app/acceptance-package.toml", "rb"))["subject"]["commit"])')
python3 ../../tools/acceptance_protocol.py check-decision paint-app/acceptance-decision.toml --spec paint-app/acceptance-specification.toml --package paint-app/acceptance-package.toml --root ../../.. --store ochre-accepted=store/ochre-accepted --tree "$X=../../.."
python3 ../../tools/acceptance_protocol.py render paint-app/acceptance-specification.toml paint-app/acceptance-package.toml paint-app/acceptance-decision.toml --root ../../.. --store ochre-accepted=store/ochre-accepted --tree "$X=../../.."
```

“Stack accepted” adds no assurance levels together and implies no failure bound
for the whole stack. With `--tree`, a checkout lacking the named commit (every clone of this repository)
is treated as a non-checkout; only the recorded digests are checked. Outside a checkout the same
limit applies: the presented bytes are not proven to be the commit's bytes.
