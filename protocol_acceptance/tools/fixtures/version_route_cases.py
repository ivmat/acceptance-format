"""Executable version-boundary controls; shared by internal and archive selftests."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import version_route as V
from fixtures._support import Cases


def run():
    cases = Cases()
    with TemporaryDirectory() as td:
        root = Path(td)
        def document(name, protocol, minor=0, kind='specification'):
            p = root / name
            p.write_text(f'[document]\nprotocol = "acceptance-protocol/{protocol}"\nminor = {minor}\nkind = "{kind}"\n')
            return str(p)
        old = document('old.toml', 0, kind='contract')
        new = document('new.toml', 1)
        def package(name, table):
            p = root / name
            p.write_text(f'[format]\nid = "acceptance/0"\n[{table}]\nid = "S"\n')
            return str(p)
        old_pkg = package('old-package.toml', 'contract')
        new_pkg = package('new-package.toml', 'specification')
        cases.check('all-v0-classifies-legacy', V.classify('check-spec', SimpleNamespace(specification=old)) == 'legacy')
        cases.check('all-v1-classifies-current', V.classify('check-spec', SimpleNamespace(specification=new)) is None)
        cases.check('package-table-v0', V.classify('format', SimpleNamespace(files=[old_pkg])) == 'legacy')
        cases.check('package-table-v1', V.classify('format', SimpleNamespace(files=[new_pkg])) is None)
        def refused(name, verb, args, message):
            stderr = StringIO()
            with patch.object(V, 'run_legacy', side_effect=AssertionError('must not route mixed inputs')), redirect_stderr(stderr):
                rc = V.route(verb, [], args)
            cases.check(name, rc == 2 and message in stderr.getvalue(), stderr.getvalue())
        refused('mixed-specification-package-R50', 'check-package', SimpleNamespace(specification=old, package=new_pkg), V.MIXED_VERSIONS_ERROR)
        refused('mixed-package-specification-reverse', 'check-package', SimpleNamespace(specification=new, package=old_pkg), V.MIXED_VERSIONS_ERROR)
        refused('legacy-predecessor-R51', 'check-spec', SimpleNamespace(specification=new, previous=[old]), V.MIXED_VERSIONS_ERROR)
        refused('legacy-predecessor-option', 'check-package', SimpleNamespace(specification=new, package=new_pkg, previous_specification=old), V.MIXED_VERSIONS_ERROR)
        refused('mixed-format-inputs', 'format', SimpleNamespace(files=[new_pkg, old_pkg]), V.MIXED_VERSIONS_ERROR)
        for minor in ('7', 'true', '0.0'):
            bad = document('bad.toml', 1, minor)
            refused('unsupported-minor-' + minor, 'check-spec', SimpleNamespace(specification=bad), 'unsupported minor for acceptance-protocol/1')
        legacy_chain = root / 'legacy-chain.toml'
        legacy_chain.write_text(Path(old).read_text() + '\n[[dependency]]\nid = "legacy"\n')
        refused('legacy-chain-fields-R53', 'check-spec', SimpleNamespace(specification=str(legacy_chain)), 'chain fields')
        cases.check('missing-file-diagnostic-falls-through', V.classify('check-spec', SimpleNamespace(specification=str(root / 'missing'))) is None)
        stderr = StringIO()
        with patch.object(V, 'LEGACY_ENTRYPOINT', root / 'absent'), redirect_stderr(stderr):
            rc = V.route('check-spec', ['check-spec', old], SimpleNamespace(specification=old))
        cases.check('absent-frozen-tree-exact-refusal', rc == 2 and stderr.getvalue() == V.NO_LEGACY_REFUSAL + '\n', stderr.getvalue())
        # Verify argparse's real aliases, including --flag=value warning syntax.
        import acceptance_protocol as AP
        stderr = StringIO()
        argv = ['check-package', old_pkg, '--contract=' + old, '--previous-contract=' + old]
        with redirect_stderr(stderr):
            AP._warn_deprecated_aliases(argv)
        parsed = AP.build_argparser().parse_args(argv)
        cases.check('deprecated-flags-share-destinations', parsed.specification == old and parsed.previous_specification == old)
        cases.check('deprecated-flags-exact-warnings', set(stderr.getvalue().splitlines()) == {
            "DEPRECATED: '--contract' is '--spec' since 0.4.0",
            "DEPRECATED: '--previous-contract' is '--previous-spec' since 0.4.0"})
        stderr = StringIO()
        with redirect_stderr(stderr):
            AP._warn_deprecated_aliases(['check-contract', old])
        cases.check('deprecated-verb-exact-warning', stderr.getvalue() == "DEPRECATED: 'check-contract' is 'check-spec' since 0.4.0\n")
    return cases.items
