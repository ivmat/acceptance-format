"""The 165 pre-split acceptance cases; review fixes complete their fixture inputs."""
from __future__ import annotations
import check_core as core
globals().update({k: v for k, v in vars(core).items() if not k.startswith("__")})


def validate(path, strict, strict_weight=False):
    """Materialize the legacy fixtures' in-tree spec and supply their isolated root.

    External F2 uses the same actual governing bytes, with its digest declared below.
    """
    path = Path(path)
    try:
        doc = tomllib.loads(path.read_text())
        spec = doc.get("spec", {})
        if spec.get("path") == "SPEC.md":
            (path.parent / "SPEC.md").write_text("Fixture governing document.\n")
    except (OSError, ValueError, AttributeError):
        pass
    return core.validate(path, strict, strict_weight, root=path.parent)

GOOD_FIXTURE = """
[format]
id = "acceptance/0"
profile = "acceptance/verification"
kind_registry = ["rust-crate", "rust-workspace"]

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 7
claims_total  = 7

[[claim]]
id        = "G-001"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a never panics"
band      = "A1"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a_no_panic"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-a.json"

  [claim.self_verify]
  command = "cargo kani --harness check_a_no_panic"
  expect  = "VERIFICATION:- SUCCESSFUL"

[[claim]]
id        = "G-002"
clause    = "S-2"
item      = "src/lib.rs::b"
statement = "b is memory safe in its unsafe block"
band      = "A2"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b.json"

  # bmc-family ABLATION control (A2 whitelist = mutation OR ablation, assurance-bands.md rule 6,
  # tightened 2026-08-22): the harness's bounds-check precondition is removed and the SAME
  # unsafe-block property must now break (observed red).
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe (ablated: bounds-check precondition removed)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b-control.json"

    [claim.evidence.control]
    kind        = "ablation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-002"

  [claim.self_verify]
  command = "cargo kani --harness verify_b_memsafe"
  expect  = "VERIFICATION:- SUCCESSFUL"

[[claim]]
id        = "G-003"
clause    = "S-3"
item      = "src/lib.rs::c"
statement = "c meets its function contract"
band      = "A3"
grade     = "contract"
bounds    = "unbounded (function-contracts, symbolic domain)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c.json"

  # bmc-family mutation control: the SAME harness re-run against a mutated impl, which must
  # now fail (observed red) — der's real mechanism for its Kani contract controls.
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"

  [claim.self_verify]
  command = "cargo kani --harness verify_c_contract"
  expect  = "VERIFICATION:- SUCCESSFUL"

[[claim]]
id        = "G-004"
clause    = "S-4"
item      = "src/lib.rs::d"
statement = "d matches its foundational spec"
band      = "A4"
grade     = "contract"
bounds    = "unbounded (Lean kernel)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff"
  result    = "pass"
  tool      = "lean4@4.x-pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d.lean"

  # kernel-family mutation control: the theorem source is mutated and re-checked; the kernel
  # must REJECT it (typecheck fails, observed red) — der's real Lean-lid mutation controls.
  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutants.lean"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-004"

  [claim.self_verify]
  command = "lake env lean lean/D.lean"
  expect  = "no errors"

[[claim]]
id        = "G-005"
clause    = "S-5"
item      = "src/lib.rs::e"
statement = "e was reviewed"
band      = "A0"
grade     = "inspection-argued"
doc_ref   = "docs/e-review.md"
status    = "evidenced"

  [[claim.evidence]]
  kind     = "human-review"
  family   = "judgment"
  ref      = "e-review"
  result   = "pass"
  tool     = "manual"
  reviewer = "ivo"
  record   = "evidence/does-not-exist-e.txt"

[[claim]]
id        = "G-006"
clause    = "S-6"
item      = "src/lib.rs::f"
statement = "f timing behavior"
band      = "A0"
grade     = "not-covered"
status    = "gap"

  [claim.self_verify]
  command = "grep -rn 'timing_budget' src/"
  expect  = "no output"
  positive_control = "grep -rn 'panic' src/ matches multiple lines"

[[claim]]
id        = "G-007"
clause    = "S-7"
item      = "src/lib.rs::g"
statement = "g contract, tool unsupported"
band      = "A0"
grade     = "not-covered"
status    = "parked"
parked_reason = "kani unsupported_construct — tool change needed"

  [claim.self_verify]
  command = "cargo kani --harness verify_g_contract"
  expect  = "VERIFICATION:- SUCCESSFUL"
  positive_control = "grep -rn 'unsupported_construct' target/kani-log matches"
"""


# --------------------------------------------------------------------------
# Standalone control-gate fixtures (assurance-bands.md rule 6) — isolated single-claim
# manifests, distinct from GOOD_FIXTURE's bundled coverage, per the four scenarios the
# control gate must draw a hard line around.
# --------------------------------------------------------------------------

def _mini_manifest(claim_toml: str) -> str:
    # 0.1-DRAFT W1: weight defaults to ABSENT, and the mandatory anti-overclaim
    # machinery only fires on claims that CLAIM weight. These fixtures exist to
    # exercise that machinery, so a claim that does not say otherwise is made
    # weighted here. Fixtures for the unweighted tier declare it explicitly.
    if "weight" not in claim_toml:
        m = re.search(r'(?m)^grade\s*=\s*"([^"]+)"', claim_toml)
        cs = re.search(r'(?m)^clause_source\s*=\s*"([^"]+)"', claim_toml)
        unweightable = (
            (m and m.group(1) in UNWEIGHTABLE_GRADES)
            or (cs and cs.group(1) in CLAUSE_SOURCES_UNWEIGHTABLE)
        )
        tier = "unweighted" if unweightable else "weighted"
        claim_toml = re.sub(r"(?m)^(\[\[claim\]\])$",
                            r'\1\nweight    = "%s"' % tier, claim_toml, count=1)
    return f"""
[format]
id = "acceptance/0"
profile = "acceptance/verification"
kind_registry = ["rust-crate", "rust-workspace"]

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 1
claims_total  = 1

{claim_toml}
"""


_A3_CLAIM_WITH_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::c"
statement = "c meets its function contract"
band      = "A3"
grade     = "contract"
bounds    = "unbounded (function-contracts, symbolic domain)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c.json"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"

  [claim.self_verify]
  command = "cargo kani --harness verify_c_contract"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# der's real, previously-impossible case: a KERNEL-family control (a mutated Lean theorem the
# kernel rejects) lifting an A4 claim — see der's Lean-lid mutation controls, STATUS 2026-08-22.
_A4_CLAIM_WITH_KERNEL_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "lean/D.lean"
statement = "d matches its foundational spec"
band      = "A4"
grade     = "contract"
bounds    = "unbounded (Lean kernel)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff"
  result    = "pass"
  tool      = "lean4@4.x-pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d.lean"

  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutant.lean"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"

  [claim.self_verify]
  command = "lake env lean lean/D.lean"
  expect  = "no errors"
"""

_A1_HYGIENE_NO_CONTROL_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a never panics"
band      = "A1"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a_no_panic"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-a.json"

  [claim.self_verify]
  command = "cargo kani --harness check_a_no_panic"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# per-band control-kind whitelist (assurance-bands.md rule 6, tightened 2026-08-22): A2 accepts
# mutation OR ablation, never planted-twin. Base fixture uses ablation (must PASS); the
# planted-twin variant below (same shape, control.kind swapped) must FAIL.
_A2_CLAIM_WITH_ABLATION_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::b"
statement = "b is memory safe in its unsafe block"
band      = "A2"
grade     = "contract"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b.json"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe (ablated: bounds-check precondition removed)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b-control.json"

    [claim.evidence.control]
    kind        = "ablation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"

  [claim.self_verify]
  command = "cargo kani --harness verify_b_memsafe"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# F3 (tightened 2026-08-22): der's real A3 module claims are assertion-style Kani harnesses — a
# zero-annotation harness with an internal assert, NOT `-Z function-contracts` — backed by a red
# bmc mutation control. That is not an under-claim; the widened A3 species text in
# assurance-bands.md says so. `record` points at "acceptance.toml" (the manifest's own generated
# file, guaranteed to exist alongside itself) so this fixture can be checked with --strict too.
_DER_SHAPED_A3_ASSERTION_CLAIM = """
[[claim]]
id        = "K-integer"
clause    = "PM/integer"
item      = "der-verified/src/integer.rs"
statement = "decode rejects non-minimal INTEGER encodings"
band      = "A3"
grade     = "contract"
clause_source = "external-standard"
bounds    = "bounded: unwind=16, input<=12B"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "integer::verify_rejects_nonminimal"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=16, input<=12B"
  semantics = ""
  record    = "acceptance.toml"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "integer::verify_rejects_nonminimal (mutant: dropped padding check)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "unwind=16, input<=12B"
  semantics = ""
  record    = "acceptance.toml"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "K-integer"

  [claim.self_verify]
  command = "cargo kani --harness integer::verify_rejects_nonminimal"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# F4 (tightened 2026-08-22): a `partial` claim's control can be mis-pointed at a DIFFERENT
# existing claim too — this must be caught even though `partial` never asserts its band is
# reached (check_control_of_claim_mismatch now runs for every status).
_PARTIAL_CLAIM_WITH_MISPOINTED_CONTROL = """
[format]
id = "acceptance/0"
profile = "acceptance/verification"
kind_registry = ["rust-crate", "rust-workspace"]

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 2
claims_total  = 2

[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::c"
statement = "c partially meets its contract"
band      = "A3"
grade     = "test-only"
status    = "partial"

  [[claim.evidence]]
  kind   = "unit-test"
  family = "dynamic"
  ref    = "c::tests"
  result = "pass"
  tool   = "rustc@1.79-pinned"
  cases  = 3
  record = "evidence/does-not-exist.log"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-002"

  [claim.self_verify]
  command = "cargo test c"
  expect  = "test result: ok"

[[claim]]
id        = "C-002"
clause    = "S-2"
item      = "src/lib.rs::d"
statement = "d is unrelated"
band      = "A0"
grade     = "ungraded"
status    = "gap"
"""


