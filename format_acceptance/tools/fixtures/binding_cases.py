"""Binding-chain fixtures shared verbatim by selftests and the mutation audit."""
from __future__ import annotations
import copy
import hashlib
import runpy
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import check_core as C
from bindings import code, code_rust
from profiles import conformance as M

# scope, name, expected (verdict, exit), required substring, operation
CASES = []


def document():
    # A native-evidence variant: these tests manipulate claim[0]'s evidence
    # record directly (weight, cover_only, epistemic_tier, build_inputs, control …)
    # and have nothing to do with the B8 acceptance-claim lowering the default
    # _green_fixture()'s claim[0] now carries.
    d = M._native_claim_fixture()['manifest']
    d['format']['profile'] = M.MEANING + '/code/rust'
    return d


def weighted(d):
    d['claim'][0].update(weight='weighted', grade='probe', bounds='bounded fixture inputs',
                         self_verify={'command': 'cargo kani', 'expect': 'SUCCESS'})


def native(scope, name, change=lambda d: None, expected=('FAIL', 1), substring='', absent=''):
    def execute():
        d = document()
        change(d)
        ctx = C.Context(Path('acceptance.toml'), None)
        # code_rust.check no longer re-runs code.check (binding-chain diagnostic
        # de-duplication — check_profiles already evaluates every prefix module in the
        # real chain). Compose the same way here for 'code/rust' scope.
        findings = code.check(d, ctx) + code_rust.check(d, ctx) if scope == 'code/rust' else code.check(d, ctx)
        actual = ('FAIL', 1) if any(f.severity == 'error' for f in findings) else ('PASS', 0)
        output = actual[0] + '\n' + '\n'.join(f.severity.upper() + ': ' + f.message for f in findings)
        assert actual == expected, (actual, output)
        assert substring in output, (substring, output)
        assert not absent or absent not in output, (absent, output)
        return output
    CASES.append((scope, name, expected, substring, execute))


native('code', 'b14-code-admitted-pass', expected=('PASS', 0), substring='PASS')
native('code', 'b14-code-doc-red', lambda d: d['subject'].update(kind='doc'), substring='B14:')
native('code', 'b1-code-git-pass', expected=('PASS', 0), substring='PASS')
native('code', 'b1-code-digest-red', lambda d: (d['subject'].pop('commit'), d['subject'].update(digest='subject:sha-512:'+'a'*128)), substring='B1: code requires git-revision')
native('code', 'b1-code-components-red', lambda d: d['subject'].update(components=[]), substring='B1: code requires git-revision')
native('code', 'b1-code-dirty-red', lambda d: d['subject'].update(dirty=True), substring='dirty = false')
native('code', 'b1-code-dirty-missing-red', lambda d: d['subject'].pop('dirty'), substring='dirty = false')
native('code', 'b1-code-prospective-pass', lambda d: (d['subject'].pop('commit'), d['subject'].update(kind='prospective-feature', mode='prospective', read_at_commit='unpinned', dirty=True)), expected=('PASS', 0), substring='PASS')
native('code/rust', 'b14-rust-prospective-feature-red', lambda d: d['subject'].update(kind='prospective-feature', mode='prospective', read_at_commit='unpinned'), substring='B14: code/rust')
native('code/rust', 'b14-rust-crate-pass', expected=('PASS', 0), substring='PASS')
native('code/rust', 'b14-rust-workspace-pass', lambda d: d['subject'].update(kind='rust-workspace'), expected=('PASS', 0), substring='PASS')
native('code/rust', 'b17-rust-inherits-parent-dirty-red', lambda d: d['subject'].update(dirty=True), substring='dirty = false')


def widened():
    declaration = code.declaration
    def widen(name):
        result = declaration(name)
        if name == 'code/rust':
            result['admits'].append('doc')
        return result
    with patch.object(code, 'declaration', widen):
        try:
            runpy.run_path(str(Path(code_rust.__file__)))
        except AssertionError as exc:
            assert 'B17: admits(code/rust)' in str(exc), str(exc)
            return 'FAIL B17: admits(code/rust) widened import rejected'
        raise AssertionError('widened child imported successfully')
