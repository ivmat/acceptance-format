"""Named class fixtures; same battery is consumed by both entry points and mutation audit."""
from __future__ import annotations
import copy
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import check_core as C
import hashdomains as H


def toml(value):
    if isinstance(value, dict): return '{' + ', '.join(json.dumps(k) + ' = ' + toml(v) for k, v in value.items()) + '}'
    if isinstance(value, list): return '[' + ', '.join(toml(v) for v in value) + ']'
    return json.dumps(value)


def encode(doc):
    return ('\n'.join(json.dumps(k) + ' = ' + toml(v) for k, v in doc.items()) + '\n').encode()


def base():
    # F10 (2026-09-24): [format].profile is REQUIRED at 0.3.0 -- no
    # compatibility default. Every case built on this base() states its own profile explicitly;
    # callers needing a different meaning/leaf already overwrite this afterward.
    return {'format': {'id': 'acceptance/0', 'profile': 'acceptance/verification'}, 'subject': {'name': 'document', 'kind': 'doc', 'digest': H.digest('subject:', b'doc')},
            'spec': {'path': 'SPEC.md', 'version': 'v1', 'axis': 'document assertions'},
            'coverage': {'clauses_total': 1, 'claims_total': 1},
            'claim': [{'id': 'C-1', 'clause': '1', 'item': 'doc', 'statement': 'document is readable', 'status': 'evidenced', 'grade': 'inspection-argued', 'weight': 'unweighted', 'band': 'A0',
                       'evidence': [{'kind': 'human-review', 'family': 'judgment', 'ref': 'review', 'tool': 'reviewer', 'reviewer': 'reader', 'result': 'pass', 'record': 'record.json', 'epistemic_tier': 'T5', 'record_hash': H.digest('record:', b'{"score": 99}')}]}]}


@contextmanager
def workspace():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root/'SPEC.md').write_text('Governing document.\n')
        (root/'record.json').write_text('{"score": 99}')
        yield root


def evaluate(doc, root, **kwargs):
    path = root/'acceptance.toml'
    path.write_bytes(encode(doc))
    return C.validate(path, False, root=root, **kwargs)


def diagnostic(rep):
    return '\n'.join(rep.errors + rep.warnings + rep.unknowns)


def result(rep):
    return C.verdict(rep), diagnostic(rep)


# Entries: name, expected verdict/exit, asserted substring, operation.
CASES = []


def add(name, change=lambda d: None, verdict='FAIL', substring='', absent='', setup=None, **kwargs):
    def execute():
        with workspace() as root:
            d = base(); change(d)
            if setup: setup(d, root)
            rep = evaluate(d, root, **kwargs)
            actual, messages = result(rep)
            expected = (verdict, 1 if verdict == 'FAIL' else 2 if verdict == 'INDETERMINATE' else 0)
            assert actual == expected, (actual, messages)
            assert substring in messages, (substring, messages)
            assert not absent or absent not in messages, (absent, messages)
    CASES.append((name, verdict, substring or ('absent: '+absent if absent else 'verdict'), execute))


add('b1-document-digest-pass', verdict='PASS')
add('b1-two-identities', lambda d:d['subject'].update(commit='a'*40, dirty=False), substring='B1: retrospective')
add('b1-no-identity', lambda d:d['subject'].pop('digest'), substring='exactly one certified identity')
add('b1-invalid-digest', lambda d:d['subject'].update(digest='bad'), substring='B1: subject digest')
add('b1-prospective-missing-read', lambda d:d['subject'].update(mode='prospective', commit='0'*40), substring='read_at_commit is REQUIRED')
add('b1-prospective-unpinned', lambda d:d['subject'].update(mode='prospective', commit='0'*40, read_at_commit='unpinned'), verdict='PASS-PROSPECTIVE')
add('b1-prospective-digest-unpinned', lambda d:d['subject'].update(mode='prospective', read_at_digest='unpinned'), verdict='PASS-PROSPECTIVE')
add('b1-prospective-two-reads', lambda d:d['subject'].update(mode='prospective', read_at_commit='unpinned', read_at_digest='unpinned'), substring='exactly one read-locator')
add('b1-components-shape', lambda d:d['subject'].update(components=[]), substring='B1: components')

def components(d):
    d['subject'].pop('digest');d['subject']['components']=[{'name':'a','digest':H.digest('subject:',b'a')}, {'name':'b','commit':'a'*40,'dirty':False}]
def certified_components(d):
    components(d)
    lines = 'a=content-digest:'+H.digest('subject:',b'a')+'\nb=git-revision:'+'a'*40+'\n'
    d['subject']['digest'] = H.digest('subject:',lines.encode())
