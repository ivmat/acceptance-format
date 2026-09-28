"""Rust binding: parent conjunction, C8 cover-only and token/family tier ceilings."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_core
from check_core import Finding
from bindings import code
# Reuse the existing declaration as the sole optional-field type registry.
from profiles.verification import OPTIONAL_RECORD_FIELDS

DECLARATION = code.declaration("code/rust")
ADMITS = frozenset(DECLARATION["admits"])
IDENTITY = frozenset(DECLARATION["identity"])
assert ADMITS <= code.ADMITS, "B17: admits(code/rust) must narrow admits(code)"
assert IDENTITY <= code.IDENTITY, "B17: identity(code/rust) must narrow identity(code)"
# B20: the concrete required build-input paths are this binding's own declaration (admits/B14/
# B17 style — same machine-readable block, read generically by core's shape rule); the guard
# below is opt-in-complete: it fires only once a weighted claim already declares SOME
# build_inputs entry (B20's nonempty-guard shape, mirroring B9/C8).
REQUIRED_BUILD_INPUTS = tuple(x for x in DECLARATION.get("required_build_inputs", []) if isinstance(x, str))
TIERS = {"kani-harness": "T2", "lean-theorem": "T1", "flux-refinement": "T2",
         "unit-test": "T3", "property-test": "T3", "fuzz": "T3", "miri": "T3",
         "lint": "T4", "semver-check": "T4", "dep-audit": "T4",
         "human-review": "T5", "llm-review": "T5"}


def _tallies(value, path="manifest"):
    if isinstance(value, dict):
        for key, child in value.items():
            location = f"{path}.{key}"
            if key == "cover_tally":
                yield location
            yield from _tallies(child, location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _tallies(child, f"{path}[{index}]")


def check(doc, ctx):
    # The 0.2 lowering pass (binding-chain diagnostic de-duplication): `check_core.check_profiles`
    # already evaluates every prefix module in the chain (`code`, then `code/rust`)
    # independently, so re-running `code.check` here duplicated its findings
    # (e.g. "B14: code does not admit subject kind" appearing twice). This
    # module now returns only its OWN additive delta over `code`.
    findings = []
    for location in _tallies(doc):
        findings.append(Finding("error", "C8: manifest-side cover_tally is not accepted (open question C4: record-level): " + location))
    if isinstance(doc.get("subject"), dict) and doc["subject"].get("kind") not in ADMITS:
        findings.append(Finding("error", "B14: code/rust does not admit subject kind"))
    # By the time a binding's own check(doc, ctx) runs, dispatch has already required and
    # validated [format].profile (B12, 0.3.0: REQUIRED, no compatibility default) — this read is
    # defensive only, never a fallback default.
    profile = doc.get("format", {}).get("profile", "")
    parts = profile.split("/") if isinstance(profile, str) else []
    meaning = (check_core._module(check_core.MODULE_ROOT / "profiles" / (parts[1] + ".py"), "meaning")
               if len(parts) >= 2 and parts[1].replace("-", "").isalnum() else None)
    families = getattr(meaning, "FAMILIES", {})
    conf = doc.get("conformance", {})
    legacy = conf.get("cover_only", []) if isinstance(conf, dict) else []
    if isinstance(conf, dict) and "cover_only" in conf:
        version = doc.get("format", {}).get("profile_version", doc.get("format", {}).get("version", "0.1.0-draft"))
        findings.append(Finding("warning" if version == "0.1.0-draft" else "error",
                                "B9: [conformance].cover_only is deprecated read-only metadata at 0.1; removed at 0.2"))
        if not isinstance(legacy, list) or not all(isinstance(r, str) and r.strip() for r in legacy):
            findings.append(Finding("error", "B9: legacy cover_only must be a list of nonempty refs"))
            legacy = []
    for claim in doc.get("claim", []):
        if not isinstance(claim, dict):
            continue
        cid = claim.get("id")
        records = claim.get("evidence", [])
        if not isinstance(records, list):
            continue
        records = [e for e in records if isinstance(e, dict)]
        kani = [e for e in records if e.get("kind") == "kani-harness"]
        if claim.get("weight") == "weighted" and kani and all(e.get("cover_only") is True or e.get("ref") in legacy for e in kani):
            findings.append(Finding("error", "C8: weighted cover-only kani evidence forbidden", cid))
        if REQUIRED_BUILD_INPUTS and claim.get("weight") == "weighted":
            declared_build_inputs = []
            for record in records:
                bi = record.get("build_inputs")
                if isinstance(bi, list):
                    declared_build_inputs.extend(e for e in bi if isinstance(e, dict))
            if declared_build_inputs:
                # Review found that a basename match let
                # `unrelated-a/Cargo.lock` + `unrelated-b/rust-toolchain.toml` — two files with the
                # right NAMES but no relationship to each other or to the build — satisfy this
                # guard; correct digests establish those files' bytes, not their relationship to
                # the build. Reverted to EXACT path semantics, anchored to the manifest's own
                # directory (B6; no separate build-context-root locator exists on `[subject]` or
                # in this binding's own declaration to anchor a laxer match against — see
                # `code/rust.md`'s `required_build_inputs` comment). A binding user whose crate
                # sits below its manifest (this binding's own real-usage example,
                # `protocol_acceptance/examples/rust-delivery/`) must declare the exact
                # manifest-relative path, e.g. via a same-directory symlink to the real file —
                # never rely on the basename alone.
                present = {entry.get("path") for entry in declared_build_inputs}
                missing = [p for p in REQUIRED_BUILD_INPUTS if p not in present]
                if missing:
                    findings.append(Finding(
                        "error",
                        f"B20: weighted claim declares build_inputs but is missing required path(s): {missing}",
                        cid,
                    ))
        for record in records:
            for key, expected_type in OPTIONAL_RECORD_FIELDS.items():
                if key not in record:
                    continue
                value = record[key]
                # Exact types exclude bool from the integer counters.
                if type(value) is not expected_type:
                    findings.append(Finding("error", f"B9: {key} must be {expected_type.__name__}", cid))
                elif expected_type is int and value < 0:
                    findings.append(Finding("error", f"B9: {key} must be nonnegative", cid))
            if ("cover_satisfied" in record) != ("cover_total" in record):
                findings.append(Finding("error", "B9: cover_satisfied / cover_total must be a pair", cid))
            if (all(type(record.get(k)) is OPTIONAL_RECORD_FIELDS[k] for k in ("cover_satisfied", "cover_total"))
                    and record["cover_satisfied"] > record["cover_total"]):
                findings.append(Finding("error", "B9: cover_satisfied exceeds cover_total", cid))
            if "epistemic_tier" not in record:
                continue
            tier = check_core._rank(record["epistemic_tier"])
            for label, ceiling in (("family", families.get(record.get("family"))), ("kind", TIERS.get(record.get("kind")))):
                if ceiling is not None and (tier is None or tier < check_core._rank(ceiling)):
                    findings.append(Finding("error", f"A2: epistemic_tier exceeds {label} ceiling {ceiling}", cid))
    return findings


if __name__ == "__main__":
    from fixtures.binding_cases import selftest
    sys.exit(selftest("code/rust") if sys.argv[1:] == ["--selftest"] else 2)
