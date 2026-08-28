#!/usr/bin/env python3
"""check_execute.py — P9: actually RUN each claim's `self_verify.command` and compare the
real output against its declared `expect`.

Pure python3 stdlib, no dependencies.

WHY THIS EXISTS
---------------
Every other checker in this repo verifies that the producer TYPED the required strings. None of
them verifies that the strings correspond to anything. A cold reader of the public repo earned a
weighted `contract` row with `command = "true"`; the row named a command, declared an expected
output, and passed every static rule. This mode NARROWS that gap -- it does not close it, and the
next section says exactly where it stops.

WHAT IT DOES NOT DO
-------------------
It does not judge whether the command is the RIGHT command for the claim (that is review), and it
does not make a green run mean the claim is true (`expect` is what green means, and `expect` is
producer-supplied). It answers one question: **does the recipe, run today, do what the row says it
does?** A row whose command does not exist, does not run, or does not produce its own declared
output is not a deciding recipe, whatever else is true of it.

**EXECUTED-PASS means "the command ran and produced the expectation". It does NOT mean the command
is a genuine oracle**, and no execution mode can make it mean that: `printf 'CLAIM VERIFIED'` runs,
exits 0, and prints exactly what the row declared. That degenerate case is refused by name
(SELF-FULFILLING-SUSPECT) because it is mechanically visible, but the general case is not -- a
command that greps its own fixture, or asserts something no implementation could violate, passes
here and is caught only by a reviewer reading the recipe. That residual is permanent and is stated
in core.md §8.2 rather than papered over.

TRUST BOUNDARY — READ THIS
--------------------------
**This mode executes commands taken from a document.** A manifest is producer-supplied data, and
`self_verify.command` is an arbitrary shell string inside it. Running one is equivalent to running
a script someone sent you. Consequences, all deliberate:

  * OFF BY DEFAULT. Nothing in `gates/run_all.sh` runs this mode; a repo that wants it enables it
    for its own manifests, whose provenance it knows.
  * It REFUSES to run at all without an explicit `--yes-run-untrusted-commands` flag, so it cannot
    be enabled by accident in a script that passes through unknown flags.
  * Every command is echoed before it runs.
  * Commands run with a timeout, in the subject root, with a scrubbed-ish environment.

There is no sandbox here and this file must not pretend otherwise. Do not point it at a manifest
you did not write or review.

Usage:
    python3 tools/check_execute.py --yes-run-untrusted-commands \\
        --subject-root <path> [--timeout 300] [--only <claim-id>] <manifest.toml>
    python3 tools/check_execute.py --selftest
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m11  # noqa: E402 — the shared M11 content-hash helper (spec/format.md, ratified 2026-08-28)

# Per-row outcomes. Named so a reader cannot confuse "we ran it and it worked" with
# "we did not run it", which is the failure mode of every summary line that counts only passes.
EXECUTED_PASS = "EXECUTED-PASS"
EXECUTED_FAIL = "EXECUTED-FAIL"
EXPECT_MISMATCH = "EXPECT-MISMATCH"
NOT_RUN = "NOT-RUN"
# A row whose declared `expect` appears verbatim inside its own command text. The command cannot
# fail to produce it, so the row's "what green means" is satisfied by the row's own typing:
# `command = "printf 'CLAIM VERIFIED'"` with `expect = "CLAIM VERIFIED"` reported EXECUTED-PASS.
# Kept as a DISTINCT outcome rather than folded into EXPECT-MISMATCH, for the same reason
# EXPECT-MISMATCH is distinct from EXECUTED-FAIL: it is a different defect and demands a
# different action (rewrite the recipe, not fix the tool).
SELF_FULFILLING = "SELF-FULFILLING-SUSPECT"

STATES = (EXECUTED_PASS, EXECUTED_FAIL, EXPECT_MISMATCH, SELF_FULFILLING, NOT_RUN)

# Which stream `expect` is matched against. STDOUT by default (tightened 2026-08-25): matching a
# combined stdout+stderr made every warning, progress line and backtrace a place for the expected
# string to appear, and a command that printed its expectation only on stderr passed.
EXPECT_STREAMS = ("stdout", "stderr", "combined")
DEFAULT_EXPECT_STREAM = "stdout"

DEFAULT_TIMEOUT = 300


@dataclass
class RowOutcome:
    claim_id: str
    state: str
    detail: str = ""
    command: str = ""
    exit_code: int | None = None


@dataclass
class Report:
    path: str
    outcomes: list[RowOutcome] = field(default_factory=list)
    # A declared hash that does NOT match is a detected falsehood, not an absence, and it exits
    # nonzero. A record with no declared hash is an absence and is reported only (P9b, proposed
    # and not adopted). The two used to share one list and neither affected the exit code.
    hash_errors: list[str] = field(default_factory=list)
    hash_notes: list[str] = field(default_factory=list)
    # `--only` naming a claim id no claim in the file carries. A SELECTION failure, not a row
    # outcome: there is no row to attribute it to, and the run decided nothing at all. Kept in its
    # own list so `ok()` can fail on it without inventing a fake RowOutcome (2026-08-28).
    selection_errors: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in STATES}
        for o in self.outcomes:
            out[o.state] = out.get(o.state, 0) + 1
        return out

    def ok(self, require_run: bool = False) -> bool:
        c = self.counts()
        if c[EXECUTED_FAIL] or c[EXPECT_MISMATCH] or c[SELF_FULFILLING]:
            return False
        if self.hash_errors:
            return False
        if self.selection_errors:
            return False
        if require_run and c[NOT_RUN]:
            return False
        return True


# ---------------------------------------------------------------------------
# expect matching
# ---------------------------------------------------------------------------


def is_self_fulfilling(expect: str, command: str) -> bool:
    """Does the row's declared `expect` appear verbatim inside its own command text?

    Then the command cannot fail to produce it and `expect` has stopped being an oracle: the
    producer typed the answer into the question. `printf 'CLAIM VERIFIED'` / `expect = "CLAIM
    VERIFIED"` reported EXECUTED-PASS until 2026-08-25.

    Matched on WORD BOUNDARIES, not as a bare substring: `expect = "ok"` against
    `command = "cat okay.txt"` is a coincidence of spelling, and accusing a row of self-fulfilment
    because a filename contains the letters is a false alarm on an honest recipe. A rule that
    cries wolf gets switched off, which costs more than the case it catches.

    Deliberately narrow, and it must be read as narrow: this catches the string being echoed
    BY the command's own text. A command that reads its expectation out of a fixture it also
    wrote, or asserts something no implementation could violate, is equally self-fulfilling and
    is invisible here. See the module docstring."""
    e = " ".join(expect.split())
    c = " ".join(command.split())
    if not e:
        return False
    pat = re.escape(e)
    if e[0].isalnum() or e[0] == "_":
        pat = r"\b" + pat
    if e[-1].isalnum() or e[-1] == "_":
        pat = pat + r"\b"
    return re.search(pat, c) is not None


def expect_matches(expect: str, output: str) -> bool:
    """`expect` is matched as a LITERAL substring of the selected stream, whitespace-collapsed.

    Deliberately dumb. Anything cleverer (regex inference, fuzzy matching, splitting on "and")
    would silently decide what a producer meant, and a matcher that guesses is a matcher that
    passes things it should not.

    The honest consequence: this makes `expect` a machine-checkable string, which is a stronger
    requirement than the prose many rows carry today ("VERIFICATION: SUCCESSFUL, and both
    kani::cover lines satisfied" is two facts and an English conjunction). That change belongs to
    the spec, not to this tool -- see the EXPECT-MISMATCH state, which is reported SEPARATELY from
    EXECUTED-FAIL for exactly this reason: a mismatch today is as likely to be a prose `expect` as
    a broken recipe, and collapsing the two would misreport the first as the second.
    """
    norm_out = " ".join(output.split())
    norm_exp = " ".join(expect.split())
    return norm_exp in norm_out


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------


def run_command(command: str, cwd: Path, timeout: int) -> tuple[int | None, str, str]:
    """Returns (exit_code, stdout, stderr). exit_code None means the command timed out.

    The two streams are kept APART (2026-08-25). Returning them concatenated meant `expect` was
    matched against warnings, progress output and backtraces as readily as against a result, and
    a command that printed its expectation only on stderr passed."""
    env = dict(os.environ)
    env["ACCEPTANCE_EXECUTE"] = "1"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None, "", f"<timed out after {timeout}s>"
    except OSError as e:
        return None, "", f"<could not execute: {e}>"
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


def check_record_hash(claim_id: str, idx: int, ev: dict,
                      subject_root: Path) -> tuple[bool, str] | None:
    """P9 second half -- RECORD BINDING. An evidence record points at a file; nothing today ties
    that pointer to the bytes the run actually produced, so a record can be regenerated, edited or
    truncated and every checker stays green.

    Returns (is_error, message), or None when there is nothing to say.

    `record_hash` (M11, format.md "Content-hashing (M11)", ratified 2026-08-28 -- self-describing
    "sha-512:<128-hex>", the evidence-record-domain content-hash of the file `record` points at),
    when present, is checked, and a MISMATCH is an error that exits nonzero: a present-but-wrong
    hash is a detected falsehood, not an absence, and reporting it at exit 0 was the same
    "vouching by silence" the format forbids everywhere else. When the hash is ABSENT on this
    claim's evidence it is reported and NOT failed here -- `check_acceptance.py` is what enforces
    P9's REQUIRED-on-weighted obligation at manifest-validation time; this mode's job is narrower
    (does the recipe run) and does not re-derive weight status from a bare `ev` dict."""
    ref = ev.get("record")
    if not isinstance(ref, str) or not ref:
        return None
    declared = ev.get("record_hash")
    p = (subject_root / ref) if not os.path.isabs(ref) else Path(ref)
    if declared is None:
        return (False,
                f"claim {claim_id!r} evidence[{idx}]: record {ref!r} declares no 'record_hash' — "
                f"nothing binds this row to the bytes its run produced (evidence-types.md, P9)")
    if not m11.is_well_formed(declared):
        return (True,
                f"claim {claim_id!r} evidence[{idx}]: record {ref!r} declares a record_hash that "
                f"is not the self-describing form 'sha-512:<128-hex>': {declared!r}")
    if not p.is_file():
        return (True,
                f"claim {claim_id!r} evidence[{idx}]: record {ref!r} declares a record_hash but "
                f"the file does not exist")
    actual = m11.digest_file("evidence-record", p)
    if actual != declared:
        return (True,
                f"claim {claim_id!r} evidence[{idx}]: record {ref!r} record_hash MISMATCH — "
                f"declared {declared[:24]}…, actual {actual[:24]}… (the record changed after it "
                f"was cited)")
    return None


def execute_manifest(path: Path, subject_root: Path, timeout: int,
                     only: str | None = None, echo: bool = True) -> Report:
    rep = Report(path=str(path))
    doc = tomllib.loads(path.read_bytes().decode("utf-8"))
    claims = doc.get("claim") or []
    if not isinstance(claims, list):
        return rep
    n_selected = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        cid = str(claim.get("id", "<no id>"))
        if only and cid != only:
            continue
        n_selected += 1
        for idx, ev in enumerate(claim.get("evidence") or []):
            if isinstance(ev, dict):
                note = check_record_hash(cid, idx, ev, subject_root)
                if note:
                    is_error, msg = note
                    (rep.hash_errors if is_error else rep.hash_notes).append(msg)
        sv = claim.get("self_verify")
        if not isinstance(sv, dict) or not isinstance(sv.get("command"), str) \
                or not sv["command"].strip():
            rep.outcomes.append(RowOutcome(cid, NOT_RUN, "no self_verify.command"))
            continue
        command = sv["command"]
        expect = sv.get("expect")

        stream = sv.get("expect_stream", DEFAULT_EXPECT_STREAM)
        if stream not in EXPECT_STREAMS:
            rep.outcomes.append(RowOutcome(
                cid, EXECUTED_FAIL,
                f"self_verify.expect_stream must be one of {list(EXPECT_STREAMS)}, got "
                f"{stream!r}", command, None))
            continue

        # Refused BEFORE running: the run would tell us nothing. The row declared an expectation
        # its own command spells out, so `expect` is not an oracle for this row at all.
        if isinstance(expect, str) and is_self_fulfilling(expect, command):
            rep.outcomes.append(RowOutcome(
                cid, SELF_FULFILLING,
                f"the declared expect {expect!r} appears verbatim inside the command text — the "
                f"command cannot fail to produce it, so running it decides nothing",
                command, None))
            continue

        if echo:
            print(f"  [{cid}] $ {command}")
        code, out, err = run_command(command, subject_root, timeout)
        if code is None:
            rep.outcomes.append(RowOutcome(cid, EXECUTED_FAIL, out + err, command, None))
            continue
        if code != 0:
            rep.outcomes.append(RowOutcome(
                cid, EXECUTED_FAIL, f"exit {code}", command, code))
            continue
        if not isinstance(expect, str) or not expect.strip():
            rep.outcomes.append(RowOutcome(
                cid, EXPECT_MISMATCH, "command succeeded but the row declares no 'expect' — "
                "exit 0 is not what green means", command, code))
            continue
        selected = {"stdout": out, "stderr": err, "combined": out + err}[stream]
        if expect_matches(expect, selected):
            rep.outcomes.append(RowOutcome(cid, EXECUTED_PASS, "", command, code))
        else:
            detail = (f"exit 0, but the declared expect was not found on {stream}: {expect!r}")
            if stream == "stdout" and expect_matches(expect, err):
                # Say WHERE it was found. Otherwise the fix looks like "the recipe is broken"
                # when it is "declare expect_stream".
                detail += (" — it WAS found on stderr; `expect` is matched against stdout unless "
                           "the row declares expect_stream = \"stderr\" or \"combined\"")
            rep.outcomes.append(RowOutcome(cid, EXPECT_MISMATCH, detail, command, code))

    # `--only` that selected NOTHING is a hard error, not a green run (2026-08-28 soundness fix).
    # A mistyped claim id used to skip every row silently and exit 0 -- with `--require-run` too,
    # because an empty outcome set has no NOT-RUN rows to count. That is the vacuous green this
    # format exists to refuse: a gate wired to `--only C-typo` reported success for a claim that
    # was never looked at. Zero matches fails, and the message names the id that matched nothing.
    if only and n_selected == 0:
        available = sorted(
            str(c.get("id", "<no id>")) for c in claims if isinstance(c, dict)
        )
        rep.selection_errors.append(
            f"--only {only!r} matched NO claim in this manifest — nothing was executed, so this "
            f"run decided nothing (available claim ids: {available})"
        )
    return rep


def print_report(rep: Report, require_run: bool = False) -> None:
    for o in rep.outcomes:
        line = f"{rep.path}:{o.claim_id}: {o.state}"
        if o.detail:
            line += f": {o.detail}"
        print(line)
    for n in rep.selection_errors:
        print(f"{rep.path}: SELECTION ERROR: {n}")
    for n in rep.hash_errors:
        print(f"{rep.path}: RECORD-BINDING ERROR: {n}")
    for n in rep.hash_notes:
        print(f"{rep.path}: RECORD-BINDING: {n}")
    c = rep.counts()
    print(f"check_execute: {len(rep.outcomes)} rows — "
          f"{c[EXECUTED_PASS]} executed-pass, {c[EXECUTED_FAIL]} executed-fail, "
          f"{c[EXPECT_MISMATCH]} expect-mismatch, {c[SELF_FULFILLING]} self-fulfilling-suspect, "
          f"{c[NOT_RUN]} not-run"
          + (f"; {len(rep.hash_errors)} record-binding error(s)" if rep.hash_errors else "")
          + (f"; {len(rep.selection_errors)} selection error(s)" if rep.selection_errors else ""))
    if c[NOT_RUN]:
        # NOT-RUN is an ABSENCE, and by default it is reported rather than failed -- a manifest
        # legitimately carries unweighted rows with no recipe. `--require-run` is how a gate says
        # "every selected row must actually have executed", which is the only reading under which
        # a green run means anything about the whole file.
        level = "ERROR" if require_run else "note"
        print(f"{rep.path}: {level}: {c[NOT_RUN]} row(s) NOT-RUN — a row that did not run is not "
              f"evidence that it would pass"
              + ("" if require_run else " (pass --require-run to make this an error)"))


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

_MANIFEST_HEAD = '''[format]
id = "acceptance/0"

[subject]
name   = "selftest"
kind   = "tool"
commit = "0000000000000000000000000000000000000000"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v0"
axis    = "the selftest's own rows"

[coverage]
clauses_total = 3
claims_total  = 3
'''


def _claim(cid: str, command: str, expect: str | None) -> str:
    out = f'''
[[claim]]
id        = "{cid}"
clause    = "S-1"
item      = "x"
statement = "s"
band      = "A0"
status    = "evidenced"
grade     = "test-only"

  [claim.self_verify]
  command = "{command}"
'''
    if expect is not None:
        out += f'  expect  = "{expect}"\n'
    return out


def selftest() -> int:
    failures: list[str] = []
    cases = 0

    # NOTE (2026-08-25): these fixtures used to run `printf '<the expect string>'`, which the
    # SELF-FULFILLING-SUSPECT rule now refuses -- correctly, and it refused them the moment the
    # rule landed. They read their output from a file instead, so the command text does not
    # contain the string being matched. That the old fixtures tripped the new rule is the rule
    # working: they were the same shape as the review probe.
    manifest = _MANIFEST_HEAD \
        + _claim("OK-1", "cat green.txt", "VERIFICATION SUCCESSFUL") \
        + _claim("FAIL-1", "exit 3", "never reached") \
        + _claim("MISMATCH-1", "cat other.txt", "VERIFICATION SUCCESSFUL")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "green.txt").write_text("VERIFICATION SUCCESSFUL\n")
        (root / "other.txt").write_text("something else entirely\n")
        (root / "allgreen.txt").write_text("ALL GREEN\n")
        (root / "okay.txt").write_text("ok\n")
        mpath = root / "acceptance.toml"
        mpath.write_text(manifest)
        rep = execute_manifest(mpath, root, timeout=30, echo=False)
        got = {o.claim_id: o.state for o in rep.outcomes}

        expected = {
            "OK-1": EXECUTED_PASS,
            "FAIL-1": EXECUTED_FAIL,
            "MISMATCH-1": EXPECT_MISMATCH,
        }
        for cid, want in expected.items():
            cases += 1
            if got.get(cid) != want:
                failures.append(f"{cid}: expected {want}, got {got.get(cid)}")
                print(f"SELFTEST FAIL: {cid} expected {want}, got {got.get(cid)}")
            else:
                print(f"SELFTEST PASS: {cid} -> {want}")

        # A row that names a command and NO expect must not pass on exit 0 alone: "which
        # command" does not determine "what green means" (core.md §3 rule 2).
        cases += 1
        m2 = root / "no_expect.toml"
        m2.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                      .replace("clauses_total = 3", "clauses_total = 1")
                      + _claim("NOEXPECT-1", "true", None))
        rep2 = execute_manifest(m2, root, timeout=30, echo=False)
        if rep2.outcomes[0].state != EXPECT_MISMATCH:
            failures.append("NOEXPECT-1: exit 0 with no expect must not be a pass")
            print("SELFTEST FAIL: NOEXPECT-1")
        else:
            print("SELFTEST PASS: NOEXPECT-1 -> exit 0 alone is not a pass")

        # The cold-reader cheat, watched red: `command = "true"` is the canonical way to earn a
        # weighted row from a static checker. Under --execute it runs, exits 0, and is caught by
        # its own declared expect.
        cases += 1
        m3 = root / "cheat.toml"
        m3.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                      .replace("clauses_total = 3", "clauses_total = 1")
                      + _claim("CHEAT-1", "true", "all 203 harnesses verified"))
        rep3 = execute_manifest(m3, root, timeout=30, echo=False)
        if rep3.outcomes[0].state != EXPECT_MISMATCH:
            failures.append("CHEAT-1: `command = true` must not pass its own expect")
            print("SELFTEST FAIL: CHEAT-1")
        else:
            print("SELFTEST PASS: CHEAT-1 -> `true` cannot produce its own declared output")

        # Record binding: a declared hash that does not match the file is caught; an absent one
        # is reported, not failed.
        cases += 1
        eff = root / "evidence.log"
        eff.write_text("real output\n")
        good = m11.digest_file("evidence-record", eff)
        note_bad = check_record_hash("C", 0, {"record": "evidence.log",
                                              "record_hash": "sha-512:" + "0" * 128}, root)
        note_good = check_record_hash("C", 0, {"record": "evidence.log",
                                               "record_hash": good}, root)
        note_absent = check_record_hash("C", 0, {"record": "evidence.log"}, root)
        if not (note_bad and note_bad[0] and "MISMATCH" in note_bad[1]) or note_good is not None \
                or not (note_absent and not note_absent[0] and "declares no" in note_absent[1]):
            failures.append("record-binding: hash checks did not behave as specified")
            print("SELFTEST FAIL: record-binding")
        else:
            print("SELFTEST PASS: record-binding -> mismatch caught, match silent, absence noted")

        # ---- review round-2, findings 7 and 8. Each was watched GREEN on the old code. ----

        # Finding 7a: the self-fulfilling recipe. `printf 'CLAIM VERIFIED'` with
        # expect = "CLAIM VERIFIED" was EXECUTED-PASS: the producer typed the answer into the
        # question and the tool reported the strongest outcome it has.
        cases += 1
        m4 = root / "selffulfil.toml"
        m4.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                      .replace("clauses_total = 3", "clauses_total = 1")
                      + _claim("SELF-1", "printf 'CLAIM VERIFIED'", "CLAIM VERIFIED"))
        rep4 = execute_manifest(m4, root, timeout=30, echo=False)
        if rep4.outcomes[0].state != SELF_FULFILLING or rep4.ok():
            failures.append(f"SELF-1: expected {SELF_FULFILLING}, got {rep4.outcomes[0].state}")
            print("SELFTEST FAIL: SELF-1")
        else:
            print(f"SELFTEST PASS: SELF-1 -> {SELF_FULFILLING}, and the report is not ok")

        # Positive control for 7a: an expect the command does NOT spell out still runs normally,
        # so the refusal is not "every printf is suspect".
        cases += 1
        m4b = root / "selffulfil_ok.toml"
        m4b.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                       .replace("clauses_total = 3", "clauses_total = 1")
                       + _claim("SELF-2", "cat green.txt", "VERIFICATION SUCCESSFUL"))
        rep4b = execute_manifest(m4b, root, timeout=30, echo=False)
        if rep4b.outcomes[0].state != EXECUTED_PASS:
            failures.append(f"SELF-2: expected {EXECUTED_PASS}, got {rep4b.outcomes[0].state}")
            print("SELFTEST FAIL: SELF-2")
        else:
            print("SELFTEST PASS: SELF-2 -> a non-echoed expect still runs and passes")

        # Finding 7b: `expect` was matched against stdout AND stderr, so a command that printed
        # its expectation only on stderr passed. It is stdout unless the row says otherwise.
        cases += 1
        m5 = root / "stderr.toml"
        m5.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                      .replace("clauses_total = 3", "clauses_total = 1")
                      + _claim("STDERR-1", "cat allgreen.txt >&2", "ALL GREEN"))
        rep5 = execute_manifest(m5, root, timeout=30, echo=False)
        if rep5.outcomes[0].state != EXPECT_MISMATCH \
                or "found on stderr" not in rep5.outcomes[0].detail:
            failures.append(f"STDERR-1: expected {EXPECT_MISMATCH} naming stderr, got "
                            f"{rep5.outcomes[0].state}: {rep5.outcomes[0].detail}")
            print("SELFTEST FAIL: STDERR-1")
        else:
            print("SELFTEST PASS: STDERR-1 -> stderr-only output is a mismatch, and says so")

        cases += 1
        m5b = root / "stderr_declared.toml"
        m5b.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                       .replace("clauses_total = 3", "clauses_total = 1")
                       + _claim("STDERR-2", "cat allgreen.txt >&2", "ALL GREEN")
                       + '  expect_stream = "stderr"\n')
        rep5b = execute_manifest(m5b, root, timeout=30, echo=False)
        if rep5b.outcomes[0].state != EXECUTED_PASS:
            failures.append(f"STDERR-2: a DECLARED stderr stream must match, got "
                            f"{rep5b.outcomes[0].state}")
            print("SELFTEST FAIL: STDERR-2")
        else:
            print("SELFTEST PASS: STDERR-2 -> an explicitly declared stderr stream matches")

        # Finding 8a: a present-but-mismatched record hash exited 0. It is a detected falsehood,
        # not an absence.
        cases += 1
        m6 = root / "hashmismatch.toml"
        m6.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                      .replace("clauses_total = 3", "clauses_total = 1")
                      + _claim("HASH-1", "cat okay.txt", "ok")
                      + '\n  [[claim.evidence]]\n  kind = "unit-test"\n  family = "dynamic"\n'
                        '  ref = "t"\n  result = "pass"\n  tool = "cargo@1.97"\n  cases = 1\n'
                        '  record = "evidence.log"\n  record_hash = "sha-512:%s"\n' % ("0" * 128))
        rep6 = execute_manifest(m6, root, timeout=30, echo=False)
        if rep6.ok() or not rep6.hash_errors:
            failures.append("HASH-1: a mismatched record_hash must make the report NOT ok")
            print("SELFTEST FAIL: HASH-1")
        else:
            print("SELFTEST PASS: HASH-1 -> a mismatched record hash is an error, not a note")

        # ...and an ABSENT hash stays a note (this mode does not itself enforce P9's
        # required-on-weighted rule; check_acceptance.py does, at manifest-validation time).
        cases += 1
        rep6b = execute_manifest(m6, root, timeout=30, echo=False)
        m6b = root / "hashabsent.toml"
        m6b.write_text(Path(m6).read_text().replace(
            '  record_hash = "sha-512:%s"\n' % ("0" * 128), ""))
        rep6b = execute_manifest(m6b, root, timeout=30, echo=False)
        if not rep6b.ok() or rep6b.hash_errors or not rep6b.hash_notes:
            failures.append("HASH-2: an ABSENT record_hash must stay a note in this mode")
            print("SELFTEST FAIL: HASH-2")
        else:
            print("SELFTEST PASS: HASH-2 -> an absent record hash is reported, not failed")

        # Finding 8b: NOT-RUN exited 0 with no way to demand otherwise.
        cases += 1
        m7 = root / "notrun.toml"
        m7.write_text(_MANIFEST_HEAD.replace("claims_total  = 3", "claims_total  = 1")
                      .replace("clauses_total = 3", "clauses_total = 1")
                      + _claim("NR-1", "cat okay.txt", "ok").replace(
                          '  [claim.self_verify]\n  command = "cat okay.txt"\n'
                          '  expect  = "ok"\n', ""))
        rep7 = execute_manifest(m7, root, timeout=30, echo=False)
        if rep7.outcomes[0].state != NOT_RUN or not rep7.ok() or rep7.ok(require_run=True):
            failures.append(
                f"NR-1: NOT-RUN must be ok by default and NOT ok under --require-run; got "
                f"state={rep7.outcomes[0].state} ok={rep7.ok()} "
                f"ok(require_run)={rep7.ok(require_run=True)}"
            )
            print("SELFTEST FAIL: NR-1")
        else:
            print("SELFTEST PASS: NR-1 -> NOT-RUN is a note by default, an error under "
                  "--require-run")

        # `--only` that matches nothing is a hard error, not a vacuous green (2026-08-28).
        # Both directions: a mistyped id fails and names itself; the correctly-spelled id
        # still selects its one row and passes.
        cases += 1
        rep8 = execute_manifest(mpath, root, timeout=30, only="OK-TYPO", echo=False)
        if (rep8.ok() or rep8.ok(require_run=True) or not rep8.selection_errors
                or "OK-TYPO" not in rep8.selection_errors[0]):
            failures.append(
                f"ONLY-0: --only matching zero claims must fail and name the id; got "
                f"ok={rep8.ok()} ok(require_run)={rep8.ok(require_run=True)} "
                f"selection_errors={rep8.selection_errors}"
            )
            print("SELFTEST FAIL: ONLY-0")
        else:
            print("SELFTEST PASS: ONLY-0 -> --only with no match is an error, not a green run")

        cases += 1
        rep9 = execute_manifest(mpath, root, timeout=30, only="OK-1", echo=False)
        if (not rep9.ok() or rep9.selection_errors or len(rep9.outcomes) != 1
                or rep9.outcomes[0].claim_id != "OK-1"):
            failures.append(
                f"ONLY-1: --only naming a real claim must select exactly it and pass; got "
                f"outcomes={[(o.claim_id, o.state) for o in rep9.outcomes]} "
                f"selection_errors={rep9.selection_errors}"
            )
            print("SELFTEST FAIL: ONLY-1")
        else:
            print("SELFTEST PASS: ONLY-1 -> --only naming a real claim selects exactly that row")

    print(f"selftest: {cases} cases, {len(failures)} failed")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True, description=__doc__)
    ap.add_argument("manifests", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--subject-root", default=None,
                    help="directory the commands run in. The manifest's [subject] block names "
                         "what is certified but carries no path (see P9a), so this is explicit.")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--only", default=None)
    ap.add_argument("--require-run", action="store_true",
                    help="every selected row must have EXECUTED. A NOT-RUN row becomes an error "
                         "instead of a note — the flag a gate uses when a green result is meant "
                         "to speak for the whole manifest rather than for the rows that happened "
                         "to carry a command.")
    ap.add_argument("--yes-run-untrusted-commands", action="store_true",
                    help="REQUIRED. Acknowledges that this mode executes commands taken from a "
                         "document, with no sandbox.")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.manifests:
        print("usage error: no manifest given", file=sys.stderr)
        return 2
    if not args.yes_run_untrusted_commands:
        print("REFUSING TO RUN: --execute mode runs commands taken from a document, with no "
              "sandbox. Pass --yes-run-untrusted-commands to acknowledge, and only for a "
              "manifest whose provenance you know.", file=sys.stderr)
        return 2
    if not args.subject_root:
        print("usage error: --subject-root is required (the manifest carries no path; see P9a)",
              file=sys.stderr)
        return 2
    root = Path(args.subject_root)
    if not root.is_dir():
        print(f"usage error: --subject-root {args.subject_root!r} is not a directory",
              file=sys.stderr)
        return 2

    any_bad = False
    for m in args.manifests:
        p = Path(m)
        if not p.is_file():
            print(f"ERROR {m}: not a file")
            any_bad = True
            continue
        print(f"-- executing {m} in {root} (timeout {args.timeout}s per row) --")
        rep = execute_manifest(p, root, args.timeout, args.only)
        print_report(rep, require_run=args.require_run)
        if not rep.ok(require_run=args.require_run):
            any_bad = True
    return 1 if any_bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
