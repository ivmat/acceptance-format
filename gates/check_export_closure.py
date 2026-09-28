#!/usr/bin/env python3
"""Exercise the real closure exporter from a clean public git checkout.

The export receipt verifies shipped bytes; closure provenance names this public commit.
No metadata reader is replaced.

A public checkout is dirty by definition WHILE a commit is in flight (the pre-commit hook
runs this suite against the working tree that is about to become the next commit, which
`git status --porcelain` always reports as dirty relative to the current HEAD). Refusing the
gate on that dirtiness would make the public repo unable to ever commit through its own hook.
So: a clean, already-committed checkout is verified in place (today's behaviour, unchanged);
a dirty checkout (or a directory that is not a git repository at all, e.g. a bare export) is
instead copied — everything the export would consider, i.e. every file except `.git` and
`__pycache__` — into a throwaway directory, `git init`-ed and committed there with a fixed,
disabled-hooks identity, and the SAME real exporter/verifier commands run against THAT copy's
own HEAD. Nothing about the exporter or verifier is mocked or replaced in either branch.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

_GIT_IDENTITY = ['-c', 'user.name=gate', '-c', 'user.email=gate@localhost',
                 '-c', 'core.hooksPath=/dev/null']


def _isolated_git_env():
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def _copy_tree_for_closure(src, dst):
    """Copy every file the export would consider, excluding .git and __pycache__."""
    def ignore(_dir, names):
        return {n for n in names if n in ('.git', '__pycache__')}
    shutil.copytree(src, dst, ignore=ignore)


def _git_init_commit(root, *, message):
    """git init + commit the tree at `root` with a fixed, hooks-disabled identity. Returns the
    resulting 40-hex commit."""
    env = _isolated_git_env()
    for args in (['init', '-q'], ['add', '-A'], ['commit', '-q', '-m', message]):
        subprocess.run(['git', *_GIT_IDENTITY, '-C', str(root), *args], check=True, env=env)
    result = subprocess.run(['git', *_GIT_IDENTITY, '-C', str(root), 'rev-parse', 'HEAD'],
                            check=True, env=env, capture_output=True, text=True)
    commit = result.stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError(f'temp copy git rev-parse HEAD did not return a commit: {commit!r}')
    return commit


def _run_closure_pipeline(export_root, expect_commit, td, provenance):
    """Run the real export + verify + consumer-CLI battery against `export_root`, using its own
    (relocated) copy of export_closure.py so REPO_ROOT inside that process is `export_root`."""
    dest = Path(td) / 'closure'
    subprocess.run([sys.executable, str(export_root / 'protocol_acceptance/tools/export_closure.py'),
                    'export', '--dest', str(dest)], check=True, cwd=export_root)
    subprocess.run([sys.executable, str(dest / 'export_closure.py'), 'verify', '--dest', str(dest),
                    '--expect-commit', expect_commit, '--require-clean',
                    '--expect-family-version', provenance['family_version']], check=True, cwd=td)
    rd = ROOT / 'protocol_acceptance/examples/rust-delivery'
    commands = [
        ('format_acceptance/tools/check_acceptance.py', ['--root', str(ROOT), '--strict', '--strict-weight', str(rd / 'acceptance.toml')]),
        ('protocol_acceptance/tools/acceptance_protocol.py', ['check-contract', str(rd / 'acceptance-contract.toml')]),
        ('protocol_acceptance/tools/acceptance_protocol.py', ['check-package', str(rd / 'acceptance.toml'), '--contract', str(rd / 'acceptance-contract.toml')]),
        ('protocol_acceptance/tools/acceptance_protocol.py', ['check-decision', str(rd / 'acceptance-decision.toml'), '--contract', str(rd / 'acceptance-contract.toml'), '--package', str(rd / 'acceptance.toml')]),
    ]
    for script, args in commands:
        subprocess.run([sys.executable, str(dest / script), *args], cwd=td, check=True)
    return dest


def _able_to_fail_dirty_copy_control(tool):
    """Able-to-fail control for the dirty-tree fallback itself (not the dest-corruption control
    below, which exercises `_verify`'s file-drift check regardless of which path built `dest`):
    take a temp copy, commit it cleanly, then corrupt a file IN THE TEMP TREE after the commit —
    this makes that copy's own git status dirty again. Exporting and verifying with
    --require-clean against the ORIGINAL commit must then FAIL on the source_dirty mismatch,
    proving the fallback path genuinely reflects the temp copy's real git state rather than
    rubber-stamping it clean."""
    with tempfile.TemporaryDirectory(prefix='public-closure-control-') as ctd:
        ctd_path = Path(ctd)
        control_root = ctd_path / 'source-copy'
        _copy_tree_for_closure(ROOT, control_root)
        control_commit = _git_init_commit(control_root, message='dirty-copy control commit')
        victim = control_root / 'format_acceptance/tools/check_core.py'
        original = victim.read_bytes()
        victim.write_bytes(original + b'\n# dirty-tree-copy corruption control\n')
        try:
            control_dest = ctd_path / 'closure'
            subprocess.run([sys.executable, str(control_root / 'protocol_acceptance/tools/export_closure.py'),
                            'export', '--dest', str(control_dest)], check=True, cwd=control_root)
            errors = tool._verify(control_dest, expect_commit=control_commit, require_clean=True)
            if not errors:
                raise ValueError('dirty-tree-copy corruption control did not fail verification')
            if not any('source_dirty' in e for e in errors):
                raise ValueError(f'dirty-tree-copy corruption control failed for the wrong reason: {errors}')
        finally:
            victim.write_bytes(original)


def main():
    provenance = json.loads((ROOT / 'EXPORT-PROVENANCE.json').read_text())
    for rel, entry in provenance['files'].items():
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'public provenance drift: {rel}')
    spec = importlib.util.spec_from_file_location('closure', ROOT / 'protocol_acceptance/tools/export_closure.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)

    try:
        commit = tool._source_commit(ROOT)
        dirty = tool._source_dirty(ROOT)
    except RuntimeError:
        commit = None
        dirty = True

    if tool._family_version(ROOT) != provenance['family_version']:
        raise ValueError('public family version mismatch')

    _able_to_fail_dirty_copy_control(tool)

    with tempfile.TemporaryDirectory(prefix='public-closure-') as td:
        td_path = Path(td)
        if commit is not None and not dirty:
            print('check_export_closure: clean committed checkout — verifying in place')
            export_root, expect_commit = ROOT, commit
        else:
            print('check_export_closure: dirty or non-git checkout — committing a temp clean '
                  'copy of the working tree for verification')
            export_root = td_path / 'source-copy'
            _copy_tree_for_closure(ROOT, export_root)
            expect_commit = _git_init_commit(export_root, message='public closure gate temp commit')
        dest = _run_closure_pipeline(export_root, expect_commit, td, provenance)

        victim = dest / 'format_acceptance/tools/check_core.py'
        original = victim.read_bytes()
        victim.write_bytes(original + b'\n# corruption control\n')
        errors = tool._verify(dest)
        if not any(e.startswith('drift:') for e in errors):
            raise ValueError('corruption control was not detected')
        victim.write_bytes(original)
        if tool._verify(dest):
            raise ValueError('restored closure failed verification')
    print('PASS check_export_closure: public provenance, real consumer CLIs, corruption refused and restoration verified')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f'FAIL check_export_closure: {exc}', file=sys.stderr)
        sys.exit(1)
