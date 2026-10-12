#!/usr/bin/env python3
"""gen_packages.py — produces the three INTRINSIC (producer-only) `acceptance.toml` packages
(`geom-math/`, `raster-draw/`, `paint-app/`) and paint-app's specification-bound
`acceptance-package.toml`, by ACTUALLY RUNNING `cargo test`, `cargo clippy`, `cargo kani` and real,
restored mutation controls against the real crates in this directory. Pure stdlib, python3.11+.

Follows `../rust-delivery/gen_package.py`'s pattern (fixed buffers for Kani, apply/run/require-red/
restore/verify-byte-equal for mutation controls, real toolchain identity from `-vV`/`--verbose`)
generalized over three crates plus a fourth, specification-bound package for paint-app. Record hashes
use the 0.3.1-errata TYPED wire (`hashdomains.digest("record:", ...)`), not m11's legacy untyped
`evidence-record` domain; see `format_acceptance/spec/hash-domains.md`.

DO NOT HAND-EDIT any generated `acceptance.toml`/`acceptance-package.toml`/`evidence/*` — re-run
this script. Usage: python3 gen_packages.py
"""
from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
import time
import tomllib

from transcripts import normalize
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

TOOLS_DIR = SCRIPT_DIR.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
import m11  # noqa: E402

sys.path.insert(0, str(SCRIPT_DIR.parent.parent.parent / "format_acceptance" / "tools"))
import hashdomains  # noqa: E402

PROFILE_ID = "acceptance/verification/code/rust"
TODAY = datetime.date.today().isoformat()


# --------------------------------------------------------------------------
# Small helpers (same shapes as ../rust-delivery/gen_package.py)
# --------------------------------------------------------------------------

def run(cmd, cwd, timeout=180, env=None):
    t0 = time.monotonic()
    full_env = {**os.environ, **env} if env else None
    proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           timeout=timeout, env=full_env)
    return proc.returncode, normalize(proc.stdout), time.monotonic() - t0


# Cross-vendor review 2026-09-26, Major #4: `cargo doc --no-deps` alone exits 0 and still prints
# "Generated" even with a broken intra-doc link (a WARNING, not an error) -- the exact string
# gen_packages.py's own self_verify.expect checks for, and exactly the condition a consumer
# re-running the RECORDED recipe (make_decision.py) would also treat as a pass. `RUSTDOCFLAGS`
# must be set identically at every one of: this generator's baseline run, this generator's mutation
# CONTROL run, the RECORDED recipe string (self_verify.command / watched_fail.of_command — what a
# consumer actually re-executes), and the consumer's own rerun (make_decision.py) — otherwise the
# "control" only proves something about a command nobody's re-execution actually runs.
DOC_ENV = {"RUSTDOCFLAGS": "-D warnings"}
DOC_COMMAND = 'RUSTDOCFLAGS="-D warnings" cargo doc --no-deps'


def git(args, cwd):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def q(s: str) -> str:
    out = []
    for c in str(s):
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def patch_file(path: Path, old: str, new: str, expect_count: int = 1) -> bytes:
    original = path.read_bytes()
    text = original.decode("utf-8")
    n = text.count(old)
    if n != expect_count:
        raise RuntimeError(f"patch_file({path}): expected {expect_count} occurrence(s) of {old!r}, found {n}")
    path.write_text(text.replace(old, new))
    return original


def restore_file(path: Path, original: bytes) -> None:
    path.write_bytes(original)
    if path.read_bytes() != original:
        raise RuntimeError(f"restore_file({path}): restored bytes do not match original — REFUSING to continue")


def record_hash(path: Path) -> str:
    """0.3.1 errata TYPED wire: `record:sha-512:<hex>` via hashdomains directly (not m11's legacy
    untyped `evidence-record` domain — see this script's module docstring)."""
    return hashdomains.digest("record:", path.read_bytes())


def render_inputs(entries) -> str:
    lines = []
    for path, digest in entries:
        lines.append("    [[claim.evidence.inputs]]")
        lines.append(f"    path   = {q(path)}")
        lines.append(f"    digest = {q(digest)}")
    return "\n".join(lines)


def render_control(of_claim: str) -> str:
    return (
        "    [claim.evidence.control]\n"
        '    kind        = "mutation"\n'
        '    expectation = "red"\n'
        '    observed    = "red"\n'
        f"    of_claim    = {q(of_claim)}\n"
    )


# --------------------------------------------------------------------------
# Toolchain identity (real, verified — never invented; same shape as rust-delivery)
# --------------------------------------------------------------------------

def _tool_commit(cmd):
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    m = re.search(r"^commit-hash:\s*([0-9a-f]{40})\s*$", out, re.MULTILINE)
    return m.group(1) if m else None


RUSTC_VERSION = subprocess.run(["rustc", "--version"], capture_output=True, text=True, check=True).stdout.strip()
CARGO_VERSION = subprocess.run(["cargo", "--version"], capture_output=True, text=True, check=True).stdout.strip()
CLIPPY_VERSION_RAW = subprocess.run(["cargo", "clippy", "--version"], capture_output=True, text=True, check=True).stdout.strip()
RUSTC_TOOL = f"{RUSTC_VERSION} + {CARGO_VERSION}"
CLIPPY_TOOL = f"{CLIPPY_VERSION_RAW} + {RUSTC_VERSION}"
RUSTC_VERBOSE = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
RUSTC_COMMIT = _tool_commit(["rustc", "-vV"])
CARGO_COMMIT = _tool_commit(["cargo", "--version", "--verbose"])
_rustc_release_m = re.search(r"^release:\s*(\S+)\s*$", RUSTC_VERBOSE, re.MULTILINE)
RUSTC_RELEASE = _rustc_release_m.group(1) if _rustc_release_m else RUSTC_VERSION
_cargo_release_m = re.search(r"^cargo (\S+)", CARGO_VERSION)
CARGO_RELEASE = _cargo_release_m.group(1) if _cargo_release_m else CARGO_VERSION

try:
    _kv = subprocess.run(["cargo", "kani", "--version"], capture_output=True, text=True, timeout=30)
    KANI_VERSION_LINE = _kv.stdout.strip() or _kv.stderr.strip()
    KANI_AVAILABLE = _kv.returncode == 0
except (OSError, subprocess.TimeoutExpired):
    KANI_VERSION_LINE, KANI_AVAILABLE = "", False
_kani_ver_m = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", KANI_VERSION_LINE)
KANI_TOOL_NOTE = (
    f"kani@{_kani_ver_m.group(1) if _kani_ver_m else KANI_VERSION_LINE} "
    "(commit unknown — `cargo kani --version` on this install reports only a semantic version, "
    "not a build sha; source identity unavailable)"
)


