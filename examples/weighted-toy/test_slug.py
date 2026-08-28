"""test_slug.py -- the real, runnable evidence for the weighted-toy manifest's one claim.

Five concrete cases (deliberately BOUNDED -- not the full string domain, see acceptance.toml's
`bounds` field): plain lowercase, plain uppercase, mixed case with an internal space, an
alphanumeric string with no letters to change, and input that is already hyphenated. Prints a
PASS/FAIL line self_verify.expect matches, and exits nonzero on any failure -- the same shape this
repo's own gate tools use, so it is a real deciding recipe, not a demonstration.

acceptance.toml's self_verify.command names this as `python3 test_slug.py`, run from THIS
directory (as `check_execute.py --subject-root examples/weighted-toy` would run it) -- also
runnable as `python3 examples/weighted-toy/test_slug.py` from the repo root; either way Python
puts this script's own directory on sys.path, so the sibling import below resolves.
"""
import sys

from slug import slug

CASES = [
    ("hello", "hello"),
    ("HELLO", "hello"),
    ("Hello World", "hello-world"),
    ("abc123", "abc123"),
    ("already-hyphenated", "already-hyphenated"),
]


def main() -> int:
    failures = []
    for given, want in CASES:
        got = slug(given)
        if got != want:
            failures.append(f"slug({given!r}) = {got!r}, want {want!r}")
        elif got != got.lower():
            failures.append(f"slug({given!r}) = {got!r} contains an uppercase letter")
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"TEST-SLUG FAILED: {len(failures)}/{len(CASES)} cases")
        return 1
    print(f"TEST-SLUG PASS: {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
