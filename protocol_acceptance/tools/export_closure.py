#!/usr/bin/env python3
"""export_closure.py — export or verify the COMPLETE, self-contained closure of the acceptance
family's consumer tools: `format_acceptance/tools/check_acceptance.py`,
`protocol_acceptance/tools/acceptance_protocol.py`, and `format_acceptance/tools/spec_inventory.py`
— every `.py` module they load and every `.toml`/`.md` policy file they read at runtime — plus a
mechanically-recomputable manifest (`CLOSURE.json`), so a downstream repo can vendor ONE directory
instead of hand-picking files (the old vendor pattern this replaces pinned three files by name and
silently drifted when a fourth file became load-bearing).

Verbs
-----
    export_closure.py export --dest DIR      # copy the closure into DIR, write DIR/CLOSURE.json
    export_closure.py verify --dest DIR       # recompute DIR's own manifest, fail on any drift,
                                                #   missing/extra file, bytecode cache, or
                                                #   requested provenance mismatch
    export_closure.py --selftest              # export to a temp dir OUTSIDE this repo, py_compile
                                                #   every exported .py, run the EXPORTED verifier
                                                #   (a subprocess, from a further-relocated copy)
                                                #   standalone, smoke-run every consumer verb the
                                                #   adoption guide documents with a RAISING audit
                                                #   hook enforcing zero reads from the source
                                                #   checkout, then a battery of able-to-fail
                                                #   controls (missing/extra/corrupt/tamper/bytecode/
                                                #   hygiene/forbidden-read/in-repo-dest-refusal)

`export` requires a nonexistent `--dest` (including no dangling symlink). It copies into a fresh,
unique sibling staging directory, scans there, and renames it into place only after success.
Failure cleans up only that staging directory; existing destinations are refused untouched.
`--dest` MUST resolve outside this repository: exporting into the source checkout makes an
untracked export show up in `git status`, so `source_dirty` would read `true` even from a clean
tagged commit. `export` refuses (exit 1, creating nothing) a `--dest` inside the checkout.

**No file is rewritten at export.** Every candidate file is copied BYTE-FOR-BYTE (`shutil.copy2`);
`export` then scans the copied bytes for apparatus/privacy tokens and REFUSES (nonzero, listing
every hit) if anything remains — fail-closed, never a silent rewrite. An earlier revision of this
tool tried to auto-redact matched tokens in the copied text; that TEXT TRANSFORM corrupted its own
exported copy (a regex literal defining the home-path pattern textually contains the very substring
it matches, so rewriting it produced a syntactically broken file — an unterminated string literal).
The fix is the one stated above: neutralize offending prose IN THE SOURCE FILES THEMSELVES (a
one-time reviewed edit to comments/docstrings and seven output-string exceptions recorded in the
adoption guide's review notes, never the CLASS-LOCK frozen spec text),
then let export be a pure copy-and-verify step with no text transformation in its own right.

The closure is derived MECHANICALLY, never hand-listed: a small in-process harness runs each real
CLI (via `runpy`, exactly as `python3 <script> ...` would — same `sys.path[0]` rule) against the
repo's own worked example (`protocol_acceptance/examples/rust-delivery/`), with a
`sys.addaudithook` recording every file the interpreter actually `open()`s, filtered to paths
inside this repository with a `.py`, `.toml`, or `.md` suffix. `.md` is in that set for a verified
reason, not by generosity: `check_core.py`'s B14 kind-admission check (`_binding_admitted_kinds`)
reads a binding's `admits = [...]` declaration from a MACHINE-READABLE fenced TOML block inside a
Markdown DOCUMENT under `format_acceptance/profiles/bindings/` (`code.md`, `code/rust.md`) — this
is genuine runtime policy data, not frozen prose, and a first cut of this tool that filtered to
`.py`/`.toml` only produced a closure that failed `[subject].kind = "rust-crate"` admission the
moment it was smoke-tested standalone (caught by this tool's own `--selftest`, not by inspection).
The frozen Class prose under `format_acceptance/spec/` (`CLASS-LOCK.toml`'s own file set) is
excluded on purpose (`EXCLUDE_PREFIXES`): confirmed, none of it is `open()`-ed by an ordinary
validation run. Ten probe commands are run (§ PROBES below) so the trace covers every code path a
real Rust/Kani producer's session exercises: `check_acceptance.py`, `check_core.py` (directly — kept
as a cross-check even though the 0.3.1 dispatch fix means `check_acceptance.py` alone now already
reaches the binding chain), `acceptance_protocol.py`'s own `check-contract` / `check-package` /
`coverage` / `check-decision` / `check-states` / `impact` verbs, `spec_inventory.py`, and one
synthetic minimal contract that sets `[acceptance].assurance_class` (the worked example does not,
so `assurance-classes.toml` would otherwise never be opened).

Apparatus hygiene: `hygiene_violations()` scans copied bytes for home-relative paths, known
reviewer/model-name tokens, and a small embedded set of internal-only apparatus tokens (the same category
`gates/check_core_generic.py` polices for the Class spec text — the token LIST is duplicated here,
deliberately NOT imported at module load, so `verify` never depends on this repository's layout;
see "Standalone by construction" below). Every pattern literal in this module is assembled from two
or more non-matching string fragments at import time specifically so this scanner's OWN pattern
definitions never self-match when this very file is one of the files being scanned (verified by
this module's own `--selftest`).

**Standalone by construction.** No module-level code in this file touches this repository's layout
(no `REPO_ROOT`-anchored file read at import time). `verify`/`_verify` read only files under the
`--dest` directory the caller names. `REPO_ROOT` (used only by `export`/`discover_closure`, i.e.
the export side, which only ever runs from this repository) is computed as a bare path expression,
never dereferenced until an export-side function actually needs it. This is verified end to end by
`--selftest`: it relocates a completed export to a SECOND directory and runs
`python3 <relocated>/export_closure.py verify --dest <relocated>` as a real subprocess — the exact
command a downstream consumer's CI runs — with no access to this repository at all.

Stdlib only (Python 3.11+): `tomllib`, `ast`, `runpy`, `hashlib`, `subprocess`, `tempfile`.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLOSURE_FILE = "CLOSURE.json"
EXPORTER_COPY_NAME = "export_closure.py"

# The three consumer entry points a downstream repo actually runs (deliverable §1's own list),
# always included even if a probe below fails to execute for some reason on the running platform.
ENTRYPOINTS = (
    "format_acceptance/tools/check_acceptance.py",
    "protocol_acceptance/tools/acceptance_protocol.py",
    "format_acceptance/tools/spec_inventory.py",
)

# These are runtime policy/data files that every closure must carry.  The probes below are what
# collect them; this floor makes a failed or accidentally narrowed probe fail closed rather than
# emit a self-consistent but incomplete manifest.
COLLECTION_FLOOR = frozenset((
    "protocol_acceptance/spec/states.toml",
    "protocol_acceptance/spec/assurance-classes.toml",
    "format_acceptance/profiles/bindings/code.md",
    "format_acceptance/profiles/bindings/code/rust.md",
))

# Example/demo/fixture content the probes read as INPUT — never part of the tools' own closure,
# even though the trace legitimately opens it while validating the worked example. Also excludes
# the frozen prose Class spec (`format_acceptance/spec/`, CLASS-LOCK.toml's own file set): those
# documents are never `open()`-ed by these tools at runtime (confirmed: `hashdomains.py` only
# reads `spec/hash-domains.md` from its own `--selftest`, which none of the three consumer CLIs
# call), so an appearance there would be a probe artifact, not a real dependency.
EXCLUDE_PREFIXES = (
    "protocol_acceptance/examples/",
    "format_acceptance/tools/fixtures/",
    "protocol_acceptance/tools/fixtures/",
    "format_acceptance/spec/",
)

_RUST_DELIVERY = "protocol_acceptance/examples/rust-delivery"

_SYNTHETIC_CONTRACT = """\
[document]
protocol   = "acceptance-protocol/0"
minor      = 0
kind       = "contract"
id         = "PROBE-0001"
version    = 1
issued_at  = "2026-01-01T00:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = { name = "probe" }
producer = { name = "probe" }

[subject]
kind        = "other"
name        = "probe"
description = "probe"
profile     = "acceptance/verification"

[[requirement]]
id            = "R1"
statement     = "probe requirement"
mandatory     = true
waivable      = false
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "T5"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"