add('b1-components-positive',certified_components,verdict='PASS')
add('b2-unknown-token',lambda d:d['claim'][0].update(band='unknown'),substring='B2:')
add('b2-control-wrong-claim',lambda d:d['claim'][0]['evidence'][0].update(control={'kind':'mutation','expectation':'red','observed':'red','of_claim':'other'}),substring='does not name this claim')
add('b2-judgment-control-no-lift',lambda d:(d['claim'][0].update(band='A1'),d['claim'][0]['evidence'][0].update(control={'kind':'mutation','expectation':'red','observed':'red','of_claim':'C-1'})),substring='B2:')
add('b3-undeclared-family',lambda d:d['claim'][0]['evidence'][0].update(family='alien'),substring='B3:')
add('b3-tier-above-ceiling',lambda d:d['claim'][0]['evidence'][0].update(epistemic_tier='T1'),substring='B3:')
add('b4-undeclared-kind',lambda d:d['claim'][0]['evidence'][0].update(kind='alien'),substring='unknown evidence kind')
add('b4-required-extra',lambda d:d['claim'][0]['evidence'][0].pop('reviewer'),substring="missing required field 'reviewer'")

def na(d):
    d['claim'][0].update(status='not-applicable', applicability='not-applicable', applicability_reason='No relevant surface', grade='out-of-scope', evidence=[])

def na_change(fn):
    def change(d):na(d);fn(d['claim'][0])
    return change
add('b5-not-applicable-positive',na,verdict='INDETERMINATE')
add('b5-not-applicable-with-evidence',na_change(lambda c:c.update(evidence=base()['claim'][0]['evidence'])),substring='B5: not-applicable / excluded carries no evidence')
add('b5-not-applicable-no-reason',na_change(lambda c:c.pop('applicability_reason')),substring='B5: applicability_reason')
add('b5-not-applicable-weighted',na_change(lambda c:c.update(weight='weighted')),substring='B5: not-applicable / excluded must be unweighted')
add('b5-excluded-as-not-applicable',na_change(lambda c:c.update(applicability='excluded')),substring='B5: excluded must stay status gap')
add('b5-not-applicable-bad-grade',na_change(lambda c:c.update(grade='probe')),substring='B5: not-applicable / excluded grade')
add('b5-invalid-applicability',lambda d:d['claim'][0].update(applicability='never'),substring='B5: applicability must')
add('b5-excluded-positive',na_change(lambda c:c.update(status='gap',applicability='excluded',scope_ref='SPEC.md')),verdict='PASS-PROSPECTIVE')
add('b5-legacy-outside-conformance-red',na_change(lambda c:c.update(status='gap',scope_ref='SPEC.md#scope')),verdict='FAIL',substring='B5: legacy')
add('b6-relative-escape',lambda d:d['spec'].update(path='../outside.md'),substring='B6: spec.path: path escapes')
add('b6-absolute',lambda d:d['spec'].update(path='/outside.md'),substring='B6: spec.path: absolute')
add('b6-symlink-escape',lambda d:d['spec'].update(path='escape'),substring='B6: spec.path: path escapes',setup=lambda d,r:(r/'escape').symlink_to(r.parent/'outside'))
add('b6-mirror-digest-mismatch',lambda d:d['spec'].update(provenance='external',version=H.digest('normative-reference:',b'wrong')),substring='digest differs')
add('b6-mirror-digest-pass',lambda d:None,verdict='PASS',setup=lambda d,r:d['spec'].update(provenance='external',version=H.digest('normative-reference:',(r/'SPEC.md').read_bytes())))
add('b7-nested-score',lambda d:d.update(nested={'inside':{'score':1}}),substring='B7: aggregate key')
add('b7-reserved-without-calibration',lambda d:d.update(nested={'alpha':1}),substring='B7:')
add('b7-calibrated-pass',lambda d:d['claim'][0]['evidence'][0].update(alpha=1,calibration='SPEC.md'),verdict='PASS')
add('b7-opaque-record-score-pass',verdict='PASS')
add('b16-record-content-mismatch',lambda d:d['claim'][0]['evidence'][0].update(record_hash=H.digest('record:',b'wrong')),substring='digest differs')
add('b7-inventory-score',verdict='FAIL',substring='B7: aggregate key',setup=lambda d,r:((r/'inventory.toml').write_text('nested = {score = 1}\n'),d['spec'].update(path='inventory.toml')))
add('b10-partial-gaps-warning',lambda d:d['claim'][0].update(status='partial'),verdict='PASS',substring='B10: legacy partial')
add('b10-partial-gaps-present',lambda d:d['claim'][0].update(status='partial',gaps=['No completeness evidence']),verdict='PASS',absent='B10:')
add('b10-invalid-gaps',lambda d:d['claim'][0].update(gaps='none'),substring='B10: gaps must')
add('b11-empty-manifest',lambda d:(d.update(claim=[]),d['coverage'].update(claims_total=0)),substring='B11: zero')
add('b11-coverage-mismatch',lambda d:d['coverage'].update(claims_total=2),substring='does not match actual')
add('b11-all-not-applicable',na,verdict='INDETERMINATE')
add('b11-ordinary-pass',verdict='PASS')
add('b11-prospective-precedes-scope',lambda d:d['subject'].update(mode='prospective',read_at_digest='unpinned'),verdict='PASS-PROSPECTIVE',meaning_only=True)
add('b11-class-error-precedes-unknown',lambda d:(d['subject'].pop('digest'),d['format'].update(profile='acceptance/missing')),substring='B1:')
add('b12-profile-required',lambda d:d['format'].pop('profile'),substring='B12: [format].profile is REQUIRED')
add('b12-reserved-core',lambda d:d['format'].update(profile='acceptance/core'),substring='B12:')
add('b12-malformed-id',lambda d:d['format'].update(profile='acceptance/verification/../bad'),substring='B12:')
add('b12-unknown-prefix',lambda d:(d['format'].update(profile='acceptance/unknown'),d['claim'][0].pop('band')),verdict='INDETERMINATE',substring='B12: unknown')
add('b13-missing-half',lambda d:d['format'].update(profile='acceptance/verification/missing'),verdict='INDETERMINATE',substring='B13: missing binding')
add('b13-unknown-suffix-scoped',lambda d:d['format'].update(profile='acceptance/verification/missing'),verdict='INDETERMINATE',substring='unknown suffix',meaning_only=True)
add('b13-binding-only-scope',verdict='PASS',binding_only=True)
add('b15-slice-warning',lambda d:d['coverage'].update(denominator='slice',slice_note='selected assertions'),verdict='PASS',substring='B15: legacy slice should disclose slice_boundary')
add('b15-slice-boundary-present',lambda d:d['coverage'].update(denominator='slice',slice_note='selected assertions',slice_boundary='Section 1 only'),verdict='PASS',absent='B15:')
add('b9-cover-metadata-positive',lambda d:d['claim'][0]['evidence'][0].update(cover_only=True,cover_satisfied=1,cover_total=2),verdict='PASS')
add('b9-cover-metadata-invalid',lambda d:d['claim'][0]['evidence'][0].update(cover_only='yes'),substring='B9:')


