#!/usr/bin/env python3
"""Gate the paint-stack snapshot and fail-fast walkthrough controls (Python stdlib).

Discovered by the leaf gates/check_*.py loop. Cargo/Kani reproduction remains an
explicit example operation; this gate checks the saved evidence and current input
bytes with both strict validators, all four protocol verbs and the example selftest.
"""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "protocol_acceptance/examples/paint-stack"
MARKERS = ("PASS paint-stack snapshot: 12 strict format checks + 12 protocol checks + decision render",
           "PASS paint-stack selftest:", "31 walkthrough cases",
           "stack accepted over inv-cargo for runtime at ",
           "not covered (trusted as the base, not checked): build-tool, language, platform, verification-tool",
           "accepted by Ochre Raster / maintainer, Studio Ochre / tools-lead under their own specifications",
           "raster-draw: declared binding: build-time-copy", "geom-math: declared binding: build-time-copy",
           "The label combines no assurance levels across the stack.",
           "PASS paint-stack chain controls:")


def check(tool):
    result = subprocess.run([sys.executable, str(tool)], cwd=ROOT,
                            capture_output=True, text=True, timeout=180)
    output = result.stdout + result.stderr
    if result.returncode:
        return [f"{tool}: exit {result.returncode}\n{output}"]
    return [f"{tool}: missing {marker!r}" for marker in MARKERS if marker not in output]


def selftest(example):
    # Preserve the relative repo layout so the copied selftest uses the real tools.
    with tempfile.TemporaryDirectory(prefix="paint-gate-") as tmp:
        tree = Path(tmp)
        (tree / "format_acceptance").symlink_to(ROOT / "format_acceptance", target_is_directory=True)
        protocol = tree / "protocol_acceptance"
        protocol.mkdir()
        (protocol / "tools").symlink_to(ROOT / "protocol_acceptance/tools", target_is_directory=True)
        sample = protocol / "examples/paint-stack"
        shutil.copytree(example, sample, symlinks=True,
                        ignore=shutil.ignore_patterns("target", "__pycache__", ".selftest-*"))
        tool = sample / "selftest.py"
        assert not check(tool), "copied snapshot must pass"
        # A source-byte change must be caught even when all record hashes and joins
        # remain internally consistent (the old standalone selftest missed this).
        source = sample / "paint-app/src/lib.rs"
        original = source.read_bytes()
        source.write_bytes(original + b"\n// unrecorded change\n")
        errors = check(tool)
        assert errors and "exit 1" in errors[0] and "digest" in errors[0], errors
        source.write_bytes(original)
        # A success-looking tool that exits nonzero or omits a marker is not green.
        fake = tree / "fake.py"
        fake.write_text("print('PASS paint-stack selftest:')\n")
        assert check(fake), "missing snapshot/walkthrough checks must fail"
        fake.write_text("print(" + repr("\n".join(MARKERS)) + ")\nraise SystemExit(37)\n")
        assert check(fake), "nonzero must fail even with all markers"
    print("SELFTEST PASS: check_paint_stack (4 controls)")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--example", type=Path, default=EXAMPLE, help="generated example to check (including a dry run)")
    args = parser.parse_args()
    if args.selftest:
        return selftest(args.example.resolve())
    errors = check(args.example.resolve() / "selftest.py")
    for error in errors:
        print("FAIL check_paint_stack:", error)
    if errors:
        return 1
    print("PASS check_paint_stack: strict snapshot, joins, hashes and 31 walkthrough cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
