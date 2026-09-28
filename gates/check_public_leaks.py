#!/usr/bin/env python3
"""Apply content and publication-apparatus leak rules to the whole export, without a git index.

Every PUBLIC_MARKERS pattern below builds its `\\b` word-boundary from a RAW Python string
literal, never an ordinary one — an ordinary `"\\b"` is interpreted as the backspace control
character (`\\x08`), not a regex word boundary, and silently never matches anything, while the
whole-tree gate still passes either way (it is scanning for a byte that cannot appear in normal
text). `--selftest` proves each category can both fire (a planted sample in a throwaway temp
tree, checked against ITS OWN regex, not merely against the full marker list) and stay quiet on a
representative benign string (a false-positive control) — run via `gates/run_all.sh` (wired below
`check_public_leaks.py`'s own plain invocation), not merely available.
"""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import check_content_leaks as gate


# These markers identify private review/governance apparatus rather than public protocol data.
# Assemble their spellings so this gate can scan itself without becoming a false positive. Every
# `\b` is a RAW-string word boundary (see module docstring) — never build one from an ordinary
# string literal again; `--selftest` below is the regression control for exactly that mistake.
PUBLIC_MARKERS = [
    ("decision-id", re.compile(r"\b" + "D" + r"-\d{4}\b")),
    ("ruling-id", re.compile(r"\b" + "R" + r"-\d{4}\b")),
    ("governance-id", re.compile(r"\b" + "ac" + "-gov" + r"(?:-\d+)?\b", re.IGNORECASE)),
    ("charter-reference", re.compile(r"\b" + "char" + r"ter\b", re.IGNORECASE)),
    ("private-source-name", re.compile(r"\b" + "acceptance" + r"-format-private\b", re.IGNORECASE)),
    ("reviewer-label", re.compile(r"\b" + "astra" + r"\b", re.IGNORECASE)),
    ("work-package-label", re.compile(r"\b" + "wp" + r"-l\d+\b", re.IGNORECASE)),
    ("private-investigation-path", re.compile(r"\b" + "inve" + r"stigation/|\b" + "inve" + r"stigation" + r"\.md\b", re.IGNORECASE)),
    ("private-status-path", re.compile(r"\b" + "status" + r"\.md\b", re.IGNORECASE)),
    ("private-slice-label", re.compile(r"\bslice\s+[A-Z]\b")),
    # More categories of private/control-plane apparatus that survived earlier rounds. Note:
    # `worker-brief` is NOT a marker here — the worker-brief adapter is a shipped public feature
    # (`protocol_acceptance/spec/adapters/worker-brief.md`), not private apparatus.
    ("model-routing-reference", re.compile(r"\b" + "model" + r"[-_]routing\b", re.IGNORECASE)),
    ("control-plane-reference", re.compile(r"\b" + "control" + r"[- ]plane\b", re.IGNORECASE)),
    ("work-package-phrase", re.compile(r"\b" + "work" + r" package" + r"s?\b", re.IGNORECASE)),
    ("owner-ruling-phrase", re.compile(r"\b" + "owner" + r" ruling\b", re.IGNORECASE)),
    ("private-subjects-path", re.compile(r"\b" + "subj" + r"ects/")),
    ("private-template-path", re.compile(r"_templ" + r"ate/")),
    ("open-question-marker", re.compile(r"\b" + "O" + r"Q-")),
    ("investigation-caps-marker", re.compile(r"\b" + "INVESTIGA" + r"TION\b")),
    # Case-sensitive: "Sol" is a reviewer's name; lowercase "sol" (the sun, a Spanish word, a
    # musical note, etc.) is an ordinary word and must NOT trip this category.
    ("reviewer-label-sol", re.compile(r"\b" + "S" + "ol" + r"\b")),
    # Case-sensitive internal ticket ids that survived earlier rounds: a versioned work-package
    # tag (`WP5`, `WP6`, `WP5v2` — distinct from the `WP-L\d` shape above) and a round/finding
    # tag (`R2-13` — distinct from the `R-\d{4}` ruling-id shape above, which has no digit
    # between the letter and the dash).
    ("internal-ticket-wp", re.compile(r"\b" + "WP" + r"\s?\d+(?:v\d+)?\b")),
    ("internal-ticket-r", re.compile(r"\b" + "R" + r"\d-\d{1,3}\b")),
]

