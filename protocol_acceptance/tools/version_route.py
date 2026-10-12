#!/usr/bin/env python3
"""Route protocol-bound documents before modern grammar validation.

Packages identify their generation by the binding table. Specifications, decisions
and amendments identify it by protocol/minor. Mixed generations are refused. The
internal frozen checker runs with isolated Python and its own working directory;
public archives without that checker print a precise migration instruction.
"""
from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
LEGACY_ROOT = _HERE / "legacy_0_3"
LEGACY_ENTRYPOINT = LEGACY_ROOT / "protocol_acceptance" / "tools" / "acceptance_protocol.py"
LEGACY_CWD = LEGACY_ENTRYPOINT.parent

ROUTE_NOTE = (
    "NOTE: acceptance-protocol/0 document checked by the frozen 0.3.2 checker; "
    "migrate with acceptance_migrate.py"
)
NO_LEGACY_REFUSAL = (
    "0.3 document: use acceptance-format tag v0.3.2, or migrate with "
    "protocol_acceptance/tools/acceptance_migrate.py"
)
MIXED_VERSIONS_ERROR = (
    "ERROR: mixed acceptance-protocol/0 and acceptance-protocol/1 inputs in one invocation "
    "— re-issue the /0 document(s) first (acceptance_migrate.py)"
)

# Per verb SPELLING (both the 0.4 name and the kept 0.3.2 alias resolve to the SAME dest names,
# since `build_argparser` gives each flag/verb pair one shared `dest=` — argparse's own
# `args.verb`/`args.<dest>` always hold whichever spelling the dest was given, never the literal
# token the caller typed, EXCEPT `args.verb` itself, which argparse sets to whatever subparser
# name/alias string the caller actually used (`"check-contract"` or `"check-spec"`) — hence both
# spellings are listed as keys here, each pointing at the SAME dest names) -- which argparse dest
# names hold acceptance-document paths that must be version-peeked before this tool's own code
# sees them. "single" dests hold one path (or None); "list" dests hold a list of paths (or None,
# `--previous`); "dir" dests hold a directory of candidate predecessors, each resolved by its own
# [document].id, exactly as `resolve_predecessor_chain` does (`*.toml`, sorted, first-id-wins).
VERB_DOC_DESTS: dict[str, dict[str, list[str]]] = {
    "format": {"list": ["files"]},
    "check-spec": {"single": ["specification"], "list": ["previous"], "dir": ["previous_dir"]},
    "check-contract": {"single": ["specification"], "list": ["previous"], "dir": ["previous_dir"]},
    "check-package": {"single": ["package", "specification", "previous_specification"], "list": ["previous"], "dir": ["previous_dir"]},
    "coverage": {"single": ["package", "specification"]},
    "decide": {"single": ["package", "specification"]},
    "check-decision": {"single": ["decision", "specification", "package", "previous_specification"], "list": ["previous"], "dir": ["previous_dir"]},
    "impact": {"single": ["decision", "specification", "package", "new_package"]},
    "render": {"single": ["specification", "package", "decision"]},
    "check-amendment": {"single": ["amendment", "specification"]},
    "apply-amendment": {"single": ["amendment", "specification", "current"]},
    "amend": {"single": ["specification", "from_decision"]},
    "project-brief": {"single": ["specification"]},
    "assemble-package": {"single": ["specification"]},
    # check-states / transition touch no acceptance document ([document].protocol does not apply
    # to states.toml, a machine-definition file) -- intentionally absent.
}

# argv-token rewriting for the frozen-checker dispatch: the frozen tree only understands 0.3.2
# spellings, so a /0 invocation that used the NEW spelling (e.g. `check-spec old.toml` on a
# `/0` document, or `--spec` naming a `/0` file) is mapped back to the old spelling before the
# subprocess call (plan §1: "it executes the frozen checker with the same argv: map check-spec ->
# check-contract and --spec -> --contract").
VERB_TO_LEGACY: dict[str, str] = {
    "check-spec": "check-contract",
    "check-contract": "check-contract",
}
FLAG_TO_LEGACY: dict[str, str] = {
    "--spec": "--contract",
    "--previous-spec": "--previous-contract",
}


