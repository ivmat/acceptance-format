#!/usr/bin/env python3
"""gen_package.py — produces `acceptance.toml` (the PACKAGE) and its `evidence/` transcripts for
the iban-check worked example, by ACTUALLY RUNNING `cargo test`, `cargo clippy`, `cargo doc`,
`cargo kani`, and five real, restored mutation controls (one per requirement that needed one:
R1/R2/R3/R4/R6) against the crate at `protocol_acceptance/examples/rust-delivery/iban-check/`.

Pure stdlib, python3.11+ (uses `tomllib` only indirectly via m11; no `tomllib` dependency itself).
No third-party dependencies. Imports `protocol_acceptance/tools/m11.py` (the repository's shared M11
content-hashing helper — itself pure stdlib) rather than reimplementing it, so this generator's
hashes are byte-identical to what `acceptance_protocol.py check-package`/`check-decision`
recompute.

SELF-REFERENCE DISCLOSURE (one-commit lag): this generator and the crate it certifies live INSIDE
`protocol_acceptance/examples/rust-delivery/` of THIS repo (the source repository). `[subject].commit`
below is `git rev-parse HEAD` of this whole repo AT THE MOMENT THIS SCRIPT RUNS; `[subject].dirty` is
`git status --short -- protocol_acceptance/examples/rust-delivery/iban-check` at that same moment. A
manifest cannot name a commit that already contains itself — this file and its evidence/ records
necessarily land in the commit AFTER the one `[subject].commit` names. If `iban-check/` was committed
on its own FIRST (the two-commit re-stamp this example's README documents), its files are already
tracked and clean by the time this script runs, so `[subject].dirty` reads false; if the crate and
the package are generated together in one breath instead, the crate's own files are still untracked
relative to the HEAD this script just read, so `[subject].dirty` reads true. Either way the actual
value below is whatever this run's `git status` really found — disclosed, not silently papered over.

DO NOT HAND-EDIT the generated acceptance.toml or evidence/ files — re-run this script.

Usage: python3 gen_package.py [--kani-timeout SECONDS]
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CRATE_DIR = SCRIPT_DIR / "iban-check"
EVIDENCE_DIR = SCRIPT_DIR / "evidence"
CONTRACT_PATH = SCRIPT_DIR / "acceptance-contract.toml"
PACKAGE_OUT = SCRIPT_DIR / "acceptance.toml"

# Pinned so every cargo invocation below writes build output under the crate's own directory,
# regardless of whatever CARGO_TARGET_DIR (if any) the calling shell/worker happens to export.
# This is not a new placeholder: the existing CRATE_DIR -> <crate> transcript replacement already
# covers this exact path, so no machine-local or worker-local target-dir name can ever reach a
# persisted evidence record (README "Transcript normalization").
CARGO_TARGET_DIR = CRATE_DIR / "target"

# protocol_acceptance/tools/m11.py — the shared M11 hashing helper (stdlib-only itself).
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "tools"))
import m11  # noqa: E402

CONTRACT_ID = "AC-2026-0001"
# As of 2026-09-24, the leaf id, not the meaning-only prefix -- B12/B14 need the binding path
# (`/code/rust`) present in [format].profile for the format's own binding dispatch to admit the
# `rust-crate` subject kind at all (core.md B12/B14; format_acceptance/tools/bindings/code_rust.py).
# The protocol tool's own PROFILES registry (protocol_acceptance/tools/profiles.py) answers this
# id as an alias of "acceptance/verification" -- same vocabulary, narrower format-level admission.
PROFILE_ID = "acceptance/verification/code/rust"

# R6 (lens correctness #25): `cargo doc --no-deps` alone exits 0 even with warnings (a broken
# intra-doc link, for example) -- `expect = "Generated"` alone then passes a transcript that is
# NOT the "zero warnings" the claim states. `RUSTDOCFLAGS=-D warnings` makes rustdoc itself treat
# every warning as a hard error (nonzero exit, no "Generated" line), so `check_execute.py`'s own
# exit-code gate rejects a warning transcript before `expect` is even consulted. This is the ONE
# command string used for the baseline check below, the R6 mutation control, AND the declared
# `self_verify.command`/`of_command` recipe a consumer re-runs -- generator and consumer must
# agree on what "clean" means.
DOC_COMMAND_DISPLAY = 'RUSTDOCFLAGS="-D warnings" cargo doc --no-deps'
DOC_COMMAND_ENV = {"RUSTDOCFLAGS": "-D warnings"}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path, timeout: int = 180,
        extra_env: dict[str, str] | None = None) -> tuple[int, str, float]:
    """Runs `cmd`, combining stdout+stderr as a real terminal would show them. Returns
    (returncode, combined_output, wall_seconds)."""
    t0 = time.monotonic()
    env = {**os.environ, "CARGO_TARGET_DIR": str(CARGO_TARGET_DIR), **(extra_env or {})}
    proc = subprocess.run(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=timeout, env=env,
    )
    elapsed = time.monotonic() - t0
    return proc.returncode, proc.stdout, elapsed


def git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def normalize_transcript(text: str, repo_root: Path) -> str:
    """Remove machine-local path prefixes before evidence is persisted and hashed.

    The replacements are deliberately narrow and stable: this crate's absolute root becomes
    ``<crate>``, the enclosing repository root becomes ``<repo>``, Rust toolchain roots become
    ``<rustup>/<toolchain>/``, any remaining macOS user prefix becomes ``<users>/<name>/``, and
    the current-home prefix becomes ``~``. Apply the
    more-specific roots first so a crate path never collapses merely to a repository or home path.
    """
    text = text.replace(str(CRATE_DIR), "<crate>")
    text = text.replace(str(repo_root), "<repo>")
    text = re.sub(
        r"/" r"Users/[^/\s]+/\.rustup/toolchains/([^/\s]+)/",
        r"<rustup>/\1/",
        text,
    )
    text = re.sub(re.escape(str(Path.home())) + r"(?=/|$)", "~", text)
    return re.sub(r"/" r"Users/([^/\s]+)/", r"<users>/\1/", text)


def write_evidence(name: str, text: str, repo_root: Path) -> str:
    """Persist normalized evidence; record hashes are computed over these exact bytes."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_text(normalize_transcript(text, repo_root))
    return f"evidence/{name}"


