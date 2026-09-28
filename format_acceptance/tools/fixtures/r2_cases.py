"""Audit R2 regression fixtures; names and asserted outcomes are reportable data."""
from .core_cases import (C, H, CASES, add, base, components, diagnostic, encode,
                         evaluate, na, synthetic, workspace)
import copy
from contextlib import contextmanager

START = len(CASES)

def components_digest(d):
    components(d)
    lines = 'a=content-digest:'+H.digest('subject:',b'a')+'\nb=git-revision:'+'a'*40+'\n'
    d['subject']['digest'] = H.digest('subject:', lines.encode())

add('b1-components-ok', components_digest, verdict='PASS')
add('b1-components-bad-name-red', lambda d:(components_digest(d),d['subject']['components'][0].update(name='a=b\n')), substring='name matching')
add('b1-components-digest-mismatch-red', lambda d:(components_digest(d),d['subject'].update(digest=H.digest('subject:',b'wrong'))), substring='components digest differs')
add('b1-components-uppercase-locator-red', lambda d:(components_digest(d),d['subject']['components'][1].update(commit='A'*40)), substring='40 lowercase hex')
add('b1-components-aggregate-case-ok', lambda d:(components_digest(d),d['subject'].update(digest='subject:sha-512:'+d['subject']['digest'].split(':')[-1].upper())), verdict='PASS')
add('b11-claims-total-mismatch-red', lambda d:d['coverage'].update(claims_total=9), substring='does not match actual')
add('b11-zero-claim-clause-red', lambda d:d['coverage'].update(clauses_total=2), substring='zero-claim clauses require')
add('b11-many-claims-per-clause-ok', lambda d:(d['claim'].append({**copy.deepcopy(d['claim'][0]),'id':'C-2'}),d['coverage'].update(claims_total=2)), verdict='PASS')
add('b11-zero-claim-clause-slice-ok', lambda d:d['coverage'].update(clauses_total=2,denominator='slice',slice_note='selected clause',slice_boundary='clause 1'), verdict='PASS')

for app in ('applicable','not-applicable','excluded'):
    for status in sorted(C.STATUSES):
        valid = (app=='applicable' and status!='not-applicable') or (app=='not-applicable' and status=='not-applicable') or (app=='excluded' and status=='gap')
        if valid:continue
        def pairing(d,a=app,s=status):
            na(d);d['claim'][0].update(applicability=a,status=s)
            if s=='parked':d['claim'][0]['parked_reason']='deferred surface'
            if s=='blocked':d['claim'][0]['blocked_by']='missing dependency'
        sub='contradicts applicability' if app=='applicable' else 'requires status not-applicable' if app=='not-applicable' else 'excluded must stay status gap'
        add(f'b5-pairing-{app}-{status}-red', pairing, substring=sub)
add('b5-pairing-inference-ok',lambda d:(na(d),d['claim'][0].pop('applicability')),verdict='INDETERMINATE',absent='B5:')

add('b6-outcome-document-missing',lambda d:d['spec'].update(path='absent.md'),verdict='INDETERMINATE',substring='unreadable document')
add('b6-outcome-document-unreadable',lambda d:d['spec'].update(path='directory'),verdict='INDETERMINATE',substring='unreadable document',setup=lambda d,r:(r/'directory').mkdir())
add('b6-outcome-document-unparsable',lambda d:d['spec'].update(path='invalid.toml'),verdict='INDETERMINATE',substring='unparsable document',setup=lambda d,r:(r/'invalid.toml').write_text('x = ['))
add('b6-outcome-record-missing-warning',lambda d:d['claim'][0]['evidence'][0].update(record='missing'),verdict='PASS',substring='record pointer does not exist')
add('b6-outcome-record-unreadable-warning',lambda d:d['claim'][0]['evidence'][0].update(record='directory'),verdict='PASS',substring='or is unreadable',setup=lambda d,r:(r/'directory').mkdir())

def strict_missing():
    with workspace() as root:
        d=base(); d['claim'][0]['evidence'][0]['record']='missing'
        path=root/'acceptance.toml';path.write_bytes(encode(d))
        rep=C.validate(path,True,root=root)
        return C.verdict(rep)[0],diagnostic(rep)