[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "package-trusted"
authority              = "probe"
profiles_required      = ["acceptance/verification"]
phase                  = "exploratory"
assurance_class        = "baseline/1"
"""


# ---------------------------------------------------------------------------
# Git — always with GIT_* environment scrubbed and hooks disabled: an inherited GIT_DIR/
# GIT_WORK_TREE/GIT_INDEX_FILE would make even a `-C <path>` invocation operate on a DIFFERENT
# repository than the one named, and an inherited hook could fire against a throwaway fixture.
# Every git call in this file goes through this one helper, whether it targets the real REPO_ROOT
# or a throwaway temp-dir fixture.
# ---------------------------------------------------------------------------

def _isolated_git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
        capture_output=True, text=True, env=_isolated_git_env(),
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} (in {root}) failed, exit {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _family_version(root: Path) -> str:
    """Read either source or public lock; archives without a lock use the export receipt.

    Both lock layouts expose only the version and file hashes needed here. Review metadata
    is optional. A present but invalid lock must never fall through to the receipt.
    """
    try:
        lock = root / "CLASS-LOCK.toml"
        if lock.exists():
            locks = tomllib.loads(lock.read_text(encoding="utf-8")).get("lock", [])
            if not locks:
                raise RuntimeError("CLASS-LOCK.toml carries no [[lock]] entry")
            current = locks[-1]
            version, files = current["version"], current["files"]
        else:
            receipt = json.loads((root / "EXPORT-PROVENANCE.json").read_text(encoding="utf-8"))
            version = receipt["family_version"]
            files = {rel: entry["sha256"] for rel, entry in receipt["files"].items()}
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise RuntimeError("invalid family version")
        if not isinstance(files, dict) or not files:
            raise RuntimeError("family metadata has no file hashes")
        for rel, digest in files.items():
            path = root / rel
            if (not isinstance(rel, str) or Path(rel).is_absolute()
                    or ".." in Path(rel).parts or not path.resolve().is_relative_to(root.resolve())):
                raise RuntimeError("family metadata path escapes source tree")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise RuntimeError(f"invalid family metadata digest: {rel}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"family metadata drift: {rel}")
        return version
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"invalid family metadata: {exc}") from exc


def _source_commit(root: Path) -> str:
    commit = _git(root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"git rev-parse HEAD did not return a 40-hex commit: {commit!r}")
    return commit


def _source_dirty(root: Path) -> bool:
    return bool(_git(root, "status", "--porcelain"))


def _dest_is_inside_repo(dest: Path) -> bool:
    try:
        dest.resolve().relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Apparatus hygiene: SCAN ONLY, never rewrite (design ruling after a prior text-transform round
# corrupted its own exported copy — see the module docstring). `export` copies every file
# byte-for-byte and refuses if this scan finds anything.
#
# Every pattern below is assembled from ≥2 fragments so this scanner's OWN pattern-definition
# lines never match themselves when this file is one of the files being scanned — a plain literal
# a plain literal home-path-pattern definition line textually CONTAINS the very substring it
# matches, so a single unbroken literal here would make `export` refuse to export this file forever. This is not
# obfuscation of a secret; the resulting patterns are logged in this module's own docstring and
# `--selftest` output. `_tok` is the one place fragment-joining happens, so the technique is
# visible in one spot, not scattered.
# ---------------------------------------------------------------------------

def _tok(*parts: str) -> str:
    return "".join(parts)


_HOME_PATH_RE = re.compile(
    re.escape(_tok("~", "/repo/")) + r"\S+"
    r"|" + re.escape(_tok("/", "Users", "/")) + r"[A-Za-z0-9_.\-]+(?:/[^\s`)]*)?"
)
_COLD_REVIEW_RE = re.compile(_tok("cold", "[- ]", "op", "us"), re.IGNORECASE)
_NAME_TOKEN_RE = re.compile(
    r"\b(" + _tok("as", "tra") + "|" + _tok("fa", "ble") + "|" + _tok("gpt", "-\\w+") + r")\b",
    re.IGNORECASE,
)
# Case-sensitive: this spells another reviewer's name; the same lowercase word (an ordinary word
# or abbreviation) must NOT trip this — kept out of _NAME_TOKEN_RE above, which is IGNORECASE.
_SOL_NAME_RE = re.compile(r"\b" + _tok("S", "ol") + r"\b")
_APPARATUS_TOKEN_RE = re.compile(
    r"\b" + _tok("OQ", "-0\\.3-\\d+") + r"\b"
    r"|\b" + _tok("OQ", "-T\\d+") + r"\b"
    r"|\b" + _tok("WP", "-[A-Z]*\\d+") + r"\b"
    r"|\b" + _tok("WP", "\\d+(?:v\\d+)?") + r"\b"
    r"|\b" + _tok("R", "\\d-\\d{1,3}") + r"\b"
    r"|\b" + _tok("subject", "s? in WP\\d*") + r"\b"
    r"|\b" + _tok("build", " plan") + r"\b"
    r"|\b" + _tok("owner", " ruling") + r"\b"
    r"|\b" + _tok("owner", " word") + r"\b"
    r"|\b" + _tok("h", "ub") + r"\b"
    r"|\b" + _tok("est", "ate") + r"\b(?!-element)"
    r"|\b" + _tok("gov", "ernor") + r"\b"
    r"|\b" + _tok("companion", " repo") + r"\b"
    r"|\b" + _tok("investigation", " closure") + r"\b"
    r"|\b" + _tok("lin", "ux") + r"\b"
    r"|\b" + _tok("found", "ry") + r"\b",
    re.IGNORECASE,
)


def hygiene_violations(text: str) -> list[tuple[int, str, str]]:
    """`(line_no, pattern_name, line_text)` for every hit — the export-time fail-closed check
    AND `--selftest`'s able-to-fail control (a planted token must be caught)."""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if _HOME_PATH_RE.search(line):
            hits.append((i, "home-path", line))
        elif _COLD_REVIEW_RE.search(line) or _NAME_TOKEN_RE.search(line) or _SOL_NAME_RE.search(line):
            hits.append((i, "reviewer-name", line))
        elif _APPARATUS_TOKEN_RE.search(line):
            hits.append((i, "apparatus", line))
    return hits


# ---------------------------------------------------------------------------
# Mechanical closure discovery (probes + audit hook)
# ---------------------------------------------------------------------------

# Each probe: (script relative to REPO_ROOT, argv, cwd relative to REPO_ROOT or a synthetic temp
# dir). Each probe must complete cleanly: an error can leave a trace that looks sufficient while
# omitting the policy branch it failed before reaching.
def _probes(synthetic_dir: Path) -> list[tuple[str, list[str], Path]]:
    rd = REPO_ROOT / _RUST_DELIVERY
    return [
        ("format_acceptance/tools/check_acceptance.py",
         ["--strict", "--strict-weight", "acceptance.toml"], rd),
        # Direct check_core.py invocation: kept as a cross-check, not a workaround — see the
        # module docstring's paragraph on the 0.3.1 dispatch fix.
        ("format_acceptance/tools/check_core.py",
         ["--strict", "--strict-weight", "acceptance.toml"], rd),
        ("protocol_acceptance/tools/acceptance_protocol.py",
         ["check-contract", "acceptance-contract.toml"], rd),
        ("protocol_acceptance/tools/acceptance_protocol.py",
         ["check-package", "acceptance.toml", "--contract", "acceptance-contract.toml"], rd),
        ("protocol_acceptance/tools/acceptance_protocol.py",
         ["coverage", "acceptance.toml", "--contract", "acceptance-contract.toml"], rd),
        ("protocol_acceptance/tools/acceptance_protocol.py",
         ["check-decision", "acceptance-decision.toml", "--contract", "acceptance-contract.toml",
          "--package", "acceptance.toml"], rd),
        ("protocol_acceptance/tools/acceptance_protocol.py", ["check-states"], rd),
        ("protocol_acceptance/tools/acceptance_protocol.py",
         ["impact", "acceptance-decision.toml", "--contract", "acceptance-contract.toml",
          "--package", "acceptance.toml",
          "--new-commit", "1111111111111111111111111111111111111111",
          "--changed", "src/checksum.rs"], rd),
        # Synthetic minimal contract declaring [acceptance].assurance_class — the worked example
        # does not, so spec/assurance-classes.toml would otherwise never be opened by a probe.
        ("protocol_acceptance/tools/acceptance_protocol.py",
         ["check-contract", "contract.toml"], synthetic_dir),
        ("format_acceptance/tools/spec_inventory.py",
         ["make", str(REPO_ROOT / "format_acceptance/spec/hash-domains.md")], REPO_ROOT),
    ]


_HARNESS_SOURCE = '''\
import sys, json, runpy, pathlib
root = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2])
script = pathlib.Path(sys.argv[3]).resolve()
records = set()
def _hook(event, args):
    if event != "open":
        return
    p = args[0]
    if not isinstance(p, str):
        return
    try:
        rp = pathlib.Path(p).resolve()
    except Exception:
        return
    if rp.suffix not in (".py", ".toml", ".md"):
        return
    try:
        rel = rp.relative_to(root)
    except ValueError:
        return
    records.add(str(rel))
sys.addaudithook(_hook)
sys.path.insert(0, str(script.parent))
sys.argv = [str(script)] + sys.argv[4:]
try:
    runpy.run_path(str(script), run_name="__main__")
except SystemExit:
    pass
except Exception as exc:
    print(f"HARNESS-PROBE-ERROR: {exc!r}", file=sys.stderr)
out.write_text(json.dumps(sorted(records)))
'''


def _run_probe(script: str, argv: list[str], cwd: Path, harness: Path,
                pycache_dir: Path) -> set[str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        out_path = Path(tf.name)
    env = dict(os.environ)
    # A stale __pycache__/*.pyc already sitting next to a source file (left over from an earlier,
    # unrelated run of these tools) makes the interpreter load the CACHED bytecode and never
    # `open()` the .py source at all — silently blinding the audit hook to a real dependency.
    # PYTHONPYCACHEPREFIX redirects cache lookups to an empty, per-export temp directory so every
    # module's first read in this trace is always a genuine source open. PYTHONDONTWRITEBYTECODE
    # is kept too so a repeated `export` never leaves new cache files behind either way.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(pycache_dir)
    try:
        result = subprocess.run(
            [sys.executable, str(harness), str(REPO_ROOT), str(out_path),
             str(REPO_ROOT / script), *argv],
            cwd=str(cwd), env=env, capture_output=True, text=True, timeout=120,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            raise RuntimeError(
                f"probe harness exit {result.returncode} for {script}: {output.strip()}"
            )
        if "HARNESS-PROBE-ERROR" in output:
            raise RuntimeError(f"probe harness reported HARNESS-PROBE-ERROR for {script}: "
                               f"{output.strip()}")
        if out_path.exists() and out_path.stat().st_size:
            return set(json.loads(out_path.read_text()))
        raise RuntimeError(f"probe harness produced no collected paths for {script}")
    finally:
        out_path.unlink(missing_ok=True)


def _is_excluded(rel: str) -> bool:
    return any(rel.startswith(p) for p in EXCLUDE_PREFIXES)


def _local_import_targets(py_path: Path) -> set[str]:
    """Top-level `import X` / `from X import ...` module-name roots this file names, for the
    static safety net. Only the first dotted component is kept; stdlib/third-party names are
    filtered out by the caller (they will simply fail to resolve to a sibling file)."""
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def _resolve_sibling(py_path: Path, name: str) -> Path | None:
    """Resolve a bare import name to a sibling `.py` file or package `__init__.py` in the SAME
    directory as `py_path` — the only shape this repo's own tools use for their local imports
    (`import check_core`, `from acceptance_grammar import ...`, `import hashdomains`, etc.)."""
    base = py_path.parent
    candidate = base / f"{name}.py"
    if candidate.is_file():
        return candidate
    candidate = base / name / "__init__.py"
    if candidate.is_file():
        return candidate
    return None


def static_import_safety_net(root: Path, collected: set[str]) -> list[str]:
    """Belt-and-suspenders per the brief: fail when a collected file locally imports another repo
    module that the mechanical trace did not also collect. Returns a list of human-readable gap
    messages (empty = clean)."""
    gaps = []
    for rel in sorted(collected):
        if not rel.endswith(".py"):
            continue
        py_path = root / rel
        for name in sorted(_local_import_targets(py_path)):
            target = _resolve_sibling(py_path, name)
            if target is None:
                continue
            target_rel = str(target.relative_to(root))
            if _is_excluded(target_rel):
                continue
            if target_rel not in collected:
                gaps.append(f"{rel} imports {name!r} ({target_rel}) but the trace never opened it")
    return gaps


def discover_closure(root: Path) -> set[str]:
    harness_dir = Path(tempfile.mkdtemp(prefix="export_closure_harness_"))
    synthetic_dir = Path(tempfile.mkdtemp(prefix="export_closure_probe9_"))
    pycache_dir = Path(tempfile.mkdtemp(prefix="export_closure_pycache_"))
    try:
        harness = harness_dir / "_harness.py"
        harness.write_text(_HARNESS_SOURCE, encoding="utf-8")
        (synthetic_dir / "contract.toml").write_text(_SYNTHETIC_CONTRACT, encoding="utf-8")
        collected: set[str] = set(ENTRYPOINTS)
        for script, argv, cwd in _probes(synthetic_dir):
            collected |= _run_probe(script, argv, cwd, harness, pycache_dir)
        collected = {rel for rel in collected if not _is_excluded(rel)}
        missing_floor = sorted(COLLECTION_FLOOR - collected)
        if missing_floor:
            raise RuntimeError("probe collection missing required path(s): "
                               + ", ".join(missing_floor))
        return collected
    finally:
        shutil.rmtree(harness_dir, ignore_errors=True)
        shutil.rmtree(synthetic_dir, ignore_errors=True)
        shutil.rmtree(pycache_dir, ignore_errors=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# export / verify
# ---------------------------------------------------------------------------

def _decode_for_scan(path: Path, raw: bytes) -> tuple[str | None, str]:
    """`(decoded_text, "")` on success, `(None, reason)` on failure — NEVER a silent skip (an
    undecodable file, or a NUL byte in a text-typed file, is itself a hygiene FAILURE, not an
    exemption from scanning). `.py` files are decoded per their OWN declared encoding (PEP 263,
    `tokenize.detect_encoding`) rather than assumed UTF-8: a file whose forbidden tokens sit beside
    a `# coding: latin-1` declaration and a non-UTF-8 byte must still be caught, not silently
    skipped because a blind UTF-8 decode raised first."""
    if b"\x00" in raw:
        return None, "contains a NUL byte in a text-typed file"
    if path.suffix == ".py":
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        except (SyntaxError, UnicodeDecodeError) as exc:
            return None, f"tokenize.detect_encoding could not determine an encoding: {exc}"
        try:
            return raw.decode(encoding), ""
        except (UnicodeDecodeError, LookupError) as exc:
            return None, f"could not decode using its own declared encoding {encoding!r}: {exc}"
    try:
        return raw.decode("utf-8"), ""
    except UnicodeDecodeError as exc:
        return None, f"could not decode as UTF-8: {exc}"


def _scan_path_for_hygiene(dst: Path) -> list[tuple[int, str, str]]:
    """Reads `dst`'s raw bytes, decodes per `_decode_for_scan` (fail-closed), and returns
    `hygiene_violations()`-shaped hits — a decode failure is itself reported as a single
    `"undecodable"` hit, never treated as "nothing to scan"."""
    raw = dst.read_bytes()
    text, reason = _decode_for_scan(dst, raw)
    if text is None:
        return [(0, "undecodable", reason)]
    return hygiene_violations(text)


def cmd_export(dest: Path) -> int:
    # Check the caller's path before resolving: a dangling symlink also already exists.
    if os.path.lexists(dest):
        print(f"EXPORT REFUSED: --dest {dest} already exists; use a nonexistent destination.",
              file=sys.stderr)
        return 1
    dest = dest.resolve()
    if _dest_is_inside_repo(dest):
        print(
            f"EXPORT REFUSED: --dest {dest} is inside this repository ({REPO_ROOT}). Exporting "
            f"into the source checkout makes the export itself show up in `git status`, so "
            f"source_dirty would read true even from a clean tagged commit. Export outside the "
            f"checkout (a sibling directory, or your downstream crate's own vendor/ directory).",
            file=sys.stderr,
        )
        return 1
    if dest.exists():
        print(
            f"EXPORT REFUSED: --dest {dest} already exists. `export` requires a destination that "
            f"does NOT exist yet — it never overwrites, merges into, or deletes existing content "
            f"(a hygiene refusal used to `rmtree` whatever sat at `--dest`, including unrelated "
            f"pre-existing files; it no longer touches `--dest` at all until every check has "
            f"already passed). Re-vendoring an existing closure: move or remove the old directory "
            f"yourself first, or export to a fresh, versioned path.",
            file=sys.stderr,
        )
        return 1

    # Provenance is captured BEFORE any write below, and from a git call whose environment is
    # scrubbed of inherited GIT_* overrides — a clean tagged checkout must report
    # source_dirty = false regardless of what this process does next.
    try:
        family_version = _family_version(REPO_ROOT)
        source_commit = _source_commit(REPO_ROOT)
        source_dirty = _source_dirty(REPO_ROOT)
    except RuntimeError as exc:
        print(f"EXPORT REFUSED: could not determine source provenance: {exc}", file=sys.stderr)
        return 1

    try:
        collected = discover_closure(REPO_ROOT)
    except RuntimeError as exc:
        print(f"EXPORT REFUSED — closure discovery failed: {exc}", file=sys.stderr)
        return 1
    gaps = static_import_safety_net(REPO_ROOT, collected)
    if gaps:
        print("EXPORT REFUSED — closure incomplete (static safety net):", file=sys.stderr)
        for gap in gaps:
            print(f"  {gap}", file=sys.stderr)
        return 1

    # Copy byte-for-byte (no text decode, no transform of any kind) into a FRESH, UNIQUELY-NAMED
    # staging directory created NEXT TO `dest` (same parent — so the final move is a same-
    # filesystem rename, not a cross-filesystem copy), THEN scan the staged bytes and refuse on
    # any hit. On a hygiene failure, delete ONLY the staging directory — `dest` itself is never
    # created, let alone touched, until every check has already passed. `dest` is populated by
    # ONE atomic rename of the staging directory, after the scan is clean.
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{dest.name}.export-staging-", dir=str(dest.parent)))
    try:
        written: list[tuple[str, Path]] = []
        for rel in sorted(collected):
            src = REPO_ROOT / rel
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            written.append((rel, dst))
        exporter_dst = staging / EXPORTER_COPY_NAME
        shutil.copy2(Path(__file__).resolve(), exporter_dst)
        written.append((EXPORTER_COPY_NAME, exporter_dst))

        hygiene_errors = []
        for rel, dst in written:
            hits = _scan_path_for_hygiene(dst)
            if hits:
                hygiene_errors.append((rel, hits))
        if hygiene_errors:
            print("EXPORT REFUSED — apparatus hygiene scan found unhandled token(s) (or an "
                  "undecodable file, scanned fail-closed rather than skipped). No rewriting is "
                  "performed: fix the offending text IN THE SOURCE FILE (never the "
                  "CLASS-LOCK frozen spec text) and re-export.", file=sys.stderr)
            for rel, hits in hygiene_errors:
                for line_no, kind, line in hits:
                    print(f"  {rel}:{line_no} [{kind}] {line.strip()[:160]}", file=sys.stderr)
            return 1

        files = [{"path": rel, "sha256": _sha256(dst)} for rel, dst in written]
        manifest = {
            "family_version": family_version,
            "source_commit": source_commit,
            "source_dirty": source_dirty,
            "files": sorted(files, key=lambda f: f["path"]),
        }
        (staging / CLOSURE_FILE).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                             encoding="utf-8")
        # Only NOW, after every check has passed, does `dest` come into existence at all — one
        # same-filesystem rename (staging and dest share a parent), never a partial write visible
        # at the final path.
        if os.path.lexists(dest):
            print(f"EXPORT REFUSED: --dest {dest} appeared during export; leaving it intact.",
                  file=sys.stderr)
            return 1
        os.rename(staging, dest)
    finally:
        # A no-op once the rename above succeeded (the directory no longer exists at `staging`);
        # on any early return or exception, this removes ONLY the staging directory this call
        # itself created — `dest` was never touched, whether it exists, doesn't exist, or (per the
        # refusal above) already had unrelated content.
        shutil.rmtree(staging, ignore_errors=True)

    print(f"EXPORT OK: {len(files)} files -> {dest}")
    for f in manifest["files"]:
        print(f"  {f['path']}")
    print(f"  family_version={family_version} source_commit={source_commit} "
          f"source_dirty={source_dirty}")
    return 0


def _verify(dest: Path, *, expect_commit: str | None = None, require_clean: bool = False,
            expect_family_version: str | None = None) -> list[str]:
    """Returns a list of human-readable error strings (empty = clean). Standalone: reads only
    files under `dest`, no repository-layout dependency of any kind — this is what makes `verify`
    (and the CLI entry point below) safe to run from a relocated, source-repo-free copy."""
    manifest_path = dest / CLOSURE_FILE
    if not manifest_path.is_file():
        return [f"{manifest_path} missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = []
    if expect_commit is not None and manifest.get("source_commit") != expect_commit:
        errors.append("source_commit mismatch: expected "
                      f"{expect_commit}, got {manifest.get('source_commit')!r}")
    if require_clean and manifest.get("source_dirty") is not False:
        errors.append(f"source_dirty mismatch: expected false (--require-clean), "
                      f"got {manifest.get('source_dirty')!r}")
    if (expect_family_version is not None
            and manifest.get("family_version") != expect_family_version):
        errors.append("family_version mismatch: expected "
                      f"{expect_family_version!r}, got {manifest.get('family_version')!r}")
    listed = {}
    for entry in manifest.get("files", []):
        listed[entry["path"]] = entry["sha256"]
        target = dest / entry["path"]
        if not target.is_file():
            errors.append(f"missing: {entry['path']}")
            continue
        actual = _sha256(target)
        if actual != entry["sha256"]:
            errors.append(f"drift: {entry['path']} (expected {entry['sha256'][:16]}…, "
                           f"got {actual[:16]}…)")
    on_disk = set()
    for suffix in ("*.py", "*.toml", "*.md"):
        for path in dest.rglob(suffix):
            if "__pycache__" in path.parts:
                continue
            on_disk.add(str(path.relative_to(dest)))
    extra = sorted(on_disk - set(listed))
    for rel in extra:
        errors.append(f"extra: {rel} (present in {dest} but not in {CLOSURE_FILE})")
    # An interpreter can silently load cached bytecode instead of the verified .py source it
    # shadows — a vendored closure must ship source only, so ANY .pyc or __pycache__ anywhere
    # under dest is itself a violation, independent of the file-list checks above.
    for path in sorted(dest.rglob("*.pyc")):
        errors.append(f"bytecode: {path.relative_to(dest)} (a vendored closure ships source only)")
    for path in sorted(p for p in dest.rglob("__pycache__") if p.is_dir()):
        errors.append(f"bytecache-dir: {path.relative_to(dest)} "
                       f"(a vendored closure ships source only)")
    return errors


def cmd_verify(dest: Path, *, expect_commit: str | None = None, require_clean: bool = False,
               expect_family_version: str | None = None) -> int:
    errors = _verify(dest, expect_commit=expect_commit, require_clean=require_clean,
                     expect_family_version=expect_family_version)
    if errors:
        print(f"VERIFY FAIL ({len(errors)} issue(s)):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    manifest = json.loads((dest / CLOSURE_FILE).read_text(encoding="utf-8"))
    print(f"VERIFY PASS: {len(manifest['files'])} files match {CLOSURE_FILE}")
    return 0


# ---------------------------------------------------------------------------
# --selftest: export, py_compile every file, run the EXPORTED verifier standalone from a relocated
# copy, smoke-run every consumer verb with a RAISING audit hook enforcing zero reads from the
# source checkout, then a battery of able-to-fail controls.
# ---------------------------------------------------------------------------

_SMOKE_HARNESS_SOURCE = '''\
import os, sys, json, runpy, pathlib
forbidden_root = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2])
script = pathlib.Path(sys.argv[3]).resolve()

def _normalize(p):
    if isinstance(p, bytes):
        try:
            return p.decode("utf-8", "surrogateescape")
        except Exception:
            return None
    if isinstance(p, str):
        return p
    fspath = getattr(p, "__fspath__", None)
    if fspath is not None:
        try:
            return _normalize(fspath())
        except Exception:
            return None
    return None

def _hook(event, args):
    if event != "open":
        return
    p = _normalize(args[0])
    if p is None:
        return
    try:
        rp = pathlib.Path(p).resolve()
    except Exception:
        return
    try:
        rp.relative_to(forbidden_root)
    except ValueError:
        return
    # RAISE, do not merely record: this ABORTS the open() the moment it is attempted (Python
    # audit-hook semantics), so a forbidden read is prevented, not just noticed after the fact.
    raise PermissionError(f"forbidden read (source-checkout access denied by smoke harness): {rp}")

sys.addaudithook(_hook)
sys.path.insert(0, str(script.parent))
sys.argv = [str(script)] + sys.argv[4:]
exit_code = None
exception = None
try:
    runpy.run_path(str(script), run_name="__main__")
    exit_code = 0
except SystemExit as e:
    if e.code is None:
        exit_code = 0
    elif isinstance(e.code, int):
        exit_code = e.code
    else:
        exit_code = 1
except BaseException as exc:
    exception = repr(exc)
forbidden_modules = []
for _name, _mod in list(sys.modules.items()):
    f = getattr(_mod, "__file__", None)
    if not f:
        continue
    try:
        rp = pathlib.Path(f).resolve()
        rp.relative_to(forbidden_root)
    except (ValueError, OSError):
        continue
    forbidden_modules.append(str(rp))
out.write_text(json.dumps({
    "exit_code": exit_code,
    "exception": exception,
    "forbidden_modules": sorted(set(forbidden_modules)),
}))
'''


def _run_smoke(script: Path, argv: tuple[str, ...], cwd: Path, forbidden_root: Path,
               harness: Path) -> dict:
    """Runs `script argv...` (an exported entry point) with cwd=`cwd`, under `-I -B` (isolated
    mode: ignores PYTHONPATH/site/user config; `-B`: never writes bytecode), PLUS an in-process
    audit hook that RAISES the moment any `open()` (string, bytes, or PathLike path, all
    normalized) resolves under `forbidden_root` — this PREVENTS the read, it does not merely
    record it afterward.

    Scope, stated precisely rather than assumed: the audit hook covers everything that runs
    in-process via `runpy` in THIS one interpreter. None of the consumer verbs this selftest
    exercises spawn a child process of their own (`check_acceptance.py`'s `validate`,
    `acceptance_protocol.py`'s `check-contract`/`check-package`/`coverage`/`check-decision`/
    `check-states`/`decide`, and `spec_inventory.py`'s `make`/`check`/`digest` are in-process file/TOML/
    Markdown parsing — verified by reading each: the only `subprocess`/git-shelling code paths in
    `acceptance_protocol.py` belong to `assemble-package`/`project-brief`, which this selftest
    never calls). A future verb that shells out would need its own child-process bootstrap; this
    one does not need it today, and the planted forbidden-read control below proves the hook that
    IS active actually fires, rather than merely being present and silent."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        out_path = Path(tf.name)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONSTARTUP")}
    try:
        process = subprocess.run(
            [sys.executable, "-I", "-B", str(harness), str(forbidden_root), str(out_path),
             str(script), *argv],
            cwd=str(cwd), env=env, capture_output=True, text=True, timeout=120,
        )
        if out_path.exists() and out_path.stat().st_size:
            result = json.loads(out_path.read_text())
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            return result
        return {"exit_code": None, "exception": "harness produced no output",
                "forbidden_modules": []}
    finally:
        out_path.unlink(missing_ok=True)


def _smoke_problems(result: dict, expected_exit: int, label: str) -> list[str]:
    """Returns violation strings (empty = clean). A caller both ENFORCES this (fail if nonempty)
    and USES it as an able-to-fail control (assert nonempty on a deliberately broken input)."""
    problems = []
    if result.get("exception"):
        problems.append(f"{label}: raised {result['exception']!r} (expected a clean CLI exit)")
    if result.get("exit_code") != expected_exit:
        problems.append(f"{label}: exit {result.get('exit_code')!r} (expected {expected_exit})")
    if result.get("forbidden_modules"):
        problems.append(
            f"{label}: loaded a module from the source checkout: {result['forbidden_modules']}"
        )
    return problems


def _py_compile_all(root: Path) -> list[str]:
    """Compiles every exported `.py` file in a SUBPROCESS: a text-transform bug that broke a
    string literal was caught only by RUNNING the exported copy, never by this repo's own
    untouched source passing its own selftest — compiling the actual exported bytes is the cheap,
    mechanical, always-on check that a rewrite bug like that cannot slip through again.

    Compiles to a throwaway temp file explicitly (never `python3 -m py_compile FILE`, which writes
    a real `__pycache__/*.pyc` next to the source, and never `os.devnull` — some interpreter
    builds refuse to byte-compile onto a non-regular file): this check must not itself create the
    bytecode `verify` correctly rejects a vendored closure for carrying."""
    errors = []
    with tempfile.TemporaryDirectory(prefix="export_closure_pycompile_") as scratch:
        cfile = str(Path(scratch) / "out.pyc")
        for path in sorted(root.rglob("*.py")):
            result = subprocess.run(
                [sys.executable, "-c",
                 "import py_compile, sys; "
                 "py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)",
                 str(path), cfile],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                errors.append(f"{path.relative_to(root)}: py_compile failed:\n{result.stderr}")
    return errors


def _selftest_export_refusals(root: Path) -> bool:
    """Exercise real copy/scan/cleanup on synthetic source bytes; mock only discovery/provenance.
    The normal export selftest separately checks real discovery and git provenance."""
    from contextlib import redirect_stderr
    from unittest.mock import patch

    source = root / "source"
    source.mkdir(exist_ok=True)
    existing = root / "existing"
    existing.mkdir()
    sentinel = existing / "keep.bin"
    sentinel.write_bytes(b"unrelated destination content\x00\xff")
    saved = sentinel.read_bytes()
    existing_file = root / "existing-file"
    existing_file.write_bytes(saved)
    dangling = root / "dangling"
    dangling.symlink_to(root / "absent-target")
    for dest in (existing, existing_file, dangling):
        with redirect_stderr(io.StringIO()) as err:
            rc = cmd_export(dest)
        if rc != 1 or "already exists" not in err.getvalue():
            print(f"SELFTEST FAIL: existing destination was not refused: {dest}", file=sys.stderr)
            return False
    if (sentinel.read_bytes() != saved or existing_file.read_bytes() != saved
            or list(existing.iterdir()) != [sentinel] or not dangling.is_symlink()
            or (root / "absent-target").exists()):
        print("SELFTEST FAIL: existing destination contents changed", file=sys.stderr)
        return False
    print("SELFTEST: export refused existing destinations; contents and dangling symlink survived")

    latin1 = ("# coding: latin-1\n# café\nvalue = " + repr(_tok("as", "tra")) + "\n").encode("latin-1")
    compile(latin1, "latin1.py", "exec")  # Valid Python, not merely malformed bytes.
    cases = (
        ("latin1.py", latin1, "reviewer-name"),
        ("bad-python.py", b"# coding: utf-8\n# \xff\n", "undecodable"),
        ("bad-cookie.py", b"# coding: no-such-codec\nx = 1\n", "undecodable"),
        ("bad-text.md", b"# \xff\n", "undecodable"),
        ("bad-policy.toml", b"# \xff\n", "undecodable"),
        ("nul-python.py", b"# \x00\n", "undecodable"),
        ("nul-text.md", b"# \x00\n", "undecodable"),
        ("nul-policy.toml", b"# \x00\n", "undecodable"),
    )
    for name, raw, kind in cases:
        payload = source / name
        payload.write_bytes(raw)
        dest = root / "refused"
        before = set(root.iterdir())
        with patch.multiple(
            sys.modules[__name__], REPO_ROOT=source,
            discover_closure=lambda _: {name}, _family_version=lambda _: "0.3.1",
            _source_commit=lambda _: "0" * 40, _source_dirty=lambda _: False,
        ), redirect_stderr(io.StringIO()) as err:
            rc = cmd_export(dest)
        if (rc != 1 or f"{name}:" not in err.getvalue() or f"[{kind}]" not in err.getvalue()
                or set(root.iterdir()) != before or payload.read_bytes() != raw
                or sentinel.read_bytes() != saved):
            print(f"SELFTEST FAIL: hygiene refusal/cleanup failed for {name}: {err.getvalue()}",
                  file=sys.stderr)
            return False
        print(f"SELFTEST: export refused {name} [{kind}]; only its staging directory was removed")
        payload.unlink()
    print("SELFTEST: compilable latin-1 forbidden token, undecodable files, and NUL text all refused")
    return True


def _selftest_probe_refusals(root: Path) -> bool:
    """Prove each closure-discovery refusal reaches `export` with its named reason."""
    from contextlib import redirect_stderr
    from unittest.mock import patch

    source = root / "source"
    source.mkdir(exist_ok=True)

    def export_refuses(reason: str, label: str) -> bool:
        destination = root / f"refused-{label}"

        def fail_discovery(_root: Path) -> set[str]:
            raise RuntimeError(reason)

        with patch.multiple(
            sys.modules[__name__], REPO_ROOT=source,
            _family_version=lambda _: "0.3.1", _source_commit=lambda _: "0" * 40,
            _source_dirty=lambda _: False, discover_closure=fail_discovery,
        ), redirect_stderr(io.StringIO()) as err:
            rc = cmd_export(destination)
        return (rc == 1 and "EXPORT REFUSED — closure discovery failed" in err.getvalue()
                and reason in err.getvalue() and not destination.exists())

    probe_cases = (
        ("nonzero-exit", subprocess.CompletedProcess([], 7, "", "probe stopped"),
         "probe harness exit 7"),
        ("reported-error", subprocess.CompletedProcess([], 0, "", "HARNESS-PROBE-ERROR: boom"),
         "HARNESS-PROBE-ERROR"),
    )
    for label, completed, reason in probe_cases:
        with patch.object(subprocess, "run", return_value=completed):
            try:
                _run_probe("probe.py", [], root, root / "harness.py", root / "pycache")
            except RuntimeError as exc:
                caught = reason in str(exc)
            else:
                caught = False
        if not caught or not export_refuses(reason, label):
            print(f"SELFTEST FAIL: export did not refuse probe {label} for {reason!r}",
                  file=sys.stderr)
            return False
        print(f"SELFTEST: export correctly REFUSED probe {label} [{reason}]")

    with patch.multiple(sys.modules[__name__], REPO_ROOT=source,
                        _run_probe=lambda *_args: set()):
        try:
            discover_closure(source)
        except RuntimeError as exc:
            floor_reason = str(exc)
        else:
            floor_reason = ""
    if ("probe collection missing required path(s)" not in floor_reason
            or not export_refuses(floor_reason, "missing-floor")):
        print("SELFTEST FAIL: export did not refuse a probe collection missing its required floor",
              file=sys.stderr)
        return False
    print("SELFTEST: export correctly REFUSED a probe collection missing its required floor")
    return True


def _selftest_verify_provenance(dest: Path, manifest: dict) -> bool:
    """Exercise each consumer provenance option both green and red against CLOSURE.json."""
    from contextlib import redirect_stderr

    manifest_path = dest / CLOSURE_FILE
    original = manifest_path.read_text(encoding="utf-8")

    def write(current: dict) -> None:
        manifest_path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")

    def alternate_40(value: str) -> str:
        return ("0" if value[0] != "0" else "1") + value[1:]

    def red(reason: str, **kwargs) -> bool:
        with redirect_stderr(io.StringIO()) as err:
            rc = cmd_verify(dest, **kwargs)
        return rc == 1 and reason in err.getvalue()

    try:
        # --expect-commit: matching manifest value is green, a changed CLOSURE.json is red.
        if cmd_verify(dest, expect_commit=manifest["source_commit"]) != 0:
            return False
        changed = dict(manifest)
        changed["source_commit"] = alternate_40(manifest["source_commit"])
        write(changed)
        if not red("source_commit mismatch:", expect_commit=manifest["source_commit"]):
            return False

        # --require-clean: a clean manifest is green and source_dirty=true is named as red.
        clean = dict(manifest)
        clean["source_dirty"] = False
        write(clean)
        if cmd_verify(dest, require_clean=True) != 0:
            return False
        dirty = dict(clean)
        dirty["source_dirty"] = True
        write(dirty)
        if not red("source_dirty mismatch:", require_clean=True):
            return False

        # --expect-family-version follows the same green/red contract.
        write(manifest)
        if cmd_verify(dest, expect_family_version=manifest["family_version"]) != 0:
            return False
        changed = dict(manifest)
        changed["family_version"] = manifest["family_version"] + "-mismatch"
        write(changed)
        if not red("family_version mismatch:",
                   expect_family_version=manifest["family_version"]):
            return False
    finally:
        manifest_path.write_text(original, encoding="utf-8")

    print("SELFTEST: verify provenance expectations correctly refused source_commit, source_dirty, "
          "and family_version mismatches (able-to-fail controls)")
    return True


def _selftest_family_version(root: Path) -> None:
    root.mkdir()
    payload = root / "payload"
    payload.write_bytes(b"class text")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    lock = root / "CLASS-LOCK.toml"
    clean_lock = ('[[lock]]\nversion="0.3.2"\ndate="2026-09-27"\n'
                  'ratified=false\nreason="Public release."\n[lock.files]\n'
                  f'payload="{digest}"\n')
    lock.write_text(clean_lock)
    assert _family_version(root) == "0.3.2"
    receipt = root / "EXPORT-PROVENANCE.json"
    receipt.write_text(json.dumps({"family_version": "0.3.2",
                                  "files": {"payload": {"sha256": digest}}}))
    lock.unlink()
    assert _family_version(root) == "0.3.2"
    for label, mutate in (
        ("receipt drift", lambda: payload.write_bytes(b"changed")),
        ("empty lock", lambda: lock.write_text("lock=[]\n")),
        ("lock drift", lambda: lock.write_text(clean_lock)),
    ):
        mutate()
        try:
            _family_version(root)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"accepted {label}")
    print("SELFTEST: public lock and receipt readers accepted clean metadata and refused drift and empty lock")


def selftest() -> int:  # noqa: C901 -- a linear checklist, not meaningfully splittable
    with tempfile.TemporaryDirectory(prefix="export_closure_selftest_") as td:
        td_path = Path(td)
        dest = td_path / "closure"
        smoke = td_path / "smoke"
        _selftest_family_version(td_path / "family-metadata")

        # --- able-to-fail control 0: the hygiene scanner itself, and confirmation it never
        # self-matches its own pattern-definition lines (the bug this whole redesign fixes).
        planted = _tok("See ", "~", "/repo/", "acceptance-format/tools/x.py and the ",
                        _tok("as", "tra"), " review finding 3.")
        if not hygiene_violations(planted):
            print("SELFTEST FAIL (able-to-fail control): a planted home-path/reviewer-name token "
                  "was not caught by hygiene_violations()", file=sys.stderr)
            return 1
        print("SELFTEST: hygiene scan correctly caught a planted home-path/reviewer-name token "
              "(able-to-fail control)")
        own_source = Path(__file__).resolve().read_text(encoding="utf-8")
        own_hits = hygiene_violations(own_source)
        if own_hits:
            print("SELFTEST FAIL: this file's OWN pattern-definition lines self-match its "
                  "hygiene scan (the exact bug this redesign exists to prevent):", file=sys.stderr)
            for h in own_hits:
                print(f"  {h}", file=sys.stderr)
            return 1
        print("SELFTEST: this file's own source passes its own hygiene scan (no self-match)")

        # --- able-to-fail control 0b: _SOL_NAME_RE is case-sensitive on purpose (a lowercase
        # "sol" is an ordinary word/abbreviation, not the reviewer's name) — prove both directions.
        sol_planted = _tok("S", "ol") + " raised this in round 4."
        sol_hits = hygiene_violations(sol_planted)
        if not sol_hits or sol_hits[0][1] != "reviewer-name":
            print("SELFTEST FAIL (able-to-fail control): a planted capitalized reviewer-name "
                  "token was not caught by hygiene_violations()", file=sys.stderr)
            return 1
        sol_benign = _tok("s", "ol") + " invictus was an ancient roman festival."
        if hygiene_violations(sol_benign):
            print("SELFTEST FAIL (false-positive control): the lowercase common word wrongly "
                  "caught by hygiene_violations() — _SOL_NAME_RE must stay case-sensitive",
                  file=sys.stderr)
            return 1
        print("SELFTEST: hygiene scan catches the capitalized reviewer name but not the "
              "lowercase common word (case-sensitive able-to-fail + false-positive controls)")

        refusal_root = td_path / "refusal-controls"
        refusal_root.mkdir()
        if not _selftest_export_refusals(refusal_root):
            return 1
        if not _selftest_probe_refusals(refusal_root):
            return 1

        # Ground truth, measured INDEPENDENTLY of `cmd_export` (a separate git call), for the
        # provenance-ordering regression guard below. This selftest runs inside an actively-being-
        # developed worktree, so it deliberately does NOT assert `source_dirty is False` — the
        # ambient repo may legitimately be dirty (uncommitted work in progress). What it DOES
        # assert is that exporting to a destination OUTSIDE the repo never CHANGES that ground
        # truth (the original bug: sampling `source_dirty` AFTER copying files into a `vendor/`
        # dir INSIDE the repo made even a clean checkout read dirty).
        expected_dirty = _source_dirty(REPO_ROOT)

        rc = cmd_export(dest)
        if rc != 0:
            print("SELFTEST FAIL: export did not succeed", file=sys.stderr)
            return 1
        if not (dest / CLOSURE_FILE).is_file():
            print("SELFTEST FAIL: CLOSURE.json missing after export", file=sys.stderr)
            return 1
        manifest = json.loads((dest / CLOSURE_FILE).read_text())
        n_files = len(manifest["files"])
        if n_files < len(ENTRYPOINTS) + 1:  # +1: the exporter now manifests itself
            print(f"SELFTEST FAIL: only {n_files} files exported", file=sys.stderr)
            return 1
        if manifest["source_dirty"] != expected_dirty:
            print(f"SELFTEST FAIL: exporting to a temp dir OUTSIDE the repo changed the measured "
                  f"source_dirty ({expected_dirty!r} before export, "
                  f"{manifest['source_dirty']!r} in the manifest) — provenance capture is not "
                  f"actually independent of the export destination", file=sys.stderr)
            return 1
        if EXPORTER_COPY_NAME not in {f["path"] for f in manifest["files"]}:
            print("SELFTEST FAIL: the exporter's own copy is not in CLOSURE.json's file list",
                  file=sys.stderr)
            return 1
        print(f"SELFTEST: exported {n_files} files, source_dirty={manifest['source_dirty']} "
              f"(unchanged by exporting outside the repo)")

        if not _selftest_verify_provenance(dest, manifest):
            print("SELFTEST FAIL: verify provenance expectations did not distinguish matching "
                  "and mismatching CLOSURE.json values", file=sys.stderr)
            return 1

        # --- compile EVERY exported .py file in a subprocess.
        compile_errors = _py_compile_all(dest)
        if compile_errors:
            print("SELFTEST FAIL: py_compile failed on the exported copy (this is the exact "
                  "class of bug a prior text-transform round introduced):", file=sys.stderr)
            for e in compile_errors:
                print(f"  {e}", file=sys.stderr)
            return 1
        print(f"SELFTEST: py_compile succeeded on all {len(list(dest.rglob('*.py')))} exported "
              f".py files")

        # --- run the EXPORTED verifier, as a real subprocess, from a SECOND, relocated copy
        # (proving no hidden dependency on this repo's own layout survives a move).
        relocated = td_path / "relocated_closure"
        shutil.copytree(dest, relocated)
        result = subprocess.run(
            [sys.executable, str(relocated / EXPORTER_COPY_NAME), "verify", "--dest", str(relocated)],
            capture_output=True, text=True, timeout=60,
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        )
        if result.returncode != 0 or "VERIFY PASS" not in result.stdout:
            print(f"SELFTEST FAIL: the EXPORTED verifier, run standalone from a relocated copy "
                  f"(the exact documented downstream command), did not pass:\n"
                  f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}",
                  file=sys.stderr)
            return 1
        print(f"SELFTEST: the exported verifier ran standalone from a relocated copy "
              f"({relocated}), the exact documented downstream command -> {result.stdout.strip()}")

        # --- reject-a-dest-inside-the-repo control: NEVER deletes anything. If the probe path
        # already exists for any reason, this control is skipped rather than risking real
        # repository content; otherwise it asserts refusal AND that nothing was created, and
        # creates/removes nothing itself either way.
        probe_name = "export_closure_selftest_probe_must_not_exist"
        inside = REPO_ROOT / probe_name
        if inside.exists():
            print(f"SELFTEST: skipping the in-repo-destination refusal control — {inside} "
                  f"already exists (this selftest must never touch pre-existing repository "
                  f"content)")
        else:
            rc_inside = cmd_export(inside)
            if rc_inside == 0:
                print("SELFTEST FAIL (able-to-fail control): export into the source checkout "
                      "was not refused", file=sys.stderr)
                return 1
            if inside.exists():
                print(f"SELFTEST FAIL: export refused a --dest inside the repo but created "
                      f"{inside} anyway — refusal must happen before any write, and this "
                      f"selftest will not delete it for you", file=sys.stderr)
                return 1
            print("SELFTEST: export correctly REFUSED a --dest inside the source checkout, "
                  "creating nothing (verified: the path still does not exist)")

        # Smoke fixture: a self-contained copy of the worked example, its OWN throwaway git repo
        # (GIT_* scrubbed, hooks disabled), never touching REPO_ROOT.
        shutil.copytree(REPO_ROOT / _RUST_DELIVERY, smoke)
        _git(smoke, "init", "-q")
        _git(smoke, "config", "user.email", "probe@example.invalid")
        _git(smoke, "config", "user.name", "probe")

        smoke_harness_dir = Path(tempfile.mkdtemp(prefix="export_closure_smoke_harness_"))
        try:
            harness = smoke_harness_dir / "_smoke_harness.py"
            harness.write_text(_SMOKE_HARNESS_SOURCE, encoding="utf-8")

            # --- negative control: a script that DELIBERATELY tries to read a file inside the
            # forbidden root must be CAUGHT — proves the hook fires, not merely exists.
            planted_reader = smoke_harness_dir / "_planted_forbidden_read.py"
            planted_reader.write_text(
                "import sys, pathlib\n"
                "target = pathlib.Path(sys.argv[1])\n"
                "sys.exit(0 if target.read_text() else 1)\n",
                encoding="utf-8",
            )
            result = _run_smoke(planted_reader, (str(REPO_ROOT / "CLASS-LOCK.toml"),), smoke,
                                 REPO_ROOT, harness)
            if not result.get("exception") or "PermissionError" not in result["exception"]:
                print(f"SELFTEST FAIL (able-to-fail control): a script that deliberately reads "
                      f"a file inside the source checkout was NOT stopped by the audit hook: "
                      f"{result}", file=sys.stderr)
                return 1
            print("SELFTEST: the audit hook correctly RAISED and blocked a planted forbidden "
                  "read (able-to-fail control)")

            # --- golden path: every consumer verb the adoption guide documents.
            golden_checks = [
                ("format_acceptance/tools/check_acceptance.py",
                 ("--strict", "--strict-weight", "acceptance.toml"), 0),
                ("protocol_acceptance/tools/acceptance_protocol.py",
                 ("check-contract", "acceptance-contract.toml"), 0),
                ("protocol_acceptance/tools/acceptance_protocol.py",
                 ("check-package", "acceptance.toml", "--contract", "acceptance-contract.toml"), 0),
                ("protocol_acceptance/tools/acceptance_protocol.py",
                 ("coverage", "acceptance.toml", "--contract", "acceptance-contract.toml"), 0),
                ("protocol_acceptance/tools/acceptance_protocol.py",
                 ("check-decision", "acceptance-decision.toml", "--contract",
                  "acceptance-contract.toml", "--package", "acceptance.toml"), 0),
                ("protocol_acceptance/tools/acceptance_protocol.py", ("check-states",), 0),
                ("protocol_acceptance/tools/acceptance_protocol.py",
                 ("decide", "acceptance.toml", "--contract", "acceptance-contract.toml",
                  "--issuer", "probe / lead", "--out", "smoke-decision-skeleton.toml",
                  "--mode", "re-execute-all"), 0),
            ]
            for script_rel, args, expected in golden_checks:
                result = _run_smoke(dest / script_rel, args, smoke, REPO_ROOT, harness)
                problems = _smoke_problems(result, expected, f"{script_rel} {' '.join(args)}")
                if problems:
                    print("SELFTEST FAIL:", file=sys.stderr)
                    for p in problems:
                        print(f"  {p}", file=sys.stderr)
                    return 1
                print(f"SELFTEST: {script_rel} {' '.join(args)} -> exit {result['exit_code']} "
                      f"(no source-checkout reads permitted; exact expected exit)")
            (smoke / "smoke-decision-skeleton.toml").unlink(missing_ok=True)

            # --- exercise the assurance-table path from the exported copy.
            (smoke / "probe-assurance-contract.toml").write_text(_SYNTHETIC_CONTRACT,
                                                                   encoding="utf-8")
            result = _run_smoke(
                dest / "protocol_acceptance/tools/acceptance_protocol.py",
                ("check-contract", "probe-assurance-contract.toml"), smoke, REPO_ROOT, harness,
            )
            problems = _smoke_problems(result, 0, "check-contract (assurance-table path)")
            if problems:
                print("SELFTEST FAIL:", file=sys.stderr)
                for p in problems:
                    print(f"  {p}", file=sys.stderr)
                return 1
            print("SELFTEST: check-contract exercised the assurance-table path "
                  f"(assurance-classes.toml) -> exit {result['exit_code']}")

            # --- exercise the spec-inventory path from the exported copy.
            (smoke / "PROBE-SPEC.md").write_text("## S-1\nProbe heading.\n", encoding="utf-8")
            result_make = _run_smoke(
                dest / "format_acceptance/tools/spec_inventory.py",
                ("make", "PROBE-SPEC.md"), smoke, REPO_ROOT, harness,
            )
            problems = _smoke_problems(result_make, 0, "spec_inventory.py make (inventory path)")
            if problems:
                print("SELFTEST FAIL:", file=sys.stderr)
                for p in problems:
                    print(f"  {p}", file=sys.stderr)
                return 1
            print(f"SELFTEST: spec_inventory.py make exercised the inventory path -> "
                  f"exit {result_make['exit_code']}")
            inventory = smoke / "PROBE-INVENTORY.toml"
            inventory.write_text(result_make["stdout"], encoding="utf-8")
            expected_digest = "inventory:sha-512:" + hashlib.sha512(
                b"inventory:" + inventory.read_bytes()
            ).hexdigest()
            for args, expected_output in (
                (("check", "PROBE-SPEC.md", inventory.name), "CLEAN "),
                (("digest", inventory.name), expected_digest),
            ):
                result = _run_smoke(dest / "format_acceptance/tools/spec_inventory.py", args,
                                    smoke, REPO_ROOT, harness)
                problems = _smoke_problems(result, 0, f"spec_inventory.py {args[0]}")
                if problems or not result.get("stdout", "").startswith(expected_output):
                    print(f"SELFTEST FAIL: inventory {args[0]}: {problems}; {result}",
                          file=sys.stderr)
                    return 1
                print(f"SELFTEST: spec_inventory.py {args[0]} exercised the inventory path -> "
                      "exit 0 (no source-checkout reads permitted; output checked)")

            # --- able-to-fail control mirroring an earlier round's own exact repro: a
            # missing Rust binding document must be CAUGHT (INDETERMINATE/exit 2), not silently
            # accepted just because stderr carries no traceback text.
            broken = td_path / "closure_broken"
            shutil.copytree(dest, broken)
            (broken / "format_acceptance/profiles/bindings/code/rust.md").unlink()
            result = _run_smoke(
                broken / "format_acceptance/tools/check_acceptance.py",
                ("--strict", "--strict-weight", "acceptance.toml"), smoke, REPO_ROOT, harness,
            )
            problems = _smoke_problems(result, 0, "corrupted-export (missing binding doc)")
            if not problems:
                print("SELFTEST FAIL (able-to-fail control): a broken export (missing Rust "
                      "binding document) was NOT caught by the smoke assertion", file=sys.stderr)
                return 1
            print(f"SELFTEST: smoke assertion correctly caught a broken export "
                  f"(missing binding doc): {problems[0]}")
        finally:
            shutil.rmtree(smoke_harness_dir, ignore_errors=True)

        # --- verify() PASSES on an untouched export.
        if cmd_verify(dest) != 0:
            print("SELFTEST FAIL: verify did not pass on a clean export", file=sys.stderr)
            return 1

        # --- able-to-fail control: corrupt one byte of one exported file; verify MUST fail.
        victim = dest / "format_acceptance/tools/check_core.py"
        original = victim.read_bytes()
        victim.write_bytes(bytes([original[0] ^ 0xFF]) + original[1:])
        errors = _verify(dest)
        if not any(e.startswith("drift:") for e in errors):
            print("SELFTEST FAIL (able-to-fail control): verify did not report drift on a "
                  "corrupted file", file=sys.stderr)
            return 1
        print("SELFTEST: verify correctly reported DRIFT on a one-byte corruption "
              "(able-to-fail control)")
        victim.write_bytes(original)
        if cmd_verify(dest) != 0:
            print("SELFTEST FAIL: verify did not pass again after restoring the byte",
                  file=sys.stderr)
            return 1

        # --- able-to-fail control: a missing manifested file must be reported "missing".
        victim2 = dest / "format_acceptance/tools/hashdomains.py"
        saved2 = victim2.read_bytes()
        victim2.unlink()
        errors = _verify(dest)
        if not any(e.startswith("missing:") for e in errors):
            print("SELFTEST FAIL (able-to-fail control): verify did not report a deleted "
                  "manifested file as missing", file=sys.stderr)
            return 1
        print("SELFTEST: verify correctly reported MISSING on a deleted file "
              "(able-to-fail control)")
        victim2.write_bytes(saved2)
        if cmd_verify(dest) != 0:
            print("SELFTEST FAIL: verify did not pass again after restoring the deleted file",
                  file=sys.stderr)
            return 1

        # --- able-to-fail control: an extra untracked file must be reported "extra".
        stray = dest / "format_acceptance/tools/_stray_untracked_probe.py"
        stray.write_text("# stray file, not in CLOSURE.json\n", encoding="utf-8")
        errors = _verify(dest)
        if not any(e.startswith("extra:") for e in errors):
            print("SELFTEST FAIL (able-to-fail control): verify did not report a stray extra "
                  "file", file=sys.stderr)
            return 1
        print("SELFTEST: verify correctly reported EXTRA on a stray untracked file "
              "(able-to-fail control)")
        stray.unlink()
        if cmd_verify(dest) != 0:
            print("SELFTEST FAIL: verify did not pass again after removing the stray file",
                  file=sys.stderr)
            return 1

        # --- able-to-fail control: tampering with the manifested EXPORTER copy itself must be
        # caught (the exporter/verifier was previously exempt from its own manifest).
        victim3 = dest / EXPORTER_COPY_NAME
        saved3 = victim3.read_bytes()
        victim3.write_bytes(saved3 + b"\n# tampered\n")
        errors = _verify(dest)
        if not any(e.startswith("drift:") and EXPORTER_COPY_NAME in e for e in errors):
            print("SELFTEST FAIL (able-to-fail control): verify did not catch tampering with "
                  "its own manifested exporter copy", file=sys.stderr)
            return 1
        print("SELFTEST: verify correctly caught tampering with the manifested EXPORTER copy "
              "itself (able-to-fail control)")
        victim3.write_bytes(saved3)
        if cmd_verify(dest) != 0:
            print("SELFTEST FAIL: verify did not pass again after restoring the exporter copy",
                  file=sys.stderr)
            return 1

        # --- able-to-fail control: a stray .pyc/__pycache__ under dest must be rejected.
        pycache_dir = dest / "format_acceptance/tools/__pycache__"
        pycache_dir.mkdir(exist_ok=True)
        (pycache_dir / "check_core.cpython-000.pyc").write_bytes(b"\x00\x00\x00\x00")
        errors = _verify(dest)
        if not any(e.startswith("bytecode:") or e.startswith("bytecache-dir:") for e in errors):
            print("SELFTEST FAIL (able-to-fail control): verify did not reject a stray "
                  "__pycache__/*.pyc under the export", file=sys.stderr)
            return 1
        print("SELFTEST: verify correctly REJECTED a stray __pycache__/*.pyc "
              "(able-to-fail control)")
        shutil.rmtree(pycache_dir)
        if cmd_verify(dest) != 0:
            print("SELFTEST FAIL: verify did not pass again after removing the stray "
                  "__pycache__", file=sys.stderr)
            return 1

    print("SELFTEST PASS: export_closure")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="export_closure.py")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="verb")

    sp = sub.add_parser("export")
    sp.add_argument("--dest", required=True, type=Path)

    sp = sub.add_parser("verify")
    sp.add_argument("--dest", required=True, type=Path)
    sp.add_argument("--expect-commit", metavar="40HEX",
                    type=lambda value: value if re.fullmatch(r"[0-9a-f]{40}", value)
                    else (_ for _ in ()).throw(argparse.ArgumentTypeError(
                        "must be exactly 40 lowercase hexadecimal characters")))
    sp.add_argument("--require-clean", action="store_true")
    sp.add_argument("--expect-family-version", metavar="VERSION")

    args = parser.parse_args(argv[1:])
    if args.selftest:
        return selftest()
    if args.verb == "export":
        return cmd_export(args.dest)
    if args.verb == "verify":
        return cmd_verify(args.dest.resolve(), expect_commit=args.expect_commit,
                          require_clean=args.require_clean,
                          expect_family_version=args.expect_family_version)
    parser.error("one of --selftest, export --dest DIR, verify --dest DIR is required")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