# 0.1-DRAFT.md fixtures — clause_source / self_verify / spec.axis+external /
# coverage.denominator+slice_note (denominator/slice_note/clause_source="test-name" are
# CLAIM-CLASSES-AWAITING-WEIGHT.md EXPERIMENTAL fields: parseable, shape-checked, not meaning-enforced).

_GAP_CLAIM_WITH_SELF_VERIFY = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h has no evidence yet"
band      = "A0"
grade     = "not-covered"
status    = "gap"

  [claim.self_verify]
  command = "grep -rn 'h_impl' src/"
  expect  = "no output"
  positive_control = "grep -rn 'g_impl' src/ matches 3 lines"
"""

# 0.1-DRAFT §1/§7.1: `out-of-scope` says the producer deliberately does not claim the item, so
# its status is one of the no-check statuses and it has no recipe. `scope_ref` is a LOCATOR.
_OUT_OF_SCOPE_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h is deliberately not implemented"
band      = "A0"
grade     = "out-of-scope"
scope_ref = "docs/scope.md#a"
status    = "gap"
"""

_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h is not implemented"
band      = "A0"
status    = "gap"
grade     = "not-covered"

  [claim.self_verify]
  command = "grep -rn 'h_impl' src/"
  expect  = "no output"
"""

_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h self-verify recipe"
band      = "A0"
grade     = "not-covered"
status    = "gap"

  [claim.self_verify]
  positive_control = "grep -rn 'g_impl' src/ matches 3 lines"
  command = "cargo test h"
"""


# --------------------------------------------------------------------------
# Enforcement-site coverage fixtures (external-review finding, 2026-08-25): 47
# of the file's 83 rep.error/rep.warn/rep.weight_pending call sites never
# fired in any prior selftest fixture -- the fixtures asserted only the
# passing direction, so "a check nobody watched fail is untested" applied to
# nearly half the validator. Each fixture below exists to fire ONE named
# site; confirmed red-before/green-after by instrumentation, not by reading.
# --------------------------------------------------------------------------

# a dynamic-only (unit-test) claim -- reused (via targeted .replace()) to
# fire the "cases" int-pos check, a missing universal evidence field, an
# invalid `result` enum value, and the A2-band dynamic-only-species error.
_UNIT_TEST_DYNAMIC_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::t"
statement = "t behavior is tested"
band      = "A1"
grade     = "test-only"
status    = "evidenced"

  [[claim.evidence]]
  kind   = "unit-test"
  family = "dynamic"
  ref    = "t::tests"
  result = "pass"
  tool   = "rustc@1.79-pinned"
  cases  = 3
  record = "evidence/does-not-exist-t.log"

  [claim.self_verify]
  command = "cargo test t"
  expect  = "test result: ok"
"""

# freedom-shaped (miri) dynamic-only evidence at A1 with a statement that
# doesn't read as a freedom claim -- fires the A1 dynamic-only advisory warn
# without tripping the A1 control-gate (miri is DYNAMIC_FREEDOM_KINDS).
_MIRI_A1_NO_FREEDOM_WORDS_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::u"
statement = "u returns the correct value"
band      = "A1"
grade     = "mechanical"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "miri"
  family    = "dynamic"
  ref       = "miri_u"
  result    = "pass"
  tool      = "miri@nightly-pinned"
  semantics = "stacked-borrows"
  record    = "evidence/does-not-exist-u.log"

  [claim.self_verify]
  command = "cargo miri test u"
  expect  = "test result: ok"
"""

# flux-refinement (reserved kind) at the reserved A3.5 band -- fires BOTH
# reserved-kind and reserved-band advisory warns on a manifest that
# otherwise validates cleanly (KIND_REGISTRY's flux-refinement is
# warn_reserved; A3.5 is BANDS' only reserved band).
_FLUX_REFINEMENT_A35_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::r"
statement = "r meets its refinement type"
band      = "A3.5"
grade     = "probe"
bounds    = "bounded: refinement domain"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "flux-refinement"
  family    = "smt-refinement"
  ref       = "verify_r_refinement"
  result    = "pass"
  tool      = "flux@pinned"
  bounds    = "refinement domain: i32"
  semantics = "liquid types"
  record    = "evidence/does-not-exist-r.json"

  [claim.self_verify]
  command = "cargo flux --harness verify_r_refinement"
  expect  = "flux: verified"
"""

# grade not in GRADES_REQUIRING_SELF_VERIFY (so check_self_verify does not
# early-return before the type check), self_verify given as a bare string
# instead of a table -- fires the "[claim.self_verify] must be a table"
# branch. weight is forced explicitly (rather than left to _mini_manifest's
# auto-detection) so check_self_verify -- gated on _is_weighted -- runs at
# all despite "ungraded" being an UNWEIGHTABLE_GRADES member.
_UNGRADED_CLAIM_BAD_SELF_VERIFY_TYPE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::v"
statement = "v has no decided grade yet"
band      = "A0"
grade     = "ungraded"
weight    = "weighted"
status    = "gap"
self_verify = "oops"
"""

# a weighted claim graded "inspection-argued" with no doc_ref -- fires the
# doc_ref advisory warn (check_grade_companions only runs for weighted
# claims, so the grade must be forced weighted explicitly here; this also
# fires the WEIGHT REFUSED "no deciding machinery" error, already covered
# elsewhere, alongside it).
_WEIGHTED_INSPECTION_ARGUED_NO_DOC_REF = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::w"
statement = "w was reviewed"
band      = "A0"
grade     = "inspection-argued"
weight    = "weighted"
status    = "gap"
"""

# a weighted claim graded "unspecified" with no clause_source = "none" --
# fires the clause_source advisory warn, same weighted-forcing rationale as
# the inspection-argued fixture above.
_WEIGHTED_UNSPECIFIED_NO_CLAUSE_SOURCE_NONE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::x"
statement = "x behavior is unspecified"
band      = "A0"
grade     = "unspecified"
weight    = "weighted"
status    = "gap"
"""

# an explicit, out-of-vocabulary `weight` value -- fires the weight-enum
# check (distinct from `weight` simply being absent, which means unweighted
# and is never an error).
_CLAIM_BAD_WEIGHT_VALUE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::y"
statement = "y has a bogus weight value"
band      = "A0"
grade     = "ungraded"
weight    = "bogus"
status    = "gap"
"""

# top-level `claim` present but not an array of tables -- fires the
# "[[claim]] entries must form an array of tables" branch. A full standalone
# manifest (not a _mini_manifest fragment): _mini_manifest always builds a
# well-formed [[claim]] array itself.
_CLAIM_NOT_ARRAY_MANIFEST = """
claim = "oops"

[format]
id = "acceptance/0"
profile = "acceptance/verification"
kind_registry = ["rust-crate", "rust-workspace"]

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 1
claims_total  = 0
"""

# claim.evidence present but not a list (a bare string) -- fires the
# "[[claim.evidence]] must be an array of tables" branch.
_CLAIM_EVIDENCE_NOT_ARRAY = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::z"
statement = "z has malformed evidence field"
band      = "A0"
grade     = "ungraded"
status    = "gap"
evidence  = "oops"
"""

