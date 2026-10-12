#!/usr/bin/env python3
"""acceptance_migrate.py — acceptance-protocol/0 -> /1 migration.
Pure stdlib, Python 3.11+.

    migrate SPEC_OR_PACKAGE... [--write] [--allow-decisions-pending]

Each positional path is peeked and migrated by STRUCTURE only — this tool edits the specific
protocol-layer fields the 0.3->0.4 rename touches (`[document].kind`, `[document].protocol`, the
`[contract]`/`[specification]` table header, its `hash` field, `[spec].path`), never a blanket
word-rename over the file's prose: a requirement STATEMENT that happens to use the English word
"contract" is the consumer's content, not this tool's business.

  - a `/0` SPECIFICATION (`[document].kind = "contract"`) -> `kind = "specification"`,
    `protocol = "acceptance-protocol/1"`. Under `--write`, a file named `acceptance-contract.toml`
    or `*.contract.toml` is renamed to `acceptance-specification.toml` / `*.specification.toml`;
    without `--write` this is a dry-run unified diff (plus the planned rename, printed) to stdout.
  - a `/0` PACKAGE (`[format]` present, `[contract]` table present) -> `[specification]` table
    (same `id`/`requirements_total`), `hash` recomputed over the specification bytes in the NEW
    `specification:` domain, `[spec].path` updated to match a renamed specification file. REFUSED
    (exit 2, the file is NOT written) if the package's existing `[contract].hash` does not already
    recompute over the UNMIGRATED specification bytes in the OLD `contract:` domain — migration
    never launders a pre-existing binding defect into a clean-looking new hash.
  - a DECISION is NEVER rewritten (`[document].kind = "decision"`): printed as
    `RE-ISSUE <path>: the consumer re-runs decide/make_decision under 0.4.0`. One or more decisions
    present without `--allow-decisions-pending` makes the whole run exit 3 (after processing every
    other input).
  - anything else (no `[document]` and no `[format]` table, an unrecognised `[document].kind`, or
    a package missing the `[spec].path` this tool needs to locate its bound specification) -> one
    `RESIDUAL <path>: <reason>` line; any residual makes the whole run exit 2 (checked after
    decisions, so a run with both a residual and a pending decision exits 2, not 3).

`--selftest` runs the fixtures below. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
import copy
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent.parent / "format_acceptance" / "tools"))

import hashdomains  # noqa: E402

OLD_PROTOCOL_ID = "acceptance-protocol/0"
NEW_PROTOCOL_ID = "acceptance-protocol/1"


def _old_contract_digest(data: bytes) -> str:
    """The retired `contract:` domain's wire form, inlined: `hashdomains.py`'s own `DOMAINS` set
    no longer registers it (the live system never parses `/0`), but this tool still needs it, once,
    to verify a `/0` package's EXISTING binding before migrating it — the SAME construction
    `hashdomains.digest` used before the rename (`sha512(prefix || bytes)`, self-describing wire
    form), just not routed through the now-/1-only registry check."""
    return "contract:" + "sha-512:" + hashlib.sha512(b"contract:" + data).hexdigest()

_KIND_RE = re.compile(r'(?m)^(\s*kind\s*=\s*)"contract"(\s*(?:#.*)?)$')
_PROTOCOL_RE = re.compile(r'(?m)^(\s*protocol\s*=\s*)"acceptance-protocol/0"(\s*(?:#.*)?)$')
_TABLE_HEADER_RE = re.compile(r'(?m)^\[contract\]\s*$')
_HASH_LINE_RE = re.compile(r'(?m)^(\s*hash\s*=\s*)"contract:sha-512:([0-9a-f]{128})"(\s*(?:#.*)?)$')
_SPEC_PATH_RE = re.compile(r'(?m)^(\s*path\s*=\s*)"([^"]*)"(\s*(?:#.*)?)$')


def _new_specification_name(old_name: str) -> str | None:
    """`acceptance-contract.toml` -> `acceptance-specification.toml`; any other
    `*.contract.toml` -> `*.specification.toml`. `None` if `old_name` does not match either
    shape (nothing to rename)."""
    if old_name == "acceptance-contract.toml":
        return "acceptance-specification.toml"
    if old_name.endswith(".contract.toml"):
        return old_name[: -len(".contract.toml")] + ".specification.toml"
    return None


def peek(path: Path) -> dict | None:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return None


def classify(doc: dict) -> str | None:
    """`"specification"` | `"decision"` | `"amendment"` | `"package"` | `None` (unrecognised)."""
    document = doc.get("document")
    if isinstance(document, dict):
        kind = document.get("kind")
        if kind in ("contract", "specification"):
            return "specification"
        if kind == "decision":
            return "decision"
        if kind == "amendment":
            return "amendment"
        return None
    if isinstance(doc.get("format"), dict):
        return "package"
    return None


class Residual(Exception):
    pass


class Refused(Exception):
    pass


def migrate_specification_text(text: str) -> str:
    doc = tomllib.loads(text)
    if doc.get('document', {}).get('protocol') != OLD_PROTOCOL_ID:
        raise Residual('specification is not acceptance-protocol/0')
    import acceptance_protocol as AP
    rendered = tomllib.loads(AP._render_specification_toml(doc))
    def unknown(before, after, prefix=''):
        if isinstance(before, dict):
            for key, value in before.items():
                if key not in after:
                    if value == []:  # renderer omits empty optional lists
                        continue
                    raise Residual(f'unknown or unmappable key {prefix}{key}')
                unknown(value, after[key], prefix + key + '.')
        elif isinstance(before, list) and before and isinstance(before[0], dict):
            for old, new in zip(before, after):
                unknown(old, new, prefix)
    unknown(doc, rendered)
    expected = copy.deepcopy(doc)
    expected['document'].update(protocol=NEW_PROTOCOL_ID, minor=0, kind='specification')
    text, n_kind = _KIND_RE.subn(r'\1"specification"\2', text, count=1)
    text, n_proto = _PROTOCOL_RE.subn(rf'\1"{NEW_PROTOCOL_ID}"\2', text, count=1)
    text = re.sub(r'(?m)^(\s*minor\s*=\s*)\d+', r'\g<1>0', text, count=1)
    if tomllib.loads(text) != expected:
        raise Residual('unsupported TOML spelling; structural rewrite was not exact')
    return text


def migrate_package_text(text: str, new_spec_name: str | None, new_hash_hex: str) -> str:
    expected = tomllib.loads(text)
    allowed = {'format', 'subject', 'contract', 'spec', 'coverage', 'claim', 'deviation',
               'filler', 'conformance', 'dependency', 'dependency_inventory', 'ext'}
    extra = set(expected) - allowed
    if extra:
        raise Residual(f'unknown package key(s): {sorted(extra)}')
    extra = set(expected['contract']) - {'id', 'hash', 'requirements_total'}
    if extra:
        raise Residual(f'unknown contract binding key(s): {sorted(extra)}')
    expected['specification'] = expected.pop('contract')
    expected['specification']['hash'] = 'specification:sha-512:' + new_hash_hex
    if expected.get('format', {}).get('protocol') == OLD_PROTOCOL_ID:
        expected['format']['protocol'] = NEW_PROTOCOL_ID
    if new_spec_name:
        expected['spec']['path'] = new_spec_name
    text = _PROTOCOL_RE.sub(rf'\1"{NEW_PROTOCOL_ID}"\2', text, count=1)
    text = _TABLE_HEADER_RE.sub("[specification]", text, count=1)
    text = _HASH_LINE_RE.sub(
        lambda m: f'{m.group(1)}"specification:sha-512:{new_hash_hex}"{m.group(3)}',
        text, count=1,
    )
    if new_spec_name is not None:
        def _fix_spec_path(m: "re.Match") -> str:
            old_value = m.group(2)
            if old_value == "acceptance-contract.toml" or old_value.endswith(".contract.toml"):
                return f'{m.group(1)}"{new_spec_name}"{m.group(3)}'
            return m.group(0)
        text = re.sub(r'(?ms)(^\[spec\]\s*\n)(.*?)(?=^\[|\Z)',
                      lambda m: m[1] + _SPEC_PATH_RE.sub(
                          lambda p: f'{p[1]}"{new_spec_name}"{p[3]}', m[2], count=1), text)
    if tomllib.loads(text) != expected:
        raise Residual('unsupported package TOML spelling; structural rewrite was not exact')
    return text


def resolve_specification_path(package_path: Path, doc: dict) -> Path:
    spec_table = doc.get("spec")
    if isinstance(spec_table, dict) and isinstance(spec_table.get('path'), str):
        candidate = (package_path.parent / spec_table['path']).resolve()
        if classify(peek(candidate) or {}) == 'specification':
            return candidate
    # [spec].path commonly points to a prose SPEC.md, not the protocol specification.
    binding_id = doc.get('contract', {}).get('id')
    candidates = [p.resolve() for p in package_path.parent.glob('*.toml')
                  if (peek(p) or {}).get('document', {}).get('id') == binding_id]
    if len(candidates) != 1:
        raise Residual('cannot uniquely locate the bound specification by id beside the package')
    return candidates[0]


def migrate_one(path: Path, *, write: bool, skip_specifications: set[Path] = frozenset()) -> tuple[str, list[str]]:
    """Returns (`kind`, messages). `kind` is one of "specification"/"package"/"decision"/
    "amendment"/"residual". `skip_specifications` -- resolved paths of specifications bound to a
    REFUSED package in this same run: migrating one anyway would turn an already-broken binding
    (wrong hash, but the file still exists) into a MORE broken one (the file renamed out from
    under it), so it is left alone too, not silently "fixed" in isolation."""
    doc = peek(path)
    if doc is None:
        raise Residual(f"{path}: unreadable or unparsable TOML")
    kind = classify(doc)

    if kind == "decision":
        return "decision", [f"RE-ISSUE {path}: the consumer re-runs decide/make_decision under 0.4.0"]

    if kind is None:
        reason = "no [document] table and no [format] table" if "document" not in doc and "format" not in doc \
            else f"unrecognised [document].kind {doc.get('document', {}).get('kind')!r}"
        raise Residual(f"{path}: {reason}")

    if kind == "amendment":
        raise Residual(f"{path}: amendment migration is not defined by this tool (re-author under 0.4.0)")

    text = path.read_text(encoding="utf-8")

    if kind == "specification":
        if path.resolve() in skip_specifications:
            return "specification", [
                f"SKIPPED {path}: bound to a REFUSED package in this run — left alone, not fixed in isolation"
            ]
        document = doc["document"]
        if document.get("kind") == "specification" and document.get("protocol") == NEW_PROTOCOL_ID:
            return "specification", [f"{path}: already acceptance-protocol/1, nothing to do"]
        new_text = migrate_specification_text(text)
        new_name = _new_specification_name(path.name)
        new_path = path.with_name(new_name) if new_name else path
        if new_path != path and new_path.exists():
            raise Residual(f'{path}: destination {new_path} already exists')
        messages = [f"specification {path} -> {new_path}" if new_path != path else f"specification {path}"]
        if write:
            new_path.write_text(new_text, encoding="utf-8")
            if new_path != path:
                path.unlink()
        else:
            import difflib
            messages.extend(difflib.unified_diff(
                text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile=str(path), tofile=str(new_path),
            ))
        return "specification", messages

    # kind == "package"
    if 'specification' in doc and 'contract' not in doc:
        return 'package', [f'{path}: already acceptance-protocol/1, nothing to do']
    spec_path = resolve_specification_path(path, doc)
    contract_table = doc.get("contract")
    if not isinstance(contract_table, dict) or not isinstance(contract_table.get("hash"), str):
        raise Residual(f"{path}: no readable [contract].hash to verify before migrating")
    old_hash_m = re.fullmatch(r"contract:sha-512:([0-9a-f]{128})", contract_table["hash"])
    if old_hash_m is None:
        raise Residual(f"{path}: [contract].hash is not a well-formed contract:sha-512: wire value")
    if not spec_path.is_file():
        raise Residual(f"{path}: bound specification {spec_path} does not exist")
    spec_bytes = spec_path.read_bytes()
    recomputed_old = _old_contract_digest(spec_bytes)
    if recomputed_old != contract_table["hash"]:
        raise Refused(
            f"{path}: [contract].hash {contract_table['hash']!r} does not recompute over "
            f"{spec_path} ({recomputed_old!r}) — refused, not fixed (a pre-existing binding defect)"
        )
    spec_text = spec_path.read_text(encoding="utf-8")
    new_spec_text = migrate_specification_text(spec_text)
    new_hash_hex = hashdomains.digest_hex("specification:", new_spec_text.encode("utf-8"))
    new_spec_name = None
    old_pointer = doc.get('spec', {}).get('path')
    if old_pointer and (path.parent / old_pointer).resolve() == spec_path:
        renamed = _new_specification_name(spec_path.name)
        if renamed:
            new_spec_name = str(Path(old_pointer).with_name(renamed))
    new_text = migrate_package_text(text, new_spec_name, new_hash_hex)
    messages = [f"package {path}"]
    if write:
        path.write_text(new_text, encoding="utf-8")
    else:
        import difflib
        messages.extend(difflib.unified_diff(
            text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=str(path), tofile=str(path) + ".new",
        ))
    return "package", messages


def run(paths: list[str], *, write: bool, allow_decisions_pending: bool) -> int:
    # Resolve the complete transaction before writing. A package alone also migrates
    # its bound specification; siblings that are decisions are only reported.
    expanded = dict.fromkeys(str(Path(p).resolve()) for p in paths)
    for raw in list(expanded):
        path = Path(raw)
        doc = peek(path) or {}
        if classify(doc) == 'package' and 'contract' in doc:
            try:
                expanded[str(resolve_specification_path(path, doc))] = None
            except Residual:
                pass  # preflight below prints the diagnostic
        for sibling in path.parent.glob('*.toml'):
            if classify(peek(sibling) or {}) == 'decision':
                expanded[str(sibling.resolve())] = None
    paths = list(expanded)
    errors = []
    for raw in paths:
        try:
            migrate_one(Path(raw), write=False)
        except (Residual, Refused) as exc:
            errors.append(('REFUSED' if isinstance(exc, Refused) else 'RESIDUAL') + ' ' + str(exc))
    if errors:
        for error in errors:
            print(error)
        return 2
    had_decision = False
    had_residual = False
    skip_specifications: set[Path] = set()

    # Pass 1: packages, while every bound specification is still at its ORIGINAL path/bytes --
    # a package resolves its specification by reading [spec].path off disk, so this must run
    # before any specification in the same invocation is renamed.
    package_paths = [Path(r) for r in paths if classify(peek(Path(r)) or {}) == "package"]
    other_paths = [Path(r) for r in paths if Path(r) not in package_paths]
    for p in package_paths:
        try:
            kind, messages = migrate_one(p, write=write)
        except Residual as exc:
            print(f"RESIDUAL {exc}")
            had_residual = True
            continue
        except Refused as exc:
            print(f"REFUSED {exc}")
            had_residual = True
            doc = peek(p)
            if doc is not None:
                try:
                    skip_specifications.add(resolve_specification_path(p, doc))
                except Residual:
                    pass
            continue
        for m in messages:
            print(m, end="" if m.endswith("\n") else "\n")

    # Pass 2: everything else (specifications, decisions, amendments, residuals).
    for p in other_paths:
        try:
            kind, messages = migrate_one(p, write=write, skip_specifications=skip_specifications)
        except Residual as exc:
            print(f"RESIDUAL {exc}")
            had_residual = True
            continue
        except Refused as exc:
            print(f"REFUSED {exc}")
            had_residual = True
            continue
        for m in messages:
            print(m, end="" if m.endswith("\n") else "\n")
        if kind == "decision":
            had_decision = True
    if had_residual:
        return 2
    if had_decision and not allow_decisions_pending:
        return 3
    return 0


def selftest() -> int:
    import shutil
    import tempfile

    ok = True

    def _write(td: Path, name: str, text: str) -> Path:
        p = td / name
        p.write_text(text, encoding="utf-8")
        return p

    # A complete historical fixture, validated by both current checkers after migration.
    from fixtures.verification_chain import _SPECIFICATION_TOML, _PACKAGE_TOML
    import acceptance_protocol as AP
    spec_text = _SPECIFICATION_TOML.replace(NEW_PROTOCOL_ID, OLD_PROTOCOL_ID).replace(
        'kind       = "specification"', 'kind       = "contract"')
    package_text = _PACKAGE_TOML.replace('[specification]', '[contract]').replace(
        '{{SPECIFICATION_HASH}}', '{HASH}')
    decision_text = (
        '[document]\n'
        'protocol = "acceptance-protocol/0"\n'
        'minor    = 0\n'
        'kind     = "decision"\n'
        'id       = "AD-MIG-1"\n'
    )

    # GREEN: a 0.3.2 spec + package round trip.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        spec = _write(d, "acceptance-contract.toml", spec_text)
        correct_hash = _old_contract_digest(spec.read_bytes())
        package = _write(d, "acceptance.toml", package_text.replace("{HASH}", correct_hash))
        (d / '.git').mkdir()
        (d / 'evidence').mkdir()
        for name in ('c1.json', 'c1-mutant.json', 'c3.json'):
            (d / 'evidence' / name).write_text('{"fixture": "protocol selftest"}\n')
        rc = run([str(spec), str(package)], write=True, allow_decisions_pending=False)
        new_spec = d / "acceptance-specification.toml"
        new_spec_doc = tomllib.loads(new_spec.read_text()) if new_spec.exists() else {}
        new_pkg_doc = tomllib.loads(package.read_text())
        green_ok = (
            rc == 0 and not spec.exists() and new_spec.exists()
            and new_spec_doc.get("document", {}).get("kind") == "specification"
            and new_spec_doc.get("document", {}).get("protocol") == NEW_PROTOCOL_ID
            and "specification" in new_pkg_doc and "contract" not in new_pkg_doc
            and new_pkg_doc["specification"]["hash"].startswith("specification:sha-512:")
            and AP.check_specification(new_spec_doc).ok()
            and AP.check_package(new_pkg_doc, new_spec_doc, package, new_spec, True)[0].ok()
            and hashdomains.digest("specification:", new_spec.read_bytes()) == new_pkg_doc["specification"]["hash"]
        )
        if not green_ok:
            print(f"SELFTEST FAIL: green-roundtrip: rc={rc}"); ok = False
        else:
            print("PASS green-roundtrip-spec-and-package")

    # RED: a decision is never modified (byte-equal before/after), and exits 3 without the flag.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        decision = _write(d, "acceptance-decision.toml", decision_text)
        before = decision.read_bytes()
        rc = run([str(decision)], write=True, allow_decisions_pending=False)
        after = decision.read_bytes()
        if rc == 3 and before == after:
            print("PASS decision-never-rewritten-exit-3")
        else:
            print(f"SELFTEST FAIL: decision-never-rewritten: rc={rc} byte_equal={before == after}"); ok = False
        rc2 = run([str(decision)], write=True, allow_decisions_pending=True)
        if rc2 == 0 and decision.read_bytes() == before:
            print("PASS decision-allow-pending-exit-0")
        else:
            print(f"SELFTEST FAIL: decision-allow-pending: rc={rc2}"); ok = False

    # RED: an unknown/unrecognised document -> residual, exit 2.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        mystery = _write(d, 'mystery.toml', spec_text.replace('[document]', '[document]\nunknown_key = true'))
        rc = run([str(mystery)], write=False, allow_decisions_pending=False)
        if rc == 2:
            print("PASS unknown-document-residual-exit-2")
        else:
            print(f"SELFTEST FAIL: unknown-document-residual: rc={rc}"); ok = False

    # RED: a package whose [contract].hash does not match the spec -> refused, not fixed.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        spec = _write(d, "acceptance-contract.toml", spec_text)
        package = _write(d, "acceptance.toml", package_text.replace("{HASH}", "contract:sha-512:" + "a" * 128))
        before_pkg = package.read_bytes()
        before_spec = spec.read_bytes()
        rc = run([str(spec), str(package)], write=True, allow_decisions_pending=False)
        if rc == 2 and package.read_bytes() == before_pkg and spec.read_bytes() == before_spec:
            print("PASS mismatched-hash-refused-not-fixed")
        else:
            print(f"SELFTEST FAIL: mismatched-hash-refused: rc={rc}"); ok = False

    print("SELFTEST PASS: acceptance_migrate (4 controls)" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--selftest" in argv[1:]:
        return selftest()
    ap = argparse.ArgumentParser(prog="acceptance_migrate.py")
    sub = ap.add_subparsers(dest="verb", required=True)
    sp = sub.add_parser("migrate")
    sp.add_argument("paths", nargs="+")
    sp.add_argument("--write", action="store_true")
    sp.add_argument("--allow-decisions-pending", action="store_true")
    args = ap.parse_args(argv[1:])
    return run(args.paths, write=args.write, allow_decisions_pending=args.allow_decisions_pending)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
