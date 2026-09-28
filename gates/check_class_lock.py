#!/usr/bin/env python3
"""Check the public release's frozen Class text against the latest public lock.

Historical entries retain earlier hashes; only the latest entry describes the shipped files.
The upstream development repository checks public/source lock parity for every version.
"""
import hashlib
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = "CLASS-LOCK.toml"


CLASS_TEXT_FILES = ['format_acceptance/spec/core.md', 'format_acceptance/spec/format.md', 'format_acceptance/spec/profiles.md', 'format_acceptance/spec/hash-domains.md', 'protocol_acceptance/spec/protocol.md', 'protocol_acceptance/spec/states.toml', 'protocol_acceptance/spec/assurance-classes.toml']


def class_text_files(root):
    return CLASS_TEXT_FILES


def digests(root):
    return {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in class_text_files(root)}


def check(root):
    path = root / LOCK
    if not path.exists():
        return [f"{LOCK} missing"]
    locks = tomllib.loads(path.read_text()).get("lock", [])
    if not locks:
        return [f"{LOCK}: no [[lock]] entry"]
    current = locks[-1]
    for key in ("version", "date", "reason", "ratified", "files"):
        if key not in current:
            return [f"{LOCK}: latest [[lock]] lacks {key!r}"]
    errors = []
    if current["ratified"] is not False:
        errors.append("public release must state ratified = false")
    want, have = current["files"], digests(root)
    for f in sorted(set(want) | set(have)):
        if f not in have:
            errors.append(f"{f}: locked in {current['version']} but no longer a Class text file")
        elif f not in want:
            errors.append(f"{f}: Class text file not covered by lock {current['version']}")
        elif want[f] != have[f]:
            errors.append(f"{f}: changed since lock {current['version']} — append a new [[lock]] "
                          f"(new version + reason) instead of editing frozen text")
    return errors


def selftest():
    ok = True
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        for f in [LOCK] + class_text_files(ROOT):
            (t / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / f, t / f)
        if check(t):
            print("SELFTEST FAIL: clean copy does not pass"); ok = False
        target = t / class_text_files(ROOT)[0]
        target.write_text(target.read_text() + "\n")
        if not any("changed since lock" in e for e in check(t)):
            print("SELFTEST FAIL: a one-byte change to frozen text was not caught"); ok = False
    print("SELFTEST PASS: check_class_lock (2 controls)" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--print-digests" in sys.argv:
        for f, d in digests(ROOT).items():
            print(f'"{f}" = "{d}"')
        return 0
    errors = check(ROOT)
    for e in errors:
        print("ERROR", e)
    if errors:
        print(f"FAIL check_class_lock: {len(errors)} error(s)")
        return 1
    v = tomllib.loads((ROOT / LOCK).read_text())["lock"][-1]["version"]
    print(f"PASS check_class_lock: Class text matches lock {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