synthetic('b6-outcome-record-missing-strict-red','FAIL','record pointer does not exist',strict_missing)
add('b6-outcome-record-absolute-red',lambda d:d['claim'][0]['evidence'][0].update(record='/tmp/record'),substring='absolute path forbidden')
add('b6-outcome-record-escape-red',lambda d:d['claim'][0]['evidence'][0].update(record='../record'),substring='path escapes repository')
add('b6-outcome-pointer-malformed-red',lambda d:d['spec'].update(path=7),substring='path must be a nonempty string')
add('b16-record-hash-mismatch-red',lambda d:d['claim'][0]['evidence'][0].update(record_hash=H.digest('record:',b'wrong')),substring='record digest differs')
add('b7-calibration-missing-red',lambda d:d['claim'][0]['evidence'][0].update(alpha=1,calibration='missing.toml'),substring='B7: calibration missing')
add('b7-calibration-does-not-exempt-score-red',lambda d:d['claim'][0]['evidence'][0].update(score=1,calibration='SPEC.md'),substring='B7: aggregate key')
add('b7-calibration-unparsable-red',lambda d:d['claim'][0]['evidence'][0].update(alpha=1,calibration='bad.toml'),substring='B7: calibration missing',setup=lambda d,r:(r/'bad.toml').write_text('a=['))
add('b7-calibration-local-only-red',lambda d:d.update(calibration='SPEC.md',child={'alpha':1}),substring='without calibration')
add('b12-unknown-suffix-with-meaning-only-still-2',lambda d:d['format'].update(profile='acceptance/verification/nosuchbinding'),verdict='INDETERMINATE',substring='unknown suffix',meaning_only=True)
add('b12-known-missing-half-scoped-ok',lambda d:d['format'].update(profile='acceptance/verification/document'),verdict='PASS-MEANING-ONLY',meaning_only=True)

@contextmanager
def meaning(root, source):
    old=C.MODULE_ROOT
    modules=root/'modules';profiles=modules/'profiles';profiles.mkdir(parents=True)
    (profiles/'verification.py').write_text((old/'profiles/verification.py').read_text())
    (profiles/'plain.py').write_text(source+'\ndef check(doc,ctx): return []\n')
    C.MODULE_ROOT=modules
    try:yield
    finally:C.MODULE_ROOT=old

def custom(mode):
    with workspace() as root:
        code='FAMILIES={}\nKINDS={}'
        if mode=='unknown-ladder':code+='\nLADDER={"ladder_id":"unregistered","tokens":["A0"]}'
        if mode=='protect':code='FAMILIES={"judgment":"T1"}\nKINDS={"human-review":{"family":"judgment","extra_required":[]}}'
        with meaning(root,code):
            d=base();d['format']['profile']='acceptance/plain';c=d['claim'][0]
            c.pop('band')
            if mode=='missing-reviewer':c['evidence'][0].pop('reviewer')
            if mode=='protect':c['evidence'][0]['epistemic_tier']='T1'
            if mode=='recipe-free':
                c.update(grade='probe',weight='weighted',clause_source='spec-document')
                c['evidence'][0]['control']={'kind':'custom','expectation':'red','observed':'red','of_claim':'C-1'}
            rep=evaluate(d,root)
            return C.verdict(rep)[0],diagnostic(rep)
for name,mode,expected,sub in (
 ('b2-ladder-id-unregistered-red','unknown-ladder','FAIL','not registered'),
 ('b4-class-kind-human-review-ok','review','PASS',''),
 ('b4-class-kind-missing-reviewer-red','missing-reviewer','FAIL',"missing required field 'reviewer'"),
 ('b4-class-family-cannot-redefine-red','protect','FAIL','above family ceiling T5'),
 ('b13-recipe-policy-meaning-owned-ok','recipe-free','PASS','')):
    synthetic(name,expected,sub,lambda m=mode:custom(m))
add('b13-verification-recipe-required-red',lambda d:d['claim'][0].update(weight='weighted',grade='probe',clause_source='spec-document'),substring='requires a [claim.self_verify]')
add('b13-verification-control-kind-red',lambda d:d['claim'][0]['evidence'][0].update(control={'kind':'custom','expectation':'red','observed':'red','of_claim':'C-1'}),substring='control.kind must be one of')

def reference(path, raw):
    return {'kind':'acceptance-claim','family':'reference','result':'pass','ref':path+'#C-1','tool':'fixture@1','record':path,'record_hash':H.digest('manifest:',raw),'manifest':path,'manifest_hash':H.digest('manifest:',raw),'claim':'C-1','records':[H.digest('record:',b'{"score": 99}')]}

