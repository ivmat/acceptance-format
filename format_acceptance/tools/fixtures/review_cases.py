"""Hub review F1–F9: behavioral cases and requested structural hygiene guards."""
from .core_cases import (C, H, CASES, add, base, certified_components, diagnostic,
                         encode, evaluate, synthetic, workspace)
from .r2_cases import meaning, reference
import ast
import copy
import inspect
from pathlib import Path

START=len(CASES)

def git_identity(d):
    d['subject'].pop('digest',None)
    d['subject'].update(commit='a'*40,dirty=False)

def no_hash_pointer(d,path):
    e=d['claim'][0]['evidence'][0];e.pop('record_hash');e['record']=path
add('b6-outcome-record-absolute-no-hash-red',lambda d:no_hash_pointer(d,'/tmp/record'),substring='B6: evidence.record: absolute path forbidden')
add('b6-outcome-record-escape-no-hash-red',lambda d:no_hash_pointer(d,'../record'),substring='B6: evidence.record: path escapes repository root')
add('b11-zero-claim-clause-git-identity-red',lambda d:(git_identity(d),d['coverage'].update(clauses_total=2)),substring='B11: zero-claim clauses require denominator = slice')
add('b13-unweighted-recipe-shape-git-identity-red',lambda d:(git_identity(d),d['claim'][0].update(self_verify={'command':'test'})),substring='self_verify.expect is required')
add('b6-spec-document-missing-git-identity-indeterminate',lambda d:(git_identity(d),d['spec'].update(path='missing.md')),verdict='INDETERMINATE',substring='B6: spec.path: unreadable document')
add('b1-components-aggregate-required-red',lambda d:(certified_components(d),d['subject'].pop('digest')),substring='B1: components require the aggregate subject.digest')
add('b2-floor-substring-is-not-disclosure-red',lambda d:(d['claim'][0].pop('band'),d['claim'][0].update(statement='evidence at A0x is named')),substring='statement must disclose A0')
add('b2-floor-word-disclosure-ok',lambda d:(d['claim'][0].pop('band'),d['claim'][0].update(statement='evidence at A0 is named')),verdict='PASS')

def reference_review(mode):
    with workspace() as root:
        with meaning(root,'FAMILIES={}\nKINDS={}\n'):
            source=base();source['format']['profile']='acceptance/plain';source['claim'][0].pop('band')
            if mode=='profile-and-indeterminate':source['claim'][0]['evidence'][0]['record']='missing'
            raw=encode(source);(root/'source.toml').write_bytes(raw)
            d=base();d['format']['profile']='acceptance/plain';claim=d['claim'][0];claim.pop('band')
            entry=reference('source.toml',raw)
            if mode=='reference-only':claim.update(weight='weighted',grade='probe',clause_source='spec-document',evidence=[entry])
            else:
                claim['evidence'].append(entry)
                profile=C._module(C.MODULE_ROOT/'profiles/plain.py','meaning')
                profile.check=lambda doc,ctx: [C.Finding('error','fixture profile rejection','C-1')] if ctx.path.name=='acceptance.toml' else []
            rep=evaluate(d,root)
            if mode=='profile-and-indeterminate':
                assert rep.claim_evaluations['C-1']=='indeterminate',rep.claim_evaluations
                assert rep.profile_errors==['fixture profile rejection'],rep.profile_errors
            else:assert 'B8: reference-only claim is never weight-bearing' in rep.class_errors
            return C.verdict(rep)[0],diagnostic(rep)
synthetic('b8-reference-only-weighted-class-red','FAIL','B8: reference-only claim is never weight-bearing',lambda:reference_review('reference-only'))
synthetic('b11-profile-error-keeps-reference-indeterminate','INDETERMINATE','B8: cited record is unresolvable',lambda:reference_review('profile-and-indeterminate'))

def depth_message():
    with workspace() as root:
        source=base();raw=encode(source);(root/'source.toml').write_bytes(raw)
        d=base();d['claim'][0]['evidence']=[reference('source.toml',raw)]
        rep=evaluate(d,root,_stack=tuple(H.digest('manifest:',str(i).encode()) for i in range(5)))
        return C.verdict(rep)[0],diagnostic(rep)
synthetic('b8-depth-diagnostic-exact','INDETERMINATE','B8: reference depth exceeds 4 edges (maximum five manifests including root)',depth_message)

def recursive_strict(cited_missing=False):
    with workspace() as root:
        source=base()
        if cited_missing:source['claim'][0]['evidence'][0]['record']='missing'
        else:
            extra=copy.deepcopy(source['claim'][0]['evidence'][0])
            extra.update(record='uncited-missing',record_hash=H.digest('record:',b'uncited'))
            source['claim'][0]['evidence'].append(extra)
        raw=encode(source);(root/'source.toml').write_bytes(raw)
        d=base();d['claim'][0]['evidence']=[reference('source.toml',raw)]
        p=root/'acceptance.toml';p.write_bytes(encode(d))
        rep=C.validate(p,True,root=root)
        if cited_missing:assert rep.claim_evaluations['C-1']=='indeterminate'
        return C.verdict(rep)[0],diagnostic(rep)
synthetic('b8-source-strict-false-uncited-missing-ok','PASS','',recursive_strict)
synthetic('b8-source-strict-false-cited-missing-indeterminate','INDETERMINATE','B8: cited record is unresolvable',lambda:recursive_strict(True))

def hygiene():
    assert list(inspect.signature(C.known_leaf).parameters)==['paths']
    assert 'assertion' not in inspect.signature(C._read_document).parameters
    source=Path(C.__file__).read_text(); tree=ast.parse(source)
    imports={n.names[0].name:n.lineno for n in tree.body if isinstance(n,ast.Import)}
    first_function=min(n.lineno for n in tree.body if isinstance(n,ast.FunctionDef))
    assert imports['hashlib']<first_function and imports['os']<first_function
    assert 'emit == rep.error' not in inspect.getsource(C.check_record_hashes)
    assert 'GRADES_REQUIRING_SELF_VERIFY' not in source
    assert 'B1: legacy components without aggregate' not in source
    return 'PASS','hygiene signatures/import placement/boolean guard'
synthetic('b13-review-hygiene-api-shape','PASS','hygiene signatures/import placement/boolean guard',hygiene)


def transitional(lane, explicit=True):
    with workspace() as root:
        with meaning(root,'FAMILIES={}\nKINDS={}\n'):
            (C.MODULE_ROOT/'profiles/conformance.py').write_text((C.MODULE_ROOT/'profiles/plain.py').read_text())
            d=base();git_identity(d);d['format']['profile']='acceptance/conformance';d['claim'][0].pop('band')
            if explicit:d['format']['profile_version']='0.1.0-draft'
            if lane=='coverage':d['coverage']['clauses_total']=2
            elif lane=='recipe':d['claim'][0]['self_verify']={'command':'test'}
            else:d['spec']['path']='missing.md'
            rep=evaluate(d,root)
            return C.verdict(rep)[0],diagnostic(rep)
for lane,rule in [('coverage','b11'),('recipe','b13'),('spec','b6')]:
    synthetic(f'{rule}-explicit-conformance-transition-{lane}-warning','PASS','legacy',lambda lane=lane:transitional(lane))
synthetic('b6-conformance-without-transition-spec-indeterminate','INDETERMINATE','unreadable document',lambda:transitional('spec',False))