# B19: the generic spec inventory. base()'s single claim already cites clause '1', so an
# inventory with one item id '1' is full coverage with no further fixture plumbing.
def inv_item(item_id, **extra):
    row = {'id': item_id, 'title': f'Item {item_id}'}
    row.update(extra)
    return row


def inventory_doc(items):
    return {'inventory': {'id': 'ewf', 'title': 'Example inventory', 'source': 'SPEC.md'},
            'item': [inv_item(i, **e) for i, e in items]}


def inventory_setup_raw(raw, digest=None, omit_digest=False):
    def setup(d, r):
        (r/'inventory.toml').write_bytes(raw)
        d['spec']['inventory'] = 'inventory.toml'
        if not omit_digest:
            d['spec']['inventory_digest'] = digest if digest is not None else H.digest('inventory:', raw)
    return setup


def inventory_setup(items=(('1', {}),), digest=None, omit_digest=False):
    return inventory_setup_raw(encode(inventory_doc(items)), digest=digest, omit_digest=omit_digest)


def two_item_claims(d):
    extra = copy.deepcopy(d['claim'][0])
    extra.update(id='C-2', clause='2')
    d['claim'].append(extra)
    d['coverage'].update(claims_total=2)


add('b19-pass-single-item',verdict='PASS',setup=inventory_setup())
add('b19-digest-missing',setup=inventory_setup(omit_digest=True),substring='B19: [spec].inventory_digest must be')
add('b19-digest-malformed',setup=inventory_setup(digest='nope'),substring='B19: [spec].inventory_digest must be')
add('b19-digest-mismatch',setup=inventory_setup(digest=H.digest('inventory:',b'wrong')),substring='B19: spec inventory digest mismatch')
add('b19-missing-item-claim',setup=inventory_setup(items=(('1',{}),('2',{}))),substring="B19: spec inventory item(s) missing a claim: ['2']")
add('b19-duplicate-item-id',setup=inventory_setup(items=(('1',{}),('1',{}))),substring="B19: duplicate inventory item id(s): ['1']")
add('b19-invalid-item-id',setup=inventory_setup(items=(('bad id',{}),)),substring='B19: item[0].id must match')
add('b19-invalid-firmness',setup=inventory_setup(items=(('1',{'firmness':'maybe'}),)),substring="firmness must be one of ['draft', 'firm']")
add('b19-firmness-draft-pass',verdict='PASS',setup=inventory_setup(items=(('1',{'firmness':'draft'}),)))
add('b19-unknown-clause',lambda d:d['claim'][0].update(clause='99'),setup=inventory_setup(),substring="cites id absent from spec inventory: '99'")
add('b19-addition-on-known-id',lambda d:d['claim'][0].update(addition=True),setup=inventory_setup(),substring="addition must not cite a declared inventory item id")
add('b19-item-ref-pass',verdict='PASS',setup=inventory_setup(items=(('1',{'ref':'S-1'}),)))
add('b19-item-ref-bad-shape',setup=inventory_setup(items=(('1',{'ref':5}),)),substring="field 'ref' must be a nonempty string")
add('b19-parent-field-pass',two_item_claims,verdict='PASS',setup=inventory_setup(items=(('1',{}),('2',{'parent':'1'}))))
add('b19-header-missing',setup=inventory_setup_raw(encode({'item':[{'id':'1','title':'One'}]})),substring='B19: [inventory] must have nonempty id, title and source')
add('b19-no-items',setup=inventory_setup_raw(encode({'inventory':{'id':'ewf','title':'Example','source':'SPEC.md'}})),substring='B19: spec inventory must declare at least one [[item]]')
add('b19-absent-is-no-op',verdict='PASS')