# claim.evidence is a list, but one entry is not a table -- fires the
# per-entry "must be a table" branch. status = "gap" (not "evidenced") so
# this never reaches check_band_reachability, which -- unlike
# check_control_of_claim_mismatch -- historically had no defensive
# isinstance guard of its own; see the check_claims fix (2026-08-25) that
# now filters non-dict evidence entries once, upstream of both consumers.
_CLAIM_EVIDENCE_ENTRY_NOT_TABLE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::z2"
statement = "z2 has a malformed evidence entry"
band      = "A0"
grade     = "ungraded"
status    = "gap"
evidence  = ["oops"]
"""


def _verdict_label(rep: "Reporter") -> str:
    """F4 (2026-09-17): the one place that decides the PASS / PASS-PROSPECTIVE word, so
    `main()` and the selftest read the SAME logic — the parity-drift lesson
    (`acceptance_grammar.py`'s own reason for existing) applied to this checker's own verdict
    label instead of to a cross-representation rule."""
    return "PASS-PROSPECTIVE" if getattr(rep, "is_prospective", False) else "PASS"


def _run_case(name: str, toml_text: str, expect_pass: bool, expect_substr: str | None = None,
              strict_weight: bool = False) -> str | None:
    """Returns None on success, or a failure description string."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "acceptance.toml"
        p.write_text(toml_text)
        rep = validate(p, strict=False, strict_weight=strict_weight)
        passed = rep.ok()
        if expect_pass:
            if not passed:
                return f"{name}: expected PASS, got errors: {rep.errors}"
            return None
        else:
            if passed:
                return f"{name}: expected FAIL, but validation passed"
            all_msgs = " | ".join(rep.errors)
            if expect_substr and expect_substr not in all_msgs:
                return (
                    f"{name}: failed, but not for the expected reason — wanted substring "
                    f"{expect_substr!r} in errors {rep.errors!r}"
                )
            return None


def selftest() -> int:
    failures: list[str] = []
    count = 0

    count += 1
    r = _run_case("good fixture", GOOD_FIXTURE, expect_pass=True)
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A3 claim with a matching observed-red bmc mutation control",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A4 claim with a matching observed-red KERNEL mutation control "
        "(family-agnostic control — der's real Lean-lid case, previously impossible)",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A1 hygiene claim with no control",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A2 claim with an ablation control PASSES (per-band whitelist)",
        _mini_manifest(_A2_CLAIM_WITH_ABLATION_CONTROL),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A2 claim with ONLY a planted-twin control FAILS (per-band whitelist — "
        "planted-twin never satisfies the band-lift gate)",
        _mini_manifest(_A2_CLAIM_WITH_ABLATION_CONTROL.replace(
            'kind        = "ablation"', 'kind        = "planted-twin"'
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: dangling control.of_claim (phantom claim id) is an error",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'of_claim    = "C-001"', 'of_claim    = "A-999"'
        )),
        expect_pass=False,
        expect_substr="does not match any claim id in this manifest",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A3 claim with no control",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            """
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"
""",
            "",
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A4 claim with no control",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            """
  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutant.lean"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"
""",
            "",
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: control whose of_claim names a different claim doesn't lift this one",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'of_claim    = "C-001"', 'of_claim    = "SOME-OTHER-CLAIM"'
        )),
        expect_pass=False,
        expect_substr="does not name this claim",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: control that observed the WRONG thing (observed != expectation) "
        "doesn't satisfy the gate",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'observed    = "red"', 'observed    = "green"'
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    # F1 (tightened 2026-08-22): observed==expectation alone is NOT enough to band-lift — a
    # green/green (or sat/sat) control "behaved as predicted" but is not a literal red, so it must
    # NOT lift A3/A4. Only a genuine bad_case substitution proves this (a naive observed==red-only
    # check would already reject green/red or red/green; these are the ones that used to slip
    # through because expectation==observed was true).
    count += 1
    r = _run_case(
        "standalone: green/green mutation control does NOT lift A3 (behaved-as-predicted != "
        "band-lifting red)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'expectation = "red"\n    observed    = "red"',
            'expectation = "green"\n    observed    = "green"',
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: sat/sat mutation control does NOT lift A4 (behaved-as-predicted != "
        "band-lifting red)",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            'expectation = "red"\n    observed    = "red"',
            'expectation = "sat"\n    observed    = "sat"',
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    # F2 (tightened 2026-08-22): a band-lifting control's CARRIER record must be species-
    # compatible with the band — (i) a bmc carrier can't lift A4 (needs kernel); (ii) a
    # judgment-family carrier (human-review) can't lift ANYTHING (never in any allowed set).
    count += 1
    r = _run_case(
        "standalone (F2-i): a bmc-carrier mutation control under an A4 claim does NOT lift it "
        "(A4 needs a kernel-family carrier)",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            """  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutant.lean"
""",
            """  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_d_bmc (mutant: off-by-one)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=16"
  semantics = ""
  record    = "evidence/does-not-exist-d-mutant.json"
""",
        )),
        expect_pass=False,
        expect_substr="not species-compatible with band",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone (F2-ii): a human-review record carrying a control under A3 does NOT lift it "
        "(judgment is never a valid carrier family)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            """  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"
""",
            """  [[claim.evidence]]
  kind     = "human-review"
  family   = "judgment"
  ref      = "c-mutant-review"
  result   = "pass"
  tool     = "manual"
  reviewer = "ivo"
  record   = "evidence/does-not-exist-c-review.txt"
""",
        )),
        expect_pass=False,
        expect_substr="not species-compatible with band",
    )
    if r:
        failures.append(r)

    # F3 (tightened 2026-08-22): a der-shaped A3 claim — an assertion-style Kani harness (no
    # `-Z function-contracts`), backed by a red bmc mutation control — validates cleanly, WITH
    # ZERO WARNINGS, under --strict.
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_DER_SHAPED_A3_ASSERTION_CLAIM))
        _rep = validate(_p, strict=True)
        if not _rep.ok():
            failures.append(
                f"der-shaped A3 (assertion harness + red mutation control): expected PASS "
                f"--strict, got errors: {_rep.errors}"
            )
        elif _rep.warnings:
            failures.append(
                f"der-shaped A3 (assertion harness + red mutation control): expected ZERO "
                f"warnings under --strict, got: {_rep.warnings}"
            )

    # F4 (tightened 2026-08-22): the of_claim-mismatch check now runs for `partial` claims too.
    count += 1
    r = _run_case(
        "standalone: a `partial` claim carrying a mis-pointed control FAILS "
        "(check now runs for every status, not just 'evidenced')",
        _PARTIAL_CLAIM_WITH_MISPOINTED_CONTROL,
        expect_pass=False,
        expect_substr="does not name this claim",
    )
    if r:
        failures.append(r)

    # 0.1-DRAFT.md §1/§2: `grade` is now REQUIRED, closed nine-token vocabulary. The base fixture
    # carries grade = "probe" (self_verify + bounds already present); these tests swap that value
    # (and, where the target grade needs different companions, add them) to exercise every token.
    count += 1
    r = _run_case(
        "standalone: claim with grade = 'contract' passes (same companions as 'probe' — "
        "0.1-DRAFT §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "contract"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with an invalid grade value FAILS (0.1-DRAFT §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "bogus"'
        )),
        expect_pass=False,
        expect_substr="grade must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim missing grade entirely FAILS (0.1-DRAFT §1, tightened from optional "
        "to required — the single largest break from the pre-freeze schema)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace('grade     = "probe"\n', '')),
        expect_pass=False,
        expect_substr="requires 'grade'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'ungraded' passes with no companion fields at all "
        "(0.1-DRAFT §1 — always legal, never strong)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "ungraded"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'test-only' passes (self_verify already present, no "
        "bounds required — 0.1-DRAFT §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "test-only"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'mechanical' passes (self_verify already present — "
        "0.1-DRAFT §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "mechanical"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'inspection-argued' and a doc_ref passes, no "
        "self_verify needed (0.1-DRAFT §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"',
            'grade     = "inspection-argued"\ndoc_ref   = "docs/a-review.md"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'inspection-argued' with NO doc_ref PASSES with a warning -- never weight-eligible, so W3 imposes no obligation",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "inspection-argued"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'not-covered', self_verify.command + positive_control "
        "passes (0.1-DRAFT §1/§4)",
        # 0.1-DRAFT §7.1 (2026-08-25): `not-covered` and `out-of-scope` assert that nothing
        # checked the item, so they cohere only with the statuses that assert no check
        # succeeded. These four cases used to hang off the EVIDENCED A1 hygiene claim, which is
        # the incoherent pairing the §7.1 table now refuses -- the fixtures were written before
        # the rule and are re-based here, not exempted from it.
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'expect  = "no output"',
            'expect  = "no output"\n'
            '  positive_control = "grep -rn \'impl\' src/ matches multiple lines"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'not-covered' and self_verify.command but NO "
        "positive_control FAILS (0.1-DRAFT §4 — now unconditional on this grade)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL),
        expect_pass=False,
        expect_substr="requires a nonempty self_verify.positive_control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'out-of-scope' and a scope_ref passes (0.1-DRAFT §1)",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'out-of-scope' and NO scope_ref FAILS (0.1-DRAFT §1)",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM.replace(
            'scope_ref = "docs/scope.md#a"\n', ""
        )),
        expect_pass=False,
        expect_substr="requires a nonempty claim-level 'scope_ref'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'unspecified' and clause_source = 'none' passes "
        "(0.1-DRAFT §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"',
            'grade     = "unspecified"\nclause_source = "none"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'unspecified' with NO clause_source PASSES with a warning -- never weight-eligible (W3)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "unspecified"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade in {contract, probe} without a claim-level bounds field FAILS "
        "(0.1-DRAFT §5)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'bounds    = "bounded: unwind=8"\n', ''
        )),
        expect_pass=False,
        expect_substr="requires a claim-level 'bounds'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'probe' with a bounds value not starting with "
        "'bounded'/'unbounded' FAILS (0.1-DRAFT §5)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'bounds    = "bounded: unwind=8"', 'bounds    = "unwind=8 only"'
        )),
        expect_pass=False,
        expect_substr="requires a claim-level 'bounds'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade in {contract, probe, test-only, mechanical, not-covered} without "
        "self_verify at all FAILS (0.1-DRAFT §1/§3)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            """
  [claim.self_verify]
  command = "cargo kani --harness check_a_no_panic"
  expect  = "VERIFICATION:- SUCCESSFUL"
""",
            "",
        )),
        expect_pass=False,
        expect_substr="requires a [claim.self_verify] table",
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §6: clause_source — invalid value fails, "test-name" warns (not an
    # error), a valid non-warning value passes silently.
    count += 1
    r = _run_case(
        "standalone: claim with an invalid clause_source value FAILS (coverage-ledger.md §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "evidenced"\nclause_source = "bogus"'
        )),
        expect_pass=False,
        expect_substr="clause_source must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "evidenced"\nclause_source = "test-name"'
        )))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"clause_source = 'test-name': expected PASS, got errors: {_rep.errors}"
            )
        elif not any("test-name" in w and "same artifact" in w for w in _rep.warnings):
            failures.append(
                f"clause_source = 'test-name': expected a WARNING naming the self-referential "
                f"clause/evidence artifact, got: {_rep.warnings}"
            )

    count += 1
    r = _run_case(
        "standalone: claim with clause_source = 'doc-comment' passes with no warning "
        "(coverage-ledger.md §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "evidenced"\nclause_source = "doc-comment"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §3: [claim.self_verify] — unknown key is an error (strict, new table).
    count += 1
    r = _run_case(
        "standalone: self_verify with an unknown key FAILS (coverage-ledger.md §3, strict table)",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT.replace(
            'command = "cargo test h"',
            'command = "cargo test h"\n  expect  = "ok"\n  bogus_key = "x"',
        )),
        expect_pass=False,
        expect_substr="unknown field",
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §3: command present => expect is required and nonempty.
    count += 1
    r = _run_case(
        "standalone: self_verify.command without expect FAILS (coverage-ledger.md §3)",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT),
        expect_pass=False,
        expect_substr="self_verify.expect is required",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: self_verify.command with expect PASSES (coverage-ledger.md §3)",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT.replace(
            'command = "cargo test h"', 'command = "cargo test h"\n  expect  = "ok"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §4: grade = "not-covered" with self_verify.command requires a nonempty
    # positive_control.
    count += 1
    r = _run_case(
        "standalone: grade = 'not-covered' with self_verify.command and NO positive_control "
        "FAILS (coverage-ledger.md §4)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL),
        expect_pass=False,
        expect_substr="requires a nonempty self_verify.positive_control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'not-covered' with self_verify.command AND positive_control PASSES "
        "(coverage-ledger.md §4)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "grep -rn \'impl\' src/ matches"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §3: self_verify IS permitted on status = "gap"/"parked" — the one
    # widening this facet makes over format.md's "gap/parked claims carry no evidence" rule; it
    # must not trip that check (which only looks at claim.evidence).
    count += 1
    r = _run_case(
        "standalone: self_verify on a 'gap' claim PASSES (coverage-ledger.md §3, permitted "
        "widening — self_verify is a recipe, not evidence)",
        _mini_manifest(_GAP_CLAIM_WITH_SELF_VERIFY),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: self_verify on a 'parked' claim PASSES (coverage-ledger.md §3)",
        _mini_manifest(
            _GAP_CLAIM_WITH_SELF_VERIFY.replace(
                'status    = "gap"',
                'status    = "parked"\nparked_reason = "tool change needed"',
            )
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # 0.1-DRAFT.md §6: [spec].axis is now REQUIRED; [spec].external stays optional and
    # type-checked. _mini_manifest already carries a valid default axis, so these tests
    # target-replace that line rather than blindly inserting a second one.
    count += 1
    r = _run_case(
        "standalone: [spec].external present and well-typed passes alongside the required "
        "axis (0.1-DRAFT §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"',
            'axis    = "public API surface of selftest-lib"\n'
            'external = ["ITU-T X.690 (2021)"]',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [spec].axis empty string FAILS (0.1-DRAFT §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"', 'axis    = ""',
        ),
        expect_pass=False,
        expect_substr="[spec].axis must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [spec].axis missing entirely FAILS (0.1-DRAFT §6, tightened from "
        "optional to required)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"\n', '',
        ),
        expect_pass=False,
        expect_substr="[spec].axis must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [spec].external not a list FAILS (0.1-DRAFT §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"',
            'axis    = "public API surface of selftest-lib"\nexternal = "RFC 5280"',
        ),
        expect_pass=False,
        expect_substr="[spec].external must be a list of nonempty strings",
    )
    if r:
        failures.append(r)

    # CLAIM-CLASSES-AWAITING-WEIGHT.md C1: [coverage].denominator / slice_note — EXPERIMENTAL, parseable and
    # shape-checked, meaning not enforced.
    count += 1
    r = _run_case(
        "standalone: [coverage].denominator = 'slice' without slice_note FAILS "
        "(CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "slice"',
        ),
        expect_pass=False,
        expect_substr="denominator = 'slice' requires a nonempty 'slice_note'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [coverage].denominator = 'slice' WITH slice_note PASSES "
        "(CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1",
            'claims_total  = 1\ndenominator = "slice"\nslice_note = "sampled subset only"',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [coverage].denominator = 'complete' PASSES (CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "complete"',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [coverage].denominator with an invalid value FAILS (CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "bogus"',
        ),
        expect_pass=False,
        expect_substr="[coverage].denominator must be one of",
    )
    if r:
        failures.append(r)

    # CLAIM-CLASSES-AWAITING-WEIGHT.md C1: a valid denominator value PASSES but carries an EXPERIMENTAL warning
    # naming CLAIM-CLASSES-AWAITING-WEIGHT.md — presence is parseable, meaning is not enforced.
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "complete"',
        ))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"[coverage].denominator EXPERIMENTAL warning: expected PASS, got errors: "
                f"{_rep.errors}"
            )
        elif not any(
            "EXPERIMENTAL" in w and "CLAIM-CLASSES-AWAITING-WEIGHT.md" in w for w in _rep.warnings
        ):
            failures.append(
                f"[coverage].denominator EXPERIMENTAL warning: expected a warning naming "
                f"CLAIM-CLASSES-AWAITING-WEIGHT.md, got: {_rep.warnings}"
            )

    # ======================================================================
    # Enforcement-site coverage fixtures (external-review finding, 2026-08-25).
    # Each block below is named for the ONE previously-dead site it fires;
    # see the fixture constants above this function for the manifests used.
    # ======================================================================

    # -- _check_field generic branches (registry-driven per-kind extra fields) --

    count += 1
    r = _run_case(
        "coverage: kani-harness evidence.bounds present but empty string fires the "
        "str-nonempty branch of _check_field (distinct from the field being absent)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'bounds    = "unwind=8"', 'bounds    = ""'
        )),
        expect_pass=False,
        expect_substr="field 'bounds' must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: kani-harness evidence.semantics (str-any) given a non-string value "
        "fires the str-any type branch of _check_field",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'semantics = ""', 'semantics = 123'
        )),
        expect_pass=False,
        expect_substr="field 'semantics' must be a string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: lean-theorem evidence.axioms (list) given a non-list value fires the "
        "list type branch of _check_field",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            'result    = "pass"\n  tool      = "lean4@4.x-pinned"\n  axioms    = []',
            'result    = "pass"\n  tool      = "lean4@4.x-pinned"\n  axioms    = "not-a-list"',
        )),
        expect_pass=False,
        expect_substr="field 'axioms' must be a list",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: unit-test evidence.cases (int-pos) given 0 fires the int-pos branch "
        "of _check_field",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('cases  = 3', 'cases  = 0')),
        expect_pass=False,
        expect_substr="field 'cases' must be an integer >= 1",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: evidence.mutants_caught (int-nonneg) given a negative value fires the "
        "int-nonneg branch of _check_field (result='fail' so the separate "
        ">=1-observed-red-mutant check does not also fire)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'record    = "evidence/does-not-exist-c-mutants.json"',
            'record    = "evidence/does-not-exist-c-mutants.json"\n  mutants_caught = -1',
        )),
        expect_pass=False,
        expect_substr="field 'mutants_caught' must be an integer >= 0",
    )
    if r:
        failures.append(r)

    # NOTE (dead code, not fixture-closable): _check_field's `else` branch ("internal
    # validator bug — unknown tag") is unreachable through any TOML input. Every call site
    # passes a tag from the closed set {str-nonempty, str-any, list, int-pos, int-nonneg},
    # all handled above; the tag values come from KIND_REGISTRY and the two hardcoded
    # mutants_total/mutants_caught calls, none of which is user-controlled. Left in place
    # per instructions (not deleted, not papered over) — recorded here as a genuine
    # unreachable site, not a fixture gap.

    # -- universal evidence fields, result enum, band-species warns --

    count += 1
    r = _run_case(
        "coverage: evidence missing a universal field ('tool') fires the universal-field "
        "nonempty-string check (distinct from any per-kind registry field)",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('tool   = "rustc@1.79-pinned"\n', '')),
        expect_pass=False,
        expect_substr="universal field 'tool' must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: evidence.result given a value outside {pass,fail,unsupported} fires "
        "the result-enum check",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('result = "pass"', 'result = "bogus"')),
        expect_pass=False,
        expect_substr="result must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: an A2 claim resting on dynamic-only evidence fires the "
        "dynamic-family band-A0/A1-only error (A2 is neither)",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('band      = "A1"', 'band      = "A2"')),
        expect_pass=False,
        expect_substr="all evidence is dynamic-family — band must be A0 or A1, got",
    )
    if r:
        failures.append(r)

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_MIRI_A1_NO_FREEDOM_WORDS_CLAIM))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"A1 dynamic-only (miri), statement doesn't read as freedom claim: "
                f"expected PASS, got errors: {_rep.errors}"
            )
        elif not any("doesn't read as a" in w and "freedom claim" in w for w in _rep.warnings):
            failures.append(
                f"A1 dynamic-only (miri), statement doesn't read as freedom claim: "
                f"expected the freedom-claim advisory warning, got: {_rep.warnings}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_FLUX_REFINEMENT_A35_CLAIM))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"flux-refinement evidence at reserved band A3.5: expected PASS, got "
                f"errors: {_rep.errors}"
            )
        else:
            if not any("reserved kind" in w and "flux-refinement" in w for w in _rep.warnings):
                failures.append(
                    f"flux-refinement evidence: expected the reserved-kind warning, got: "
                    f"{_rep.warnings}"
                )
            if not any("reserved band" in w for w in _rep.warnings):
                failures.append(
                    f"band A3.5: expected the reserved-band warning, got: {_rep.warnings}"
                )

    # -- control block structural fields --

    count += 1
    r = _run_case(
        "coverage: evidence.control given a non-table value fires the "
        "\"'control' must be a table\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'record    = "evidence/does-not-exist-a.json"',
            'record    = "evidence/does-not-exist-a.json"\n  control   = "bogus"',
        )),
        expect_pass=False,
        expect_substr="'control' must be a table",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.kind given a value outside CONTROL_KIND_VALUES fires the "
        "control.kind-enum check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'kind        = "mutation"', 'kind        = "bogus-kind"'
        )),
        expect_pass=False,
        expect_substr="control.kind must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.expectation given a value outside CONTROL_EXPECTATION_VALUES "
        "fires the control.expectation-enum check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'expectation = "red"', 'expectation = "bogus"'
        )),
        expect_pass=False,
        expect_substr="control.expectation must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.observed given an empty string fires the control.observed "
        "nonempty-string check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'observed    = "red"', 'observed    = ""'
        )),
        expect_pass=False,
        expect_substr="control.observed must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.of_claim given an empty string fires the control.of_claim "
        "nonempty-string check (distinct from a nonempty-but-dangling of_claim)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'of_claim    = "C-001"', 'of_claim    = ""'
        )),
        expect_pass=False,
        expect_substr="control.of_claim must be a nonempty string",
    )
    if r:
        failures.append(r)

    # -- mutants_caught / result='pass' cross-field check --

    count += 1
    r = _run_case(
        "coverage: a mutation-testing record with result='pass' and mutants_caught=0 "
        "fires the >=1-observed-red-mutant check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'record    = "evidence/does-not-exist-c.json"',
            'record    = "evidence/does-not-exist-c.json"\n  mutants_caught = 0',
        )),
        expect_pass=False,
        expect_substr="must show >=1 observed-red mutant",
    )
    if r:
        failures.append(r)

    # -- record pointer resolution under --strict --

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM))
        _rep = validate(_p, strict=True)
        if _rep.ok():
            failures.append(
                "record pointer does not exist, --strict: expected FAIL, validation passed"
            )
        elif not any("record pointer does not exist" in e for e in _rep.errors):
            failures.append(
                f"record pointer does not exist, --strict: expected an ERROR (not a "
                f"warning) naming the missing record, got errors: {_rep.errors}, "
                f"warnings: {_rep.warnings}"
            )

    # -- self_verify structural checks --

    count += 1
    r = _run_case(
        "coverage: self_verify.command present but empty on a grade requiring "
        "self_verify fires the command-nonempty check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'command = "cargo kani --harness check_a_no_panic"', 'command = ""'
        )),
        expect_pass=False,
        expect_substr="requires self_verify.command to be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: self_verify given as a non-table value, on a grade that does NOT "
        "require self_verify, fires the \"must be a table\" branch",
        _mini_manifest(_UNGRADED_CLAIM_BAD_SELF_VERIFY_TYPE),
        expect_pass=False,
        expect_substr="[claim.self_verify] must be a table",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: a self_verify field given a non-string value fires the "
        "self_verify.{field} must-be-a-string check",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT.replace(
            'command = "cargo test h"',
            'command = "cargo test h"\n  expect  = "ok"\n  precondition = 42',
        )),
        expect_pass=False,
        expect_substr="self_verify.precondition must be a string",
    )
    if r:
        failures.append(r)

    # -- grade-companion advisory warnings (require an explicitly weighted claim: --
    # -- check_grade_companions only runs for weighted claims, and both grades below --
    # -- are members of UNWEIGHTABLE_GRADES, which _mini_manifest would otherwise --
    # -- auto-mark unweighted) --

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_WEIGHTED_INSPECTION_ARGUED_NO_DOC_REF))
        _rep = validate(_p, strict=False)
        if not any("no deciding machinery" in e for e in _rep.errors):
            failures.append(
                f"weighted grade='inspection-argued': expected the WEIGHT REFUSED "
                f"'no deciding machinery' error too, got errors: {_rep.errors}"
            )
        if not any("SHOULD carry a nonempty claim-level 'doc_ref'" in w for w in _rep.warnings):
            failures.append(
                f"weighted grade='inspection-argued' with no doc_ref: expected the "
                f"doc_ref advisory warning, got: {_rep.warnings}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_WEIGHTED_UNSPECIFIED_NO_CLAUSE_SOURCE_NONE))
        _rep = validate(_p, strict=False)
        if not any("no deciding machinery" in e for e in _rep.errors):
            failures.append(
                f"weighted grade='unspecified': expected the WEIGHT REFUSED "
                f"'no deciding machinery' error too, got errors: {_rep.errors}"
            )
        if not any("SHOULD carry clause_source = 'none'" in w for w in _rep.warnings):
            failures.append(
                f"weighted grade='unspecified' with no clause_source='none': expected "
                f"the clause_source advisory warning, got: {_rep.warnings}"
            )

    # -- weight / clause_source hard errors --

    count += 1
    r = _run_case(
        "coverage: an explicit, out-of-vocabulary claim.weight value fires the "
        "weight-enum check",
        _mini_manifest(_CLAIM_BAD_WEIGHT_VALUE),
        expect_pass=False,
        expect_substr="weight must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: a weighted claim with clause_source='test-name' fires the WEIGHT "
        "REFUSED reserved-clause_source error (distinct from the advisory 'test-name' "
        "warning both grades share)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"',
            'status    = "evidenced"\nweight    = "weighted"\nclause_source = "test-name"',
        )),
        expect_pass=False,
        expect_substr="reserved to mean unweightable by design",
    )
    if r:
        failures.append(r)

    # -- claim / evidence structural checks --

    count += 1
    r = _run_case(
        "coverage: top-level `claim` present but not an array of tables fires the "
        "\"[[claim]] entries must form an array of tables\" check",
        _CLAIM_NOT_ARRAY_MANIFEST,
        expect_pass=False,
        expect_substr="[[claim]] entries must form an array of tables",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: a claim missing a required top-level field ('clause') fires the "
        "claim-field nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace('clause    = "S-1"\n', '')),
        expect_pass=False,
        expect_substr="field 'clause' must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.band given a value outside BANDS fires the band-enum check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'band      = "A1"', 'band      = "A9"'
        )),
        expect_pass=False,
        expect_substr="band must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.status given a value outside STATUSES fires the status-enum "
        "check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "bogus"'
        )),
        expect_pass=False,
        expect_substr="status must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.evidence present but not a list (a bare string) fires the "
        "\"[[claim.evidence]] must be an array of tables\" check",
        _mini_manifest(_CLAIM_EVIDENCE_NOT_ARRAY),
        expect_pass=False,
        expect_substr="[[claim.evidence]] must be an array of tables",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.evidence is a list but one entry is not a table -- fires the "
        "per-entry \"must be a table\" check without crashing check_control_of_claim_mismatch "
        "/ check_band_reachability on the non-dict entry (bug found and fixed 2026-08-25: "
        "both used to assume every evidence item was a dict)",
        _mini_manifest(_CLAIM_EVIDENCE_ENTRY_NOT_TABLE),
        expect_pass=False,
        expect_substr="evidence[0]: must be a table",
    )
    if r:
        failures.append(r)

    # -- [format] / [subject] / [spec] / [coverage] section and field checks --

    count += 1
    r = _run_case(
        "coverage: manifest with no [format] section at all fires the "
        "\"[format] section missing\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            '[format]\nid = "acceptance/0"\nprofile = "acceptance/verification"\n'
            'kind_registry = ["rust-crate", "rust-workspace"]\n\n', ''
        ),
        expect_pass=False,
        expect_substr="[format] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: manifest with no [subject] section at all fires the "
        "\"[subject] section missing\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            '[subject]\nname   = "selftest-lib"\nkind   = "rust-crate"\n'
            'commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"\ndirty  = false\n\n',
            '',
        ),
        expect_pass=False,
        expect_substr="[subject] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [subject].name empty fires the subject-name nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'name   = "selftest-lib"', 'name   = ""'
        ),
        expect_pass=False,
        expect_substr="[subject].name must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [subject].kind given a value outside SUBJECT_KINDS fires the "
        "subject-kind enum check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'kind   = "rust-crate"', 'kind   = "bogus-kind"'
        ),
        expect_pass=False,
        expect_substr="[subject].kind must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [subject].dirty given a non-bool value fires the subject-dirty "
        "type check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'dirty  = false', 'dirty  = "false"'
        ),
        expect_pass=False,
        expect_substr="[subject].dirty must be a bool",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: manifest with no [spec] section at all fires the "
        "\"[spec] section missing\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            '[spec]\npath    = "SPEC.md"\nversion = "v1"\n'
            'axis    = "public API surface of selftest-lib"\n\n',
            '',
        ),
        expect_pass=False,
        expect_substr="[spec] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [spec].path empty fires the spec-path nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'path    = "SPEC.md"', 'path    = ""'
        ),
        expect_pass=False,
        expect_substr="[spec].path must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [spec].version empty fires the spec-version nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'version = "v1"', 'version = ""'
        ),
        expect_pass=False,
        expect_substr="[spec].version must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: manifest with no [coverage] section at all fires the "
        "\"[coverage] section missing\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            '[coverage]\nclauses_total = 1\nclaims_total  = 1\n\n', ''
        ),
        expect_pass=False,
        expect_substr="[coverage] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [coverage].clauses_total < 1 fires the clauses_total range check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'clauses_total = 1', 'clauses_total = 0'
        ),
        expect_pass=False,
        expect_substr="[coverage].clauses_total must be an integer >= 1",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [coverage].claims_total given a non-integer value fires the "
        "claims_total type check (distinct from a valid-but-mismatched integer)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'claims_total  = 1', 'claims_total  = "one"'
        ),
        expect_pass=False,
        expect_substr="[coverage].claims_total must be an integer,",
    )
    if r:
        failures.append(r)

    # -- validate()'s own file-level error paths --

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "does-not-exist.toml"
        _rep = validate(_p, strict=False)
        if _rep.ok():
            failures.append("validate() on a nonexistent path: expected FAIL, passed")
        elif not any("cannot read file" in e for e in _rep.errors):
            failures.append(
                f"validate() on a nonexistent path: expected 'cannot read file', got: "
                f"{_rep.errors}"
            )

    count += 1
    r = _run_case(
        "coverage: a file that is not valid TOML fires the TOML-parse-error check",
        "this is not [valid = toml at all {{{",
        expect_pass=False,
        expect_substr="TOML parse error",
    )
    if r:
        failures.append(r)

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_bytes(b"\xff\xfe\x00not valid utf-8")
        _rep = validate(_p, strict=False)
        if _rep.ok():
            failures.append("validate() on non-UTF-8 bytes: expected FAIL, passed")
        elif not any("not valid UTF-8" in e for e in _rep.errors):
            failures.append(
                f"validate() on non-UTF-8 bytes: expected 'not valid UTF-8', got: "
                f"{_rep.errors}"
            )

    bad_cases = [
        (
            "bad format id",
            GOOD_FIXTURE.replace('id = "acceptance/0"', 'id = "acceptance/1"'),
            "acceptance/0",
        ),
        (
            "bad commit",
            GOOD_FIXTURE.replace(
                'commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"', 'commit = "deadbeef"'
            ),
            "commit",
        ),
        (
            "claims_total mismatch",
            GOOD_FIXTURE.replace("claims_total  = 7", "claims_total  = 8"),
            "claims_total",
        ),
        (
            "duplicate claim id",
            GOOD_FIXTURE.replace('id        = "G-002"', 'id        = "G-001"'),
            "duplicate",
        ),
        (
            "evidenced claim with no evidence",
            GOOD_FIXTURE.replace(
                """  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a_no_panic"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-a.json"
""",
                "",
            ),
            "requires at least one evidence entry",
        ),
        (
            "gap claim with evidence",
            GOOD_FIXTURE.replace(
                """status    = "gap"
""",
                """status    = "gap"

  [[claim.evidence]]
  kind     = "human-review"
  family   = "judgment"
  ref      = "f-review"
  result   = "pass"
  tool     = "manual"
  reviewer = "ivo"
  record   = "evidence/does-not-exist-f.txt"
""",
            ),
            "must have NO evidence entries",
        ),
        (
            "parked without parked_reason",
            GOOD_FIXTURE.replace(
                'parked_reason = "kani unsupported_construct — tool change needed"\n', ""
            ),
            "parked_reason",
        ),
        (
            "unknown evidence kind",
            GOOD_FIXTURE.replace('kind      = "kani-harness"\n  family    = "bmc"\n  ref       = "check_a_no_panic"',
                                  'kind      = "made-up-kind"\n  family    = "bmc"\n  ref       = "check_a_no_panic"'),
            "unknown evidence kind",
        ),
        (
            "kind/family mismatch",
            GOOD_FIXTURE.replace(
                'kind      = "kani-harness"\n  family    = "bmc"\n  ref       = "check_a_no_panic"',
                'kind      = "kani-harness"\n  family    = "dynamic"\n  ref       = "check_a_no_panic"',
            ),
            "kind/family mismatch",
        ),
        (
            "missing per-kind required field (kani-harness without bounds)",
            GOOD_FIXTURE.replace('  bounds    = "unwind=8"\n', ""),
            "missing required field 'bounds'",
        ),
        (
            "lr without calibration",
            GOOD_FIXTURE.replace(
                '  record    = "evidence/does-not-exist-a.json"\n',
                '  record    = "evidence/does-not-exist-a.json"\n  lr        = 3.5\n',
            ),
            "calibration",
        ),
        (
            "judgment-only evidence with band A2",
            GOOD_FIXTURE.replace(
                'id        = "G-005"\nclause    = "S-5"\nitem      = "src/lib.rs::e"\nstatement = "e was reviewed"\nband      = "A0"',
                'id        = "G-005"\nclause    = "S-5"\nitem      = "src/lib.rs::e"\nstatement = "e was reviewed"\nband      = "A2"',
            ),
            "band must be A0",
        ),
        (
            "A4 claim with only bmc evidence",
            GOOD_FIXTURE.replace(
                """  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff"
  result    = "pass"
  tool      = "lean4@4.x-pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d.lean"
""",
                """  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_d_bmc"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-d.json"
""",
            ),
            "not reachable by any passing evidence",
        ),
        (
            "A3 claim with no control",
            GOOD_FIXTURE.replace(
                """
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
                "",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "control whose of_claim names a different claim can't lift the claim it's attached to",
            GOOD_FIXTURE.replace(
                '    of_claim    = "G-003"',
                '    of_claim    = "G-002"',
            ),
            "does not name this claim",
        ),
        (
            "control with observed != expectation doesn't satisfy the gate (bmc-family)",
            GOOD_FIXTURE.replace(
                """    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
                """    kind        = "mutation"
    expectation = "red"
    observed    = "green"
    of_claim    = "G-003"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "A2 claim with only a planted-twin control MUST FAIL (per-band whitelist, "
            "assurance-bands.md rule 6: A2 = mutation|ablation only, tightened 2026-08-22)",
            GOOD_FIXTURE.replace(
                """    kind        = "ablation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-002"
""",
                """    kind        = "planted-twin"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-002"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "A3 claim whose only control is a planted-twin MUST FAIL (planted-twin never "
            "satisfies the band-lift gate, at any band)",
            GOOD_FIXTURE.replace(
                """    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
                """    kind        = "planted-twin"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "A4 claim whose only control is a planted-twin MUST FAIL (planted-twin never "
            "satisfies the band-lift gate, at any band)",
            GOOD_FIXTURE.replace(
                """    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-004"
""",
                """    kind        = "planted-twin"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-004"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "control.of_claim naming a claim id that does not exist anywhere in the manifest "
            "(phantom claim) is an error",
            GOOD_FIXTURE.replace(
                '    of_claim    = "G-003"',
                '    of_claim    = "A-999"',
            ),
            "does not match any claim id in this manifest",
        ),
    ]

    for name, text, substr in bad_cases:
        count += 1
        r = _run_case(name, text, expect_pass=False, expect_substr=substr)
        if r:
            failures.append(r)

    # ------------------------------------------------------------------
    # 0.1-DRAFT W2.3 / W2.5 (P1, P2 -- ADOPTED 2026-08-25). Asserted under --strict-weight so
    # they are hard errors in the fixture; all three fail on the pre-adoption validator, which
    # granted weight to every one of these claims.
    # ------------------------------------------------------------------
    count += 1
    r = _run_case(
        "P1: weighted claim with NO clause_source is refused weight (--strict-weight)",
        _mini_manifest(_DER_SHAPED_A3_ASSERTION_CLAIM.replace(
            'clause_source = "external-standard"\n', "")),
        expect_pass=False,
        expect_substr="clause_source not recorded",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P2: weighted claim with no watched-fail witness is refused weight (--strict-weight)",
        # Strip ONLY the control block. The old pattern ran to end-of-string and took the
        # [claim.self_verify] table with it, so the claim ALSO broke a pre-adoption rule --
        # which, under the §8.1 membership invariant (S4), is now an outright refusal rather
        # than a pending one. The fixture has to isolate the P2 defect to assert P2.
        # ...and the band drops to A0 with the control, because A3 is control-gated: leaving it
        # at A3 substitutes an assurance-bands error for the P2 refusal being asserted.
        _mini_manifest(re.sub(
            r"(?m)^    \[claim\.evidence\.control\]\n(?:    \w.*\n)*", "",
            _DER_SHAPED_A3_ASSERTION_CLAIM).replace('band      = "A3"', 'band      = "A0"')),
        expect_pass=False,
        expect_substr="no watched-fail witness",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P1+P2 both satisfied: the golden A3 claim keeps its weight under --strict-weight",
        _mini_manifest(_DER_SHAPED_A3_ASSERTION_CLAIM),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # ----------------------------------------------------------------------
    # Round 2 (2026-08-25). Every fixture below passed clean, WEIGHTED, on the code of
    # the same morning; each was watched red against it before its fix landed. They are the
    # TOML half of a parity gap: the Markdown checker refused all of these and the TOML
    # validator did not, which made the manifest representation the weaker of the two.
    # ----------------------------------------------------------------------

    # Finding 2: `watched_fail` was ANY nonempty string, so a phrase satisfied a weighted-tier
    # obligation -- the one thing §4.1 says may never happen.
    _WF_CLAIM = """
[[claim]]
id        = "W-1"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a rejects non-minimal encodings"
band      = "A0"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"
weight    = "weighted"
clause_source = "spec-document"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "unwind=8"
  semantics = ""
  record    = "acceptance.toml"

  [claim.self_verify]
  command = "cargo kani --harness check_a"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""
    _WF_GOOD_BLOCK = """
    [claim.self_verify.watched_fail]
    of_command = "cargo kani --harness check_a"
    perturbed  = "deleted the minimality check in decode"
    observed   = "check_a FAILED on the padding assertion"
    date       = "2026-08-25"
"""
    count += 1
    r = _run_case(
        "R2_2: watched_fail as a free-text string is refused (a phrase is not a witness)",
        _mini_manifest(_WF_CLAIM + '  watched_fail = "x"\n'),
        expect_pass=False,
        expect_substr="must be a [claim.self_verify.watched_fail] TABLE",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_2: a fully-formed watched_fail table satisfies W2.5 and keeps the claim weighted",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_2: watched_fail.perturbed must be a statement, not a token",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'perturbed  = "deleted the minimality check in decode"', 'perturbed  = "x"')),
        expect_pass=False,
        expect_substr="a single token is not a statement",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_2: watched_fail.of_command must name THIS claim's own command",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'of_command = "cargo kani --harness check_a"',
            'of_command = "cargo kani --harness check_b"')),
        expect_pass=False,
        expect_substr="does not equal this claim's own self_verify.command",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_2: watched_fail.date must be an ISO date -- 'when' is part of the witness",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'date       = "2026-08-25"', 'date       = "recently"')),
        expect_pass=False,
        expect_substr="must be an ISO date",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_2: a watched_fail table missing a required field is refused",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            '    date       = "2026-08-25"\n', "")),
        expect_pass=False,
        expect_substr="requires 'date'",
    )
    if r:
        failures.append(r)

    # A MALFORMED witness must not satisfy the requirement it fails to meet. Asserted directly
    # on the predicate, because at the file level such a claim is refused outright (§8.1
    # membership: it breaks a rule, so it is not on the backlog) and the pending reason is not
    # emitted -- which is correct, and is why the message-matching harness cannot state this.
    count += 1
    _sv_bad = {"command": "cargo kani --harness check_a",
               "watched_fail": {"of_command": "cargo kani --harness check_a",
                                "perturbed": "deleted the minimality check",
                                "observed": "check_a FAILED", "date": "recently"}}
    _sv_good = {"command": "cargo kani --harness check_a",
                "watched_fail": {"of_command": "cargo kani --harness check_a",
                                 "perturbed": "deleted the minimality check",
                                 "observed": "check_a FAILED", "date": "2026-08-25"}}
    if _watched_fail_block_is_valid(_sv_bad) or not _watched_fail_block_is_valid(_sv_good):
        failures.append(
            "R2_2: a malformed watched_fail table must not count as a witness (and a "
            "well-formed one must)"
        )
        print("SELFTEST FAIL: R2_2-malformed-witness-is-not-a-witness", file=sys.stderr)

    # Finding 2 (parity): §4.1 witness 3 is scoped to `not-covered`. A positive_control on a
    # `contract` row shows the command CAN match some input; it says nothing about whether the
    # proof would notice a broken implementation.
    count += 1
    r = _run_case(
        "R2_2: positive_control does not witness a non-not-covered grade (§4.1 witness 3)",
        _mini_manifest(_WF_CLAIM.replace(
            'expect  = "VERIFICATION:- SUCCESSFUL"',
            'expect  = "VERIFICATION:- SUCCESSFUL"\n'
            '  positive_control = "the same harness against a known-bad fixture"')),
        expect_pass=False,
        expect_substr="no watched-fail witness",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # Findings 3 and 5: §7.1 status x grade x weight coherence, absent from TOML entirely.
    count += 1
    r = _run_case(
        "R2_5: status = 'gap' + grade = 'contract' + weighted is INCOHERENT",
        _mini_manifest(_WF_CLAIM.replace('grade     = "probe"', 'grade     = "contract"')
                       .replace('status    = "evidenced"', 'status    = "gap"')
                       + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="cannot be a gap and a proof at the same time",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_3: status = 'partial' + grade = 'not-covered' + weighted is INCOHERENT",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'status    = "gap"', 'status    = "partial"'
        ).replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "the same grep against src/b.rs hits"',
        )),
        expect_pass=False,
        expect_substr="does not cohere with grade 'not-covered'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_3: an UNWEIGHTED incoherent pair warns and does not error (P5 stays DEFERRED)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'grade     = "not-covered"', 'grade     = "probe"'
        ).replace(
            'status    = "gap"',
            'status    = "parked"\nparked_reason = "tool change needed"\n'
            'weight    = "unweighted"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_3: out-of-scope scope_ref must be a locator, not free prose",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM.replace(
            'scope_ref = "docs/scope.md#a"', 'scope_ref = "nonsense"')),
        expect_pass=False,
        expect_substr="scope_ref must be a LOCATOR",
    )
    if r:
        failures.append(r)

    # Finding 4: the §8.1 membership invariant. `FAIL 2 errors` alongside `pending: 1` said the
    # row was on a backlog meaning "fine until the rules changed", which it was not.
    count += 1
    _adv7 = _WF_CLAIM.replace('grade     = "probe"', 'grade     = "contract"') \
                     .replace('bounds    = "bounded: unwind=8"\n', "") \
                     .replace('clause_source = "spec-document"\n', "") \
                     .replace('  [claim.self_verify]\n'
                              '  command = "cargo kani --harness check_a"\n'
                              '  expect  = "VERIFICATION:- SUCCESSFUL"\n', "")
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "adv7.toml"
        _p.write_text(_mini_manifest(_adv7), encoding="utf-8")
        _rep = validate(_p, strict=False)
        n_pending_adv7 = getattr(_rep, "n_pending", 0)
        if _rep.ok() or n_pending_adv7 != 0:
            failures.append(
                f"R2_4: a claim breaking pre-adoption rules must not be weight-pending — "
                f"got ok={_rep.ok()} pending={n_pending_adv7}"
            )
            print("SELFTEST FAIL: R2_4-broken-row-is-not-weight-pending", file=sys.stderr)
        # Positive control: fixing the pre-adoption defects DOES put it on the backlog.
        _p2 = Path(_td) / "adv7fixed.toml"
        _p2.write_text(_mini_manifest(_WF_CLAIM), encoding="utf-8")
        _rep2 = validate(_p2, strict=False)
        if not _rep2.ok() or getattr(_rep2, "n_pending", 0) != 1:
            failures.append(
                f"R2_4 positive control: a row lacking only P1/P2 machinery must be pending — "
                f"got ok={_rep2.ok()} pending={getattr(_rep2, 'n_pending', 0)}"
            )
            print("SELFTEST FAIL: R2_4-positive-control", file=sys.stderr)

    # Finding 6: P3 and P4 mechanically adopted in TOML.
    def _predicate_claim(extra: str) -> str:
        # Claim-level fields must sit ABOVE the [claim.self_verify] table or TOML nests them
        # inside it.
        return _WF_CLAIM.replace(
            'clause_source = "spec-document"',
            'clause_source = "spec-document"\nitem_kind = "predicate"\n' + extra,
        ) + _WF_GOOD_BLOCK

    count += 1
    r = _run_case(
        "R2_6: a weighted predicate row with no fraction is refused weight (§7.2)",
        _mini_manifest(_predicate_claim("")),
        expect_pass=False,
        expect_substr="'over' (what the predicate ranges over) is missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_6: a predicate row with over + covered passes (§7.2)",
        _mini_manifest(_predicate_claim(
            'over      = "the 33 production harnesses in module X"\ncovered   = "4/33"')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_6: a predicate fraction whose numerator exceeds its denominator is refused",
        _mini_manifest(_predicate_claim(
            'over      = "the 33 production harnesses"\ncovered   = "40/33"')),
        expect_pass=False,
        expect_substr="numerator exceeds its denominator",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_6: status = 'blocked' is a valid status (P4 adopted), and requires blocked_by",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'status    = "gap"', 'status    = "blocked"'
        ).replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "the same grep against src/b.rs hits"',
        )),
        expect_pass=False,
        expect_substr="requires a nonempty 'blocked_by'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_6: status = 'blocked' with blocked_by passes (P4 adopted)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'status    = "gap"',
            'status    = "blocked"\nblocked_by = "kani 0.67 cannot quantify over a generic T"'
        ).replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "the same grep against src/b.rs hits"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # N1 (cold reader, 2026-08-26) — his exact fixture: a unit test carrying a `contract` grade.
    # §0.5 has said "a test is never contract" since it was written; nothing enforced it.
    _N1_CLAIM = """
[[claim]]
id        = "N1-1"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a decides the rule"
band      = "A1"
grade     = "contract"
bounds    = "unbounded: all inputs"
status    = "evidenced"
weight    = "weighted"
clause_source = "spec-document"

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "tests::a_decides"
  result    = "pass"
  tool      = "cargo@1.97"
  cases     = 2
  record    = "acceptance.toml"

  [claim.self_verify]
  command = "cargo test a_decides"
  expect  = "test result: ok"

    [claim.self_verify.watched_fail]
    of_command = "cargo test a_decides"
    perturbed  = "deleted the minimality check in decode"
    observed   = "a_decides failed on the padding assertion"
    date       = "2026-08-26"
"""
    count += 1
    r = _run_case(
        "N1: a weighted `contract` backed only by dynamic-family evidence is refused (§0.5)",
        _mini_manifest(_N1_CLAIM),
        expect_pass=False,
        expect_substr="requires a SYMBOLIC domain",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "N1 positive control: the same claim graded `test-only` is fine",
        _mini_manifest(_N1_CLAIM.replace('grade     = "contract"', 'grade     = "test-only"')
                                .replace('bounds    = "unbounded: all inputs"\n', "")
                                .replace('band      = "A1"', 'band      = "A0"')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "N1 positive control: `contract` on bmc-family evidence keeps its weight",
        _mini_manifest(_N1_CLAIM.replace('kind      = "unit-test"', 'kind      = "kani-harness"')
                                .replace('family    = "dynamic"', 'family    = "bmc"')
                                .replace('  cases     = 2\n',
                                         '  bounds    = "unwind=8"\n  semantics = ""\n')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R6_1: an annotation with a colon separator is still metadata",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'observed   = "check_a FAILED on the padding assertion"',
            'observed   = "bug, observed: 2026-08-25"')),
        expect_pass=False,
        expect_substr="a single token is not a statement",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R6_1: a date in the MIDDLE of a description is not metadata and must not be stripped",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'observed   = "check_a FAILED on the padding assertion"',
            'observed   = "failure on 2026-08-25 after harness mutation"')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R5_1: `bounded` is a TOKEN, not a prefix — `boundedness:...` is refused",
        _mini_manifest(_WF_CLAIM.replace(
            'bounds    = "bounded: unwind=8"', 'bounds    = "boundedness:unwind=8"')
            + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="starting with 'bounded' or 'unbounded'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R5_2: a date annotation inside `observed` does not satisfy the phrase floor",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'observed   = "check_a FAILED on the padding assertion"',
            'observed   = "y, observed 2026-08-25"')),
        expect_pass=False,
        expect_substr="a single token is not a statement",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R3-3c: a bounds token with no stated limit is refused (§5 requires the limit text)",
        _mini_manifest(_WF_CLAIM.replace(
            'bounds    = "bounded: unwind=8"', 'bounds    = "bounded"') + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="nothing about WHAT THE CHECK RANGED OVER",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R3-3c positive control: a single-token limit like `unwind=8` is a real limit and passes",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_11: positive_control must be a statement, not a token (§4 is a weighted-tier "
        "obligation, so a phrase match earning it is the one thing §4.1 forbids)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'expect  = "no output"', 'expect  = "no output"\n  positive_control = "x"')),
        expect_pass=False,
        expect_substr="a single token is not a control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2_6: status = 'blocked' forbids evidence entries, exactly like gap/parked",
        _mini_manifest(_WF_CLAIM.replace('grade     = "probe"', 'grade     = "not-covered"')
                       .replace('bounds    = "bounded: unwind=8"\n', "")
                       .replace('status    = "evidenced"',
                                'status    = "blocked"\nblocked_by = "the tool cannot reach it"')
                       + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="must have NO evidence entries",
    )
    if r:
        failures.append(r)

    # ------------------------------------------------------------------
    # F1-F4 (2026-09-17, linux findings fold — estate core-alignment plan §2h, RFC-0015 trial).
    # Each: one RED fixture (the old, closed/overloaded/silent behavior), one GREEN fixture
    # (the class-level fix). See spec/format.md "§0 Class -> Instance -> Run" and design rules
    # 4/7.
    # ------------------------------------------------------------------

    # F1 RED: an unknown, undeclared [subject].kind is still an error — the registry is open,
    # not absent.
    count += 1
    r = _run_case(
        "F1 RED: [subject].kind outside the base registry, with no [format].kind_registry "
        "declaring it, still FAILS (the registry is OPEN, not ABSENT)",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            'kind   = "rust-crate"', 'kind   = "export-json-rfc-0015"'
        ),
        expect_pass=False,
        expect_substr="[subject].kind must be one of",
    )
    if r:
        failures.append(r)

    # F1 GREEN: the new base token for a proposed feature of an existing tool/artifact.
    count += 1
    r = _run_case(
        "F1 GREEN: [subject].kind = 'prospective-feature' (the RFC-0015/export-json shape — "
        "a proposed feature OF an existing tool, not itself built yet) PASSES as a base token",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            'kind   = "rust-crate"', 'kind   = "prospective-feature"'
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # Base-token GREEN: each added base kind is recognized without a declared extension.
    for kind in ("ml-model", "dataset", "spec", "design", "agent-output"):
        count += 1
        r = _run_case(
            f"Base-token GREEN: [subject].kind = '{kind}' PASSES as a base token",
            _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
                'kind   = "rust-crate"', f'kind   = "{kind}"'
            ),
            expect_pass=True,
        )
        if r:
            failures.append(r)

    # F1 GREEN (extension mechanism): a profile-declared kind, via [format].kind_registry.
    # `_mini_manifest` already declares `kind_registry = ["rust-crate", "rust-workspace"]`
    # (revision: those two tokens left the base registry, B14) — this case REPLACES that
    # declaration with one naming only the kind under test, so it still proves the extension
    # mechanism admits a kind the base registry does not.
    count += 1
    r = _run_case(
        "F1 GREEN: a kind declared in [format].kind_registry PASSES (the declared extension "
        "mechanism, distinct from the base registry)",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            'kind   = "rust-crate"', 'kind   = "fixture-corpus"'
        ).replace(
            'kind_registry = ["rust-crate", "rust-workspace"]', 'kind_registry = ["fixture-corpus"]'
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # F2 RED: [spec].provenance = "external" with a bare, uncheckable version tag.
    count += 1
    r = _run_case(
        "F2 RED: [spec].provenance = 'external' with a bare version tag FAILS — a tag names "
        "nothing checkable for a governing document outside the subject's own tree",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            'version = "v1"', 'version = "v1"\nprovenance = "external"'
        ),
        expect_pass=False,
        expect_substr="normative-reference:sha-512:",
    )
    if r:
        failures.append(r)

    # F2 GREEN: a real normative-reference digest.
    count += 1
    r = _run_case(
        "F2 GREEN: [spec].provenance = 'external' with a normative-reference digest PASSES "
        "(the class-level hash domain for a spec document the subject is written against but "
        "does not itself contain)",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            'version = "v1"',
            'version = "' + core.hashdomains.digest('normative-reference:', b'Fixture governing document.\n') + '"\n'
            'provenance = "external"',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # F2 positive control: the default ("in-tree") stays free-form — no regression.
    count += 1
    r = _run_case(
        "F2 positive control: [spec].provenance omitted (defaults to 'in-tree') keeps the "
        "pre-existing free-form 'version' behavior",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # F3 RED: mode = "prospective" with no read_at_commit conflates the two meanings of commit.
    count += 1
    r = _run_case(
        "F3 RED: [subject].mode = 'prospective' with no read_at_commit FAILS — 'commit' alone "
        "cannot say both 'what is certified' (nothing) and 'what the claims were read against'",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            'dirty  = false', 'dirty  = false\nmode   = "prospective"'
        ),
        expect_pass=False,
        expect_substr="read_at_commit is REQUIRED",
    )
    if r:
        failures.append(r)

    # F3 GREEN: the distinct field makes the two meanings machine-visible.
    count += 1
    r = _run_case(
        "F3 GREEN: [subject].mode = 'prospective' with read_at_commit PASSES — the two "
        "meanings are now two fields, not one prose-only overload",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            'dirty  = false',
            'dirty  = false\nmode   = "prospective"\n'
            'read_at_commit = "1111111111111111111111111111111111111111"',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # F3 positive control: mode omitted (retrospective, the pre-existing default) needs no
    # read_at_commit — full backward compatibility with every manifest written before this field.
    count += 1
    r = _run_case(
        "F3 positive control: [subject].mode omitted (defaults to 'retrospective') validates "
        "exactly as before this fold — no migration required for existing manifests",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # F4 RED: a wholly-prospective manifest (every claim gap/parked/blocked, nothing checked)
    # must not be reported as plain PASS — proof-able-to-fail: _verdict_label with the
    # is_prospective computation removed (simulated here by checking the flag directly) would
    # print "PASS" for this exact manifest, which is the linux finding.
    count += 1
    with tempfile.TemporaryDirectory() as _td_f4:
        _p_f4 = Path(_td_f4) / "f4-red.toml"
        _p_f4.write_text(_mini_manifest(_OUT_OF_SCOPE_CLAIM), encoding="utf-8")
        _rep_f4 = validate(_p_f4, strict=False)
        if not (_rep_f4.ok() and getattr(_rep_f4, "is_prospective", False) is True):
            failures.append(
                "F4 RED: a wholly-gap manifest must validate with is_prospective=True "
                f"— got ok={_rep_f4.ok()} is_prospective={getattr(_rep_f4, 'is_prospective', None)}"
            )
            print("SELFTEST FAIL: F4-red-wholly-prospective-flag", file=sys.stderr)
        elif _verdict_label(_rep_f4) != "PASS-PROSPECTIVE":
            failures.append(
                f"F4 RED: a wholly-prospective manifest's verdict must be PASS-PROSPECTIVE, "
                f"not plain PASS — the exact bug 100%-warnings PASS reported as (linux F4); "
                f"got {_verdict_label(_rep_f4)!r}"
            )
            print("SELFTEST FAIL: F4-red-verdict-label", file=sys.stderr)

    # F4 GREEN: one evidenced claim alongside a gap keeps the ordinary PASS verdict — this rule
    # changes a label, never a pass/fail decision (design rule 7).
    count += 1
    with tempfile.TemporaryDirectory() as _td_f4g:
        _p_f4g = Path(_td_f4g) / "f4-green.toml"
        _f4g_manifest = _mini_manifest(_OUT_OF_SCOPE_CLAIM).replace(
            "clauses_total = 1", "clauses_total = 2"
        ).replace("claims_total  = 1", "claims_total  = 2") + _A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'id        = "C-001"', 'id        = "C-002"'
        ).replace('clause    = "S-1"', 'clause    = "S-2"')
        _p_f4g.write_text(_f4g_manifest, encoding="utf-8")
        _rep_f4g = validate(_p_f4g, strict=False)
        if not _rep_f4g.ok() or getattr(_rep_f4g, "is_prospective", False) is not False:
            failures.append(
                "F4 GREEN: a manifest with >=1 evidenced claim must be ok() and NOT "
                f"is_prospective — got ok={_rep_f4g.ok()} "
                f"is_prospective={getattr(_rep_f4g, 'is_prospective', None)}"
            )
            print("SELFTEST FAIL: F4-green-not-prospective", file=sys.stderr)
        elif _verdict_label(_rep_f4g) != "PASS":
            failures.append(
                f"F4 GREEN: a manifest with real evidence must keep the ordinary PASS "
                f"verdict, got {_verdict_label(_rep_f4g)!r}"
            )
            print("SELFTEST FAIL: F4-green-verdict-label", file=sys.stderr)

    if failures:
        for f in failures:
            print(f"SELFTEST FAIL: {f}", file=sys.stderr)
        print(f"SELFTEST FAILED: {len(failures)}/{count} cases", file=sys.stderr)
        return 1

    print(f"SELFTEST PASS: {count} fixtures")
    return 0


