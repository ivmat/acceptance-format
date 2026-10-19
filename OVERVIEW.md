# Overview: what acceptance covers, and what it does not

The [README](README.md) explains the idea in a few minutes. This page goes one level deeper. It walks
through one complete example, lists the other uses with the example to look at for each, and states
plainly what the format and protocol do and do not cover.

## The idea in one paragraph

For each thing the code must do, you keep one **claim** with its evidence, and you rate how strong that
evidence is. A claim only counts (it gets **weight**) if a recorded witness shows its check can fail, and
if the check can be re-run by anyone who has the code. Anything not checked stays in the file as an open
**gap**. On top of that
record, a **consumer** writes what it needs before the code exists (the **specification**), a
**producer** delivers the code with its record (the **package**), and the consumer records one
**decision**. The decision is bound by content hashes to the specification, the package and the declared
identity of the code, so changing any of them makes it stale.

## A walk through one example: paint-stack

[`paint-stack`](protocol_acceptance/examples/paint-stack/README.md) is a tiny Rust workspace with three
crates, connected by package dependencies:

- `geom-math`: integer square root and squared distance;
- `raster-draw`: draws circles on a pixel canvas; its `accuracy_ok` verification helper uses `geom-math`;
- `paint-app`: a command-line tool, `paint circle`, that writes the circle to an image file. It declares
  both libraries as dependencies.

The parties are simulated and one author wrote everything; the example says so. It is small on purpose:
every step below is real and can be re-checked.

### 1. The consumer writes the specification first

Before looking at any code, paint-app's consumer writes what it needs: four mandatory requirements and
one optional one.

| id | what it asks | evidence the consumer will accept |
|---|---|---|
| R1 | every ink pixel is within 0.5 pixels of the requested radius (for circles fully inside the canvas) | tier T3 or stronger, weighted, with a failure control |
| R2 | the drawn circle is symmetric | the same |
| R3 | the drawn circle is closed: one connected ring of pixels | the same |
| R4 | `paint circle` rejects every malformed command line without crashing | the same |
| R5 | the documentation builds with no warnings (optional) | tier T4, weighted; no separate control, but the weighted claim's failure witness is still required |

R1–R4 also require a re-run recipe, evidence for the delivered revision, a grade of at least `test-only`,
a band of at least A1, and passing dynamic evidence. R5 requires a recipe, delivered-revision freshness,
mechanical evidence, a grade of at least `mechanical` and a band of at least A0.

It also adds one **chain** requirement: every library paint-app is built with must itself be accepted, by
an acceptor this consumer trusts (step 5).

The consumer declares an **assurance class**, `baseline/1`, because the use is low-consequence: a wrong
circle costs a redraw. A higher class would demand stronger evidence, for example proofs and independent
review.

### 2. The producer records claims, with honest strength

Each crate's producer records one claim per requirement:

- **Tests** back paint-app's claims: integration tests run the real binary on eight requests and check
  every pixel of the written files with an independent geometry check. A byte-exact golden image is also
  compared.
- **Proofs** back `geom-math`: Kani (a model checker for Rust) proves the integer square root correct, and
  the distance computation free of panics and overflow, for every possible input.
- **Bounds are stated, not hidden.** `raster-draw`'s proofs cover each octant of circles up to radius 6.
  Whole circles, and larger ones, have sampled property tests only. The record says exactly that, and grades those claims accordingly.

Every claim names a command and the output that means "pass". Anyone who has the code can re-run it; for
an open-source library, that is everyone. The recorded run is kept with the claim.

### 3. Every weighted claim shows that its check can fail

For each weighted claim, the producer broke the code on purpose and recorded what failed. Examples: an
off-by-one in the square root's comparison, a distance computation that overflows on extreme inputs, an
inverted image colour mapping, holes punched in the drawn circle. All eleven controls in the example went
red, and the source was restored byte for byte afterwards. A claim without such a
witness keeps its place in the file, but it gets no weight and cannot meet a requirement that asks for
weight.

### 4. The consumer judges, and records one decision

The consumer re-runs every recipe its decision relies on and records the observed output. The tools
check that each requirement is met at the strength asked, and that the decision is bound by hash to the
exact specification and package and to the declared identity of the code. They also re-check the recorded
digests of the source files the claims rely on. The verdict is *accepted*. If the specification, the
package or a digested source file changes, the decision no longer applies until someone checks again.
With the source repository at hand, the tools also confirm those files match the named commit. In a copy
without that commit (any clone of this repository), only the recorded digests are checked: files without
a recorded digest are not covered, and the bytes are not proven to be the commit's.

### 5. Each library is accepted by whoever uses it, and the stack is checked

- `raster-draw`'s maintainers accept `geom-math` with their own specification and decision.
- paint-app's consumer accepts `raster-draw` the same way.
- paint-app's package lists every library it is built with. The checker verifies that list against
  `Cargo.lock` and the workspace manifests, every one of them pinned by digest.
- The chain requirement then demands a valid acceptance decision for every listed library, from a
  directory of decisions the consumer chose to trust.

The check is **recursive**: accepting paint-app re-checks that `raster-draw`'s own acceptance still
holds, including what *it* was built on.

### 6. What makes the acceptance fail

The example's own checks show each of these:

- **A library's decision is removed:** the app's check fails and names the library.
- **One byte of a library source file the claims rely on changes:** the recorded digest no longer matches,
  and the check fails, naming the library.
- **A library's acceptance expires:** the historical decision stays valid as a record. The **effect
  check**, which a gate runs before merging, publishing or deploying, refuses it and names the library.

### 7. What the result says, and what it does not

The renderer prints:

```text
stack accepted over inv-cargo for runtime at <time>
not covered (trusted as the base, not checked): build-tool, language, platform, verification-tool
```