# B20: typed toolchain and build-input identity, plus a tightened captured_at_commit shape.
# base()'s single evidence entry (kind='human-review') already satisfies every universal
# field, so these fixtures only add/mutate the new optional fields.
add('b20-toolchain-commit-pass',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[{'name':'tool-a','commit':'a'*40}]),verdict='PASS')
add('b20-toolchain-digest-pass',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[{'name':'tool-b','digest':H.digest('artifact:',b'bin')}]),verdict='PASS')
add('b20-toolchain-empty-list',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[]),substring='toolchain must be a nonempty list of tables when present (B20)')
add('b20-toolchain-missing-name',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[{'commit':'a'*40}]),substring='name must be a nonempty string (B20)')
add('b20-toolchain-bad-version',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[{'name':'t','commit':'a'*40,'version':''}]),substring='version must be a nonempty string when present (B20)')
add('b20-toolchain-bad-commit',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[{'name':'t','commit':'short'}]),substring='commit must be 40 lowercase hex characters when present (B20)')
add('b20-toolchain-bad-digest',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[{'name':'t','digest':'nope'}]),substring="digest must be an 'artifact:sha-512:<128-hex>' wire digest when present (B20)")
add('b20-toolchain-no-commit-or-digest',lambda d:d['claim'][0]['evidence'][0].update(toolchain=[{'name':'t'}]),substring='at least one of commit or digest is required (B20)')
add('b20-build-inputs-empty-list',lambda d:d['claim'][0]['evidence'][0].update(build_inputs=[]),substring='build_inputs must be a nonempty list of tables when present (B20)')
add('b20-build-inputs-missing-path',lambda d:d['claim'][0]['evidence'][0].update(build_inputs=[{'digest':H.digest('artifact:',b'x')}]),substring='path must be a nonempty string (B20)')
add('b20-build-inputs-bad-digest',lambda d:d['claim'][0]['evidence'][0].update(build_inputs=[{'path':'input.txt','digest':'nope'}]),substring="digest must be an 'artifact:sha-512:<128-hex>' wire digest (B20)")
add('b20-captured-at-commit-short',lambda d:d['claim'][0]['evidence'][0].update(captured_at_commit='deadbee'),substring='captured_at_commit must be 40 lowercase hex characters when present (B20)')
add('b20-captured-at-commit-pass',lambda d:d['claim'][0]['evidence'][0].update(captured_at_commit='a'*40),verdict='PASS')


# B21: evidence-only assurance metadata -- a structural/proof-coverage metric and a declared
# tool-qualification note. Both DECLARED ONLY (shape checked, never validated for truth).
add('b21-coverage-pass',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'branch','value':0.85}),verdict='PASS')
add('b21-coverage-with-of-pass',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'mcdc','value':1,'of':'decisions in fn parse_der'}),verdict='PASS')
add('b21-coverage-not-a-table',lambda d:d['claim'][0]['evidence'][0].update(coverage='branch'),substring='coverage must be a table when present (B21)')
add('b21-coverage-bad-metric',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'lines','value':0.5}),substring="coverage.metric must be one of ['branch', 'decision', 'mcdc', 'proof-obligation', 'statement']")
add('b21-coverage-value-over-one',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'statement','value':1.5}),substring='coverage.value must be a number in [0, 1]')
add('b21-coverage-value-negative',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'statement','value':-0.1}),substring='coverage.value must be a number in [0, 1]')
add('b21-coverage-value-not-a-number',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'statement','value':'high'}),substring='coverage.value must be a number in [0, 1]')
add('b21-coverage-value-bool-refused',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'statement','value':True}),substring='coverage.value must be a number in [0, 1]')
add('b21-coverage-of-empty',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'statement','value':0.5,'of':''}),substring='coverage.of, if present, must be a nonempty string (B21)')
add('b21-coverage-unknown-field',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'statement','value':0.5,'denominator':7}),substring="coverage carries unknown field(s) ['denominator']")
add('b21-tool-qualification-pass',lambda d:d['claim'][0]['evidence'][0].update(tool_qualification={'basis':'vendor DO-330 TQL-1 letter, reference 2026-004'}),verdict='PASS')
add('b21-tool-qualification-with-level-pass',lambda d:d['claim'][0]['evidence'][0].update(tool_qualification={'level':'TQL-1','basis':'vendor letter'}),verdict='PASS')
add('b21-tool-qualification-not-a-table',lambda d:d['claim'][0]['evidence'][0].update(tool_qualification='TQL-1'),substring='tool_qualification must be a table when present (B21)')
add('b21-tool-qualification-missing-basis',lambda d:d['claim'][0]['evidence'][0].update(tool_qualification={'level':'TQL-1'}),substring='tool_qualification.basis must be a nonempty string (B21)')
add('b21-tool-qualification-level-empty',lambda d:d['claim'][0]['evidence'][0].update(tool_qualification={'level':'','basis':'vendor letter'}),substring='tool_qualification.level, if present, must be a nonempty string (B21)')
add('b21-tool-qualification-unknown-field',lambda d:d['claim'][0]['evidence'][0].update(tool_qualification={'basis':'x','vendor':'acme'}),substring="tool_qualification carries unknown field(s) ['vendor']")
add('b21-both-fields-pass',lambda d:d['claim'][0]['evidence'][0].update(coverage={'metric':'decision','value':0.9},tool_qualification={'basis':'x'}),verdict='PASS')
add('b21-absent-is-no-op',verdict='PASS')


