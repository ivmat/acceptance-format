# weighted-toy — start here to write a weighted manifest

`acceptance.toml` in this directory is a genuine, non-illustrative **certificate**
(`illustrative = false`) for the two files beside it — `slug.py` (the subject) and `test_slug.py`
(the real, runnable evidence). It validates `--strict --strict-weight` and its recipe actually
runs (`check_execute.py`, below). Copy this directory's `acceptance.toml` as your starting point,
not `format_acceptance/examples/minimal.acceptance.toml` (that one is `illustrative = true` and
deliberately omits every field a real certificate needs).

## The subject

`slug.py::slug(s)` lowercases `s` and replaces each run of whitespace with a hyphen — about 20
lines, on purpose. `SPEC.md` states the one property the manifest certifies (`S-1`). `test_slug.py`
checks it against 5 concrete cases and prints a `PASS`/`FAIL` line.

## Field-by-field, mapped to what a first-time author needs

| field | value here | why |
|---|---|---|
| `[format].illustrative` | `false` | THE point — a certificate, not a fixture (a manifest-level convention marking a real certificate, not a numbered class rule) |
| `[spec].axis` | "the properties SPEC.md documents for ... slug()" | REQUIRED once any claim claims weight (`coverage-ledger.md` §1) |
| `clause_source` | `"spec-document"` | points at `SPEC.md`'s `S-1`, not at the test's own name (`coverage-ledger.md` §6 forbids `test-name`/`none` on a weighted claim) |
| `band` | `"A0"` | honest floor for a plain unit test with no mutation-control block — see the comment on the claim for what would earn A1 |
| `grade` | `"probe"` | bounded, fixture-shaped evidence (5 concrete cases, not the full string domain) — REQUIRES `self_verify` + `bounds` + `watched_fail` (`coverage-ledger.md` §§2–3) |
| `bounds` | `"bounded: ..."` | both the claim-level and the evidence-level `bounds` fields are required on `probe`; the per-grade `bounds` requirement is owned by the verification profile (`format.md`'s evidence-record schema, `evidence-types.md`) |
| `[claim.self_verify]` | `command` + `expect` | the deciding recipe: run it yourself |
| `[claim.self_verify.watched_fail]` | genuinely performed | see below — this is not invented prose |
| `record_hash` | a real typed `record:` digest | computed with `format_acceptance/tools/hashdomains.py`'s own `digest("record:", ...)` over `examples/weighted-toy/evidence/test-slug-run.txt`'s bytes — never the untyped legacy `evidence-record:`/bare wire (`format_acceptance/spec/hash-domains.md`'s "Read-only legacy record wires"), which is accepted read-only with a WARNING but MUST NOT be emitted by producers |

## The watched-fail control was genuinely performed

`coverage-ledger.md` §3: *"A weighted recipe must carry a witness that it has been watched to
fail."* This was done for real, not written from imagination: `slug.py`'s `.lower()` call was removed, `test_slug.py` was
re-run and 2 of the 5 cases genuinely failed (the two containing an uppercase letter — the other 3
correctly did not, since they had no uppercase letters to catch), the failure text was copied
verbatim into `[claim.self_verify.watched_fail].observed`, and the file was restored and re-verified
clean (`git status --short` empty, the test passing again) before this manifest was written.

## Reproduce it yourself

```sh
# from the repo root
python3 format_acceptance/tools/check_acceptance.py --strict --strict-weight examples/weighted-toy/acceptance.toml
python3 format_acceptance/tools/check_execute.py --yes-run-untrusted-commands \
  --subject-root examples/weighted-toy examples/weighted-toy/acceptance.toml
```

Both must PASS / `EXECUTED-PASS`; `gates/run_all.sh` runs both as part of the gate suite.

## Why the command is `python3 test_slug.py`, not `python3 examples/weighted-toy/test_slug.py`

The recorded recipe writes its command relative to the subject root. A real subject is usually its
own self-contained tree (a crate, a script, a toy like this one) with its own root, and
`check_execute.py --subject-root <path>` runs each `self_verify.command` from *that* root — so a
real certificate's commands are subject-root-relative, the way `cargo kani ...` in a crate's own
manifest would be. `test_slug.py` is still directly runnable as
`python3 examples/weighted-toy/test_slug.py` from the repo root; only the manifest's own recorded
command differs.