def toolchain_rustc_cargo() -> str:
    lines = ["  [[claim.evidence.toolchain]]", '  name    = "rustc"', f"  version = {q(RUSTC_RELEASE)}"]
    if RUSTC_COMMIT:
        lines.append(f"  commit  = {q(RUSTC_COMMIT)}")
    lines.append("  [[claim.evidence.toolchain]]")
    lines.append('  name    = "cargo"')
    lines.append(f"  version = {q(CARGO_RELEASE)}")
    if CARGO_COMMIT:
        lines.append(f"  commit  = {q(CARGO_COMMIT)}")
    return "\n".join(lines)


def toolchain_rustc_only() -> str:
    lines = ["  [[claim.evidence.toolchain]]", '  name    = "rustc"', f"  version = {q(RUSTC_RELEASE)}"]
    if RUSTC_COMMIT:
        lines.append(f"  commit  = {q(RUSTC_COMMIT)}")
    return "\n".join(lines)


def build_inputs_block(crate_dir: Path) -> str:
    """B20 required_build_inputs (code/rust binding): Cargo.lock + rust-toolchain.toml. Both live
    at the WORKSPACE root here (one lockfile/toolchain pin for all three crates), one level above
    every crate's own manifest. B20 (0.3.1, cross-vendor review round 2 Finding 3) matches
    `required_build_inputs` by EXACT path, anchored to the manifest's own directory (B6) — a
    basename match was rejected as unsound (it would let two unrelated files with the right names
    satisfy the guard). Since this crate's manifest sits ABOVE the shared lockfile/toolchain pin
    (the reverse of `rust-delivery`'s layout, where the crate sits below its manifest), the fix is
    the SAME one `rust-delivery/gen_package.py`'s `_ensure_build_input_symlink` uses, mirrored: a
    same-directory (here, same-CRATE-directory) relative symlink named exactly `Cargo.lock` /
    `rust-toolchain.toml`, pointing at `../Cargo.lock` / `../rust-toolchain.toml` — one source of
    truth (the real files never move), a bare declared `path` that resolves via B6 to the exact
    same bytes, and B20's exact-path match is satisfied honestly rather than worked around."""
    lines = []
    for name in ("Cargo.lock", "rust-toolchain.toml"):
        full = SCRIPT_DIR / name
        digest = hashdomains.digest("artifact:", full.read_bytes())
        _ensure_build_input_symlink(crate_dir, name)
        lines.append("  [[claim.evidence.build_inputs]]")
        lines.append(f"  path   = {q(name)}")
        lines.append(f"  digest = {q(digest)}")
    return "\n".join(lines)


def _ensure_build_input_symlink(crate_dir: Path, name: str) -> None:
    """Creates/repairs `crate_dir/<name>` as a relative symlink to `../<name>` (the real,
    workspace-root file), so a bare, manifest-relative `path` resolves to the SAME bytes
    `SCRIPT_DIR / name` names — one source of truth, never a duplicate regeneration could forget
    to refresh. Mirrors `../rust-delivery/gen_package.py`'s `_ensure_build_input_symlink` exactly,
    with the parent/child relationship inverted (this workspace's manifests sit ABOVE the shared
    lockfile's directory, not below a per-crate one)."""
    link = crate_dir / name
    target = Path("..") / name
    if link.is_symlink():
        if link.readlink() == target:
            return
        link.unlink()
    elif link.exists():
        raise RuntimeError(f"{link} exists and is not a symlink -- refusing to overwrite it")
    link.symlink_to(target)


# --------------------------------------------------------------------------
# Generic claim/evidence rendering
# --------------------------------------------------------------------------

def emit_claim(body, crate_dir, *, id, clause, item, statement, band, status, commit,
                weight=None, grade=None, bounds=None, self_verify=None, evidence=(), control_of=None):
    body.append("[[claim]]")
    body.append(f"id            = {q(id)}")
    if clause:
        body.append(f"clause        = {q(clause)}")
    body.append(f"item          = {q(item)}")
    body.append(f"statement     = {q(statement)}")
    body.append(f"band          = {q(band)}")
    body.append(f"status        = {q(status)}")
    if weight:
        body.append(f"weight        = {q(weight)}")
    if grade:
        body.append(f"grade         = {q(grade)}")
    body.append('clause_source = "spec-document"')
    if bounds:
        body.append(f"bounds        = {q(bounds)}")
    body.append(f"captured_at_commit = {q(commit)}")
    body.append("")
    if self_verify:
        body.append("  [claim.self_verify]")
        body.append(f"  command = {q(self_verify['command'])}")
        body.append(f"  expect  = {q(self_verify['expect'])}")
        if "watched_fail" in self_verify:
            wf = self_verify["watched_fail"]
            body.append("")
            body.append("    [claim.self_verify.watched_fail]")
            body.append(f"    of_command = {q(wf['of_command'])}")
            body.append(f"    perturbed  = {q(wf['perturbed'])}")
            body.append(f"    observed   = {q(wf['observed'])}")
            body.append(f"    date       = {q(wf['date'])}")
        body.append("")
    for ev in evidence:
        body.append("  [[claim.evidence]]")
        for k in ("kind", "family", "method", "epistemic_tier"):
            if k in ev:
                body.append(f"  {k:<11}= {q(ev[k])}")
        body.append(f"  ref         = {q(ev['ref'])}")
        body.append(f"  result      = {q(ev['result'])}")
        body.append(f"  tool        = {q(ev['tool'])}")
        if "cases" in ev:
            body.append(f"  cases       = {ev['cases']}")
        if "bounds" in ev:
            body.append(f"  bounds      = {q(ev['bounds'])}")
        if "generator" in ev:
            body.append(f"  generator   = {q(ev['generator'])}")
        if "semantics" in ev:
            body.append(f"  semantics   = {q(ev['semantics'])}")
        rec_path = crate_dir / ev["record"]
        body.append(f"  record      = {q(ev['record'])}")
        body.append(f"  record_hash = {q(record_hash(rec_path))}")
        body.append(f"  captured_at_commit = {q(commit)}")
        if ev.get("inputs"):
            body.append(render_inputs(ev["inputs"]))
        if ev.get("with_toolchain") == "rustc_cargo":
            body.append(toolchain_rustc_cargo())
        elif ev.get("with_toolchain") == "rustc_only":
            body.append(toolchain_rustc_only())
        if ev.get("with_build_inputs"):
            body.append(build_inputs_block(crate_dir))
        body.append("")
    if control_of:
        body.append(render_control(control_of))
        body.append("")


def input_entries(crate_dir: Path, paths):
    return [(p, m11.digest_file("subject", crate_dir / p)) for p in paths]