def build_input_setup(content=b'lockbytes', wrong_digest=False):
    def setup(d, r):
        (r/'input.txt').write_bytes(content)
        digest = H.digest('artifact:', b'other-bytes') if wrong_digest else H.digest('artifact:', content)
        d['claim'][0]['evidence'][0]['build_inputs'] = [{'path': 'input.txt', 'digest': digest}]
    return setup
add('b20-build-inputs-digest-pass',verdict='PASS',setup=build_input_setup())
add('b20-build-inputs-digest-mismatch',setup=build_input_setup(wrong_digest=True),substring='build-input digest differs from declared artifact:sha-512 hash')
add('b20-build-inputs-unresolvable-warn',lambda d:d['claim'][0]['evidence'][0].update(build_inputs=[{'path':'missing.txt','digest':H.digest('artifact:',b'x')}]),verdict='PASS',substring='build-input pointer does not exist')


def synthetic(name, expected, substring, operation):
    def execute():
        actual, messages = operation()
        assert actual == expected, (actual, messages)
        assert substring in messages, (substring, messages)
    CASES.append((name,expected,substring,execute))


def addition_reported_case():
    with workspace() as root:
        d = base()
        extra = copy.deepcopy(d['claim'][0])
        extra.update(id='C-2', clause='99', addition=True, status='gap', grade='ungraded', evidence=[])
        d['claim'].append(extra)
        d['coverage'].update(claims_total=2)
        inventory_setup()(d, root)
        rep = evaluate(d, root)
        assert getattr(rep, 'n_inventory_additions', None) == 1, rep.n_inventory_additions
        return C.verdict(rep)[0], diagnostic(rep) + '\n' + '\n'.join(getattr(rep, 'notes', []))
synthetic('b19-addition-reported', 'PASS', 'addition claim(s) beyond the spec inventory', addition_reported_case)


def build_input_strict():
    with workspace() as root:
        d = base()
        d['claim'][0]['evidence'][0]['build_inputs'] = [{'path': 'missing.txt', 'digest': H.digest('artifact:', b'x')}]
        path = root / 'acceptance.toml'
        path.write_bytes(encode(d))
        rep = C.validate(path, True, root=root)
        return C.verdict(rep)[0], diagnostic(rep)
synthetic('b20-build-inputs-unresolvable-strict-red', 'FAIL', 'build-input pointer does not exist', build_input_strict)


def bandless(with_band):
    with workspace() as root:
        d=base();rep=C.Reporter('synthetic');rep.ladder=None
        if not with_band:d['claim'][0].pop('band')
        C.check_band_mechanism(rep,d['claim'][0])
        return bool(rep.errors),'\n'.join(rep.errors)
synthetic('b2-bandless-meaning-rejects-band',True,'B2:',lambda:bandless(True))
synthetic('b2-bandless-meaning-pass',False,'',lambda:bandless(False))


def binding(admits=('doc',),identity=('content-digest',),child=None):
    with workspace() as root:
        d=base();rep=evaluate(d,root)
        bindings=[(None,{'admits':list(admits),'identity':list(identity)})]
        if child:bindings.append((None,child))
        C.check_binding_chain(rep,bindings,d)
        return bool(rep.errors),diagnostic(rep)
synthetic('b14-kind-not-admitted',True,'B14:',lambda:binding(('rust-crate',)))
synthetic('b1-code-digest-not-admitted',True,'B1: binding',lambda:binding(identity=('git-revision',)))
synthetic('b17-admits-widens',True,'B17: admits',lambda:binding(child={'admits':['doc','tool'],'identity':['content-digest']}))
synthetic('b17-identity-widens',True,'B17: identity',lambda:binding(child={'admits':['doc'],'identity':['content-digest','git-revision']}))
synthetic('b17-narrowing-pass',False,'',lambda:binding(admits=('doc','tool'),identity=('content-digest','git-revision'),child={'admits':['doc'],'identity':['content-digest']}))