- The label covers the **runtime libraries** only. The compiler, the verifier and the platform are named
  as trusted, not checked.
- Each library was accepted at its own strength. "Stack accepted" does **not** add those up into one
  guarantee for the whole app.

## Other uses, and where to look

| use | what you get | where to look |
|---|---|---|
| Checking your own code | each declared requirement is backed by a check with a recorded failure witness, or listed as an open gap; a claim without the witness gets no weight | [`examples/weighted-toy/`](examples/weighted-toy/README.md) |
| Accepting code written by an AI agent or a tool | you write the specification first; the agent fills the package; you re-run and decide | [`rust-delivery`](protocol_acceptance/examples/rust-delivery/README.md), paint-stack |
| Reporting formal verification honestly | proofs mapped to the requirements they support, with their bounds and the rules nothing checked | [`docs/CASE-STUDY.md`](docs/CASE-STUDY.md), paint-stack |
| Handing code to another team or organisation | a hash-bound specification, package and decision; a mandatory requirement not yet met is listed, not hidden | [`rust-delivery`](protocol_acceptance/examples/rust-delivery/README.md) (verdict: accepted with a condition) |
| Noticing when evidence goes stale | a change to the specification, the package or a digested source file makes the old decision stop applying, and lists what must be re-checked | `rust-delivery` (`impact-events.jsonl`) |
| Following a named standard | each clause in the declared inventory or slice of a standard is evidenced, marked not applicable or excluded with a reason, or left as an open gap | [conformance profile](format_acceptance/profiles/conformance/PROFILE.md) and its examples |
| Making failures diagnosable | classes of fault paired with the diagnostic outcome each must produce, with evidence for the scenarios exercised; the supplied examples use synthetic records | [troubleshooting profile](format_acceptance/profiles/troubleshooting/PROFILE.md) and its examples |
| Scaling evidence to how critical the code is | the consumer declares an assurance class; higher classes demand stronger evidence | [`assurance-classes.toml`](protocol_acceptance/spec/assurance-classes.toml) |
| Tightening requirements over time | start with loose floors, tighten them as the product matures; floors never loosen silently | [protocol](protocol_acceptance/spec/protocol.md) §3.5–§3.6 |
| Moving from an earlier release | specifications and packages are migrated; decisions are never rewritten | [`acceptance_migrate.py`](protocol_acceptance/tools/acceptance_migrate.py) |

The verification profile, which covers the cases above about code doing what it should, is the most
developed. The conformance and troubleshooting profiles are newer.

## What it covers

- What the code must do, written down before the code, by the party that needs it.
- One claim per requirement, with its evidence, its strength on a fixed scale from T1 (a machine-checked
  proof) down to T5 (a human or AI review), and its stated bounds.
- A witness for each weighted claim that its check can fail, and a command that anyone who has the code
  can re-run.
- Declared gaps, kept visible: the file cannot look stronger than its evidence.
- A consumer's decision, bound by hash to the specification, the package and the declared identity of the
  code, so it goes stale when they change. The recorded digests of the source files the claims rely on are
  re-checked; files without a recorded digest are not covered.
- Acceptance of the libraries a project is built with, checked recursively, for libraries inside one
  Cargo workspace.

## What it does not cover

- **It does not prove the software correct.** It records what was checked and how strongly. A check that
  verifies the wrong property passes like one that verifies the right one; choosing the right check is
  still a reviewer's job.
- **The tools check the records, not the world.** They cannot see whether the code was really broken for
  a failure witness. Anyone who has the code can reproduce the documented break and check that the
  command then fails; that does not authenticate the original run.
- **It does not write your requirements.** Listing what the code must do is still the hard part. Declared
  gaps stay visible, but the tools cannot discover a requirement nobody wrote down.
- **No payment, pricing, legal terms or business contracts.** Acceptance is between a producer and a
  consumer about an artefact. Those processes can cite an acceptance by its identifiers and hashes, from
  outside.
- **Not a replacement for SBOMs, build provenance or signing.** It records what was verified, and is
  designed to sit alongside those formats.
- **Stacking, today, has limits.** It covers libraries inside one Cargo workspace. If any dependency comes
  from crates.io or git, the whole stack check is undecided, never accepted. The toolchain and platform
  are trusted, not checked. The trusted directory of decisions is unsigned: write access to it is
  authority.
- **Not yet:** choosing which verification tools and reviewers a consumer accepts; tracing which accepted
  claims back one specific function call across several libraries; signing for exchanges between
  organisations. See [ROADMAP.md](ROADMAP.md).

## How it relates to other formats

Test reports, coverage, CI badges, SARIF, assurance cases, CycloneDX attestations, VEX, SBOMs, SLSA,
in-toto and cargo-vet each cover part of this ground. The ideas underneath are established: mutation
testing, claims backed by evidence, audited dependencies. What this format adds is the combination,
across checkable specification, package and decision documents, with one combined rendered view:

- weight only for a check with a recorded witness that it can fail;
- gaps that stay visible;
- requirements set by the consumer, before the code exists;
- a decision that goes stale when what it was bound to changes.

A format of our own also leaves us free to design it for every use case we care about, with no
external constraint. Where an existing format is adequate, we can still fall back to it, with
extensions if needed. [WHY.md](WHY.md) compares it with each of these formats in
turn.

## Status

Acceptance 0.4.0 is locked, not ratified. The tools are Python 3.11+, standard library only. The code
binding today is Rust; C, Python and Go are planned, and the core permits other kinds of artefact
(see [ROADMAP.md](ROADMAP.md)). Every example in this repository was produced by one author with simulated
parties. Ratification is a separate, later act. See [KNOWN-LIMITS.md](KNOWN-LIMITS.md) for the
current limits.
