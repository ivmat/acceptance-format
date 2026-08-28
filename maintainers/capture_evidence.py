#!/usr/bin/env python3
"""capture_evidence.py -- regenerate every evidence/*.txt transcript the root acceptance.toml
(this repo's own self-manifest) cites, at the current HEAD.

Writes each plain/mutation evidence/*.txt in the same wrapper shape the manifest's records expect:

    $ <command>
    [<MUTATION CONTROL description lines>]        # mutation records only
    (run at <ISO-Z>, from repo root, HEAD=<full-sha>[ + this one-line mutation, reverted immediately after])
    ---
    <verbatim stdout of the command>
    ---
    exit: <code>

Mutation records: the named one-line source edit is applied, the command re-run, and the file
restored to its exact original bytes (asserted). A mutation that fails to change the file, or a
mutation run that does not go RED, aborts -- a silent no-op would manufacture a false control.

evidence/self-reference-disclosure.txt is a fourth, DIFFERENT kind of record: it is not a command
transcript but a generated STATEMENT about the repo (the commit of record, each cited file's own
git-log-derived identity, the author list) -- so it is regenerated here too, at capture time, from
fresh git queries, rather than hand-edited. A hand-frozen copy of this file goes stale the moment
a later commit re-pins [subject].commit: the sha it names stops matching the manifest's own pins,
and nothing catches that drift because it is prose, not a record the validator diffs against
anything. Regenerating it alongside the other records is what keeps it honest.

Uses tools/m11.py as a LIBRARY (imported, not shelled out to its CLI) to print each freshly
written record's M11 digest immediately after writing it -- the same value
`repin_manifest.py` (run next) writes into `record_hash`, so a maintainer sees it without a
second command.

Repo-root relative throughout: run as `python3 maintainers/capture_evidence.py <repo-root>`
against a CLEAN checkout (uncommitted changes make `HEAD=<sha>` in the transcript a lie about
what was actually run). Pair with `maintainers/repin_manifest.py`, which edits acceptance.toml's
pins and record_hash values to match what this script just wrote -- see maintainers/README.md.

One-off tooling used to assemble this repository (2026-08-28), made repo-root relative and
self-contained.
"""
import subprocess
import sys
import os
import datetime
import pathlib

ROOT = pathlib.Path(sys.argv[1]).resolve()
os.chdir(ROOT)
SHA = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

sys.path.insert(0, str(ROOT / "tools"))
import m11  # noqa: E402  (path must be set up first)


def now_z():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd):
    """Run a shell command from repo root; return (combined_output, returncode). stderr is merged
    into stdout in emission order (stderr=STDOUT), matching the committed transcripts: most tools
    print to stdout, but check_acceptance.py prints its SELFTEST FAIL summary to stderr."""
    p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.stdout, p.returncode


def wrap(command, body, rc, mut_desc=None):
    if not body.endswith("\n"):
        body += "\n"
    head = ["$ " + command]
    if mut_desc:
        head += mut_desc
        head.append(f"(run at {now_z()}, from repo root, HEAD={SHA} + this one-line mutation, reverted immediately after)")
    else:
        head.append(f"(run at {now_z()}, from repo root, HEAD={SHA})")
    return "\n".join(head) + "\n---\n" + body + "---\nexit: " + str(rc) + "\n"


def write(relpath, text):
    (ROOT / relpath).write_text(text)
    digest = m11.digest_bytes("evidence-record", text.encode())
    print(f"  wrote {relpath} ({len(text)} bytes, rc-line: {text.splitlines()[-1]}, record_hash: {digest})")