CASES.append(('code/rust', 'b17-widened-child-import-red', ('FAIL', 1), 'B17: admits(code/rust)', widened))


def covers(d):
    weighted(d)
    d['claim'][0]['evidence'][0]['cover_only'] = True


def mixed(d):
    covers(d)
    e = copy.deepcopy(d['claim'][0]['evidence'][0]); e['cover_only'] = False
    d['claim'][0]['evidence'].append(e)


native('code/rust', 'b9-cover-only-weighted-red', covers, substring='C8:')
native('code/rust', 'b9-verification-leaf-cover-red', lambda d: (covers(d), d['format'].update(profile='acceptance/verification/code/rust')), substring='C8:')
native('code/rust', 'b9-cover-only-unweighted-pass', lambda d: d['claim'][0]['evidence'][0].update(cover_only=True), expected=('PASS', 0), substring='PASS', absent='C8:')
native('code/rust', 'b9-mixed-kani-pass', mixed, expected=('PASS', 0), substring='PASS', absent='C8:')
native('code/rust', 'b9-zero-kani-pass', lambda d: (weighted(d), d['claim'][0].update(evidence=[])), expected=('PASS', 0), substring='PASS', absent='C8:')
native('code/rust', 'b9-name-does-not-imply-cover-pass', lambda d: (weighted(d), d['claim'][0]['evidence'][0].update(ref='wire::check_witnessed')), expected=('PASS', 0), substring='PASS', absent='C8:')
for meaning in ('conformance', 'verification'):
    native('code/rust', 'b9-binding-cover-string-'+meaning+'-red',
           lambda d, meaning=meaning: (weighted(d), d['format'].update(profile='acceptance/'+meaning+'/code/rust'),
                                      d['claim'][0]['evidence'][0].update(cover_only='true')),
           substring='B9: cover_only must be bool')
native('code/rust', 'b9-dynamic-does-not-excuse-cover-red', lambda d: (covers(d), d['claim'][0]['evidence'].append({'kind':'unit-test'})), substring='C8:')


def legacy_cover(d):
    weighted(d)
    d['conformance']['cover_only'] = [d['claim'][0]['evidence'][0]['ref']]


native('code/rust', 'b9-legacy-cover-red', legacy_cover, substring='C8:')
# GREEN's default profile_version is 0.2.0; the WARNING-at-0.1.0-draft path needs
# that transitional version declared explicitly, or the guard is already at its 0.2 ERROR.
native('code/rust', 'b9-legacy-cover-warning', lambda d: (d['conformance'].update(cover_only=[]), d['format'].update(profile_version='0.1.0-draft')), expected=('PASS', 0), substring='WARNING: B9: [conformance].cover_only is deprecated')
native('code/rust', 'b9-legacy-cover-malformed-red', lambda d: d['conformance'].update(cover_only='harness'), substring='B9: legacy cover_only must be a list')
native('code/rust', 'b9-legacy-cover-02-red', lambda d: (d['conformance'].update(cover_only=[]), d['format'].update(profile_version='0.2')), substring='removed at 0.2')
native('code/rust', 'b9-obsolete-tally-red', lambda d: d.update(cover_tally='1/1'), substring='C8: manifest-side cover_tally')
for kind, ceiling in code_rust.TIERS.items():
    native('code/rust', 'a2-kind-'+kind+'-ceiling-pass', lambda d,k=kind,t=ceiling: d['claim'][0].update(evidence=[{'kind': k, 'epistemic_tier': t}]), expected=('PASS',0), substring='PASS')
    if ceiling != 'T1':
        native('code/rust', 'a2-kind-'+kind+'-red', lambda d,k=kind: d['claim'][0].update(evidence=[{'kind': k, 'epistemic_tier':'T1'}]), substring='A2: epistemic_tier exceeds kind ceiling')
