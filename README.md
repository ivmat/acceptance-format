# Acceptance protocol + format

**Acceptance 0.3.2 — locked, not ratified.** The 0.3.x release records requirements,
evidence and a consumer's acceptance decision. Validation checks the records;
it does not certify the software or ratify the specification.

The format describes claims and their evidence. The protocol connects a consumer's
contract, a producer's package and a consumer's decision. Verification, conformance
and troubleshooting profiles add domain rules. Assurance classes set evidence floors.

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

1. **Contract** — as the *consumer*, you write what the code must do: the requirements,
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

**1. Contract.** Before writing it, you say what it must do and what evidence you will
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
meet the contract.

**3. Decision.** You re-run `python3 test_slug.py`, see the expected output, and record
*accepted*. If `slug()` changes later, that decision no longer applies until you check
again.

This is simplified: the real files also carry hashes, evidence records and tool versions.
The complete, working version is in [`examples/weighted-toy/`](examples/weighted-toy/).

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
python3 protocol_acceptance/tools/acceptance_protocol.py check-contract protocol_acceptance/examples/rust-delivery/acceptance-contract.toml
python3 protocol_acceptance/tools/acceptance_protocol.py check-package protocol_acceptance/examples/rust-delivery/acceptance.toml --contract protocol_acceptance/examples/rust-delivery/acceptance-contract.toml --root .
python3 protocol_acceptance/tools/acceptance_protocol.py check-decision protocol_acceptance/examples/rust-delivery/acceptance-decision.toml --contract protocol_acceptance/examples/rust-delivery/acceptance-contract.toml --package protocol_acceptance/examples/rust-delivery/acceptance.toml --root .
bash gates/run_all.sh
```

These commands check the supplied records. Reproducing the Rust evidence additionally
requires the Rust and Kani toolchains; see the example's README.

Read the [format](format_acceptance/spec/core.md),
[protocol](protocol_acceptance/spec/protocol.md),
[weighted-tier rules](format_acceptance/spec/0.1-DRAFT.md),
[worker-brief adapter](protocol_acceptance/spec/adapters/worker-brief.md),
[Kani adoption guide](protocol_acceptance/adoption/KANI-FV-ADOPTION.md),
[assumptions](ASSUMPTIONS.md) and [comparisons](WHY.md).

## Known limits

The Rust example ships as supplied, regenerated with typed `record:sha-512:` hashes; the
weighted toy is typed the same way. IB-001/IB-002 band-wording warnings are accepted known
limits if emitted; untyped legacy record-hash wire warnings remain only for the conformance
profile's fixtures, which are copied read-only teaching material and are not migrated. The
gate output records the warnings for this exact cut. See
[KNOWN-LIMITS.md](KNOWN-LIMITS.md) for the mechanisms deferred to 0.4, and
[ROADMAP.md](ROADMAP.md) for what 0.4 is planned (not final) to add.

`EXPORT-PROVENANCE.json` identifies the exact source commit, family version, dirty
state and SHA-256 of every exported file it lists; the two license files below are
repository-resident and are not themselves exported files, so they carry no provenance
entry. The source family version there is authoritative for later editorial 0.3.x exports.

Dual licensed under Apache-2.0 or MIT; see [LICENSE-APACHE](LICENSE-APACHE) and
[LICENSE-MIT](LICENSE-MIT). [LICENSE-NOTES.md](LICENSE-NOTES.md) records the license
rationale per material type.
