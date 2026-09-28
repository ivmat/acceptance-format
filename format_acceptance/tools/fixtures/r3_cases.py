"""Audit R3: named verdict fixtures, also consumed by the source mutation audit."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from .core_cases import C, H, CASES, add, base, diagnostic, encode, evaluate, synthetic, workspace
from .r2_cases import reference

START = len(CASES)
GROUPS = {}

def group(number, start):
    GROUPS[number] = [row[0] for row in CASES[start:]]

n = len(CASES)
for name, prefix in [('bare', b''), ('evidence-record', b'evidence-record:')]:
    add(f'b16-untyped-{name}-wire-ok', lambda d,p=prefix: d['claim'][0]['evidence'][0].update(record_hash='sha-512:'+hashlib.sha512(p+b'{"score": 99}').hexdigest()), verdict='PASS', substring=f'B16: untyped record_hash (legacy wire: {name}); use record:sha-512', absent='mismatch')
add('b16-untyped-no-wire-matches-red', lambda d:d['claim'][0]['evidence'][0].update(record_hash='sha-512:'+'0'*128), substring='untyped record_hash mismatch: no legacy wire matches')
add('b16-manifest-typed-on-native-red', lambda d:d['claim'][0]['evidence'][0].update(record_hash=H.digest('manifest:',b'{"score": 99}')), substring='record_hash must use record:')
add('b16-unknown-prefix-red', lambda d:d['claim'][0]['evidence'][0].update(record_hash='alien:sha-512:'+'0'*128), substring='record_hash must use record:')
add('b16-wrong-length-red', lambda d:d['claim'][0]['evidence'][0].update(record_hash='sha-512:abc'), substring='record_hash must use record:')
group(1,n)

def reference_row(mode):
    with workspace() as root:
        source=base(); claim=source['claim'][0]
        # A T3 native record allows a weaker supplied reference tier to be tested.
        claim['evidence'][0].update(kind='unit-test',family='dynamic',cases=1,epistemic_tier='T3')
        if mode=='bandless': claim.pop('band');claim['statement']='Source evaluated at A0'
        raw=encode(source);(root/'source.toml').write_bytes(raw)
        d=base(); ev=reference('source.toml',raw);d['claim'][0]['evidence']=[ev]
        if mode=='missing-ref':ev.pop('ref')
        if mode=='fail':ev['result']='fail'
        if mode=='hash':ev['record_hash']=H.digest('manifest:',b'other')
        if mode=='weaker':ev['epistemic_tier']='T5'
        if mode=='equal':ev['epistemic_tier']='T3'
        rep=evaluate(d,root)
        if mode in ('ok','equal'):assert rep.doc['claim'][0]['evidence'][0]['epistemic_tier']=='T3'
        return C.verdict(rep)[0],diagnostic(rep)
n=len(CASES)
for name,mode,v,sub in [
 ('b8-reference-row-missing-ref-red','missing-ref','FAIL','reference row ref must equal'),
 ('b8-reference-row-result-fail-red','fail','FAIL','reference row result must equal'),
 ('b8-reference-row-record-hash-neq-manifest-hash-red','hash','FAIL','reference row record_hash must equal'),
 ('b8-reference-row-ok','ok','PASS','B1: subject digest not recomputed')]:
    synthetic(name,v,sub,lambda m=mode:reference_row(m))
group(2,n)
n=len(CASES)
add('b5-applicability-table-bypass-red',lambda d:d['claim'].append({'id':'C-2','clause':'1','item':'x','statement':'out of scope','status':'not-applicable','grade':'out-of-scope','weight':'weighted','scope_ref':'SPEC.md','applicability':{}}) or d['coverage'].update(claims_total=2),substring='B5: applicability_reason must be nonempty')
add('b5-excluded-companions-red',lambda d:d['claim'][0].update(status='gap',applicability='excluded',applicability_reason='Deferred',evidence=[],grade='ungraded'),substring='B5: excluded requires nonempty scope_ref')
def table_warning():
    with workspace() as root:
        rep=C.Reporter('fixture');rep.doc={'format':{'profile':'acceptance/conformance','profile_version':'0.1.0-draft'}};rep.meaning_name='conformance'
        C.check_applicability(rep,{'status':'not-applicable','applicability':{},'applicability_reason':'No surface','weight':'unweighted'})
        assert not rep.errors,rep.errors
        return 'PASS','\n'.join(rep.warnings)
synthetic('b5-applicability-table-conformance-0-1-warning','PASS','B5: legacy applicability table is advisory',table_warning)
group(3,n)
n=len(CASES)
add('b7-calibration-on-claim-red',lambda d:d['claim'][0].update(alpha=1,calibration='SPEC.md'),substring='B7: manifest.claim[0].alpha')
add('b7-calibration-on-manifest-red',lambda d:d.update(beta=1,calibration='SPEC.md'),substring='B7: manifest.beta')
add('b7-calibration-on-evidence-ok',lambda d:d['claim'][0]['evidence'][0].update(lr=1,calibration='SPEC.md'),verdict='PASS',absent='B7:')
group(4,n)

def conformance_case(mode):
    from profiles import conformance as M
    with workspace() as root:
        # _native_claim_fixture: claims 1/5 carry NATIVE evidence, not the
        # default B8 acceptance-claim reference rows _green_fixture() gives them —
        # every mode here mutates claim[0]'s evidence[0] as a native record.
        f=M._native_claim_fixture();d=f['manifest']
        if mode in ('species-red','species-ok'):
            claim=d['claim'][0];claim['band']='A4' if mode=='species-red' else 'A1'
            claim['evidence'][0].update(kind='unit-test',family='dynamic',cases=1,control={'kind':'mutation','of_claim':claim['id'],'observed':'red','expectation':'red'})
        if mode=='partial-failed':
            d['claim'][0]['status']='partial'
            d['claim'][0]['evidence'][0]['result']='fail'
        if mode=='empty':d['claim'][0]['evidence']=[]
        if mode=='nested':
            # B8: the legacy [conformance].source_manifest pointer is retired;
            # the analogous B6-boundary-crossing test now cites a nested source
            # manifest through a real class B8 acceptance-claim reference row.
            (root/'nested').mkdir();(root/'nested/.git').mkdir()
            source=M._source_fixture();raw=M._toml_bytes(source)
            (root/'nested/source.toml').write_bytes(raw)
            wire=M.source_manifest_digest(raw)
            ev=M._reference_evidence('PM/wire')
            ev.update(manifest='nested/source.toml', record='nested/source.toml',
                      manifest_hash=wire, record_hash=wire, ref='nested/source.toml#PM/wire',
                      records=[source['claim'][0]['evidence'][0]['record_hash']])
            d['claim'][0]['evidence']=[ev]
        for key,filename in [('inventory','standard.clauses.toml'),('record','applicability.toml')]:
            (root/filename).write_bytes(M._toml_bytes(f[key]))
        (root/'evidence').mkdir()
        for i in (1,5):(root/f'evidence/record-{i}.json').write_bytes(M._fixture_record(i))
        rep=evaluate(d,root)
        if mode in ('partial-failed','empty'):assert 'not reachable' not in diagnostic(rep),diagnostic(rep)
        if mode=='species-ok':assert not any('mismatch' in x for x in rep.warnings)
        return C.verdict(rep)[0],diagnostic(rep)
n=len(CASES)
synthetic('c-species-ceiling-red','FAIL','band must be A0 or A1',lambda:conformance_case('species-red'))
synthetic('c-species-ceiling-ok','PASS','',lambda:conformance_case('species-ok'))
group(5,n)
n=len(CASES)
add('b2-partial-above-ceiling-no-control-red',lambda d:d['claim'][0].update(status='partial',band='A4'),substring='B2: band above control-free ceiling requires')
def floor(d,passing):
    c=d['claim'][0];c.pop('band');c['statement']='Evaluated at A0';c['evidence'][0]['result']='pass' if passing else 'fail'
add('b2-bandless-floor-unreachable-red',lambda d:floor(d,False),substring="band 'A0' is not reachable")
add('b2-bandless-floor-reachable-ok',lambda d:floor(d,True),verdict='PASS',absent='not reachable')
group(6,n)
n=len(CASES)
for name,mode,v,sub in [
 ('b8-bandless-source-explicit-a0-red','bandless','FAIL','band-less source requires a band-less referencing claim'),
 ('b8-reference-tier-weaker-than-derived-red','weaker','FAIL','reference tier must equal derived minimum'),
 ('b8-reference-tier-equal-ok','equal','PASS','B1:')]:
    synthetic(name,v,sub,lambda m=mode:reference_row(m))
group(7,n)
n=len(CASES)
def scope_case(flag):
    with workspace() as root:
        d=base();d['format']['profile']='acceptance/verification/code/rust'
        d['subject']={'name':'crate','kind':'rust-crate','commit':'a'*40,'dirty':False}
        rep=evaluate(d,root,**{flag:True})
        assert C.verdict(rep)==('PASS',0),diagnostic(rep)
        assert not rep.scope_meaning and not rep.scope_binding
        return C.verdict(rep)[0],'\n'.join(rep.notes)
synthetic('b12-scoping-flag-ignored-when-both-halves-present','PASS','scoping flag ignored: both halves present; full composed verdict',lambda:scope_case('meaning_only'))
synthetic('b12-binding-scoping-flag-ignored-when-both-halves-present','PASS','scoping flag ignored: both halves present; full composed verdict',lambda:scope_case('binding_only'))
def compatibility():
    with workspace() as root:
        d=base();d['format']['profile']='acceptance/verification/unknown';(root/'acceptance.toml').write_bytes(encode(d))
        run=subprocess.run([sys.executable,str(Path(C.__file__).with_name('check_acceptance.py')),'--root',str(root),str(root/'acceptance.toml')],capture_output=True,text=True)
        assert run.returncode==2,run.stdout+run.stderr
        return 'INDETERMINATE',run.stdout
synthetic('b12-compat-cli-unknown-suffix-still-indeterminate','INDETERMINATE','B12: unknown suffix',compatibility)
group(8,n)
n=len(CASES)
# The legacy [conformance].source_manifest pointer is retired; the same
# repository-boundary-crossing check now runs on a class B8 acceptance-claim
# reference row's own `manifest` pointer (check_core.check_reference_evidence).
synthetic('b8-source-in-nested-repo-red','FAIL','B6: reference manifest: path crosses repository boundary',lambda:conformance_case('nested'))
group(9,n)

# Group 10 (the archived rs-verified-der trial's B6-containment/B2-control exception fixtures)
# retired: the trial moved to the companion's archive/, so `trials/` no
# longer carries it and step 3 of the companion gate accepts no exception (every trial must
# PASS; none present -> skip). See docs/ACCEPTANCE-0.3-BUILD-PLAN.md revision.

def profile_contract():
    text=(Path(C.__file__).parents[1]/'profiles/conformance/PROFILE.md').read_text()
    c3=text[text.index('- **C3/C4'):text.index('- **C5')]
    c8=text[text.index('- **C8'):text.index('- **C9')]
    assert 'status = "not-applicable"' in c3 and 'class B5 is primary' in c3
    assert 'code/rust' in c8 and 'Names are never interpreted' in c8
    assert 'binding-side check does not\nexist yet' not in text
    assert 'composes meaning ∧ binding' in text
    return 'PASS','operative C3/C4, C8 and composed leaf contract'
n=len(CASES)
synthetic('c-profile-operative-contract-ok','PASS','operative C3/C4, C8 and composed leaf contract',profile_contract)
group(11,n)
n=len(CASES)
add('b1-digest-not-recomputed-warning',verdict='PASS',substring='B1: subject digest not recomputed')
def profile_segment():
    rep=C.Reporter('fixture');parsed=C.parse_profile(rep,{'format':{'profile':'acceptance/1meaning/2binding'}})
    assert parsed==('1meaning',['2binding']) and not rep.errors,(parsed,rep.errors)
    return 'PASS','leading-digit segments parsed'
synthetic('b12-segment-leading-digit-ok','PASS','leading-digit segments parsed',profile_segment)
def component_example():
    import re,tomllib
    text=(Path(C.__file__).parents[1]/'spec/format.md').read_text().split('## Components subject shape (B1)',1)[1]
    example=tomllib.loads(re.search(r'```toml\n(.*?)```',text,re.S)[1])
    assert example['subject']['components'][0]['dirty'] is False
    return 'PASS','git component dirty = false'
synthetic('b1-components-example-dirty-ok','PASS','git component dirty = false',component_example)
group(12,n)


# Pass 5 review findings: separate groups retain exact diagnostic assertions.
GROUPS[13] = ['b8-transitive-reference-red']
n=len(CASES)
def unknown_once():
    with workspace() as root:
        d=base();d['format']['profile']='acceptance/unknown-meaning'
        rep=evaluate(d,root)
        assert rep.unknowns.count('B12: unknown meaning prefix unknown-meaning') == 1,rep.unknowns
        return C.verdict(rep)[0],diagnostic(rep)
synthetic('b12-unknown-prefix-once','INDETERMINATE','B12: unknown meaning prefix unknown-meaning',unknown_once)
group(14,n)
n=len(CASES)
def broken_binding(scoped):
    from .r2_cases import meaning
    with workspace() as root:
        with meaning(root, 'FAMILIES={}\nKINDS={}'):
            bindings=C.MODULE_ROOT/'bindings';bindings.mkdir()
            (bindings/'document.py').write_text('raise RuntimeError("fixture binding import exploded")\n')
            d=base();d['format']['profile']='acceptance/verification/document'
            rep=evaluate(d,root,meaning_only=scoped)
            assert not rep.scope_meaning
            assert 'missing binding half' not in diagnostic(rep),diagnostic(rep)
            return C.verdict(rep)[0],diagnostic(rep)
for scoped in (False,True):
    synthetic('b13-present-broken-binding-'+('scoped' if scoped else 'plain')+'-indeterminate',
              'INDETERMINATE','B13: binding import failed document: RuntimeError: fixture binding import exploded',
              lambda value=scoped:broken_binding(value))
group(15,n)
n=len(CASES)
def suffixless_scope():
    with workspace() as root:
        for flag in ('meaning_only','binding_only'):
            rep=evaluate(base(),root,**{flag:True})
            assert C.verdict(rep)==('PASS',0),diagnostic(rep)
            assert rep.notes==['scoping flag ignored: the profile has no binding half; full verdict'],rep.notes
        return 'PASS','\n'.join(rep.notes)
synthetic('b12-suffixless-scoping-note','PASS','scoping flag ignored: the profile has no binding half; full verdict',suffixless_scope)
group(16,n)
n=len(CASES)
synthetic('c-partial-reachability-not-evaluated','PASS','',lambda:conformance_case('partial-failed'))
synthetic('c-empty-reachability-not-evaluated','FAIL','requires at least one evidence entry',lambda:conformance_case('empty'))
group(17,n)


R3_CASES = CASES[START:]
# The public protocol gate cannot depend on the private companion checkout.
# The standalone R3 audit runs its gate fixtures as well.
del CASES[START:]
CASES.extend(R3_CASES)
# Audit the existing R2 transitivity fixture without registering a duplicate.
R3_CASES += [row for row in CASES if row[0] in GROUPS[13]]

def run():
    failed=[]
    for name,verdict,substring,operation in R3_CASES:
        try:
            operation()
            print(f'PASS {name}: expected {verdict}/{1 if verdict=="FAIL" else 2 if verdict=="INDETERMINATE" else 0}; contains {substring!r}')
        except Exception as exc:
            failed.append(name);print(f'FAIL {name}: {type(exc).__name__}: {exc}')
    print(f'R3: {len(R3_CASES)} fixtures, {len(failed)} failures')
    return bool(failed)

if __name__=='__main__':sys.exit(run())