native('code/rust', 'a2-family-ceiling-red', lambda d: d['claim'][0].update(evidence=[{'kind':'lean-theorem','family':'bmc','epistemic_tier':'T1'}]), substring='A2: epistemic_tier exceeds family ceiling T2')
native('code/rust', 'a2-weaker-tier-pass', lambda d: d['claim'][0]['evidence'][0].update(epistemic_tier='T5'), expected=('PASS',0), substring='PASS')


def artifact_wire(payload=b'fixture'):
    return 'artifact:sha-512:' + hashlib.sha512(payload).hexdigest()


# B20: code/rust declares Cargo.lock + rust-toolchain.toml as required build inputs, but only
# once a weighted claim already declares SOME build_inputs entry (opt-in-complete, mirrors B9).
native('code/rust', 'b20-no-build-inputs-declared-pass', weighted, expected=('PASS', 0), substring='PASS')
native('code/rust', 'b20-required-build-input-incomplete-red',
       lambda d: (weighted(d), d['claim'][0]['evidence'][0].update(build_inputs=[{'path': 'Cargo.lock', 'digest': artifact_wire()}])),
       substring="B20: weighted claim declares build_inputs but is missing required path(s): ['rust-toolchain.toml']")
native('code/rust', 'b20-required-build-input-complete-pass',
       lambda d: (weighted(d), d['claim'][0]['evidence'][0].update(build_inputs=[
           {'path': 'Cargo.lock', 'digest': artifact_wire(b'a')},
           {'path': 'rust-toolchain.toml', 'digest': artifact_wire(b'b')},
       ])),
       expected=('PASS', 0), substring='PASS')
# Review found that matching by basename let a correctly-digested
# but structurally-unrelated file satisfy this guard — reverted to EXACT path semantics, anchored
# to the manifest's own directory (no build-context-root locator exists to anchor a laxer match;
# `[subject]` and this binding's own declaration carry no such field). A subdirectory-prefixed
# path — even the SAME subdirectory for both required names — no longer satisfies a bare-named
# requirement (this binding's own real-usage example, `protocol_acceptance/examples/rust-delivery/
# `, now declares same-directory symlinks instead — see that example's `gen_package.py`).
native('code/rust', 'b20-required-build-input-subdirectory-path-red',
       lambda d: (weighted(d), d['claim'][0]['evidence'][0].update(build_inputs=[
           {'path': 'iban-check/Cargo.lock', 'digest': artifact_wire(b'a')},
           {'path': 'iban-check/rust-toolchain.toml', 'digest': artifact_wire(b'b')},
       ])),
       substring="B20: weighted claim declares build_inputs but is missing required path(s): ['Cargo.lock', 'rust-toolchain.toml']")
# Rejection fixture named by the review: two CORRECTLY-DIGESTED but structurally-unrelated files
# (different, unrelated directories) must not satisfy the guard merely by carrying the right
# basenames — correct digests establish those files' bytes, not their relationship to the build.
native('code/rust', 'b20-required-build-input-unrelated-mixed-directories-red',
       lambda d: (weighted(d), d['claim'][0]['evidence'][0].update(build_inputs=[
           {'path': 'unrelated-a/Cargo.lock', 'digest': artifact_wire(b'a')},
           {'path': 'unrelated-b/rust-toolchain.toml', 'digest': artifact_wire(b'b')},
       ])),
       substring="B20: weighted claim declares build_inputs but is missing required path(s): ['Cargo.lock', 'rust-toolchain.toml']")
native('code/rust', 'b20-required-build-input-unweighted-pass',
       lambda d: d['claim'][0]['evidence'][0].update(build_inputs=[{'path': 'Cargo.lock', 'digest': artifact_wire()}]),
       expected=('PASS', 0), substring='PASS')