def peek_document(path) -> dict | None:
    """Reads only `[document]` from `path` via a bare `tomllib.load`. Returns `None` on any
    failure (missing file, bad TOML, no `[document]` table) -- deliberately swallowed here so the
    modern checker's own, more specific error reporting still fires for that path."""
    try:
        with open(path, "rb") as fh:
            doc = tomllib.load(fh)
    except Exception:
        return None
    document = doc.get("document", doc)
    declared_protocol = document.get('protocol') if isinstance(document, dict) else None
    requirements = doc.get('requirement')
    requirements = requirements if isinstance(requirements, list) else []
    legacy = declared_protocol == 'acceptance-protocol/0' or 'contract' in doc
    if legacy and (any(key in doc for key in ('dependency', 'dependency_inventory', 'chain_evaluation'))
                   or any(isinstance(req, dict) and 'chain' in req for req in requirements)):
        raise VersionRouteError('ERROR: chain fields in an acceptance-protocol/0 document')
    if "contract" in doc and "specification" in doc:
        raise VersionRouteError(MIXED_VERSIONS_ERROR)
    if "contract" in doc:
        return {"protocol": "acceptance-protocol/0"}
    if "specification" in doc:
        return {"protocol": "acceptance-protocol/1", "minor": 0}
    return document if isinstance(document, dict) else None


def _collect_dir_candidates(dir_path) -> list[Path]:
    d = Path(dir_path)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.toml"))


def gather_paths(verb: str, args) -> list[Path]:
    """Every acceptance-document path this invocation touches, per `VERB_DOC_DESTS[verb]`."""
    spec = VERB_DOC_DESTS.get(verb)
    if spec is None:
        return []
    paths: list[Path] = []
    for dest in spec.get("single", []):
        value = getattr(args, dest, None)
        if value:
            paths.append(Path(value))
    for dest in spec.get("list", []):
        value = getattr(args, dest, None) or []
        paths.extend(Path(v) for v in value)
    for dest in spec.get("dir", []):
        value = getattr(args, dest, None)
        if value:
            paths.extend(_collect_dir_candidates(value))
    return paths


class VersionRouteError(Exception):
    """Raised before any routing; the caller prints `str(exc)` to stderr and exits 2."""


def classify(verb: str, args) -> str | None:
    """Peeks every document this invocation touches and returns `"legacy"` (route to the frozen
    checker), `None` (every peeked document is `/1`; the caller proceeds normally), or raises
    `VersionRouteError` (a mix, or a `/1` document with `minor != 0`)."""
    paths = gather_paths(verb, args)
    versions: set[str] = set()
    minor_errors: list[str] = []
    for p in paths:
        document = peek_document(p)
        if document is None:
            continue
        protocol = document.get("protocol")
        if protocol == "acceptance-protocol/0":
            versions.add("acceptance-protocol/0")
        elif protocol == "acceptance-protocol/1":
            versions.add("acceptance-protocol/1")
            minor = document.get("minor")
            if type(minor) is not int or minor != 0:
                minor_errors.append(
                    f"ERROR: {p}: unsupported minor for acceptance-protocol/1: {minor!r} (must be 0)"
                )
        # any other / missing `protocol` value is left for the modern checker's own
        # "[document].protocol must be ... got ..." error.

    if len(versions) > 1:
        raise VersionRouteError(MIXED_VERSIONS_ERROR)
    if versions == {"acceptance-protocol/0"}:
        return "legacy"
    if minor_errors:
        raise VersionRouteError("\n".join(minor_errors))
    return None


