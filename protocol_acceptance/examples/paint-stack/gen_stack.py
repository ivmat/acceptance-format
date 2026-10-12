#!/usr/bin/env python3
"""Generate all intrinsic packages, edge triples and ordered consumer decisions.

Run from a clean committed tree. --dry-run /tmp/NEW-DIR copies the current generator
sources but restores committed Rust inputs from HEAD, without creating a commit.
All real tool runs and generated documents then stay in that temporary tree.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import os
from pathlib import Path
import shutil
import subprocess
import sys

from stack_support import (ROOT, REPO, CRATES, SPEC_IDS, PRODUCERS, ISSUERS,
                           STORE, PROFILE, load, paths, save)
sys.path.insert(0, str(REPO / "protocol_acceptance/tools"))
import acceptance_protocol as AP
import chain


def cleanup_targets():
    for parent, directories, _ in os.walk(ROOT):
        if "target" in directories:
            shutil.rmtree(Path(parent) / "target")
            directories.remove("target")


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def requirement(rid, statement, **extra):
    return dict(id=rid, statement=statement, mandatory=True, waivable=False,
                domain="correctness", clause_source="consumer-statement", **extra)


def chain_requirement(rid, relations, completeness="verified", boundary=None):
    rule = dict(relations=relations, depth="all", level="C2", completeness=completeness,
                binds="consumed", acceptors=["ochre-accepted"], allow_conditions=False,
                unaccepted="refuse", max_elements=500)
    if boundary is not None:
        rule["boundary"] = boundary
    return requirement(rid, "All dependencies are accepted or explicitly inside the declared boundary.",
                       kind="chain", chain=rule)


def authority(crate):
    return dict(rule="all-mandatory-satisfied", consumer_verification="re-execute-all",
                authority=ISSUERS[crate], profiles_required=[PROFILE], phase="final",
                stale_after="P30D" if crate == "geom-math" else "P180D",
                assurance_class="baseline/1", authority_store=[dict(id="ochre-accepted", kind="dir",
                issuers=["Ochre Raster / maintainer", "Studio Ochre / tools-lead"])])


def library_spec(crate, intrinsic):
    # Requirement IDs preserve the SPEC.md mapping, including its explicit bounds.
    spec = dict(document=dict(protocol=AP.PROTOCOL_ID, minor=0, kind="specification",
                id=SPEC_IDS[crate], version=1, issued_at=AP.now_utc_iso(), issued_by="consumer", status="issued"),
                parties=dict(consumer={"name": ISSUERS[crate]}, producer={"name": PRODUCERS[crate]}),
                subject=dict(kind="rust-crate", name=crate, profile=PROFILE),
                acceptance=authority(crate), requirement=[])
    for claim in intrinsic["claim"]:
        spec["requirement"].append(requirement(claim["clause"],
            f"SPEC.md {claim['clause']}: {claim['statement']} Evidence is limited to the bounds disclosed by that claim.",
            evidence=dict(min_tier="T3", weighted_required=True, control_required=True,
                          recipe_required=True, freshness="delivered-revision", independence="none",
                          profile={PROFILE: dict(min_grade="test-only", min_band="A1", families=["dynamic"])})))
    if crate == "raster-draw":
        spec["requirement"].append(chain_requirement("runtime", ["runtime"]))
    return spec


def bind_package(crate, package, spec, sp, pp, commit):
    package["subject"].update(commit=commit, path=(ROOT / crate).relative_to(REPO).as_posix(), dirty=False)
    package["specification"] = dict(id=SPEC_IDS[crate], hash=AP.m11.digest_file("specification", sp),
                                    requirements_total=len(spec["requirement"]))
    package["spec"] = dict(path=sp.name, version=SPEC_IDS[crate] + "@v1", axis="Consumer requirements mapped to the crate SPEC.md clauses and declared dependencies")
    package["coverage"] = dict(clauses_total=len(spec["requirement"]), claims_total=len(package["claim"]))
    if len(spec["requirement"]) != len(package["claim"]):
        package["coverage"].update(denominator="slice", slice_note="Claims cover item requirements; chain requirements are checked from dependency inventories.", slice_boundary=", ".join(c["clause"] for c in package["claim"]))
    package["filler"] = [dict(profile=PROFILE, party=PRODUCERS[crate], role="producer")]
    for claim in package["claim"]:
        if crate != "paint-app":
            claim["item"] = "../../" + claim["item"]
            claim["self_verify"]["command"] = "cd ../.. && " + claim["self_verify"]["command"]
            wf = claim["self_verify"].get("watched_fail")
            if wf:
                wf["of_command"] = "cd ../.. && " + wf["of_command"]
        for ev in claim["evidence"]:
            if crate != "paint-app":
                ev["record"] = "../../" + ev["record"]
                for item in ev.get("inputs", []):
                    item["path"] = "../../" + item["path"]
            # Every claim digests the source plus Cargo.toml; keep the binding's
            # exact bare Cargo.lock/toolchain paths beside the edge manifest.
            if ev["result"] == "pass":
                ev["build_inputs"] = []
                for name in ("src/lib.rs", "Cargo.toml", "Cargo.lock", "rust-toolchain.toml"):
                    original = ROOT / crate / name
                    rel = name if name in ("Cargo.lock", "rust-toolchain.toml") else os.path.relpath(original, pp.parent)
                    ev["build_inputs"].append(dict(path=rel, digest=chain.hashdomains.digest("artifact:", original.read_bytes())))
    if crate != "paint-app":
        # The code/rust binding wants bare Cargo.lock/rust-toolchain.toml beside the manifest. They are
        # committed relative symlinks to the workspace files (part of the subject commit), never generated
        # copies: a copy made at generation time is absent from the subject commit and fails --tree.
        for name in ("Cargo.lock", "rust-toolchain.toml"):
            link = pp.parent / name
            if not (link.is_symlink() and link.resolve() == (ROOT / name).resolve()):
                raise SystemExit(f"{link}: expected a committed symlink to ../../../{name} (create and commit it before generating)")
    return package


def inventory(crate, pp, commit):
    children = {"raster-draw": ["geom-math"], "paint-app": ["raster-draw", "geom-math"]}[crate]
    inputs = []
    for name, role in [("Cargo.lock", "lockfile"), ("Cargo.toml", "workspace-manifest")] + [(c + "/Cargo.toml", "member-manifest") for c in CRATES]:
        p = ROOT / name
        inputs.append(dict(role=role, path=os.path.relpath(p, pp.parent), digest=chain.hashdomains.digest("artifact:", p.read_bytes())))
    inv = dict(id="inv-cargo", source="lockfile", reader=f"cargo-lock/{load(ROOT / 'Cargo.lock')['version']}", covers=["runtime"], entries=len(children), input=inputs)
    direct = load(ROOT / crate / "Cargo.toml").get("dependencies", {})
    deps = [dict(id=c, name=c, inventory="inv-cargo", relation="runtime", role="direct" if c in direct else "transitive",
                 consumed="source", binding="build-time-copy", source=dict(commit=commit, path=(ROOT / c).relative_to(REPO).as_posix()),
                 lock={"entry": c + " " + load(ROOT / c / "Cargo.toml")["package"]["version"]}) for c in children]
    return [inv], deps


def generate(commit):
    os.environ["CARGO_NET_OFFLINE"] = "true"
    os.chdir(ROOT)
    import gen_packages as gp
    if gp.KANI_VERSION_LINE != "cargo-kani 0.67.0":
        raise RuntimeError(f"expected cargo-kani 0.67.0, got {gp.KANI_VERSION_LINE}")
    if STORE.exists() and any(STORE.iterdir()):
        raise RuntimeError("store is not empty; use a clean source tree before generation")
    STORE.mkdir(parents=True, exist_ok=True)
    sp, _, _ = paths("paint-app")
    app_spec = load(sp)
    app_spec["acceptance"] = authority("paint-app")
    app_spec["requirement"] = [r for r in app_spec["requirement"] if r.get("kind") != "chain"] + [
        chain_requirement("runtime", ["runtime"])]
    save(sp, app_spec)
    for crate, builder in zip(CRATES, (gp.build_geom_math, gp.build_raster_draw, gp.build_paint_app)):
        builder(commit, False)
        sp, pp, _ = paths(crate)
        package = load(ROOT / crate / "acceptance.toml") if crate != "paint-app" else load(pp)
        spec = library_spec(crate, package) if crate != "paint-app" else app_spec
        save(sp, spec)
        package = bind_package(crate, deepcopy(package), spec, sp, pp, commit)
        if crate != "geom-math":
            package["dependency_inventory"], package["dependency"] = inventory(crate, pp, commit)
        save(pp, package)
        subprocess.run([sys.executable, str(ROOT / "paint-app/make_decision.py"), "--crate", crate], check=True)
    for command, env in [(["cargo", "test", "--workspace"], None), (["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"], None), (["cargo", "doc", "--no-deps", "--workspace"], dict(os.environ, RUSTDOCFLAGS="-D warnings"))]:
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    sp, pp, dp = paths("paint-app")
    subprocess.run([sys.executable, str(REPO / "protocol_acceptance/tools/acceptance_protocol.py"),
                    "render", str(sp), str(pp), str(dp), "--root", str(REPO),
                    "--store", "ochre-accepted=" + str(STORE), "--tree", commit + "=" + str(REPO)], check=True)
    print(f"[gen_stack] generated three accepted decisions at {commit}", flush=True)


def dry_run(destination):
    destination = destination.resolve()
    if not destination.is_relative_to(Path('/tmp').resolve()):
        raise RuntimeError("dry-run destination must be under /tmp")
    destination.mkdir(parents=True, exist_ok=False)
    # Copy the worktree's public tool closure and example sources, never .git or targets.
    for name in ("format_acceptance", "protocol_acceptance"):
        shutil.copytree(REPO / name, destination / name, symlinks=True,
                        ignore=shutil.ignore_patterns("target", "__pycache__", "legacy_0_3", ".selftest-*"))
    (destination / "gates").mkdir()
    shutil.copyfile(REPO / "gates/check_paint_stack.py", destination / "gates/check_paint_stack.py")
    copied = destination / ROOT.relative_to(REPO)
    commit = git("rev-parse", "HEAD")
    # Pending comment edits are not yet a committed subject. Use actual HEAD inputs
    # for the rehearsal so dirty=false is truthful and no synthetic commit is needed.
    for rel in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml"] + [f"{c}/Cargo.toml" for c in CRATES] + [p.relative_to(ROOT).as_posix() for c in CRATES for p in (ROOT / c / "src").rglob("*") if p.is_file()]:
        data = subprocess.check_output(["git", "-C", str(REPO), "show", f"{commit}:{ROOT.relative_to(REPO) / rel}"])
        (copied / rel).write_bytes(data)
    print(f"[gen_stack] dry run: committed Rust inputs at {commit}; current generator sources; output {destination}", flush=True)
    subprocess.run([sys.executable, str(copied / "gen_stack.py"), "--rehearsal-commit", commit], check=True)
    print(f"[gen_stack] dry run PASS: {destination}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", type=Path)
    parser.add_argument("--rehearsal-commit", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.dry_run:
        dry_run(args.dry_run)
    else:
        if args.rehearsal_commit:
            if not REPO.is_relative_to(Path('/tmp').resolve()) or (REPO / '.git').exists():
                raise RuntimeError("rehearsal is only allowed in a temporary non-checkout tree")
            commit = args.rehearsal_commit
        else:
            if git("status", "--porcelain"):
                raise RuntimeError("generation requires a clean, committed source tree")
            commit = git("rev-parse", "HEAD")
        generate(commit)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        cleanup_targets()