# (category, planted-sample, benign-sample) — one able-to-fail control and one false-positive
# control per PUBLIC_MARKERS row, in the SAME order. The planted sample must contain exactly the
# marker; the benign sample is a representative near-miss (ordinary word, or a PUBLIC-shaped id
# spelled close to the private one) that must NOT trip the pattern.
SELFTEST_SAMPLES = [
    ("decision-id", "see D-0123 for the ruling", "see AD-0001 for the public decision"),
    ("ruling-id", "cites R-0008 as precedent", "cites AR-0008, an unrelated public label"),
    ("governance-id", "tracked as AC-GOV-12 upstream", "no governance identifiers appear here"),
    ("charter-reference", "see CHARTER §4 for the rule", "the chartered accountant signed off"),
    ("private-source-name", "forked from acceptance-format-private", "the acceptance format is public"),
    ("reviewer-label", "astra reviewed this delivery", "an astral projection is not a review"),
    ("work-package-label", "tracked under WP-L7", "the wp-lab experiment failed"),
    ("private-investigation-path", "see INVESTIGATION.md for detail", "investigative journalism, no file"),
    ("private-status-path", "read status.md first", "the status quo remains unchanged"),
    ("private-slice-label", "handled by slice A", "a slice of pie for dessert"),
    ("model-routing-reference", "consult the model-routing tier before assigning work",
     "the routing model predicted heavy traffic"),
    ("control-plane-reference", "escalate to the control plane for a ruling",
     "the control tower cleared the plane for landing"),
    ("work-package-phrase", "split this into two work packages for the team",
     "the network package manager updated 12 dependencies"),
    ("owner-ruling-phrase", "per an owner ruling from last week",
     "the property owner ruled out any renovation"),
    ("private-subjects-path", "see subjects/example/ENVELOPE.md for detail",
     "the subjects of the study varied widely"),
    ("private-template-path", "copy the _template/ directory for a new leaf",
     "the template file was blank"),
    ("open-question-marker", "flagged as OQ-7 pending a ruling",
     "the IOQ-2 sensor calibration passed"),
    ("investigation-caps-marker", "marked INVESTIGATION in the header",
     "the investigation proceeded slowly"),
    ("reviewer-label-sol", "Sol raised this in round 4",
     "sol invictus was an ancient roman festival"),
    ("internal-ticket-wp", "tracked in WP5v2 before shipping",
     "the WP directory holds nothing"),
    ("internal-ticket-r", "documented under R2-13 in the log",
     "flight R2 departs from gate 13"),
]


def scan_public_markers(
    root: Path, files: list[str], skip: frozenset[str] = frozenset(),
    markers: list[tuple[str, "re.Pattern"]] | None = None,
) -> list[str]:
    """The publication-apparatus half of the gate (PUBLIC_MARKERS only — the content-leak half is
    `check_content_leaks.py`'s own job and has its own test suite). Returns the relpaths that hit
    at least one marker; also prints one `FAIL:` line per hit, matching `main()`'s original
    behavior exactly (extracted so `--selftest` exercises the SAME code, not a re-implementation).
    `markers` defaults to the full `PUBLIC_MARKERS` list; `selftest()` below passes a
    SINGLE-category subset so a sample can be attributed to its OWN category, not merely to
    "some category in the full list fired" (a sample that only a DIFFERENT category actually
    catches must fail that category's own control)."""
    active = PUBLIC_MARKERS if markers is None else markers
    marker_hits: list[str] = []
    for rel in files:
        if rel in skip:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"FAIL: cannot scan publication markers in {rel}: {exc}")
            marker_hits.append(rel)
            continue
        for name, pattern in active:
            if pattern.search(text):
                print(f"FAIL: public marker {name} in {rel}")
                marker_hits.append(rel)
    return marker_hits