def reference_test(mode):
    with workspace() as root:
        source=base();source['subject']['kind']='doc'
        if mode=='lean-as-kani':
            source['claim'][0]['evidence'][0].update(kind='lean-theorem',family='kernel',axioms=[],semantics='proof kernel',epistemic_tier='T1')
        if mode=='source-core-fail':source['subject'].pop('digest')
        if mode=='source-gap':source['claim'][0].update(status='gap',grade='out-of-scope',evidence=[])
        if mode=='source-failing-record':
            source['claim'][0]['status']='partial';source['claim'][0]['evidence'][0]['result']='fail'
        if mode=='source-control':source['claim'][0]['evidence'][0]['control']={'kind':'mutation','expectation':'red','observed':'red','of_claim':'C-1'}
        if mode=='source-unknown':source['format']['profile']='acceptance/verification/missing'
        if mode=='cross-ladder':source['claim'][0].pop('band');source['format']['profile']='acceptance/bandless'
        raw=encode(source);(root/'source.toml').write_bytes(raw)
        d=base();claim=d['claim'][0];claim['evidence']=[{'kind':'acceptance-claim','family':'reference','result':'pass','manifest':'source.toml','manifest_hash':H.digest('manifest:',raw),'claim':'C-1','records':[H.digest('record:',b'{"score": 99}')]}]
        ev=claim['evidence'][0]
        if mode=='missing-claim':ev['claim']='absent'
        if mode=='wrong-hash':ev['manifest_hash']=H.digest('manifest:',b'wrong')
        if mode=='missing-records':ev.pop('records')
        if mode=='empty-records':ev['records']=[]
        if mode in ('wrong-record','lean-as-kani'):ev['records']=[H.digest('record:',b'kani-impostor')]
        if mode=='own-control':ev['control']={'kind':'mutation','expectation':'red','observed':'red','of_claim':'C-1'}
        if mode=='weighted':claim['weight']='weighted'
        if mode=='band-above':claim['band']='A1'
        if mode=='tier-above':ev['epistemic_tier']='T1'
        if mode=='unreadable':ev['manifest']='missing.toml'
        if mode=='unparseable':raw=b'not = [valid';(root/'source.toml').write_bytes(raw);ev['manifest_hash']=H.digest('manifest:',raw)
        ev.update(ref=ev['manifest']+'#'+ev['claim'], tool='fixture@1', record=ev['manifest'], record_hash=ev['manifest_hash'])
        stack=(ev['manifest_hash'],) if mode=='cycle' else tuple(H.digest('manifest:',str(i).encode()) for i in range(5)) if mode=='depth' else ()
        oldroot=C.MODULE_ROOT
        if mode=='cross-ladder':
            profiles=root/'modules/profiles';profiles.mkdir(parents=True);(profiles/'bandless.py').write_text('FAMILIES={"judgment":"T5"}\nKINDS={}\ndef check(doc,ctx): return []\n')
            # Keep verification available for the referencing side.
            (profiles/'verification.py').write_text((oldroot/'profiles/verification.py').read_text())
            C.MODULE_ROOT=root/'modules'
        try: rep=evaluate(d,root,_stack=stack)
        finally:C.MODULE_ROOT=oldroot
        return C.verdict(rep)[0],diagnostic(rep)

for mode,expected,message in [
    ('pass','PASS',''),('wrong-hash','FAIL','B8: source manifest hash mismatch'),('source-core-fail','FAIL','B8: source manifest fails'),
    ('source-failing-record','FAIL','passing non-control'),('missing-claim','FAIL','B8: source claim'),('source-gap','FAIL','B8: source claim'),('source-control','FAIL','passing non-control'),('own-control','FAIL','controls do not transfer'),
    ('weighted','FAIL','reference-only claim'),('band-above','FAIL','B8: reference band'),('cross-ladder','FAIL','B8: cross-ladder'),
    ('cycle','INDETERMINATE','B8: cycle'),('depth','INDETERMINATE','reference depth exceeds 4 edges'),('wrong-record','FAIL','passing non-control'),
    ('lean-as-kani','FAIL','passing non-control'),('tier-above','FAIL','B3/B8:'),('missing-records','FAIL','B8: records'),('empty-records','FAIL','B8: records'),
    ('source-unknown','INDETERMINATE','source manifest is INDETERMINATE'),('unreadable','INDETERMINATE','unreadable source'),('unparseable','INDETERMINATE','source manifest is INDETERMINATE')]:
    synthetic('b8-'+mode,expected,message,lambda m=mode:reference_test(m))


def domain_case(domain):
    wire=H.digest(domain,b'fixture')
    import hashlib
    expected=domain+'sha-512:'+hashlib.sha512(domain.encode()+b'fixture').hexdigest()
    assert wire == expected
    assert H.parse(wire) == (domain,expected.rsplit(':',1)[1])
for domain in sorted(H.DOMAINS):
    CASES.append(('b16-'+domain[:-1]+'-wire','PASS','exact digest and parsed domain',lambda d=domain:domain_case(d)))


