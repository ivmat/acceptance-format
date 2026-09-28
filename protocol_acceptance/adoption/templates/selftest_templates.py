#!/usr/bin/env python3
"""selftest_templates.py — proves the two adoption templates in this directory actually work:

1. `kani-crate.contract.toml` passes `acceptance_protocol.py check-contract` AS SHIPPED (a
   requester contract skeleton needs no fake data to be well-formed — every `<FILL: ...>` marker
   sits in a free-text field).
2. `kani-crate.acceptance.toml` (a producer PACKAGE skeleton) does NOT pass as shipped — its
   `<FILL: ...>` markers sit in fields the format actually type-checks (a commit, a hash, a record
   pointer), so `check_acceptance.py --strict` refuses it with clear, field-named errors. This
   selftest asserts that refusal happens (the "state precisely why a skeleton cannot" half).
3. A FIXTURE FILLER substitutes real values for every marker (a real 40-hex commit from a throwaway
   git repo, a real evidence record file, its real `record:` hash via `hashdomains.py`, a real
   `artifact:` toolchain digest, and a `contract:` hash recomputed over a same-way-filled copy of
   the contract) and re-validates: the FILLED package passes
   `check_acceptance.py --strict --strict-weight`.
4. The filled contract/package pair passes the adoption guide's real `check-package` and
   `coverage` CLIs, with R1 satisfied and R2 deviation-declared.

Run directly: `python3 selftest_templates.py`. Stdlib only. Exit 0/1.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
CHECK_ACCEPTANCE = REPO_ROOT / "format_acceptance/tools/check_acceptance.py"
ACCEPTANCE_PROTOCOL = REPO_ROOT / "protocol_acceptance/tools/acceptance_protocol.py"
HASHDOMAINS_DIR = REPO_ROOT / "format_acceptance/tools"

sys.path.insert(0, str(HASHDOMAINS_DIR))
import hashdomains  # noqa: E402


FILL_RE = re.compile(r"<FILL:[^>]*>")


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argv], cwd=str(cwd), capture_output=True, text=True,
                           timeout=120)


def check_contract_template_passes() -> list[str]:
    result = run([str(ACCEPTANCE_PROTOCOL), "check-contract",
                  str(HERE / "kani-crate.contract.toml")], cwd=HERE)
    if result.returncode != 0:
        return [f"kani-crate.contract.toml FAILED check-contract as shipped "
                f"(exit {result.returncode}, expected exactly 0):\n{result.stdout}{result.stderr}"]
    if "Traceback" in result.stderr:
        return [f"check-contract raised an unhandled exception:\n{result.stderr}"]
    return []


def check_package_skeleton_fails_clearly() -> list[str]:
    result = run([str(CHECK_ACCEPTANCE), "--strict", "--strict-weight",
                  str(HERE / "kani-crate.acceptance.toml")], cwd=HERE)
    out = result.stdout + result.stderr
    # Exact expected exit (FAIL = 1, not merely "nonzero" — a usage error or an unhandled
    # exception would also be nonzero and must NOT be mistaken for the intended refusal).
    if result.returncode != 1:
        return [f"kani-crate.acceptance.toml exited {result.returncode} (expected exactly 1, "
                f"FAIL) as shipped:\n{out}"]
    if "Traceback" in result.stderr:
        return [f"kani-crate.acceptance.toml raised an unhandled exception, not a clean "
                f"validator refusal:\n{result.stderr}"]
    # Every remaining <FILL: ...> marker in the raw file should be named by at least one error
    # line, so a producer who ran the validator on the untouched skeleton gets pointed at each gap.
    errors = []
    if "commit" not in out:
        errors.append("no error mentions the placeholder [subject].commit")
    if "record_hash" not in out and "record:" not in out:
        errors.append("no error mentions the placeholder record_hash")
    return errors


def _isolated_git_env() -> dict[str, str]:
    """Scrub every inherited `GIT_*` override (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, ...):
    without this, `cwd=repo` does NOT guarantee `git init`/`config`/`add`/`commit` actually operate
    on `repo` — an inherited `GIT_DIR` silently redirects them to a DIFFERENT repository."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(repo: Path, *args: str) -> str:
    env = _isolated_git_env()
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        capture_output=True, text=True, env=env, check=True,
    )
    return result.stdout.strip()