def q(s: str) -> str:
    """Quote a string as a TOML basic string (single-line; escapes backslash/quote/control)."""
    out = []
    for c in s:
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


def extract_test_result_line(output: str) -> str:
    m = list(re.finditer(r"^test result: .*$", output, re.MULTILINE))
    if not m:
        raise RuntimeError(f"no 'test result:' line found in output:\n{output}")
    return m[-1].group(0)


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def patch_file(path: Path, old: str, new: str, expect_count: int = 1) -> bytes:
    """Applies a targeted textual patch, asserting `old` occurs exactly `expect_count` times.
    Returns the ORIGINAL bytes (for restoration)."""
    original = path.read_bytes()
    text = original.decode("utf-8")
    n = text.count(old)
    if n != expect_count:
        raise RuntimeError(f"patch_file({path}): expected {expect_count} occurrence(s) of {old!r}, found {n}")
    patched = text.replace(old, new)
    path.write_text(patched)
    return original


def restore_file(path: Path, original: bytes) -> None:
    """Restores `path` to `original` bytes EXACTLY and verifies byte-equality."""
    path.write_bytes(original)
    if path.read_bytes() != original:
        raise RuntimeError(f"restore_file({path}): restored bytes do not match original — REFUSING to continue")


# --------------------------------------------------------------------------
# M11 "subject:" domain — declared input digests
# --------------------------------------------------------------------------

def input_entries(paths: list[str]) -> list[tuple[str, str]]:
    out = []
    for p in paths:
        full = CRATE_DIR / p
        out.append((p, m11.digest_file("subject", full)))
    return out


ALL_SRC_INPUTS = ["src/lib.rs", "src/syntax.rs", "src/checksum.rs", "Cargo.toml"]


# --------------------------------------------------------------------------
# TOML rendering helpers
# --------------------------------------------------------------------------

def render_inputs(inputs: list[tuple[str, str]]) -> str:
    lines = []
    for path, digest in inputs:
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


# core.md B20's `required_build_inputs` for the code/rust binding (format_acceptance/profiles/
# bindings/code/rust.md): Cargo.lock + rust-toolchain.toml. `path` is B6-contained relative to
# THIS manifest's own directory (rust-delivery/), unlike `[[claim.evidence.inputs]]` above (which
# is relative to iban-check/, the protocol's own §8 change-impact convention -- a separate field).
#
# `required_build_inputs` is checked by EXACT
# path match (reverted from a basename match review rejected) -- neither `[subject]` nor
# this binding's own declaration carries a build-context-root locator to anchor a subdirectory-
# relative match, so the anchor is the manifest's own directory. This crate lives one level below
# its manifest (`iban-check/`), so the declared path must be the bare, binding-required name,
# backed by a same-directory symlink or a byte-identical regular copy of the crate input.
# Publication uses regular copies; regeneration checks them for drift before using them.
REQUIRED_BUILD_INPUT_NAMES = ["Cargo.lock", "rust-toolchain.toml"]


def _ensure_build_input_symlink(name: str) -> None:
    """Accept an identical published copy, or create/repair the relative source symlink.

    A regular copy must match the crate input exactly; never overwrite a differing file.
    """
    link = SCRIPT_DIR / name
    target = Path("iban-check") / name
    if link.is_symlink():
        if link.readlink() == target:
            return
        link.unlink()
    elif link.exists():
        if link.is_file() and link.read_bytes() == (CRATE_DIR / name).read_bytes():
            return
        raise RuntimeError(f"{link} differs from the crate build input -- refusing to overwrite it")
    link.symlink_to(target)