def write_evidence(crate_dir: Path, name: str, text: str) -> str:
    (crate_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (crate_dir / "evidence" / name).write_text(normalize(text))
    return f"evidence/{name}"


def header(crate_name: str, commit: str, dirty: bool, extra: str = "") -> str:
    return f"""\
# GENERATED FILE — DO NOT HAND-EDIT.
#
# Produced by protocol_acceptance/examples/paint-stack/gen_packages.py, which actually ran
# `cargo test`, `cargo clippy`{", `cargo kani`" if extra == "kani" else ""} and real, restored
# mutation controls against {crate_name}/ (this directory's sibling). Transcripts are in evidence/.
#
# SELF-REFERENCE DISCLOSURE (same convention as ../rust-delivery/gen_package.py, spec/format.md
# "[format] self-location"): {"[subject].dirty is `false`: this manifest certifies the committed state of " + crate_name + "/ at the commit below, generated after that commit." if not dirty else "[subject].dirty is honestly `true`: " + crate_name + "/ had uncommitted changes at generation time, so this manifest does NOT certify a clean commit; input hashes identify the tested edited bytes."}
# Transcript paths normalized to <WORKSPACE>, <REPO>, <HOME> before hashing.
# Generated: {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
#
# Re-run: python3 gen_packages.py

"""


def assemble(body_lines) -> str:
    return "\n".join(body_lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# geom-math
# --------------------------------------------------------------------------

def build_geom_math(commit: str, dirty: bool) -> None:
    crate_dir = SCRIPT_DIR / "geom-math"
    print("[gen_packages] === geom-math ===")

    rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("geom-math baseline `cargo test` failed")
    test_record = write_evidence(crate_dir, "cargo-test.txt", out)
    test_result_line = re.findall(r"^test result: .*$", out, re.MULTILINE)[-1]

    rc, out, _ = run(["cargo", "clippy", "--", "-D", "warnings"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("geom-math baseline `cargo clippy` failed")
    clippy_record = write_evidence(crate_dir, "clippy.txt", out)

    kani_records = {}
    if not KANI_AVAILABLE:
        raise RuntimeError("cargo kani is not available — geom-math's weighted claims require it")
    for harness in ("isqrt_correct_full_domain", "dist2_never_overflows_full_domain"):
        print(f"[gen_packages] geom-math: cargo kani --harness {harness}")
        rc, out, elapsed = run(["cargo", "kani", "--harness", harness], cwd=crate_dir, timeout=280)
        rec = write_evidence(crate_dir, f"kani-{harness}.txt", out)
        ok = rc == 0 and "VERIFICATION:- SUCCESSFUL" in out
        print(f"[gen_packages]   -> rc={rc} elapsed={elapsed:.1f}s pass={ok}")
        if not ok:
            raise RuntimeError(f"geom-math Kani harness {harness} did not pass — refusing to certify")
        kani_records[harness] = rec

    # Mutation control GM-001 (isqrt): off-by-one in the digit-by-digit comparison.
    lib_path = crate_dir / "src" / "lib.rs"
    original = read_bytes(lib_path)
    patch_file(lib_path, "if n >= res + bit {", "if n > res + bit {")
    try:
        rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original)
    if rc == 0:
        raise RuntimeError("GM-001 mutation control did not go red")
    gm1_control = write_evidence(crate_dir, "gm1-mutation-control.txt", out)
    print("[gen_packages] GM-001 control: RED as expected, restored, byte-equal")

    # Mutation control GM-002 (dist2): naive i32 multiply overflows/panics on extremes.
    original2 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "pub fn dist2(dx: i32, dy: i32) -> u64 {\n    let a = dx.unsigned_abs() as u64;\n    let b = dy.unsigned_abs() as u64;\n    a * a + b * b\n}",
        "pub fn dist2(dx: i32, dy: i32) -> u64 {\n    let a = dx as i64;\n    let b = dy as i64;\n    ((a * a) + (b * b)) as u64\n}",
    )
    try:
        rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original2)
    if rc == 0:
        raise RuntimeError("GM-002 mutation control did not go red")
    gm2_control = write_evidence(crate_dir, "gm2-mutation-control.txt", out)
    print("[gen_packages] GM-002 control: RED (panic on i32::MIN/MAX) as expected, restored, byte-equal")

    rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("geom-math post-mutation sanity `cargo test` failed")

    inputs = input_entries(crate_dir, ["src/lib.rs", "Cargo.toml"])
    body = [header("geom-math", commit, dirty)]
    body += [
        "[format]", 'id       = "acceptance/0"', 'protocol = "acceptance-protocol/1"',
        f"profile  = {q(PROFILE_ID)}", "",
        "[subject]", 'name   = "geom-math"', 'kind   = "rust-crate"',
        f"commit = {q(commit)}", f"dirty  = {'true' if dirty else 'false'}", "",
        "[spec]", 'path    = "SPEC.md"', 'version = "v1"',
        'axis    = "the SPEC.md clauses (S-1, S-2)"', "",
        "[coverage]", "clauses_total = 2", "claims_total  = 2", "",
    ]

    body.append("# ===================================================================")
    body.append("# GM-001 -- S-1: isqrt is correct over the full u32 domain")
    body.append("# ===================================================================")
    emit_claim(
        body, crate_dir, id="GM-001", clause="S-1", item="src/lib.rs::isqrt (verification::isqrt_correct_full_domain)",
        statement="isqrt(n) returns the floor integer square root of n for every u32 n (full domain): r*r <= n < (r+1)*(r+1). Never panics or overflows.",
        band="A1", status="evidenced", weight="weighted", grade="probe",
        bounds="unbounded: full u32 domain (no narrowing) -- the loop bound is fixed at 16 iterations regardless of n, so this is not a bounded slice of the domain",
        commit=commit,
        self_verify={"command": "cargo kani --harness isqrt_correct_full_domain", "expect": "VERIFICATION:- SUCCESSFUL"},
        evidence=[
            {"kind": "kani-harness", "family": "bmc", "method": "kani-harness", "epistemic_tier": "T2",
             "ref": "verification::isqrt_correct_full_domain", "result": "pass", "tool": KANI_TOOL_NOTE,
             "bounds": "unwind=18, full u32 domain (no kani::assume narrowing at all)", "semantics": "",
             "record": kani_records["isqrt_correct_full_domain"], "inputs": inputs},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "tests::isqrt_known_values, tests::isqrt_exhaustive_small_range (200,000 real, non-symbolic values, independent of the Kani proof)",
             "result": "pass", "tool": RUSTC_TOOL, "cases": 200002, "record": test_record,
             "inputs": inputs, "with_toolchain": "rustc_cargo", "with_build_inputs": True},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "cargo test (mutant: `n >= res + bit` weakened to `n > res + bit`, an off-by-one in the digit-by-digit comparison)",
             "result": "fail", "tool": RUSTC_TOOL + " (1-line mutation, reverted)", "cases": 200002, "record": gm1_control},
        ],
        control_of="GM-001",
    )

    body.append("# ===================================================================")
    body.append("# GM-002 -- S-2: dist2 never panics/overflows over the full i32xi32 domain")
    body.append("# ===================================================================")
    emit_claim(
        body, crate_dir, id="GM-002", clause="S-2", item="src/lib.rs::dist2 (verification::dist2_never_overflows_full_domain)",
        statement="dist2(dx, dy) never panics or overflows for any i32 pair, including i32::MIN/i32::MAX, full domain.",
        band="A1", status="evidenced", weight="weighted", grade="probe",
        bounds="unbounded: full (i32, i32) domain (no narrowing)",
        commit=commit,
        self_verify={"command": "cargo kani --harness dist2_never_overflows_full_domain", "expect": "VERIFICATION:- SUCCESSFUL"},
        evidence=[
            {"kind": "kani-harness", "family": "bmc", "method": "kani-harness", "epistemic_tier": "T2",
             "ref": "verification::dist2_never_overflows_full_domain", "result": "pass", "tool": KANI_TOOL_NOTE,
             "bounds": "full i32 x i32 domain (no kani::assume narrowing)", "semantics": "",
             "record": kani_records["dist2_never_overflows_full_domain"], "inputs": inputs},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "tests::dist2_known_values, tests::dist2_extremes_do_not_panic", "result": "pass",
             "tool": RUSTC_TOOL, "cases": 5, "record": test_record, "inputs": inputs,
             "with_toolchain": "rustc_cargo", "with_build_inputs": True},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "cargo test (mutant: dist2 rewritten to a naive i32 multiply-then-widen, which overflows/panics on i32::MIN/i32::MAX)",
             "result": "fail", "tool": RUSTC_TOOL + " (mutation, reverted)", "cases": 5, "record": gm2_control},
        ],
        control_of="GM-002",
    )

    (crate_dir / "acceptance.toml").write_text(assemble(body))
    print(f"[gen_packages] wrote {crate_dir / 'acceptance.toml'}")
    _ = clippy_record  # referenced for provenance only (not cited as claim evidence in this pass)
    _ = test_result_line