def selftest() -> int:
    errors = []
    covered = {name for name, _pat in PUBLIC_MARKERS}
    sampled = {name for name, _bad, _good in SELFTEST_SAMPLES}
    if covered != sampled:
        errors.append(f"SELFTEST_SAMPLES does not cover exactly PUBLIC_MARKERS: "
                       f"missing={covered - sampled}, extra={sampled - covered}")
    pattern_by_name = dict(PUBLIC_MARKERS)
    for name, planted, benign in SELFTEST_SAMPLES:
        pattern = pattern_by_name[name]
        with tempfile.TemporaryDirectory(prefix="check-public-leaks-selftest-") as td:
            root = Path(td)
            (root / "planted.md").write_text(planted + "\n", encoding="utf-8")
            (root / "benign.md").write_text(benign + "\n", encoding="utf-8")
            # Scoped to THIS category's own regex only — a sample that some OTHER category
            # happens to also catch must not be mistaken for a working control on THIS one.
            hits = scan_public_markers(root, ["planted.md", "benign.md"], markers=[(name, pattern)])
        if "planted.md" not in hits:
            errors.append(f"{name}: able-to-fail control did NOT fire under its OWN category "
                           f"on {planted!r}")
        if "benign.md" in hits:
            errors.append(f"{name}: false-positive control WRONGLY fired under its OWN category "
                           f"on {benign!r}")

    # Prove the per-category scoping above is actually load-bearing, not a no-op: neuter
    # "private-investigation-path"'s regex in memory (replace it with one that can never match)
    # and confirm its OWN planted sample ("see INVESTIGATION.md for detail") now fails
    # attribution to that category — even though the FULL PUBLIC_MARKERS list still flags the
    # same text, via the unrelated "investigation-caps-marker" category (its planted text
    # contains the substring "INVESTIGATION"). If per-category scoping above were a no-op (i.e.
    # if it silently fell back to "any category in the full list fires"), this neutering would
    # go undetected — exactly the correctness gap a review found in an earlier version of this
    # selftest.
    neutered_name = "private-investigation-path"
    neutered_pattern = re.compile(r"(?!)")  # a regex that can never match anything
    neutered_sample = dict((n, p) for n, p, _b in SELFTEST_SAMPLES)[neutered_name]
    with tempfile.TemporaryDirectory(prefix="check-public-leaks-selftest-neuter-") as td:
        root = Path(td)
        (root / "neutered.md").write_text(neutered_sample + "\n", encoding="utf-8")
        own_hits = scan_public_markers(root, ["neutered.md"], markers=[(neutered_name, neutered_pattern)])
        full_hits = scan_public_markers(root, ["neutered.md"], markers=PUBLIC_MARKERS)
    if "neutered.md" in own_hits:
        errors.append("neutering control invalid: the neutered pattern matched under its own "
                       "category (it should never match anything)")
    if "neutered.md" not in full_hits:
        errors.append(f"neutering control invalid: no OTHER category in PUBLIC_MARKERS catches "
                       f"{neutered_name}'s planted sample either, so this cannot demonstrate "
                       f"cross-category masking")

    if errors:
        for e in errors:
            print("SELFTEST FAIL:", e)
        return 1
    print(f"SELFTEST PASS: check_public_leaks — {len(SELFTEST_SAMPLES)} categories each "
          f"able-to-fail (planted) and false-positive-clean (benign), each checked under its OWN "
          f"category, plus a neutering control proving that scoping is load-bearing")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    root = Path(__file__).resolve().parents[1]
    baseline = root / 'gates/leak_baseline.json'
    if json.loads(baseline.read_text()) != {}:
        print('FAIL: public leak baseline must be exactly empty')
        return 1
    files = []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {'.git', '__pycache__'})
        for name in sorted(names):
            p = Path(base) / name
            if p.is_symlink() and not p.resolve().is_relative_to(root):
                print('FAIL: escaping symlink:', p.relative_to(root))
                return 1
            files.append(p.relative_to(root).as_posix())
    # Retain exactly the original rules and two source/fixture exemptions.
    gate.tracked_files = lambda: files
    result = gate.check_tree()
    marker_hits = scan_public_markers(root, files, skip=frozenset({"gates/check_public_leaks.py"}))
    if marker_hits:
        result = 1
    print(f'Leak scope: {len(files)} working-tree files; git metadata and Python cache directories excluded')
    return result


if __name__ == '__main__':
    sys.exit(main())
