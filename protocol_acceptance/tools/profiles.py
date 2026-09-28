#!/usr/bin/env python3
"""profiles.py — profile bindings for the acceptance protocol core (protocol.md §6.6, P11).

Pure stdlib, no dependencies. The core tool (`acceptance_protocol.py`) is profile-blind (P11): it
never hard-codes a grade, a band, a family or a kind name. Everything that vocabulary-shaped lives
here, keyed by `profile_id`, and the core only ever calls through the small interface each profile
entry exposes:

    PROFILES[profile_id] = {
        "tier_ceiling": {method_or_kind_token: "T1".."T5", ...},   # §6.1
        "grade_rank":   {grade_token: int, ...},                    # profile-local ordering (format_acceptance/profiles/verification/PROFILE.md §3)
        "band_rank":    {band_token: int, ...},                     # profile-local ordering
        "revision_alias": "captured_at_commit",                     # §6.2 cond 7 / format_acceptance/profiles/verification/code/rust.md §1
        "floor_check":  callable(profile_floor_table, claim) -> (bool, reason_or_None),  # §6.2 cond 9
    }

The first (and, in `/0`, only) profile is `acceptance/verification`, projected for Rust code
delivery by `format_acceptance/profiles/verification/code/rust.md` (renamed 2026-09-24). A second
profile is added by adding a second entry to `PROFILES`; the core needs no change to consume it.
"""

from __future__ import annotations

import functools
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent / "format_acceptance" / "tools"))  # repo tools/: check_acceptance

import check_acceptance as _CA  # noqa: E402
import check_core as _CC  # noqa: E402 — revision L5: the profile-neutral core, for conformance/troubleshooting
import acceptance_grammar as _AG  # noqa: E402

# Revision L5: load the conformance and troubleshooting MEANING modules the same way check_acceptance.py
# loads verification's (`check_core._module`, a private `sys.modules` name) — never a plain `import
# profiles.conformance`, which would collide with THIS file's own bare module name `profiles`.
_CONFORMANCE_MEANING = _CC._module(_CC.MODULE_ROOT / "profiles" / "conformance.py", "meaning")
_TROUBLESHOOTING_MEANING = _CC._module(_CC.MODULE_ROOT / "profiles" / "troubleshooting.py", "meaning")

# ---------------------------------------------------------------------------------------------
# acceptance/verification (format_acceptance/profiles/verification/PROFILE.md §§2-3, code/rust.md
# §2) — vocabulary copied from the public `spec/evidence-types.md` grade/band ladders and the
# method/kind -> tier ceiling table (split by R5, 2026-09-24: the language-neutral tokens and the
# floor mechanism moved to PROFILE.md; the Rust-only tokens stayed at code/rust.md, renamed
# 2026-09-24). _TIER_CEILING below still merges both — this tool is not itself split by binding.
# ---------------------------------------------------------------------------------------------

# format_acceptance/profiles/verification/PROFILE.md §3: "The grade ordering exists only here, as
# floors a consumer may set." — the format itself (spec/0.1-DRAFT.md §1) deliberately does NOT
# order grades; this profile orders them for the single purpose of a contract floor.
_GRADE_RANK = {
    "contract": 5,
    "probe": 4,
    "test-only": 3,
    "mechanical": 2,
    "not-covered": 2,
    "inspection-argued": 1,
    "ungraded": 0,
    "unspecified": 0,
    "out-of-scope": 0,
}

_BAND_ORDER = ["A0", "A1", "A2", "A3", "A3.5", "A4"]
_BAND_RANK = {b: i for i, b in enumerate(_BAND_ORDER)}

# format_acceptance/profiles/verification/PROFILE.md §2 (the seven language-neutral tokens) and
# code/rust.md §2 (the five Rust-only tokens), verbatim from the public verification profile's
# method/kind -> epistemic_tier ceiling table.
_TIER_CEILING = {
    "lean-theorem": "T1",
    "kani-harness": "T2",
    "flux-refinement": "T2",
    "unit-test": "T3",
    "property-test": "T3",
    "fuzz": "T3",
    "miri": "T3",
    "lint": "T4",
    "semver-check": "T4",
    "dep-audit": "T4",
    "human-review": "T5",
    "llm-review": "T5",
}


# Finding 10: the closed vocabularies a profile floor may cite, read from the SAME registries
# `check_acceptance.py` itself enforces — never a second, driftable copy.
_ALLOWED_FLOOR_KEYS = {"min_grade", "min_band", "families", "kinds"}
_KNOWN_FAMILIES = {reg["family"] for reg in _CA.KIND_REGISTRY.values()}
_KNOWN_KINDS = set(_CA.KIND_REGISTRY.keys())