def _sha256_git_commit(repo: Path) -> str:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "probe")
    return _git(repo, "rev-parse", "HEAD")


def fill(text: str, values: dict[str, str]) -> str:
    """Replace every `<FILL: ...>` marker in document order with the next value in `values`'
    ordered list — the filler is positional and dumb ON PURPOSE, matching a real producer's own
    generator script (never hand-edited, see the templates' own header comment)."""
    it = iter(values)
    def _sub(_match):
        return next(it)
    return FILL_RE.sub(_sub, text)


def build_filled_package(workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "src").mkdir(exist_ok=True)
    (workdir / "src" / "lib.rs").write_text("// probe crate\n", encoding="utf-8")
    commit = _sha256_git_commit(workdir)

    evidence_dir = workdir / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    record_path = evidence_dir / "kani-never-panics.txt"
    record_bytes = b"VERIFICATION:- SUCCESSFUL\nharness never_panics finished in 1.2s\n"
    record_path.write_bytes(record_bytes)
    record_hash = hashdomains.digest("record:", record_bytes)
    # Two DISTINCT toolchain artifacts (guide §6: one entry is not enough) — neither
    # needs a real installed Kani, only a stable byte string to digest, since toolchain digests are
    # never recomputed against a file on disk (check_code_identity_shape is shape-only; only
    # build_inputs digests are recomputed, by check_build_input_hashes).
    bundle_digest = hashdomains.digest("artifact:", b"probe-kani-bundle-manifest-bytes")
    launcher_digest = hashdomains.digest("artifact:", b"probe-cargo-kani-launcher-bytes")
    # build_inputs digests, unlike toolchain digests, ARE recomputed over the pointed file's own
    # bytes (B20 / check_build_input_hashes), resolved relative to the manifest's own directory —
    # so these two files must actually exist, at workdir root, beside acceptance.toml.
    cargo_lock_bytes = b'# probe Cargo.lock\nversion = 3\n'
    rust_toolchain_bytes = b'[toolchain]\nchannel = "stable"\n'
    (workdir / "Cargo.lock").write_bytes(cargo_lock_bytes)
    (workdir / "rust-toolchain.toml").write_bytes(rust_toolchain_bytes)
    cargo_lock_digest = hashdomains.digest("artifact:", cargo_lock_bytes)
    rust_toolchain_digest = hashdomains.digest("artifact:", rust_toolchain_bytes)

    contract_template = (HERE / "kani-crate.contract.toml").read_text(encoding="utf-8")
    contract_values = [
        "probe-crate", "2026-01-01T00:00:00Z", "your-team", "probe-maintainer",
        "probe-crate", "the crate this template validates against",
        "the parser never panics on any input up to 64 bytes", "your-team / lead",
    ]
    filled_contract = fill(contract_template, contract_values)
    contract_path = workdir / "acceptance-contract.toml"
    contract_path.write_text(filled_contract, encoding="utf-8")
    contract_hash = hashdomains.digest("contract:", filled_contract.encode("utf-8"))

    package_template = (HERE / "kani-crate.acceptance.toml").read_text(encoding="utf-8")
    # ORDER MUST MATCH the template's own `<FILL: ...>` markers top to bottom exactly (28 markers,
    # verified by `grep -no '<FILL:[^>]*>' kani-crate.acceptance.toml` against the shipped file:
    # 25 base markers + 1 extra toolchain digest (bundle+launcher, was one entry) + 2 build_inputs
    # digests (Cargo.lock, rust-toolchain.toml), guide §6).
    package_values = [
        "probe-crate",                              # [subject].name
        commit,                                     # [subject].commit
        "AC-probe-crate-0001",                      # [contract].id
        contract_hash,                              # [contract].hash
        "AC-probe-crate-0001@v1",                   # [spec].version
        "AC-probe-crate-0001",                      # [spec].axis
        "src/lib.rs",                               # K-001 item
        "the parser never panics on any input up to 64 bytes",  # K-001 statement
        "bounded: KANI_BOUND=64 bytes (real capacity: 64 -- fixed-size probe)",  # K-001 bounds
        commit,                                     # K-001 captured_at_commit
        "cargo kani --harness never_panics",        # self_verify.command
        "VERIFICATION:- SUCCESSFUL",                # self_verify.expect
        "src/lib.rs::never_panics",                 # evidence.ref
        "kani@0.67.0 (commit unknown -- cargo kani --version reports no commit)",  # evidence.tool
        "bounded: KANI_BOUND=64 bytes",             # evidence.bounds
        "unwind=65, no loop-bound errors",          # evidence.semantics
        "kani-never-panics.txt",                    # record filename
        record_hash,                                # record_hash
        commit,                                     # evidence.captured_at_commit
        bundle_digest,                               # toolchain[0] kani-bundle digest
        launcher_digest,                             # toolchain[1] cargo-kani-launcher digest
        cargo_lock_digest,                           # build_inputs[0] Cargo.lock digest
        rust_toolchain_digest,                       # build_inputs[1] rust-toolchain.toml digest
        "src/lib.rs",                               # K-002 item
        "the harness bound is 64 bytes; the real input can be up to 64 bytes (fixed-size probe)",  # deviation statement
        "probe fixture -- no real bound gap in this smoke test",  # deviation cause
        "none for this fixed-size probe",           # deviation impact
        "n/a for this fixed-size probe",            # deviation remedy
    ]
    filled_package = fill(package_template, package_values)
    if "<FILL:" in filled_package:
        remaining = FILL_RE.findall(filled_package)
        raise AssertionError(f"filler ran out of values; unfilled markers remain: {remaining}")
    package_path = workdir / "acceptance.toml"
    package_path.write_text(filled_package, encoding="utf-8")
    return package_path


