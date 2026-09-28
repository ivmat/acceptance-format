"""fixtures/assurance_class_chain.py — the assurance-class + spec-maturity selftest chain
(protocol.md §3.7, revision).

This is a CLASS-rung mechanism, not tied to one profile — unlike `PROFILE_CHAINS`'s entries, it
is wired into `run_selftest` through `CORE_CHAINS` (acceptance_protocol.py). It still exercises
`acceptance/verification`'s package validator as its substrate (the simplest already-bound
profile), the same way `verification_chain.py` carries the rest of the profile-blind Class-rung
cases — no new profile vocabulary of its own.

Case groups (protocol.md §3.7, the maturity rule):
  - class floors met / not met on a firm requirement of a final-phase contract (ERROR)
  - the same gap on a draft requirement, or in phase exploratory/crystallizing (NOTE, not error)
  - per-requirement assurance_class override: raises the class (accepted), lowers it (refused)
  - required_meaning: a class-required profile missing from profiles_required, scoped by
    [subject].kind, and the unconditional pass when the kind does not match
  - independence's 4th value (`third-party`): tightening ordering, and the coverage floor itself
    (excludes both the producer AND the consumer, not the producer alone)
  - the three new [requirement.evidence] floors (coverage_min, build_inputs_required,
    tool_qualification_required): coverage() pass/fail on each
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from acceptance_protocol import (
    PROTOCOL_ID, _monotonic_violations, check_assurance_table_monotonic, check_contract,
    check_contract_tightening, check_package, load_toml,
)
from fixtures._support import Cases, write

import m11

_SUBJECT_COMMIT = "c1a55" + "0" * 35  # 40 lowercase hex chars


def _contract_toml(
    *, contract_id: str = "AC-TEST-CLASS-1",
    contract_class: str | None = "baseline/3",
    phase: str = "final",
    subject_kind: str = "other",
    profiles_required: str = '["acceptance/verification"]',
    req_evidence: str,
    req_firmness: str | None = None,
    req_class_override: str | None = None,
    policy_block: str = "",
) -> str:
    class_line = f'assurance_class          = "{contract_class}"\n' if contract_class else ""
    firmness_line = f'firmness      = "{req_firmness}"\n' if req_firmness else ""
    override_line = f'assurance_class = "{req_class_override}"\n' if req_class_override else ""
    return f'''
[document]
protocol   = "{PROTOCOL_ID}"
minor      = 0
kind       = "contract"
id         = "{contract_id}"
version    = 1
issued_at  = "2026-09-24T10:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = {{ name = "Acme Class Test", contact = "class@acme.example" }}
producer = {{ name = "supplier-class-test" }}

[subject]
kind         = "{subject_kind}"
name         = "component-x"
description  = "assurance-class protocol selftest fixture (revision)"
deliverables = ["artifact"]
constraints  = []
profile      = "acceptance/verification"
{policy_block}
[[requirement]]
id            = "R1"
statement     = "R1 must hold"
mandatory     = true
waivable      = true
domain        = "correctness"
clause_source = "consumer-statement"
{firmness_line}{override_line}{req_evidence}

[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "spot-check"
authority             = "Acme Class Test / lead"
profiles_required     = {profiles_required}
stale_after           = "P90D"
phase                 = "{phase}"
{class_line}'''


_FLOOR_BASELINE_3_MET = '''  [requirement.evidence]
  min_tier                     = "T2"
  weighted_required            = true
  control_required             = true
  recipe_required              = true
  freshness                    = "delivered-revision"
  independence                 = "consumer-run"
  build_inputs_required        = false
  tool_qualification_required  = false
  [requirement.evidence.coverage_min]
  metric = "decision"
  value  = 0.85
'''

_FLOOR_BASELINE_0 = '''  [requirement.evidence]
  min_tier          = "T5"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
'''


def run() -> list[tuple[str, bool, object]]:
    cases = Cases()

    # --- F4 (2026-09-24): the shipped assurance-classes.toml is monotone
    # 0..4, on every mechanically-compared axis AND the documentary `bounds` axis (the header's
    # own claim covers both). ---
    violations = check_assurance_table_monotonic()
    cases.check("assurance-table-monotonic-0-to-4-PASS", not violations, violations)

    # --- A2 (0.3.1 errata, F24): the monotonicity check now ALSO covers required_meaning ------
    # Able-to-fail control: a planted table reproducing the pre-errata 0.3.0 shape (conformance
    # required UNCONDITIONALLY at level 2, dropped at level 3, then required again at level 4) is
    # exactly the F24 defect the errata fixes — the extended check must catch it, on the axis the
    # OLD `check_assurance_table_monotonic` (pre-A2) never looked at.
    _planted_level_2 = {
        "min_tier": "T3", "weighted_required": True, "control_required": False,
        "recipe_required": False, "independence": "author-not-producer",
        "freshness": "delivered-revision", "build_inputs_required": False,
        "tool_qualification_required": False, "bounds": "bounded",
        "required_meaning": [{"profile": "acceptance/conformance"}],
    }
    _planted_level_3 = {
        "min_tier": "T2", "weighted_required": True, "control_required": True,
        "recipe_required": True, "independence": "consumer-run",
        "freshness": "delivered-revision", "build_inputs_required": False,
        "tool_qualification_required": False, "bounds": "bounded",
        "coverage_min": {"metric": "decision", "value": 0.8},
        "required_meaning": [
            {"profile": "acceptance/troubleshooting", "when_kind": ["application-delivery"]},
        ],
    }
    planted_violations = _monotonic_violations({2: _planted_level_2, 3: _planted_level_3})
    cases.check(
        "required-meaning-non-monotone-table-is-CAUGHT-A2",
        any("acceptance/conformance" in v and "level 3 vs level 2" in v for v in planted_violations),
        planted_violations,
    )

    # Positive control: the SAME planted level 3, extended to also carry the level-2 profile
    # unconditionally, is clean on required_meaning (still isolating the mechanism, not the real
    # table's own already-covered PASS above).
    _planted_level_3_fixed = dict(_planted_level_3)
    _planted_level_3_fixed["required_meaning"] = [
        {"profile": "acceptance/conformance"},
        {"profile": "acceptance/troubleshooting", "when_kind": ["application-delivery"]},
    ]
    fixed_violations = _monotonic_violations({2: _planted_level_2, 3: _planted_level_3_fixed})
    cases.check(
        "required-meaning-monotone-when-fixed-PASS-A2", not fixed_violations, fixed_violations,
    )

    # --- A2 edge case (review fold): an ABSENT or EMPTY when_kind are both unconditional,
    # matching the runtime check's own `not when_kind` reading (§3.7, `applies = not when_kind or
    # ...`) — an unconditional lower-level entry is never covered by a SCOPED-only upper-level one.
    _empty_wk_lo = dict(_planted_level_2)
    _empty_wk_lo["required_meaning"] = [{"profile": "acceptance/x-edge", "when_kind": []}]
    _scoped_only_hi = dict(_planted_level_3)
    _scoped_only_hi["required_meaning"] = [
        {"profile": "acceptance/x-edge", "when_kind": ["some-kind"]},
    ]
    empty_wk_violations = _monotonic_violations({2: _empty_wk_lo, 3: _scoped_only_hi})
    cases.check(
        "required-meaning-empty-when-kind-unconditional-vs-scoped-upper-is-CAUGHT-A2",
        any(
            "acceptance/x-edge" in v and "unconditionally" in v and "level 3 vs level 2" in v
            for v in empty_wk_violations
        ),
        empty_wk_violations,
    )

    # --- A2 fail-closed (review fold): a malformed required_meaning shape is a REPORTED
    # violation, never silently skipped or silently accepted. ----------------------------------
    _malformed_non_list = dict(_planted_level_2)
    _malformed_non_list["required_meaning"] = "not-a-list"
    malformed_violations = _monotonic_violations({2: _malformed_non_list, 3: _planted_level_3})
    cases.check(
        "required-meaning-malformed-non-list-is-CAUGHT-A2",
        any("required_meaning must be a list" in v for v in malformed_violations),
        malformed_violations,
    )

    # --- Review found: union higher-level scopes per profile —
    # an equivalent split (two narrower rows whose UNION equals the lower row's scope) must NOT be
    # flagged; a genuinely-narrowed split (the union still misses a kind) must still be caught. ---
    _equiv_lower = {
        "min_tier": "T3", "weighted_required": True, "control_required": False,
        "recipe_required": False, "independence": "author-not-producer",
        "freshness": "delivered-revision", "build_inputs_required": False,
        "tool_qualification_required": False, "bounds": "bounded",
        "required_meaning": [{"profile": "acceptance/x-equiv-test", "when_kind": ["a", "b"]}],
    }
    _equiv_split_upper = {
        "min_tier": "T2", "weighted_required": True, "control_required": True,
        "recipe_required": True, "independence": "consumer-run",
        "freshness": "delivered-revision", "build_inputs_required": False,
        "tool_qualification_required": False, "bounds": "bounded",
        "coverage_min": {"metric": "decision", "value": 0.8},
        "required_meaning": [
            {"profile": "acceptance/x-equiv-test", "when_kind": ["a"]},
            {"profile": "acceptance/x-equiv-test", "when_kind": ["b"]},
        ],
    }
    equiv_split_violations = _monotonic_violations({2: _equiv_lower, 3: _equiv_split_upper})
    cases.check(
        "required-meaning-equivalent-split-is-PASS-A2-cv2-5",
        not any("x-equiv-test" in v for v in equiv_split_violations),
        equiv_split_violations,
    )

    _genuinely_narrowed_upper = dict(_equiv_split_upper)
    _genuinely_narrowed_upper["required_meaning"] = [
        {"profile": "acceptance/x-equiv-test", "when_kind": ["a"]},
    ]
    narrowed_violations = _monotonic_violations({2: _equiv_lower, 3: _genuinely_narrowed_upper})
    cases.check(
        "required-meaning-genuinely-narrowed-split-is-CAUGHT-A2-cv2-5",
        any("x-equiv-test" in v for v in narrowed_violations),
        narrowed_violations,
    )

    # --- Review found: a malformed when_kind element (not a
    # nonempty string) must be a REPORTED violation, never a silent accept nor an uncaught
    # TypeError from frozenset() construction. ---
    _malformed_element_lower = dict(_planted_level_2)
    _malformed_element_lower["required_meaning"] = [
        {"profile": "acceptance/x-malformed-test", "when_kind": [1]},
    ]
    malformed_element_violations = _monotonic_violations({2: _malformed_element_lower, 3: _planted_level_3})
    cases.check(
        "required-meaning-malformed-when-kind-element-int-is-CAUGHT-A2-cv2-6",
        any("when_kind elements must all be nonempty strings" in v for v in malformed_element_violations),
        malformed_element_violations,
    )
    _malformed_element_nested = dict(_planted_level_2)
    _malformed_element_nested["required_meaning"] = [
        {"profile": "acceptance/x-malformed-test", "when_kind": [["nested"]]},
    ]
    malformed_nested_violations = _monotonic_violations({2: _malformed_element_nested, 3: _planted_level_3})
    cases.check(
        "required-meaning-malformed-when-kind-element-nested-list-is-CAUGHT-A2-cv2-6",
        any("when_kind elements must all be nonempty strings" in v for v in malformed_nested_violations),
        malformed_nested_violations,
    )

    # --- F6 (2026-09-24): [policy].hash is self-describing
    # ('normative-reference:sha-512:<hex>'); the retired bare 'sha-512:<hex>' form is an ERROR,
    # same as contract/package/decision (§7, one wire form). ---
    _f6_lenient_floor = '''  [requirement.evidence]
  min_tier          = "T5"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
'''
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        c_bare = write(
            td, "f6-policy-bare.toml",
            _contract_toml(
                req_evidence=_f6_lenient_floor, contract_class=None,
                policy_block=(
                    '\n[policy]\nref  = "https://acme.example/supplier-policy/v3"\n'
                    'hash = "sha-512:' + ('ab' * 64) + '"\n'
                ),
            ),
        )
        doc_bare, _e = load_toml(c_bare)
        rep_bare = check_contract(doc_bare)
        cases.expect_fail("f6-policy-hash-bare-wire-form-is-error-FAIL", rep_bare, "retired bare")

        c_ok = write(
            td, "f6-policy-ok.toml",
            _contract_toml(
                req_evidence=_f6_lenient_floor, contract_class=None,
                policy_block=(
                    '\n[policy]\nref  = "https://acme.example/supplier-policy/v3"\n'
                    'hash = "normative-reference:sha-512:' + ('ab' * 64) + '"\n'
                ),
            ),
        )
        doc_ok, _e = load_toml(c_ok)
        rep_ok = check_contract(doc_ok)
        cases.check(
            "f6-policy-hash-self-describing-form-ok-PASS",
            not any("policy" in e for e in rep_ok.errors), rep_ok.errors,
        )

    # --- A: class floors on a firm, final-phase requirement ----------------------------------
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        c_path = write(td, "a1.toml", _contract_toml(req_evidence=_FLOOR_BASELINE_3_MET))
        doc, _e = load_toml(c_path)
        rep = check_contract(doc)
        cases.check("baseline-3-firm-final-meets-floor-PASS", rep.ok(), rep.errors)

        c_path2 = write(td, "a2.toml", _contract_toml(req_evidence=_FLOOR_BASELINE_0))
        doc2, _e = load_toml(c_path2)
        rep2 = check_contract(doc2)
        cases.expect_fail("baseline-3-firm-final-below-floor-FAIL", rep2, "below its assurance class")

    # --- B: draft requirement / non-final phase -- NOTE, never an error ----------------------
    # b1's contract is `crystallizing`, not `final` (A4, 0.3.1 errata: a draft requirement in a
    # FINAL contract is now a hard ERROR — see the G section below; a draft requirement is only
    # ever a spec-clarity NOTE outside `final`).
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        c_path = write(
            td, "b1.toml",
            _contract_toml(req_evidence=_FLOOR_BASELINE_0, req_firmness="draft", phase="crystallizing"),
        )
        doc, _e = load_toml(c_path)
        rep = check_contract(doc)
        cases.check("draft-requirement-below-floor-is-PASS-not-error", rep.ok(), rep.errors)
        cases.check(
            "draft-requirement-below-floor-emits-NOTE",
            any("NOTE (spec-clarity gap" in w and "draft" in w for w in rep.warnings),
            rep.warnings,
        )

        c_path2 = write(
            td, "b2.toml",
            _contract_toml(req_evidence=_FLOOR_BASELINE_0, phase="exploratory"),
        )
        doc2, _e = load_toml(c_path2)
        rep2 = check_contract(doc2)
        cases.check("exploratory-phase-below-floor-is-PASS-not-error", rep2.ok(), rep2.errors)
        cases.check(
            "exploratory-phase-below-floor-emits-NOTE",
            any("NOTE (spec-clarity gap" in w and "exploratory" in w for w in rep2.warnings),
            rep2.warnings,
        )

    # --- A4 (0.3.1 errata, §3.5/§3.7): a `final`-phase contract MUST have every requirement
    # `firm` — a `draft` requirement in a `final` contract is a hard ERROR, not a NOTE. -------
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        # RED: a final-phase contract with one draft requirement.
        c_path = write(
            td, "a4-red.toml",
            _contract_toml(req_evidence=_FLOOR_BASELINE_3_MET, phase="final", req_firmness="draft"),
        )
        doc, _e = load_toml(c_path)
        rep = check_contract(doc)
        cases.expect_fail(
            "final-phase-draft-requirement-is-ERROR-A4", rep,
            "firmness must not be 'draft' in a 'final'-phase contract",
        )

        # GREEN: the SAME contract with the requirement explicitly firm (still final-phase).
        c_path2 = write(
            td, "a4-green.toml",
            _contract_toml(req_evidence=_FLOOR_BASELINE_3_MET, phase="final", req_firmness="firm"),
        )
        doc2, _e = load_toml(c_path2)
        rep2 = check_contract(doc2)
        cases.check("final-phase-firm-requirement-is-PASS-A4", rep2.ok(), rep2.errors)

        # GREEN: absent firmness defaults to firm — a final-phase contract that never sets
        # firmness at all (every other fixture in this file) must still pass (no regression).
        c_path3 = write(
            td, "a4-green-default.toml",
            _contract_toml(req_evidence=_FLOOR_BASELINE_3_MET, phase="final"),
        )
        doc3, _e = load_toml(c_path3)
        rep3 = check_contract(doc3)
        cases.check("final-phase-absent-firmness-defaults-firm-PASS-A4", rep3.ok(), rep3.errors)

        # Review fold: a draft requirement BELOW its class floor, in a `final`-phase contract, is
        # ONLY the A4 firmness ERROR — `check_contract_assurance_class`'s maturity-gap NOTE branch
        # must NOT also fire for the same requirement (the defect is reported once, not twice).
        c_path4 = write(
            td, "a4-red-below-floor.toml",
            _contract_toml(req_evidence=_FLOOR_BASELINE_0, phase="final", req_firmness="draft"),
        )
        doc4, _e = load_toml(c_path4)
        rep4 = check_contract(doc4)
        cases.expect_fail(
            "final-phase-draft-below-floor-is-ONLY-firmness-ERROR-A4", rep4,
            "firmness must not be 'draft' in a 'final'-phase contract",
        )
        cases.check(
            "final-phase-draft-below-floor-emits-NO-duplicate-maturity-NOTE-A4",
            not any("NOTE (spec-clarity gap" in w for w in rep4.warnings),
            rep4.warnings,
        )

        # Not applicable outside `final`: the SAME draft requirement, below the same floor, in
        # `crystallizing` is legal — a real (non-vacuous) restatement of B1's own case, self
        # contained here for A4 traceability (review fold: the prior version of this case asserted
        # `True` unconditionally).
        c_path5 = write(
            td, "a4-crystallizing-draft-below-floor.toml",
            _contract_toml(req_evidence=_FLOOR_BASELINE_0, phase="crystallizing", req_firmness="draft"),
        )
        doc5, _e = load_toml(c_path5)
        rep5 = check_contract(doc5)
        cases.check("crystallizing-draft-below-floor-is-PASS-not-error-A4", rep5.ok(), rep5.errors)
        cases.check(
            "crystallizing-draft-below-floor-emits-NOTE-A4",
            any("NOTE (spec-clarity gap" in w and "draft" in w for w in rep5.warnings),
            rep5.warnings,
        )

    # --- C: per-requirement override -- raise accepted, lower refused ------------------------
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        c_path = write(
            td, "c1.toml",
            _contract_toml(
                contract_class="baseline/1", req_evidence=_FLOOR_BASELINE_3_MET,
                req_class_override="baseline/3",
            ),
        )
        doc, _e = load_toml(c_path)
        rep = check_contract(doc)
        cases.check("override-raises-baseline-1-to-3-is-PASS", rep.ok(), rep.errors)

        c_path2 = write(
            td, "c2.toml",
            _contract_toml(
                contract_class="baseline/3", req_evidence=_FLOOR_BASELINE_3_MET,
                req_class_override="baseline/1",
            ),
        )
        doc2, _e = load_toml(c_path2)
        rep2 = check_contract(doc2)
        cases.expect_fail(
            "override-lowers-baseline-3-to-1-is-FAIL", rep2,
            "WEAKER than the contract's assurance_class",
        )

    # --- D: required_meaning, scoped by [subject].kind ----------------------------------------
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        c_path = write(
            td, "d1.toml",
            _contract_toml(
                req_evidence=_FLOOR_BASELINE_3_MET, subject_kind="application-delivery",
                profiles_required='["acceptance/verification"]',
            ),
        )
        doc, _e = load_toml(c_path)
        rep = check_contract(doc)
        cases.expect_fail(
            "required-meaning-missing-for-application-delivery-FAIL", rep,
            "requires profile 'acceptance/troubleshooting'",
        )

        c_path2 = write(
            td, "d2.toml",
            _contract_toml(
                req_evidence=_FLOOR_BASELINE_3_MET, subject_kind="application-delivery",
                profiles_required='["acceptance/verification", "acceptance/troubleshooting"]',
            ),
        )
        doc2, _e = load_toml(c_path2)
        rep2 = check_contract(doc2)
        cases.check("required-meaning-present-is-PASS", rep2.ok(), rep2.errors)

        # subject.kind = "other" (the A/B/C default) never matches troubleshooting's when_kind —
        # already exercised by A1's clean PASS above, restated here by name for W4 traceability.
        cases.check(
            "required-meaning-not-applicable-for-non-matching-kind-is-PASS-see-A1",
            True, None,
        )

    # --- E: independence's 4th value, `third-party` -------------------------------------------
    tight_base_ev = '''  [requirement.evidence]
  min_tier          = "T3"
  weighted_required = true
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "{indep}"
'''
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        old_path = write(
            td, "e-old.toml",
            _contract_toml(
                contract_id="AC-TEST-CLASS-TIGHT", contract_class=None,
                req_evidence=tight_base_ev.format(indep="consumer-run"),
            ),
        )
        old_doc, _e = load_toml(old_path)

        raise_text = _contract_toml(
            contract_id="AC-TEST-CLASS-TIGHT-2", contract_class=None,
            req_evidence=tight_base_ev.format(indep="third-party"),
        ).replace('status     = "issued"', 'status     = "issued"\nsupersedes = "AC-TEST-CLASS-TIGHT"')
        new_path = write(td, "e-new.toml", raise_text)
        new_doc, _e = load_toml(new_path)
        tight_raise = check_contract_tightening(new_doc, old_doc)
        cases.check(
            "tightening-independence-consumer-run-to-third-party-is-PASS",
            tight_raise.ok(), tight_raise.errors,
        )

        lower_text = _contract_toml(
            contract_id="AC-TEST-CLASS-TIGHT-3", contract_class=None,
            req_evidence=tight_base_ev.format(indep="consumer-run"),
        ).replace('status     = "issued"', 'status     = "issued"\nsupersedes = "AC-TEST-CLASS-TIGHT"')
        # base for THIS comparison is third-party (simulate a chain step tightened to third-party,
        # then an attempted step back down to consumer-run without `relaxed`).
        third_party_base_text = _contract_toml(
            contract_id="AC-TEST-CLASS-TIGHT", contract_class=None,
            req_evidence=tight_base_ev.format(indep="third-party"),
        )
        third_party_base_path = write(td, "e-tp-base.toml", third_party_base_text)
        third_party_base_doc, _e = load_toml(third_party_base_path)
        lower_path = write(td, "e-lower.toml", lower_text)
        lower_doc, _e = load_toml(lower_path)
        tight_lower = check_contract_tightening(lower_doc, third_party_base_doc)
        cases.expect_fail(
            "tightening-independence-third-party-to-consumer-run-without-relaxed-FAIL",
            tight_lower, "independence weakened",
        )

    # --- E (continued) + F: the coverage() floor checks themselves ---------------------------
    def _coverage_contract(evidence_block: str) -> str:
        return f'''
[document]
protocol   = "{PROTOCOL_ID}"
minor      = 0
kind       = "contract"
id         = "AC-TEST-CLASS-COV"
version    = 1
issued_at  = "2026-09-24T10:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = {{ name = "Acme Class Test", contact = "class@acme.example" }}
producer = {{ name = "supplier-class-test" }}

[subject]
kind         = "other"
name         = "component-x"
description  = "coverage-floor selftest fixture (revision)"
deliverables = ["artifact"]
constraints  = []
profile      = "acceptance/verification"

[[requirement]]
id            = "R1"
statement     = "R1 must hold"
mandatory     = true
waivable      = true
domain        = "correctness"
clause_source = "consumer-statement"
{evidence_block}

[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "spot-check"
authority             = "Acme Class Test / lead"
profiles_required     = ["acceptance/verification"]
stale_after           = "P90D"
'''

    def _claim_toml(evidence_extra: str, *, author: str | None = None) -> str:
        author_line = f'  author = "{author}"\n' if author else ""
        return f'''
[[claim]]
id        = "C1"
clause    = "R1"
item      = "src/lib.rs::r1"
statement = "C1 satisfies R1"
band      = "A1"
weight    = "unweighted"
grade     = "test-only"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "test_r1"
  result    = "pass"
  tool      = "cargo test"
  record    = "evidence/c1.json"
{author_line}{evidence_extra}
'''

    def _package_toml(claim_block: str) -> str:
        return f'''
[format]
id      = "acceptance/0"
profile = "acceptance/verification"

[contract]
id                 = "AC-TEST-CLASS-COV"
hash               = "{{{{CONTRACT_HASH}}}}"
requirements_total = 1

[subject]
name   = "component-x"
kind   = "other"
commit = "{_SUBJECT_COMMIT}"
dirty  = false

[spec]
path    = "acceptance-contract.toml"
version = "AC-TEST-CLASS-COV@v1"
axis    = "the requirements of contract AC-TEST-CLASS-COV"

[coverage]
clauses_total = 1
claims_total  = 1
{claim_block}'''

    def _run_pair(evidence_floor: str, claim_evidence_extra: str, *, author: str | None = None):
        with tempfile.TemporaryDirectory() as tdstr:
            td = Path(tdstr)
            c_path = write(td, "cov.toml", _coverage_contract(evidence_floor))
            c_hash = m11.digest_file("contract", c_path)
            p_path = write(
                td, "acceptance.toml",
                _package_toml(_claim_toml(claim_evidence_extra, author=author)).replace("{{CONTRACT_HASH}}", c_hash),
            )
            contract, _e = load_toml(c_path)
            package, _e = load_toml(p_path)
            _rep, cov = check_package(package, contract, p_path, c_path, strict=False)
            return cov["requirements"]["R1"]

    def _claim_toml_multi(evidence_blocks: list[str]) -> str:
        """F1 (2026-09-24): a claim with MULTIPLE relied-on evidence
        records, needed to test the "every tool-produced record" quantifier — `_claim_toml`
        above only ever carries one."""
        return f'''
[[claim]]
id        = "C1"
clause    = "R1"
item      = "src/lib.rs::r1"
statement = "C1 satisfies R1"
band      = "A1"
weight    = "unweighted"
grade     = "test-only"
status    = "evidenced"
{''.join(evidence_blocks)}
'''

    def _run_multi(evidence_floor: str, evidence_blocks: list[str]):
        with tempfile.TemporaryDirectory() as tdstr:
            td = Path(tdstr)
            c_path = write(td, "cov.toml", _coverage_contract(evidence_floor))
            c_hash = m11.digest_file("contract", c_path)
            p_path = write(
                td, "acceptance.toml",
                _package_toml(_claim_toml_multi(evidence_blocks)).replace("{{CONTRACT_HASH}}", c_hash),
            )
            contract, _e = load_toml(c_path)
            package, _e = load_toml(p_path)
            _rep, cov = check_package(package, contract, p_path, c_path, strict=False)
            return cov["requirements"]["R1"]

    coverage_min_floor = '''  [requirement.evidence]
  min_tier          = "T5"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
  [requirement.evidence.coverage_min]
  metric = "branch"
  value  = 0.8
'''
    r = _run_pair(coverage_min_floor, '  [claim.evidence.coverage]\n  metric = "branch"\n  value  = 0.9\n')
    cases.check("coverage-min-value-above-floor-satisfied-PASS", r["status"] == "satisfied", r)

    r = _run_pair(coverage_min_floor, '  [claim.evidence.coverage]\n  metric = "branch"\n  value  = 0.5\n')
    cases.check("coverage-min-value-below-floor-not-satisfied-FAIL", r["status"] != "satisfied", r)
    cases.check(
        "coverage-min-value-below-floor-reason-names-cond-11",
        "cond 11" in r["reasons"].get("C1", ""), r["reasons"],
    )

    r = _run_pair(coverage_min_floor, '  [claim.evidence.coverage]\n  metric = "statement"\n  value  = 0.99\n')
    cases.check("coverage-min-metric-mismatch-not-satisfied-FAIL", r["status"] != "satisfied", r)

    r = _run_pair(coverage_min_floor, '')
    cases.check("coverage-min-no-coverage-record-not-satisfied-FAIL", r["status"] != "satisfied", r)

    build_inputs_floor = '''  [requirement.evidence]
  min_tier              = "T5"
  weighted_required     = false
  control_required      = false
  recipe_required       = false
  freshness             = "any"
  independence          = "none"
  build_inputs_required = true
'''
    r = _run_pair(build_inputs_floor, '  build_inputs = [{ path = "Cargo.lock", digest = "artifact:sha-512:' + ('ab' * 64) + '" }]\n')
    cases.check("build-inputs-required-declared-satisfied-PASS", r["status"] == "satisfied", r)

    r = _run_pair(build_inputs_floor, '')
    cases.check("build-inputs-required-absent-not-satisfied-FAIL", r["status"] != "satisfied", r)
    cases.check(
        "build-inputs-required-reason-names-cond-9",
        "cond 9" in r["reasons"].get("C1", ""), r["reasons"],
    )

    tool_qual_floor = '''  [requirement.evidence]
  min_tier                     = "T5"
  weighted_required            = false
  control_required             = false
  recipe_required              = false
  freshness                    = "any"
  independence                 = "none"
  tool_qualification_required  = true
'''
    r = _run_pair(tool_qual_floor, '  [claim.evidence.tool_qualification]\n  basis = "vendor DO-330 letter"\n')
    cases.check("tool-qualification-required-declared-satisfied-PASS", r["status"] == "satisfied", r)

    r = _run_pair(tool_qual_floor, '')
    cases.check("tool-qualification-required-absent-not-satisfied-FAIL", r["status"] != "satisfied", r)
    cases.check(
        "tool-qualification-required-reason-names-cond-10",
        "cond 10" in r["reasons"].get("C1", ""), r["reasons"],
    )

    # --- F1 (2026-09-24): the quantifier is EVERY tool-produced
    # relied-on record (family != "judgment"), not "at least one" — the old reading let a single
    # compliant record vouch for the whole claim while another tool-produced record relied on
    # carried neither field. A `judgment`-family record (human/llm review) is exempt.
    _build_inputs_ok = (
        '  build_inputs = [{ path = "Cargo.lock", digest = "artifact:sha-512:' + ('ab' * 64) + '" }]\n'
    )
    _tool_record_a_build_inputs = (
        '\n  [[claim.evidence]]\n  kind      = "unit-test"\n  family    = "dynamic"\n'
        '  ref       = "test_r1"\n  result    = "pass"\n  tool      = "cargo test"\n'
        '  record    = "evidence/c1.json"\n' + _build_inputs_ok
    )
    _tool_record_b_no_build_inputs = (
        '\n  [[claim.evidence]]\n  kind      = "lint"\n  family    = "mechanical"\n'
        '  ref       = "clippy"\n  result    = "pass"\n  tool      = "cargo clippy"\n'
        '  record    = "evidence/c1-lint.json"\n'
    )
    _human_review_record = (
        '\n  [[claim.evidence]]\n  kind      = "human-review"\n  family    = "judgment"\n'
        '  ref       = "review"\n  result    = "pass"\n  tool      = "reviewer"\n'
        '  reviewer  = "reader"\n  record    = "evidence/c1-review.json"\n'
    )

    r = _run_multi(build_inputs_floor, [_tool_record_a_build_inputs, _tool_record_b_no_build_inputs])
    cases.check(
        "build-inputs-required-one-of-two-tool-records-missing-not-satisfied-FAIL-F1",
        r["status"] != "satisfied", r,
    )
    cases.check(
        "build-inputs-required-one-of-two-tool-records-missing-reason-names-cond-9-F1",
        "cond 9" in r["reasons"].get("C1", ""), r["reasons"],
    )

    r = _run_multi(
        build_inputs_floor,
        [_tool_record_a_build_inputs, _tool_record_a_build_inputs, _human_review_record],
    )
    cases.check(
        "build-inputs-required-all-tool-records-carry-plus-judgment-exempt-satisfied-PASS-F1",
        r["status"] == "satisfied", r,
    )

    _tool_qual_ok = '  [claim.evidence.tool_qualification]\n  basis = "vendor DO-330 letter"\n'
    _tool_record_c_tool_qual = (
        '\n  [[claim.evidence]]\n  kind      = "unit-test"\n  family    = "dynamic"\n'
        '  ref       = "test_r1"\n  result    = "pass"\n  tool      = "cargo test"\n'
        '  record    = "evidence/c1.json"\n' + _tool_qual_ok
    )
    _tool_record_d_no_tool_qual = _tool_record_b_no_build_inputs  # same shape, no tool_qualification

    r = _run_multi(tool_qual_floor, [_tool_record_c_tool_qual, _tool_record_d_no_tool_qual])
    cases.check(
        "tool-qualification-required-one-of-two-tool-records-missing-not-satisfied-FAIL-F1",
        r["status"] != "satisfied", r,
    )
    cases.check(
        "tool-qualification-required-one-of-two-tool-records-missing-reason-names-cond-10-F1",
        "cond 10" in r["reasons"].get("C1", ""), r["reasons"],
    )

    r = _run_multi(
        tool_qual_floor,
        [_tool_record_c_tool_qual, _tool_record_c_tool_qual, _human_review_record],
    )
    cases.check(
        "tool-qualification-required-all-tool-records-carry-plus-judgment-exempt-satisfied-PASS-F1",
        r["status"] == "satisfied", r,
    )

    # --- E (continued): third-party independence excludes BOTH sides -------------------------
    third_party_floor = '''  [requirement.evidence]
  min_tier          = "T5"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "third-party"
'''
    r = _run_pair(third_party_floor, '', author="Independent Lab X")
    cases.check("third-party-independent-author-satisfied-PASS", r["status"] == "satisfied", r)

    r = _run_pair(third_party_floor, '', author="Acme Class Test")  # the contract's own consumer name
    cases.check("third-party-author-equals-consumer-not-satisfied-FAIL", r["status"] != "satisfied", r)
    cases.check(
        "third-party-author-equals-consumer-reason-names-cond-8",
        "cond 8" in r["reasons"].get("C1", ""), r["reasons"],
    )

    r = _run_pair(third_party_floor, '', author="supplier-class-test")  # the contract's own producer name
    cases.check("third-party-author-equals-producer-not-satisfied-FAIL", r["status"] != "satisfied", r)

    r = _run_pair(third_party_floor, '')  # no author at all
    cases.check("third-party-no-author-not-satisfied-FAIL", r["status"] != "satisfied", r)

    # --- §6.2 conditions 1, 4, 6 (revision): coverage-time floors with no prior mutation-audited
    # fixture — `status != evidenced` (cond 1), the `methods` floor (cond 4), and a negative
    # `recipe_required` case on the claim's own `self_verify` (cond 6; the positive case already
    # lives in verification_chain.py's coverage-R1 fixture, but no fixture forced the negative
    # branch). Reuses `_package_toml`/`_coverage_contract` directly since `_claim_toml` hardcodes
    # `status = "evidenced"` and has no claim-level (non-evidence) extension point.
    def _claim_toml_custom(*, status: str = "evidenced", claim_extra: str = "", evidence_extra: str = "") -> str:
        return f'''
[[claim]]
id        = "C1"
clause    = "R1"
item      = "src/lib.rs::r1"
statement = "C1 satisfies R1"
band      = "A1"
weight    = "unweighted"
grade     = "test-only"
status    = "{status}"

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "test_r1"
  result    = "pass"
  tool      = "cargo test"
  record    = "evidence/c1.json"
{evidence_extra}
{claim_extra}'''

    def _run_custom(evidence_floor: str, **kwargs):
        with tempfile.TemporaryDirectory() as tdstr:
            td = Path(tdstr)
            c_path = write(td, "cov.toml", _coverage_contract(evidence_floor))
            c_hash = m11.digest_file("contract", c_path)
            p_path = write(
                td, "acceptance.toml",
                _package_toml(_claim_toml_custom(**kwargs)).replace("{{CONTRACT_HASH}}", c_hash),
            )
            contract, _e = load_toml(c_path)
            package, _e = load_toml(p_path)
            _rep, cov = check_package(package, contract, p_path, c_path, strict=False)
            return cov["requirements"]["R1"]

    lenient_floor = '''  [requirement.evidence]
  min_tier          = "T5"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
'''
    r = _run_custom(lenient_floor, status="partial")
    cases.check("status-not-evidenced-not-satisfied-FAIL-cond-1", r["status"] != "satisfied", r)
    cases.check("status-not-evidenced-reason-names-cond-1", "cond 1" in r["reasons"].get("C1", ""), r["reasons"])

    methods_pass_floor = lenient_floor + '  methods            = ["unit-test"]\n'
    methods_fail_floor = lenient_floor + '  methods            = ["property-test"]\n'
    r = _run_custom(methods_pass_floor)
    cases.check("methods-floor-matching-kind-satisfied-PASS-cond-4", r["status"] == "satisfied", r)
    r = _run_custom(methods_fail_floor)
    cases.check("methods-floor-no-matching-record-not-satisfied-FAIL-cond-4", r["status"] != "satisfied", r)
    cases.check(
        "methods-floor-no-matching-record-reason-names-cond-4",
        "cond 4" in r["reasons"].get("C1", ""), r["reasons"],
    )

    recipe_floor = lenient_floor.replace("recipe_required   = false", "recipe_required   = true")
    r = _run_custom(recipe_floor)  # no [claim.self_verify] at all
    cases.check("recipe-required-no-self-verify-not-satisfied-FAIL-cond-6", r["status"] != "satisfied", r)
    cases.check(
        "recipe-required-no-self-verify-reason-names-cond-6",
        "cond 6" in r["reasons"].get("C1", ""), r["reasons"],
    )
    r = _run_custom(recipe_floor, claim_extra='\n  [claim.self_verify]\n  command = "cargo test --test r1"\n  expect  = "test result: ok"\n')
    cases.check("recipe-required-with-self-verify-satisfied-PASS-cond-6", r["status"] == "satisfied", r)

    # --- §6.2 condition 5 (revision): control_required — no prior fixture forced this branch at
    # coverage-computation time (R1's fixture in verification_chain.py always carries a
    # satisfying control; nothing removed it to prove the floor is enforced).
    control_floor = lenient_floor.replace("control_required  = false", "control_required  = true")
    r = _run_custom(control_floor)  # no control and no watched_fail on the claim's evidence
    cases.check("control-required-no-control-not-satisfied-FAIL-cond-5", r["status"] != "satisfied", r)
    cases.check(
        "control-required-no-control-reason-names-cond-5",
        "cond 5" in r["reasons"].get("C1", ""), r["reasons"],
    )
    r = _run_custom(
        control_floor,
        evidence_extra='  [claim.evidence.control]\n  kind        = "mutation"\n  expectation = "red"\n  observed    = "red"\n  of_claim    = "C1"\n',
    )
    cases.check("control-required-observed-red-control-satisfied-PASS-cond-5", r["status"] == "satisfied", r)

    return cases.items


if __name__ == "__main__":
    import sys

    items = run()
    failed = [c for c in items if not c[1]]
    for name, _ok, detail in failed:
        print(f"SELFTEST FAIL: {name}: {detail}")
    print(f"{'SELFTEST FAILED' if failed else 'SELFTEST PASS'}: {len(items) - len(failed)}/{len(items)} cases")
    sys.exit(99 if failed else 0)