def _rust_verification_validate_floor(table: dict) -> list[str]:
    """Finding 10 / protocol.md §6.6 item 2, §3.3: the profile's floor-schema validator. Unknown
    keys and out-of-vocabulary tokens are ERRORS — a typo like `min_band = "A999"` or
    `min_grade = "typo"` must invalidate the contract, never silently weaken the floor to "always
    met" or "always skipped"."""
    errors: list[str] = []
    if not isinstance(table, dict):
        return ["profile floor table must be a table"]
    for k in table:
        if k not in _ALLOWED_FLOOR_KEYS:
            errors.append(
                f"unknown profile floor key {k!r} (allowed: {sorted(_ALLOWED_FLOOR_KEYS)})"
            )
    # Finding 15: type-check BEFORE set membership — `min_grade not in _AG.GRADES` raises
    # TypeError on an unhashable value (e.g. a list) instead of returning a validation error.
    min_grade = table.get("min_grade")
    if min_grade is not None:
        if not isinstance(min_grade, str):
            errors.append(f"min_grade must be a string, got {type(min_grade).__name__} (Finding 15)")
        elif min_grade not in _AG.GRADES:
            errors.append(f"min_grade {min_grade!r} is not one of {sorted(_AG.GRADES)}")
    min_band = table.get("min_band")
    if min_band is not None:
        if not isinstance(min_band, str):
            errors.append(f"min_band must be a string, got {type(min_band).__name__} (Finding 15)")
        elif min_band not in _CA.BANDS:
            errors.append(f"min_band {min_band!r} is not one of {sorted(_CA.BANDS)}")
    families = table.get("families")
    if families is not None:
        if not isinstance(families, list) or not families or not all(isinstance(f, str) for f in families):
            errors.append("families, if present, must be a nonempty list of strings")
        else:
            bad = [f for f in families if f not in _KNOWN_FAMILIES]
            if bad:
                errors.append(f"families contains unknown token(s) {bad} (known: {sorted(_KNOWN_FAMILIES)})")
    kinds = table.get("kinds")
    if kinds is not None:
        if not isinstance(kinds, list) or not kinds or not all(isinstance(k, str) for k in kinds):
            errors.append("kinds, if present, must be a nonempty list of strings")
        else:
            bad = [k for k in kinds if k not in _KNOWN_KINDS]
            if bad:
                errors.append(f"kinds contains unknown token(s) {bad} (known: {sorted(_KNOWN_KINDS)})")
    return errors


def _rust_verification_floor_check(floor: dict, claim: dict):
    """format_acceptance/profiles/verification/PROFILE.md §3: a claim meets the `acceptance/verification` profile floor iff
    rank(claim.grade) >= rank(min_grade), rank(claim.band) >= rank(min_band), and >= 1 PASSING
    evidence record has family in `families` (and kind in `kinds`). Shape of `floor` is opaque to
    the core (protocol.md §3.1 rule 5) — validated only here.

    Finding 10: `kinds` is enforced INDEPENDENTLY of `families` — either may be declared alone,
    and when both are declared a single passing record must satisfy both, not just whichever one
    happened to be truthy."""
    min_grade = floor.get("min_grade")
    if min_grade is not None:
        grade = claim.get("grade")
        if grade not in _GRADE_RANK or _GRADE_RANK[grade] < _GRADE_RANK.get(min_grade, 0):
            return False, f"grade {grade!r} does not reach profile min_grade {min_grade!r}"

    min_band = floor.get("min_band")
    if min_band is not None:
        band = claim.get("band")
        if band not in _BAND_RANK or _BAND_RANK[band] < _BAND_RANK.get(min_band, 0):
            return False, f"band {band!r} does not reach profile min_band {min_band!r}"

    families = floor.get("families")
    kinds = floor.get("kinds")
    if families or kinds:
        fams = set(families) if families else None
        knds = set(kinds) if kinds else None
        passing = [
            e for e in (claim.get("evidence") or [])
            if isinstance(e, dict) and e.get("result") == "pass"
        ]
        ok = any(
            (fams is None or e.get("family") in fams) and (knds is None or e.get("kind") in knds)
            for e in passing
        )
        if not ok:
            parts = []
            if fams is not None:
                parts.append(f"family in {sorted(fams)}")
            if knds is not None:
                parts.append(f"kind in {sorted(knds)}")
            return False, f"no passing evidence record with {' and '.join(parts)}"

    return True, None