def run_legacy(argv: list[str], *, quiet: bool = False, entrypoint: Path | None = None,
               audit_path: Path | None = None) -> int:
    """Maps `argv` (verb + flags) to 0.3.2 spelling and runs the frozen checker as a subprocess
    with the SAME argv (mapped), `python3 -I`, cwd inside the frozen tree. Prints the one required
    NOTE line to stderr first, unless `quiet` (a gate's own internal compatibility probe, which
    checks only the exit code and would otherwise flood a gate run with the frozen checker's real
    PASS/WARN/FAIL lines). Returns the frozen checker's own exit code."""
    entrypoint = entrypoint or LEGACY_ENTRYPOINT
    if not entrypoint.exists():
        if not quiet:
            print(NO_LEGACY_REFUSAL, file=sys.stderr)
        return 2
    mapped = list(argv)
    if mapped and mapped[0] in VERB_TO_LEGACY:
        mapped[0] = VERB_TO_LEGACY[mapped[0]]
    mapped = [FLAG_TO_LEGACY.get(tok.split("=", 1)[0], tok.split("=", 1)[0])
              + ("=" + tok.split("=", 1)[1] if "=" in tok else "") for tok in mapped]
    # The isolated cwd must not change the caller's path semantics (including outputs).
    path_flags = {"--contract", "--previous-contract", "--previous", "--previous-dir",
                  "--package", "--new-package", "--from-decision", "--current", "--pointer",
                  "--out", "--out-events", "--root", "--states", "--changed-file", "--fill"}
    positional_counts = {"check-contract": 1, "check-package": 1, "coverage": 1, "decide": 1,
                         "check-decision": 1, "impact": 1, "render": 3, "check-amendment": 1,
                         "project-brief": 1, "assemble-package": 2}
    remaining = positional_counts.get(mapped[0], 0) if mapped else 0
    previous_flag = None
    for i in range(1, len(mapped)):
        token = mapped[i]
        if token.startswith("--"):
            flag, sep, value = token.partition("=")
            if sep and flag in path_flags:
                mapped[i] = flag + "=" + str(Path(value).resolve())
            previous_flag = flag if not sep and flag not in {"--json", "--strict", "--effect", "--allow-conditions", "--dry-run", "--stats"} else None
        else:
            if previous_flag in path_flags or (previous_flag is None and remaining):
                mapped[i] = str(Path(token).resolve())
                if previous_flag is None:
                    remaining -= 1
            previous_flag = None
    if not quiet:
        print(ROUTE_NOTE, file=sys.stderr)
    # Captured, not inherited: a caller that redirects `sys.stdout`/`sys.stderr` at the Python
    # level (this tool's own in-process CLI tests, among others) would otherwise see nothing from
    # a real child process, since a subprocess's inherited stdio is an OS file descriptor, not
    # Python's `sys.stdout` object. Re-emitting through `sys.stdout`/`sys.stderr` here keeps the
    # frozen checker's output visible to both a real terminal AND any such redirect.
    command = [sys.executable, "-I", str(entrypoint), *mapped]
    if audit_path is not None:
        # Gate-only observation of the real dispatch, without editing frozen sources.
        probe = """import sys, runpy, json
from pathlib import Path
entry, audit, *args = sys.argv[1:]
sys.path.insert(0, str(Path(entry).parent))
sys.argv = [entry, *args]
try:
    runpy.run_path(entry, run_name='__main__')
finally:
    Path(audit).write_text(json.dumps({n: m.__file__ for n, m in sys.modules.items()
                                     if getattr(m, '__file__', None)}))
"""
        command = [sys.executable, "-I", "-c", probe, str(entrypoint), str(audit_path), *mapped]
    result = subprocess.run(
        command,
        cwd=str(entrypoint.parent),
        capture_output=True,
        text=True,
    )
    if not quiet:
        sys.stdout.write(result.stdout)
        sys.stdout.flush()
        sys.stderr.write(result.stderr)
        sys.stderr.flush()
    return result.returncode


def route_format(args, argv: list[str], *, bound_meaning=None, tool_name=None) -> int | None:
    """The format CLIs also refuse mixed bindings before loading a package grammar."""
    try:
        verdict = classify('format', args)
    except VersionRouteError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if verdict != 'legacy':
        return None
    entry = LEGACY_ROOT / 'format_acceptance/tools' / (tool_name or (
        'check_acceptance.py' if bound_meaning == 'verification' else 'check_core.py'))
    paths = {str(p): str(Path(p).resolve()) for p in args.files}
    mapped = [paths.get(token, token) for token in argv[1:]]
    for i, token in enumerate(mapped):
        if token in {'--root', '--subject-root'} and i + 1 < len(mapped):
            mapped[i + 1] = str(Path(mapped[i + 1]).resolve())
        elif token.startswith(('--root=', '--subject-root=')):
            flag, value = token.split('=', 1)
            mapped[i] = flag + '=' + str(Path(value).resolve())
    return run_legacy(mapped, entrypoint=entry)


def route(verb: str, raw_argv: list[str], args) -> int | None:
    """The single entry point `acceptance_protocol.py`'s `main()` calls, right after
    `parser.parse_args()`, before `args.func(args)`. Returns an exit code to use VERBATIM (the
    frozen checker ran, or a version-routing error fired) or `None` (every document is `/1`;
    the caller should proceed with `args.func(args)`)."""
    try:
        verdict = classify(verb, args)
    except VersionRouteError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if verdict == "legacy":
        return run_legacy(raw_argv)
    return None
