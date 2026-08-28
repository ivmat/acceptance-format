"""slug.py -- the tiny subject the weighted-toy manifest certifies one property of.

slug(s) lowercases s and replaces each run of whitespace with a single hyphen. Deliberately about
20 lines: this is the smallest subject examples/weighted-toy/acceptance.toml can honestly write a
real, non-illustrative weighted claim against.
"""
import re
import sys


def slug(s: str) -> str:
    """Lowercase s and replace each run of whitespace with a single '-'."""
    return re.sub(r"\s+", "-", s.strip().lower())


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(slug(arg))