def module_case(mode):
    with workspace() as root:
        original_root, original_docs = C.MODULE_ROOT, C.BINDING_DOC_ROOT
        modules=root/'modules'; profiles=modules/'profiles';bindings=modules/'bindings';docs=root/'binding-docs'
        profiles.mkdir(parents=True);bindings.mkdir();docs.mkdir()
        (profiles/'verification.py').write_text((original_root/'profiles/verification.py').read_text())
        (profiles/'plain.py').write_text('FAMILIES={"judgment":"T5"}\nKINDS={}\nASSERTION_SURFACES=("assertions.inventory",)\nAGGREGATES={"rating"}\ndef check(doc,ctx):\n    from check_core import Finding\n    doc.clear()\n    return [Finding("error","B13: meaning delta failed")]\n')
        (bindings/'document.py').write_text('def check(doc,ctx): return []\n')
        (docs/'document.md').write_text('```toml\nadmits=["doc"]\nidentity=["content-digest"]\n```\n')
        d=base();d['format']['profile']='acceptance/verification/document'
        if mode=='missing-doc':(docs/'document.md').unlink()
        if mode=='admission':(docs/'document.md').write_text('```toml\nadmits=["tool"]\nidentity=["content-digest"]\n```\n')
        if mode=='identity':(docs/'document.md').write_text('```toml\nadmits=["doc"]\nidentity=["git-revision"]\n```\n')
        if mode in ('profile-adds','cannot-suppress','surface','extension'):
            d['format']['profile']='acceptance/plain';d['claim'][0].pop('band')
            if mode=='cannot-suppress':d['subject'].pop('digest')
            if mode=='surface':d['assertions']={'inventory':'surface.toml'};(root/'surface.toml').write_text('score=1\n')
            if mode=='extension':d['metadata']={'rating':3}
        if mode=='broken-binding-scoped':(bindings/'document.py').write_text('raise RuntimeError("unavailable")\n')
        if mode=='unknown-meaning-binding-only':d['format']['profile']='acceptance/absent/document'
        if mode=='binding-adds':(bindings/'document.py').write_text('def check(doc,ctx):\n    from check_core import Finding\n    return [Finding("error","B13: binding delta failed")]\n')
        if mode=='unknown-before-profile':
            d['format']['profile']='acceptance/plain/missing';d['claim'][0].pop('band')
        if mode=='nonempty-bandless':
            d['format']['profile']='acceptance/plain'
        if mode=='narrow-chain':
            (bindings/'document_restricted.py').write_text('def check(doc,ctx): return []\n')
            (docs/'document').mkdir();(docs/'document/restricted.md').write_text('```toml\nadmits=["doc"]\nidentity=["content-digest"]\n```\n')
            d['format']['profile']='acceptance/verification/document/restricted'
        C.MODULE_ROOT,C.BINDING_DOC_ROOT=modules,docs
        try:rep=evaluate(d,root,meaning_only=mode=='broken-binding-scoped',binding_only=mode=='unknown-meaning-binding-only')
        finally:C.MODULE_ROOT,C.BINDING_DOC_ROOT=original_root,original_docs
        return C.verdict(rep)[0],diagnostic(rep)

for mode,expected,message in [
    ('broken-binding-scoped','INDETERMINATE','B13: binding import failed document: RuntimeError: unavailable'),('unknown-meaning-binding-only','INDETERMINATE','B12: unknown meaning'),('loaded','PASS',''),('missing-doc','INDETERMINATE','B14:'),('admission','FAIL','B14:'),('identity','FAIL','B1: binding'),
    ('profile-adds','FAIL','B13: meaning delta failed'),('binding-adds','FAIL','B13: binding delta failed'),
    ('cannot-suppress','FAIL','B1: retrospective'),('unknown-before-profile','INDETERMINATE','B13: missing binding'),
    ('surface','FAIL','B7: aggregate key'),('extension','FAIL','B7: aggregate key'),('nonempty-bandless','FAIL','B2:'),('narrow-chain','PASS','')]:
    prefix='b14' if mode in ('loaded','missing-doc','admission') else 'b1' if mode=='identity' else 'b7' if mode in ('surface','extension') else 'b2' if mode=='nonempty-bandless' else 'b17' if mode=='narrow-chain' else 'b11' if mode=='unknown-before-profile' else 'b13'
    synthetic(prefix+'-'+mode,expected,message,lambda m=mode:module_case(m))


def missing_prerequisite(mode):
    with workspace() as root:
        d=base()
        if mode=='unreadable':d['spec']['path']='missing.toml'
        if mode=='unparsable':d['spec']['path']='bad.toml';(root/'bad.toml').write_text('a = [oops')
        path=root/'acceptance.toml';path.write_bytes(encode(d))
        rep=C.validate(path,False,root=None if mode=='no-root' else root)
        return C.verdict(rep)[0],diagnostic(rep)
for mode in ('no-root','unreadable','unparsable'):
    synthetic('b11-'+mode,'INDETERMINATE','B6:',lambda m=mode:missing_prerequisite(m))


def versioned_na():
    from acceptance_grammar import check_applicability_fields
    d=base();na(d);d['claim'][0].update(status='gap',scope_ref='SPEC.md#scope')
    errors,_=check_applicability_fields(d['claim'][0],'0.2')
    return bool(errors),'\n'.join(errors)
synthetic('b5-legacy-02-error',True,'B5: legacy',versioned_na)


def b18_pairs():
    import check_parity_selftest as parity
    failures=parity.run_class_field_pairs(False)
    assert not failures, failures
CASES.append(('b18-class-field-pairs','PASS','13 parsed/validated twin fields',b18_pairs))


