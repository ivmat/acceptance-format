#!/usr/bin/env python3
"""Capture cargo/Kani runs and mutation controls, then call assemble-package.

The fill.toml file contains the semantic slice. The generic assembler supplies claim,
coverage, evidence and identity bindings. This example adds mechanically measured B20
build/tool identities with the reference TOML encoder, then runs strict validators.
A full regeneration requires a clean committed crate, clippy, and permission to run
the several-minute Kani harness. Never attach a newly measured identity to an old run.
Usage: python3 gen_package.py [--kani-timeout SECONDS]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tomllib
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
SPECIFICATION_PATH = SCRIPT_DIR / "acceptance-specification.toml"
PACKAGE_OUT = SCRIPT_DIR / "acceptance.toml"
PROTOCOL_TOOL = SCRIPT_DIR.parent.parent / "tools/acceptance_protocol.py"
FORMAT_TOOL = SCRIPT_DIR.parents[2] / "format_acceptance/tools/check_acceptance.py"

# Pinned so every cargo invocation below writes build output under the crate's own directory,
# regardless of whatever CARGO_TARGET_DIR (if any) the calling shell/worker happens to export.
# This is not a new placeholder: the existing CRATE_DIR -> <crate> transcript replacement already
# covers this exact path, so no machine-local or worker-local target-dir name can ever reach a
# persisted evidence record (README "Transcript normalization").
CARGO_TARGET_DIR = CRATE_DIR / "target"

# protocol_acceptance/tools/m11.py — the shared M11 hashing helper (stdlib-only itself).
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "tools"))
import m11  # noqa: E402
import acceptance_protocol as AP

SPECIFICATION_ID = "AC-2026-0001"
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
    RUNS.append((cmd, proc.returncode, proc.stdout, extra_env or {}))
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
    cmd, rc, output, extra_env = RUNS[-1]
    if output != text:
        raise RuntimeError("record differs from captured command output")
    command = " ".join(cmd)
    if extra_env:
        command = DOC_COMMAND_DISPLAY
    CAPTURED[name] = {"id": Path(name).stem, "command": command, "returncode": rc,
                      "role": "control" if "mutation-control" in name else "primary",
                      "transcript": "transcripts/" + name, "record": "evidence/" + name}
    return f"evidence/{name}"


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
    recorded = {}
    if PACKAGE_OUT.is_file() and PACKAGE_OUT.parent == SCRIPT_DIR:
        package = tomllib.loads(PACKAGE_OUT.read_text())
        for claim in package.get("claim", []):
            for evidence in claim.get("evidence", []):
                for entry in evidence.get("build_inputs", []):
                    recorded[entry["path"]] = entry["digest"]
    for name in REQUIRED_BUILD_INPUT_NAMES:
        full = CRATE_DIR / name
        snapshot = SCRIPT_DIR / name
        if name in recorded and snapshot.is_file():
            actual = m11.hashdomains.digest("artifact:", snapshot.read_bytes())
            if actual != recorded[name]:
                raise RuntimeError(f"{snapshot} differs from the recorded package build input")
            full = snapshot
        if not full.is_file():
            missing.append(name)
            continue
        digest = m11.hashdomains.digest("artifact:", full.read_bytes())
        if full != SCRIPT_DIR / name:
            _ensure_build_input_symlink(name)
        lines.append("  [[claim.evidence.build_inputs]]")
        lines.append(f"  path   = {AP._toml_scalar(name)}")
        lines.append(f"  digest = {AP._toml_scalar(digest)}")
    return "\n".join(lines), missing


RUNS = []
CAPTURED = {}


def dump(path, data, comment="# GENERATED; do not hand-edit.\n"):
    """Generic table layout, with scalar encoding supplied by the reference tool."""
    lines = [comment.rstrip()]
    def table(values, prefix):
        nested = []
        for key, value in values.items():
            key = AP._toml_key(key)
            arrays = isinstance(value, list) and value and isinstance(value[0], dict)
            if isinstance(value, dict) or arrays:
                nested.append((key, value, arrays))
            else:
                lines.append(f"{key} = {AP._toml_scalar(value)}")
        for key, value, arrays in nested:
            path_key = ".".join(prefix + [key])
            for child in value if arrays else [value]:
                lines.extend(["", f"[[{path_key}]]" if arrays else f"[{path_key}]"])
                table(child, prefix + [key])
    table(data, [])
    path.write_text("\n".join(lines) + "\n")


def capture_identity(probes):
    """FV adoption §6: identify both the installed bundle and the launcher."""
    version = re.search(r"(\d+\.\d+\.\d+)", probes["cargo kani --version"]).group(1)
    bundle = Path.home() / ".kani" / ("kani-" + version)
    if not bundle.is_dir():
        raise RuntimeError("Kani bundle unavailable; refusing version-only identity")
    lines = [f"{p.relative_to(bundle).as_posix()}:{hashlib.sha256(p.read_bytes()).hexdigest()}"
             for p in sorted(bundle.rglob("*")) if p.is_file() and not p.is_symlink()]
    manifest = ("\n".join(lines) + "\n").encode()
    EVIDENCE_DIR.mkdir(exist_ok=True)
    (EVIDENCE_DIR / "kani-bundle.manifest.txt").write_bytes(manifest)
    launcher = Path(shutil.which("cargo-kani") or "")
    entries = [{"name": "kani-bundle", "version": version,
                "digest": m11.hashdomains.digest("artifact:", manifest)},
               {"name": "cargo-kani-launcher", "version": version,
                "digest": m11.hashdomains.digest("artifact:", launcher.read_bytes())}]
    for name, probe in [("rustc", "rustc -vV"), ("cargo", "cargo --version --verbose")]:
        commit = re.search(r"^commit-hash: ([0-9a-f]{40})$", probes[probe], re.M)
        if not commit:
            raise RuntimeError(f"missing exact {name} commit")
        entries.append({"name": name, "commit": commit.group(1)})
    kani_rustc = subprocess.run([str(bundle / "toolchain/bin/rustc"), "-vV"],
                               capture_output=True, text=True, check=True).stdout
    kani_commit = re.search(r"^commit-hash: ([0-9a-f]{40})$", kani_rustc, re.M)
    if not kani_commit:
        raise RuntimeError("missing exact Kani compiler toolchain identity")
    entries.append({"name": "kani-rustc", "commit": kani_commit.group(1)})
    return entries


def assemble_captured(commit, date, probes, identity):
    transcript_dir = SCRIPT_DIR / "transcripts"
    transcript_dir.mkdir(exist_ok=True)
    for name, row in CAPTURED.items():
        prefix = "".join(f"$ {command}\n{output}\n" for command, output in probes.items())
        (transcript_dir / name).write_text(prefix + "$ " + row["command"] + "\n" +
                                          (EVIDENCE_DIR / name).read_text())
    dump(SCRIPT_DIR / "manifest.toml", {"report": {"commit": commit, "date": date},
                                       "run": list(CAPTURED.values())})
    fill = tomllib.loads((SCRIPT_DIR / "fill.toml").read_text())
    by_id = {row["id"]: row for row in CAPTURED.values()}
    for claim in fill["claim"]:
        if "watched_fail" in claim:
            control = next(by_id[e["run"]] for e in claim["evidence"]
                           if by_id[e["run"]]["role"] == "control")
            claim["watched_fail"]["observed"] = "\n".join(
                (SCRIPT_DIR / control["record"]).read_text().strip().splitlines()[-12:])
        recipe = claim.get("recipe", {})
        if recipe.get("command", "").startswith("cargo test"):
            primary = next(row for row in CAPTURED.values() if row["role"] == "primary"
                           and row["command"] == recipe["command"])
            recipe["expect"] = extract_test_result_line((SCRIPT_DIR / primary["record"]).read_text())
    dump(SCRIPT_DIR / "fill.runtime.toml", fill)
    tool = str(PROTOCOL_TOOL)
    subprocess.run([sys.executable, tool, "project-brief", str(SPECIFICATION_PATH),
                    "--allowed-writes", str(SCRIPT_DIR / "writes.toml"),
                    "--out", str(SCRIPT_DIR / "brief.yaml"), "--stats"], check=True)
    subprocess.run([sys.executable, tool, "assemble-package", str(SCRIPT_DIR / "brief.yaml"),
                    str(SCRIPT_DIR), "--spec", str(SPECIFICATION_PATH),
                    "--fill", str(SCRIPT_DIR / "fill.runtime.toml"), "--out", str(PACKAGE_OUT)], check=True)
    # B20 is an existing optional wire field not yet emitted by the generic assembler.
    # Enrich only these mechanical identities; every claim/result/hash came from assembly.
    package = tomllib.loads(PACKAGE_OUT.read_text())
    for claim in package["claim"]:
        for evidence in claim.get("evidence", []):
            if evidence.get("control"):
                continue
            evidence["toolchain"] = identity if evidence["kind"] == "kani-harness" else [entry for entry in identity if entry["name"] in ("rustc", "cargo")]
            evidence["build_inputs"] = []
            for name in ("Cargo.lock", "rust-toolchain.toml"):
                source = CRATE_DIR / name
                target = SCRIPT_DIR / name
                if target.is_symlink():
                    target.unlink()
                target.write_bytes(source.read_bytes())
                evidence["build_inputs"].append({"path": name,
                    "digest": m11.hashdomains.digest("artifact:", source.read_bytes())})
    dump(PACKAGE_OUT, package, "# GENERATED by gen_package.py via assemble-package; do not hand-edit.\n")
    subprocess.run([sys.executable, str(FORMAT_TOOL),
                    "--strict", "--strict-weight", str(PACKAGE_OUT)], check=True)
    subprocess.run([sys.executable, tool, "check-package", str(PACKAGE_OUT),
                    "--spec", str(SPECIFICATION_PATH)], check=True)
    return 0


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
    if dirty:
        raise RuntimeError("crate has uncommitted changes; preserve the historical package until a clean subject is available")
    today = datetime.date.today().isoformat()

    # Capture identity in the crate's pinned build context, never the caller's cwd.
    probe_commands = ["rustc --version", "cargo --version", "cargo clippy --version",
                      "rustc -vV", "cargo --version --verbose", "cargo kani --version"]
    probes = {}
    for command in probe_commands:
        proc = subprocess.run(command.split(), cwd=CRATE_DIR, capture_output=True, text=True, check=True)
        probes[command] = proc.stdout.strip()
    rustc_tool = probes["rustc --version"] + " + " + probes["cargo --version"]
    clippy_version_raw = probes["cargo clippy --version"]
    identity = capture_identity(probes)

    kani_available = True
    kani_version_line = ""
    try:
        kv = subprocess.run(["cargo", "kani", "--version"], cwd=CRATE_DIR, capture_output=True, text=True, timeout=30)
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
            # An incomplete run has no completed report row and is never assembled.
            (EVIDENCE_DIR / "kani-validate-never-panics.txt").write_text(normalize_transcript(
                partial + f"\n\n[gen_package] TIMED OUT after {args.kani_timeout}s\n", repo_root))
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

    return assemble_captured(commit, today, probes, identity)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
