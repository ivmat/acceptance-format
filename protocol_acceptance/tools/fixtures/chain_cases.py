"""Executable chain fixtures. Each store is materialized from source trees in a temp dir."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import shutil
import subprocess
import sys
import tomllib
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import acceptance_protocol as AP
import chain as C
from fixtures._support import Cases

COMMIT = "a" * 40
T = "2026-10-10T12:00:00Z"
PROFILE = "acceptance/verification/code/rust"
SOURCE = Path(__file__).with_name("chain_tree")


def dumps(doc):
    def scalar(v):
        if isinstance(v, dict):
            return "{ " + ", ".join(json.dumps(k) + " = " + scalar(x) for k, x in v.items()) + " }"
        if isinstance(v, list):
            return "[" + ", ".join(scalar(x) for x in v) + "]"
        return json.dumps(v)
    return "\n".join(json.dumps(k) + " = " + scalar(v) for k, v in doc.items()) + "\n"


def save(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(doc))


def rule(level="C2", **changes):
    result = dict(relations=["runtime"], depth="all", level=level, completeness="verified",
                  binds="consumed", allow_conditions=False, unaccepted="refuse", max_elements=500)
    if level == "C2":
        result["acceptors"] = ["trusted"]
    result.update(changes)
    return result


class Estate:
    def __init__(self, root, commit=COMMIT):
        root = root.resolve()
        self.root, self.commit = root, commit
        shutil.copytree(SOURCE, root, dirs_exist_ok=True)
        self.store = root / "store"
        self.store.mkdir(exist_ok=True)
        self.specs, self.packages, self.decisions, self.paths = {}, {}, {}, {}
        self.old_root = AP._ROOT_OVERRIDE
        AP._ROOT_OVERRIDE = root
        for name, children in (("geom-math", []), ("raster-draw", ["geom-math"]), ("paint-app", ["geom-math", "raster-draw"])):
            self.add(name, children)

    def close(self):
        AP._ROOT_OVERRIDE = self.old_root

    def context(self, effect=None, stores=True):
        return C.Invocation(AP, {"trusted": self.store} if stores else {}, {self.commit: self.root}, self.root, effect)

    def pin_inputs(self, package):
        pp = self.paths[package["subject"]["name"]][1]
        inputs = []
        for rel, role in [("Cargo.lock", "lockfile"), ("Cargo.toml", "workspace-manifest")] + [(n + "/Cargo.toml", "member-manifest") for n in ("geom-math", "raster-draw", "paint-app")]:
            p = self.root / rel
            inputs.append(dict(role=role, path=os.path.relpath(p, pp.parent), digest=C.hashdomains.digest("artifact:", p.read_bytes())))
        package["dependency_inventory"][0]["input"] = inputs

    def add(self, name, children, suffix="", issued=T):
        key = name + suffix
        sp = self.root / name / "acceptance" / ("S-" + key) / "acceptance-specification.toml"
        pp = sp.with_name("acceptance.toml")
        self.paths[key] = sp, pp
        spec = {
            "document": dict(protocol=AP.PROTOCOL_ID, minor=0, kind="specification", id="S-" + key, version=1, issued_at=T, issued_by="consumer", status="issued"),
            "parties": dict(consumer={"name": "consumer"}, producer={"name": "supplier"}),
            "subject": dict(kind="rust-crate", name=name, profile=PROFILE),
            "acceptance": dict(rule="all-mandatory-satisfied", consumer_verification="package-trusted", authority="maintainer" if name == "geom-math" and not suffix else "lead", profiles_required=[PROFILE], authority_store=[dict(id="trusted", kind="dir", issuers=["lead", "maintainer"])]),
            "requirement": [dict(id="own", statement="Own source reviewed", mandatory=True, waivable=False, domain="correctness", clause_source="consumer-statement", evidence=dict(min_tier="T5", weighted_required=False, control_required=False, recipe_required=False, freshness="any", independence="none")),
                            dict(id="runtime", kind="chain", statement="Every dependency accepted", mandatory=True, waivable=False, domain="packaging", clause_source="consumer-statement", chain=rule())],
        }
        package = {
            "format": dict(id="acceptance/0", protocol=AP.PROTOCOL_ID, profile=PROFILE),
            "subject": dict(name=name, kind="rust-crate", commit=self.commit, path=name, dirty=False),
            "specification": dict(id="S-" + key, requirements_total=2),
            "spec": dict(path="acceptance-specification.toml", version="1", axis="Own source and dependencies"),
            "coverage": dict(clauses_total=2, claims_total=1, denominator="slice", slice_note="One item and a chain", slice_boundary="own"),
            "claim": [dict(id="own-claim", clause="own", item="../../src/lib.rs", statement="Source reviewed", status="evidenced", band="A0", weight="unweighted", grade="inspection-argued", clause_source="spec-document", evidence=[dict(kind="human-review", family="judgment", reviewer="reviewer", epistemic_tier="T5", ref="review", result="pass", tool="reviewer", record="review.txt", build_inputs=[dict(path="../../src/lib.rs", digest=C.hashdomains.digest("artifact:", (self.root / name / "src/lib.rs").read_bytes()))])])],
            "dependency_inventory": [dict(id="cargo", source="lockfile", reader="cargo-lock/4", covers=["runtime"], entries=len(children))],
            "dependency": [dict(id=child, name=child, inventory="cargo", relation="runtime", role="direct" if child == {"paint-app": "raster-draw", "raster-draw": "geom-math"}.get(name) else "transitive", consumed="source", binding="build-time-copy", source=dict(commit=self.commit, path=child), lock={"entry": child + " 0.1.0"}) for child in children],
        }
        self.specs[key], self.packages[key] = spec, package
        # Additional edge acceptance uses the same crate's reader inputs.
        self.pin_inputs(package)
        self.write(key)
        pp.with_name("review.txt").write_text("reviewed fixture source\n")
        self.decide(key, issued)

    def write(self, key):
        sp, pp = self.paths[key]
        save(sp, self.specs[key])
        self.packages[key]["specification"]["hash"] = AP.m11.digest_file("specification", sp)
        save(pp, self.packages[key])

    def decide(self, key, issued=T):
        spec, package = self.specs[key], self.packages[key]
        sp, pp = self.paths[key]
        with patch.object(AP, "now_utc_iso", return_value=issued):
            decision = tomllib.loads(AP.build_decision_skeleton(spec, package, pp, sp, spec["acceptance"]["authority"], None, self.context()))
        decision["verification"].pop("run", None)
        decision["document"]["id"] = "D-" + key
        decision["binds"]["specification"]["path"] = sp.relative_to(self.root).as_posix()
        decision["binds"]["package"]["path"] = pp.relative_to(self.root).as_posix()
        decision["validity"]["stale_after"] = "2027-12-31"
        self.decisions[key] = decision
        save(self.store / ("D-" + key + ".toml"), decision)
        return decision

    def check(self, key="paint-app", effect=None):
        sp, pp = self.paths[key]
        return AP.check_decision(self.decisions[key], self.specs[key], self.packages[key], sp, pp, chain_context=self.context(effect))

    def evaluate(self, key="paint-app", **kwargs):
        return self.context().evaluate(self.specs[key], self.packages[key], self.paths[key][1], T, **kwargs)

# Every RED has a concrete assertion and a guard disabled/restored by protocol_mutations.
REASONS = {}
GUARDS = {}
TESTS = {}


def case(name, reason, guard=None, filename="chain.py"):
    def register(fn):
        TESTS[name] = fn
        REASONS[name] = reason
        if guard:
            GUARDS[name] = (filename, guard)
        return fn
    return register


def detail(result):
    if isinstance(result, tuple):
        cov, _, rows, errors, unknowns = result
        return "\n".join(errors + unknowns + [str(r["reasons"]) for r in cov.values()] + [r["reason"] for r in rows])
    return "\n".join(result.errors + result.unknowns + result.warnings)


def edit_child(e, name="geom-math", **fields):
    e.decisions[name]["document"].update(fields)
    save(e.store / ("D-" + name + ".toml"), e.decisions[name])


def cargo_edit(e, rel, old, new):
    p = e.root / rel
    p.write_text(p.read_text().replace(old, new))
    for pkg in e.packages.values():
        e.pin_inputs(pkg)


def snapshot(e, **changes):
    e.decisions["paint-app"]["chain_evaluation"]["budget"].update(changes)
    return e.check()


def joined(e):
    return detail(e.evaluate())


@case("G1", "stack accepted")
def g1(e):
    pkg, spec = e.packages["paint-app"], e.specs["paint-app"]
    rep = e.check()
    sp, pp = e.paths["paint-app"]
    rendered = AP.render_markdown(spec, pkg, e.decisions["paint-app"], sp, pp, None, e.context())
    expected = ("stack accepted over cargo for runtime at " + T,
                "not covered (trusted as the base, not checked): build-tool, language, platform, verification-tool",
                "accepted by lead, maintainer under their own specifications", "declared binding", "combines no assurance levels")
    return rep.ok() and all(x in rendered for x in expected), detail(rep) + rendered


@case("G9", "uncovered relations always qualified")
def g9(e):
    sp, pp = e.paths["paint-app"]
    spec, pkg = e.specs["paint-app"], e.packages["paint-app"]
    expected = "not covered (trusted as the base, not checked): build-tool, language, platform, verification-tool"
    views = [AP.render_markdown(spec, pkg, decision, sp, pp, None, e.context())
             for decision in (None, e.decisions["paint-app"])]
    # Direct depth covers no relations for the label, including runtime itself.
    spec["requirement"][1]["chain"]["depth"] = "direct"
    direct = AP.render_markdown(spec, pkg, None, sp, pp, None, e.context())
    return (all(expected in view for view in views)
            and "not covered (trusted as the base, not checked): build-tool, language, platform, runtime, verification-tool" in direct
            and "stack accepted" not in direct), "\n".join(views) + direct


@case("R77", "not covered (trusted as the base, not checked):", 'if tokens - covered:')
def r77(e):
    return g9(e)


@case("G2", "explicit empty closure")
def g2(e):
    rep = e.check("geom-math")
    return rep.ok() and not e.decisions["geom-math"]["chain_element"] if "chain_element" in e.decisions["geom-math"] else rep.ok(), detail(rep)


@case("G3", "non-chain output unchanged")
def g3(e):
    spec, pkg = deepcopy(e.specs["geom-math"]), deepcopy(e.packages["geom-math"])
    spec["requirement"] = spec["requirement"][:1]
    sp, pp = e.paths["geom-math"]
    a = AP.render_markdown(spec, pkg, None, sp, pp, None)
    with patch.object(C, "render", return_value=""):
        b = AP.render_markdown(spec, pkg, None, sp, pp, None)
    return a == b and "| Relation |" not in a, a


def make_gap(e):
    e.specs["paint-app"]["requirement"][1]["chain"]["unaccepted"] = "gap"
    for p in e.store.glob("*.toml"):
        p.unlink()
    e.write("paint-app")
    e.decide("paint-app")


@case("G4", "determinate gap; no stack accepted; NOTE")
def g4(e):
    make_gap(e)
    rep = e.check()
    spec = e.specs["paint-app"]
    sp, pp = e.paths["paint-app"]
    rendered = AP.render_markdown(spec, e.packages["paint-app"], e.decisions["paint-app"], sp, pp, None, e.context())
    note = AP.check_specification(spec).warnings
    return rep.ok() and "stack accepted" not in rendered and any("NOTE" in s and "gap mode" in s for s in note), detail(rep) + rendered


@case("G5", "store view differs from recorded listing")
def g5(e):
    doc = deepcopy(e.decisions["geom-math"])
    doc["document"]["id"] = "unrelated"
    doc["binds"]["subject"]["commit"] = "c" * 40
    save(e.store / "unrelated.toml", doc)
    rep = e.check()
    return rep.ok() and REASONS["G5"] in detail(rep), detail(rep)


@case("G6", "conservative gap")
def g6(e):
    originals = {p.name: p.read_bytes() for p in e.store.glob("*.toml")}
    make_gap(e)
    for name, raw in originals.items():
        if "paint-app" not in name:
            (e.store / name).write_bytes(raw)
    rep = e.check()
    return rep.ok(), detail(rep)


@case("G7", "latest then lowest hash")
def g7(e):
    original = deepcopy(e.decisions["geom-math"])
    original["document"].update(id="latest", issued_at="2026-10-10T11:59:59Z")
    # Use a distinct specification id so this candidate cannot supersede the original.
    e.add("geom-math", [], suffix="-second", issued="2026-10-10T12:00:01Z")
    at = "2026-10-10T12:00:02Z"
    d = e.decide("paint-app", at)
    pin = next(r["decision"] for r in d["chain_element"] if r["dependency"] == "geom-math")
    later_ok = pin["id"] == "D-geom-math-second"
    twin = deepcopy(e.decisions["geom-math-second"])
    twin["document"]["id"] = "twin"
    save(e.store / "twin.toml", twin)
    d = e.decide("paint-app", at)
    got = next(r["decision"]["hash"] for r in d["chain_element"] if r["dependency"] == "geom-math")
    hashes = [AP.m11.digest_file("decision", e.store / n) for n in ("twin.toml", "D-geom-math-second.toml")]
    return later_ok and got == min(hashes), got


@case("R1a", "completeness: missing row", 'require(not (closure - set(keys)),')
def r1a(e):
    p = e.packages["paint-app"]
    p["dependency"].pop(0)
    p["dependency_inventory"][0]["entries"] -= 1
    return joined(e)


@case("R1b", "completeness: extra row", 'require(not (set(keys) - closure)')
def r1b(e):
    p = e.packages["paint-app"]
    row = deepcopy(p["dependency"][0]); row["id"] = "extra"; row["lock"]["entry"] = "ghost 0.1.0"
    p["dependency"].append(row); p["dependency_inventory"][0]["entries"] += 1
    return joined(e)


@case("R2", "identity join: source.commit/path mismatch", 'require(core.b1_git_revision_equal(row["source"],')
def r2(e):
    e.packages["paint-app"]["dependency"][0]["source"]["path"] = "wrong"
    return joined(e)


@case("R3", "identity join: source.commit/path mismatch", 'require(core.b1_git_revision_equal(row["source"],')
def r3(e):
    e.packages["paint-app"]["dependency"][0]["source"]["commit"] = "c" * 40
    return joined(e)


for ident, rel in (("R4a", "Cargo.lock"), ("R4b", "geom-math/Cargo.toml")):
    def f(e, rel=rel):
        with (e.root / rel).open("a") as out:
            out.write("\n# drift\n")
        return joined(e)
    case(ident, "input digests: digest mismatch", 'require(hashdomains.digest("artifact:", raw) == row["digest"],')(f)


@case("R4c", "reader: input is not workspace Cargo.lock", 'require(lock_path.name == "Cargo.lock",')
def r4c(e):
    shutil.copyfile(e.root / "Cargo.lock", e.root / "copy.lock")
    p = e.packages["paint-app"]
    p["dependency_inventory"][0]["input"][0]["path"] = "../../../copy.lock"
    return joined(e)


@case("R4d", "reader: missing or extra input row", 'require(supplied == expected')
def r4d(e):
    p = e.packages["paint-app"]
    (e.root / "extra.toml").write_text("")
    p["dependency_inventory"][0]["input"].append(dict(role="member-manifest", path="../../../extra.toml", digest=C.hashdomains.digest("artifact:", b"")))
    return joined(e)


@case("R62", "input digests: missing or unresolvable reader input", 'raise Failure(f"input digests: missing or unresolvable reader input')
def r62(e):
    (e.root / "Cargo.lock").unlink()
    return joined(e)


@case("R19", "reader: member/lock key bijection mismatch", 'require(set(member_by_key) ==')
def r19(e):
    cargo_edit(e, "geom-math/Cargo.toml", 'name = "geom-math"', 'name = "wrong"')
    return joined(e)


@case("R20", "reader: duplicate canonical key", 'require(key not in by_key,')
def r20(e):
    cargo_edit(e, "Cargo.lock", "version = 4", 'version = 4\n[[package]]\nname = "geom-math"\nversion = "0.1.0"\nsource = "registry+test"')
    return joined(e)


@case("R21", "reader: subject.path does not match member", 'require(len(starts) == 1,')
def r21(e):
    e.packages["paint-app"]["subject"]["path"] = "wrong"
    return joined(e)


for ident, source in (("R22", "registry+fixture"), ("R23", "git+fixture")):
    def f(e, source=source):
        cargo_edit(e, "Cargo.lock", 'dependencies = ["raster-draw 0.1.0"]', 'dependencies = ["raster-draw 0.1.0", "external 1.0.0 (' + source + ')"]\n[[package]]\nname="external"\nversion="1.0.0"\nsource="' + source + '"')
        cargo_edit(e, "paint-app/Cargo.toml", '[dependencies]', '[dependencies]\nexternal = "1"')
        return joined(e)
    case(ident, "reader: needs delivered identities (0.4.x)", 'require(not any("source" in by_key[k]')(f)


@case("R24", "reader: lockfile version does not match reader", 'require(lock.get("version") in (3, 4)')
def r24(e):
    cargo_edit(e, "Cargo.lock", "version = 4", "version = 3")
    return joined(e)


@case("R25", "reader: unsupported workspace members", 'require(isinstance(members, list)')
def r25(e):
    cargo_edit(e, "Cargo.toml", '"geom-math"', '"geom-*"')
    return joined(e)


@case("R5", "no decision qualifies", 'raise Failure("no decision qualifies"')
def r5(e):
    for p in e.store.glob("*.toml"):
        p.unlink()
    return joined(e)


@case("R6", "issuer not in issuers", 'require(child.get("document", {}).get("issuer") in definition["issuers"],')
def r6(e):
    e.specs["paint-app"]["acceptance"]["authority_store"][0]["issuers"] = ["outsider"]
    return joined(e)


@case("R7", "whole-tree / other-subtree near miss", 'if bs.get("commit") == dep["source"].get("commit")')
def r7(e):
    e.decisions["geom-math"]["binds"]["subject"].pop("path")
    edit_child(e)
    return joined(e)


@case("R8", "child ineligible at T: [validity].stale_after", 'require(eligible, "child ineligible at T:')
def r8(e):
    e.decisions["geom-math"]["validity"]["stale_after"] = "2026-10-09"
    edit_child(e)
    return joined(e)


@case("R9", "child future-issued at T", 'require(timestamp(child["document"]["issued_at"]) <= at,')
def r9(e):
    e.decisions["geom-math"]["chain_evaluation"]["at"] = "2026-10-11T00:00:00Z"
    edit_child(e, issued_at="2026-10-11T00:00:00Z")
    return joined(e)


def superseder(e, issued, issuer="lead", verdict="rejected"):
    doc = deepcopy(e.decisions["geom-math"])
    doc["document"].update(id="superseder", issued_at=issued, issuer=issuer, verdict=verdict)
    save(e.store / "superseder.toml", doc)


@case("R10", "child superseded at T", 'require(not self.superseded(row, definition, rows, at),')
def r10(e):
    superseder(e, "2026-10-10T12:00:01Z")
    return detail(e.context().evaluate(e.specs["paint-app"], e.packages["paint-app"], e.paths["paint-app"][1], "2026-10-10T12:00:02Z"))


@case("R10b", "unlisted superseder ignored", 'if s.get("document", {}).get("issuer") not in definition["issuers"]')
def r10b(e):
    superseder(e, "2026-10-10T12:00:01Z", "outsider")
    e.decide("paint-app", "2026-10-10T12:00:02Z")
    rep = e.check()
    return rep.ok(), detail(rep)


def isolated(e):
    e.add("geom-math", [], suffix="-second", issued="2026-10-10T12:00:01Z")
    e.decide("paint-app", "2026-10-10T12:00:02Z")
    pin = next(r["decision"]["id"] for r in e.decisions["paint-app"]["chain_element"] if r["dependency"] == "geom-math")
    assert pin == "D-geom-math-second", pin


@case("R11", "runtime/geom-math: pinned child not found", 'require(matches, "pinned child not found",')
def r11(e):
    isolated(e)
    (e.store / "D-geom-math.toml").unlink()
    return detail(e.check())


@case("R14", "budget max_depth exceeded", 'require(len(self.active) < self.limits["max_depth"]')
def r14(e):
    return detail(snapshot(e, max_depth=1))


@case("R15", "recorded budget above ceiling", 'require(all(type(value[k]) is int')
def r15(e):
    return detail(snapshot(e, max_evaluations=10001))


@case("R16", "reserved or unknown chain fields", 'if extra:')
def r16(e):
    messages = []
    for field in ("bridge_min", "min_class", "profiles", "authorship"):
        spec = deepcopy(e.specs["paint-app"])
        spec["requirement"][1]["chain"][field] = "reserved"
        messages.append(detail(AP.check_specification(spec)))
    assert all("reserved or unknown chain fields" in s for s in messages), messages
    return "\n".join(messages)


@case("R17", "relation has no covering inventory meeting completeness", 'if not covering:')
def r17(e):
    e.specs["paint-app"]["requirement"][1]["chain"]["relations"].append("platform")
    result = e.evaluate()
    cov = AP.compute_coverage(e.specs["paint-app"], e.packages["paint-app"], e.paths["paint-app"][1])
    C.merge_coverage(cov, result)
    rendered = C.render(e.specs["paint-app"], e.packages["paint-app"], cov,
                        e.decisions["paint-app"], decision_ok=True)
    assert "stack accepted" not in rendered
    return detail(result)


@case("R18", "weakened without relaxed", 'for key in weaker:')
def r18(e):
    base = e.specs["paint-app"]
    variants = [("relations", []), ("depth", "direct"), ("level", "C0"), ("completeness", "declared"), ("allow_conditions", True), ("unaccepted", "gap"), ("boundary", [dict(identity=dict(commit="b"*40), reason="base")]), ("acceptors", ["trusted", "extra"])]
    reports = []
    for field, value in variants:
        new = deepcopy(base); new["requirement"][1]["chain"][field] = value
        reports.append(detail(AP.check_specification_tightening(new, base)))
    for field, value in (("issuers", ["lead", "maintainer", "extra"]), ("kind", "git")):
        new = deepcopy(base); new["acceptance"]["authority_store"][0][field] = value
        reports.append(detail(AP.check_specification_tightening(new, base)))
    assert all("weakened without relaxed" in s for s in reports), reports
    return "\n".join(reports)


@case("R26", "accepted-with-conditions", 'require(eligible, "child ineligible at T:')
def r26(e):
    d = e.decisions["geom-math"]
    d["disposition"][0].update(status="satisfied-with-conditions", conditions=["c"])
    d["condition"] = [dict(id="c", requirement="own", statement="follow up", owner="consumer", due="2027-01-01", verify="review followup", discharged_by="reviewer")]
    edit_child(e, verdict="accepted-with-conditions")
    return joined(e)


@case("R27", "not 'final'", 'require(eligible, "child ineligible at T:')
def r27(e):
    e.specs["geom-math"]["acceptance"]["phase"] = "exploratory"
    e.write("geom-math"); e.decide("geom-math")
    return joined(e)


@case("R28", "producer identity set", 'if issuer is not None and issuer in producer_names:', "acceptance_protocol.py")
def r28(e):
    e.specs["geom-math"]["parties"]["producer"]["name"] = "maintainer"
    e.write("geom-math"); e.decide("geom-math")
    return joined(e)


@case("R29", "store not configured: child-trusted", 'require(sid in self.stores,')
def r29(e):
    spec = e.specs["raster-draw"]
    spec["acceptance"]["authority_store"].append(dict(id="child-trusted", kind="dir", issuers=["lead", "maintainer"]))
    spec["requirement"][1]["chain"]["acceptors"] = ["child-trusted"]
    e.write("raster-draw")
    context = C.Invocation(AP, {"trusted": e.store, "child-trusted": e.store}, {e.commit: e.root}, e.root)
    with patch.object(e, "context", return_value=context):
        e.decide("raster-draw")
    return joined(e)


@case("R30", "cross-org C2 is forbidden", 'if isinstance(spec.get("parties"), dict) and spec["parties"].get("boundary") == "cross-org":')
def r30(e):
    e.specs["paint-app"]["parties"]["boundary"] = "cross-org"
    return detail(AP.check_specification(e.specs["paint-app"]))


@case("R31", "child build input digest mismatch", 'require(hashdomains.digest("artifact:", target.read_bytes()) == item["digest"],')
def r31(e):
    (e.root / "geom-math/src/lib.rs").write_text("// drift\n")
    return detail(e.check())


@case("R32", "self-edge", 'require(not equal(dep["source"], package["subject"]),')
def r32(e):
    pkg = e.packages["paint-app"]
    pkg["dependency_inventory"].append(dict(id="manual", source="manual", covers=["runtime"], entries=1))
    pkg["dependency"].append(dict(id="self", name="self", inventory="manual", relation="runtime", role="direct", consumed="source", source=C.identity(pkg["subject"])))
    return joined(e)


def effect_detail(e, date):
    historical = e.check()
    effect = e.check(effect=date)
    eligible, reason = AP.check_decision_effect(e.decisions["paint-app"], e.specs["paint-app"], effect, date, False)
    assert historical.ok() and effect.ok(), detail(historical) + detail(effect)
    assert not eligible and "ineligible at D" in reason, reason
    return "historically valid; " + reason


@case("R33", "child ineligible at D", 'if not eligible:')
def r33(e):
    return effect_detail(e, "2028-01-01")


@case("R34", "child ineligible at D", 'if not eligible:')
def r34(e):
    e.decisions["geom-math"]["validity"]["stale_after"] = "2026-10-11"
    edit_child(e)
    e.decide("raster-draw")
    isolated(e)
    return effect_detail(e, "2026-10-12")


@case("R35", "child superseded at D", 'if self.superseded(row, definition, rows, d):')
def r35(e):
    superseder(e, "2026-10-11T00:00:00Z")
    return effect_detail(e, "2026-10-12")


@case("R36", "pinned child not found", 'require(matches, "pinned child not found",')
def r36(e):
    (e.store / "D-raster-draw.toml").unlink()
    historical, effect = e.check(), e.check(effect="2026-10-12")
    eligible, reason = AP.check_decision_effect(e.decisions["paint-app"], e.specs["paint-app"], effect, "2026-10-12", False)
    a, b = detail(historical), detail(effect)
    return not historical.ok() and not effect.ok() and not eligible and "not VALID" in reason and "pinned child not found" in a and "pinned child not found" in b, a + b + reason


@case("R37", "differs from snapshot row set", 'if not isinstance(got, list) or not all(isinstance(x, str) for x in got)')
def r37(e):
    original = deepcopy(e.decisions["paint-app"])
    messages = []
    for field in ("chain_basis", "chain_boundary", "chain_gaps"):
        e.decisions["paint-app"] = deepcopy(original)
        e.decisions["paint-app"]["disposition"][1][field] = ["forged"]
        message = detail(e.check())
        assert field + " differs from snapshot row set" in message
        messages.append(message)
    return "\n".join(messages)


@case("R38", "basis forbidden on chain disposition", 'if "basis" in disp:')
def r38(e):
    e.decisions["paint-app"]["disposition"][1]["basis"] = []
    return detail(e.check())


@case("R39", "verification.run names dependency id", 'if any(r.get("claim") in dep_ids')
def r39(e):
    e.decisions["paint-app"]["verification"]["run"] = [dict(claim="geom-math", command="x", result="pass", observed="x", at=T)]
    return detail(e.check())


@case("R40", "indeterminate is not a gap", 'status = "gap" if exc.status == "refused"')
def r40(e):
    e.specs["paint-app"]["requirement"][1]["chain"]["unaccepted"] = "gap"
    result = e.context(stores=False).evaluate(e.specs["paint-app"], e.packages["paint-app"], e.paths["paint-app"][1], T)
    ok = result[0]["runtime"]["status"] != "satisfied" and all(r["status"] == "indeterminate" for r in result[2])
    return ok, ("indeterminate is not a gap" if ok else "converted to gap")


@case("R41", "C1/C3 reserved", 'elif rule["level"] in ("C1", "C3"):')
def r41(e):
    reports = []
    for level in ("C1", "C3"):
        e.specs["paint-app"]["requirement"][1]["chain"] = rule(level)
        reports.append(joined(e))
    assert all("C1/C3 reserved" in s for s in reports)
    return "\n".join(reports)


@case("R42", "max_elements exceeded", 'if len(selected) > rule["max_elements"]:')
def r42(e):
    e.specs["paint-app"]["requirement"][1]["chain"]["max_elements"] = 1
    return joined(e)


@case("R43", "but no [[deviation]] names it", 'if status != "satisfied" and rid not in dev_by_req:', "acceptance_protocol.py")
def r43(e):
    for p in e.store.glob("*.toml"):
        p.unlink()
    sp, pp = e.paths["paint-app"]
    return detail(AP.check_package(e.packages["paint-app"], e.specs["paint-app"], pp, sp, False, chain_context=e.context())[0])


@case("R44", "B1 path grammar", 'if "path" in source_tbl and not _valid_b1_path(source_tbl["path"]):', "../../format_acceptance/tools/check_core.py")
def r44(e):
    messages = []
    for path in ("a/./b", "a//b", "..", "/a", "a\\b", "é"):
        e.packages["paint-app"]["dependency"][0]["source"]["path"] = path
        messages.append(joined(e))
    assert all("B1 path grammar" in s for s in messages)
    return "\n".join(messages)


@case("R45", "path is an ERROR inside a [[subject.components]] locator", 'if "path" in component:', "../../format_acceptance/tools/check_core.py")
def r45(e):
    pkg = deepcopy(e.packages["paint-app"])
    pkg["subject"].pop("commit"); pkg["subject"].pop("path")
    pkg["subject"]["components"] = [dict(name="part", commit=COMMIT, path="part")]
    save(e.paths["paint-app"][1], pkg)
    rep = AP.check_core.validate(e.paths["paint-app"][1], strict=False, root=e.root)
    return detail(rep)


@case("R46", "store document.id does not equal file stem", 'require(re.fullmatch(r"[A-Za-z0-9._-]+", p.stem)')
def r46(e):
    edit_child(e, id="different")
    return joined(e)


for ident, rel, old, new in (("R47", "Cargo.lock", 'dependencies = ["geom-math"]', 'dependencies = []'), ("R55", "Cargo.lock", 'dependencies = ["raster-draw 0.1.0"]', 'dependencies = []')):
    def f(e, rel=rel, old=old, new=new):
        cargo_edit(e, rel, old, new)
        return joined(e)
    case(ident, "reader: manifest-lock edge mismatch", 'require(set(manifest_edges) == lock_names,')(f)


@case("R48", "gap under unaccepted=refuse", 'require(rule["unaccepted"] == "gap",')
def r48(e):
    e.decisions["paint-app"]["chain_element"][0].update(status="gap")
    e.decisions["paint-app"]["chain_element"][0].pop("decision")
    return detail(e.check())


@case("R49", "snapshot element identity/declaration differs", 'require(all(old.get(k) == v for k, v in row.items()),')
def r49(e):
    make_gap(e)
    e.decisions["paint-app"]["chain_element"][0]["identity"]["path"] = "different"
    return detail(e.check())


@case("R52", "legacy child: re-issue under acceptance-protocol/1", 'require(child.get("document", {}).get("protocol") != "acceptance-protocol/0",')
def r52(e):
    edit_child(e, protocol="acceptance-protocol/0")
    return joined(e)


@case("R54", "child superseded at T", 'require(not self.superseded(row, definition, rows, at),')
def r54(e):
    e.decide("paint-app", "2026-10-10T12:00:02Z")
    superseder(e, "2026-10-10T12:00:01Z")
    return detail(e.check())


@case("R56", "reader: virtual workspace required", 'require("workspace" in workspace and "package" not in workspace,')
def r56(e):
    cargo_edit(e, "Cargo.toml", "[workspace]", '[package]\nname="root"\nversion="0.1.0"\n[workspace]')
    return joined(e)


@case("R57", "store hygiene:", 'require(not p.is_symlink() and p.is_file()')
def r57(e):
    (e.store / "link.toml").symlink_to(e.store / "D-geom-math.toml")
    return joined(e)


@case("R58", "unsupported minor for acceptance-protocol/1", 'if type(document.get("minor")) is not int or document.get("minor") != 0:', "acceptance_protocol.py")
def r58(e):
    e.specs["paint-app"]["document"]["minor"] = 1
    return detail(AP.check_specification(e.specs["paint-app"]))


def checkout_estate(e):
    root = e.root / "checkout"
    shutil.copytree(SOURCE, root)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PRE_COMMIT", "SKIP"))}
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args], env=env, stderr=subprocess.DEVNULL, text=True).strip()
    git("init", "-q"); git("add", "."); git("commit", "-qm", "subject")
    commit = git("rev-parse", "HEAD")
    child = Estate(root, commit)
    git("add", "."); git("commit", "-qm", "edge packages after subject")
    return child


@case("G8", "two-commit re-stamp")
def g8(e):
    child = checkout_estate(e)
    try:
        rep = child.check()
        return rep.ok(), detail(rep)
    finally:
        child.close()


@case("G10", "prose item containing / is not a checkout citation")
def g10(e):
    prose = "paint-app (paint-app/src/lib.rs, tested through the compiled `paint` binary and the library directly)"
    for item in (prose, "src/lib.rs explanation", "src/lib.rs\n", "src/(lib.rs)",
                 "src/lib.rs)", "./lib.rs", "../lib.rs", "src/../lib.rs", "/src/lib.rs",
                 "src//lib.rs", "src/", "src\\lib.rs", "lib", ".", "..", "", None):
        assert C.claim_sources(dict(item=item)) == [], repr(item)
    for item in ("src/lib.rs", "src/lib.rs::symbol", "lib.rs", "lib.rs::symbol", "src/lib"):
        assert C.claim_sources(dict(item=item)) == [item.split("::", 1)[0]], item
    for source in ("../../src/lib.rs", dict(path="../../src/lib.rs")):
        assert C.claim_sources(dict(source=source, item=prose)) == ["../../src/lib.rs"]
    child = checkout_estate(e)
    try:
        child.packages["paint-app"]["claim"][0]["item"] = prose
        child.write("paint-app")
        child.decide("paint-app")
        sp, pp = child.paths["paint-app"]
        result = subprocess.run([
            sys.executable, str(Path(AP.__file__)), "check-decision",
            str(child.store / "D-paint-app.toml"), "--spec", str(sp), "--package", str(pp),
            "--store", "trusted=" + str(child.store), "--tree", child.commit + "=" + str(child.root),
        ], capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    finally:
        child.close()


def exported_checkout(e):
    """Commit the presented tree without importing its named source commit."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PRE_COMMIT", "SKIP"))}
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "public export")):
        subprocess.run(["git", "-C", str(e.root), "-c", "core.hooksPath=/dev/null",
                        "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
                       env=env, capture_output=True, text=True, check=True)


@case("G11", "tree checkout: commit aaaaaaaaaaaa not present in this repository; recorded digests checked", 'note = f"NOTE tree checkout: commit')
def g11(e):
    exported_checkout(e)
    context = e.context()
    for _ in range(2):
        context.checkout(e.packages["paint-app"], e.paths["paint-app"][1])
    sp, pp = e.paths["paint-app"]
    result = subprocess.run([
        sys.executable, str(Path(AP.__file__)), "check-decision",
        str(e.store / "D-paint-app.toml"), "--spec", str(sp), "--package", str(pp),
        "--store", "trusted=" + str(e.store), "--tree", e.commit + "=" + str(e.root),
    ], capture_output=True, text=True)
    output = result.stdout + result.stderr
    note = "NOTE " + REASONS["G11"]
    render_ok, render_detail = render_in_clone(e)
    return result.returncode == 0 and note in output and context.checkout_notes == [note] and render_ok, output + render_detail


def render_in_clone(e):
    sp, pp = e.paths["paint-app"]
    command = [
        sys.executable, str(Path(AP.__file__)), "render", str(sp), str(pp),
        str(e.store / "D-paint-app.toml"), "--store", "trusted=" + str(e.store),
        "--tree", e.commit + "=" + str(e.root),
    ]
    stdout = subprocess.run(command, capture_output=True, text=True)
    out = e.root / "view.md"
    written = subprocess.run([*command, "--out", str(out)], capture_output=True, text=True)
    views = [stdout.stdout, out.read_text() if out.exists() else ""]
    note = "NOTE " + REASONS["G11"]
    ok = stdout.returncode == written.returncode == 0
    for view in views:
        ok = ok and view.splitlines().count(note) == 1 and "stack accepted over" in view
        ok = ok and 0 <= view.find(note) < view.find("| Relation |") < view.find("stack accepted over")
    ok = ok and views[0].rstrip() == views[1].rstrip()
    return ok, "stdout and --out preserve checkout notes before stack table" if ok else "render checkout note, order, label or output parity failed: " + repr(views)


@case("G11-render", "stdout and --out preserve checkout notes before stack table", "lines.extend(context.checkout_notes)", "acceptance_protocol.py")
def g11_render(e):
    exported_checkout(e)
    return render_in_clone(e)


@case("R79", "input digests: digest mismatch", 'require(hashdomains.digest("artifact:", raw) == row["digest"],')
def r79(e):
    exported_checkout(e)
    # The checkout fallback itself succeeds, but reader digest checks still fail.
    e.context().checkout(e.packages["paint-app"], e.paths["paint-app"][1])
    e.packages["paint-app"]["dependency_inventory"][0]["input"][0]["digest"] = C.hashdomains.digest("artifact:", b"different")
    result = e.evaluate()
    return any(REASONS["R79"] in error for error in result[3]), detail(result)


@case("R78", "tree checkout: input absent from commit", 'pointers.append(item)')
def r78(e):
    child = checkout_estate(e)
    try:
        package = child.packages["paint-app"]
        package["claim"][0]["item"] = "src/missing.rs::symbol"
        try:
            child.context().checkout(package, child.paths["paint-app"][1])
        except C.Failure as exc:
            return exc.reason
        return "missing item citation silently skipped"
    finally:
        child.close()


@case("R59", "tree checkout: presented input differs from commit", 'require(presented.returncode == 0 and presented.stdout.strip() == committed.stdout.strip(),')
def r59(e):
    child = checkout_estate(e)
    try:
        (child.root / "paint-app/src/lib.rs").write_text("// drift\n")
        return detail(child.check())
    finally:
        child.close()


@case("R60", "gap replay indeterminate:", 'if gap and any(s == "indeterminate"')
def r60(e):
    original = deepcopy(e.decisions["geom-math"])
    make_gap(e)
    original["binds"]["package"]["path"] = "missing/acceptance.toml"
    save(e.store / "D-geom-math.toml", original)
    return detail(e.check())


@case("R61", "gap replay indeterminate:", 'if gap and any(s == "indeterminate"')
def r61(e):
    original = deepcopy(e.decisions["geom-math"])
    make_gap(e)
    original["binds"]["package"]["path"] = "missing/acceptance.toml"
    save(e.store / "D-geom-math.toml", original)
    # The actual decision-time result is indeterminate; forge its row and witness sets.
    e.decide("paint-app")
    d = e.decisions["paint-app"]
    assert any(r["status"] == "indeterminate" for r in d["chain_element"])
    for row in d["chain_element"]:
        row["status"] = "gap"
    disp = next(r for r in d["disposition"] if r["requirement"] == "runtime")
    disp.update(chain_basis=[], chain_boundary=[], chain_gaps=sorted(r["dependency"] for r in d["chain_element"]), status="satisfied")
    d["document"]["verdict"] = "accepted"
    return detail(e.check())



for ident, label in (("R50", "mixed-specification-package-R50"), ("R51", "legacy-predecessor-R51"), ("R53", "legacy-chain-fields-R53")):
    def f(e, label=label):
        from fixtures import version_route_cases
        found = next(r for r in version_route_cases.run() if r[0] == label)
        return found[1], str(found[2])
    case(ident, "mixed acceptance-protocol/0 and acceptance-protocol/1" if ident != "R53" else "chain fields in an acceptance-protocol/0 document",
         'if len(versions) > 1:' if ident != "R53" else 'if legacy and (any(key in doc', "version_route.py")(f)

for ident, rel, old, new, reason, guard in (
    ("R25-version", "geom-math/Cargo.toml", 'version = "0.1.0"', 'version.workspace = true', "literal package name/version required", 'require(all(isinstance(pkg.get(k), str) and pkg[k]'),
    ("R25-rename", "paint-app/Cargo.toml", 'path = "../raster-draw"', 'path = "../raster-draw", package = "raster-draw"', "renamed dependency unsupported", 'require("package" not in entry,'),
    ("R25-workspace-dep", "paint-app/Cargo.toml", 'path = "../raster-draw"', 'workspace = true', "workspace dependency unsupported", 'require("workspace" not in entry,'),
    ("R25-target", "paint-app/Cargo.toml", '[dependencies]', '[target.unix.dependencies]', "target dependency tables unsupported", 'require("target" not in manifest,'),
    ("R56-member", "geom-math/Cargo.toml", '[package]', '[package]\nworkspace = ".."', "package.workspace unsupported", 'require("workspace" not in pkg,'),
    ("reader-path-target", "paint-app/Cargo.toml", 'path = "../raster-draw"', 'path = "../geom-math"', "path target mismatch", 'require(target in member_by_key and resolved =='),
):
    def f(e, rel=rel, old=old, new=new):
        cargo_edit(e, rel, old, new)
        return joined(e)
    case(ident, reason, guard)(f)

@case("R57-directory", "store hygiene:", 'require(not p.is_symlink() and p.is_file()')
def r57_directory(e):
    (e.store / "directory").mkdir()
    return joined(e)

@case("R57-unparsable", "store hygiene: unparsable file", 'raise Failure(f"store hygiene: unparsable file')
def r57_unparsable(e):
    (e.store / "broken.toml").write_text("[invalid")
    return joined(e)

@case("G-reader-v3", "cargo-lock/3")
def reader_v3(e):
    cargo_edit(e, "Cargo.lock", "version = 4", "version = 3")
    pkg = e.packages["geom-math"]
    pkg["dependency_inventory"][0]["reader"] = "cargo-lock/3"
    result = e.evaluate("geom-math")
    return result[0]["runtime"]["status"] == "satisfied", detail(result)

@case("G-dev-build", "union includes dev and build edges")
def dev_build(e):
    cargo_edit(e, "paint-app/Cargo.toml", '[dependencies]', '[dev-dependencies]')
    cargo_edit(e, "raster-draw/Cargo.toml", '[dependencies]', '[build-dependencies]')
    result = e.evaluate("geom-math")
    return result[0]["runtime"]["status"] == "satisfied", detail(result)



@case("R4d-missing", "reader: missing input", 'require(p in inputs,')
def missing_input(e):
    e.packages["paint-app"]["dependency_inventory"][0]["input"].pop()
    return joined(e)

@case("G-store-freeze", "one frozen store view per invocation")
def frozen_view(e):
    context = e.context()
    (e.store / "D-geom-math.toml").unlink()
    sp, pp = e.paths["paint-app"]
    before = AP.check_decision(e.decisions["paint-app"], e.specs["paint-app"], e.packages["paint-app"], sp, pp, chain_context=context)
    after = e.check()
    return before.ok() and not after.ok() and "pinned child not found" in detail(after), detail(before) + detail(after)


@case("G-cli", "consumer CLI tree/store mappings")
def cli_chain(e):
    sp, pp = e.paths["paint-app"]
    tool = str(Path(AP.__file__))
    options = ["--tree", e.commit + "=" + str(e.root), "--store", "trusted=" + str(e.store)]
    commands = [
        ["check-package", str(pp), "--spec", str(sp), *options],
        ["check-decision", str(e.store / "D-paint-app.toml"), "--package", str(pp), "--spec", str(sp), *options],
        ["check-decision", str(e.store / "D-paint-app.toml"), "--package", str(pp), "--spec", str(sp), "--effect", "--now", "2026-10-12", *options],
        ["decide", str(pp), "--spec", str(sp), "--issuer", "lead", "--out", str(e.root / "draft.toml"), *options],
        ["render", str(sp), str(pp), str(e.store / "D-paint-app.toml"), *options],
    ]
    output = []
    for args in commands:
        result = subprocess.run([sys.executable, tool, *args], capture_output=True, text=True)
        output.append(result.stdout + result.stderr)
        if result.returncode:
            return False, "\n".join(output)
    draft = tomllib.loads((e.root / "draft.toml").read_text())
    return draft["binds"]["package"]["path"] == pp.relative_to(e.root).as_posix() and "chain_evaluation" in draft, "\n".join(output)


for ident, field, value, reason in (
    ("R16-depth", "depth", 2, "chain.depth must be one of"),
    ("R16-binds", "binds", "source-with-bridge", "chain.binds must be one of"),
):
    def f(e, field=field, value=value):
        e.specs["paint-app"]["requirement"][1]["chain"][field] = value
        return detail(AP.check_specification(e.specs["paint-app"]))
    case(ident, reason, 'if not isinstance(rule.get(key), str) or rule[key] not in allowed:')(f)

for field in sorted(AP.check_core.DEPENDENCY_RESERVED_TABLES):
    def f(e, field=field):
        e.packages["paint-app"]["dependency"][0][field] = {}
        return joined(e)
    case("R16-" + field, '.' + field + ' is reserved', 'for reserved in DEPENDENCY_RESERVED_TABLES:', '../../format_acceptance/tools/check_core.py')(f)

@case("R16-delivered-value", "consumed 'delivered' is reserved", 'if consumed == "delivered":', '../../format_acceptance/tools/check_core.py')
def reserved_delivered(e):
    e.packages["paint-app"]["dependency"][0]["consumed"] = "delivered"
    return joined(e)

@case("R16-checksum", ".lock.checksum is reserved", 'if "checksum" in lock_tbl:', '../../format_acceptance/tools/check_core.py')
def reserved_checksum(e):
    e.packages["paint-app"]["dependency"][0]["lock"]["checksum"] = "reserved"
    return joined(e)

@case("R16-toolchain-inventory", ".source 'toolchain' is reserved", 'if source == "toolchain":', '../../format_acceptance/tools/check_core.py')
def reserved_inventory(e):
    e.packages["paint-app"]["dependency_inventory"][0]["source"] = "toolchain"
    return joined(e)

@case("R16-store-kind", "authority_store kind/fields reserved", 'if row.get("kind") != "dir" or set(row)')
def reserved_store(e):
    e.specs["paint-app"]["acceptance"]["authority_store"][0]["kind"] = "git"
    return detail(AP.check_specification(e.specs["paint-app"]))


@case("R63", "reader: lockfile rows carry relation 'runtime' only", 'require(inv["covers"] == ["runtime"]')
def r63(e):
    e.packages["paint-app"]["dependency_inventory"][0]["covers"] = ["runtime", "platform"]
    e.packages["paint-app"]["dependency"][0]["relation"] = "platform"
    result = e.evaluate()
    return "\n".join(result[3])


def render_without_label(e, decision):
    sp, pp = e.paths["paint-app"]
    rendered = AP.render_markdown(e.specs["paint-app"], e.packages["paint-app"], decision, sp, pp, None, e.context())
    ok = "stack accepted over" not in rendered and "| Relation |" in rendered and "chain policy satisfied" in rendered
    return ok, ("no acceptance label; chain policy satisfied" if ok else rendered)


@case("R64", "no acceptance label; chain policy satisfied", 'if decision is None or not decision_ok')
def r64(e):
    assert g1(e)[0]
    return render_without_label(e, None)


@case("R65", "no acceptance label; chain policy satisfied", 'if decision is None or not decision_ok')
def r65(e):
    assert g1(e)[0]
    d = e.decisions["paint-app"]
    d["document"]["verdict"] = "rejected"
    d["verification"]["run"] = [dict(claim="own-claim", command="review", result="fail", observed="Consumer review failed", at=T)]
    next(r for r in d["disposition"] if r["requirement"] == "own").update(status="unsatisfied", note="Consumer review failed")
    assert e.check().ok(), detail(e.check())
    return render_without_label(e, d)


@case("R66", "but no [[deviation]] names it", 'if chain_decision is None and req.get("kind")', "acceptance_protocol.py")
def r66(e):
    d = e.decisions["paint-app"]
    for row in d["chain_element"]:
        row.update(status="refused", reason="store not configured: trusted")
        row.pop("decision")
    d["disposition"][1].update(chain_basis=[], status="unsatisfied")
    d["document"]["verdict"] = "rejected"
    return detail(e.check())


@case("R67", "store hygiene: bad issued_at", 'raise Failure(f"store hygiene: bad issued_at')
def r67(e):
    messages = []
    for issued in ("invalid", "2026-10-10T12:00:01", "2026-10-10 12:00:01Z", "20261010T120001Z"):
        superseder(e, issued)
        messages.append("\n".join(e.evaluate()[3]))
    return all("store hygiene: bad issued_at" in m for m in messages), "\n".join(messages)


@case("R68", "tree checkout: presented input differs from commit", 'require(presented.returncode == 0 and presented.stdout.strip() == committed.stdout.strip(),')
def r68(e):
    child = checkout_estate(e)
    try:
        subprocess.run(["git", "-C", str(child.root), "update-index", "--skip-worktree", "paint-app/src/lib.rs"], check=True)
        (child.root / "paint-app/src/lib.rs").write_text("// hidden drift\n")
        return detail(child.check())
    finally:
        child.close()


@case("R69", "tree checkout: git unavailable", 'raise Failure("tree checkout: git unavailable")')
def r69(e):
    child = checkout_estate(e)
    try:
        with patch.dict(os.environ, {"PATH": str(child.root / "no-git")}):
            return detail(child.check())
    finally:
        child.close()


@case("R70", "malformed.toml: AttributeError", 'failure = Failure(')
def malformed_candidate(e):
    malformed = deepcopy(e.decisions["geom-math"])
    malformed["document"]["id"] = "malformed"
    malformed["chain_evaluation"] = "malformed"
    save(e.store / "malformed.toml", malformed)
    parent = e.decisions["paint-app"]
    pin = parent["chain_element"][0]["decision"]
    pin.update(id="malformed", hash=AP.m11.digest_file("decision", e.store / "malformed.toml"))
    try:
        e.context().select(e.specs["paint-app"], rule(), e.packages["paint-app"]["dependency"][0], C.timestamp(T), C.budget(C.CEILINGS), pin=pin)
    except C.Failure as exc:
        if exc.status != "error":
            return False, "malformed candidate was not an ERROR"
    else:
        return False, "malformed candidate accepted"
    result = e.evaluate(decision=parent)
    errors = "\n".join(result[3])
    other = next(r for r in result[2] if r["dependency"] == "raster-draw")
    return other["status"] == "satisfied" and "malformed.toml: AttributeError" in errors, errors


@case("R71", "snapshot unknown row key", 'require(set(old) <=')
def snapshot_unknown(e):
    e.decisions["paint-app"]["chain_element"][0]["forged"] = True
    return detail(e.check())


@case("G-budget-leaves", "one visit per candidate including leaves")
def budget_leaves(e):
    context = e.context()
    state = C.budget(C.CEILINGS)
    for _ in range(3):
        context.select(e.specs["paint-app"], rule(), e.packages["paint-app"]["dependency"][0], C.timestamp(T), state)
    return state.visits == 3 and not state.active, str(state.visits)


@case("R72", "budget max_evaluations exceeded", 'state.visit()')
def candidate_budget(e):
    e.add("geom-math", [], suffix="-second")
    state = C.budget(dict(max_depth=8, max_evaluations=1))
    try:
        e.context().select(e.specs["paint-app"], rule(), e.packages["paint-app"]["dependency"][0], C.timestamp(T), state, gap=True)
    except C.Failure as exc:
        return exc.reason
    return "budget bypassed"


@case("R73", "no acceptance label; chain policy satisfied", 'if decision is None or not decision_ok')
def invalid_render(e):
    assert g1(e)[0]
    e.decisions["paint-app"]["document"]["issuer"] = "outsider"
    return render_without_label(e, e.decisions["paint-app"])


@case("R74", "tree checkout: presented input differs from commit", 'env.update(GIT_CONFIG_NOSYSTEM=')
def replace_objects(e):
    child = checkout_estate(e)
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        def git(*args):
            return subprocess.check_output(["git", "-C", str(child.root), "-c", "core.hooksPath=/dev/null",
                                            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
                                           env=env, text=True).strip()
        (child.root / "paint-app/src/lib.rs").write_text("// replacement hides drift\n")
        git("add", "paint-app/src/lib.rs")
        replacement = git("commit-tree", git("write-tree"), "-m", "replacement")
        git("replace", child.commit, replacement)
        assert git("rev-parse", child.commit + ":paint-app/src/lib.rs") == git("hash-object", "paint-app/src/lib.rs")
        try:
            child.context().checkout(child.packages["paint-app"], child.paths["paint-app"][1])
        except C.Failure as exc:
            return exc.status == "error" and REASONS["R74"] in exc.reason, exc.reason
        return False, "replacement concealed drift"
    finally:
        child.close()


@case("R75", "tree checkout: probe failed:", 'raise Failure("tree checkout: probe failed: " + first_line)')
def corrupt_checkout(e):
    child = checkout_estate(e)
    try:
        (child.root / ".git/HEAD").write_text("corrupt HEAD\n")
        result = child.evaluate()
        errors = "\n".join(result[3])
        return REASONS["R75"] in errors, errors
    finally:
        child.close()


@case("R76", "but no [[deviation]] names it", 'if chain_decision is None and req.get("kind")', "acceptance_protocol.py")
def mixed_store_failures(e):
    # One candidate fails through an unconfigured child store; another has an
    # unlisted issuer. Both reasons survive in the same element's failure list.
    r29(e)
    e.add("raster-draw", ["geom-math"], suffix="-outsider")
    edit_child(e, "raster-draw-outsider", issuer="outsider")
    spec = e.specs["paint-app"]
    spec["requirement"][1]["chain"]["boundary"] = [dict(identity=dict(commit=e.commit, path="geom-math"), reason="trusted base")]
    e.write("paint-app")
    sp, pp = e.paths["paint-app"]
    rep, _ = AP.check_package(e.packages["paint-app"], spec, pp, sp, False, chain_context=e.context())
    message = detail(rep)
    return ("store not configured: child-trusted" in message and "issuer not in issuers" in message
            and any(REASONS["R76"] in error for error in rep.errors)
            and "decision-time evaluation governs" not in message), message


@case("G-probe-classification", "archive NOTE; other probe failures are errors")
def probe_classification(e):
    sp, pp = e.paths["paint-app"]
    rep, _ = AP.check_package(e.packages["paint-app"], e.specs["paint-app"], pp, sp, False, chain_context=e.context())
    assert rep.ok() and "NOTE tree is not a git checkout; recorded digests checked" in rep.warnings, detail(rep)
    for stderr in ("fatal: detected dubious ownership\nsecond line", "fatal: permission denied\nsecond line", "fatal: corrupt repository\nsecond line"):
        with patch.object(C.subprocess, "run", return_value=subprocess.CompletedProcess([], 128, "", stderr)):
            try:
                e.context().checkout(e.packages["paint-app"], pp)
            except C.Failure as exc:
                assert exc.status == "error" and exc.reason == "tree checkout: probe failed: " + stderr.splitlines()[0], str(exc)
            else:
                return False, "probe failure silently skipped"
    missing = f"fatal: Not a valid object name {e.commit}^{{commit}}"
    for code, stderr in ((128, "fatal: corrupt repository\n" + missing),
                         (128, "fatal: permission denied"), (1, missing), (128, ""),
                         (128, "error: expected commit type\n" + missing)):
        responses = [subprocess.CompletedProcess([], 0, str(e.root) + "\n", ""),
                     subprocess.CompletedProcess([], code, "", stderr)]
        with patch.object(C.subprocess, "run", side_effect=responses) as run:
            try:
                e.context().checkout(e.packages["paint-app"], pp)
            except C.Failure as exc:
                diagnostic = stderr.splitlines()[0] if stderr else "no diagnostic"
                assert exc.status == "error" and exc.reason == "tree checkout: probe failed: " + diagnostic, str(exc)
                args, kwargs = run.call_args
                assert args[0][-3:] == ["cat-file", "-e", e.commit + "^{commit}"]
                assert "--no-replace-objects" in args[0] and kwargs["env"]["LC_ALL"] == "C"
            else:
                return False, "commit probe failure silently skipped"
    child = checkout_estate(e)
    try:
        obj = child.root / ".git/objects" / child.commit[:2] / child.commit[2:]
        obj.chmod(0o600)
        obj.write_bytes(b"corrupt object\n")
        try:
            child.context().checkout(child.packages["paint-app"], child.paths["paint-app"][1])
        except C.Failure as exc:
            assert exc.status == "error" and exc.reason.startswith("tree checkout: probe failed: "), str(exc)
        else:
            return False, "corrupt commit silently skipped"
    finally:
        child.close()
    return True, "archive NOTE; other probe failures are errors"


@case("G-store-exemption", "only exclusively unconfigured elements receive P6 exemption")
def store_exemption(e):
    sp, pp = e.paths["paint-app"]
    context = e.context(stores=False)
    rep, _ = AP.check_package(e.packages["paint-app"], e.specs["paint-app"], pp, sp, False, chain_context=context)
    assert rep.ok() and "decision-time evaluation governs" in detail(rep), detail(rep)
    def select(spec, rule, dep, *args, **kwargs):
        if dep["id"] == "geom-math":
            return C.Invocation.store_rows(context, spec, rule)
        raise C.Failure("issuer not in issuers", "refused")
    with patch.object(context, "select", side_effect=select):
        rep, _ = AP.check_package(e.packages["paint-app"], e.specs["paint-app"], pp, sp, False, chain_context=context)
    return (any("P6" in error for error in rep.errors)
            and "decision-time evaluation governs" not in detail(rep)), detail(rep)


@case("G-error-order", "all input digests and checkout precede readers")
def error_order(e):
    pkg = e.packages["paint-app"]
    extra = deepcopy(pkg["dependency_inventory"][0])
    extra.update(id="second", entries=0)
    extra["input"][0]["digest"] = C.hashdomains.digest("artifact:", b"wrong")
    pkg["dependency_inventory"].append(extra)
    with patch.object(C, "cargo_reader", side_effect=C.Failure("reader indeterminate", "indeterminate")) as reader:
        # Dispatch is registered by function object, so inject the registry explicitly.
        try:
            C.inventories(pkg, e.paths["paint-app"][1], e.root, {"cargo-lock/4": reader})
        except C.Failure as exc:
            assert exc.status == "error" and "input digests: digest mismatch" in exc.reason, str(exc)
        else:
            return False, "digest missed"
        assert not reader.called
        pkg["dependency_inventory"].pop()
        checkout = lambda *args: C.require(False, "checkout error")
        try:
            C.inventories(pkg, e.paths["paint-app"][1], e.root, {"cargo-lock/4": reader}, checkout=checkout)
        except C.Failure as exc:
            assert exc.status == "error" and exc.reason == "checkout error", str(exc)
        else:
            return False, "checkout missed"
        return not reader.called, "readers not reached after input/checkout errors"


@case("G-gap-error-order", "gap ERROR beats indeterminate")
def gap_error_order(e):
    e.add("geom-math", [], suffix="-second")
    def candidate(row, *args):
        raise C.Failure("bad candidate", "error" if row["doc"]["document"]["id"] == "D-geom-math" else "indeterminate")
    with patch.object(C.Invocation, "candidate", side_effect=candidate):
        try:
            e.context().select(e.specs["paint-app"], rule(), e.packages["paint-app"]["dependency"][0], C.timestamp(T), C.budget(C.CEILINGS), gap=True)
        except C.Failure as exc:
            return exc.status == "error" and "gap replay error:" in exc.reason, str(exc)
    return False, "gap error missed"


@case("G-relative-root", "relative root resolved before identity join")
def relative_root(e):
    context = C.Invocation(AP, {"trusted": e.store}, {e.commit: Path(os.path.relpath(e.root))})
    root = context.root_for(e.packages["paint-app"], e.paths["paint-app"][1])
    result = context.evaluate(e.specs["paint-app"], e.packages["paint-app"], e.paths["paint-app"][1], T)
    return root == e.root and result[0]["runtime"]["status"] == "satisfied", detail(result)


@case("G-child-previous", "children resolve predecessors only through previous-dir")
def child_previous(e):
    context = e.context()
    context.previous_paths = [e.root / "top-level-only.toml"]
    context.previous_dir = e.root / "predecessors"
    observed = []
    original = AP.check_decision
    def checking(*args, **kwargs):
        observed.append(kwargs)
        return original(*args, **kwargs)
    with patch.object(AP, "check_decision", side_effect=checking):
        result = context.evaluate(e.specs["paint-app"], e.packages["paint-app"], e.paths["paint-app"][1], T)
    return (result[0]["runtime"]["status"] == "satisfied" and observed
            and all(not kw.get("previous_paths") and kw.get("previous_dir") == context.previous_dir for kw in observed)), detail(result)


@case("G-malformed-shapes", "malformed child input and store definitions produce errors")
def malformed_shapes(e):
    context = e.context()
    row = next(r for r in context.stores["trusted"] if r["doc"]["document"]["id"] == "D-geom-math")
    definition = e.specs["paint-app"]["acceptance"]["authority_store"][0]
    spec, package, sp, pp = context.resolve(row)
    for claims, reason in ((["bad"], "malformed child claim"), ([dict(evidence=[dict(build_inputs=[{}])])], "malformed child build input")):
        malformed = deepcopy(package)
        malformed["claim"] = claims
        with patch.object(context, "resolve", return_value=(spec, malformed, sp, pp)):
            try:
                context.candidate(row, definition, [], e.packages["paint-app"]["dependency"][0], rule(), C.timestamp(T), C.budget(C.CEILINGS))
            except C.Failure as exc:
                assert exc.status == "error" and exc.reason == reason, str(exc)
            else:
                return False, "malformed shape missed"
    old = deepcopy(e.specs["paint-app"])
    old["acceptance"]["authority_store"] = [{}]
    rep = AP.Reporter("malformed previous store")
    C.tightening(rep, "runtime", e.specs["paint-app"]["requirement"][1], old["requirement"][1], e.specs["paint-app"], old, False)
    return bool(rep.errors), detail(rep)


@case("G-effect-cli", "effect CLI keeps historical ok true")
def effect_cli(e):
    sp, pp = e.paths["paint-app"]
    result = subprocess.run([sys.executable, str(Path(AP.__file__)), "check-decision", str(e.store / "D-paint-app.toml"), "--spec", str(sp), "--package", str(pp), "--store", "trusted=" + str(e.store), "--tree", e.commit + "=" + str(e.root), "--effect", "--now", "2028-01-01", "--json"], capture_output=True, text=True)
    output = json.loads(result.stdout)
    return result.returncode == 1 and output["ok"] and not output["effect_eligible"] and "ineligible at D" in output["effect_reason"], result.stdout + result.stderr

@case("G-amendment-chain-roundtrip", "amendment serializer preserves paint-app chain and stores")
def amendment_chain_roundtrip(e):
    path = Path(AP.__file__).parents[1] / "examples/paint-stack/paint-app/acceptance-specification.toml"
    original = tomllib.loads(path.read_text())
    for boundaries in (None, [], [dict(identity=dict(commit=e.commit, path="geom-math"), reason="trusted base")]):
        source = deepcopy(original)
        if boundaries is not None:
            next(r for r in source["requirement"] if r.get("kind") == "chain")["chain"]["boundary"] = boundaries
        rendered = AP._render_specification_toml(source)
        restored = tomllib.loads(rendered)
        rep = AP.check_specification(restored)
        assert restored == source, "amendment serialization changed specification content"
        assert rep.ok(), detail(rep)
        assert "[requirement.chain]" in rendered and "[[acceptance.authority_store]]" in rendered
        if boundaries:
            assert "[[requirement.chain.boundary]]" in rendered
    return True, "complete content equal; check-spec passes with and without boundaries"


@case("G-render-acceptance-details", "acceptance details require a stack label")
def render_acceptance_details(e):
    spec, package = e.specs["paint-app"], e.packages["paint-app"]
    sp, pp = e.paths["paint-app"]
    valid = e.decisions["paint-app"]
    rejected = deepcopy(valid)
    rejected["document"]["verdict"] = "rejected"
    for decision in (None, rejected):
        rendered = AP.render_markdown(spec, package, decision, sp, pp, None, e.context())
        for text in ("stack accepted", "accepted by ", "declared binding:", "Each element was accepted"):
            assert text not in rendered, rendered
    make_gap(e)
    rendered = AP.render_markdown(spec, package, e.decisions["paint-app"], sp, pp, None, e.context())
    assert "chain policy satisfied" in rendered, rendered
    for text in ("stack accepted", "accepted by ", "declared binding:", "Each element was accepted"):
        assert text not in rendered, rendered
    return True, "no decision, rejected decision and gap output omit acceptance details"


def run(only=None):
    cases = Cases()
    for name, fn in TESTS.items():
        if only and name != only:
            continue
        with TemporaryDirectory() as td:
            estate = None
            try:
                estate = Estate(Path(td))
                result = fn(estate)
                if isinstance(result, tuple):
                    ok, message = result
                else:
                    ok, message = REASONS[name] in result, result
                cases.check(name + ": " + REASONS[name], ok, message)
            except Exception as exc:
                cases.check(name + ": " + REASONS[name], False, f"{type(exc).__name__}: {exc}" if isinstance(exc, AssertionError) else traceback.format_exc())
            finally:
                if estate:
                    estate.close()
    if not only or only == "cycle":
        state = C.budget(C.CEILINGS)
        def injected_resolver(digest):
            state.enter(digest)
            try:
                injected_resolver(digest)
            finally:
                state.active.pop()
        try:
            injected_resolver("injected-hash")
            cases.check("cycle: active-path cycle", False)
        except C.Failure as exc:
            cases.check("cycle: active-path cycle", exc.status == "indeterminate" and exc.reason == "active-path cycle", str(exc))
    return cases.items


if __name__ == "__main__":
    results = run(sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == "--case" else None)
    for name, ok, message in results:
        print(f"SELFTEST {'PASS' if ok else 'FAIL'}: {name}" + (f" — {message}" if not ok else ""))
    failures = sum(not ok for _, ok, _ in results)
    print(f"chain fixtures: {len(results)} cases, {failures} failures")
    raise SystemExit(bool(failures))