# --------------------------------------------------------------------------
# raster-draw
# --------------------------------------------------------------------------

def build_raster_draw(commit: str, dirty: bool) -> None:
    crate_dir = SCRIPT_DIR / "raster-draw"
    print("[gen_packages] === raster-draw ===")

    rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("raster-draw baseline `cargo test` failed")
    test_record = write_evidence(crate_dir, "cargo-test.txt", out)

    rc, out, _ = run(["cargo", "clippy", "--", "-D", "warnings"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("raster-draw baseline `cargo clippy` failed")

    if not KANI_AVAILABLE:
        raise RuntimeError("cargo kani is not available — raster-draw's RD-001/RD-002 require it")
    kani_records = {}
    for harness in ("octant_accurate_bounded", "octant_adjacent_bounded"):
        print(f"[gen_packages] raster-draw: cargo kani --harness {harness}")
        rc, out, elapsed = run(["cargo", "kani", "--harness", harness], cwd=crate_dir, timeout=280)
        rec = write_evidence(crate_dir, f"kani-{harness}.txt", out)
        ok = rc == 0 and "VERIFICATION:- SUCCESSFUL" in out
        print(f"[gen_packages]   -> rc={rc} elapsed={elapsed:.1f}s pass={ok}")
        if not ok:
            raise RuntimeError(f"raster-draw Kani harness {harness} did not pass")
        kani_records[harness] = rec

    lib_path = crate_dir / "src" / "lib.rs"

    # RD-001 control: break the midpoint decision update (drop the `+ 1`), which desyncs the
    # curve from the true radius.
    original = read_bytes(lib_path)
    patch_file(lib_path, "err += 2 * y as i64 + 1;", "err += 2 * y as i64;")
    try:
        rc, out, _ = run(["cargo", "test", "--lib", "property_accuracy_over_many_radii"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original)
    if rc == 0:
        raise RuntimeError("RD-001 mutation control did not go red")
    rd1_control = write_evidence(crate_dir, "rd1-mutation-control.txt", out)
    print("[gen_packages] RD-001 control: RED as expected, restored, byte-equal")

    # RD-002 control: drop the x-negation in circle_points' Q1 quadrant, breaking the seam
    # continuity that makes the assembled curve closed and 8-connected.
    original2 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "full.extend(q0.iter().rev().map(|&(x, y)| (-x, y))); // Q1",
        "full.extend(q0.iter().rev().map(|&(x, y)| (x, y))); // Q1 (mutated: negation dropped)",
    )
    try:
        rc, out, _ = run(["cargo", "test", "--lib", "property_closed_8_connected_cycle_over_many_radii"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original2)
    if rc == 0:
        raise RuntimeError("RD-002 mutation control did not go red")
    rd2_control = write_evidence(crate_dir, "rd2-mutation-control.txt", out)
    print("[gen_packages] RD-002 control: RED as expected, restored, byte-equal")

    # RD-003 control: drop the double-negation in Q2, breaking one of the 8 reflections.
    original3 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "full.extend(q0.iter().map(|&(x, y)| (-x, -y))); // Q2",
        "full.extend(q0.iter().map(|&(x, y)| (x, -y))); // Q2 (mutated: x-negation dropped)",
    )
    try:
        rc, out, _ = run(["cargo", "test", "--lib", "property_8way_symmetry_as_a_set"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original3)
    if rc == 0:
        raise RuntimeError("RD-003 mutation control did not go red")
    rd3_control = write_evidence(crate_dir, "rd3-mutation-control.txt", out)
    print("[gen_packages] RD-003 control: RED as expected, restored, byte-equal")

    # RD-004 control: remove the bounds check in set_pixel, causing a real index-out-of-bounds panic.
    original4 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "        if x >= self.width || y >= self.height {\n            return;\n        }\n        self.pixels[(y * self.width + x) as usize] = color;",
        "        self.pixels[(y * self.width + x) as usize] = color;",
    )
    try:
        rc, out, _ = run(["cargo", "test", "--lib"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original4)
    if rc == 0:
        raise RuntimeError("RD-004 mutation control did not go red")
    rd4_control = write_evidence(crate_dir, "rd4-mutation-control.txt", out)
    print("[gen_packages] RD-004 control: RED (real panic) as expected, restored, byte-equal")

    rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("raster-draw post-mutation sanity `cargo test` failed")
    rc, out, _ = run(["cargo", "clippy", "--", "-D", "warnings"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("raster-draw post-mutation sanity `cargo clippy` failed")

    inputs = input_entries(crate_dir, ["src/lib.rs", "Cargo.toml"])
    body = [header("raster-draw", commit, dirty, extra="kani")]
    body += [
        "[format]", 'id       = "acceptance/0"', 'protocol = "acceptance-protocol/1"',
        f"profile  = {q(PROFILE_ID)}", "",
        "[subject]", 'name   = "raster-draw"', 'kind   = "rust-crate"',
        f"commit = {q(commit)}", f"dirty  = {'true' if dirty else 'false'}", "",
        "[spec]", 'path    = "SPEC.md"', 'version = "v1"',
        'axis    = "the SPEC.md clauses (S-1..S-4)"', "",
        "[coverage]", "clauses_total = 4", "claims_total  = 4", "",
    ]

    body.append("# === RD-001 -- S-1: accuracy ===")
    emit_claim(
        body, crate_dir, id="RD-001", clause="S-1", item="src/lib.rs::fill_octant, accuracy_ok (verification::octant_accurate_bounded)",
        statement="fill_octant accuracy is Kani-proved for r <= 6. Full circle_points accuracy is property-tested for radii sampled up to 2000. Rendered-canvas geometry claims apply only to fully-inside circles; draw_circle retains clipping.",
        band="A1", status="evidenced", weight="weighted", grade="probe",
        bounds="bounded: Kani exhaustive for r <= 6 (KANI_MAX_R); property-tested (300 random samples, xorshift64 seed 0xDEADBEEFCAFEF00D) for r in 0..=2000 -- not an unbounded argument over every radius",
        commit=commit,
        self_verify={"command": "cargo kani --harness octant_accurate_bounded", "expect": "VERIFICATION:- SUCCESSFUL"},
        evidence=[
            {"kind": "kani-harness", "family": "bmc", "method": "kani-harness", "epistemic_tier": "T2",
             "ref": "verification::octant_accurate_bounded", "result": "pass", "tool": KANI_TOOL_NOTE,
             "bounds": "unwind=10, r <= 6 (KANI_MAX_R), exhaustive over that range", "semantics": "",
             "record": kani_records["octant_accurate_bounded"], "inputs": inputs},
            {"kind": "property-test", "family": "dynamic", "method": "property-test", "epistemic_tier": "T3",
             "ref": "tests::property_accuracy_over_many_radii", "result": "pass", "tool": RUSTC_TOOL,
             "cases": 300, "generator": "hand-rolled xorshift64, seed 0xDEADBEEFCAFEF00D, r in 0..=2000",
             "record": test_record, "inputs": inputs, "with_toolchain": "rustc_cargo", "with_build_inputs": True},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "cargo test --lib property_accuracy_over_many_radii (mutant: dropped `+ 1` in the midpoint decision update)",
             "result": "fail", "tool": RUSTC_TOOL + " (1-line mutation, reverted)", "cases": 300, "record": rd1_control},
        ],
        control_of="RD-001",
    )

    body.append("# === RD-002 -- S-2: closed, 8-connected, no gaps ===")
    emit_claim(
        body, crate_dir, id="RD-002", clause="S-2", item="src/lib.rs::fill_octant, circle_points",
        statement="Kani proves only fill_octant intra-octant and mirrored-seam adjacency for r <= 6. Full circle_points closedness (consecutive points, including wraparound, Chebyshev-adjacent) is property-tested for radii sampled in 1..=2000. Rendered-canvas geometry is claimed only for fully-inside circles.",
        band="A1", status="evidenced", weight="weighted", grade="probe",
        bounds="bounded: Kani exhaustive for r <= 6 (fill_octant's own adjacency, including the seam into circle_points' mirrored octant); property-tested (300 samples) for r in 1..=2000 -- the full assembled circle_points' closedness is NOT proved by Kani (only property-tested), see the crate's own doc comment and the example README",
        commit=commit,
        self_verify={"command": "cargo kani --harness octant_adjacent_bounded", "expect": "VERIFICATION:- SUCCESSFUL"},
        evidence=[
            {"kind": "kani-harness", "family": "bmc", "method": "kani-harness", "epistemic_tier": "T2",
             "ref": "verification::octant_adjacent_bounded", "result": "pass", "tool": KANI_TOOL_NOTE,
             "bounds": "unwind=10, r <= 6 (KANI_MAX_R), exhaustive over that range, includes the seam adjacency |x_last - y_last| <= 1",
             "semantics": "", "record": kani_records["octant_adjacent_bounded"], "inputs": inputs},
            {"kind": "property-test", "family": "dynamic", "method": "property-test", "epistemic_tier": "T3",
             "ref": "tests::property_closed_8_connected_cycle_over_many_radii", "result": "pass", "tool": RUSTC_TOOL,
             "cases": 300, "generator": "hand-rolled xorshift64, seed 0x123456789ABCDEF0, r in 1..=2000",
             "record": test_record, "inputs": inputs},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "cargo test --lib property_closed_8_connected_cycle_over_many_radii (mutant: dropped the x-negation assembling circle_points' Q1 quadrant)",
             "result": "fail", "tool": RUSTC_TOOL + " (1-line mutation, reverted)", "cases": 300, "record": rd2_control},
        ],
        control_of="RD-002",
    )

    body.append("# === RD-003 -- S-3: 8-way symmetry ===")
    emit_claim(
        body, crate_dir, id="RD-003", clause="S-3", item="src/lib.rs::circle_points",
        statement="The set circle_points(r) returns is closed under all 8 symmetries of the square about the center, property-tested for r sampled up to 1000. Rendered-canvas symmetry is claimed only for fully-inside circles.",
        band="A1", status="evidenced", weight="weighted", grade="test-only",
        bounds="bounded: property-tested (200 samples, xorshift64 seed 0x0BADC0DE12345678) for r in 1..=1000 -- not Kani-proved (see the crate doc comment: reflecting a Vec inside a bounded-model-checking harness was judged not worth its Kani cost beyond what fill_octant's own proof already establishes)",
        commit=commit,
        self_verify={"command": "cargo test --lib property_8way_symmetry_as_a_set", "expect": "test result: ok"},
        evidence=[
            {"kind": "property-test", "family": "dynamic", "method": "property-test", "epistemic_tier": "T3",
             "ref": "tests::property_8way_symmetry_as_a_set", "result": "pass", "tool": RUSTC_TOOL,
             "cases": 200, "generator": "hand-rolled xorshift64, seed 0x0BADC0DE12345678, r in 1..=1000",
             "record": test_record, "inputs": inputs, "with_toolchain": "rustc_cargo", "with_build_inputs": True},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "cargo test --lib property_8way_symmetry_as_a_set (mutant: dropped the x-negation assembling circle_points' Q2 quadrant)",
             "result": "fail", "tool": RUSTC_TOOL + " (1-line mutation, reverted)", "cases": 200, "record": rd3_control},
        ],
        control_of="RD-003",
    )

    body.append("# === RD-004 -- S-4: clipping never panics ===")
    emit_claim(
        body, crate_dir, id="RD-004", clause="S-4", item="src/lib.rs::Canvas::set_pixel, Canvas::pixel, draw_circle",
        statement="set_pixel/pixel never panic for any i32 coordinate (in or out of bounds, including i32::MIN/MAX), and draw_circle never panics for any (cx, cy, r).",
        band="A1", status="evidenced", weight="weighted", grade="test-only",
        commit=commit,
        self_verify={"command": "cargo test --lib", "expect": "test result: ok"},
        evidence=[
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "tests::set_pixel_and_pixel_never_panic_far_out_of_bounds, tests::draw_circle_on_tiny_canvas_with_large_radius_does_not_panic",
             "result": "pass", "tool": RUSTC_TOOL, "cases": 9, "record": test_record, "inputs": inputs,
             "with_toolchain": "rustc_cargo", "with_build_inputs": True},
            {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
             "ref": "cargo test --lib (mutant: bounds check removed from Canvas::set_pixel)",
             "result": "fail", "tool": RUSTC_TOOL + " (mutation, reverted)", "cases": 9, "record": rd4_control},
        ],
        control_of="RD-004",
    )

    (crate_dir / "acceptance.toml").write_text(assemble(body))
    print(f"[gen_packages] wrote {crate_dir / 'acceptance.toml'}")


# --------------------------------------------------------------------------
# paint-app: intrinsic package AND the specification-bound package (share evidence)
# --------------------------------------------------------------------------

def build_paint_app(commit: str, dirty: bool) -> dict:
    crate_dir = SCRIPT_DIR / "paint-app"
    print("[gen_packages] === paint-app ===")

    rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("paint-app baseline `cargo test` failed")
    test_record = write_evidence(crate_dir, "cargo-test.txt", out)

    rc, out, _ = run(["cargo", "clippy", "--all-targets", "--", "-D", "warnings"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("paint-app baseline `cargo clippy` failed")

    rc, out, _ = run(["cargo", "doc", "--no-deps"], cwd=crate_dir, timeout=60, env=DOC_ENV)
    if rc != 0 or "warning" in out:
        print(out); raise RuntimeError("paint-app baseline `cargo doc --no-deps` (RUSTDOCFLAGS=-D warnings) did not pass cleanly")
    doc_record = write_evidence(crate_dir, "cargo-doc.txt", out)

    lib_path = crate_dir / "src" / "lib.rs"

    # PA-001 control: parse_args' --r handling made to panic on non-numeric input.
    original = read_bytes(lib_path)
    patch_file(
        lib_path,
        '            "--r" => {\n                if r.is_some() {\n                    return Err(ArgError::DuplicateFlag(flag.clone()));\n                }\n                r = Some(value.parse::<u32>().map_err(|_| ArgError::BadValue {\n                    flag: flag.clone(),\n                    value: value.clone(),\n                })?);\n            }',
        '            "--r" => {\n                if r.is_some() {\n                    return Err(ArgError::DuplicateFlag(flag.clone()));\n                }\n                r = Some(value.parse::<u32>().unwrap());\n            }',
    )
    try:
        rc, out, _ = run(["cargo", "test", "--lib", "rejects_every_malformed_invocation_without_panicking"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original)
    if rc == 0:
        raise RuntimeError("PA-001 mutation control did not go red")
    pa1_control = write_evidence(crate_dir, "pa1-mutation-control.txt", out)
    print("[gen_packages] PA-001 control: RED (real panic) as expected, restored, byte-equal")

    # PA-002 control: invert the PPM gray mapping (ink/background swapped), breaking the golden image.
    original2 = read_bytes(lib_path)
    patch_file(lib_path, "let gray = 255u8.wrapping_sub(v);", "let gray = v;")
    try:
        rc, out, _ = run(["cargo", "test", "--test", "cli", "valid_invocation_writes_a_real_ppm_file_independently_verified"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original2)
    if rc == 0:
        raise RuntimeError("PA-002 mutation control did not go red")
    pa2_control = write_evidence(crate_dir, "pa2-mutation-control.txt", out)
    print("[gen_packages] PA-002 control: RED as expected, restored, byte-equal")

    # PA-003 control: break symmetry at the render layer by drawing with cx/cy swapped internally.
    original3 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "    raster_draw::draw_circle(&mut canvas, cx as i32, cy as i32, r, INK);",
        "    raster_draw::draw_circle(&mut canvas, cx as i32, cy as i32 + 1, r, INK);",
    )
    try:
        rc, out, _ = run(["cargo", "test", "--test", "cli", "valid_invocation_writes_a_real_ppm_file_independently_verified"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original3)
    if rc == 0:
        raise RuntimeError("PA-003 mutation control did not go red")
    pa3_control = write_evidence(crate_dir, "pa3-mutation-control.txt", out)
    print("[gen_packages] PA-003 control: RED as expected, restored, byte-equal")

    # PA-004 control: drop every other point before encoding, breaking closedness on the file.
    original4 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "    for y in 0..h as i32 {\n        for x in 0..w as i32 {\n            let v = canvas.pixel(x, y).unwrap_or(0);\n            let gray = 255u8.wrapping_sub(v);\n            out.push(gray);\n            out.push(gray);\n            out.push(gray);\n        }\n    }",
        "    for y in 0..h as i32 {\n        for x in 0..w as i32 {\n            let mut v = canvas.pixel(x, y).unwrap_or(0);\n            if (x + y) % 5 == 0 { v = 0; }\n            let gray = 255u8.wrapping_sub(v);\n            out.push(gray);\n            out.push(gray);\n            out.push(gray);\n        }\n    }",
    )
    try:
        rc, out, _ = run(["cargo", "test", "--test", "cli", "valid_invocation_writes_a_real_ppm_file_independently_verified"], cwd=crate_dir, timeout=60)
    finally:
        restore_file(lib_path, original4)
    if rc == 0:
        raise RuntimeError("PA-004 mutation control did not go red")
    pa4_control = write_evidence(crate_dir, "pa4-mutation-control.txt", out)
    print("[gen_packages] PA-004 control: RED as expected, restored, byte-equal")

    # R5 (specification-only, optional): docs build control — a broken intra-doc link.
    original5 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "use raster_draw::Canvas;",
        "//! See [`totally::bogus::path`] for details.\nuse raster_draw::Canvas;",
    )
    try:
        rc, out, _ = run(["cargo", "doc", "--no-deps"], cwd=crate_dir, timeout=60, env=DOC_ENV)
    finally:
        restore_file(lib_path, original5)
    if rc == 0:
        raise RuntimeError("R5 (docs) mutation control did not go red under RUSTDOCFLAGS=-D warnings")
    r5_control = write_evidence(crate_dir, "r5-mutation-control.txt", out)
    r5_control_tail = "\n".join(out.strip().splitlines()[-6:])
    print("[gen_packages] R5 (docs) control: RED as expected, restored, byte-equal")

    rc, out, _ = run(["cargo", "test"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("paint-app post-mutation sanity `cargo test` failed")
    rc, out, _ = run(["cargo", "clippy", "--all-targets", "--", "-D", "warnings"], cwd=crate_dir, timeout=60)
    if rc != 0:
        print(out); raise RuntimeError("paint-app post-mutation sanity `cargo clippy` failed")

    inputs = input_entries(crate_dir, ["src/lib.rs", "src/main.rs", "Cargo.toml", "tests/cli.rs", "tests/fixtures/circle_cx15_cy15_r10.ppm.hex"])

    def claim_kwargs(claim_id, clause, statement, control_record, control_ref, control_cmd, test_ref, cases, test_cmd_expect):
        return dict(
            id=claim_id, clause=clause,
            item="paint-app (paint-app/src/lib.rs, tested through the compiled `paint` binary and the library directly)",
            statement=statement, band="A1", status="evidenced", weight="weighted", grade="test-only",
            bounds="bounded: 8 (cx,cy,r) tuples: (0,0,0), (1,1,1), (3,3,3), (10,10,4), (25,25,15), (8,40,8), (45,10,10), (35,40,30); CLI malformed cases and golden fixture separately tested",
            commit=commit,
            self_verify={"command": test_cmd_expect[0], "expect": test_cmd_expect[1]},
            evidence=[
                {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
                 "ref": test_ref + "; tests/cli.rs::valid_invocation_writes_a_real_ppm_file_independently_verified (8 disk files)", "result": "pass", "tool": RUSTC_TOOL, "cases": cases, "record": test_record,
                 "inputs": inputs, "with_toolchain": "rustc_cargo", "with_build_inputs": True},
                {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3",
                 "ref": control_ref, "result": "fail", "tool": RUSTC_TOOL + " (mutation, reverted)", "cases": 1, "record": control_record},
            ],
            control_of=claim_id,
        )

    common_claims = [
        claim_kwargs("PA-001", "S-1",
                     "paint circle parses any well-formed invocation and rejects every malformed one (missing/duplicate/unknown flags, non-numeric values, unknown subcommand, empty output path, or a circle that does not fit entirely inside the auto-sized canvas) with a clean Err, never a panic — checked both as a library (parse_args, render_circle) and through the compiled binary (tests/cli.rs).",
                     pa1_control, "cargo test --lib rejects_every_malformed_invocation_without_panicking (mutant: --r parsing changed to .unwrap(), panics on non-numeric input)",
                     None, "tests::parses_a_well_formed_invocation_in_any_flag_order, tests::rejects_every_malformed_invocation_without_panicking, tests::circle_not_fully_inside_canvas_is_rejected_not_silently_clipped, tests/cli.rs (integration tests through the real binary)",
                     22, ("cargo test", "test result: ok")),
        claim_kwargs("PA-002", "S-2",
                     "For every (cx, cy, r) in the disclosed domain (see DOMAINS in src/lib.rs's test module: 8 combinations, radii 0..=30, including the cx=r/cy=r boundary), and ONLY for circles fully inside the canvas (cx >= r, cy >= r; a circle that would not fit is rejected outright, see PA-001) -- every ink pixel actually present in the output PPM file is within 0.5 of the declared radius from the declared center, checked by an oracle re-derived from scratch in the test itself (not by calling raster-draw's own circle_points/accuracy_ok), plus a byte-for-byte golden-image comparison against a checked-in fixture.",
                     pa2_control, "cargo test --test cli valid_invocation_writes_a_real_ppm_file_independently_verified (mutant: PPM gray mapping inverted, ink/background swapped)",
                     None, "tests::golden_image_matches_fixture, tests::independent_accuracy_over_disclosed_domain, tests::ppm_consistent_with_circle_points_not_independent",
                     8, ("cargo test", "test result: ok")),
        claim_kwargs("PA-003", "S-3",
                     "For every (cx, cy, r) in the disclosed domain (DOMAINS, src/lib.rs and tests/cli.rs), and only for circles fully inside the canvas: every ink pixel ACTUALLY FOUND in the output PPM file (by exhaustive scan, not by asking the renderer what it drew) has all 7 of its symmetric reflections about the declared center also present as ink in that same file.",
                     pa3_control, "cargo test --test cli valid_invocation_writes_a_real_ppm_file_independently_verified (mutant: circle rendered off-center by 1 pixel)",
                     None, "tests::independent_symmetry_over_disclosed_domain", 8, ("cargo test", "test result: ok")),
        claim_kwargs("PA-004", "S-4",
                     "For every (cx, cy, r) in the disclosed domain (DOMAINS, src/lib.rs and tests/cli.rs), and only for circles fully inside the canvas: every ink pixel ACTUALLY FOUND in the output PPM file (by exhaustive scan) forms exactly ONE 8-connected component (a real flood-fill from one ink pixel reaches every other ink pixel); independently sorted angular order also has Chebyshev-adjacent consecutive pixels, including wraparound.",
                     pa4_control, "cargo test --test cli valid_invocation_writes_a_real_ppm_file_independently_verified (mutant: every 5th encoded pixel forced to background, punching holes in the curve)",
                     None, "tests::independent_closedness_8_connectivity_over_disclosed_domain", 8, ("cargo test", "test result: ok")),
    ]

    # ---- intrinsic (producer-only, no [specification]) ----
    body = [header("paint-app", commit, dirty)]
    body += [
        "[format]", 'id       = "acceptance/0"', 'protocol = "acceptance-protocol/1"',
        f"profile  = {q(PROFILE_ID)}", "",
        "[subject]", 'name   = "paint-app"', 'kind   = "rust-crate"',
        f"commit = {q(commit)}", f"dirty  = {'true' if dirty else 'false'}", "",
        "[spec]", 'path    = "SPEC.md"', 'version = "v1"',
        'axis    = "the SPEC.md clauses (S-1..S-4)"', "",
        "[coverage]", "clauses_total = 4", "claims_total  = 4", "",
    ]
    for kw in common_claims:
        body.append(f"# === {kw['id']} -- {kw['clause']} ===")
        emit_claim(body, crate_dir, **kw)
    (crate_dir / "acceptance.toml").write_text(assemble(body))
    print(f"[gen_packages] wrote {crate_dir / 'acceptance.toml'}")

    # ---- specification-bound package (acceptance-package.toml) ----
    specification_path = crate_dir / "acceptance-specification.toml"
    specification_hash = m11.digest_file("specification", specification_path)
    pkg_body = [header("paint-app", commit, dirty)]
    pkg_body += [
        "[format]", 'id       = "acceptance/0"', 'protocol = "acceptance-protocol/1"',
        f"profile  = {q(PROFILE_ID)}", "",
        "[subject]", 'name   = "paint-app"', 'kind   = "rust-crate"',
        f"commit = {q(commit)}", f"dirty  = {'true' if dirty else 'false'}", "",
        "[specification]", 'id                 = "AC-PAINT-0001"', f"hash               = {q(specification_hash)}",
        "requirements_total = 5", "",
        "[spec]", 'path    = "acceptance-specification.toml"', 'version = "AC-PAINT-0001@v1"',
        'axis    = "the requirements of specification AC-PAINT-0001"', "",
        "[coverage]", "clauses_total = 5", "claims_total  = 5", "",
    ]
    # Cross-vendor review 2026-09-26, Blocker #1: this zip previously read ("R1","R2","R3","R4"),
    # matching pkg_claims' OWN order (PA-001 CLI, PA-002 accuracy, PA-003 symmetry, PA-004
    # closedness) positionally against the SPECIFICATION's clause order (R1 accuracy, R2 symmetry, R3
    # closedness, R4 CLI) -- a silent off-by-one-family mismatch (PA-001/CLI mislabeled R1/accuracy,
    # etc.), verified against ../paint-app/acceptance-specification.toml's actual R1..R4 statements
    # rather than assumed. Fixed: explicit, checked mapping below.
    pkg_claims = [dict(kw) for kw in common_claims]
    PA_TO_SPECIFICATION_CLAUSE = {"PA-001": "R4", "PA-002": "R1", "PA-003": "R2", "PA-004": "R3"}
    specification = tomllib.loads((crate_dir / "acceptance-specification.toml").read_text())
    requirements = {r["id"]: r["statement"] for r in specification["requirement"]}
    for rid, phrase in {"R1": "within 0.5", "R2": "eight symmetries", "R3": "8-connected", "R4": "malformed invocation"}.items():
        if phrase not in requirements[rid]:
            raise RuntimeError(f"review requirement mapping: {rid} no longer says {phrase!r}")
    for kw in pkg_claims:
        kw["clause"] = PA_TO_SPECIFICATION_CLAUSE[kw["id"]]
    for kw in pkg_claims:
        pkg_body.append(f"# === {kw['id']} -- {kw['clause']} ===")
        emit_claim(pkg_body, crate_dir, **kw)

    # R5 (optional, docs) claim.
    pkg_body.append("# === PA-005 -- R5 (optional): docs build clean ===")
    emit_claim(
        pkg_body, crate_dir, id="PA-005", clause="R5", item="paint-app (cargo doc --no-deps)",
        statement=f"{DOC_COMMAND} builds paint-app's documentation with zero warnings (RUSTDOCFLAGS=\"-D warnings\" makes a warning a hard build error, so the recorded recipe itself — not just this generator's own separate text scan — is what the mutation control below actually fails under).",
        band="A0", status="evidenced", weight="weighted", grade="mechanical", commit=commit,
        self_verify={"command": DOC_COMMAND, "expect": "Generated",
                     "watched_fail": {"of_command": DOC_COMMAND,
                                      "perturbed": "added a broken intra-doc link ([`totally::bogus::path`]) to the crate root doc comment",
                                      "observed": r5_control_tail,
                                      "date": TODAY}},
        evidence=[
            {"kind": "lint", "family": "mechanical", "method": "lint", "epistemic_tier": "T4",
             "ref": f"{DOC_COMMAND} over the whole crate (0 warnings)", "result": "pass",
             "tool": f"rustdoc (bundled with {RUSTC_VERSION}) via {CARGO_VERSION}", "record": doc_record,
             "inputs": inputs, "with_toolchain": "rustc_cargo", "with_build_inputs": True},
            {"kind": "lint", "family": "mechanical", "method": "lint", "epistemic_tier": "T4",
             "ref": f"{DOC_COMMAND} (mutant: broken intra-doc link added to crate root doc comment) -- FAILS (nonzero exit) under RUSTDOCFLAGS=-D warnings, not merely a warning in the text",
             "result": "fail", "tool": f"rustdoc (bundled with {RUSTC_VERSION}) via {CARGO_VERSION} (mutation, reverted)",
             "record": r5_control},
        ],
        control_of="PA-005",
    )
    pkg_body.append("[[filler]]")
    pkg_body.append('profile = ' + q(PROFILE_ID))
    pkg_body.append('party   = "Ochre Paint / maintainer"')
    pkg_body.append('role    = "producer"')
    pkg_body.append("")

    (crate_dir / "acceptance-package.toml").write_text(assemble(pkg_body))
    print(f"[gen_packages] wrote {crate_dir / 'acceptance-package.toml'}")

    return {"specification_hash": specification_hash, "commit": commit}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    repo_root = Path(git(["rev-parse", "--show-toplevel"], cwd=SCRIPT_DIR))
    commit = git(["rev-parse", "HEAD"], cwd=repo_root)
    rel = SCRIPT_DIR.relative_to(repo_root)
    # The subject is the Rust workspace, as in rust-delivery's crate-scoped check.
    # Acceptance documents and generators are outside that subject. Their uncommitted
    # rename must not relabel unchanged, committed Rust inputs as dirty. The new
    # specification is bound separately by its freshly computed specification hash.
    inputs = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml"]
    for crate in ("geom-math", "raster-draw", "paint-app"):
        inputs.extend([f"{crate}/Cargo.toml", f"{crate}/src"])
    paths = [str(rel / path) for path in inputs]
    dirty = bool(git(["status", "--short", "--", *paths], cwd=repo_root).strip())
    print(f"[gen_packages] repo_root={repo_root} commit={commit} dirty={dirty}")
    print(f"[gen_packages] {RUSTC_TOOL}")
    print(f"[gen_packages] {CLIPPY_VERSION_RAW}")
    print(f"[gen_packages] kani: {KANI_VERSION_LINE!r} available={KANI_AVAILABLE}")

    build_geom_math(commit, dirty)
    build_raster_draw(commit, dirty)
    build_paint_app(commit, dirty)
    print("[gen_packages] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