def selected_meaning():
    from types import SimpleNamespace
    d = document()
    d['claim'][0]['evidence'][0]['epistemic_tier'] = 'T2'
    seen = []
    def selected(path, namespace):
        seen.append((path.name, namespace))
        return SimpleNamespace(FAMILIES={'bmc': 'T3'})
    with patch.object(C, '_module', selected):
        findings = code_rust.check(d, C.Context(Path('acceptance.toml'), None))
    assert seen == [('conformance.py', 'meaning')], seen
    assert any(f.severity == 'error' and 'family ceiling T3' in f.message for f in findings), findings
    return 'FAIL A2: selected conformance family ceiling T3'
CASES.append(('code/rust', 'a2-selected-meaning-family-red', ('FAIL',1), 'selected conformance family ceiling T3', selected_meaning))


def composed(name, change=lambda f: None, expected=('PASS', 0), substring='PASS', *, meaning_only=False, native_meaning=False, absent=''):
    def execute():
        # A native-evidence variant: these tests manipulate claim[0]'s
        # evidence record directly and have nothing to do with the B8 lowering.
        f = M._native_claim_fixture(); f['manifest']['format']['profile'] = M.MEANING + '/code/rust'
        change(f)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for key, filename in [('manifest','acceptance.toml'),('inventory','standard.clauses.toml'),('record','applicability.toml')]:
                (root/filename).write_bytes(M._toml_bytes(f[key]))
            (root/'evidence').mkdir()
            for n in (1,5): (root/f'evidence/record-{n}.json').write_bytes(M._fixture_record(n))
            path = root/'acceptance.toml'
            if native_meaning:
                findings = M.check(f['manifest'], C.Context(path,root))
                actual = ('FAIL',1) if any(x.severity=='error' for x in findings) else ('PASS',0)
                output = actual[0]+'\n'+'\n'.join(x.message for x in findings)
            else:
                report = C.validate(path, True, True, root=root, meaning_only=meaning_only)
                actual = C.verdict(report)
                output = actual[0]+'\n'+'\n'.join(report.errors+report.warnings+report.unknowns)
                cli = M.validate(path,root=root,meaning_only=meaning_only)
                assert (cli.verdict,cli.exit_code)==actual,cli.render()
            assert actual == expected,(actual,output)
            assert substring in output,(substring,output)
            assert not absent or absent not in output,(absent,output)
            return output
    CASES.append(('conformance',name,expected,substring,execute))


composed('c3-new-encoding-pass', absent='B5: legacy')
composed('c3-legacy-warning', lambda f: (f['manifest']['format'].update(profile_version='0.1.0-draft'), f['manifest']['claim'][2].update(status='gap',grade='out-of-scope',scope_ref='applicability.toml')), substring='B5: legacy')
composed('c3-mixed-status-red', lambda f: f['manifest']['claim'][2].update(status='gap'), ('FAIL',1), 'B5: applicability not-applicable')
composed('c3-new-evidence-red', lambda f: f['manifest']['claim'][2].update(evidence=copy.deepcopy(f['manifest']['claim'][0]['evidence'])), ('FAIL',1), 'C3:')
composed('c3-new-weight-red', lambda f: f['manifest']['claim'][2].update(weight='weighted'), ('FAIL',1), 'C3:')
composed('c3-reason-drift-red', lambda f: f['manifest']['claim'][2].update(applicability_reason='Other scope'), ('FAIL',1), 'C7:')
composed('c3-excluded-scope-red', lambda f: f['manifest']['claim'][3].pop('scope_ref'), ('FAIL',1), 'C4:')
composed('c8-moved-meaning-pass', lambda f: covers(f['manifest']), native_meaning=True, absent='C8:')
composed('c8-moved-scoped-red', lambda f: covers(f['manifest']), ('FAIL',1), 'C8:', meaning_only=True)
composed('c8-moved-binding-red', lambda f: covers(f['manifest']), ('FAIL',1), 'C8:')
composed('c-control-kind-red', lambda f: f['manifest']['claim'][0]['evidence'][0].update(control={'kind':'made-up','of_claim':'CONF/EWF-1','expectation':'red','observed':'red'}), ('FAIL',1), 'control.kind must be one of')
composed('c-weighted-grade-requires-recipe-red', lambda f: (weighted(f['manifest']), f['manifest']['claim'][0].pop('self_verify')), ('FAIL',1), "requires a [claim.self_verify] table")
composed('c-weighted-grade-requires-bounds-red', lambda f: (weighted(f['manifest']), f['manifest']['claim'][0].pop('bounds')), ('FAIL',1), "requires a claim-level 'bounds' field")
composed('c-not-covered-positive-control-red', lambda f: (weighted(f['manifest']), f['manifest']['claim'][0].update(grade='not-covered',status='gap',evidence=[])), ('FAIL',1), 'requires a nonempty self_verify.positive_control')