def _rust_package_constraints(package: dict) -> list[str]:
    """format_acceptance/profiles/verification/code/rust.md §1 / protocol.md §6.6 item 6,
    Finding 17: "`dirty` must be false for a package a decision may accept" — a PACKAGE-level
    constraint (not a per-claim floor), exposed as a check the core calls through the profile
    binding (never a rule the core hard-codes by profile name)."""
    subj = package.get("subject") if isinstance(package, dict) else None
    if isinstance(subj, dict) and subj.get("dirty") is True:
        return ["package [subject].dirty must be false for a decision to accept it (verification/code/rust.md §1)"]
    return []


def _rust_verification_floor_not_weaker(old: dict, new: dict) -> bool:
    """protocol.md §3.5 tightening rule, profile-floor clause: "a profile floor may not weaken by
    the profile's own orderings." True iff `new` is at least as strict as `old`: min_grade/min_band
    rank must not decrease; `families`/`kinds` are compared SYMMETRICALLY, where ABSENCE means
    "unrestricted" (Finding 5) — removing a previously-declared restriction (present -> absent) is
    a weakening (everything now qualifies), exactly like WIDENING it (old not a superset of new);
    narrowing (new subset of old), or adding the restriction fresh (absent -> present), is a
    tightening. Previously `kinds` was not compared at all, and an EMPTY `new` families set
    (`families` removed) trivially satisfied `issubset` and passed as "not weaker"."""
    old_mg, new_mg = old.get("min_grade"), new.get("min_grade")
    if old_mg is not None:
        if new_mg is None or _GRADE_RANK.get(new_mg, -1) < _GRADE_RANK.get(old_mg, -1):
            return False
    old_mb, new_mb = old.get("min_band"), new.get("min_band")
    if old_mb is not None:
        if new_mb is None or _BAND_RANK.get(new_mb, -1) < _BAND_RANK.get(old_mb, -1):
            return False
    for key in ("families", "kinds"):
        old_present = isinstance(old.get(key), list)
        new_present = isinstance(new.get(key), list)
        if not old_present:
            continue  # absent in `old` = unrestricted there; nothing to protect
        if not new_present:
            return False  # restriction REMOVED = weaker (Finding 5)
        old_set = set(old[key])
        new_set = set(new[key])
        if not new_set.issubset(old_set):
            return False  # widened = weaker
    return True


# ---------------------------------------------------------------------------------------------
# worker-brief.md §1/§2 — the driver's two mechanical projections (`project-brief`/
# `assemble-package` in acceptance_protocol.py) reach EVERY Rust-specific decision through this
# small interface, exactly like the rest of the profile (P11): the core tool never hard-codes a
# cargo/rustc/kani command shape.
# ---------------------------------------------------------------------------------------------

# command "shape" -> (kind, family, method, epistemic_tier). One command classifies to exactly
# ONE evidence species (verification/PROFILE.md §2 + verification/code/rust.md §2's combined
# method/kind -> tier ceiling table) — a SECOND reading of
# the same transcript under a different kind (e.g. a `property-test` row carved out of the same
# `cargo test` run as a `unit-test` row) is not a command-classification fact and is NOT handled
# here; it is worker-declared (see assemble-package's `fill.toml` "extra evidence" rows).
_RUST_COMMAND_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^cargo\s+test\b"), "unit-test"),
    (re.compile(r"^cargo\s+kani\b"), "kani-harness"),
    (re.compile(r"^cargo\s+clippy\b"), "lint-clippy"),
    (re.compile(r"^cargo\s+doc\b"), "lint-doc"),
]