def check_filled_package_passes() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="templates_selftest_") as td:
        package_path = build_filled_package(Path(td))
        result = run([str(CHECK_ACCEPTANCE), "--strict", "--strict-weight", package_path.name],
                     cwd=package_path.parent)
        out = result.stdout + result.stderr
        if result.returncode != 0:
            return [f"filled kani-crate.acceptance.toml FAILED check_acceptance.py --strict "
                    f"(exit {result.returncode}):\n{out}"]
        if "PASS" not in out:
            return [f"filled package did not report PASS:\n{out}"]
        return []


def check_filled_pair_protocol_clis() -> list[str]:
    """Exercise the guide's package-level commands, not merely format-level validation."""
    with tempfile.TemporaryDirectory(prefix="templates_selftest_protocol_pair_") as td:
        package_path = build_filled_package(Path(td))
        contract_path = package_path.with_name("acceptance-contract.toml")
        errors = []
        result = run([str(ACCEPTANCE_PROTOCOL), "check-package", package_path.name,
                      "--contract", contract_path.name], cwd=package_path.parent)
        out = result.stdout + result.stderr
        if result.returncode != 0:
            errors.append("filled contract/package pair FAILED check-package (expected exit 0):\n"
                          + out)
        elif "R1: satisfied" not in out or "R2: deviation-declared" not in out:
            errors.append("check-package passed but did not report R1 satisfied and R2 "
                          f"deviation-declared:\n{out}")

        result = run([str(ACCEPTANCE_PROTOCOL), "coverage", package_path.name,
                      "--contract", contract_path.name], cwd=package_path.parent)
        out = result.stdout + result.stderr
        if result.returncode != 0:
            errors.append("filled contract/package pair FAILED coverage (expected exit 0):\n" + out)
        elif "R1: satisfied" not in out or "R2: deviation-declared" not in out:
            errors.append("coverage passed but did not report R1 satisfied and R2 "
                          f"deviation-declared:\n{out}")
        return errors