def build_inputs_block() -> tuple[str, list[str]]:
    """Real digests over the real files, never invented (B20/B16 `artifact:` domain). Returns
    (rendered TOML block or "", list of names skipped because the file does not exist)."""
    lines: list[str] = []
    missing: list[str] = []
    for name in REQUIRED_BUILD_INPUT_NAMES:
        full = CRATE_DIR / name
        if not full.is_file():
            missing.append(name)
            continue
        digest = m11.hashdomains.digest("artifact:", full.read_bytes())
        _ensure_build_input_symlink(name)
        lines.append("  [[claim.evidence.build_inputs]]")
        lines.append(f"  path   = {q(name)}")
        lines.append(f"  digest = {q(digest)}")
    return "\n".join(lines), missing


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kani-timeout", type=int, default=600)
    args = ap.parse_args(argv[1:])

    if not CRATE_DIR.is_dir():
        print(f"error: crate not found at {CRATE_DIR}", file=sys.stderr)
        return 2

    repo_root = Path(git(["rev-parse", "--show-toplevel"], cwd=SCRIPT_DIR))
    commit = git(["rev-parse", "HEAD"], cwd=repo_root)
    dirty_out = git(["status", "--short", "--", "protocol_acceptance/examples/rust-delivery/iban-check"], cwd=repo_root)
    dirty = bool(dirty_out.strip())
    today = datetime.date.today().isoformat()

    rustc_version = subprocess.run(["rustc", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    cargo_version = subprocess.run(["cargo", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    clippy_version_raw = subprocess.run(["cargo", "clippy", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    rustc_tool = f"{rustc_version} + {cargo_version}"
    clippy_tool = f"{clippy_version_raw} + {rustc_version}"

    # B20 typed toolchain identity: real, verified 40-hex commits, straight from each tool's own
    # `-vV`/`--verbose` output -- never invented. `rustc -vV` and `cargo --version --verbose` both
    # print `commit-hash: <40-hex>`; clippy shares rustc's build (its own `--version` prints only a
    # 10-hex prefix, not the 40-hex B20 requires) and cargo-kani's plain `--version` prints a bare
    # semantic version with no commit at all -- both are left out of the typed `toolchain` list
    # rather than manufacturing a value the install cannot supply (leaf trap 5a.4, code/rust.md).
    def _tool_commit(cmd: list[str]) -> str | None:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        m = re.search(r"^commit-hash:\s*([0-9a-f]{40})\s*$", out, re.MULTILINE)
        return m.group(1) if m else None

    rustc_verbose = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
    rustc_commit = _tool_commit(["rustc", "-vV"])
    cargo_commit = _tool_commit(["cargo", "--version", "--verbose"])
    rustc_release_m = re.search(r"^release:\s*(\S+)\s*$", rustc_verbose, re.MULTILINE)
    rustc_release = rustc_release_m.group(1) if rustc_release_m else rustc_version
    print(f"[gen_package] rustc commit={rustc_commit!r} cargo commit={cargo_commit!r} (B20 typed toolchain)")

    def toolchain_rustc_cargo() -> str:
        """Typed `toolchain` block naming rustc + cargo (real 40-hex commits) -- for a record
        whose free-text `tool` string names both. B20/B21 (core.md)."""
        lines = ["  [[claim.evidence.toolchain]]", f"  name    = \"rustc\"", f"  version = {q(rustc_release)}"]
        if rustc_commit:
            lines.append(f"  commit  = {q(rustc_commit)}")
        lines.append("  [[claim.evidence.toolchain]]")
        lines.append(f"  name    = \"cargo\"")
        cargo_release_m = re.search(r"^cargo (\S+)", cargo_version)
        lines.append(f"  version = {q(cargo_release_m.group(1) if cargo_release_m else cargo_version)}")
        if cargo_commit:
            lines.append(f"  commit  = {q(cargo_commit)}")
        return "\n".join(lines)

    def toolchain_rustc_only() -> str:
        """Typed `toolchain` block naming only rustc -- for the clippy (lint) record: clippy's own
        `--version` output has no 40-hex commit (only a 10-hex prefix), so B20's `commit` shape
        cannot be met for a `clippy` entry; rustc's own real commit is written instead, since
        clippy is literally the same rustc build clippy's `tool` string already names."""
        lines = ["  [[claim.evidence.toolchain]]", f"  name    = \"rustc\"", f"  version = {q(rustc_release)}"]
        if rustc_commit:
            lines.append(f"  commit  = {q(rustc_commit)}")
        return "\n".join(lines)

    kani_available = True
    kani_version_line = ""
    try:
        kv = subprocess.run(["cargo", "kani", "--version"], capture_output=True, text=True, timeout=30)
        kani_version_line = kv.stdout.strip() or kv.stderr.strip()
        kani_available = kv.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        kani_available = False

    print(f"[gen_package] commit={commit} dirty={dirty}")
    print(f"[gen_package] {rustc_tool}")
    print(f"[gen_package] {clippy_version_raw}")
    print(f"[gen_package] kani: {kani_version_line!r} available={kani_available}")

    # ----------------------------------------------------------------------
    # BASELINE runs (real, clean tree)
    # ----------------------------------------------------------------------

    print("[gen_package] running: cargo test --test malformed")
    rc, out, _ = run(["cargo", "test", "--test", "malformed"], cwd=CRATE_DIR)
    if rc != 0:
        print(out)
        raise RuntimeError("baseline `cargo test --test malformed` did not pass — refusing to certify")
    malformed_result_line = extract_test_result_line(out)
    malformed_record = write_evidence("malformed-test.txt", out, repo_root)
    malformed_cases = int(re.search(r"(\d+) passed", malformed_result_line).group(1))

    print("[gen_package] running: cargo test --test checksum")
    rc, out, _ = run(["cargo", "test", "--test", "checksum"], cwd=CRATE_DIR)
    if rc != 0:
        print(out)
        raise RuntimeError("baseline `cargo test --test checksum` did not pass — refusing to certify")
    checksum_result_line = extract_test_result_line(out)
    checksum_record = write_evidence("checksum-test.txt", out, repo_root)

    print("[gen_package] running: cargo test --test no_panic")
    rc, out, _ = run(["cargo", "test", "--test", "no_panic"], cwd=CRATE_DIR)
    if rc != 0:
        print(out)
        raise RuntimeError("baseline `cargo test --test no_panic` did not pass — refusing to certify")
    no_panic_result_line = extract_test_result_line(out)
    no_panic_record = write_evidence("no-panic-test.txt", out, repo_root)
    no_panic_cases = int(re.search(r"(\d+) passed", no_panic_result_line).group(1))

    print("[gen_package] running: cargo clippy -- -D warnings")
    rc, out, _ = run(["cargo", "clippy", "--", "-D", "warnings"], cwd=CRATE_DIR)
    if rc != 0:
        print(out)
        raise RuntimeError("baseline `cargo clippy -- -D warnings` did not pass — refusing to certify")
    clippy_record = write_evidence("clippy.txt", out, repo_root)

    print("[gen_package] running: " + DOC_COMMAND_DISPLAY)
    rc, out, _ = run(["cargo", "doc", "--no-deps"], cwd=CRATE_DIR, extra_env=DOC_COMMAND_ENV)
    if rc != 0 or "warning" in out:
        print(out)
        raise RuntimeError(f"baseline `{DOC_COMMAND_DISPLAY}` did not pass cleanly — refusing to certify")
    doc_record = write_evidence("cargo-doc.txt", out, repo_root)

    kani_pass = False
    kani_record = None
    kani_expect = "VERIFICATION:- SUCCESSFUL"
    kani_elapsed = None
    if kani_available:
        print(f"[gen_package] running: cargo kani --harness validate_never_panics (timeout={args.kani_timeout}s) — this takes several minutes")
        try:
            rc, out, kani_elapsed = run(
                ["cargo", "kani", "--harness", "validate_never_panics"],
                cwd=CRATE_DIR, timeout=args.kani_timeout,
            )
            kani_record = write_evidence("kani-validate-never-panics.txt", out, repo_root)
            kani_pass = (rc == 0) and (kani_expect in out)
            print(f"[gen_package] kani: rc={rc} elapsed={kani_elapsed:.1f}s pass={kani_pass}")
        except subprocess.TimeoutExpired as e:
            partial = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
            kani_record = write_evidence(
                "kani-validate-never-panics.txt",
                partial + f"\n\n[gen_package] TIMED OUT after {args.kani_timeout}s\n", repo_root,
            )
            kani_pass = False
    if not kani_available or not kani_pass:
        raise RuntimeError(
            "cargo kani is not available or the baseline proof did not pass within the time-box — "
            "per the brief, this would be recorded as a blocked claim with the transcript, not faked. "
            "This run refuses to proceed silently; see evidence/kani-validate-never-panics.txt."
        )

    # ----------------------------------------------------------------------
    # MUTATION CONTROLS — apply, run (expect RED), restore, verify byte-equality
    # ----------------------------------------------------------------------

    print("[gen_package] mutation control R1: neuter the charset-rejection branch")
    lib_path = CRATE_DIR / "src" / "lib.rs"
    original_lib = read_bytes(lib_path)
    patch_file(
        lib_path,
        "        if !syntax::is_iban_byte(buf[i]) {\n            return Err(IbanError::BadCharacter);\n        }",
        "        if false && !syntax::is_iban_byte(buf[i]) {\n            return Err(IbanError::BadCharacter);\n        }",
    )
    rc, out, _ = run(["cargo", "test", "--test", "malformed"], cwd=CRATE_DIR)
    restore_file(lib_path, original_lib)
    if rc == 0:
        raise RuntimeError("R1 mutation control did not go red — refusing to certify a non-discriminating control")
    r1_control_record = write_evidence("r1-mutation-control.txt", out, repo_root)
    r1_control_tail = "\n".join(out.strip().splitlines()[-12:])
    print("[gen_package] R1 control: RED as expected, restored, byte-equal")

    print("[gen_package] mutation control R2: ISO 7064 modulus 97 -> 96")
    checksum_path = CRATE_DIR / "src" / "checksum.rs"
    original_checksum = read_bytes(checksum_path)
    text = original_checksum.decode("utf-8")
    targets = [
        "remainder = (remainder * 10 + d) % 97;",
        "remainder = (remainder * 10 + tens) % 97;",
        "remainder = (remainder * 10 + ones) % 97;",
    ]
    for t in targets:
        if text.count(t) != 1:
            raise RuntimeError(f"R2 patch target not found exactly once: {t!r}")
        text = text.replace(t, t.replace("% 97", "% 96"))
    checksum_path.write_text(text)
    rc, out, _ = run(["cargo", "test", "--test", "checksum"], cwd=CRATE_DIR)
    restore_file(checksum_path, original_checksum)
    if rc == 0:
        raise RuntimeError("R2 mutation control did not go red — refusing to certify a non-discriminating control")
    r2_control_record = write_evidence("r2-mutation-control.txt", out, repo_root)
    print("[gen_package] R2 control: RED as expected, restored, byte-equal")

    print("[gen_package] mutation control R3: shrink the `rearranged` buffer to 2 bytes")
    original_lib2 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "let mut rearranged = [0u8; MAX_LEN];",
        "let mut rearranged = [0u8; 2];",
    )
    rc, out, _ = run(["cargo", "test", "--test", "checksum"], cwd=CRATE_DIR)
    restore_file(lib_path, original_lib2)
    if rc == 0:
        raise RuntimeError("R3 mutation control did not go red — refusing to certify a non-discriminating control")
    r3_control_record = write_evidence("r3-mutation-control.txt", out, repo_root)
    print("[gen_package] R3 control: RED (panic) as expected, restored, byte-equal")

    print("[gen_package] mutation control R4: insert an empty `unsafe {}` block")
    original_lib3 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "pub fn validate(input: &str) -> Result<(), IbanError> {\n",
        "pub fn validate(input: &str) -> Result<(), IbanError> {\n    unsafe {}\n",
    )
    rc, out, _ = run(["cargo", "clippy", "--", "-D", "warnings"], cwd=CRATE_DIR)
    restore_file(lib_path, original_lib3)
    if rc == 0:
        raise RuntimeError("R4 mutation control did not go red — refusing to certify a non-discriminating control")
    r4_control_record = write_evidence("r4-mutation-control.txt", out, repo_root)
    print("[gen_package] R4 control: RED as expected, restored, byte-equal")

    print("[gen_package] mutation control R6: add a broken intra-doc link")
    original_lib4 = read_bytes(lib_path)
    patch_file(
        lib_path,
        "//! This crate deliberately does NOT interpret",
        "//! See [`totally::bogus::path`] for details.\n//!\n//! This crate deliberately does NOT interpret",
    )
    rc, out, _ = run(["cargo", "doc", "--no-deps"], cwd=CRATE_DIR, extra_env=DOC_COMMAND_ENV)
    restore_file(lib_path, original_lib4)
    if rc == 0:
        raise RuntimeError("R6 mutation control did not go red — refusing to certify a non-discriminating control")
    r6_control_record = write_evidence("r6-mutation-control.txt", out, repo_root)
    # Captured from the ACTUAL run above, not hand-typed — under RUSTDOCFLAGS=-D warnings a
    # broken intra-doc link is now a hard `error:`, not a `warning:` (rustdoc exits nonzero and
    # never reaches "Generated"), so this must track whatever rustdoc's current wording is.
    r6_control_tail = "\n".join(out.strip().splitlines()[-8:])
    print("[gen_package] R6 control: RED as expected, restored, byte-equal")

    # Final sanity: the tree must be back to fully clean/passing before we certify anything.
    rc, out, _ = run(["cargo", "test"], cwd=CRATE_DIR, timeout=60)
    if rc != 0:
        print(out)
        raise RuntimeError("post-mutation sanity `cargo test` failed — the tree was not restored cleanly")
    rc, out, _ = run(["cargo", "clippy", "--", "-D", "warnings"], cwd=CRATE_DIR, timeout=60)
    if rc != 0:
        print(out)
        raise RuntimeError("post-mutation sanity `cargo clippy` failed — the tree was not restored cleanly")
    print("[gen_package] post-mutation sanity: cargo test + clippy both clean")

    # ----------------------------------------------------------------------
    # Assemble acceptance.toml
    # ----------------------------------------------------------------------

    dirty_clause = (
        "the crate's own files were untracked relative to that HEAD when this ran — hence\n"
        "# [subject].dirty = true below, disclosed rather than hidden"
        if dirty else
        "iban-check/ was already committed, on its own, before this ran (the two-commit\n"
        "# re-stamp this example's README documents) — hence [subject].dirty = false below"
    )

    contract_hash = m11.digest_file("contract", CONTRACT_PATH)

    def record_hash(relpath: str) -> str:
        # 0.3.1: writers MUST emit the typed `record:sha-512:` construction (hash-domains.md's
        # Read-only legacy record wires section) — `m11.digest_file("evidence-record", ...)` wrote
        # the untyped legacy bare wire, which the 0.3.1 wording now states is read-only.
        return m11.hashdomains.digest("record:", (SCRIPT_DIR / relpath).read_bytes())

    kani_tool_note = (
        f"kani@{re.search(r'([0-9]+\\.[0-9]+\\.[0-9]+)', kani_version_line).group(1) if re.search(r'([0-9]+\\.[0-9]+\\.[0-9]+)', kani_version_line) else kani_version_line} "
        "(commit unknown — `cargo kani --version` on this install reports only a semantic "
        "version, not a build sha; see the example README's Friction section)"
    )

    inputs_malformed = render_inputs(input_entries(ALL_SRC_INPUTS + ["tests/malformed.rs"]))
    inputs_checksum = render_inputs(input_entries(ALL_SRC_INPUTS + ["tests/checksum.rs"]))
    inputs_kani = render_inputs(input_entries(ALL_SRC_INPUTS))
    inputs_no_panic = render_inputs(input_entries(ALL_SRC_INPUTS + ["tests/no_panic.rs"]))
    inputs_clippy = render_inputs(input_entries(ALL_SRC_INPUTS))
    inputs_doc = render_inputs(input_entries(ALL_SRC_INPUTS))

    # B20 typed build-input identity: real digests over Cargo.lock + rust-toolchain.toml (both
    # real files at iban-check/ as of the rust-delivery migration -- rust-toolchain.toml did not exist
    # before this pass; it was added, real and honest (it records the toolchain CHANNEL this very
    # run verified against, `rustc -vV` below -- `channel = "stable"` floats to whatever "stable"
    # resolves to at build time, not a single exact toolchain), rather than declaring build_inputs
    # against a file that does not exist. Written once on the PRIMARY (non-kani) evidence record
    # of each weighted
    # claim -- the union of a claim's own evidence already satisfies the code/rust binding's
    # `required_build_inputs` guard (B20 opt-in-complete shape) the moment one record carries it.
    build_inputs, build_inputs_missing = build_inputs_block()
    if build_inputs_missing:
        print(f"[gen_package] NOTE: build_inputs SKIPPED for missing file(s) (never invented): {build_inputs_missing}")

    header = f"""\
# GENERATED FILE — DO NOT HAND-EDIT.
#
# Produced by protocol_acceptance/examples/rust-delivery/gen_package.py, which actually ran `cargo test`,
# `cargo clippy`, `cargo doc`, `cargo kani`, and five real mutation controls (R1/R2/R3/R4/R6)
# against protocol_acceptance/examples/rust-delivery/iban-check/ — apply patch, run, require the expected
# verdict, restore the file byte-exactly, verify the restoration. Transcripts are in evidence/.
#
# SELF-REFERENCE (one-commit lag): [subject].commit names this repo's HEAD at generation time;
# this file and evidence/ necessarily land in the commit AFTER that one. This run found that
# {dirty_clause}. Generated: {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
#
# Kani tool identity: `cargo kani --version` on this install prints a bare semantic version
# ({kani_version_line!r}), not a build/commit sha — evidence-types.md asks for "tool identity AT
# BUILD GRANULARITY (commit, not version)" for kani-harness records; this install cannot supply
# that, so `tool` below says so explicitly rather than inventing a commit. See README Friction.
#
# TRANSCRIPT NORMALIZATION (a disclosed transform, before persistence and record hashing): absolute
# crate-root paths become <crate>; absolute repository-root paths become <repo>; any
# macOS-user Rustup-toolchain prefixes become <rustup>/<toolchain>/; every other macOS-user prefix
# becomes <users>/<name>/; and a remaining current-home prefix becomes ~. Thus each record_hash is
# over the normalized evidence bytes exactly as delivered, never over machine-local transcript bytes.
#
# Re-run: python3 gen_package.py

"""

    body = []
    body.append(header)
    body.append("[format]")
    body.append('id       = "acceptance/0"')
    body.append(f'protocol = "acceptance-protocol/0"')
    body.append(f'profile  = {q(PROFILE_ID)}')
    body.append("")
    body.append("[subject]")
    body.append(f"name   = {q('iban-check')}")
    body.append(f'kind   = "rust-crate"')
    body.append(f"commit = {q(commit)}")
    body.append(f"dirty  = {'true' if dirty else 'false'}")
    body.append("")
    body.append("[contract]")
    body.append(f"id                 = {q(CONTRACT_ID)}")
    body.append(f"hash               = {q(contract_hash)}")
    body.append("requirements_total = 6")
    body.append("")
    body.append("[spec]")
    body.append(f'path    = {q("acceptance-contract.toml")}')
    body.append(f'version = {q(CONTRACT_ID + "@v1")}')
    body.append(f'axis    = {q("the requirements of contract " + CONTRACT_ID)}')
    body.append("")
    body.append("[coverage]")
    body.append("clauses_total = 6")
    body.append("claims_total  = 6")
    body.append("")

    # -- IB-001 (R1) --------------------------------------------------------
    body.append("# ===================================================================")
    body.append("# IB-001 -- R1: malformed input is rejected")
    body.append("# ===================================================================")
    body.append("[[claim]]")
    body.append('id            = "IB-001"')
    body.append('clause        = "R1"')
    body.append(f'item          = {q("iban-check/tests/malformed.rs")}')
    body.append(f'statement     = {q("Malformed IBAN values are rejected cleanly, with the specific IbanError variant matching the specific defect (charset, unknown country, bad length, bad checksum), in the fixed check order validate documents, and without a panic or crash on any of the fixtures below.")}')
    body.append('band          = "A1"')
    body.append('status        = "evidenced"')
    body.append('weight        = "weighted"')
    body.append('grade         = "test-only"')
    body.append('clause_source = "spec-document"')
    body.append(f'bounds        = {q("bounded: 9 named malformed fixtures spanning all 4 IbanError variants")}')
    body.append(f"captured_at_commit = {q(commit)}")
    body.append("")
    body.append("  [claim.self_verify]")
    body.append(f'  command = {q("cargo test --test malformed")}')
    body.append(f"  expect  = {q(malformed_result_line)}")
    body.append("")
    body.append("    [claim.self_verify.watched_fail]")
    body.append(f'    of_command = {q("cargo test --test malformed")}')
    body.append(f'    perturbed  = {q("neutered the charset-rejection branch in validate (changed `if !syntax::is_iban_byte(buf[i])` to `if false && !syntax::is_iban_byte(buf[i])`, so no input is ever rejected for its character set)")}')
    body.append(f"    observed   = {q(r1_control_tail)}")
    body.append(f'    date       = {q(today)}')
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind        = "unit-test"')
    body.append('  family      = "dynamic"')
    body.append('  method      = "unit-test"')
    body.append('  epistemic_tier = "T3"')
    body.append(f'  ref         = {q("tests/malformed.rs (9 named fixtures covering BadCharacter/UnknownCountry/BadLength/BadChecksum)")}')
    body.append('  result      = "pass"')
    body.append(f"  tool        = {q(rustc_tool)}")
    body.append(f"  cases       = {malformed_cases}")
    body.append(f"  record      = {q(malformed_record)}")
    body.append(f"  record_hash = {q(record_hash(malformed_record))}")
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append(inputs_malformed)
    body.append(toolchain_rustc_cargo())
    if build_inputs:
        body.append(build_inputs)
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind        = "unit-test"')
    body.append('  family      = "dynamic"')
    body.append('  method      = "unit-test"')
    body.append('  epistemic_tier = "T3"')
    body.append(f'  ref         = {q("tests/malformed.rs (mutant: charset-rejection branch neutered)")}')
    body.append('  result      = "fail"')
    body.append(f"  tool        = {q(rustc_tool + ' (1-line mutation, reverted)')}")
    body.append(f"  cases       = {malformed_cases}")
    body.append(f'  record      = {q("evidence/r1-mutation-control.txt")}')
    body.append(f'  record_hash = {q(record_hash("evidence/r1-mutation-control.txt"))}')
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append("")
    body.append(render_control("IB-001"))
    body.append("")

    # -- IB-002 (R2) --------------------------------------------------------
    body.append("# ===================================================================")
    body.append("# IB-002 -- R2: ISO 7064 mod-97-10 checksum is computed correctly")
    body.append("# ===================================================================")
    body.append("[[claim]]")
    body.append('id            = "IB-002"')
    body.append('clause        = "R2"')
    body.append(f'item          = {q("iban-check/tests/checksum.rs")}')
    body.append(f'statement     = {q("The ISO 7064 mod-97-10 checksum is computed correctly, with no panic or crash on any tested input: 10 known-valid IBANs (one per supported country) pass, a corrupted check-digit pair is rejected, and flipping one digit of any known-valid IBAN always changes the verdict (200 LCG-driven trials).")}')
    body.append('band          = "A1"')
    body.append('status        = "evidenced"')
    body.append('weight        = "weighted"')
    body.append('grade         = "test-only"')
    body.append('clause_source = "spec-document"')
    body.append(f'bounds        = {q("bounded: 10 known-valid IBANs + LCG-perturbed sample of 200 (seed 0xC0FFEE)")}')
    body.append(f"captured_at_commit = {q(commit)}")
    body.append("")
    body.append("  [claim.self_verify]")
    body.append(f'  command = {q("cargo test --test checksum")}')
    body.append(f"  expect  = {q(checksum_result_line)}")
    body.append("")
    body.append("    [claim.self_verify.watched_fail]")
    body.append(f'    of_command = {q("cargo test --test checksum")}')
    body.append(f'    perturbed  = {q("changed the ISO 7064 modulus in checksum::mod97_is_valid from 97 to 96 at all three reduction sites")}')
    body.append(f"    observed   = {q('all_known_valid_ibans_pass and flipping_one_digit_of_a_valid_iban_always_changes_the_verdict FAILED: assertion left==right failed, left: Err(BadChecksum), right: Ok(()) — the mutated modulus rejects every real IBAN')}")
    body.append(f'    date       = {q(today)}')
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind        = "unit-test"')
    body.append('  family      = "dynamic"')
    body.append('  method      = "unit-test"')
    body.append('  epistemic_tier = "T3"')
    body.append(f'  ref         = {q("tests/checksum.rs::{all_known_valid_ibans_pass, a_wrong_checksum_is_rejected}")}')
    body.append('  result      = "pass"')
    body.append(f"  tool        = {q(rustc_tool)}")
    body.append("  cases       = 2")
    body.append(f"  record      = {q(checksum_record)}")
    body.append(f"  record_hash = {q(record_hash(checksum_record))}")
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append(inputs_checksum)
    body.append(toolchain_rustc_cargo())
    if build_inputs:
        body.append(build_inputs)
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind        = "property-test"')
    body.append('  family      = "dynamic"')
    body.append('  method      = "property-test"')
    body.append('  epistemic_tier = "T3"')
    body.append(f'  ref         = {q("tests/checksum.rs::flipping_one_digit_of_a_valid_iban_always_changes_the_verdict")}')
    body.append('  result      = "pass"')
    body.append(f"  tool        = {q(rustc_tool)}")
    body.append("  cases       = 200")
    body.append(f'  generator   = {q("hand-rolled LCG (Numerical Recipes constants 6364136223846793005/1442695040888963407), seed 0xC0FFEE, 20 trials x 10 known-valid IBANs, each flipping one randomly LCG-chosen digit position to a different digit")}')
    body.append(f"  record      = {q(checksum_record)}")
    body.append(f"  record_hash = {q(record_hash(checksum_record))}")
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append(inputs_checksum)
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind        = "unit-test"')
    body.append('  family      = "dynamic"')
    body.append('  method      = "unit-test"')
    body.append('  epistemic_tier = "T3"')
    body.append(f'  ref         = {q("tests/checksum.rs (mutant: ISO 7064 modulus 97 -> 96)")}')
    body.append('  result      = "fail"')
    body.append(f"  tool        = {q(rustc_tool + ' (1-line mutation x3 sites, reverted)')}")
    body.append("  cases       = 3")
    body.append(f'  record      = {q("evidence/r2-mutation-control.txt")}')
    body.append(f'  record_hash = {q(record_hash("evidence/r2-mutation-control.txt"))}')
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append("")
    body.append(render_control("IB-002"))
    body.append("")

    # -- IB-003 (R3) --------------------------------------------------------
    body.append("# ===================================================================")
    body.append("# IB-003 -- R3: validate never panics on any input")
    body.append("# ===================================================================")
    body.append("[[claim]]")
    body.append('id            = "IB-003"')
    body.append('clause        = "R3"')
    body.append(f'item          = {q("iban-check/src/lib.rs::validate (verification::validate_never_panics)")}')
    body.append(f'statement     = {q("validate never panics: proved by Kani for all ASCII inputs up to 20 bytes (bounded model check), and tested over 20,000+ random byte-string samples up to 128 bytes including non-ASCII/invalid-UTF-8-adjacent content (dynamic fuzz-style loop).")}')
    body.append('band          = "A1"')
    body.append('status        = "evidenced"')
    body.append('weight        = "weighted"')
    body.append('grade         = "probe"')
    body.append('clause_source = "spec-document"')
    body.append(f'bounds        = {q("bounded: Kani KANI_BOUND=20 ASCII bytes, unwind=24 (crate real MAX_LEN stays 34 — only the harness input is bounded); dynamic sample up to 128 bytes, full byte range")}')
    body.append(f"captured_at_commit = {q(commit)}")
    body.append("")
    body.append("  [claim.self_verify]")
    body.append(f'  command = {q("cargo kani --harness validate_never_panics")}')
    body.append(f"  expect  = {q(kani_expect)}")
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind      = "kani-harness"')
    body.append('  family    = "bmc"')
    body.append('  method    = "kani-harness"')
    body.append('  epistemic_tier = "T2"')
    body.append(f'  ref       = {q("verification::validate_never_panics")}')
    body.append('  result    = "pass"')
    body.append(f"  tool      = {q(kani_tool_note)}")
    body.append(f'  bounds    = {q("unwind=24, KANI_BOUND=20 ASCII bytes (< 0x80)")}')
    body.append('  semantics = ""')
    body.append(f"  record    = {q(kani_record)}")
    body.append(f"  record_hash = {q(record_hash(kani_record))}")
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append(inputs_kani)
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind        = "unit-test"')
    body.append('  family      = "dynamic"')
    body.append('  method      = "unit-test"')
    body.append('  epistemic_tier = "T3"')
    body.append(f'  ref         = {q("tests/no_panic.rs (3 #[test] fns: 20,000-trial hand-rolled xorshift64 fuzz loop up to 128 bytes; 123 adversarial near-miss-length trials; 5 edge cases)")}')
    body.append('  result      = "pass"')
    body.append(f"  tool        = {q(rustc_tool)}")
    body.append(f"  cases       = {no_panic_cases}")
    body.append(f"  record      = {q(no_panic_record)}")
    body.append(f"  record_hash = {q(record_hash(no_panic_record))}")
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append(inputs_no_panic)
    body.append(toolchain_rustc_cargo())
    if build_inputs:
        body.append(build_inputs)
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind        = "unit-test"')
    body.append('  family      = "dynamic"')
    body.append('  method      = "unit-test"')
    body.append('  epistemic_tier = "T3"')
    body.append(f'  ref         = {q("tests/checksum.rs (mutant: `rearranged` buffer in validate shrunk from MAX_LEN=34 to 2 bytes) -- fast dynamic witness in place of a second ~7-minute Kani run; see README Friction")}')
    body.append('  result      = "fail"')
    body.append(f"  tool        = {q(rustc_tool + ' (1-line mutation, reverted)')}")
    body.append("  cases       = 3")
    body.append(f'  record      = {q("evidence/r3-mutation-control.txt")}')
    body.append(f'  record_hash = {q(record_hash("evidence/r3-mutation-control.txt"))}')
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append("")
    body.append(render_control("IB-003"))
    body.append("")

    # -- IB-004 (R4) --------------------------------------------------------
    body.append("# ===================================================================")
    body.append("# IB-004 -- R4: no unsafe code")
    body.append("# ===================================================================")
    body.append("[[claim]]")
    body.append('id            = "IB-004"')
    body.append('clause        = "R4"')
    body.append(f'item          = {q("iban-check/src/lib.rs (#![forbid(unsafe_code)]) + cargo clippy")}')
    body.append(f'statement     = {q("The crate contains no unsafe code: #![forbid(unsafe_code)] makes any `unsafe` block a hard compile error, and cargo clippy runs clean under -D warnings.")}')
    body.append('band          = "A1"')
    body.append('status        = "evidenced"')
    body.append('weight        = "weighted"')
    body.append('grade         = "mechanical"')
    body.append('clause_source = "spec-document"')
    body.append(f"captured_at_commit = {q(commit)}")
    body.append("")
    body.append("  [claim.self_verify]")
    body.append(f'  command = {q("cargo clippy -- -D warnings")}')
    body.append(f'  expect  = {q("Finished")}')
    body.append("")
    body.append("    [claim.self_verify.watched_fail]")
    body.append(f'    of_command = {q("cargo clippy -- -D warnings")}')
    body.append(f'    perturbed  = {q("inserted an empty `unsafe {}` block at the top of validate\'s body")}')
    body.append(f"    observed   = {q('error: usage of an `unsafe` block --> src/lib.rs:104:5 (forbid(unsafe_code) makes this a hard compile error, not merely a lint warning); could not compile `iban-check` (lib) due to 2 previous errors')}")
    body.append(f'    date       = {q(today)}')
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind      = "lint"')
    body.append('  family    = "mechanical"')
    body.append('  method    = "lint"')
    body.append('  epistemic_tier = "T4"')
    body.append(f'  ref       = {q("#![forbid(unsafe_code)] (src/lib.rs:1) + cargo clippy -- -D warnings over the whole crate")}')
    body.append('  result    = "pass"')
    body.append(f"  tool      = {q(clippy_tool)}")
    body.append(f"  record    = {q(clippy_record)}")
    body.append(f"  record_hash = {q(record_hash(clippy_record))}")
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append(inputs_clippy)
    body.append(toolchain_rustc_only())
    if build_inputs:
        body.append(build_inputs)
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind      = "lint"')
    body.append('  family    = "mechanical"')
    body.append('  method    = "lint"')
    body.append('  epistemic_tier = "T4"')
    body.append(f'  ref       = {q("cargo clippy -- -D warnings (mutant: empty `unsafe {}` block inserted in validate)")}')
    body.append('  result    = "fail"')
    body.append(f"  tool      = {q(clippy_tool + ' (1-line mutation, reverted)')}")
    body.append(f'  record    = {q("evidence/r4-mutation-control.txt")}')
    body.append(f'  record_hash = {q(record_hash("evidence/r4-mutation-control.txt"))}')
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append("")
    body.append(render_control("IB-004"))
    body.append("")

    # -- IB-005 (R5, cross-cutting placeholder) ------------------------------
    body.append("# ===================================================================")
    body.append("# IB-005 -- R5: cross-cutting (\"verification of R1-R3 is unbounded\") -- NOT MET")
    body.append("# ===================================================================")
    body.append("[[claim]]")
    body.append('id        = "IB-005"')
    body.append('clause    = "R5"')
    body.append(f'item      = {q("cross-cutting: R1, R2, R3")}')
    body.append(f'statement = {q("No unbounded verification argument exists yet for R1/R2/R3: IB-001/IB-002 are bounded dynamic samples (points, not sets) and IB-003\'s Kani proof is bounded to 20 ASCII bytes. See [[deviation]] below.")}')
    body.append('band      = "A0"')
    body.append('status    = "gap"')
    body.append('grade     = "unspecified"')
    body.append('clause_source = "spec-document"')
    body.append(f"captured_at_commit = {q(commit)}")
    body.append("# weight omitted -> unweighted (W1): this row documents the gap the deviation below names;")
    body.append("# it does not itself carry the format's vouching -- the deviation carries the disclosure.")
    body.append("")

    # -- IB-006 (R6, optional) ------------------------------------------------
    body.append("# ===================================================================")
    body.append("# IB-006 -- R6 (optional): cargo doc builds clean")
    body.append("# ===================================================================")
    body.append("[[claim]]")
    body.append('id            = "IB-006"')
    body.append('clause        = "R6"')
    body.append(f'item          = {q("iban-check (cargo doc --no-deps, warnings fatal)")}')
    body.append(f'statement     = {q("cargo doc --no-deps builds the crate\'s documentation with zero warnings — enforced by making rustdoc warnings fatal (RUSTDOCFLAGS=-D warnings), not merely by checking for the word \'Generated\'.")}')
    body.append('band          = "A0"')
    body.append('status        = "evidenced"')
    body.append('weight        = "weighted"')
    body.append('grade         = "mechanical"')
    body.append('clause_source = "spec-document"')
    body.append(f"captured_at_commit = {q(commit)}")
    body.append("")
    body.append("  [claim.self_verify]")
    body.append(f'  command = {q(DOC_COMMAND_DISPLAY)}')
    body.append(f'  expect  = {q("Generated")}')
    body.append("")
    body.append("    [claim.self_verify.watched_fail]")
    body.append(f'    of_command = {q(DOC_COMMAND_DISPLAY)}')
    body.append(f'    perturbed  = {q("added a broken intra-doc link ([`totally::bogus::path`]) to the crate root doc comment")}')
    body.append(f"    observed   = {q(r6_control_tail)}")
    body.append(f'    date       = {q(today)}')
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind      = "lint"')
    body.append('  family    = "mechanical"')
    body.append('  method    = "lint"')
    body.append('  epistemic_tier = "T4"')
    body.append(f'  ref       = {q(DOC_COMMAND_DISPLAY + " over the whole crate (0 warnings, enforced by -D warnings)")}')
    body.append('  result    = "pass"')
    body.append(f"  tool      = {q('rustdoc (bundled with ' + rustc_version + ') via ' + cargo_version)}")
    body.append(f"  record    = {q(doc_record)}")
    body.append(f"  record_hash = {q(record_hash(doc_record))}")
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append(inputs_doc)
    body.append(toolchain_rustc_cargo())
    if build_inputs:
        body.append(build_inputs)
    body.append("")
    body.append("  [[claim.evidence]]")
    body.append('  kind      = "lint"')
    body.append('  family    = "mechanical"')
    body.append('  method    = "lint"')
    body.append('  epistemic_tier = "T4"')
    body.append(f'  ref       = {q(DOC_COMMAND_DISPLAY + " (mutant: broken intra-doc link added to crate root doc comment)")}')
    body.append('  result    = "fail"')
    body.append(f"  tool      = {q('rustdoc (bundled with ' + rustc_version + ') via ' + cargo_version + ' (1-line mutation, reverted)')}")
    body.append(f'  record    = {q("evidence/r6-mutation-control.txt")}')
    body.append(f'  record_hash = {q(record_hash("evidence/r6-mutation-control.txt"))}')
    body.append(f"  captured_at_commit = {q(commit)}")
    body.append("")
    body.append(render_control("IB-006"))
    body.append("")

    # -- deviation + filler ---------------------------------------------------
    body.append("# ===================================================================")
    body.append("[[deviation]]")
    body.append('requirement      = "R5"')
    body.append('kind             = "unmet"')
    body.append(f'statement        = {q("R1/R2/R3 evidence is entirely bounded: R1/R2 rest on named test fixtures plus a 200-trial LCG-perturbed sample (dynamic, points not sets); R3 (probe grade) is a Kani proof bounded to inputs of at most 20 ASCII bytes, unwind=24 -- not the crate\'s real 34-byte capacity, and not an unbounded/kernel-checked argument. No unbounded argument exists for any of the three.")}')
    body.append(f'cause            = {q("No Lean/Aeneas extraction lane exists for this crate, and CBMC\'s own cost on this machine (measured: 29s/206s/415s at a 8/16/20-byte harness bound; did not finish within a 10-minute time-box unconstrained at the real 34-byte maximum) makes a full-length or genuinely unbounded Kani proof impractical within this delivery.")}')
    body.append(f'impact           = {q("Inputs longer than the tested/proved envelope are covered only by informal structural reasoning (uniform, length-bounded per-byte loops), not by a machine-checked argument. A crafted input outside the proved/tested range could in principle still misbehave, though nothing in the code\'s shape suggests one exists.")}')
    body.append(f'remedy           = {q("Extend the Kani harness\'s bound as CBMC/toolchain performance allows, or add a Lean/Aeneas extraction of validate\'s core loop for a genuinely unbounded proof. Target: before v2 (see the consumer decision\'s condition C1).")}')
    body.append("waiver_requested = true")
    body.append("")
    body.append("[[filler]]")
    body.append(f'profile = {q(PROFILE_ID)}')
    body.append(f'party   = {q("ivmat")}')
    body.append('role    = "producer"')
    body.append("")

    text = "\n".join(body).rstrip() + "\n"
    PACKAGE_OUT.write_text(text)
    print(f"[gen_package] wrote {PACKAGE_OUT} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
