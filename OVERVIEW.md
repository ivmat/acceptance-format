# Overview: from requirements to acceptance

Acceptance joins a consumer's specification, a producer's claims and evidence,
and a consumer's decision. Content hashes bind the documents to each other and
to the declared subject. A weighted claim needs an honest grade and a rerunnable
check with a recorded failure witness; missing evidence remains an explicit gap.

This is the general walkthrough. Start with [weighted-toy](examples/weighted-toy/README.md)
to write a first manifest, or use the [documentation index](docs/README.md) to find
a rule or another example.

## A walk through one example: paint-stack

[`paint-stack`](protocol_acceptance/examples/paint-stack/README.md) is a tiny Rust workspace with three
crates, connected by package dependencies:

- `geom-math`: integer square root and squared distance;
- `raster-draw`: draws circles on a pixel canvas; its `accuracy_ok` verification helper uses `geom-math`;
- `paint-app`: a command-line tool, `paint circle`, that writes the circle to an image file. It declares
  both libraries as dependencies.

The parties are simulated and one author wrote everything; the example says so. It is small on purpose:
every step below is real and can be re-checked. The [example README](protocol_acceptance/examples/paint-stack/README.md) owns the commands, file layout and reproduction instructions.

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

## Where to go next

The [documentation index](docs/README.md) routes by task, including standards
conformance, troubleshooting, migration and the normative specifications.
[WHY.md](WHY.md) compares this approach with existing formats.

The tools check the records, not the world: they cannot establish that a recorded
failure happened or that the chosen requirements cover the real need. Declared
gaps are visible, but omitted requirements remain a review problem. The
[known limits](KNOWN-LIMITS.md) and [assumptions](ASSUMPTIONS.md) state the remaining
boundaries. The [roadmap](ROADMAP.md) describes planned work.