# ---- plain records --------------------------------------------------------------------------
PLAIN = [
    ("evidence/step1-check-acceptance-selftest.txt",
     "python3 tools/check_acceptance.py --selftest", 0),
    ("evidence/step2-examples-validate.txt",
     "python3 tools/check_acceptance.py --strict --strict-weight examples/minimal.acceptance.toml examples/rs-verified-der/acceptance.toml", 0),
    ("evidence/step3-check-ledger-selftest.txt",
     "python3 tools/check_ledger.py --selftest", 0),
    ("evidence/step4-envelope-ledger-check.txt",
     "python3 tools/check_ledger.py --strict-weight examples/rs-verified-der/ENVELOPE.md", 0),
    ("evidence/step5-check-execute-selftest.txt",
     "python3 tools/check_execute.py --selftest", 0),
    ("evidence/step6-parity-selftest.txt",
     "python3 tools/check_parity_selftest.py --quiet", 0),
    ("evidence/step7-content-leak-scan.txt",
     "python3 gates/check_content_leaks.py", 0),
    ("evidence/step8-schema-drift-check.txt",
     "bash -c 'diff -q <(python3 tools/emit_schema.py) schema/acceptance-0.1.0-draft.schema.json && python3 tools/emit_schema.py --check examples/minimal.acceptance.toml examples/rs-verified-der/acceptance.toml'", 0),
]

# ---- mutation records: (relpath, command, target_file, old, new, line_anchor|None, desc_lines) ----
MUT = [
    ("evidence/step1-mutation-control-clause-source-check-disabled.txt",
     "python3 tools/check_acceptance.py --selftest",
     "tools/check_acceptance.py", "if cs is None:", "if cs is None and False:", None,
     ["MUTATION CONTROL: tools/check_acceptance.py's W2.3/P1 'clause_source not recorded' refusal",
      "(the 'if cs is None:' branch inside the weighted-claim checks) was disabled by",
      "changing it to 'if cs is None and False:', then the identical selftest command was re-run."]),
    ("evidence/step3-mutation-control-positive-control-check-disabled.txt",
     "python3 tools/check_ledger.py --selftest",
     "tools/check_ledger.py", 'if grade == "not-covered":', 'if False and grade == "not-covered":', 1266,
     ["MUTATION CONTROL: tools/check_ledger.py's core.md §4 positive_control-required-on-not-covered",
      "enforcement (the 'if grade == \"not-covered\":' guard around check_positive_control(...), line",
      "1266) was disabled by changing it to 'if False and grade == \"not-covered\":', then the",
      "identical selftest command was re-run. NOTE: this line NUMBER drifts as the file changes --",
      "re-locate it (`grep -n 'if grade == \"not-covered\":' tools/check_ledger.py`) before reusing",
      "this script; the assertion below fails loudly if the anchor is stale rather than mutating",
      "the wrong occurrence."]),
    ("evidence/step5-mutation-control-self-fulfilling-check-disabled.txt",
     "python3 tools/check_execute.py --selftest",
     "tools/check_execute.py", "return re.search(pat, c) is not None", "return False", None,
     ["MUTATION CONTROL: tools/check_execute.py's is_self_fulfilling() word-boundary echo detector",
      "('return re.search(pat, c) is not None', the SELF-FULFILLING-SUSPECT rule) was disabled by",
      "forcing it to 'return False', then the identical selftest command was re-run."]),
]


def apply_mutation(target, old, new, line_anchor):
    p = ROOT / target
    original = p.read_bytes()
    text = original.decode()
    if line_anchor is not None:
        lines = text.split("\n")
        idx = line_anchor - 1
        assert old in lines[idx], f"{target}: line {line_anchor} does not contain {old!r}: {lines[idx]!r}"
        lines[idx] = lines[idx].replace(old, new, 1)
        mutated = "\n".join(lines)
    else:
        assert text.count(old) == 1, f"{target}: expected exactly 1 occurrence of {old!r}, found {text.count(old)}"
        mutated = text.replace(old, new, 1)
    assert mutated != text, f"{target}: mutation was a no-op"
    p.write_bytes(mutated.encode())
    return original


def restore(target, original):
    p = ROOT / target
    p.write_bytes(original)
    assert p.read_bytes() == original, f"{target}: restore failed"


