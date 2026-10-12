"""Checked stacking for acceptance-protocol/1. Stdlib only; no acceptance-result cache.

Format shape and identity remain owned by check_core. Stores are read exactly once by
an Invocation; all recursive checks share that view and the active-path budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import datetime as dt
import json
import os
import re
import subprocess
import tomllib

import check_core as core
import hashdomains

CEILINGS = {"max_depth": 8, "max_evaluations": 10000}
FIELDS = {"relations", "depth", "level", "completeness", "binds", "acceptors",
          "allow_conditions", "unaccepted", "max_elements", "boundary"}


class Failure(Exception):
    def __init__(self, reason, status="error", *, unconfigured_store=False):
        self.reason, self.status = reason, status
        self.unconfigured_store = unconfigured_store
        super().__init__(reason)


def require(condition, reason, status="error", *, unconfigured_store=False):
    if not condition:
        raise Failure(reason, status, unconfigured_store=unconfigured_store)


def identity(value):
    return {k: value[k] for k in ("commit", "path", "digest") if k in value}


def equal(a, b):
    if "commit" in a or "commit" in b:
        return core.b1_git_revision_equal(a, b)
    return a.get("digest") is not None and a.get("digest") == b.get("digest")


def timestamp(value):
    try:
        require(isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})", value), "invalid issued_at")
        parsed = dt.datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "issued_at requires timezone")
        return parsed
    except (ValueError, TypeError, AttributeError):
        raise Failure("invalid issued_at") from None


def bindings(rep, profile):
    # The format registry is the sole source of relation tokens.
    _, parts = core.parse_profile(rep, {"format": {"profile": profile}})
    return core.load_bindings(rep, parts) if parts else []


def format_report(path, root=None):
    rep = core.Reporter(str(path))
    rep.context = core.Context(Path(path), root, strict=False)
    rep.unknowns, rep.notes = [], []
    return rep


def relations(profile):
    rep = format_report(Path("acceptance.toml"))
    return core.registered_relations(bindings(rep, profile))


def check_requirement(rep, ctx, req):
    rule = req.get("chain")
    if not isinstance(rule, dict):
        rep.error(f"{ctx}: [requirement.chain] required")
        return
    for key in ("evidence", "demands", "over"):
        if key in req:
            rep.error(f"{ctx}: chain forbids {key}")
    extra = set(rule) - FIELDS
    if extra:
        rep.error(f"{ctx}: reserved or unknown chain fields: {sorted(extra)}")
    for key, allowed in (("depth", {"direct", "all"}), ("level", {"C0", "C1", "C2", "C3"}),
                         ("completeness", {"declared", "verified"}), ("binds", {"consumed"}),
                         ("unaccepted", {"gap", "refuse"})):
        if not isinstance(rule.get(key), str) or rule[key] not in allowed:
            rep.error(f"{ctx}: chain.{key} must be one of {sorted(allowed)}")
    for key in ("relations",):
        val = rule.get(key)
        if not isinstance(val, list) or not val or not all(isinstance(x, str) for x in val) or len(set(val)) != len(val):
            rep.error(f"{ctx}: chain.{key} requires distinct nonempty strings")
    if type(rule.get("allow_conditions")) is not bool:
        rep.error(f"{ctx}: chain.allow_conditions requires a boolean")
    if type(rule.get("max_elements")) is not int or rule["max_elements"] < 0:
        rep.error(f"{ctx}: chain.max_elements requires a nonnegative integer")
    acceptors = rule.get("acceptors")
    if rule.get("level") == "C2":
        if not isinstance(acceptors, list) or not acceptors or not all(isinstance(x, str) and x for x in acceptors):
            rep.error(f"{ctx}: C2 requires acceptors")
    elif "acceptors" in rule:
        rep.error(f"{ctx}: acceptors permitted only for C2")
    boundary = rule.get("boundary", [])
    if not isinstance(boundary, list):
        rep.error(f"{ctx}: boundary requires an array of tables")
        return
    for row in boundary:
        if not isinstance(row, dict) or set(row) != {"identity", "reason"} or not isinstance(row.get("reason"), str) or not row["reason"]:
            rep.error(f"{ctx}: boundary requires identity and reason")
            continue
        ident = row.get("identity")
        valid = isinstance(ident, dict) and (set(ident) <= {"commit", "path"} and isinstance(ident.get("commit"), str) and bool(core.COMMIT_RE.fullmatch(ident["commit"])) or set(ident) == {"digest"} and core._wire(ident.get("digest"), "subject:"))
        if not valid or "path" in ident and not core._valid_b1_path(ident["path"]):
            rep.error(f"{ctx}: boundary identity violates B1 path/identity grammar")
    if rule.get("unaccepted") == "gap" and isinstance(req.get("statement"), str) and re.search(r"\baccept", req["statement"], re.I):
        rep.warn(f"NOTE {ctx}: accept… statement promises more than gap mode delivers")


def check_specification(rep, spec):
    acceptance = spec.get("acceptance")
    acceptance = acceptance if isinstance(acceptance, dict) else {}
    stores = acceptance.get("authority_store", [])
    if not isinstance(stores, list):
        rep.error("authority_store must be an array of tables")
        stores = []
    by_id = {}
    for row in stores:
        if not isinstance(row, dict):
            rep.error("authority_store must be a table")
            continue
        sid = row.get("id")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", sid) or sid in by_id:
            rep.error("authority_store id invalid or duplicate")
        else:
            by_id[sid] = row
        if row.get("kind") != "dir" or set(row) - {"id", "kind", "issuers"}:
            rep.error("authority_store kind/fields reserved; only dir is supported")
        issuers = row.get("issuers")
        if not isinstance(issuers, list) or not issuers or not all(isinstance(x, str) and x for x in issuers):
            rep.error("authority_store issuers requires nonempty strings")
    subject = spec.get("subject")
    subject = subject if isinstance(subject, dict) else {}
    profile = subject.get("profile", "acceptance/verification")
    tokens = relations(profile)
    requirements = spec.get("requirement")
    for req in requirements if isinstance(requirements, list) else []:
        if not isinstance(req, dict) or req.get("kind") != "chain":
            continue
        rule = req.get("chain")
        if not isinstance(rule, dict):
            continue
        if isinstance(rule.get("relations"), list):
            for token in rule["relations"]:
                if not isinstance(token, str) or token not in tokens:
                    rep.error(f"chain relation {token!r} is not registered")
        if rule.get("level") == "C2":
            if isinstance(spec.get("parties"), dict) and spec["parties"].get("boundary") == "cross-org":
                rep.error("cross-org C2 is forbidden in acceptance-protocol/1")
            for sid in rule.get("acceptors", []) if isinstance(rule.get("acceptors"), list) else []:
                if not isinstance(sid, str) or sid not in by_id:
                    rep.error(f"C2 acceptor {sid!r} is not a declared authority_store")


def tightening(rep, rid, new, old, new_spec, old_spec, relaxed):
    if old.get("kind") != "chain" or new.get("kind") != "chain" or relaxed:
        return
    a, b = old.get("chain", {}), new.get("chain", {})
    weaker = []
    for key, ordered in (("depth", ["direct", "all"]), ("completeness", ["declared", "verified"]),
                         ("allow_conditions", [True, False]), ("unaccepted", ["gap", "refuse"])):
        if a.get(key) in ordered and b.get(key) in ordered and ordered.index(b[key]) < ordered.index(a[key]):
            weaker.append(key)
    levels = {"C0": {"C0", "C1", "C2", "C3"}, "C1": {"C1", "C2", "C3"}, "C2": {"C2"}, "C3": {"C3"}}
    if b.get("level") not in levels.get(a.get("level"), set()):
        weaker.append("level")
    if not set(a.get("relations", [])) <= set(b.get("relations", [])):
        weaker.append("relations")
    if any(not any(equal(x.get("identity", {}), y.get("identity", {})) for y in a.get("boundary", [])) for x in b.get("boundary", [])):
        weaker.append("boundary")
    old_stores = {s["id"]: s for s in old_spec.get("acceptance", {}).get("authority_store", []) if isinstance(s, dict) and isinstance(s.get("id"), str)}
    new_stores = {s["id"]: s for s in new_spec.get("acceptance", {}).get("authority_store", []) if isinstance(s, dict) and isinstance(s.get("id"), str)}
    for sid in b.get("acceptors", []):
        before, after = old_stores.get(sid, {}), new_stores.get(sid, {})
        if sid not in a.get("acceptors", []) or before.get("kind") != after.get("kind") or not set(after.get("issuers", [])) <= set(before.get("issuers", [])):
            weaker.append("acceptors declared store definition")
    for key in weaker:
        rep.error(f"requirement {rid!r}: chain {key} weakened without relaxed")



def claim_sources(claim):
    """Explicit source citations, plus file-shaped item locators (symbol suffix removed)."""
    require(isinstance(claim, dict), "malformed claim")
    pointers = []
    source = claim.get("source")
    if isinstance(source, str):
        pointers.append(source)
    elif isinstance(source, dict) and isinstance(source.get("path"), str):
        pointers.append(source["path"])
    item = claim.get("item", "")
    if isinstance(item, str):
        item = item.split("::", 1)[0]
        if core._valid_b1_path(item) and ("/" in item or Path(item).suffix):
            pointers.append(item)
    return pointers


def contained(base, value, root):
    path = (base / value).resolve()
    require(path.is_relative_to(root.resolve()), f"input/locator outside tree: {value}")
    return path


def cargo_reader(inv, package, path, root, inputs):
    """Read only pinned virtual-workspace inputs; derive closure and member identity join."""
    rows = [d for d in package.get("dependency", []) if d["inventory"] == inv["id"]]
    require(inv["covers"] == ["runtime"] and all(row["relation"] == "runtime" for row in rows), "reader: lockfile rows carry relation 'runtime' only")
    lock_rows = [r for r in inv["input"] if r["role"] == "lockfile"]
    lock_path = contained(path.parent, lock_rows[0]["path"], root)
    require(lock_path.name == "Cargo.lock", "reader: input is not workspace Cargo.lock")
    workspace_path = lock_path.parent / "Cargo.toml"
    supplied = {contained(path.parent, r["path"], root): r["role"] for r in inv["input"]}
    require(supplied.get(workspace_path) == "workspace-manifest", "reader: missing workspace input")
    def read(p):
        require(p in inputs, f"reader: missing input {p.name}")
        try:
            return tomllib.loads(inputs[p].decode("utf-8"))
        except (ValueError, UnicodeError):
            raise Failure(f"reader: unparsable input {p.name}") from None
    lock, workspace = read(lock_path), read(workspace_path)
    require(lock.get("version") in (3, 4) and inv["reader"] == f'cargo-lock/{lock.get("version")}', "reader: lockfile version does not match reader")
    require("workspace" in workspace and "package" not in workspace, "reader: virtual workspace required; package forbidden")
    ws = workspace["workspace"]
    require(isinstance(ws, dict) and "exclude" not in ws, "reader: workspace exclude unsupported")
    members = ws.get("members")
    require(isinstance(members, list) and all(core._valid_b1_path(m) for m in members), "reader: unsupported workspace members (literal repository-relative paths required)")
    require(len(members) == len(set(members)), "reader: duplicate workspace member")
    expected = {lock_path: "lockfile", workspace_path: "workspace-manifest"}
    member_by_key, manifests = {}, {}
    for member in members:
        member_path = contained(workspace_path.parent, member, root)
        manifest_path = member_path / "Cargo.toml"
        expected[manifest_path] = "member-manifest"
        manifest = read(manifest_path)
        pkg = manifest.get("package", {})
        require("workspace" not in pkg, "reader: package.workspace unsupported")
        require(all(isinstance(pkg.get(k), str) and pkg[k] for k in ("name", "version")), "reader: literal package name/version required (version.workspace unsupported)")
        require("target" not in manifest, "reader: target dependency tables unsupported")
        key = f'{pkg["name"]} {pkg["version"]}'
        require(key not in member_by_key, "reader: duplicate member key")
        member_by_key[key] = member_path.relative_to(root).as_posix()
        manifests[key] = manifest
        for table in ("dependencies", "dev-dependencies", "build-dependencies"):
            deps = manifest.get(table, {})
            require(isinstance(deps, dict), "reader: malformed dependency table")
            for name, entry in deps.items():
                require(isinstance(entry, (str, dict)), f"reader: malformed dependency {name}")
                if isinstance(entry, dict):
                    require("package" not in entry, "reader: renamed dependency unsupported")
                    require("workspace" not in entry, "reader: workspace dependency unsupported")
    require(supplied == expected and len(inv["input"]) == len(expected), "reader: missing or extra input row")
    packages = lock.get("package", [])
    require(isinstance(packages, list), "reader: malformed lock packages")
    by_key = {}
    for pkg in packages:
        require(isinstance(pkg, dict) and all(isinstance(pkg.get(k), str) for k in ("name", "version")), "reader: malformed lock key")
        key = f'{pkg["name"]} {pkg["version"]}'
        require(key not in by_key, f"reader: duplicate canonical key {key}")
        by_key[key] = pkg
    require(set(member_by_key) == {k for k, p in by_key.items() if "source" not in p}, "reader: member/lock key bijection mismatch")
    edges = {}
    for key, pkg in by_key.items():
        edges[key] = []
        require(isinstance(pkg.get("dependencies", []), list), "reader: malformed lock dependencies")
        for ref in pkg.get("dependencies", []):
            require(isinstance(ref, str), "reader: malformed lock reference")
            matched = [k for k, p in by_key.items() if ref in (p["name"], k, f'{k} ({p.get("source")})')]
            require(len(matched) == 1, f"reader: ambiguous or unresolved reference {ref}")
            edges[key].append(matched[0])
    subject = package.get("subject", {})
    require(core._valid_b1_path(subject.get("path")), "reader: subject.path required")
    starts = [k for k, p in member_by_key.items() if p == subject["path"]]
    require(len(starts) == 1, "reader: subject.path does not match member holding subject key")
    start = starts[0]
    closure, pending = set(), list(edges[start])
    while pending:
        key = pending.pop()
        if key == start or key in closure:
            continue
        closure.add(key)
        pending.extend(edges[key])
    for key in closure | {start}:
        if key not in manifests:
            continue
        manifest_edges = {}
        for table in ("dependencies", "dev-dependencies", "build-dependencies"):
            for name, entry in manifests[key].get(table, {}).items():
                manifest_edges.setdefault(name, []).append(entry)
        lock_names = {by_key[k]["name"] for k in edges[key]}
        require(set(manifest_edges) == lock_names, f"reader: manifest-lock edge mismatch {key}: {sorted(set(manifest_edges) ^ lock_names)}")
        for target in edges[key]:
            name = by_key[target]["name"]
            for entry in manifest_edges[name]:
                if isinstance(entry, dict) and "path" in entry:
                    require(isinstance(entry["path"], str), f"reader: invalid path target {key} -> {name}")
                    resolved = contained(root / member_by_key[key], entry["path"], root)
                    require(target in member_by_key and resolved == root / member_by_key[target], f"reader: path target mismatch {key} -> {name}")
                else:
                    require("source" in by_key[target], f"reader: non-path target lacks source {key} -> {name}")
    require(not any(r.get("lock", {}).get("entry") in closure and "source" in by_key[r["lock"]["entry"]] for r in package.get("dependency", []) if r.get("inventory") == inv["id"]), "reader: declaration claims external source package")
    require(not any("source" in by_key[k] for k in closure), "reader: needs delivered identities (0.4.x)", "indeterminate")
    rows = [d for d in package.get("dependency", []) if d["inventory"] == inv["id"]]
    for row in rows:
        key = row["lock"]["entry"]
        if key in closure:
            require(core.b1_git_revision_equal(row["source"], {"commit": subject.get("commit"), "path": member_by_key[key]}), f"identity join: source.commit/path mismatch for {row['id']}", "refused")
            require(row["role"] == ("direct" if key in edges[start] else "transitive"), f"identity join: role mismatch for {row['id']}", "refused")
    keys = [r["lock"]["entry"] for r in rows]
    require(not (closure - set(keys)), f"completeness: missing row {sorted(closure - set(keys))}", "refused")
    require(not (set(keys) - closure) and len(keys) == len(set(keys)), "completeness: extra row", "refused")
    return {"completeness": "verified", "role_verified": True}


def inventories(package, path, root, readers, checkout=None):
    require(root is not None or not any(i.get("source") == "lockfile" for i in package.get("dependency_inventory", []) if isinstance(i, dict)), "input digests: reader input root unresolved")
    root = root or path.parent.resolve()
    rep = format_report(path, root)
    loaded = bindings(rep, package.get("format", {}).get("profile"))
    core.check_dependency_declaration(rep, package, loaded)
    # B22 checks digest mismatches too; preserve the normative input-digest step label.
    shape = [e for e in rep.errors if "input digest differs" not in e]
    require(not shape, "declaration shape: " + "; ".join(shape))
    result, recorded, pending = {}, [], []
    for inv in package.get("dependency_inventory", []):
        if inv["source"] == "manual":
            result[inv["id"]] = {"completeness": "declared", "role_verified": False}
            continue
        inputs = {}
        for row in inv["input"]:
            target = contained(path.parent, row["path"], root)
            try:
                raw = target.read_bytes()
            except OSError:
                raise Failure(f"input digests: missing or unresolvable reader input {row['path']}") from None
            require(hashdomains.digest("artifact:", raw) == row["digest"], f"input digests: digest mismatch {row['path']}")
            inputs[target] = raw
            recorded.append({"inventory": inv["id"], **row})
        pending.append((inv, inputs))
    if checkout is not None:
        checkout(package, path)
    for inv, inputs in pending:
        reader = readers.get(inv["reader"])
        require(reader is not None, f"reader: unregistered reader {inv['reader']}")
        result[inv["id"]] = reader(inv, package, path, root, inputs)
    return result, recorded


def mappings(values, tree=False):
    out = {}
    pattern = r"([0-9a-f]{40})=(.+)" if tree else r"([A-Za-z0-9._-]+)=(.+)"
    for value in values or []:
        match = re.fullmatch(pattern, value)
        require(match is not None, "invalid --tree/--store mapping")
        key, path = match.groups()
        require(key not in out, "duplicate --tree/--store mapping")
        out[key] = Path(path).resolve()
    return out


@dataclass
class Budget:
    limits: dict
    active: list = field(default_factory=list)
    visits: int = 0
    scopes: list = field(default_factory=list)

    def visit(self):
        self.visits += 1
        require(self.visits <= self.limits["max_evaluations"] and all(self.visits - start <= limits["max_evaluations"] for limits, start, _ in self.scopes), "budget max_evaluations exceeded", "indeterminate")

    def enter(self, digest):
        require(digest not in self.active, "active-path cycle", "indeterminate")
        require(len(self.active) < self.limits["max_depth"] and all(len(self.active) - depth < limits["max_depth"] for limits, _, depth in self.scopes), "budget max_depth exceeded", "indeterminate")
        self.active.append(digest)


def budget(value):
    require(isinstance(value, dict) and set(value) == set(CEILINGS), "recorded budget malformed")
    require(all(type(value[k]) is int and 0 < value[k] <= CEILINGS[k] for k in CEILINGS), "recorded budget above ceiling or invalid")
    return Budget(dict(value))


class Invocation:
    def __init__(self, api, stores=None, trees=None, root=None, effect=None, previous_paths=None, previous_dir=None):
        self.api, self.trees, self.root, self.effect = api, {key: Path(value).resolve() for key, value in (trees or {}).items()}, Path(root).resolve() if root else None, effect
        self.previous_paths, self.previous_dir = previous_paths, previous_dir
        self.stores, self.listings, self.store_errors = {}, {}, {}
        self.effect_failures = []
        self.checkout_notes = []
        for sid, path in (stores or {}).items():
            try:
                rows = []
                for p in sorted(path.iterdir()):
                    require(not p.is_symlink() and p.is_file() and p.suffix == ".toml", f"store hygiene: {sid}/{p.name} is not a regular top-level TOML file")
                    raw = p.read_bytes()
                    try:
                        doc = tomllib.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeError):
                        raise Failure(f"store hygiene: unparsable file {sid}/{p.name}") from None
                    document = doc.get("document", {})
                    require(isinstance(document, dict), "store hygiene: malformed decision document")
                    try:
                        timestamp(document.get("issued_at"))
                    except Failure:
                        raise Failure(f"store hygiene: bad issued_at {sid}/{p.name}") from None
                    bound = doc.get("binds", {})
                    require(isinstance(bound, dict) and all(isinstance(bound.get(k, {}), dict) for k in ("subject", "specification", "package")), "store hygiene: malformed decision bindings")
                    require(document.get("kind") == "decision", "store hygiene: decisions only")
                    require(re.fullmatch(r"[A-Za-z0-9._-]+", p.stem) and document.get("id") == p.stem, "store document.id does not equal file stem")
                    rows.append({"doc": doc, "hash": hashdomains.digest("decision:", raw), "path": p})
                self.stores[sid] = rows
                listing = "".join(sorted(f'{r["doc"]["document"]["id"]} {r["hash"]}\n' for r in rows))
                self.listings[sid] = hashdomains.digest("store:", listing.encode())
            except (Failure, OSError) as exc:
                self.store_errors[sid] = str(exc)

    def root_for(self, package, path):
        root = self.trees.get(package.get("subject", {}).get("commit")) or self.root or core._repository_root(path)
        return Path(root).resolve() if root is not None else None

    def store_rows(self, spec, rule):
        definitions = {r["id"]: r for r in spec.get("acceptance", {}).get("authority_store", []) if isinstance(r, dict) and isinstance(r.get("id"), str)}
        rows = []
        for sid in rule.get("acceptors", []):
            require(sid not in self.store_errors, self.store_errors.get(sid, ""))
            require(sid in self.stores, f"store not configured: {sid}", "indeterminate", unconfigured_store=True)
            require(sid in definitions, f"undeclared store: {sid}")
            rows.extend((r, definitions[sid]) for r in self.stores[sid])
        return rows

    def resolve(self, row):
        child = row["doc"]
        require(child.get("document", {}).get("protocol") != "acceptance-protocol/0", "legacy child: re-issue under acceptance-protocol/1", "refused")
        binds = child.get("binds", {})
        root = self.trees.get(binds.get("subject", {}).get("commit"))
        require(root is not None, "child tree not configured", "indeterminate")
        docs, paths = [], []
        for key in ("specification", "package"):
            locator = binds.get(key, {}).get("path")
            require(core._valid_b1_path(locator), f"child {key} locator violates B1 path grammar")
            p = contained(root, locator, root)
            doc, error = self.api.load_toml(p)
            require(not error, f"child {key} does not resolve: {locator}", "indeterminate")
            docs.append(doc)
            paths.append(p)
        spec, package = docs
        require(spec.get("document", {}).get("protocol") == "acceptance-protocol/1" and "contract" not in package and "specification" in package,
                "legacy child: re-issue under acceptance-protocol/1", "refused")
        expected = root / binds["subject"].get("path", "") / "acceptance" / binds["specification"].get("id", "")
        require(paths == [expected / "acceptance-specification.toml", expected / "acceptance.toml"], "edge package locator must name subject/acceptance/specification-id", "refused")
        return spec, package, *paths

    def superseded(self, candidate, definition, rows, at):
        c = candidate["doc"]
        cb = c.get("binds", {})
        start = timestamp(c["document"]["issued_at"])
        for row, _ in rows:
            s = row["doc"]
            sb = s.get("binds", {})
            if s.get("document", {}).get("issuer") not in definition["issuers"] or not equal(sb.get("subject", {}), cb.get("subject", {})) or sb.get("specification", {}).get("id") != cb.get("specification", {}).get("id"):
                continue
            later = timestamp(s["document"].get("issued_at"))
            if start < later <= at:
                return True
        return False

    def candidate(self, row, definition, rows, dep, rule, at, state):
        state.visit()
        child = row["doc"]
        require(child.get("document", {}).get("issuer") in definition["issuers"], "issuer not in issuers", "refused")
        require(equal(child.get("binds", {}).get("subject", {}), dep["source"]), "child identity mismatch", "refused")
        state.enter(row["hash"])
        try:
            spec, package, sp, pp = self.resolve(row)
            root = self.trees[child["binds"]["subject"]["commit"]]
            for claim in package.get("claim", []):
                require(isinstance(claim, dict), "malformed child claim")
                digested = set()
                for ev in self.api.evidence_list(claim):
                    for item in ev.get("build_inputs", []):
                        require(isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("digest"), str), "malformed child build input")
                        target = contained(pp.parent, item["path"], root)
                        require(target.is_file(), "child build input does not resolve", "indeterminate")
                        require(hashdomains.digest("artifact:", target.read_bytes()) == item["digest"], "child build input digest mismatch", "refused")
                        digested.add(target)
                for pointer in claim_sources(claim):
                    source_path = contained(pp.parent, pointer, root)
                    require(source_path.is_file(), "child claim source does not resolve", "indeterminate")
                    require(source_path in digested, "edge package must digest claim source files", "refused")
            previous_root = self.api._ROOT_OVERRIDE
            self.api._ROOT_OVERRIDE = root
            try:
                rep = self.api.check_decision(child, spec, package, sp, pp, decision_path=row["path"], chain_context=self, chain_budget=state, previous_dir=self.previous_dir)
            finally:
                self.api._ROOT_OVERRIDE = previous_root
            require(not rep.errors, "child check-decision: " + "; ".join(rep.errors), "refused")
            require(not rep.unknowns, "child check-decision: " + "; ".join(rep.unknowns), "indeterminate")
            require(timestamp(child["document"]["issued_at"]) <= at, "child future-issued at T", "refused")
            eligible, reason = self.api.check_decision_effect(child, spec, rep, at.date().isoformat(), rule["allow_conditions"], chain_effect=False)
            require(eligible, "child ineligible at T: " + reason, "refused")
            require(not self.superseded(row, definition, rows, at), "child superseded at T", "refused")
            if self.effect is not None:
                d = timestamp(self.effect + "T23:59:59Z")
                eligible, reason = self.api.check_decision_effect(child, spec, rep, self.effect, rule["allow_conditions"], chain_effect=False)
                if not eligible:
                    self.effect_failures.append(f"{row['path']}: child ineligible at D: " + reason)
                if self.superseded(row, definition, rows, d):
                    self.effect_failures.append(f"{row['path']}: child superseded at D")
            pin = {"id": child["document"]["id"], "hash": row["hash"], "issuer": child["document"]["issuer"]}
            if "stale_after" in child.get("validity", {}):
                pin["stale_after"] = child["validity"]["stale_after"]
            return pin
        finally:
            state.active.pop()

    def select(self, spec, rule, dep, at, state, pin=None, gap=False):
        rows = self.store_rows(spec, rule)
        if pin is not None:
            matches = [(r, d) for r, d in rows if r["hash"] == pin.get("hash")]
            require(matches, "pinned child not found", "refused")
        else:
            matches = [(r, d) for r, d in rows if equal(r["doc"].get("binds", {}).get("subject", {}), dep["source"])]
        successes, failures = [], []
        for row, definition in matches:
            if gap and timestamp(row["doc"]["document"]["issued_at"]) > at:
                continue
            effect_start = len(self.effect_failures)
            try:
                witness = self.candidate(row, definition, rows, dep, rule, at, state)
                if pin is not None:
                    require(witness == pin, "pinned child metadata differs", "refused")
                successes.append((row, witness, self.effect_failures[effect_start:]))
            except Failure as exc:
                failures.append((exc.status, f'{row["path"]}: {exc.reason}'))
            except Exception as exc:
                failure = Failure(f"candidate {row['path']}: {type(exc).__name__}: {exc}", "error")
                failures.append((failure.status, failure.reason))
            finally:
                del self.effect_failures[effect_start:]
        # A gap must remain determinate even when another candidate qualifies.
        if gap and any(s == "error" for s, _ in failures):
            raise Failure("gap replay error: " + "; ".join(r for _, r in failures))
        if gap and any(s == "indeterminate" for s, _ in failures):
            raise Failure("gap replay indeterminate: " + "; ".join(r for _, r in failures), "indeterminate")
        if successes:
            successes.sort(key=lambda pair: pair[0]["hash"])
            successes.sort(key=lambda pair: timestamp(pair[0]["doc"]["document"]["issued_at"]), reverse=True)
            self.effect_failures.extend(successes[0][2])
            return successes[0][1]
        for row, _ in rows:
            bs = row["doc"].get("binds", {}).get("subject", {})
            if bs.get("commit") == dep["source"].get("commit") and not equal(bs, dep["source"]):
                failures.append(("refused", f'{row["doc"]["document"]["id"]}: whole-tree / other-subtree near miss'))
        status = "error" if any(s == "error" for s, _ in failures) else "indeterminate" if any(s == "indeterminate" for s, _ in failures) else "refused"
        raise Failure("no decision qualifies" + (": " + "; ".join(r for _, r in failures) if failures else ""), status)

    def listing_notes(self, decision):
        recorded = {r.get("id"): r.get("listing") for r in decision.get("chain_evaluation", {}).get("stores", []) if isinstance(r, dict)}
        notes = [f"INFO {sid}: store view differs from recorded listing; current {value}"
                 for sid, value in sorted(self.listings.items()) if recorded.get(sid) != value]
        if self.effect is not None:
            notes.extend(f"INFO current store listing {sid}: {value}" for sid, value in sorted(self.listings.items()))
        return notes

    def checkout(self, package, path):
        root = self.trees.get(package.get("subject", {}).get("commit"))
        if root is None:
            return
        root = Path(root).resolve()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PRE_COMMIT", "SKIP"))}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_NO_REPLACE_OBJECTS="1", LC_ALL="C")
        def git(*args):
            try:
                return subprocess.run(["git", "--no-replace-objects", "--literal-pathspecs", "-C", str(root),
                                       "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", *args],
                                      env=env, capture_output=True, text=True)
            except OSError:
                raise Failure("tree checkout: git unavailable") from None
        probe = git("rev-parse", "--show-toplevel")
        if probe.returncode:
            first_line = probe.stderr.splitlines()[0] if probe.stderr else "no diagnostic"
            outside = first_line.startswith("fatal: not a git repository (or any of the parent directories):")
            # Git can report 'not a repository' for a corrupt .git directory too.
            for parent in (root, *root.parents):
                try:
                    (parent / ".git").lstat()
                except FileNotFoundError:
                    continue
                except OSError:
                    pass
                outside = False
                break
            if outside:
                note = "NOTE tree is not a git checkout; recorded digests checked"
                if note not in self.checkout_notes:
                    self.checkout_notes.append(note)
                return
            raise Failure("tree checkout: probe failed: " + first_line)
        require(Path(probe.stdout.strip()).resolve() == root, "--tree must name repository top directory")
        commit = package["subject"]["commit"]
        commit_probe = git("cat-file", "-e", commit + "^{commit}")
        if commit_probe.returncode:
            # Match the entire C-locale diagnostic: corruption can add errors before
            # the same final line and must never be mistaken for an absent object.
            if (commit_probe.returncode == 128
                    and commit_probe.stderr.strip() == f"fatal: Not a valid object name {commit}^{{commit}}"):
                note = f"NOTE tree checkout: commit {commit[:12]} not present in this repository; recorded digests checked"
                if note not in self.checkout_notes:
                    self.checkout_notes.append(note)
                return
            diagnostic = commit_probe.stderr.splitlines()[0] if commit_probe.stderr else "no diagnostic"
            raise Failure("tree checkout: probe failed: " + diagnostic)
        pointers = []
        for inv in package.get("dependency_inventory", []):
            for item in inv.get("input", []):
                require(isinstance(item, dict) and isinstance(item.get("path"), str), "tree checkout: malformed input path")
                pointers.append(item["path"])
        for claim in package.get("claim", []):
            pointers.extend(claim_sources(claim))
            for ev in self.api.evidence_list(claim):
                for item in ev.get("build_inputs", []):
                    require(isinstance(item, dict) and isinstance(item.get("path"), str), "tree checkout: malformed build input path")
                    pointers.append(item["path"])
        files = sorted({contained(path.parent, p, root).relative_to(root).as_posix() for p in pointers})
        for file in files:
            committed = git("rev-parse", package["subject"]["commit"] + ":" + file)
            require(committed.returncode == 0, "tree checkout: input absent from commit")
            presented = git("hash-object", "--no-filters", "--", file)
            require(presented.returncode == 0 and presented.stdout.strip() == committed.stdout.strip(), "tree checkout: presented input differs from commit")

    def evaluate(self, spec, package, path, at, decision=None, state=None):
        limits = decision.get("chain_evaluation", {}).get("budget") if decision is not None else CEILINGS
        if state is None:
            try:
                state = budget(limits)
            except Failure:
                return self._evaluate(spec, package, path, at, decision, None)
        start = len(state.scopes)
        try:
            try:
                local = budget(limits)
                state.scopes.append((local.limits, state.visits, len(state.active)))
            except Failure:
                pass  # _evaluate reports malformed snapshots in the ordinary result channel.
            return self._evaluate(spec, package, path, at, decision, state)
        finally:
            del state.scopes[start:]

    def _evaluate(self, spec, package, path, at, decision=None, state=None):
        reqs = [r for r in spec.get("requirement", []) if r.get("kind") == "chain"]
        if not reqs:
            return {}, None, [], [], []
        errors, unknowns, rows, coverage = [], [], [], {}
        evaluation = decision.get("chain_evaluation", {}) if decision is not None else {}
        limits = evaluation.get("budget") if decision is not None else CEILINGS
        try:
            validated = budget(limits)
            if state is None:
                state = validated
            when = timestamp(at)
            require(set(evaluation) <= {"at", "budget", "inputs", "stores"}, "reserved chain_evaluation field")
            require(decision is None or evaluation.get("at") == at, "chain_evaluation.at differs from issued_at")
            root = self.root_for(package, path)
            if root is None and not any(i.get("source") == "lockfile" for i in package.get("dependency_inventory", [])):
                root = path.parent.resolve()
            require(root is not None, "reader: repository root unresolved")
            invs, inputs = inventories(package, path, root, self.api._profiles.CHAIN_READERS.get("/".join(package.get("format", {}).get("profile", "").split("/")[2:]), {}), checkout=self.checkout)
            if decision is not None:
                require(evaluation.get("inputs") == inputs, "recorded reader input digests differ")
            snapshot = {"at": at, "budget": dict(limits), "inputs": inputs,
                        "stores": [{"id": sid, "listing": value} for sid, value in sorted(self.listings.items())]}
        except Failure as exc:
            (unknowns if exc.status == "indeterminate" else errors).append(exc.reason)
            for req in reqs:
                coverage[req["id"]] = {"status": "partial", "basis": [], "reasons": {"_chain": exc.reason}, "mandatory": req.get("mandatory", False)}
            return coverage, None, [], errors, unknowns
        recorded = decision.get("chain_element", []) if decision is not None else []
        if not isinstance(recorded, list) or not all(isinstance(r, dict) for r in recorded):
            errors.append("chain_element must be an array of tables")
            recorded = []
        expected_keys = []
        for req in reqs:
            rule, rid = req["chain"], req["id"]
            reasons, selected, element_failures = {}, [], {}
            for dep in sorted(package.get("dependency", []), key=lambda d: d["id"]):
                if dep["relation"] in rule["relations"] and not (rule["depth"] == "direct" and invs[dep["inventory"]]["role_verified"] and dep["role"] != "direct"):
                    selected.append(dep)
            if not selected and rule["level"] in ("C1", "C3"):
                reasons["_level"] = "C1/C3 reserved"
            for relation in rule["relations"]:
                covering = [i for i in package.get("dependency_inventory", []) if relation in i["covers"] and (rule["completeness"] == "declared" or invs[i["id"]]["completeness"] == "verified")]
                if not covering:
                    reasons[relation] = "relation has no covering inventory meeting completeness"
            if len(selected) > rule["max_elements"]:
                reasons["_limit"] = "max_elements exceeded"
            for dep in selected:
                row = {"requirement": rid, "dependency": dep["id"], "relation": dep["relation"], "level": rule["level"], "identity": identity(dep["source"])}
                expected_keys.append((rid, dep["id"]))
                old = None
                try:
                    require(not equal(dep["source"], package["subject"]), "self-edge", "indeterminate")
                    old = None
                    if decision is not None:
                        matches = [r for r in recorded if r.get("requirement") == rid and r.get("dependency") == dep["id"]]
                        require(len(matches) == 1, "snapshot missing/duplicate element")
                        old = matches[0]
                        require(all(old.get(k) == v for k, v in row.items()), "snapshot element identity/declaration differs")
                        require(old.get("status") in {"satisfied", "boundary", "gap", "refused", "indeterminate"}, "invalid snapshot status")
                        require("act" not in old, "snapshot act reserved")
                        require(set(old) <= {"requirement", "dependency", "relation", "level", "identity", "status", "reason", "decision"}, "snapshot unknown row key")
                    boundary = any(equal(dep["source"], b["identity"]) for b in rule.get("boundary", []))
                    if boundary:
                        row.update(status="boundary", reason="declared boundary")
                    elif rule["level"] in ("C1", "C3"):
                        raise Failure("C1/C3 reserved", "indeterminate")
                    elif old is not None and old["status"] in ("refused", "indeterminate"):
                        require("decision" not in old, "non-witness row carries pin")
                        row.update(status=old["status"], reason=old.get("reason", "recorded non-witness"))
                    elif old is not None and old["status"] == "gap":
                        require(rule["unaccepted"] == "gap", "gap under unaccepted=refuse")
                        require("decision" not in old, "non-witness row carries pin")
                        try:
                            if rule["level"] == "C2":
                                self.select(spec, rule, dep, when, state, gap=True)
                        except Failure as exc:
                            if exc.status != "refused":
                                raise
                        row.update(status="gap", reason="recorded determinate gap")
                    elif rule["level"] == "C0":
                        row.update(status="satisfied", reason="disclosed identity")
                    else:
                        pin = old.get("decision") if old else None
                        require(old is None or isinstance(pin, dict), "satisfied C2 row missing pin")
                        witness = self.select(spec, rule, dep, when, state, pin=pin)
                        row.update(status="satisfied", reason="accepted witness", decision=witness)
                    if old is not None:
                        require(old["status"] == row["status"], "snapshot status differs")
                        require(("decision" in old) == ("decision" in row), "snapshot unexpected pin")
                except Failure as exc:
                    status = "gap" if exc.status == "refused" and rule["unaccepted"] == "gap" and decision is None else exc.status
                    row.update(status="refused" if status == "error" else status, reason=exc.reason)
                    element_failures[dep["id"]] = {"unconfigured_store": exc.unconfigured_store}
                    if exc.status == "error":
                        errors.append(f"{rid}/{dep['id']}: {exc.reason}")
                    if decision is not None:
                        (unknowns if exc.status == "indeterminate" else errors).append(f"{rid}/{dep['id']}: {exc.reason}")
                rows.append(row)
                if row["status"] not in ("satisfied", "boundary", "gap"):
                    reasons[dep["id"]] = row["reason"]
            status = "satisfied" if not reasons else "deviation-declared" if any(d.get("requirement") == rid for d in package.get("deviation", [])) else "partial"
            coverage[rid] = {"status": status, "basis": [], "reasons": reasons, "element_failures": element_failures, "mandatory": req.get("mandatory", False)}
        if decision is not None:
            if sorted((r.get("requirement", ""), r.get("dependency", "")) for r in recorded) != sorted(expected_keys):
                errors.append("snapshot row set differs from declaration")
            for disp in decision.get("disposition", []):
                rid = disp.get("requirement")
                if rid not in coverage:
                    continue
                if "basis" in disp:
                    errors.append("basis forbidden on chain disposition")
                for field, status in (("chain_basis", "satisfied"), ("chain_boundary", "boundary"), ("chain_gaps", "gap")):
                    want = sorted(r["dependency"] for r in recorded if r.get("requirement") == rid and r.get("status") == status)
                    got = disp.get(field)
                    if not isinstance(got, list) or not all(isinstance(x, str) for x in got) or sorted(got) != want:
                        errors.append(f"{rid}: {field} differs from snapshot row set")
            dep_ids = {d["id"] for d in package.get("dependency", [])}
            if any(r.get("claim") in dep_ids for r in decision.get("verification", {}).get("run", [])):
                errors.append("verification.run names dependency id")
        return coverage, snapshot, rows, errors, unknowns


def merge_coverage(cov, result):
    requirements, snapshot, rows, errors, unknowns = result
    cov["requirements"].update(requirements)
    cov["chain"] = {"snapshot": snapshot, "rows": rows, "errors": errors, "unknowns": unknowns}
    for mandatory, prefix in ((True, "mandatory"), (False, "optional")):
        rs = [r for r in cov["requirements"].values() if bool(r["mandatory"]) == mandatory]
        cov["summary"][prefix + "_total"] = len(rs)
        cov["summary"][prefix + "_satisfied"] = sum(r["status"] == "satisfied" for r in rs)
    cov["summary"]["acceptable"] = cov["summary"]["mandatory_total"] == cov["summary"]["mandatory_satisfied"]


def snapshot_toml(snapshot, rows):
    def scalar(v):
        if isinstance(v, dict):
            return "{ " + ", ".join(f"{k} = {scalar(x)}" for k, x in v.items()) + " }"
        if isinstance(v, list):
            return "[" + ", ".join(scalar(x) for x in v) + "]"
        return json.dumps(v)
    lines = ["[chain_evaluation]"]
    lines += [f"{k} = {scalar(v)}" for k, v in snapshot.items()]
    for row in rows:
        lines.append("\n[[chain_element]]")
        lines += [f"{k} = {scalar(v)}" for k, v in row.items()]
    return "\n".join(lines) + "\n"


def render(spec, package, cov, decision=None, decision_ok=False):
    if not any(r.get("kind") == "chain" for r in spec.get("requirement", [])):
        return ""
    data = cov.get("chain", {})
    rows = data.get("rows", [])
    reqs = [r for r in spec["requirement"] if r.get("kind") == "chain"]
    tokens = relations(package.get("format", {}).get("profile"))
    lines = ["", "| Relation | Inventories / completeness | Boundary | Gaps |", "|---|---|---|---|"]
    for token in sorted(tokens | {t for r in reqs for t in r["chain"]["relations"]}):
        invs = [i for i in package.get("dependency_inventory", []) if token in i["covers"]]
        desc = ", ".join(i["id"] + " / " + ("verified" if i["source"] == "lockfile" and data.get("snapshot") else "declared" if i["source"] == "manual" else "unverified") for i in invs) or "uncovered"
        boundary = ", ".join(sorted({r["dependency"] for r in rows if r["relation"] == token and r["status"] == "boundary"}))
        gaps = ", ".join(sorted({r["dependency"] for r in rows if r["relation"] == token and r["status"] == "gap"}))
        lines.append(f"| {token} | {desc} | {boundary} | {gaps} |")
    covered = {t for r in reqs if r["chain"]["depth"] == "all" for t in r["chain"]["relations"]}
    policy_satisfied = (not data.get("errors") and not data.get("unknowns")
                        and all(cov["requirements"][r["id"]]["status"] == "satisfied" for r in reqs))
    accepted = (not data.get("errors") and not data.get("unknowns") and data.get("snapshot") is not None
                and all(cov["requirements"][r["id"]]["status"] == "satisfied" for r in reqs)
                and bool(covered) and all(r["status"] == "boundary" or r["status"] == "satisfied" and r["level"] == "C2" and "decision" in r for r in rows))
    if decision is None or not decision_ok or decision.get("document", {}).get("verdict") not in {"accepted", "accepted-with-conditions"}:
        accepted = False
    if accepted:
        lines.append("\nstack accepted over " + ", ".join(i["id"] for i in package.get("dependency_inventory", [])) + " for " + ", ".join(sorted(covered)) + " at " + decision["document"]["issued_at"])
    else:
        lines.append("\nchain policy " + ("satisfied" if policy_satisfied else "not satisfied"))
    if tokens - covered:
        lines.append("not covered (trusted as the base, not checked): " + ", ".join(sorted(tokens - covered)))
    for req in reqs:
        for b in req["chain"].get("boundary", []):
            lines.append(f"Boundary {json.dumps(b['identity'], sort_keys=True)}: {b['reason']}")
    for inv in package.get("dependency_inventory", []):
        if inv["source"] == "manual":
            lines.append(f"{inv['id']}: declared completeness.")
    if accepted:
        issuers = sorted({r["decision"]["issuer"] for r in rows if "decision" in r})
        lines.append("accepted by " + (", ".join(issuers) or "no issuers") + " under their own specifications")
        for dep in package.get("dependency", []):
            lines.append(f"{dep['id']}: declared binding: {dep.get('binding', 'not stated')}")
        lines.append("The label combines no assurance levels across the stack. Each element was accepted at its own floor; no failure bound for the whole stack follows.")
    return "\n".join(lines) + "\n"