# K-001 is UNWEIGHTED by design in the shipped template (§4 of the guide: a band-A1 panic-freedom
# claim needs no band-lift CONTROL, but adding `weight = "weighted"` is a SEPARATE obligation — a
# weighted claim needs its own watched-fail WITNESS regardless of band). This control proves both
# halves mechanically: weighting the filled claim with no witness FAILS, and adding a `[claim.self_verify.watched_fail]` table makes the SAME weighted claim
# PASS — the concrete "valid weighted example" the guide's §4 shows.
_WATCHED_FAIL_SNIPPET = (
    '\n\n    [claim.self_verify.watched_fail]\n'
    '    of_command = "cargo kani --harness never_panics"\n'
    '    perturbed  = "removed the bounds check before the panic-free operation, so an '
    'out-of-range index is reachable"\n'
    '    observed   = "VERIFICATION:- FAILED\\nindex out of bounds panic reachable in '
    'never_panics"\n'
    '    date       = "2026-01-01"\n'
)


def _weighted_variant(filled_package: str, *, with_witness: bool) -> str:
    text = filled_package.replace(
        'status        = "evidenced"\ngrade         = "probe"',
        'status        = "evidenced"\nweight        = "weighted"\ngrade         = "probe"',
        1,
    )
    if text == filled_package:
        raise AssertionError("weighted-claim fixture: K-001's status/grade lines were not found "
                              "(the template's own shape changed; update this fixture)")
    if with_witness:
        marker = ('  [claim.self_verify]\n'
                   '  command = "cargo kani --harness never_panics"\n'
                   '  expect  = "VERIFICATION:- SUCCESSFUL"\n')
        if marker not in text:
            raise AssertionError("weighted-claim fixture: K-001's self_verify block was not "
                                  "found (the template's own shape changed; update this fixture)")
        text = text.replace(marker, marker + _WATCHED_FAIL_SNIPPET, 1)
    return text


def check_weighted_claim_needs_witness() -> list[str]:
    errors = []
    with tempfile.TemporaryDirectory(prefix="templates_selftest_weighted_") as td:
        package_path = build_filled_package(Path(td))
        filled = package_path.read_text(encoding="utf-8")

        # Half 1: weighting K-001 with NO witness must FAIL — a band-lift control is not the same
        # obligation as a weight witness.
        no_witness = _weighted_variant(filled, with_witness=False)
        package_path.write_text(no_witness, encoding="utf-8")
        result = run([str(CHECK_ACCEPTANCE), "--strict", "--strict-weight", package_path.name],
                     cwd=package_path.parent)
        if result.returncode == 0:
            errors.append("weighting K-001 with no watched-fail witness PASSED — expected a "
                           "WEIGHT REFUSED error (a band-A1 freedom claim needs no band-lift "
                           "control, but a WEIGHTED claim still needs its own witness)")
        elif "WEIGHT REFUSED" not in (result.stdout + result.stderr):
            errors.append(f"weighting K-001 with no witness failed for an unexpected reason "
                           f"(expected 'WEIGHT REFUSED'):\n{result.stdout}{result.stderr}")

        # Half 2: the SAME weighted claim, now with a watched-fail witness, must PASS.
        with_witness = _weighted_variant(filled, with_witness=True)
        package_path.write_text(with_witness, encoding="utf-8")
        result = run([str(CHECK_ACCEPTANCE), "--strict", "--strict-weight", package_path.name],
                     cwd=package_path.parent)
        if result.returncode != 0:
            errors.append(f"a weighted K-001 WITH a watched-fail witness FAILED (expected PASS):"
                           f"\n{result.stdout}{result.stderr}")
        elif "weighted: 1" not in (result.stdout + result.stderr):
            errors.append(f"a weighted K-001 with a witness passed but did not report as "
                           f"weighted:\n{result.stdout}{result.stderr}")
    return errors


def main() -> int:
    errors = []
    errors += check_contract_template_passes()
    errors += check_package_skeleton_fails_clearly()
    errors += check_filled_package_passes()
    errors += check_filled_pair_protocol_clis()
    errors += check_weighted_claim_needs_witness()
    if errors:
        print("SELFTEST FAIL: selftest_templates")
        for e in errors:
            print(f"  {e}")
        return 1
    print("SELFTEST PASS: selftest_templates (5 controls: contract-as-shipped, "
          "package-skeleton-refuses-clearly, package-filled-passes, "
          "filled-pair-check-package-and-coverage, weighted-claim-needs-its-own-witness)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