def _git_log1(paths):
    """git log -1 --format='%H %ad' --date=iso-strict -- <paths>, trimmed."""
    out, rc = run(f"git log -1 --format='%H %ad' --date=iso-strict -- {paths}")
    assert rc == 0, f"git log -1 -- {paths} failed (rc={rc}): {out}"
    return out.strip()


def _git_authors():
    out, rc = run("git log --format='%an' | sort -u")
    assert rc == 0, f"git log --format='%an' | sort -u failed (rc={rc}): {out}"
    return out.strip()


def generate_disclosure():
    """evidence/self-reference-disclosure.txt's content, freshly computed at capture time -- see
    the module docstring: this is a generated statement about the repo, not a frozen transcript."""
    row_check = _git_log1("tools/check_acceptance.py")
    row_toml = _git_log1("acceptance.toml")
    row_spec = _git_log1("spec/core.md spec/format.md")
    authors = _git_authors()
    return f"""self-reference disclosure — producer/verifier relationship
============================================================

Observable fact, checkable by any reader of this repo directly (git log/blame, no special
tooling): the manifest at the repo root, `acceptance.toml`, the spec it cites (spec/core.md,
spec/format.md), and the validator that checks it (tools/check_acceptance.py) all live in this
same repository, in the same tree, and were produced by the same author.

Commit of record for this certification (spec_sha = validator_sha = [subject].commit):
  {SHA}

git log -1 --format='%H %ad' --date=iso-strict -- <path>, at capture time:
  tools/check_acceptance.py  {row_check}
  acceptance.toml            {row_toml}
  spec/core.md spec/format.md {row_spec}

git log --format='%an' | sort -u  ->  {authors}

Author of both the validator and this manifest: {authors} (@ivmat). The producer of this
manifest and the verifier that decides its claims are therefore not independent parties. That is
recorded plainly here, not argued away.

The one-commit lag (format.md, "[format] self-location", self-certification convention). The
commit named above is the CLEAN commit at which every evidence transcript in this directory was
captured, and it is the commit whose spec and validator were read. It cannot be the commit that
contains this manifest, because a manifest cannot name a commit that already includes itself. The
manifest and these evidence records land in the immediately following commit, whose diff is
exactly that manifest-and-evidence update and nothing else. A reader who wants to check the lag
runs `git show --stat` on the commit that carries acceptance.toml and confirms it touches nothing
but acceptance.toml and evidence/.

Nothing in this file raises the producer/verifier relationship above what a reader can check for
themselves. Every claim in acceptance.toml carries a `self_verify.command` the reader re-executes
against their own checkout, and an `expect` stating what the run must show. That re-run — never
this file's own say-so about itself, and never the manifest's — is what the format's escape from
self-reference actually is.
"""


def main():
    dirty = subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout
    if dirty.strip():
        print("WARNING: working tree is not clean -- HEAD in every transcript will not describe "
              "what was actually captured. Commit or stash first.", file=sys.stderr)

    print(f"Capturing evidence at HEAD={SHA}")
    print("plain records:")
    for relpath, cmd, exp_rc in PLAIN:
        body, rc = run(cmd)
        assert rc == exp_rc, f"{relpath}: expected rc {exp_rc}, got {rc}\n{body}"
        write(relpath, wrap(cmd, body, rc))

    print("mutation-control records:")
    for relpath, cmd, target, old, new, anchor, desc in MUT:
        original = apply_mutation(target, old, new, anchor)
        try:
            body, rc = run(cmd)
        finally:
            restore(target, original)
        assert rc != 0, f"{relpath}: mutation did NOT go red (rc={rc}) -- control is vacuous\n{body}"
        st = subprocess.run(["git", "status", "--short", target], capture_output=True, text=True).stdout.strip()
        assert st == "", f"{relpath}: {target} not clean after restore: {st!r}"
        write(relpath, wrap(cmd, body, rc, mut_desc=desc))

    print("generated records:")
    write("evidence/self-reference-disclosure.txt", generate_disclosure())

    print("done. git status:")
    print(subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout)


if __name__ == "__main__":
    main()
