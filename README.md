# Acceptance protocol + format

**Acceptance 0.4.0 — locked, not ratified.** This release records specifications,
evidence and a consumer's acceptance decision, and can check acceptance across a stack of
libraries. Validation checks the records; it does not certify the software or ratify the
specification.

The format describes claims and their evidence. The protocol connects a consumer's
specification, a producer's package and a consumer's decision. Verification, conformance
and troubleshooting profiles add domain rules. Assurance classes set evidence floors.

For a longer overview, with one example walked through end to end, every use case, and what the
format does and does not cover, see [OVERVIEW.md](OVERVIEW.md).

For the theory behind it, see the paper [Acceptance as a Protocol for Delegated Work](docs/papers/acceptance/README.md)
(draft, not peer reviewed).

## What is this? (start here)

You wrote some code, or an AI agent wrote it for you. How do you know it is correct?
A green "tests pass" badge does not answer the questions that matter:

- What exactly must this code do?
- How well was each part checked: a few spot tests, or a proof for every input?
- What was not checked at all?
- Can I re-check it tomorrow, or after the next change, without trusting my memory?

The acceptance format and protocol make you write these answers down, next to the code,
in a form a tool can re-check. The main use is simple: **make sure your own code is
correct, and keep it that way.** The same records also work when the code goes to
someone else.

### The format: a checkable record of what the code does

The format is one file, `acceptance.toml`, that lives with the code. For each thing the
code must do, it holds one **claim** with:

- **what** the code must do, in one statement;
- **the evidence** — a test, a proof, a review — and how strong it is, on a fixed scale
  from T1 (a machine-checked proof) down to T5 (a human or AI review);
- **a command** anyone can re-run, and the output that means "pass";
- or an open **gap**, if nothing checks it yet.

### Why a green check is not enough: the check must be able to fail

A passing test proves something only if it would fail when the code is wrong. Many tests
would not. In one real case, a change that deleted a sort step broke no test at all, so a
claim resting on those tests would have looked verified. Code coverage has the same
problem: it shows which lines ran, not whether anything checked the result.

So the format backs a claim — it gives the claim **weight** — only when you show that the
check can fail:

1. Break the code on purpose (for example, delete the line that does the work).
2. Run the claim's command and watch it go red.
3. Record what you broke and what failed, then restore the code.

A weighted claim also needs an honest **grade**: does the evidence settle the claim for
every input, or only for some sample inputs or small sizes? A proof about 12-byte inputs
is not a proof about real-size inputs, and the grade says so.

A claim that misses any of this is not deleted. It stays in the file, marked
**unweighted**, which means "the format promises nothing here — the same as *it was
reviewed*". The file can never look stronger than its evidence.

The tools check that each record is complete and consistent. They cannot check that you
really broke the code; anyone can re-run the command to see for themselves. The tools also
do not grade how good the software is.

### The protocol: say what "correct" means before you build

The protocol splits the work into three documents. When you check your own code, you
write all three; you just wear a different hat for each:

1. **Specification** — as the *consumer*, you write what the code must do: the requirements,
   which ones are mandatory, and what evidence each one needs (for example: "at least T3,
   weighted, and shown able to fail"). Write it first, before the code, so the code cannot
   bend the target.
2. **Package** — as the *producer*, you deliver the code with its `acceptance.toml`. Each
   claim answers a requirement. Any mandatory requirement you did not meet is listed as a
   deviation, not hidden.
3. **Decision** — as the consumer again, you check the package, re-run the commands, and
   record one verdict: *accepted*, *accepted with conditions*, *evidence requested*, or
   *rejected*.

Each document is locked to the previous one by a content hash. If the requirements or the
code change, the old decision no longer applies, so you know you must check again.

### A tiny example

The code: a function that turns a title into a URL slug.

```python
def slug(s):
    """Lowercase s and replace each run of whitespace with '-'."""
    return re.sub(r"\s+", "-", s.strip().lower())
```

**1. Specification.** Before writing it, you say what it must do and what evidence you will
accept:

```toml
[[requirement]]
id        = "S-1"
statement = "slug(s) never returns an uppercase ASCII letter"
mandatory = true

  [requirement.evidence]
  min_tier          = "T3"   # tests are strong enough here
  weighted_required = true   # the check must be shown able to fail
```

**2. Package.** After writing it, you record the claim in `acceptance.toml`:

```toml
[[claim]]
id        = "WT-1"
clause    = "S-1"                  # answers requirement S-1
statement = "slug(s) never returns a string containing an uppercase ASCII letter"
weight    = "weighted"
grade     = "probe"                # honest: 5 sample inputs, not every string
bounds    = "bounded: 5 concrete input strings"

  [claim.self_verify]
  command = "python3 test_slug.py"         # anyone can re-run this
  expect  = "TEST-SLUG PASS: 5 cases"

    [claim.self_verify.watched_fail]       # proof that the check can fail
    of_command = "python3 test_slug.py"
    perturbed  = "removed .lower() from slug()"
    observed   = "TEST-SLUG FAILED: 2/5 cases"
    date       = "2026-08-28"
```

Delete the `watched_fail` part and the validator says `WEIGHT REFUSED … no watched-fail
witness`. The claim stays in the file, but it no longer counts as backed, so it does not
meet the specification.

**3. Decision.** You re-run `python3 test_slug.py`, see the expected output, and record
*accepted*. If `slug()` changes later, that decision no longer applies until you check
again.

This is simplified: the real files also carry hashes, evidence records and tool versions.
The complete, working version is in [`examples/weighted-toy/`](examples/weighted-toy/).

### Stacking: one library on another

Code rarely stands alone: an app calls a library, which calls another library. Acceptance stacks
the same way.

- Each library is accepted by whoever uses it, with its own specification, package and decision.
- The app's package lists every library it is built with, and the checker verifies that list
  against `Cargo.lock`.
- The app's specification can then require every one of those libraries to be accepted, by an
  acceptor the app's team trusts:

```toml
[[requirement]]
id = "runtime"
statement = "All dependencies are accepted or explicitly inside the declared boundary."
mandatory = true
waivable = false
domain = "correctness"
clause_source = "consumer-statement"
kind = "chain"

  [requirement.chain]
  relations = ["runtime"]
  depth = "all"
  level = "C2"                  # a valid acceptance decision, not just a listing
  completeness = "verified"     # the list must match Cargo.lock
  binds = "consumed"
  acceptors = ["ochre-accepted"]
  allow_conditions = false
  unaccepted = "refuse"
  max_elements = 500
```

The check is recursive. Accepting the app re-checks that each library's own acceptance still
holds, including what that library was built on: remove one library's decision or change a byte of any source file
its claims rely on (each is digested), and the app's check fails and names the library; let a library's
acceptance expire, and the app's effect check (`check-decision --effect --now <date>`) fails and names it.

Two honest limits. Each library is accepted at its own strength: "stack accepted" does not add
those up into one guarantee for the whole app. And today the checker follows libraries inside one
Cargo workspace; if any dependency in the closure comes from crates.io or git, the whole stack check
is undecided (indeterminate), never accepted.

The worked example is [`paint-stack/`](protocol_acceptance/examples/paint-stack/README.md):
`geom-math` ← `raster-draw` ← `paint-app`.

### When to use it

Use it when:

- you need to be sure your code is correct, not just that the tests pass;
- an AI agent or a tool writes code for you, and you must decide whether to trust it;
- a bug would be costly or hard to undo;
- you want the gaps to be visible, not discovered later;
- you hand code to another team or a customer, and they must decide whether to rely on it.

It is probably not worth it for throwaway scripts or quick prototypes.

### Two words you will meet

- **Profile** — what kind of acceptance is meant. *Verification*: does the code do what the
  requirements say? This is the main one today. *Conformance* (does it follow a named
  standard?) and *troubleshooting* (if it fails later, can the failure be diagnosed?) are
  newer and less developed.
- **Assurance class** — how critical the code is. A higher class demands stronger
  evidence.

For a larger delivery with all three documents, see the
[Rust example](protocol_acceptance/examples/rust-delivery/README.md).

## Quickstart

Python 3.11+ is required. From this tree's root, validate the supplied Rust example:

```sh
python3 format_acceptance/tools/check_acceptance.py --root . --strict --strict-weight protocol_acceptance/examples/rust-delivery/acceptance.toml
python3 protocol_acceptance/tools/acceptance_protocol.py check-spec protocol_acceptance/examples/rust-delivery/acceptance-specification.toml
python3 protocol_acceptance/tools/acceptance_protocol.py check-package protocol_acceptance/examples/rust-delivery/acceptance.toml --spec protocol_acceptance/examples/rust-delivery/acceptance-specification.toml --root .
python3 protocol_acceptance/tools/acceptance_protocol.py check-decision protocol_acceptance/examples/rust-delivery/acceptance-decision.toml --spec protocol_acceptance/examples/rust-delivery/acceptance-specification.toml --package protocol_acceptance/examples/rust-delivery/acceptance.toml --root .
bash gates/run_all.sh
```

These commands check the supplied records. Reproducing the Rust evidence additionally
requires the Rust and Kani toolchains; see the example's README.

Check and render the supplied library stack from the example's directory:

```sh
cd protocol_acceptance/examples/paint-stack
X=$(python3 -c 'import tomllib; print(tomllib.load(open("paint-app/acceptance-package.toml", "rb"))["subject"]["commit"])')
python3 ../../tools/acceptance_protocol.py check-decision paint-app/acceptance-decision.toml --spec paint-app/acceptance-specification.toml --package paint-app/acceptance-package.toml --root ../../.. --store ochre-accepted=store/ochre-accepted --tree "$X=../../.."
python3 ../../tools/acceptance_protocol.py render paint-app/acceptance-specification.toml paint-app/acceptance-package.toml paint-app/acceptance-decision.toml --root ../../.. --store ochre-accepted=store/ochre-accepted --tree "$X=../../.."
cd ../../..
```

In clones, the renderer prints this note before the stack table (`<commit>` is the
first twelve characters of the recorded subject commit):

```text
NOTE tree checkout: commit <commit> not present in this repository; recorded digests checked

| Relation | Inventories / completeness | Boundary | Gaps |
|---|---|---|---|
| build-tool | uncovered |  |  |
| language | uncovered |  |  |
| platform | uncovered |  |  |
| runtime | inv-cargo / verified |  |  |
| verification-tool | uncovered |  |  |
```

The renderer ends with these lines (`<issued_at>` is the paint-app decision's timestamp):

```text
stack accepted over inv-cargo for runtime at <issued_at>
not covered (trusted as the base, not checked): build-tool, language, platform, verification-tool
accepted by Ochre Raster / maintainer, Studio Ochre / tools-lead under their own specifications
raster-draw: declared binding: build-time-copy
geom-math: declared binding: build-time-copy
The label combines no assurance levels across the stack. Each element was accepted at its own floor; no failure bound for the whole stack follows.
```

The label covers runtime only. Toolchain and platform relations are trusted as the base
and are not checked. With `--tree`, a checkout lacking the named commit (every clone of this repository)
is treated as a non-checkout; only the recorded digests are checked. Outside a checkout the same
limit applies: the presented bytes are not proven to be the commit's bytes.

Read the [format](format_acceptance/spec/core.md),
[protocol](protocol_acceptance/spec/protocol.md),
[weighted-tier rules](format_acceptance/spec/0.1-DRAFT.md),
[worker-brief adapter](protocol_acceptance/spec/adapters/worker-brief.md),
[Kani adoption guide](protocol_acceptance/adoption/KANI-FV-ADOPTION.md),
[assumptions](ASSUMPTIONS.md) and [comparisons](WHY.md).

## Known limits

The Rust examples are regenerated at 0.4.0. Rechecking the records does not rerun the
Rust or Kani tools. The weighted toy retains its historical evidence with updated bindings.
For `--tree`, a checkout lacking the named commit (every clone of this repository) is treated as a
non-checkout; only the recorded digests are checked.

The 0.4.0 checker refuses 0.3 protocol documents. Use
[tag v0.3.2](https://github.com/ivmat/acceptance-format/tree/v0.3.2) to check them, or use
[the migration tool](protocol_acceptance/tools/acceptance_migrate.py):
`python3 protocol_acceptance/tools/acceptance_migrate.py migrate SPEC_OR_PACKAGE...`
previews the changes; `--write` applies them. Decisions are never rewritten: the consumer
must re-issue them. See [KNOWN-LIMITS.md](KNOWN-LIMITS.md) for current limits and
[ROADMAP.md](ROADMAP.md) for planned work.

`EXPORT-PROVENANCE.json` identifies the exact source commit, family version, dirty
state and SHA-256 of every exported file it lists; the two license files below are
repository-resident and are not themselves exported files, so they carry no provenance
entry. The source family version there is authoritative for later editorial exports.

Dual licensed under Apache-2.0 or MIT; see [LICENSE-APACHE](LICENSE-APACHE) and
[LICENSE-MIT](LICENSE-MIT). The paper under `docs/papers/` is the one exception: it is licensed
under CC BY 4.0. [LICENSE-NOTES.md](LICENSE-NOTES.md) records the license rationale per material type.