def cover_metadata(**metadata):
    def change(f):
        weighted(f['manifest'])
        f['manifest']['claim'][0]['evidence'][0].update(metadata)
    return change


composed('b9-cover-only-string-conformance-red', cover_metadata(cover_only='true'), ('FAIL',1), 'B9: cover_only must be bool')
composed('b9-cover-only-false-conformance-pass', cover_metadata(cover_only=False), absent='B9:')
for key in ('cover_satisfied', 'cover_total'):
    for label, value in [('bool', True), ('string', '1'), ('negative', -1)]:
        fields = {'cover_satisfied': 0, 'cover_total': 1, key: value}
        composed('b9-'+key+'-'+label+'-conformance-red', cover_metadata(**fields), ('FAIL',1),
                 'B9: '+key+(' must be nonnegative' if label=='negative' else ' must be int'))
    composed('b9-'+key+'-unpaired-conformance-red', cover_metadata(**{key: 0}), ('FAIL',1), 'B9: cover_satisfied / cover_total must be a pair')
composed('b9-cover-count-order-conformance-red', cover_metadata(cover_satisfied=2, cover_total=1), ('FAIL',1), 'B9: cover_satisfied exceeds cover_total')
composed('b9-cover-count-zero-conformance-pass', cover_metadata(cover_satisfied=0, cover_total=0), absent='B9:')
composed('b9-cover-count-equal-conformance-pass', cover_metadata(cover_satisfied=1, cover_total=1), absent='B9:')


def malformed_format():
    fixture = M._green_fixture()
    fixture['manifest']['format'] = 'oops'
    error = M._run_case('c-format-not-table-indeterminate', fixture, 'INDETERMINATE', "not this check's profile")
    assert error is None, error
    return "INDETERMINATE not this check's profile; library and CLI exit 2"
CASES.append(('conformance', 'c-format-not-table-indeterminate', ('INDETERMINATE',2), "not this check's profile", malformed_format))


def digests():
    for domain, fn in [('normative-reference:',M.normative_digest),('applicability-record:',M.applicability_digest),('manifest:',M.source_manifest_digest)]:
        raw=b'\x00fixture\xff\r\n'
        assert fn(raw)==domain+'sha-512:'+hashlib.sha512(domain.encode()+raw).hexdigest()
    return 'PASS byte-identical three domain digests'
CASES.append(('conformance','c-digests-byte-identical',('PASS',0),'byte-identical',digests))


def selftest(scope=None):
    cases=[c for c in CASES if scope is None or c[0]==scope]
    errors=[]
    for _, name, expected, substring, operation in cases:
        try:
            output=operation()
            assert substring in output,(substring,output)
            print(f'PASS {name}: expected {expected}; contains {substring!r}')
        except Exception as exc:
            errors.append(name)
            print(f'FAIL {name}: {exc}')
    print(f'SELFTEST {"FAIL" if errors else "PASS"}: {len(cases)} {scope or "binding-chain"} fixtures')
    return int(bool(errors))


if __name__=='__main__':
    sys.exit(selftest())
