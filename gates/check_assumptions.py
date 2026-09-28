#!/usr/bin/env python3
"""gates/check_assumptions.py — every stated residual of the Class rung is anchored in ASSUMPTIONS.md.

The two residual sections — format_acceptance/spec/core.md "## §5 What the class deliberately does not
do" and protocol_acceptance/spec/protocol.md "## 11. ..." — list what the core trusts and does not check.
Rule: every top-level bullet ("- ") and every "**Residual" paragraph in those sections carries at least
one tag [A-nn]; every tag names a row of the "Acceptance family" table in ASSUMPTIONS.md; every row of
that table is cited by at least one tag. Stdlib only. `--selftest` proves the gate can fail.
"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = [
    ("format_acceptance/spec/core.md", "## §5 What the class deliberately does not do"),
    ("protocol_acceptance/spec/protocol.md", "## 11."),
]
TAG = re.compile(r"\[(A-\d\d)\]")
ROW = re.compile(r"^\|\s*(A-\d\d)\s*\|", re.M)


def section(text, start):
    i = text.index(start)
    j = text.find("\n## ", i + len(start))
    return text[i:] if j < 0 else text[i:j]


def items(sec):
    """Top-level bullets and **Residual paragraphs, each as one string."""
    parts = re.split(r"(?m)^(?=- |\*\*Residual)", sec)
    return [p for p in parts if p.startswith("- ") or p.startswith("**Residual")]


def check(root):
    errors, cited = [], set()
    rows = set(ROW.findall((root / "ASSUMPTIONS.md").read_text()))
    for rel, start in SECTIONS:
        try:
            sec = section((root / rel).read_text(), start)
        except ValueError:
            errors.append(f"{rel}: section {start!r} not found")
            continue
        for it in items(sec):
            tags = TAG.findall(it)
            if not tags:
                errors.append(f"{rel}: untagged residual: {it.strip().splitlines()[0][:90]}")
            for t in tags:
                cited.add(t)
                if t not in rows:
                    errors.append(f"{rel}: tag [{t}] has no row in ASSUMPTIONS.md")
    for r in sorted(rows - cited):
        errors.append(f"ASSUMPTIONS.md: row {r} is cited by no residual in the core spec")
    return errors


def selftest():
    import shutil
    ok = True
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        for rel in ["ASSUMPTIONS.md"] + [r for r, _ in SECTIONS]:
            (t / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, t / rel)
        if check(t):
            print("SELFTEST FAIL: clean copy does not pass"); ok = False
        core = t / SECTIONS[0][0]
        clean = core.read_text()
        core.write_text(clean.replace("[A-01]", "", 1))           # untag one bullet (A-01 still cited by protocol.md)
        if not any("untagged residual" in e for e in check(t)):
            print("SELFTEST FAIL: untagged bullet not caught"); ok = False
        core.write_text(clean.replace("[A-02]", "[A-99]", 1))      # unknown tag + orphaned row
        errs = check(t)
        if not any("[A-99]" in e for e in errs) or not any("row A-02" in e for e in errs):
            print("SELFTEST FAIL: unknown tag / orphan row not caught"); ok = False
    print("SELFTEST PASS: check_assumptions (3 controls)" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    errors = check(ROOT)
    for e in errors:
        print("ERROR", e)
    if errors:
        print(f"FAIL check_assumptions: {len(errors)} error(s)")
        return 1
    n = len(set(ROW.findall((ROOT / "ASSUMPTIONS.md").read_text())))
    print(f"PASS check_assumptions: every Class residual anchored; {n} stated assumptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