def profile_weight_refusal():
    import tomllib
    from fixtures import legacy
    with workspace() as root:
        doc = tomllib.loads(legacy._mini_manifest(legacy._A3_CLAIM_WITH_CONTROL).replace('"A3"', '"A4"'))
        rep = evaluate(doc, root)
        assert C.verdict(rep) == ('FAIL', 1), diagnostic(rep)
        assert rep.profile_errors and not rep.class_errors, diagnostic(rep)
        assert getattr(rep, 'n_weighted', 0) == 0, rep.n_weighted
        assert rep.weight_refused, rep.weight_refused
CASES.append(('b13-profile-refuses-weight','FAIL','profile errors refuse the named claim weight',profile_weight_refusal))


def judgment_only_lift():
    d=base();claim=d['claim'][0];claim['band']='A1'
    claim['evidence'].append({'family':'bmc','result':'fail','control':{'kind':'mutation','of_claim':'C-1','expectation':'red','observed':'red'}})
    rep=C.Reporter('fixture');rep.ladder={'tokens':['A0','A1'],'control_free_ceiling':{'default':'A0'}};rep.meaning_name='plain'
    C.check_band_mechanism(rep,claim)
    assert any('B2:' in e for e in rep.errors),rep.errors
CASES.append(('b2-judgment-only-failed-carrier','FAIL','B2:',judgment_only_lift))


# 0.3.1 defect fix (`check_core.dispatch`): a caller-forced `bound_meaning` (check_acceptance.py's
# "verification meaning explicitly bound" compatibility entry — the SAME entry point protocol
# profiles.py's "acceptance/verification" package_validator reaches) discarded the declared
# `[format].profile` binding suffix even when it EQUALS the bound meaning, so an
# `acceptance/verification/code/rust` package never ran the `code/rust` binding's own `check()`
# on the check_acceptance.py-bound path — B20's build_inputs guard and B9's binding-declared
# cover-only over-claim guard (C8 here) were silently skipped. These two fixtures exercise that
# EXACT path (`bound_meaning='verification'`, matching `check_acceptance.py.validate`'s own
# `kwargs.setdefault('bound_meaning', 'verification')`) — not the ordinary unbound `check_core.py`
# dispatch every other fixture in this file already exercises, and not `bindings/code_rust.py`'s
# own isolated unit fixtures (`binding_cases.py`, which call `code_rust.check()` directly,
# bypassing `dispatch()` entirely and so could never have caught this).
def _bound_leaf_doc():
    d = base()
    d['format']['profile'] = 'acceptance/verification/code/rust'
    d['subject'].update(kind='rust-crate', commit='a' * 40, dirty=False)
    d['subject'].pop('digest', None)
    d['claim'][0].update(weight='weighted', grade='probe', band='A0',
                          bounds='bounded fixture inputs',
                          self_verify={'command': 'cargo kani', 'expect': 'SUCCESS'})
    return d


def bound_dispatch_b20_missing_build_input():
    d = _bound_leaf_doc()
    d['claim'][0]['evidence'][0].update(
        kind='unit-test', family='dynamic', cases=1,
        build_inputs=[{'path': 'Cargo.lock', 'digest': H.digest('artifact:', b'fixture')}],
    )
    with workspace() as root:
        (root / 'Cargo.lock').write_text('fixture')
        rep = evaluate(d, root, bound_meaning='verification')
        return C.verdict(rep)[0], diagnostic(rep)
synthetic(
    'bound-dispatch-b20-missing-build-input-red', 'FAIL',
    "B20: weighted claim declares build_inputs but is missing required path(s): ['rust-toolchain.toml']",
    bound_dispatch_b20_missing_build_input,
)


def bound_dispatch_b9_cover_only_over_claim():
    d = _bound_leaf_doc()
    d['claim'][0]['evidence'][0].update(
        kind='kani-harness', family='bmc', bounds='unwind=8', semantics='', cover_only=True,
    )
    with workspace() as root:
        rep = evaluate(d, root, bound_meaning='verification')
        return C.verdict(rep)[0], diagnostic(rep)
synthetic(
    'bound-dispatch-b9-cover-only-over-claim-red', 'FAIL',
    'C8: weighted cover-only kani evidence forbidden',
    bound_dispatch_b9_cover_only_over_claim,
)


# Folded 2026-09-26: a declared meaning
# that DIFFERS from a caller-forced bound meaning must be INDETERMINATE (exit 2), never a clean
# PASS -- a differ-case manifest (declares `acceptance/conformance`) run through the
# verification-bound compatibility path.
def bound_dispatch_differ_case_is_indeterminate():
    d = base()
    d['format']['profile'] = 'acceptance/conformance'
    with workspace() as root:
        rep = evaluate(d, root, bound_meaning='verification')
        return C.verdict(rep)[0], diagnostic(rep)
synthetic(
    'bound-dispatch-differ-meaning-is-INDETERMINATE-not-PASS', 'INDETERMINATE',
    "B13: declared meaning 'conformance' differs from the meaning 'verification' this entry "
    "point forces",
    bound_dispatch_differ_case_is_indeterminate,
)


from fixtures import r2_cases  # registers the additive R2 battery
from fixtures import review_cases

def run():
    failures=[]
    for name, expected, substring, operation in CASES:
        try:operation()
        except Exception as exc:failures.append(f'{name}: {type(exc).__name__}: {exc}')
    return len(CASES),failures