def reference_case(mode):
    with workspace() as root:
        source=base(); d=base(); c=d['claim'][0]
        directory=root/'nested';directory.mkdir();(directory/'SPEC.md').write_text('Source spec.');(directory/'record.json').write_text('{"score": 99}')
        if mode=='relative':
            source['spec'].update(provenance='external',version=H.digest('normative-reference:',b'Source spec.'))
        if mode=='missing':source['claim'][0]['evidence'][0]['record']='missing'
        if mode=='bandless':
            source['claim'][0].pop('band');source['claim'][0]['statement']='Band-less at floor A0'
            c.pop('band');c['statement']='Reference at floor A0'
        if mode=='transitive':
            leaf=encode(base());(directory/'leaf.toml').write_bytes(leaf)
            entry=reference('leaf.toml',leaf)
            source['claim'][0]['evidence']=[entry]
        raw=encode(source);(directory/'source.toml').write_bytes(raw)
        ev=reference('nested/source.toml',raw)
        if mode=='transitive':
            valid_source=C.validate(directory/'source.toml', False, root=root)
            assert C.verdict(valid_source)==('PASS',0),diagnostic(valid_source)
            ev['records']=[entry['record_hash']]
        if mode=='wrong-domain':ev['records']=[H.digest('manifest:',b'anything')]
        if mode=='mixed':
            c.update(weight='weighted',grade='probe',clause_source='spec-document',self_verify={'command':'test command','expect':'ok','watched_fail':{'of_command':'test command','perturbed':'remove guard','observed':'check failed','date':'2026-09-22'}})
            c['evidence'][0]['result']='fail';c['evidence'].append(ev)
        elif mode=='missing':c['evidence'].append(ev)
        else:c['evidence']=[ev]
        rep=evaluate(d,root)
        if mode=='missing':
            assert rep.claim_evaluations['C-1']=='indeterminate',rep.claim_evaluations
            messages = diagnostic(rep)
            assert "B8: cited record is unresolvable" in messages
            rep.unknowns.clear()  # verdict must independently consume evaluation state
        if mode=='mixed':assert "claim 'C-1'" in rep.weight_refused
        return C.verdict(rep)[0],messages if mode=='missing' else diagnostic(rep)
for name,mode,verdict,sub in (
 ('b8-mixed-reference-weight-red','mixed','FAIL','not reachable'),
 ('b11-reference-indeterminate-propagates','missing','INDETERMINATE','B8: cited record is unresolvable'),
 ('b8-transitive-reference-red','transitive','FAIL','must be NATIVE'),
 ('b8-cited-record-domain-red','wrong-domain','FAIL','record: domain'),
 ('b8-source-relative-base','relative','PASS',''),
 ('b8-same-ladder-bandless-source-floor','bandless','PASS','')):
    synthetic(name,verdict,sub,lambda m=mode:reference_case(m))

# An actual six-file chain. Spy only records calls; the real validator still executes.
def depth_case():
    with workspace() as root:
        raw=encode(base());(root/'m6.toml').write_bytes(raw)
        for number in range(5,0,-1):
            d=base();d['claim'][0]['evidence']=[reference(f'm{number+1}.toml',raw)]
            raw=encode(d);(root/f'm{number}.toml').write_bytes(raw)
        original=C.validate;seen=[]
        def counted(path,*args,**kwargs):
            seen.append(path.name)
            return original(path,*args,**kwargs)
        C.validate=counted
        try:rep=C.validate(root/'m1.toml',False,root=root)
        finally:C.validate=original
        assert 'm6.toml' not in seen,seen
        assert seen==[f'm{i}.toml' for i in range(1,6)],seen
        assert rep.claim_evaluations['C-1']=='indeterminate'
        return C.verdict(rep)[0],diagnostic(rep)
synthetic('b8-depth-six-manifests','INDETERMINATE','source manifest is INDETERMINATE',depth_case)

# A registered ladder cannot be reordered by a meaning's local token list.
def registered_order():
    with workspace() as root:
        with meaning(root,'FAMILIES={}\nKINDS={}\nLADDER={"ladder_id":"acceptance/verification/A","tokens":["A4","A0"]}'):
            d=base();d['format']['profile']='acceptance/plain'
            rep=evaluate(d,root)
            assert rep.ladder['tokens'][0]=='A0' and rep.ladder['tokens'][-1]=='A4'
            return C.verdict(rep)[0],diagnostic(rep)
synthetic('b2-registered-token-order-authoritative','PASS','',registered_order)

add('b2-bandless-floor-disclosure-red',lambda d:d['claim'][0].pop('band'),substring='statement must disclose A0')
add('b13-core-recipe-shape-red',lambda d:d['claim'][0].update(self_verify={'command':'test'}),substring='self_verify.expect is required')


def cross_floor(disclose=True):
    with workspace() as root:
        registry=C._module(C.Path(C.__file__).resolve().parent/'profiles/__init__.py','registry')
        registry.LADDERS['acceptance/test/P']=('P0','P1')
        try:
            with meaning(root,'FAMILIES={}\nKINDS={}\nLADDER={"ladder_id":"acceptance/test/P"}'):
                source=base();source['format']['profile']='acceptance/plain';source['claim'][0]['band']='P0'
                raw=encode(source);(root/'source.toml').write_bytes(raw)
                d=base();c=d['claim'][0];c.pop('band');c['evidence']=[reference('source.toml',raw)]
                if disclose:c['statement']='Cross-ladder reference treated at floor A0'
                rep=evaluate(d,root)
                assert rep.ladder['tokens'][0]=='A0'
                assert C.control_free_ceiling(rep,c)==0
                return C.verdict(rep)[0],diagnostic(rep)
        finally:registry.LADDERS.pop('acceptance/test/P')
synthetic('b8-cross-ladder-bandless-floor','PASS','',cross_floor)
synthetic('b8-cross-ladder-floor-undisclosed-red','FAIL','statement must disclose A0',lambda:cross_floor(False))