_RUST_COMMAND_CLASS_FIELDS: dict[str, dict[str, str]] = {
    "unit-test":    {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3"},
    "kani-harness": {"kind": "kani-harness", "family": "bmc", "method": "kani-harness", "epistemic_tier": "T2"},
    "lint-clippy":  {"kind": "lint", "family": "mechanical", "method": "lint", "epistemic_tier": "T4"},
    "lint-doc":     {"kind": "lint", "family": "mechanical", "method": "lint", "epistemic_tier": "T4"},
}

# Per command-shape, the tool-identity probe(s) `assemble-package` expects a transcript to have
# CAPTURED (worker-brief.md §2 "the tool's `--version` line captured in the transcript") — a list
# of argv lists, run before the real command, whose combined-output lines the assembler reads back
# out of the SAME transcript file (never trusted from a separately-typed string).
_RUST_VERSION_PROBES: dict[str, list[list[str]]] = {
    "unit-test":    [["rustc", "--version"], ["cargo", "--version"]],
    "kani-harness": [["cargo", "kani", "--version"]],
    "lint-clippy":  [["cargo", "clippy", "--version"], ["rustc", "--version"]],
    "lint-doc":     [["rustc", "--version"], ["cargo", "--version"]],
}


def rust_command_class(command: str) -> str | None:
    """Classifies a recipe command into one of the four shapes this profile knows. `None` means
    `assemble-package` cannot mechanically classify the command — the evidence row must then come
    from a worker-declared override (fill.toml) or the assembly is refused."""
    cmd = (command or "").strip()
    for pat, cls in _RUST_COMMAND_PATTERNS:
        if pat.match(cmd):
            return cls
    return None


def rust_evidence_class_fields(command: str) -> dict[str, str] | None:
    """verification/PROFILE.md §2 / verification/code/rust.md §2, worker-brief.md §2: `kind`/`family`/`method`/`epistemic_tier`, mechanically
    derived from the command's shape alone — never worker-typed."""
    cls = rust_command_class(command)
    return dict(_RUST_COMMAND_CLASS_FIELDS[cls]) if cls else None


def rust_version_probe_commands(command: str) -> list[list[str]]:
    """The `--version` probes a captured transcript for this command shape must carry."""
    cls = rust_command_class(command)
    return [list(c) for c in _RUST_VERSION_PROBES.get(cls, [])]


def rust_tool_string(command: str, probe_outputs: dict[str, str]) -> str | None:
    """Builds the evidence record's `tool` string from the probe outputs CAPTURED IN the
    transcript (`probe_outputs` keyed by the exact probe command, e.g. `"rustc --version"`),
    never from a value handed in out-of-band. Formats mirror the ones this example's generator
    used by hand before this verb existed (kept byte-for-byte, including the pre-existing
    `cargo kani --version` fallback: an earlier hand-written regex meant to extract a bare
    semantic version from that line never matched in practice — a doubled backslash inside a raw
    string made the pattern look for a literal backslash character — so the note has always
    carried the FULL `cargo-kani X.Y.Z` line rather than a bare `X.Y.Z`; reproduced here as
    observed fact, not "fixed", since the previous generator's output is the byte-identity
    target)."""
    cls = rust_command_class(command)
    rustc = probe_outputs.get("rustc --version", "")
    cargo = probe_outputs.get("cargo --version", "")
    if cls == "unit-test":
        return f"{rustc} + {cargo}"
    if cls == "lint-clippy":
        clippy = probe_outputs.get("cargo clippy --version", "")
        return f"{clippy} + {rustc}"
    if cls == "lint-doc":
        return f"rustdoc (bundled with {rustc}) via {cargo}"
    if cls == "kani-harness":
        raw = probe_outputs.get("cargo kani --version", "")
        return (
            f"kani@{raw} "
            "(commit unknown — `cargo kani --version` on this install reports only a semantic "
            "version, not a build sha; see the example README's Friction section)"
        )
    return None


_TEST_RESULT_RE = re.compile(r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed", re.MULTILINE)


def rust_judge_run(command: str, returncode: int, output: str) -> tuple[str, int | None]:
    """worker-brief.md §2 `result`/`cases`: mechanically parsed/derived from the (already-captured)
    transcript and the command's shape — never worker-typed. Returns (result, cases); `cases` is
    `None` where the command shape carries no case count (kani-harness/lint).

    `cases`, for a `cargo test` run: the PASSED count on a clean run, or the TOTAL (passed+failed)
    count on a run the recipe expected to go red (a mutation control) — the same convention this
    example's hand-written generator used (reusing the baseline's total test count on a control
    row, since the control mutates behaviour, not the number of tests in the binary)."""
    cls = rust_command_class(command)
    if cls == "unit-test":
        m = _TEST_RESULT_RE.search(output)
        if not m:
            return "fail", None
        passed, failed = int(m.group(2)), int(m.group(3))
        cases = passed if failed == 0 else passed + failed
        result = "pass" if (returncode == 0 and m.group(1) == "ok") else "fail"
        return result, cases
    if cls == "kani-harness":
        result = "pass" if (returncode == 0 and "VERIFICATION:- SUCCESSFUL" in output) else "fail"
        return result, None
    if cls == "lint-clippy":
        return ("pass" if returncode == 0 else "fail"), None
    if cls == "lint-doc":
        result = "pass" if (returncode == 0 and "warning" not in output) else "fail"
        return result, None
    return "fail", None


def rust_input_set(command: str, subject_dir) -> list[str]:
    """worker-brief.md §2 `[[claim.evidence.inputs]]`: "digests of the files the transcript's
    command read (the profile's declared input set)". Mechanical, not hardcoded to one crate's
    file names: `lib.rs` (the crate root, always read) + every locally-declared `mod NAME;` file,
    ordered by the position of that module's FIRST USE (`NAME::`) in `lib.rs`'s own body — the
    crate's own call order, not an arbitrary declaration or alphabetical order — + `Cargo.toml` +,
    for a `cargo test --test NAME` command specifically, the one matching `tests/NAME.rs`
    integration-test file (the only extra compilation unit that binary pulls in). verification/code/rust.md §8's
    declared-input-set glob (`src/**`, `tests/**`, ...) is the outer bound; this narrows it to what
    THIS command's compilation unit actually reads, per requirement's `ref` in the profile floor."""
    from pathlib import Path as _Path
    subject_dir = _Path(subject_dir)
    cls = rust_command_class(command)
    if cls is None:
        return []
    lib_path = subject_dir / "src" / "lib.rs"
    if not lib_path.is_file():
        return []
    inputs = ["src/lib.rs"]
    lib_text = lib_path.read_text(encoding="utf-8")
    declared_mods = re.findall(r"^\s*(?:pub\s+)?mod\s+(\w+)\s*;", lib_text, re.MULTILINE)

    def first_use(name: str) -> float:
        m = re.search(rf"\b{re.escape(name)}::", lib_text)
        return m.start() if m else float("inf")

    for name in sorted(declared_mods, key=first_use):
        rel = f"src/{name}.rs"
        if (subject_dir / rel).is_file():
            inputs.append(rel)
    if (subject_dir / "Cargo.toml").is_file():
        inputs.append("Cargo.toml")
    if cls == "unit-test":
        m = re.search(r"--test\s+(\S+)", command)
        if m:
            test_rel = f"tests/{m.group(1)}.rs"
            if (subject_dir / test_rel).is_file():
                inputs.append(test_rel)
    return inputs


def rust_recipe_carrier(requirement: dict) -> dict | None:
    """worker-brief.md §1 `done_criteria` source, tier 2: "the profile's recipe carrier for the
    requirement's pattern (a template the projector fills with the subject's paths)". No template
    table is implemented yet for this profile (verification/code/rust.md §1's recipe-carrier list is prose, not
    machine-readable, and pattern-matching a requirement's intent from free text would be a guess
    this profile declines to make) — always returns `None`, so `project-brief` falls through to
    tier 3 ("recipe: proposed by worker") for every requirement lacking a contract-declared
    `[requirement.evidence.recipe]`. Documented gap, not a silent no-op: see worker-brief.md §1's
    own three-tier order and NEXT-SESSION-DRIVER.md."""
    return None


# ---------------------------------------------------------------------------------------------
# acceptance/conformance — revision L5. `format_acceptance/tools/profiles/conformance.py`'s own
# docstring: "Sibling reuse by reference, not a second family or ladder registry" — conformance
# borrows verification's kind/family/tier vocabulary wholesale, minus `flux-refinement`
# (`KINDS = {k: v for k, v in verification.KINDS.items() if k != "flux-refinement"}`). Mirrored
# here for the identical reason: this is the SAME borrowed vocabulary, not a second copy of it.
# `min_grade`/`min_band`/`families`/`kinds` is the SAME floor shape as verification (protocol.md
# §6.6 item 2 leaves the shape to the profile; conformance's own evidence vocabulary happens to be
# verification's, so its floor shape is too) — the two `_rust_verification_*` functions above are
# NOT reused directly because their vocabulary (`_GRADE_RANK`/`_BAND_RANK`/`_KNOWN_*`) must stay
# conformance's own (no A3.5, no flux-refinement), never silently drift with verification's.
# ---------------------------------------------------------------------------------------------

_CONFORMANCE_TIER_CEILING = {k: v for k, v in _TIER_CEILING.items() if k != "flux-refinement"}
_CONFORMANCE_KNOWN_KINDS = {k for k in _CA.KIND_REGISTRY if k != "flux-refinement"}
_CONFORMANCE_KNOWN_FAMILIES = {
    reg["family"] for k, reg in _CA.KIND_REGISTRY.items() if k != "flux-refinement"
}
# conformance.py's own band fallback (no A3.5 — "reserved A3.5 has no rank in this
# borrowed-evidence lane", format_acceptance/tools/profiles/conformance.py).
_CONFORMANCE_BAND_ORDER = getattr(_AG, "BAND_ORDER", ("A0", "A1", "A2", "A3", "A4"))
_CONFORMANCE_BAND_RANK = {b: i for i, b in enumerate(_CONFORMANCE_BAND_ORDER)}
_CONFORMANCE_ALLOWED_FLOOR_KEYS = {"min_grade", "min_band", "families", "kinds"}


def _conformance_validate_floor(table: dict) -> list[str]:
    """protocol.md §6.6 item 2, §3.3: closed-vocabulary floor-schema validator, conformance's own
    tokens (mirrors Finding 10's verification validator, against conformance's registries)."""
    errors: list[str] = []
    if not isinstance(table, dict):
        return ["profile floor table must be a table"]
    for k in table:
        if k not in _CONFORMANCE_ALLOWED_FLOOR_KEYS:
            errors.append(
                f"unknown profile floor key {k!r} (allowed: {sorted(_CONFORMANCE_ALLOWED_FLOOR_KEYS)})"
            )
    min_grade = table.get("min_grade")
    if min_grade is not None:
        if not isinstance(min_grade, str):
            errors.append(f"min_grade must be a string, got {type(min_grade).__name__}")
        elif min_grade not in _AG.GRADES:
            errors.append(f"min_grade {min_grade!r} is not one of {sorted(_AG.GRADES)}")
    min_band = table.get("min_band")
    if min_band is not None:
        if not isinstance(min_band, str):
            errors.append(f"min_band must be a string, got {type(min_band).__name__}")
        elif min_band not in _CONFORMANCE_BAND_RANK:
            errors.append(f"min_band {min_band!r} is not one of {sorted(_CONFORMANCE_BAND_RANK)}")
    families = table.get("families")
    if families is not None:
        if not isinstance(families, list) or not families or not all(isinstance(f, str) for f in families):
            errors.append("families, if present, must be a nonempty list of strings")
        else:
            bad = [f for f in families if f not in _CONFORMANCE_KNOWN_FAMILIES]
            if bad:
                errors.append(f"families contains unknown token(s) {bad} (known: {sorted(_CONFORMANCE_KNOWN_FAMILIES)})")
    kinds = table.get("kinds")
    if kinds is not None:
        if not isinstance(kinds, list) or not kinds or not all(isinstance(k, str) for k in kinds):
            errors.append("kinds, if present, must be a nonempty list of strings")
        else:
            bad = [k for k in kinds if k not in _CONFORMANCE_KNOWN_KINDS]
            if bad:
                errors.append(f"kinds contains unknown token(s) {bad} (known: {sorted(_CONFORMANCE_KNOWN_KINDS)})")
    return errors


def _conformance_floor_check(floor: dict, claim: dict):
    """Same rule as verification's (verification/PROFILE.md §3), against conformance's own rank tables."""
    min_grade = floor.get("min_grade")
    if min_grade is not None:
        grade = claim.get("grade")
        if grade not in _GRADE_RANK or _GRADE_RANK[grade] < _GRADE_RANK.get(min_grade, 0):
            return False, f"grade {grade!r} does not reach profile min_grade {min_grade!r}"

    min_band = floor.get("min_band")
    if min_band is not None:
        band = claim.get("band")
        if band not in _CONFORMANCE_BAND_RANK or _CONFORMANCE_BAND_RANK[band] < _CONFORMANCE_BAND_RANK.get(min_band, 0):
            return False, f"band {band!r} does not reach profile min_band {min_band!r}"

    families = floor.get("families")
    kinds = floor.get("kinds")
    if families or kinds:
        fams = set(families) if families else None
        knds = set(kinds) if kinds else None
        passing = [
            e for e in (claim.get("evidence") or [])
            if isinstance(e, dict) and e.get("result") == "pass"
        ]
        ok = any(
            (fams is None or e.get("family") in fams) and (knds is None or e.get("kind") in knds)
            for e in passing
        )
        if not ok:
            parts = []
            if fams is not None:
                parts.append(f"family in {sorted(fams)}")
            if knds is not None:
                parts.append(f"kind in {sorted(knds)}")
            return False, f"no passing evidence record with {' and '.join(parts)}"

    return True, None


def _conformance_floor_not_weaker(old: dict, new: dict) -> bool:
    """protocol.md §3.5 tightening rule — same comparator shape as verification's, over
    conformance's own rank tables (Finding 5's absence-is-unrestricted symmetry preserved)."""
    old_mg, new_mg = old.get("min_grade"), new.get("min_grade")
    if old_mg is not None:
        if new_mg is None or _GRADE_RANK.get(new_mg, -1) < _GRADE_RANK.get(old_mg, -1):
            return False
    old_mb, new_mb = old.get("min_band"), new.get("min_band")
    if old_mb is not None:
        if new_mb is None or _CONFORMANCE_BAND_RANK.get(new_mb, -1) < _CONFORMANCE_BAND_RANK.get(old_mb, -1):
            return False
    for key in ("families", "kinds"):
        old_present = isinstance(old.get(key), list)
        new_present = isinstance(new.get(key), list)
        if not old_present:
            continue
        if not new_present:
            return False
        if not set(new[key]).issubset(set(old[key])):
            return False
    return True


# ---------------------------------------------------------------------------------------------
# acceptance/troubleshooting — revision L5. troubleshooting.py's own closed vocabulary (PROFILE.md,
# revision T7): a claim carries `fault_class` and an ordinal `outcome` (`OUTCOMES`, imported from the
# meaning module itself, never re-typed here) instead of verification's `grade`; bands are the
# SAME A0-A4 ladder ("troubleshooting.py: LADDER = verification.LADDER — assurance-bands.md's
# A0-A4 apply unchanged"). The floor shape is therefore genuinely different from verification's
# and conformance's: `min_band`, `min_outcome`, `fault_classes` — no `min_grade` concept exists
# for this meaning.
# ---------------------------------------------------------------------------------------------

_TS_OUTCOMES = _TROUBLESHOOTING_MEANING.OUTCOMES
_TS_FAMILIES = _TROUBLESHOOTING_MEANING.FAMILIES     # family -> tier ceiling ("T3"/"T4")
_TS_KINDS = _TROUBLESHOOTING_MEANING.KINDS           # kind -> {"family": ..., "extra": {...}}
_TS_TIER_CEILING = {kind: _TS_FAMILIES[info["family"]] for kind, info in _TS_KINDS.items()}
_TS_BAND_RANK = _BAND_RANK  # same ladder object verification uses (troubleshooting.py: "A0-A4 apply unchanged")
_TS_ALLOWED_FLOOR_KEYS = {"min_band", "min_outcome", "fault_classes"}


def _troubleshooting_validate_floor(table: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(table, dict):
        return ["profile floor table must be a table"]
    for k in table:
        if k not in _TS_ALLOWED_FLOOR_KEYS:
            errors.append(f"unknown profile floor key {k!r} (allowed: {sorted(_TS_ALLOWED_FLOOR_KEYS)})")
    min_band = table.get("min_band")
    if min_band is not None:
        if not isinstance(min_band, str):
            errors.append(f"min_band must be a string, got {type(min_band).__name__}")
        elif min_band not in _TS_BAND_RANK:
            errors.append(f"min_band {min_band!r} is not one of {sorted(_TS_BAND_RANK)}")
    min_outcome = table.get("min_outcome")
    if min_outcome is not None:
        if not isinstance(min_outcome, str):
            errors.append(f"min_outcome must be a string, got {type(min_outcome).__name__}")
        elif min_outcome not in _TS_OUTCOMES:
            errors.append(f"min_outcome {min_outcome!r} is not one of {list(_TS_OUTCOMES)}")
    fault_classes = table.get("fault_classes")
    if fault_classes is not None:
        if not isinstance(fault_classes, list) or not fault_classes or not all(isinstance(f, str) for f in fault_classes):
            errors.append("fault_classes, if present, must be a nonempty list of strings")
    return errors


def _troubleshooting_floor_check(floor: dict, claim: dict):
    min_band = floor.get("min_band")
    if min_band is not None:
        band = claim.get("band")
        if band not in _TS_BAND_RANK or _TS_BAND_RANK[band] < _TS_BAND_RANK.get(min_band, 0):
            return False, f"band {band!r} does not reach profile min_band {min_band!r}"

    min_outcome = floor.get("min_outcome")
    if min_outcome is not None:
        outcome = claim.get("outcome")
        if outcome not in _TS_OUTCOMES or _TS_OUTCOMES.index(outcome) < _TS_OUTCOMES.index(min_outcome):
            return False, f"outcome {outcome!r} does not reach profile min_outcome {min_outcome!r}"

    fault_classes = floor.get("fault_classes")
    if fault_classes is not None and claim.get("fault_class") not in set(fault_classes):
        return False, f"fault_class {claim.get('fault_class')!r} is not in {sorted(fault_classes)}"

    return True, None


def _troubleshooting_floor_not_weaker(old: dict, new: dict) -> bool:
    old_mb, new_mb = old.get("min_band"), new.get("min_band")
    if old_mb is not None:
        if new_mb is None or _TS_BAND_RANK.get(new_mb, -1) < _TS_BAND_RANK.get(old_mb, -1):
            return False
    old_mo, new_mo = old.get("min_outcome"), new.get("min_outcome")
    if old_mo is not None:
        if new_mo is None or _TS_OUTCOMES.index(new_mo) < _TS_OUTCOMES.index(old_mo):
            return False
    old_fc, new_fc = old.get("fault_classes"), new.get("fault_classes")
    if isinstance(old_fc, list):
        if not isinstance(new_fc, list) or not set(new_fc).issubset(set(old_fc)):
            return False
    return True


PROFILES: dict[str, dict] = {
    "acceptance/verification": {
        "tier_ceiling": _TIER_CEILING,
        "grade_rank": _GRADE_RANK,
        "band_rank": _BAND_RANK,
        "revision_alias": "captured_at_commit",
        "floor_check": _rust_verification_floor_check,
        "floor_not_weaker": _rust_verification_floor_not_weaker,
        # Finding 10 (§6.6 item 2, §3.3): the floor-schema validator — unknown keys/tokens error.
        "validate_floor": _rust_verification_validate_floor,
        # Finding 17 (§6.6 items 6, 8): package-level constraints and the package validator,
        # reached ONLY through this binding — the core never calls check_acceptance.py directly
        # by name.
        "package_constraints": _rust_package_constraints,
        "package_validator": _CA.validate,
        # The worker-brief adapter supplies the mechanical
        # command-classification interface `project-brief`/`assemble-package` reach through
        # `PROFILES[id][...]`, never by hard-coding a cargo/rustc/kani shape in the core tool.
        "command_class": rust_command_class,
        "evidence_class_fields": rust_evidence_class_fields,
        "version_probe_commands": rust_version_probe_commands,
        "tool_string": rust_tool_string,
        "judge_run": rust_judge_run,
        "recipe_carrier": rust_recipe_carrier,
        "input_set": rust_input_set,
    },
    # Revision L5: bound alongside verification, through the SAME profile-neutral core dispatcher
    # (see the leaf-id alias registered below this dict for the rust-delivery migration).
    # (`check_core.validate`, keyed to each meaning via `bound_meaning`) — never a second,
    # hand-rolled validation path.
    "acceptance/conformance": {
        "tier_ceiling": _CONFORMANCE_TIER_CEILING,
        "grade_rank": _GRADE_RANK,
        "band_rank": _CONFORMANCE_BAND_RANK,
        "revision_alias": "captured_at_commit",
        "floor_check": _conformance_floor_check,
        "floor_not_weaker": _conformance_floor_not_weaker,
        "validate_floor": _conformance_validate_floor,
        "package_validator": functools.partial(_CC.validate, bound_meaning="conformance"),
    },
    "acceptance/troubleshooting": {
        "tier_ceiling": _TS_TIER_CEILING,
        "band_rank": _TS_BAND_RANK,
        "revision_alias": "captured_at_commit",
        "floor_check": _troubleshooting_floor_check,
        "floor_not_weaker": _troubleshooting_floor_not_weaker,
        "validate_floor": _troubleshooting_validate_floor,
        "package_validator": functools.partial(_CC.validate, bound_meaning="troubleshooting"),
    },
}

# As of 2026-09-24 (rust-delivery migration onto the locked 0.3.0 core): B12 makes
# `[format].profile` carry the full leaf id (`acceptance/<meaning>/<binding path>`) once a
# manifest wants the format's own binding dispatch (`check_core.py` §6.6 item 8) to admit a
# binding-specific subject kind (B14: `rust-crate`/`rust-workspace` are admitted only by the
# `code`/`code/rust` binding chain, not by the base registry) — `protocol_acceptance/examples/
# rust-delivery/` now declares `[format].profile = "acceptance/verification/code/rust"` for
# exactly that reason. This PROTOCOL-layer registry stays keyed by MEANING for every other
# profile/example in this repo (the assurance-classes examples, the protocol selftest fixtures,
# `acceptance/conformance`, `acceptance/troubleshooting` all keep the meaning-only id unchanged),
# so this is an ALIAS onto the identical binding, not a second, independently-maintained entry —
# the leaf id and the meaning id answer every `PROFILES[...]` lookup (tier_ceiling, grade_rank,
# floor_check, floor_not_weaker, validate_floor, package_constraints, package_validator, the
# worker-brief mechanical-command interface) identically, because code/rust.md's own vocabulary
# (§2 tier ceilings, the PROFILE.md-lifted floor mechanism) is exactly what `"acceptance/
# verification"` above already encodes; the binding path adds an admission narrowing at the
# format layer, not a second vocabulary at the protocol layer.
PROFILES["acceptance/verification/code/rust"] = PROFILES["acceptance/verification"]
