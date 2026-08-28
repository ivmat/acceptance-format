# Witness envelope + coverage ledger — `rs-verified-der` @ `130de97`

**Role: legacy acceptance carrier for the DER subject.** This Markdown ledger predates the TOML
manifest (`spec/format.md`) and is checked by `tools/check_ledger.py`, not
`tools/check_acceptance.py`. It stays as the format's most mature worked sample and is retained
until this subject's acceptance is expressed as a manifest under the newer representation; nothing
here is deprecated in the sense of being wrong, only in the sense of predating the manifest form.

**What this is.** One table saying, per *encoding rule*, whether this crate decides that rule, how
strongly, and the exact command you run to check the answer yourself. It is the consumer-side view:
you should be able to answer "is the thing I care about actually verified here?" without reading a
proof, and without reading the crate's 96 KB `PROOF_MANIFEST.md`.

> ### Re-certified at `130de97` — 2026-08-25
>
> This envelope was first built against `2b9f3d55`. It has since been **fully re-certified** against
> `130de97`, and the counts, the gate receipt and every recipe below now speak for that commit.
> What the re-certification actually did — stated as a procedure, because "re-certified" is a word
> anyone can type — is in §8.1. It produced one new finding (§7, **E-3**: three recipes asserted a
> grep-zero that was never zero, at `2b9f3d55` *or* here) and one correction to a derived count.

**What it is not.** Not a badge, not a score, and not a replacement for the crate's own documents —
every row cites them. Where this envelope and the crate's generated documents disagree, **the crate's
generated documents are authoritative** and this envelope has a bug. One such disagreement is
recorded below (§7, finding E-1) and it is a defect in the crate's prose, not in this table.

---

## 1. Subject identity — what exactly is being certified

| | |
|---|---|
| subject | `rs-verified-der` (crate `der-verified` 0.1.1), sources at `der-verified/src/` |
| commit | `130de97` (public, `github.com/ivmat/rs-verified-der`) |
| tree state | clean at the certified commit; the run log records `git status --porcelain` sampled clean **at launch and at completion**, not assumed |
| spec axis | **X.690 (2021) DER encoding rules**, per type + framing; **RFC 5280** profile surface. See §3. |
| gate receipt | `./check.sh` exit 0 at `bffab69`, `== check.sh: PASS (L3 kani floor: GREEN; L4 lean lid: PASS) ==`, run with `DER_REQUIRE_LEAN=1` |
| proof floor (L3) | **203 of 203 Kani harnesses SUCCESSFUL, 0 FAILED** — `evidence/check-bffab69.log:1149` |
| unbounded lids (L4) | 6 Lean lids, `lean lid: PASS (sorry-free)`, re-extracted from the shipped `.rs`; `lid-source-state.txt unchanged (hashes identical)` |
| tests | 485 unit tests + 34 doc-tests (no integration-test directory exists) |
| unsafe | 0 `unsafe` blocks; crate is `#![forbid(unsafe_code)]` |
| toolchain | Kani `0.67.0`, CBMC `6.8.0` (kani-bundled, read from the run's own output), CaDiCaL 2.0.0 (948 occurrences in the raw log, never another value), rustc `1.97.0`, Lean 4 `v4.30.0-rc2` |
| cost | 1h11m07s wall, peak 20.43 GiB. **That peak is systemd cgroup-wide `MemoryPeak` sampled every 20 s** — a different measure from the previous run's 20.26 GiB (`/usr/bin/time -v` largest-single-process RSS). Not one series; do not read a trend into it. |
| freshness | the run at `bffab69` speaks for HEAD iff `git diff bffab69..HEAD -- der-verified/src lean` is empty. **Run that command; do not trust this sentence.** (At `130de97` it is empty: the two commits between them touch only `CHANGELOG.md`, `PROOF_MANIFEST.md` and the evidence logs.) |

**Two toolchain caveats stated up front,** because they bound everything below:

- Kani is pinned **by version string, not by commit**. Two Kani builds reporting `0.67.0` can have
  different capabilities. Every row's proof evidence inherits that weakness.
- The certified run was executed on the maintainer's own machine, not a clean-room VM — the run log
  says so in its own header. Two earlier runs *were* clean-room VMs but had to skip the Lean stage.

---

## 2. What the strength labels mean

Read the label before reading the status. An `evidenced` row at `PROBE` strength is a much weaker
statement than an `evidenced` row at `CONTRACT`.

> ### Weighted rows and admitted rows
>
> **Every claim about this crate is admitted to this table — including the ones no machine decides.**
> That is deliberate: a claim left out of the ledger is a claim the reader has to infer from silence,
> which is the failure this document exists to prevent. But admission is not endorsement. Rows sit in
> two tiers, and the tier is marked explicitly on every row.
>
> **Weight is not a rank of the grade, and this block used to say it was.** Until 2026-08-26 the two
> bullets here read *"Weighted — `CONTRACT+L4`, `CONTRACT`, `mechanical`"* against *"Admitted —
> `PROBE`, `test-only`, `inspection-argued`, `not-covered`"*, i.e. weight was presented as the top of
> the strength ladder. `spec/core.md` §2 says the opposite, in one line:
>
> > **band = how good is the evidence? · grade = does the evidence decide the item? · weight = is
> > the format standing behind this row at all?**
>
> Six grades are **weight-eligible** — `contract`, `probe`, `test-only`, `mechanical`,
> `not-covered` and `out-of-scope` — and three are not: `inspection-argued`, `unspecified` and
> `ungraded`, because no deciding machinery exists for them by definition. So a `PROBE` row and a
> `not-covered` row can both be weighted, and a `CONTRACT` row can fail to be. What a weighted row
> promises is exactly this: **the grade is the right grade, the recipe decides the item at that
> grade, and the recipe has been watched to report the claim false** (§4.1). What it never promises
> is that the grade is a strong one. *The state this makes writable — and the reason the old legend
> was worse than untidy — is `probe` + weighted: an honest, well-controlled proof that genuinely
> does not decide the item. The old legend had no cell for it.*
>
> The split **cannot be crossed by writing better prose.** A row becomes weighted when a deciding,
> watched-to-fail recipe is attached to it, and not before.
>
> **That more than half the rows are admitted is the ledger working, not failing.** The crate's own
> headline is "203 of 203 harnesses SUCCESSFUL", which is true and which invites the reading that 203
> of 203 *rules* are decided. Compare §5.2's `DER-C-INT-2` (weighted: a Lean lid over all content
> lengths) with §5.3's `DER-X-BOUND` (admitted: a compositional argument nobody has machine-checked). Both sit
> under the same green check. The table's job is to stop them reading alike.

| label | means |
|---|---|
| **CONTRACT** | **the row's stated item** is asserted as a property of the **shipped** function over a **symbolic** (bounded) input domain. Where the item is a semantic equivalence, the oracle must be **independent of the state under test**; where the item is a direct safety property (e.g. panic-freedom), the assertion decides it directly and no separate oracle applies. Bounded: it holds up to the declared buffer/unwind, and says nothing beyond it. Where a row's Kani half also has an unbounded Lean lid proving the same rule, that fact is disclosed in the row's own prose rather than folded into a separate grade token — the grade names what the row's WITNESSED recipe decides. |
| **PROBE** | bounded, monomorphic, or fixture-shaped evidence — **or** evidence offered for an item it does not decide, the commonest case being a panic-freedom harness cited for a *conformance* item. A probe never counts as the row's item being verified. |
| **test-only** | `#[test]` / doc-test at named concrete inputs. Witnesses points, not sets. |
| **inspection-argued** | a documented human argument with no mechanical oracle. Weakest admissible evidence. |
| **not-covered** | no layer of this crate decides this rule, though it is in scope. The row exists so you do not have to infer it from silence. |
| **out-of-scope** | the rule is deliberately outside what this crate sets out to do, and that boundary is declared in the crate's own documents. Not a gap; a fence. |

### Weight — what the FORMAT promises about a row

Every row sits in one of two tiers (`spec/core.md` §0):

- **WEIGHTED** (marked explicitly, `**weighted**`): the format certifies this claim-class as fully
  expressible and decidable. The grade means one thing and the recipe decides it.
- **⚠ UNWEIGHTED** (marked explicitly, or **left unmarked**): admitted as an assertion; **the format
  promises nothing about this claim — same evidentiary level as "it was reviewed"**. The claim may
  still be true and important. It is simply not something the format vouches for.

> **Corrected 2026-08-25.** This block used to read *"WEIGHTED (unmarked, the default appearance of
> a graded row)"* — a convention that inverts W1, which says omitted weight means **unweighted** and
> that the format never vouches by silence. An external review found `tools/check_ledger.py` had the
> same inversion, so the tool agreed with the convention and both were wrong. Under the corrected
> rule no row in this envelope claimed weight at all for a day: every row was unweighted until it was
> marked *and* met W2.
>
> **The rows marked `**weighted**` below earned it on 2026-08-26**, one at a time, by the P2
> remediation pass: for each, the named harness was run against a deliberately perturbed copy of the
> shipped source in a scratch worktree, watched to report the claim false, restored, and watched to
> come back green. The perturbation and the observation are recorded **on the row**, in §4.1's
> structured form, bound to that row's own recipe. Rows whose recipe has not been through that are
> still unweighted, and the ones where a perturbation did **not** turn the recipe red are named in
> §7 as findings rather than quietly left out.

Weight is refused — never the claim itself. A row drops to unweighted when its grade has no deciding
machinery (`inspection-argued`, `unspecified`), when its clause is read off its own evidence, or
when no one has yet watched its recipe fail.

> **`CONTRACT` here is NOT Kani's `#[kani::requires]`/`#[kani::ensures]` machinery.** This crate uses
> **zero** function contracts — all 203 harnesses are plain `#[kani::proof]`, and modular proofs are
> built with `#[kani::stub]` + `-Z stubbing`. `CONTRACT` in this table is the review-lens sense
> (*proves the documented rule, on the real shipped path, with an independent oracle*), which is the
> distinction a consumer actually cares about. Verified by `grep -rn 'kani::\(requires\|ensures\|
> proof_for_contract\)' der-verified/src` → **no matches**.

---

**Tier counts for this envelope: 72 weighted, 8 unweighted, 80 rows total** — computed, not typed, by `python3 tools/check_ledger.py` and cross-checked against this line (`core.md` W5). Two earlier figures are deliberately spelled out in words rather than digits, because W5 refuses a rendering that states two different tier-count tuples and a superseded figure written in the count format would be a second stated count: the first claimed seventy-two weighted rows against two unweighted (produced by the W1 inversion described above), and the second, after that inversion was corrected, was zero weighted against seventy-four unweighted. The row total rose from seventy-four to eighty on 2026-08-26 because six rows were **split**, not added — three dual-claim rows became six (`DER-F-8`/`DER-F-8-TLV`, `DER-F-9`/`DER-F-9-TLV`, `DER-C-BITS-4`/`DER-C-BITS-4-DEC`), two sub-claims that had been riding inside a weighted row's prose became rows of their own (`DER-F-8b`, `DER-C-OCT-2b`), and one row whose bounded and unbounded halves could not carry the same grade was separated into `DER-F-4`/`DER-F-4b` (§7, **E-8**).

## 3. The spec axis — and why it is not the module list

The rows below are **X.690 encoding rules and RFC 5280 profile rules**, not source modules. That
choice is the point of this document. The crate's own `PROOF_MANIFEST.md` is organised per module
and answers *"does `sequence.rs` have harnesses?"*. A consumer asks *"is the constructed-form rule
enforced?"* — a question no module owns, and therefore a question a module-shaped table cannot have
a row for. Three of the most important rows in this ledger (`DER-F-8`, `DER-F-9`, `DER-C-OID-2`)
exist **only** on this axis.

Item ids are stable and never reused. Rule references are to X.690 (2021) unless marked RFC 5280.

### 3.1 The `clause source` column — who says the rule should hold (`core.md` W2.3, P1)

Every graded table below carries a **`clause source`** column, added 2026-08-25 to satisfy P1: a
claim that carries weight must record *which clause of which specification it is about*. The item
and the clause are different fields — the item is what was checked, the clause is who says it should
hold — and a row that leaves the second unstated has provenance a reader cannot distinguish from
having none.

Each cell names the clause and then, in parentheses, one token of the spec's closed set
(`external-standard` · `spec-document` · `doc-comment` · `test-name` · `none`). Four classes appear
here, and the distribution is itself a finding:

- **`external-standard` (69 rows)** — X.690 (2021), X.680 (2021), or an RFC. The great majority, as
  it should be for a ledger whose axis is encoding rules.
- **`doc-comment` (3 rows)** — `DER-F-1b`, `DER-F-3`, `DER-P-4`. The requirement is the *crate's own*,
  written in the shipped doc comment the proof is held to: decoder totality, the `u32::MAX` tag cap,
  and error precedence. No standard states any of the three — X.690 sets no upper bound on a tag
  number, and RFC 5280 mandates no order for reporting violations. Naming the RFC on those rows would
  have been the cheap, wrong answer.
- **`spec-document` (7 rows)** — the crate-wide hygiene rows and `DER-X-L4`, whose text lives in an
  in-tree document (`README.md`, `PROOF_MANIFEST.md`, `DOCS-SYNC.md`, `ASSUMPTIONS.md`,
  `gates/map_declared.txt`). **Stated residual:** `PROOF_MANIFEST.md` is partly *generated from the
  source it describes*, so a citation into it is weaker than a citation into a standard. The cells
  point at its hand-written framing prose rather than at a generated table, which narrows the
  circularity without closing it.
- **`none` (1 row)** — `DER-X-BOUND`. Panic-freedom *at realistic input sizes* is a claim about the
  reach of this crate's proofs, not about a requirement anyone wrote down. `none` is reserved to mean
  unweightable by design, which is the right label here and costs nothing: the row is already
  unweighted on its `inspection-argued` grade.

**A clause citation upgrades provenance, never evidence.** `DER-F-8` and `DER-C-BITS-4` now cite
X.680's universal-class tag table; that does **not** touch the disclosed sub-claim that the crate's
*transcription* of that table is faithful, which nothing decides and which §6.1 states in full.

**The token the field exists to keep out is `test-name`, and one row nearly earned it.**
`DER-C-ENUM-2` — *"ENUMERATED uses identifier UNIVERSAL 10"* — is `test-only`: its whole evidence is
a concrete unit test, and the shortest honest-looking answer would have been to point at that test.
That is the provenance W2.3 refuses, because a requirement read off its own test's name is one
nothing could falsify. The requirement is X.680's tag assignment, which exists whether or not the
test does, so the row cites the standard and keeps its weight-eligibility for a reason rather than
by luck. No row in this envelope records `test-name`.

**Where that leaves the backlog.** The P1 axis is clear for every row: none is refused weight for
want of a recorded clause, and none records a token reserved to mean unweightable except
`DER-X-BOUND`, which is unweighted on its grade anyway.

**P2 — the watched-fail obligation — was the whole of what remained on 2026-08-25, and most of it
was discharged on 2026-08-26.** The count then was 63 rows with no witness. The count now is stated
in one place only, the tier-count line above, because W5 refuses a rendering that states two
different tuples and a backlog figure written here would be exactly that. What the line does not
say, and this paragraph does:

- **Every weighted row's witness came from a run, not from a description.** The pass perturbed the
  shipped source in a scratch worktree (`git worktree` off a backup ref; the real tree was never
  touched), ran that row's own harness under a memory cap, recorded the verdict, restored with
  `git checkout` and ran it again. A row is weighted only where the sequence was **red then green**.
- **The rows still unweighted are unweighted for a stated reason, and the reasons are of three
  kinds.** (a) The grade is not weight-eligible — `inspection-argued` on `DER-F-8b`,
  `DER-C-OCT-2b`, `DER-S-5b`, `DER-X-BOUND`; nothing to watch fail, by definition. (b) The only
  recipe is the **Lean lid**, and this pass deliberately did not run the Aeneas/Charon/Lean stack —
  `DER-F-1b` and `DER-F-4b`. (c) The recipe is the **whole-gate run `G`** or a committed-log read `R`, neither of
  which a single-harness mutation can falsify in a night — the `DER-S-*` hygiene rows, where they
  say so.
- **Every row now states its tier.** `tools/check_ledger.py` reports `80 rows checked (72 weighted,
  8 unweighted), 0 errors, 0 warnings` — no `tier-unstated`, no `weight-pending`. The eight
  unweighted rows are the four whose grade is never weight-eligible (`DER-F-8b`, `DER-C-OCT-2b`,
  `DER-S-5b`, `DER-X-BOUND`), the two whose only recipe is the Lean lid (`DER-F-1b`, `DER-F-4b`),
  the one whose recipe is the whole-gate run (`DER-S-2`), and the one whose seeded-bad control
  needs the Lean toolchain (`DER-S-5a`).
- **Four perturbations did not turn their harness red**, and all four are recorded on the row and in
  §7 rather than dropped. Two are reach findings (**E-7**): the perturbed line is unreachable at the
  harness's declared bound, which is a fact about the claim's *reach* and is the more useful half of
  the result. Two are the cover-only harnesses (**E-6**), where the verdict cannot say no but the
  **tally** fell from `1 of 1` to `0 of 1` — those two rows are weighted on the tally, and say so.

---

## 4. Self-verify recipes

All commands run from the repository root at `130de97`. `<H>` = a harness path of the form
`<module>::proofs::<fn>`.

| id | recipe | what green means |
|---|---|---|
| **G** | `DER_REQUIRE_LEAN=1 ./check.sh` | Exit 0 + `== check.sh: PASS (L3 kani floor: GREEN; L4 lean lid: PASS) ==`. Gates, 485 tests, all 203 harnesses. Needs ≥24 GB RAM, ~71 min, harnesses run sequentially. **Set `DER_REQUIRE_LEAN=1`** — without it an absent Lean toolchain takes a guarded SKIP path and still exits 0; see the note below. |
| **K** `<H>` | `cargo kani -Z stubbing --manifest-path der-verified/Cargo.toml --harness <H>` | `VERIFICATION:- SUCCESSFUL` for that one harness (note Kani's literal spelling, with the dash). Re-derives the row from source. Six modules are HEAVY (>7 GB peak, up to ~20 GB): `set_of`, `sequence`, `x509_name`, `x509_tbs_certificate`, `x509_certificate`, `x509_extension` — see `gates/tiers.txt`. |
| **R** `<H>` | `awk '/Checking harness <H>/,/^Verification Time/' evidence/check-bffab69.log` | The committed run's own `SUMMARY`, **cover tally**, and `VERIFICATION:- SUCCESSFUL` line for that harness. A bare `grep '<H>'` prints only the `Checking harness …` heading and shows you **neither** — the verdict and cover lines come several lines later. Valid only while the freshness command in §1 returns empty. |
| **N** `<thm>` | `sh lean/check_lean.sh`, then read `<thm>` in `lean/<X>Proofs.lean` | **Require the literal `lean lid: PASS (sorry-free)`.** The lid re-extracts from the shipped `.rs` and fails closed on drift — but see the warning below. |
| **T** `<filter>` | `cargo test --manifest-path Cargo.toml <filter>` | `test result: ok`. Point evidence only. |
| **A** `<pattern>` | a grep that **must return nothing**, with its positive control | Used only by `not-covered` rows. A zero from a grep is a claim about your pattern, so each A-recipe below carries the control input that *would* match. |
| **D** `<doc §>` | open the cited section and read the argument | `inspection-argued` rows only. There is nothing to run. |
| **M** `<command>` | a **mechanical** check — an in-tree gate, or a presence-grep — run exactly as written | its own stated output, and exit 0. `mechanical` rows only. *Added 2026-08-26.* §4.1 asks a `mechanical` row for a **seeded-bad fixture the gate must catch** rather than a behavioural mutation, because a formatter or a count-derivation gate has no behavioural oracle to mutate — the claim being weighted is the gate's own claim. Each such row records that seeding on the row, as its watched-fail witness. |
| **E** `<pattern> @ <file>` | an absence check **scoped to the implementation region and to code lines**: `sed -n '1,/^mod tests/p' <file> \| grep -v '^\s*//' \| grep -Eic '<pattern>'`. Where a module's `#[cfg(kani)] mod proofs` precedes its `mod tests`, the region marker is `^#\[cfg(kani)\]` instead — each row states the one it used | **0**, with its positive controls stated on the row: (control 1) **required** — the same scoping and pattern class find something that IS present; (control 2) **where available** — dropping the scope does *not* return 0, i.e. the scope is what produced the zero. See the warning below for why one control is not enough, and why control 2 is not always available. |

> ### Absence checks are the weakest recipe here, and this envelope got one wrong twice
>
> **Replaced 2026-08-26.** This row used to define `E` as an *enumeration of `ProfileError`'s four
> variants*, and claimed the four mapped one-to-one onto `DER-P-1`…`DER-P-4`, so a rule absent from
> the enum was thereby shown unenforced. **That recipe is unsound and is withdrawn.** The crate's own
> `COVERAGE.md` §4 replaced it for the same reason, and this envelope is conformed to that ruling
> rather than kept as a second, weaker opinion about the same commit.
>
> **Why it was unsound.** The `ProfileError` docstring gives one direction only — *variant ⇒ enforced
> rule*. It does not give the converse, so enumerating the enum cannot establish that an absent rule
> is unenforced: a rule could be enforced by returning an existing variant, or by returning `Ok` on a
> path that silently accepts. **`DER-P-4` is the standing counterexample inside this very crate** —
> error precedence is an enforced, `contract`-graded rule with *no variant of its own*. So the four
> variants do not map onto the four `DER-P-*` rows, and the recipe built on assuming they did decided
> nothing. Positive enumeration beats absence-grepping only where the set is closed **in the
> direction you need**; an error enum is closed for *"what can be reported"*, not for *"what is
> checked"*.
>
> **And the absence-grep it replaced failed twice, in two independent ways** — both worth stating,
> because they are the two ways a grep-zero lies:
>
> - **Wrong scope.** `DER-P-5/6/7` each promised a grep scoped to `der-verified/src/profile.rs`. Run
>   against the file it returns **14 hits**, not zero, and did so at `2b9f3d55` too (§7, **E-3**). All
>   14 are inside `profile.rs`'s own `mod tests`. **A Rust module's unit tests live in the same file,
>   so scoping a grep to one file does not exclude fixtures.**
> - **Wrong pattern.** The first replacement control was written `grep -c
>   'basic_constraints\|BasicConstraints'` and returned **0 on the whole file**, appearing to show the
>   fixtures had vanished. They had not: they are named `EXT_BASIC_CONSTRAINTS_DEFAULT`, upper-snake,
>   which neither alternative matches case-sensitively. **The control that was supposed to catch a
>   lying grep was itself a lying grep.**
>
> So `E` is an absence check with **two** controls, and both are necessary:
>
> ```sh
> # the claim: scoped to the implementation region, above `mod tests`
> sed -n '1,/^mod tests/p' der-verified/src/profile.rs | grep -Eic 'basic_?constraints'   # -> 0
> # control 1 -- the same scoping and pattern class DO find a rule that is enforced
> sed -n '1,/^mod tests/p' der-verified/src/profile.rs | grep -ic  'ExtensionsRequireV3'  # -> 6
> # control 2 -- the scoping is doing real work; unscoped, the fixtures are still there
> grep -Eic 'basic_?constraints' der-verified/src/profile.rs                              # -> 14
> ```
>
> Control 1 proves the pattern can find something. Control 2 proves the *scope* is what produced the
> zero. A single control catches only one of the two failures above. Reading `ProfileError`'s four
> variants alongside these rows is still worthwhile as a **supporting inspection** — it is simply not
> the thing that decides them.
>
> **Two further things this envelope learned on 2026-08-26, running the recipe rather than quoting
> it**, and both are on the rows below rather than buried here:
>
> - **A third way a grep-zero lies: comment mentions.** `DER-C-BITS-4`'s not-covered half asks
>   whether `bit_string.rs` ever decodes a TLV. `grep -c 'decode_tlv'` over its implementation
>   region returns **1** — and that one hit is a *doc comment* saying `decode_tlv` passes the tag
>   through untouched. The code count is **0**. So `E` filters comment lines (`grep -v '^\s*//'`)
>   before counting, and a row that does not say whether it counted comments has not said what it
>   measured. The reverse error is just as easy: a pattern that only ever appears in prose reads as
>   *present* to a naive grep and gives a **false non-zero**, which would sink an honest row.
> - **Control 2 is not always available, and `COVERAGE.md` overstates that it is.** That file gives
>   `DER-P-6` and `DER-P-7` the note *"same controls"* as `DER-P-5`. Measured here: unscoped,
>   `key_?usage` and `name_?constraint` return **0** over `profile.rs` too — there are no
>   fixtures naming them anywhere in the file, so removing the scope changes nothing and control 2
>   cannot fire. Those two rows carry **control 1 only**, and say so. The zero is still the right
>   answer; the scoping is simply not what produced it, and claiming otherwise would be the same
>   defect as the lying control it was invented to catch. Recorded in §7 as **E-4**.

> ### ⚠ A green `check.sh` could mean the Lean stage never ran — **FIXED 2026-08-25**
>
> **This was the defect, and it is the one this envelope's own §4 warned about.**
> `lean/check_lean.sh` is **guarded**: with no Aeneas/Charon/Lean toolchain it printed a SKIP line
> and **exited 0**, indistinguishably from a pass, and `check.sh` then printed an unqualified
> `== check.sh: PASS ==`. So `PASS` alone did **not** witness any row backed by an L4 (Lean) lid. Two of the
> crate's own three recent clean-room runs are in exactly that state — they ran on VMs with no Lean
> stack and had to cite a separate lid log for L4.
>
> **What changed.** The lean stage now emits a machine-readable `lean-lid-status: PASS | SKIP |
> FAIL` on every exit path (and writes `$DER_LID_STATUS_FILE`), and `check.sh`'s summary line names
> the state:
>
> ```
> == check.sh: PASS (L3 kani floor: GREEN; L4 lean lid: PASS) ==      <- L4 witnessed
> == check.sh: PASS (L3 kani floor: GREEN; L4 lean lid: SKIP -- NOT WITNESSED) ==
> ```
>
> plus a loud multi-line NOT-WITNESSED block in the second case. `DER_REQUIRE_LEAN=1` turns an
> absent toolchain into a hard failure, and should be set for any run that will be published or
> minted into a receipt. A self-test (`gates/test_check_lean_skip.py`, run by `check.sh` *before*
> the stage it guards) drives all three states, including a stub-toolchain positive control proving
> the guard does not fire unconditionally.
>
> **For runs at or after `3725018`, read the summary line — it now carries the answer.** For runs
> BEFORE that commit the old warning stands in full: grep the output for `lean lid: PASS
> (sorry-free)` and confirm it is not `SKIP`.
>
> **The certified run of this envelope is the first run under the fix**, and it is the strong case
> rather than the grandfathered one: `bffab69` was run with `DER_REQUIRE_LEAN=1` set, so an absent
> Aeneas/Lean toolchain would have **failed** it rather than skipping, and its summary line reads
> `PASS (L3 kani floor: GREEN; L4 lean lid: PASS)`. It also reports `lid-source-state.txt unchanged
> (hashes identical)`, so the six extracted Lean sources did not drift. The trade is stated in §1:
> the run is on the maintainer's box, because that is the only machine carrying the Aeneas/Charon/
> Lean stack, so a single run covering both L3 and L4 cannot also be clean-room. Earlier runs bought
> clean-room provenance by giving up L4.

**Cover tallies matter and the gate does not enforce them.** Kani reports a harness whose
`kani::cover` is unsatisfiable as `SUCCESSFUL` with `0 of 1 cover properties satisfied`.
`check.sh` does **not** fail on that. Three harnesses are in exactly that state and are disclosed
(§6). When recipe **R** shows a `0 of N cover properties satisfied` line, read it.

---

## 5. The coverage ledger

### 5.1 Framing — identifier, length, TLV (X.690 §8.1, §10.1)

| id | rule | clause source | status | strength | verify |
|---|---|---|---|---|---|
| `DER-F-1` | Identifier octets decode: class, constructed bit, tag number; low- and high-tag forms (§8.1.2) | X.690 (2021) §8.1.2 (external-standard) | evidenced | **weighted** · **PROBE** (bounded — a symbolic `[u8; 7]` identifier buffer, `unwind(12)`). **Re-graded from CONTRACT 2026-08-26, conforming to `COVERAGE.md`'s review-adjudicated ruling: the cited harness is a ROUND TRIP.** It decodes, re-encodes the decoded `Tag` with the crate's own `encode_tag`, and compares to the input. That decides *canonicality* — an accepted string is the unique encoding of what it decoded to — but **not** that the class/constructed/tag-number bits were read correctly, because the oracle is the crate's own encoder. A decoder and encoder sharing one misreading pass together. The tag lid is **not** an L4 row for *this* rule | `K tag::proofs::decode_tag_accepts_only_canonical` · watched-fail(`K tag::proofs::decode_tag_accepts_only_canonical`): read the constructed bit from identifier bit 7 (`& 0x40`) instead of bit 6 (`& 0x20`) in the shipped `decode_tag` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: re[..relen] == buf[..used]`; restoring the source returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-1b` | `decode_tag` terminates on any input and an accepted decode consumes `1..=input.len()` bytes | `tag.rs::decode_tag` doc comment — *"never panics"*, returns `(tag, bytes_consumed)` (doc-comment). The `1..=len` half restates X.690 (2021) §8.1.2's identifier-octet framing; totality has no clause in the standard | evidenced | ⚠ **UNWEIGHTED** · **CONTRACT** — the only recipe on this row is the Lean lid, and **no one has watched it fail**. The P2 pass of 2026-08-26 ran Kani mutations only; perturbing a lid and re-running `check_lean.sh` needs the Aeneas/Charon/Lean stack, which that pass deliberately did not touch. Weight is refused for want of a witness, not for any doubt about the lid | `N tag_decode_total`, `tag_decode_used_bounds` (`lean/TagProofs.lean`, ∀-length) |
| `DER-F-2` | High-tag-number form must be minimal — no leading `0x80` padding (§8.1.2.4.2 c) | X.690 (2021) §8.1.2.4.2 c) (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — `unwind(12)`; a symbolic first identifier octet constrained to the high-tag marker, over every class and both forms, against a symbolic single continuation octet `<= 30`) | `K tag::proofs::high_tag_of_small_number_is_non_minimal` · `K tag::proofs::leading_zero_high_tag_is_non_minimal` · watched-fail(`K tag::proofs::high_tag_of_small_number_is_non_minimal`): weakened the high-tag minimality floor in the shipped `decode_tag` from `number <= 30` to `number <= 3` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_tag(&[first, v]) == Err(TagError::NonMinimal)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-3` | Tag numbers above the supported width are rejected as `TooLarge`, never misread and never a panic. **Supported range is up to `u32::MAX`** (`tag.rs:9`) — a documented deviation from unlimited DER, safe for X.509 | `tag.rs` module docs, *"Supported range & compliance boundary"* (doc-comment) — a declared deviation from X.690 (2021) §8.1.2.4.2, which sets no upper bound | evidenced | **weighted** · **PROBE** (bounded — `unwind(12)`; the harness fixes ONE overflow encoding, `90 80 80 80 00`, and leaves only the first identifier octet symbolic) | `K tag::proofs::too_large_tag_is_classified` · watched-fail(`K tag::proofs::too_large_tag_is_classified`): loosened the shipped `decode_tag`'s u32 overflow guard from `number > u32::MAX >> 7` to `>> 3` -> the harness reported `VERIFICATION:- FAILED` on the `Err(TagError::TooLarge)` assertion; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-4` | Length is the **shortest** definite form — short form for <128, no leading zero octets in long form (§10.1), **as decided by the bounded Kani half**. *Re-graded and split 2026-08-26 on a review adjudication of §7's **E-8**; the unbounded Lean half is now `DER-F-4b`* | X.690 (2021) §10.1 (external-standard) | evidenced | **weighted** · **PROBE** (bounded — a symbolic `[u8; 8]` length buffer, `unwind(10)`). **Re-graded from CONTRACT+L4: the cited harness is a ROUND TRIP.** It decodes, re-encodes the decoded length with the crate's own `encode_length`, and compares to the input. That decides *canonicality* — an accepted length string is the unique encoding of what it decoded to — but **not** that the length octets were read as §10.1 requires, because the oracle is the crate's own encoder. A decoder and encoder sharing one misreading pass together. This is the same shape as the adjudicated `DER-F-1` and as `DER-C-OCT-2`, where the mutation pass proved it (§7, **E-5**). The two non-minimality harnesses beside it are fixture-shaped and do not lift the grade | `K length::proofs::decode_accepts_only_canonical` · `K length::proofs::leading_zero_is_non_minimal` · `K length::proofs::long_form_of_short_value_is_non_minimal` · watched-fail(`K length::proofs::decode_accepts_only_canonical`): lowered the shipped `decode_length`'s long-form minimality threshold from `0x80` to `0x40`, admitting long-form encodings of values `0x40..=0x7F` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: relen == used`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-4b` | The same shortest-definite-form rule **over every input length**, kernel-checked in Lean through the Aeneas lid. *Split out of `DER-F-4` on 2026-08-26 by the same adjudication: the lid is the oracle independent of the crate's own encoder, and independence is what would carry this rule above its Kani half — so it is stated as its own claim at its own evidentiary state rather than folded into a grade the Kani evidence does not support (§7, **E-8**)* | X.690 (2021) §10.1 (external-standard) | evidenced | ⚠ **UNWEIGHTED** · **CONTRACT** — the only recipe on this row is the Lean lid, and **no one has watched it fail**, exactly as on `DER-F-1b`. The P2 pass of 2026-08-26 ran Kani mutations only; perturbing a lid and re-running `check_lean.sh` needs the Aeneas/Charon/Lean stack, which that pass deliberately did not touch. Weight is refused for want of a witness, not for any doubt about the lid — and refusing it here is the point of the split: the strong, unwitnessed half no longer rides on the weak, witnessed one | `N decode_accepts_only_canonical` (`lean/LengthProofs.lean`, ∀-length) |
| `DER-F-5` | Indefinite length (`0x80`) and the reserved `0xFF` initial octet are rejected (§8.1.3.6, §10.1) | X.690 (2021) §8.1.3.6, §10.1 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 8]` length buffer with the initial octet pinned to the case under test, `unwind(10)`) | `K length::proofs::indefinite_is_classified` · `K length::proofs::reserved_is_classified` · watched-fail(`K length::proofs::indefinite_is_classified`): moved the shipped `decode_length`'s indefinite-length rejection from initial octet `0x80` to `0x81` -> the harness reported `VERIFICATION:- FAILED` (an index-out-of-bounds check on the length octets, reached because `0x80` then fell through to the long-form path); restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-6` | An accepted TLV consumes exactly `header + declared length`, its value is exactly that window, and `used ≤ input.len()` — **no over-read** (§8.1.1) | X.690 (2021) §8.1.1, §8.1.3 (external-standard) | evidenced | **weighted** · **CONTRACT** (unbounded — the Lean lid `decode_tlv_structure` quantifies over all input lengths; the Kani half that carries this row's witness is bounded at a symbolic `[u8; 16]` with symbolic input length, `unwind(16)`). **Residual, stated:** the witness below is for the Kani recipe; the Lean half has not been watched to fail | `K tlv::proofs::decode_tlv_structure` · `N decode_tlv_structure` (`lean/TlvProofs.lean`, ∀-length) · watched-fail(`K tlv::proofs::decode_tlv_structure`): relaxed the shipped `decode_tlv`'s over-read guard by one byte, from `input.len() < end` to `input.len() + 1 < end` -> the harness reported `VERIFICATION:- FAILED`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-7` | A top-level DER value is *exactly one* TLV — trailing bytes are rejected (§8.1.1.1) | X.690 (2021) §8.1.1.1 (external-standard) | evidenced | **weighted** · **PROBE** (bounded — `unwind(16)`; each harness uses **one fixed valid object plus one symbolic trailing byte**, not a symbolic TLV domain). The Lean lids do not cover the strict variants at all | `K tlv::proofs::strict_rejects_trailing` · `K sequence::proofs::strict_rejects_trailing` · `K set_of::proofs::strict_rejects_trailing` · watched-fail(`K tlv::proofs::strict_rejects_trailing`): changed the shipped `decode_tlv_strict`'s exactly-one-TLV test from `used != input.len()` to `used > input.len()`, admitting trailing bytes -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_tlv_strict(&[0x02, 0x01, v, t]) == Err(TlvError::TrailingData)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-8` | **The shipped form rule agrees with the crate's primitive-only table** for every identifier — e.g. `21 00` is rejected as a BOOLEAN. Decided across X.680's full assignment range `1..=36`, incl. the high-tag types 31..=36. *Reworded 2026-08-26 to what the harnesses actually decide; the standards-agreement half is now its own row, `DER-F-8b`* | X.690 (2021) §8.1.2, §10.2 + X.680 (2021) Table 1, universal-class tag assignments (external-standard). **The citation is to the standard; the crate's *transcription* of Table 1 is `DER-F-8b`, which nothing decides. A clause reference does not upgrade that transcription's evidence.** | evidenced | **weighted** · **CONTRACT** (unbounded — complete over the entire identifier domain: symbolic `u32` tag number × all four classes × both forms, with no buffer and no unwind limit) | `K identifier_form::proofs::constructed_form_rule_matches_oracle_on_all_tags` · `K identifier_form::proofs::rejects_every_disclosed_illegal_identifier` · `K identifier_form::proofs::high_tag_universal_types_are_form_checked` · `K identifier_form::proofs::legal_der_the_comparison_library_rejected_is_still_accepted` · watched-fail(`K identifier_form::proofs::constructed_form_rule_matches_oracle_on_all_tags`): flipped the shipped `required_form`'s entry for universal tags 9 and 10 (REAL, ENUMERATED) from `Primitive` to `Constructed` -> the harness reported `VERIFICATION:- FAILED` on both directions of the biconditional; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-8b` | **That table itself is a faithful transcription of X.680** — i.e. the types it marks primitive-only really are primitive-only. *Split out of `DER-F-8` on 2026-08-26, conforming to `COVERAGE.md`* | X.680 (2021) Table 1, universal-class tag assignments (external-standard) | **partial** | ⚠ **UNWEIGHTED** · **inspection-argued** — the four domain-complete theorems compare the shipped `match` against a bitmask oracle **written by the same author**. They establish the two encodings agree on all 2^32 tag numbers, which is what a transcription slip would violate; they cannot establish agreement with the standard. Spot-checked per-arm by concrete tests. Never weight-eligible: there is no deciding machinery to watch fail | `D identifier_form.rs` — read the per-arm citations, whose own source says the same-author mask cannot establish standards correctness. **A shared misreading of X.680 passes every harness in `DER-F-8`.** |
| `DER-F-8-TLV` | The same constructed-form rule at the **default** framing entry point — `tlv::decode_tlv`, `decode_tlv_strict`, `tag::decode_tag` and the SEQUENCE child walk. *Split out of `DER-F-8` on 2026-08-26: "done at the opt-in entry point; not-covered at `decode_tlv`" is two claims, and a cell holding both lets a reader take whichever half they prefer* | X.690 (2021) §8.1.2, §10.2 (external-standard) | **gap** | **weighted** · **not-covered** — in scope for this axis and deliberately undecided here: a permissive framing reader is the crate's stated design (§6.1), and `identifier_form` is opt-in | `E 'identifier_form' @ der-verified/src/tlv.rs` — code lines of the implementation region only (`grep -v '^\s*//'`, region `1,/^#\[cfg(kani)\]/`) -> **0**. positive-control(`E 'identifier_form' @ der-verified/src/tlv.rs`): ran the same scoped, comment-filtered grep for `decode_length`, a helper this region really does call -> it returned 3, so the pattern class and the scoping can both produce a non-zero on this file, observed 2026-08-26. Control 2 is **not available** here: unscoped, `identifier_form` returns 0 over `tlv.rs` as well — the scope is not what produced this zero |
| `DER-F-9` | **The reserved EOC identifier `00 00` is never a legal DER identifier** — universal 0 is BER's end-of-contents marker (§8.1.5), and DER admits no indefinite-length encoding for it to terminate (§10.1) | X.690 (2021) §8.1.5, §10.1 (external-standard) | evidenced | **weighted** · **CONTRACT** (unbounded — a domain-complete biconditional over every identifier: rejected iff UNIVERSAL 0, either form, no buffer and no unwind limit) | `K identifier_form::proofs::reserved_eoc_rejected_iff_universal_zero` · watched-fail(`K identifier_form::proofs::reserved_eoc_rejected_iff_universal_zero`): moved the shipped `validate_identifier_form`'s reserved-identifier rejection off UNIVERSAL 0 onto UNIVERSAL 60 -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: (got == Err(FormError::ReservedIdentifier)) == is_eoc`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-F-9-TLV` | The same EOC rule at the **default** framing entry point (`tlv::decode_tlv` and friends). *Split out of `DER-F-9` on 2026-08-26, same reason as `DER-F-8-TLV`* | X.690 (2021) §8.1.5, §10.1 (external-standard) | **gap** | **weighted** · **not-covered** — `decode_tlv` accepts `00 00` and reports a zero-length UNIVERSAL 0 value; see §6.1 | `E 'identifier_form' @ der-verified/src/tlv.rs` — code lines of the implementation region only -> **0**, the same measurement as `DER-F-8-TLV`. positive-control(`E 'identifier_form' @ der-verified/src/tlv.rs`): ran the same scoped, comment-filtered grep for `decode_length`, a helper this region really does call -> it returned 3, so a non-zero is reachable for this pattern class and this scope, observed 2026-08-26. Control 2 not available, as above |

### 5.2 Content codecs — per type

| id | rule | clause source | status | strength | verify |
|---|---|---|---|---|---|
| `DER-C-BOOL` | `TRUE` is encoded as `0xFF` and nothing else; content is exactly one octet (§11.1) | X.690 (2021) §11.1 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — exhaustive over the whole 1-octet content domain: a symbolic `u8`, no unwind limit needed) | `K boolean::proofs::one_octet_is_canonical` · `K boolean::proofs::wrong_length_is_bad_length` · watched-fail(`K boolean::proofs::one_octet_is_canonical`): changed the shipped `decode_bool`'s canonical TRUE octet from `0xFF` to `0xFE` -> the harness reported `VERIFICATION:- FAILED` on both `b != 0x00 && b != 0xFF` and `b == encode_bool(v)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-INT-1` | INTEGER content is minimal two's-complement — no redundant `00`/`FF` padding (§8.3) | X.690 (2021) §8.3 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 8]` content buffer, `unwind(12)`) | `K integer::proofs::decode_accepts_only_minimal` · `K integer::proofs::redundant_positive_padding_is_non_minimal` · `K integer::proofs::redundant_negative_padding_is_non_minimal` · watched-fail(`K integer::proofs::decode_accepts_only_minimal`): turned the shipped `decode_integer`'s two-branch redundant-padding test from a disjunction into a conjunction, so no padding is rejected -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: relen == n`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-INT-2` | The same minimality rule at **arbitrary magnitude** (big serial numbers), not just `i64` | X.690 (2021) §8.3 (external-standard) — the same clause as `DER-C-INT-1`, at arbitrary magnitude | evidenced | **weighted** · **CONTRACT** (unbounded — the Lean lid `validate_iff_minimal` quantifies over all content lengths; the Kani half that carries this row's witness is a symbolic 20-octet buffer at symbolic length, `unwind(1)`). **Residual, stated:** the witness below is for the Kani recipe; the Lean half has not been watched to fail — see `DER-F-1b` | `K big_integer::proofs::validate_iff_minimal_oracle` · `N validate_iff_minimal` (`lean/BigIntProofs.lean`, ∀-length) · watched-fail(`K big_integer::proofs::validate_iff_minimal_oracle`): changed the shipped `validate_integer_content`'s negative redundant-padding sentinel from `0xFF` to `0xFE` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: accepted == oracle_says_ok`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-INT-3` | INTEGER content is never empty (§8.3.1) | X.690 (2021) §8.3.1 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — the empty-content case exactly, with no unwind limit; the claim is about one input, and that input is the whole of it) | `K integer::proofs::empty_is_classified` · watched-fail(`K integer::proofs::empty_is_classified`): removed the shipped `decode_integer`'s empty-content rejection, rewriting the guard to an unreachable length test -> the harness reported `VERIFICATION:- FAILED` on an index-out-of-bounds check reached by the now-unguarded read of `content[0]`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-BITS-1` | BIT STRING unused-bits octet is `0..=7` (§11.2.1) | X.690 (2021) §11.2.1 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — `unwind(6)`, over a symbolic unused-bits octet, i.e. the whole `u8` domain of that field) | `K bit_string::proofs::unused_too_large_is_classified` · watched-fail(`K bit_string::proofs::unused_too_large_is_classified`): raised the shipped `decode_bit_string`'s unused-bits ceiling from 7 to 9 -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_bit_string(&[u]) == Err(BitStringError::UnusedBitsTooLarge)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-BITS-2` | Every unused bit is zero (§11.2.2) | X.690 (2021) §11.2.2 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — `unwind(6)`, over a symbolic unused-bits octet and a symbolic final content octet) | `K bit_string::proofs::nonzero_padding_is_classified` · `K bit_string::proofs::decode_accepts_only_canonical` · watched-fail(`K bit_string::proofs::nonzero_padding_is_classified`): replaced the shipped `decode_bit_string`'s padding mask `(1 << unused) - 1` with `(1 << unused) >> 1`, so most non-zero pad bits pass -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_bit_string(&[unused, last]) == Err(BitStringError::NonZeroPadding)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-BITS-3` | The empty BIT STRING is exactly `[0x00]` (§11.2.2.1) | X.690 (2021) §11.2.2.1 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — the wholly empty content case and the empty-with-non-zero-unused case, both with no unwind limit) | `K bit_string::proofs::empty_is_classified` · `K bit_string::proofs::empty_nonzero_unused_is_classified` · watched-fail(`K bit_string::proofs::empty_is_classified`): made the shipped `decode_bit_string` accept wholly empty content instead of rejecting it as `Empty` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_bit_string(&[]) == Err(BitStringError::Empty)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-BITS-4` | BIT STRING must use the **primitive** form, **at the opt-in `identifier_form` entry point** (§10.2). *Split on 2026-08-26: the not-covered half at `decode_bit_string` is now `DER-C-BITS-4-DEC`* | X.690 (2021) §10.2 + X.680 (2021) Table 1 (BIT STRING = UNIVERSAL 3) (external-standard) — and it inherits `DER-F-8b`'s unweighted transcription caveat with the table, per §6.1 | evidenced | **weighted** · **CONTRACT** (unbounded — inherited from `DER-F-8`: the rule is decided over the entire identifier domain, and BIT STRING is UNIVERSAL 3, inside it) | `K identifier_form::proofs::constructed_form_rule_matches_oracle_on_all_tags` (BIT STRING is UNIVERSAL 3, inside the decided range) · `K identifier_form::proofs::rejects_every_disclosed_illegal_identifier` · watched-fail(`K identifier_form::proofs::constructed_form_rule_matches_oracle_on_all_tags`): flipped the shipped `required_form`'s entry for two universal tags (9 and 10) from `Primitive` to `Constructed` -> the harness reported `VERIFICATION:- FAILED` on both directions of the biconditional it checks for every tag number, UNIVERSAL 3 included; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-BITS-4-DEC` | The same primitive-form rule at `bit_string::decode_bit_string` itself. *Split out of `DER-C-BITS-4` on 2026-08-26* | X.690 (2021) §10.2 (external-standard) | **gap** | **weighted** · **not-covered** — `decode_bit_string` takes the TLV's **content** and never sees the identifier, so it cannot enforce a form rule. **E-1 (the docstring that claimed otherwise) is FIXED** — it now names the typed callers and `identifier_form` | `E 'decode_tlv' @ der-verified/src/bit_string.rs` — code lines of the implementation region only (`grep -v '^\s*//'`, region `1,/^#\[cfg(kani)\]/`) -> **0**: the module never decodes a TLV, so no identifier reaches it. positive-control(`E 'decode_tlv' @ der-verified/src/bit_string.rs`): ran the same scoped, comment-filtered grep over `octet_string.rs`, a module that *does* decode a TLV -> it returned 2, and dropping the comment filter over `bit_string.rs` itself returns 1 (a doc comment naming `decode_tlv`), so both the pattern and the comment filter are doing real work, observed 2026-08-26 |
| `DER-C-BITS-5` | NamedBitList trailing-zero minimality (X.680 §22.7, e.g. `KeyUsage`) | X.680 (2021) §22.7 (external-standard) | **gap** | **weighted** · **out-of-scope** — weight attaches to *the producer declared this, here*, and to nothing about the code | `D bit_string.rs` module docstring — a property of the ASN.1 *type*, deliberately not applied to a bare BIT STRING |
| `DER-C-OCT-1` | OCTET STRING must use the primitive form; the BER constructed (segmented) form is rejected (§10.2) | X.690 (2021) §10.2 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — `unwind(16)`, over the constructed identifier `0x24` with a symbolic 1-octet body) — *at the typed parser, not at the framing layer* | `K octet_string::proofs::constructed_form_is_rejected` · `K octet_string::proofs::accepted_identifier_is_canonical_0x04` · watched-fail(`K octet_string::proofs::constructed_form_is_rejected`): narrowed the shipped `decode_octet_string`'s constructed-form rejection to empty-valued TLVs only -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_octet_string(&[0x24, 0x01, a]) == Err(OctetStringError::Constructed)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-OCT-2` | An accepted OCTET STRING's content is exactly the value **that `decode_tlv` returned** — the typed parser forwards the framing layer's value slice unchanged. *Item narrowed and grade lowered 2026-08-26 — see the mutation finding in the strength cell and §7, **E-5*** | X.690 (2021) §8.7, and §8.1.1's value window (external-standard) | evidenced | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` at symbolic input length, `unwind(16)`). **Why not CONTRACT: the oracle is derived from the state under test.** The harness compares `decode_octet_string`'s output against `decode_tlv(input).unwrap()` — the same function the subject calls. Perturbing `decode_tlv` so its value slice is the whole tail rather than the declared `header..header+len` window moved subject and oracle together and the harness stayed **GREEN**; only perturbing `decode_octet_string`'s own forwarding turned it red. So it decides *forwarding fidelity* and not *the window*, which is the same defect `COVERAGE.md` had a second-model review adjudicate on `DER-F-1` | `K octet_string::proofs::accepted_content_is_the_tlv_value` · watched-fail(`K octet_string::proofs::accepted_content_is_the_tlv_value`): dropped the last byte of the forwarded value in the shipped `decode_octet_string` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: dec.len() == tlv.value.len()`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-OCT-2b` | That the forwarded value **is** the declared `header..header+len` window. *Split out of `DER-C-OCT-2` on 2026-08-26, because that row's own harness cannot decide it* | X.690 (2021) §8.1.1 — the value window (external-standard) | **partial** | ⚠ **UNWEIGHTED** · **inspection-argued** — it follows compositionally from `DER-F-6` (`tlv::decode_tlv_structure` re-derives the header independently and compares against the declared length widened to `u64`, deliberately not reusing the implementation's own cast) plus `DER-C-OCT-2`'s forwarding. **That composition is prose, and no single harness checks it.** Never weight-eligible at this grade | `D PROOF_MANIFEST.md` §8.3 — the oracle-provenance section; and read `DER-F-6` and `DER-C-OCT-2` together |
| `DER-C-NULL` | NULL content is empty and nothing else (§8.8) | X.690 (2021) §8.8 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — the empty content plus symbolic content at lengths 1, 2 and 3, with no unwind limit) | `K null::proofs::only_empty_is_valid` · watched-fail(`K null::proofs::only_empty_is_valid`): widened the shipped `decode_null` to accept one content octet as well as none -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_null(&[a]) == Err(NullError::NonEmpty)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-OID-1` | OID subidentifiers are minimal base-128 — no leading `0x80`, last octet terminates (§8.19) | X.690 (2021) §8.19 (external-standard) | evidenced | **weighted** · **CONTRACT** (unbounded — the Lean lid `validate_iff_canonical` quantifies over all content lengths; the Kani half that carries this row's witness is bounded at a symbolic 5-octet buffer, `unwind(8)`). **Residual, stated:** the witness below is for the Kani recipe; the Lean half has not been watched to fail | `K oid::proofs::leading_0x80_is_non_minimal` · `K oid::proofs::later_0x80_is_non_minimal` · `K oid::proofs::unterminated_is_truncated` · `N validate_iff_canonical` (`lean/OidProofs.lean`, ∀-length) · watched-fail(`K oid::proofs::leading_0x80_is_non_minimal`): moved the shipped `validate_oid`'s leading-`0x80` subidentifier minimality check onto `0x81` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: validate_oid(&buf) == Err(OidError::NonMinimalSubid)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-OID-2` | **Subidentifier width limits and arc materialisation** (`X = min(Z/40,2)`, `Y = Z − 40X`) | X.690 (2021) §8.19.4 (external-standard) — the first-subidentifier arc formula | **gap** | **weighted** · **out-of-scope** — weight attaches to the declaration, not to the code | `D oid.rs` docstring, "Scope boundaries (deliberate)": a canonical subidentifier may exceed `u64` and is accepted; *"a downstream arc decoder must enforce its own integer-width limit"*. The crate ships a canonical-form validator, not an arc decoder. |
| `DER-C-ENUM-1` | ENUMERATED **content** follows the INTEGER rules (§8.4) | X.690 (2021) §8.4 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 9]` content buffer at symbolic length, `unwind(12)`; the delegation is proved over that whole domain and inherits `DER-C-INT-1`) | `K enumerated::proofs::decode_delegates_to_integer` · `K enumerated::proofs::encode_delegates_to_integer` · watched-fail(`K enumerated::proofs::decode_delegates_to_integer`): made the shipped `decode_enumerated` add one to the delegated INTEGER value instead of returning it unchanged -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: r == crate::integer::decode_integer(&buf[..n])`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-ENUM-2` | ENUMERATED uses identifier UNIVERSAL 10 | X.680 (2021) Table 1 — UNIVERSAL 10 is ENUMERATED (external-standard). The rule is read off the standard's tag-assignment table, **not** off the unit test's name | evidenced | **weighted** · **test-only** — the tag is a constant checked by a concrete unit test; no harness asserts it. Witnesses one point, not a set | `T enumerated::tests` · watched-fail(`T enumerated::tests`): changed the shipped `enumerated::TAG` constant from 10 to 11 -> `tag_is_universal_10` FAILED and the run reported `test result: FAILED. 2 passed; 1 failed`; restoring returned it to `test result: ok. 3 passed; 0 failed`, observed 2026-08-26 |
| `DER-C-UTF8` | UTF8String content is well-formed UTF-8; ill-formed input is rejected with its position (§8.23) | X.690 (2021) §8.23 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 4]` content buffer at symbolic length, `unwind(6)`; the oracle is `core`'s own `str::from_utf8`, which is genuinely independent of the state under test) | `K utf8_string::proofs::validate_iff_std` · `K utf8_string::proofs::ill_formed_reports_position` · `K utf8_string::proofs::constructed_form_is_rejected` · watched-fail(`K utf8_string::proofs::validate_iff_std`): weakened the shipped `validate_utf8`'s continuation-byte test from `& 0xC0 == 0x80` to `& 0x80 == 0x80`, admitting `0xC0..=0xFF` as continuations -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: validate_utf8(..).is_ok() == core::str::from_utf8(..).is_ok()`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-STR-1` | PrintableString / IA5String / NumericString / VisibleString accept exactly their charset (§8.23, X.680) | X.690 (2021) §8.23 + X.680 (2021)'s restricted-character-string definitions (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 4]` content buffer at symbolic length, `unwind(6)`, per charset; a biconditional against an independently-formulated charset oracle, all four types) | `K restricted_string::proofs::validate_iff_all_in_charset_printable` (and `_ia5`, `_numeric`, `_visible`) · `K restricted_string::proofs::charset_exactly_matches_oracle_printable` (×4) · watched-fail(`K restricted_string::proofs::validate_iff_all_in_charset_printable`): added `*` to PrintableString's accepted punctuation set in the shipped `Charset::contains` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: validate_content(.., Charset::Printable).is_ok() == all_in`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-STR-2` | Those four types reject the constructed form and require their own tag | X.690 (2021) §10.2 + X.680 (2021) Table 1, tag identity (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(16)`) — *at the typed parser*. The label rests on the `accepted_identifier_*` harnesses, which are fully symbolic; the `constructed_form_*` and `wrong_tag_*` harnesses beside them are fixture-shaped and would be PROBE alone | `K restricted_string::proofs::accepted_identifier_is_canonical_printable` (×4 — rules out high-tag forms, wrong class/number **and** the constructed form) · `K restricted_string::proofs::constructed_form_is_rejected_printable` (×4) · watched-fail(`K restricted_string::proofs::accepted_identifier_is_canonical_printable`): narrowed the shipped `decode_restricted_string`'s constructed-form rejection to empty-valued TLVs only -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: buf[0] == Charset::Printable.identifier()`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-UTC` | UTCTime is exactly `YYMMDDHHMMSSZ` — 13 octets, mandatory seconds, `Z` terminator, field ranges (§11.8) | X.690 (2021) §11.8 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 14]` content buffer at symbolic length, `unwind(14)`; a biconditional against a separately-written canonical-form oracle) | `K utc_time::proofs::accepted_iff_canonical_oracle` · `K utc_time::proofs::not_zulu_is_classified` · `K utc_time::proofs::full_year_pivot_is_correct` · watched-fail(`K utc_time::proofs::accepted_iff_canonical_oracle`): widened the shipped `decode_utc_time`'s month range to `1..=13` -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_utc_time(..).is_ok() == is_canonical_der_utctime(..)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-GEN` | GeneralizedTime is `YYYYMMDDHHMMSS[.fff]Z` — mandatory seconds, `Z`, canonical fraction with no trailing zeros (§11.7) | X.690 (2021) §11.7 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 19]` content buffer at symbolic length, `unwind(20)`; a biconditional against a separately-written canonical-form oracle) | `K generalized_time::proofs::accepted_iff_canonical_oracle` · `K generalized_time::proofs::fraction_trailing_zero_is_classified` · `K generalized_time::proofs::bad_fraction_separator_is_classified` · watched-fail(`K generalized_time::proofs::accepted_iff_canonical_oracle`): widened the shipped `decode_generalized_time`'s hour range to `0..=24` -> the harness reported `VERIFICATION:- FAILED` on the accepted-iff-canonical biconditional; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-SEQ-1` | A SEQUENCE's children tile its content exactly — the walk consumes precisely the content bytes (§8.9) | X.690 (2021) §8.9 (external-standard) | evidenced | **weighted** · **CONTRACT** (unbounded — the Lean lid `decode_sequence_structure` is the only lid in the crate unbounded in **child count** as well as byte length; the Kani half that carries this row's witness is a symbolic 8-octet content buffer, `unwind(16)`). **Residual, stated:** the witness below is for the Kani recipe; the Lean half has not been watched to fail — see `DER-F-1b` | `K sequence::proofs::ok_implies_exact_tiling` · `N decode_sequence_structure` (`lean/SequenceProofs.lean`) · watched-fail(`K sequence::proofs::ok_implies_exact_tiling`): made the shipped `Elements` walk advance one octet past each child's own encoded length, so the children no longer tile the content -> the harness reported `VERIFICATION:- FAILED`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-SEQ-2` | The shipped SEQUENCE walk never over-reads, and each step advances by exactly the child's own encoded length | X.690 (2021) §8.9.1 (external-standard) — *"the complete encoding of one data value from each of the types … in the order of their definition"* is the advance-exactness half. The no-over-read half is a memory-safety property the standard does not speak to | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic 8-octet content buffer, `unwind(16)`; real-path, independent oracle — rewritten 2026-08-24, see §6.2) | `K sequence::proofs::no_over_read` · `R sequence::proofs::no_over_read` (check its two cover lines are satisfied) · watched-fail(`K sequence::proofs::no_over_read`): made the shipped `Elements` walk advance one octet past each child's own encoded length -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: new_off == off + expected_used`, **and its cover tally fell from 2 of 2 to 1 of 2**; restoring returned both to `SUCCESSFUL` and 2 of 2, observed 2026-08-26 |
| `DER-C-SEQ-3` | SEQUENCE is constructed and carries identifier `0x30` | X.690 (2021) §8.9.1 + X.680 (2021) Table 1 (UNIVERSAL 16) (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(16)`, for the canonicality harness; the `tag_correctness` harness beside it is a three-fixture check) | `K sequence::proofs::tag_correctness` · `K sequence::proofs::accepted_identifier_is_canonical_0x30` · watched-fail(`K sequence::proofs::accepted_identifier_is_canonical_0x30`): narrowed the shipped `decode_sequence_tlv`'s constructed-form requirement so a primitive-form empty SEQUENCE (`10 00`) is accepted -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: input[0] == 0x30`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26. **Recorded because it is the point of the exercise:** the same perturbation left `tag_correctness` GREEN — its `10 01 a` fixture has a non-empty body, so a fixture-shaped harness did not see a defect the symbolic one caught |
| `DER-C-SETOF-1` | SET OF members appear in ascending order of their **encodings** (§11.6) | X.690 (2021) §11.6 (external-standard) | **partial** | **weighted** · **PROBE** (bounded — `unwind(16)`; a biconditional, but only over **two fixed-shape 3-octet children** with symbolic content, and the comparator lemma is limited to slices of ≤ 3 bytes). Not established for arbitrary member encodings or counts | `K set_of::proofs::ordering_iff_oracle` · `K set_of::proofs::cmp_padded_matches_oracle` · `K set_of::proofs::unsorted_children_are_rejected` · watched-fail(`K set_of::proofs::ordering_iff_oracle`): inverted the shipped `decode_set_of`'s ordering test, so it rejects ascending members and accepts descending ones -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: accepted == ordered`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-SETOF-2` | Equal adjacent member encodings are accepted (SET **OF**, not SET) | X.690 (2021) §11.6 (external-standard) — ascending, not strictly ascending | evidenced | **weighted** · **PROBE** (bounded — `unwind(16)`, over a wholly concrete 6-byte fixture; it witnesses one point, not the rule) | `K set_of::proofs::duplicate_adjacent_encodings_are_accepted` · watched-fail(`K set_of::proofs::duplicate_adjacent_encodings_are_accepted`): tightened the shipped `decode_set_of` to strict ascent, so equal adjacent member encodings are rejected -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: decode_set_of(&content) == Ok(2)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-C-SETOF-3` | The shipped SET OF walk never over-reads | X.690 (2021) §8.12 (external-standard) — the member-tiling half; the no-over-read half is a memory-safety property with no clause | **partial** | **weighted** · **PROBE** (bounded — a symbolic 8-octet content buffer, `unwind(16)`) — bounded no-out-of-bounds-access plus an extensional postcondition; see §6.3 | `K set_of::proofs::no_over_read`. **Does not** show the shipped loop used the same per-child boundaries as the oracle, nor that its cursor never over-advances past the final read · watched-fail(`K set_of::proofs::no_over_read`): widened the per-member window in the shipped `decode_set_of` by one octet, so the walk reads one byte past the final child -> the harness reported `VERIFICATION:- FAILED` **and its cover tally fell from 2 of 2 to 1 of 2**; restoring returned both to `SUCCESSFUL` and 2 of 2, observed 2026-08-26 |
| `DER-C-SET` | General `SET` (§10.3) — DER ordering of a heterogeneous SET | X.690 (2021) §10.3 (external-standard) | **gap** | **weighted** · **out-of-scope** — weight attaches to the declaration, not to the code | `D DECISIONS.md` D13; `README.md` scope section. Not implemented, not claimed. |
| `DER-C-CTX` | `[n] EXPLICIT` context tagging (§8.14) | X.690 (2021) §8.14.2 (external-standard) | evidenced | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length with a symbolic expected tag number `n: u32`, `unwind(20)`) — panic-freedom only, which does not decide the tagging rule | `K context_tag::proofs::decode_explicit_context_never_panics` · watched-fail(`K context_tag::proofs::decode_explicit_context_never_panics`): dropped the first byte of the inner value in the shipped `decode_explicit_context` with an unchecked `[1..]` slice, which panics on an empty explicit-context value -> the harness reported `VERIFICATION:- FAILED`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26. **Also recorded:** replacing `decode_tlv`'s `checked_add` header/length overflow guard with a plain `+` left this harness GREEN — that guard is unreachable at a 16-octet bound, so this row's panic-freedom claim says nothing about it |
| `DER-C-CTX-IMP` | `[n] IMPLICIT` context tagging | X.690 (2021) §8.14 (external-standard) — the IMPLICIT form | **gap** | **weighted** · **out-of-scope** — weight attaches to the declaration, not to the code | `D PROOF_MANIFEST.md` §6.2 — *"only the explicit-context form is addressed"*. Consequence: X.509's deprecated `[1]`/`[2]` unique identifiers are **rejected**, not parsed (`DER-X-TBS-2`) |

### 5.3 X.509 / PKCS structural surface

**Read this block before trusting any row in it.** Every module here is proved **panic-free**, not
**conformant**: the harnesses are `*_never_panics`. Panic-freedom is a real and valuable safety
property — this is the layer a malformed certificate attacks — but it does **not** decide whether the
parser accepts exactly the RFC 5280 structures. On the rule axis, that makes these rows `partial`.

| id | structure (RFC 5280 unless noted) | clause source | status | strength | verify |
|---|---|---|---|---|---|
| `DER-X-ALGID` | `AlgorithmIdentifier` §4.1.1.2 — framing | RFC 5280 §4.1.1.2 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`; all three `Ok`-tail covers satisfied) — panic-freedom, which is a real safety property but does not decide the structural item | `K x509_algorithm_identifier::proofs::parse_algorithm_identifier_never_panics` · watched-fail(`K x509_algorithm_identifier::proofs::parse_algorithm_identifier_never_panics`): shifted the shipped `parse_algorithm_identifier`'s post-OID slice start by one (`&algo_content[oid_used + 1..]`), which indexes past the end when the OID fills the SEQUENCE content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-X-SPKI` | `SubjectPublicKeyInfo` §4.1.2.7 — framing | RFC 5280 §4.1.2.7 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`; the `Ok`-tail cover is satisfied) — panic-freedom, which is a real safety property but does not decide the structural item | `K x509_spki::proofs::parse_never_panics` · watched-fail(`K x509_spki::proofs::parse_never_panics`): shifted the shipped `parse_subject_public_key_info`'s post-AlgorithmIdentifier slice start by one, which indexes past the end when that field fills the content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-X-NAME` | `Name` / `RDNSequence` §4.1.2.4 — framing | RFC 5280 §4.1.2.4 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length; `unwind(12)` for the RDN lemma, `unwind(10)` for the outer walk, which stubs `validate_rdn`). The witnessed harness is the RDN lemma, and it asserts more than panic-freedom — it also bounds consumption, `2 <= used <= input.len()`. **Nothing witnesses the RDN parser's own accept path:** `validate_rdn_never_panics` has no cover at all, and its sibling stubs the function, so §6.4's gap stands | `K x509_name::proofs::validate_never_panics` (stubs `validate_rdn`) · `K x509_name::proofs::validate_rdn_never_panics` (**no cover at all**) · watched-fail(`K x509_name::proofs::validate_rdn_never_panics`): shifted the post-type-OID slice start by one in the shipped `validate_rdn`'s AttributeTypeAndValue walk, which indexes past the end when the OID fills the content -> the harness reported `VERIFICATION:- FAILED` after 9m55s of solving; restoring the source returned it to `SUCCESSFUL` in 9m03s, observed 2026-08-26. **The most expensive row in this ledger to falsify**, at roughly 15 GB of CBMC peak each way — which is itself the reason this layer's bounds are the smallest in the crate |
| `DER-X-VALID` | `Validity` §4.1.2.5 — framing | RFC 5280 §4.1.2.5 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`) — panic-freedom only, and its `Ok`-tail **cover is UNSATISFIED**: a genuine `Validity` needs ≥ 32 octets, so no 16-octet input reaches the tail (§6.4). **Measured consequence, 2026-08-26:** a perturbation *past* the notBefore field — shifting the post-notBefore slice by one — left this harness **GREEN**, because that line is unreachable at this bound. The witness below is a perturbation the bound does reach, and this row's panic-freedom claim covers only the prefix of `parse_validity` that a 16-octet input can execute | `R x509_validity::proofs::parse_never_panics` (`0 of 1 cover`) · `K x509_validity::proofs::parse_never_panics` · `K x509_validity::proofs::parse_validity_ok_path_witnessed` (companion witness, no stubs) · watched-fail(`K x509_validity::proofs::parse_never_panics`): deleted the shipped `parse_validity`'s empty-content guard and sliced the notBefore field from offset 1, which panics on the empty SEQUENCE `30 00` -> the harness reported `VERIFICATION:- FAILED`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-X-EXT-1` | `Extension` / `Extensions` §4.1.2.9 — framing | RFC 5280 §4.1.2.9 (external-standard) | partial | **weighted** · **PROBE** (bounded — the symbolic harness is a `[u8; 13]` input at symbolic length, `unwind(12)`; the witnessed companion runs a concrete 16-octet two-`Extension` fixture). **Cover UNSATISFIED on the symbolic harness** — see §6.4. **Read the witness below before reading this row's `expect`:** the companion harness asserts *nothing but a `kani::cover`*, so its **verdict cannot report this claim false** — Kani calls an unsatisfiable cover `SUCCESSFUL` and `check.sh` does not fail on it (§7, **E-6**). For this row, green means `VERIFICATION:- SUCCESSFUL` **and** `1 of 1 cover properties satisfied`; the tally is the answer, not the exit status | `R x509_extension::proofs::validate_extensions_never_panics` (`0 of 1 cover`) · `K x509_extension::proofs::validate_extensions_ok_path_witnessed` · watched-fail(`K x509_extension::proofs::validate_extensions_ok_path_witnessed`): shifted the post-extnID slice start by one in the shipped `parse_extension`, so the walk can index past the end of an Extension's content -> the verdict stayed `VERIFICATION:- SUCCESSFUL`, exactly as E-6 predicts, **and the cover tally fell from `1 of 1` to `0 of 1`** — the concrete valid fixture stopped reaching the `Ok` tail. Restoring the source returned it to `1 of 1`. So the recipe does discriminate, through its tally rather than its exit code, observed 2026-08-26 |
| `DER-X-EXT-2` | DER `DEFAULT` omission: a `critical` field encoding `FALSE` must be absent (§11.5) | X.690 (2021) §11.5 + RFC 5280 §4.1.2.9 (`critical BOOLEAN DEFAULT FALSE`) (external-standard) | evidenced | **weighted** · **test-only** — one concrete unit test. `parse_extension_never_panics` calls the parser and covers `Ok`; it never asserts this rule | `T x509_extension::tests::rejects_critical_present_but_false` · watched-fail(`T x509_extension::tests::rejects_critical_present_but_false`): guarded the shipped `parse_extension`'s present-and-FALSE rejection behind an unreachable condition, so a canonically-encoded `critical = FALSE` is accepted -> the test FAILED and the run reported `test result: FAILED. 0 passed; 1 failed`; restoring returned it to `test result: ok. 1 passed; 0 failed`, observed 2026-08-26 |
| `DER-X-EXT-3` | **Extension *contents* (basicConstraints, keyUsage, SAN, …)** | RFC 5280 §4.2.1 — the standard certificate extensions (external-standard) | **gap** | **weighted** · **not-covered** — `extnValue` is an opaque OCTET STRING; `critical` is peeked, not acted on | `E 'basic_?constraints' @ der-verified/src/x509_extension.rs` — code lines of the implementation region only -> **0**; the same scoped grep for `key_?usage` and for `subject_?alt`, run separately, also returns 0, so no standard extension is named in the code at all. positive-control(`E 'basic_?constraints' @ der-verified/src/x509_extension.rs`): ran the same scoped, comment-filtered grep for `extn_value`, which the module really does handle -> it returned 3, and keeping comment lines in raises the three claim patterns' combined count from 0 to 4, so both the pattern class and the comment filter are doing real work, observed 2026-08-26. Read alongside `D PROOF_MANIFEST.md` §6.2 — *"extension contents are never interpreted"* |
| `DER-X-TBS-1` | `TBSCertificate` §4.1 — the full field skeleton (version, serial, signature, issuer, validity, subject, SPKI, extensions) | RFC 5280 §4.1 — the `TBSCertificate` ASN.1 definition (external-standard) | partial | **weighted** · **PROBE** (bounded — the symbolic harness is a `[u8; 10]` input, `unwind(12)`, with 2 stubs; the witnessed companion runs one concrete 135-octet valid v1 specimen with **3 stubs**, so it witnesses the glue, not the parser). **Cover UNSATISFIED, stub-mediated** — see §6.4. **As with `DER-X-EXT-1`, green here is the tally and not the exit status** (§7, **E-6**): the companion asserts nothing but a `kani::cover`. Sharper still on this row — the companion runs **one** input, so only a perturbation on *that specimen's* path can ever be seen. The first perturbation tried, removing the missing-serialNumber guard, moved **neither** verdict nor tally, because the specimen has a serialNumber and never reaches that guard | `R x509_tbs_certificate::proofs::parse_tbs_certificate_never_panics` (`0 of 1 cover`, 2 stubs) · `K x509_tbs_certificate::proofs::parse_tbs_certificate_ok_path_witnessed` (**3 stubs** — glue reachability only) · watched-fail(`K x509_tbs_certificate::proofs::parse_tbs_certificate_ok_path_witnessed`): broke the shipped `parse_tbs_certificate`'s strict-tiling rule, requiring exactly one byte to remain after the last field instead of none -> the verdict stayed `VERIFICATION:- SUCCESSFUL` and **the cover tally fell from `1 of 1` to `0 of 1`** — the valid specimen stopped reaching the `Ok` tail. Restoring returned it to `1 of 1`, observed 2026-08-26 |
| `DER-X-TBS-2` | DER `DEFAULT` omission for `version`: a present `[0]` encoding v1 is rejected (§11.5) | X.690 (2021) §11.5 + RFC 5280 §4.1.2.1 (`version … DEFAULT v1`) (external-standard) | evidenced | **weighted** · **test-only** — one concrete unit test; no harness asserts it | `T x509_tbs_certificate::tests` — `TbsCertificateError::VersionMustBeOmitted` · watched-fail(`T x509_tbs_certificate::tests`): moved the shipped `parse_tbs_certificate`'s DEFAULT-v1 rejection off version 0 onto version 9 -> `rejects_present_version_v1_must_be_omitted` FAILED and the run reported `test result: FAILED. 9 passed; 1 failed`; restoring returned it to `test result: ok. 10 passed; 0 failed`, observed 2026-08-26 |
| `DER-X-CERT` | `Certificate` §4.1 — outermost composition | RFC 5280 §4.1 — the `Certificate` ASN.1 definition (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 12]` input at symbolic length, `unwind(12)`, with `parse_tbs_certificate` stubbed; the `Ok`-tail cover **is** satisfied here, unlike its three siblings in §6.4) — panic-freedom, which does not decide the composition. See `DER-X-BOUND`: a real certificate is ~170 octets against this 12 | `K x509_certificate::proofs::parse_certificate_never_panics` · watched-fail(`K x509_certificate::proofs::parse_certificate_never_panics`): widened the tbsCertificate span in the shipped `parse_certificate` by one octet, which indexes past the end when the TBS field fills the outer content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice while its cover stayed `1 of 1`; restoring the source returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-X-BOUND` | **Panic-freedom at realistic input sizes** | none — no external clause governs this item. It is a claim about the *reach* of this crate's own proofs at realistic input sizes, not about a specification requirement, and `none` is reserved to mean unweightable by design (`core.md` W2.3) | **partial** | ⚠ **UNWEIGHTED** · **inspection-argued** — doubly unweightable: the grade has no deciding machinery, and the clause source is one of the two tokens reserved to mean unweightable | `D PROOF_MANIFEST.md` §8.1 — `x509_certificate` panic-freedom is proved at **≤12 bytes**; a real certificate is ~170 bytes. `rsa_private_key` at **≤20 bytes** vs ~317. Real-size panic-freedom *"rests on an un-machine-checked compositional argument"*. |
| `DER-K-PKCS8` | PKCS#8 `PrivateKeyInfo` (RFC 5208 §5) | RFC 5208 §5 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`; a separate 48-octet concrete `Ok`-path witness sits beside it) — panic-freedom, which is a real safety property but does not decide the structural item | `K pkcs8::proofs::parse_never_panics` · watched-fail(`K pkcs8::proofs::parse_never_panics`): shifted the shipped `pkcs8::parse`'s post-version slice start by one, which indexes past the end when the version field fills the content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-K-EPKI` | `EncryptedPrivateKeyInfo` (RFC 5958 §3) | RFC 5958 §3 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`) — panic-freedom, which is a real safety property but does not decide the structural item | `K encrypted_private_key_info::proofs::parse_never_panics` · watched-fail(`K encrypted_private_key_info::proofs::parse_never_panics`): shifted the shipped parser's post-encryptionAlgorithm slice start by one, which indexes past the end when that field fills the content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-K-RSAPUB` | `RSAPublicKey` (RFC 8017 §A.1.1) | RFC 8017 §A.1.1 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`) — panic-freedom, which is a real safety property but does not decide the structural item | `K rsa_public_key::proofs::parse_strict_never_panics` · watched-fail(`K rsa_public_key::proofs::parse_strict_never_panics`): shifted the shipped parser's post-modulus slice start by one, which indexes past the end when the modulus fills the SEQUENCE content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-K-RSAPRIV` | `RSAPrivateKey` (RFC 8017 §A.1.2) | RFC 8017 §A.1.2 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 20]` input at symbolic length, `unwind(20)`, with `validate_other_prime_infos` stubbed (that sub-parser has its own harness)) — panic-freedom, which is a real safety property but does not decide the structural item. See `DER-X-BOUND`: a real key is ~317 octets | `K rsa_private_key::proofs::parse_never_panics` · watched-fail(`K rsa_private_key::proofs::parse_never_panics`): shifted the shipped `rsa_private_key::parse`'s post-version slice start by one, which indexes past the end when the version field fills the content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-K-ECPRIV` | `ECPrivateKey` (RFC 5915 §3) | RFC 5915 §3 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`) — panic-freedom, which is a real safety property but does not decide the structural item | `K ec_private_key::proofs::parse_never_panics` · watched-fail(`K ec_private_key::proofs::parse_never_panics`): shifted the shipped `ec_private_key::parse`'s post-version slice start by one, which indexes past the end when the version field fills the content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-K-ECDSASIG` | `ECDSA-Sig-Value` (RFC 3279 §2.2.3) | RFC 3279 §2.2.3 (external-standard) | partial | **weighted** · **PROBE** (bounded — a symbolic `[u8; 16]` input at symbolic length, `unwind(20)`) — panic-freedom, which is a real safety property but does not decide the structural item | `K ecdsa_sig_value::proofs::parse_strict_never_panics` · watched-fail(`K ecdsa_sig_value::proofs::parse_strict_never_panics`): shifted the shipped parser's post-`r` slice start by one, which indexes past the end when `r` fills the SEQUENCE content -> the harness reported `VERIFICATION:- FAILED` on the out-of-bounds slice; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-X-L4` | An unbounded (Lean) lid over **any** X.509 structural module | `gates/map_declared.txt` row `x509_structural_lid` → `DER-REMAINING-WORK.md` §3 (spec-document) — the item is the crate's own declared work surface, so its text has an in-tree source and no external one | **gap** | **weighted** · **not-covered** — all seven `x509_*` modules are Kani-only | `A x509 @ lean/*.lean` — `grep -ric x509 lean/*.lean` returns **0** for every one of the twelve lid and extraction files. positive-control(`A x509 @ lean/*.lean`): ran the identical command for `Tlv`, a codec that *does* have a lid -> six of the same twelve files came back non-zero, 5 to 224 hits each, so the command and the corpus can both produce a large non-zero and the zero above is about X.509 rather than about the grep, observed 2026-08-26. Cross-check `D gates/map_declared.txt` row `x509_structural_lid` |

### 5.4 RFC 5280 profile rules

The `profile` module is the crate's only *semantic* layer, and — unusually for this crate — its rules
are proved as **biconditionals**, which is stronger than the structural layer beneath it.

| id | rule | clause source | status | strength | verify |
|---|---|---|---|---|---|
| `DER-P-1` | The inner `signature` and outer `signatureAlgorithm` must be identical (§4.1.1.2) | RFC 5280 §4.1.1.2 (external-standard) | **partial** | **weighted** · **PROBE** (bounded — `unwind(4)`; a biconditional, but **monomorphic in slice length**: the OIDs are always a symbolic `[u8; 2]` and the parameters a fixed 1-byte slice). Since this rule is *about* the algorithm identifiers, that bound is on the rule itself, not incidental | `K profile::proofs::rule1_mismatch_iff_algorithms_differ` · watched-fail(`K profile::proofs::rule1_mismatch_iff_algorithms_differ`): narrowed the shipped `validate_profile`'s rule-1 equality test to the `parameters` field, dropping the algorithm-OID comparison -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: (r == Err(ProfileError::SignatureAlgorithmMismatch)) == (a != b)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-P-2` | Extensions may appear only in a v3 certificate (§4.1.2.1, §4.1.2.9) | RFC 5280 §4.1.2.1, §4.1.2.9 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — `unwind(4)`, but complete over the rule's **full** domain: a symbolic `version: u8` across all 256 values, not just 0/1/2, and a symbolic extensions-present flag) | `K profile::proofs::rule2_requires_v3_iff_extensions_present_and_not_v3` · watched-fail(`K profile::proofs::rule2_requires_v3_iff_extensions_present_and_not_v3`): changed the shipped `validate_profile`'s rule-2 version test from `!= 2` to `> 2`, so v1 and v2 certificates could carry extensions -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: (r == Err(ProfileError::ExtensionsRequireV3)) == (has_ext && version != 2)`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-P-3` | Dates through 2049 use UTCTime; 2050 onward use GeneralizedTime (§4.1.2.5) | RFC 5280 §4.1.2.5.1, §4.1.2.5.2 (external-standard) | evidenced | **weighted** · **CONTRACT** (bounded — `unwind(4)`, over a symbolic `u16` year and a symbolic encoding choice for both `notBefore` and `notAfter`; a biconditional, plus a proof that UTCTime *cannot* denote ≥ 2050) | `K profile::proofs::rule3_generalized_too_early_iff_year_le_2049` · `K profile::proofs::utc_time_can_never_denote_2050_or_later` · watched-fail(`K profile::proofs::rule3_generalized_too_early_iff_year_le_2049`): moved the shipped `check_time_encoding_year`'s GeneralizedTime cut-off from `year <= 2049` to `year < 2049` -> the harness reported `VERIFICATION:- FAILED` on both the notBefore and notAfter assertions; restoring returned it to `SUCCESSFUL`, observed 2026-08-26 |
| `DER-P-4` | Error precedence follows declaration order (determinism of the reported violation) | `profile.rs::validate_profile` doc comment — *"the first violated rule's `ProfileError` (checked in the order the variants are declared)"* (doc-comment). **RFC 5280 mandates no precedence**, so this is the crate's own determinism promise and the clause is its doc comment, not the RFC | evidenced | **weighted** · **CONTRACT** (bounded — `unwind(4)`, over all four violations independently symbolic at once; the harness's own cover witnesses the all-four-violated case) | `K profile::proofs::error_precedence_follows_declaration_order` · watched-fail(`K profile::proofs::error_precedence_follows_declaration_order`): swapped the notBefore and notAfter checks in the shipped `validate_profile`, so the reported violation no longer follows declaration order -> the harness reported `VERIFICATION:- FAILED`, `assertion failed: r == expected`; restoring returned it to `SUCCESSFUL`, observed 2026-08-26. **This row is why recipe `E` was rewritten** (§4): error precedence is an enforced, contract-graded rule with no `ProfileError` variant of its own, so enumerating that enum cannot decide what the profile layer checks |
| `DER-P-5` | Basic constraints (§4.2.1.9) | RFC 5280 §4.2.1.9 (external-standard) | **gap** | **weighted** · **not-covered** — in scope for RFC 5280 and decided by nothing in this crate | `E 'basic_?constraints' @ der-verified/src/profile.rs` — implementation region only (`sed -n '1,/^mod tests/p'`), case-insensitive -> **0**. positive-control(`E 'basic_?constraints' @ der-verified/src/profile.rs`): ran the same scoped grep for `ExtensionsRequireV3`, a rule this module really does enforce -> it returned 6, so the command and the scope can produce a non-zero, observed 2026-08-26. **Control 2 also holds here:** dropping the scope returns 14 — the `mod tests` fixtures name `basicConstraints` — so the scope is demonstrably what produced the zero. **This is the row whose earlier unscoped grep was simply wrong; see §7, E-3**. Cross-check `D gates/map_declared.txt` |
| `DER-P-6` | Key usage (§4.2.1.3) | RFC 5280 §4.2.1.3 (external-standard) | **gap** | **weighted** · **not-covered** — in scope for RFC 5280 and decided by nothing in this crate | `E 'key_?usage' @ der-verified/src/profile.rs` — implementation region only (`sed -n '1,/^mod tests/p'`), case-insensitive -> **0**. positive-control(`E 'key_?usage' @ der-verified/src/profile.rs`): ran the same scoped grep for `ExtensionsRequireV3`, a rule this module really does enforce -> it returned 6, so the command and the scope can produce a non-zero, observed 2026-08-26. **Control 2 is NOT available here, and `COVERAGE.md` says otherwise:** unscoped, this pattern returns 0 over `profile.rs` as well, so removing the scope changes nothing and cannot show the scope did any work. The zero is still right; the row carries control 1 only. Recorded in §7 as **E-4**. Cross-check `D gates/map_declared.txt` |
| `DER-P-7` | Name constraints (§4.2.1.10) | RFC 5280 §4.2.1.10 (external-standard) | **gap** | **weighted** · **not-covered** — in scope for RFC 5280 and decided by nothing in this crate | `E 'name_?constraint' @ der-verified/src/profile.rs` — implementation region only (`sed -n '1,/^mod tests/p'`), case-insensitive -> **0**. positive-control(`E 'name_?constraint' @ der-verified/src/profile.rs`): ran the same scoped grep for `ExtensionsRequireV3`, a rule this module really does enforce -> it returned 6, so the command and the scope can produce a non-zero, observed 2026-08-26. **Control 2 is NOT available here either** — unscoped, the pattern returns 0 over `profile.rs` too. Control 1 only; see §7, **E-4**. Cross-check `D gates/map_declared.txt` |
| `DER-P-8` | Validity against a clock (§4.1.2.5) | RFC 5280 §4.1.2.5 (external-standard) | **gap** | **weighted** · **not-covered** — the crate is heap-free and clock-free by design, so it cannot compare a certificate against "now" | `A '::now(' @ der-verified/src/` — `grep -r '::now(' der-verified/src/` -> **0** (likewise `SystemTime` and `Instant`, run separately: no file matches either). positive-control(`A '::now(' @ der-verified/src/`): ran `grep -c 'Time' der-verified/src/x509_validity.rs` -> 115 — the crate has UTCTime and GeneralizedTime *values* in abundance and no *clock*, which is exactly the distinction this row records, observed 2026-08-26. Cross-check `D gates/map_declared.txt` row `validity_against_clock` |
| `DER-P-9` | Certificate-path / trust validation; signature and crypto verification | RFC 5280 §6 — certification-path validation (external-standard) | **gap** | **weighted** · **out-of-scope** — weight attaches to the declaration, not to the code | `D README.md` scope section — *"Out of scope (not implemented, not proven)"*. `gates/map_declared.txt` rows `path_validation`, `crypto_verification`. |
| `DER-P-10` | String canonicalisation / name-comparison rules; OID semantics | RFC 5280 §7 — processing rules for internationalized names (external-standard) | **gap** | **weighted** · **out-of-scope** — weight attaches to the declaration, not to the code | `D PROOF_MANIFEST.md` §6.2 |

### 5.5 Crate-wide safety and hygiene

| id | claim | clause source | status | strength | verify |
|---|---|---|---|---|---|
| `DER-S-1` | No `unsafe` anywhere | `README.md` — *"The crate is `#![forbid(unsafe_code)]`"* (spec-document) | evidenced | **weighted** · **mechanical** (compiler-enforced; the manifest's inventory independently derives 0 `unsafe` blocks) | `M grep -rn forbid der-verified/src/lib.rs` — exactly one line, `der-verified/src/lib.rs:172:#![forbid(unsafe_code)]`, and exit 0. *The pattern is the bare word deliberately: a `<recipe-ref>` may not contain parentheses, because §4.1's witness binding is delimited by them, and a recipe a witness cannot name is a recipe nothing can be watched to falsify.* · watched-fail(`M grep -rn forbid der-verified/src/lib.rs`): replaced the shipped crate attribute with `#![deny(unsafe_op_in_unsafe_fn)]`, which forbids nothing -> the recipe returned no output and exit 1; restoring the attribute returned the single `lib.rs:172` match and exit 0, observed 2026-08-26 |
| `DER-S-2` | **No harness triggers a panic within that harness's own symbolic domain, assumptions, stubs and unwind bound.** *Item narrowed 2026-08-26 to `COVERAGE.md`'s wording: the previous phrasing, "no panic on malformed input … for every harnessed entry point", reads as a claim about entry points rather than about harnesses, which is a wider claim than the evidence* | `PROOF_MANIFEST.md` §3.1 (the L3 floor's panic-freedom claim) + §8.1 (each harness's declared bound) (spec-document) — no external standard states it | evidenced | ⚠ **UNWEIGHTED** · **CONTRACT** (bounded — each harness's own declared symbolic buffer and `unwind`, enumerated in `PROOF_MANIFEST.md` §8.1). The *item here is panic-freedom itself*, decided directly over symbolic input, so the grade is relative to this item; it is `PROBE` only when a panic-freedom proof is offered for a **different** item, which is exactly the X.509 rows' situation. **Weight refused for want of a witness:** this row's recipe is the whole-gate run `G` (~71 min, 203 harnesses) or a per-harness log read `R`, and the P2 pass of 2026-08-26 ran single-harness mutations. Watching `G` fail is a real and affordable obligation — it is simply not one a night of second-long runs discharges. See `DER-X-BOUND` for what the bounds cost at realistic input sizes | `G`, or `R` per harness |
| `DER-S-3` | Every public entry point is named by a harness | `PROOF_MANIFEST.md` §4, *"Entry points — covered, and not covered"* — the hand-written framing, not the generated table it introduces (spec-document) | **partial** | **weighted** · **mechanical** — 84 public entry points; **73 harnessed, 11 not**. The 11 (`PROOF_MANIFEST.md` §4.1): `generalized_time::require_no_fraction`, `utf8_string::decode_utf8_str`, and nine in `restricted_string` — **eight per-type wrappers** over a harnessed generic core (`decode_`/`encode_..._into` for printable/ia5/numeric/visible) **plus `Charset::tag_number`**, which is not a wrapper | `M python3 gates/gen_proof_manifest.py --check` — the gate that holds those figures to the source; re-derive them with `--json` · watched-fail(`M python3 gates/gen_proof_manifest.py --check`): seeded the generated public-entry-point count in `PROOF_MANIFEST.md` from 84 to 85, a drift of exactly the kind this row's figures would suffer -> the gate exited 1 and printed the offending line as a diff against the source-derived value; restoring the manifest returned `proof-manifest gate: PASS` and exit 0, observed 2026-08-26 |
| `DER-S-4` | The documentation's counts match the source | `DOCS-SYNC.md` — *"any code/proof/feature change MUST be accompanied by a docs-sync pass"*, and *"never invent a number"* (spec-document) | evidenced | **weighted** · **mechanical** — each gate has its own self-test, run first, in `check.sh` | `M python3 gates/gen_proof_manifest.py --check` (and `python3 gates/gen_verification_map.py --check` beside it) · watched-fail(`M python3 gates/gen_proof_manifest.py --check`): seeded the generated harness count in `PROOF_MANIFEST.md` from 203 to 204 -> the gate exited 1 and printed the drift as a diff, naming the fix as `--write` and warning against running it if the source did not change; restoring the manifest returned `proof-manifest gate: PASS (generated regions + 8 guarded count-claims current)` and exit 0, observed 2026-08-26 |
| `DER-S-5a` | The Lean lids contain no `sorry` | `PROOF_MANIFEST.md` §3.2 — *"All L4 proofs are `sorry`-free, and that is a gate, not an eyeball check"* (spec-document) | evidenced | ⚠ **UNWEIGHTED** · **mechanical** — `check_lean.sh` fails closed on `sorryAx` or a `declaration uses 'sorry'` warning, and **was negative-tested by injecting one**. That injection is exactly the seeded-bad fixture §4.1 asks of a `mechanical` row, but it was done on another day by another hand and is not recorded here in the structured form, so this row is refused weight rather than credited with someone else's control. Re-running it needs the Aeneas/Charon/Lean stack, which the 2026-08-26 pass deliberately did not touch | `N` — `check_lean.sh` |
| `DER-S-5b` | The lids assume no axiom about this crate's own code (13 declared axioms, all specs for upstream `core` primitives) | `ASSUMPTIONS.md` A6 and its header — *"no lid declares an axiom asserting a property of `der-verified`'s own functions"* (spec-document) | evidenced | ⚠ **UNWEIGHTED** · **inspection-argued** — never weight-eligible: nothing *mechanically* keeps a crate-code assumption out of a future lid, so this property is reviewed, not gated, and the format declines to vouch for it | `D evidence/AXIOM-AUDIT-2026-08-18.md` |

---

## 6. The five things a consumer must not miss

### 6.1 Framing acceptance is **not** DER validity (`DER-F-8`, `DER-F-9`)

> **Now four rows, not two (2026-08-26).** *"Decided at the opt-in entry point; not covered at
> `decode_tlv`"* was being carried in a single cell, and a cell holding two claims lets a reader take
> whichever half they prefer — which, on exactly this pair of rules, is the misreading this whole
> section exists to prevent. The decided half is `DER-F-8` / `DER-F-9`; the undecided half at the
> default framing entry point is `DER-F-8-TLV` / `DER-F-9-TLV`, each with its own status, its own
> grade and its own executed absence check. `DER-C-BITS-4` was split the same way, and the
> standards-transcription sub-claim that used to live inside `DER-F-8`'s prose is now `DER-F-8b`.
> Nothing about the crate changed; what changed is that the reader can no longer land on the
> reassuring half by accident.

> **UPDATED 2026-08-25 — the two rules are now decided, but NOT where you are about to assume.**
> A new module, `identifier_form`, decides both (`DECISIONS.md` D34). `tlv::decode_tlv`,
> `tlv::decode_tlv_strict`, `tag::decode_tag` and `sequence`'s child walk are **unchanged** and
> still accept every input in this section — deliberately, because recursive parsing depends on a
> permissive framing reader. So the rules are enforced for callers who switch to
> `identifier_form::decode_tlv_form_checked` / `decode_tlv_form_checked_strict`, and for nobody else. **The paragraph
> below is still true of the framing layer, which is what most callers use.** Whether to wire the
> check into `decode_tlv_strict` is open (`DER-REMAINING-WORK.md` R3), as is recursion into the
> children of a constructed TLV (R4) — the new module decides one identifier, not a tree.
>
> **`decode_tlv_form_checked` is not a DER validator, and its name was changed to stop implying it
> was.** It decides framing plus one identifier's *form*; it never reads content octets, so it
> accepts `01 01 01` (BOOLEAN `true` must be `0xFF`), `02 02 00 01` (non-minimal INTEGER) and
> `05 01 00` (NULL must be empty). Content canonicality stays with the per-type codecs. The first
> version of this work shipped as `decode_tlv_der` with docs saying "the bytes must be valid DER";
> a review seat caught it before publication and the three counterexamples are now pinned by a
> harness and a test.
>
> **The harnesses behind these two rows are mutation-controlled, and the controls found a real
> miss.** `evidence/MUTATION-CONTROLS-2026-08-25-identifier-form.md` records two rounds. Round 2
> (M4–M6) was **preregistered** — predictions written to `PREREG-mutations-v2.md`, sha256
> `6da2284717…`, locked before the runs — and all three matched *harness-for-harness*, not merely in
> count. The one that matters is **M6**: reverting the `31..=36` arm (the high-tag universal types
> DATE, TIME-OF-DAY, DATE-TIME, DURATION, OID-IRI, RELATIVE-OID-IRI) turned four harnesses red, but
> `rejects_every_disclosed_illegal_identifier` **survived** — every specimen it pins is a low tag
> number ≤ 30, so no fixture harness in the pre-review set could reach the high-tag form. That is
> exactly why a constructed DATE (`3F 1F 00`) was accepted by the first version of this module, and
> exactly why `high_tag_universal_types_are_form_checked` had to be added. M6 is the evidence that
> the new harness is not decorative. M5 covers the direction the others cannot — corrupting the
> *oracle* while leaving the implementation untouched — and is caught only by `oracle_is_well_formed`,
> whose own limit is stated there: it checks the masks' *shape*, never their *content*.
>
> Two labelling cautions a consumer should carry into the rows above. First, the four
> domain-complete theorems compare the shipped `match` against a bitmask oracle **written by the
> same author**: they establish that the two encodings of the table agree on all 2^32 tag numbers —
> exactly what a transcription slip would violate — and **not** that the table agrees with X.680,
> which stays inspection-argued per-arm and spot-checked by concrete tests. Second, the two
> *composition* harnesses (`decode_tlv_form_checked_is_decode_tlv_refined_by_the_rule`,
> `decode_tlv_form_checked_strict_requires_full_consumption`) are stated relative to the rule and survived
> every mutation that broke it; they witness the composition, not the rule's content.

`tlv::decode_tlv` returning `Ok` means *"these bytes are a well-formed TLV"*, **not** *"these bytes are
valid DER"*. Two X.690 rules were, until 2026-08-25, enforced in **no verified layer of this crate**,
and are still enforced in none of the framing layers below:

- constructed encodings of primitive-only universal types are accepted — repro `21 00` (BOOLEAN),
  `26 01 39` (OBJECT IDENTIFIER), `2C 01 01` (UTF8String), `33 01 00` (PrintableString);
- the reserved EOC identifier `00 00` is accepted.

This was found by **differential fuzzing against an independent implementation** and is disclosed at
`PROOF_MANIFEST.md` §6.3. Nothing in the manifest was falsified by it — it is a scope gap, not a bug.
Where a *typed* parser exists it does check its own tag and form (`octet_string`, `restricted_string`,
`utf8_string`, the `pkcs8`/`x509_*` parsers), but that is a property of those call sites, not of the
framing layer. **A generic walk over untrusted bytes will accept the inputs above.**

*Self-verify (recipe A).* There is no negative harness to run, so verify the absence — a bare
`grep constructed` on `tag.rs`/`tlv.rs` returns **many** matches (the parsed `constructed`
field itself, `tag.rs:117`), so it verifies nothing. Grep for a *rejection decision* instead:

```sh
grep -n 'Constructed' der-verified/src/tag.rs der-verified/src/tlv.rs      # → empty
grep -n 'Constructed' der-verified/src/octet_string.rs                     # positive control → hits
grep -n 'MustBePrimitive' der-verified/src/identifier_form.rs              # → hits (where it IS decided)
```

The framing modules have no `Constructed` error variant at all; `octet_string.rs:42` defines one and
`octet_string.rs:61` acts on it. That contrast *is* the residual, and it is **unchanged** by the
2026-08-25 work — which is the point of the third grep: the rule now lives in `identifier_form`, and
the first grep still returns empty, so the framing layer still does not decide it. Then read §6.3's
table.

### 6.2 `sequence::no_over_read` was proving a **copy** until 2026-08-24 (`DER-C-SEQ-2`)

Until commit `0e327b7`, both `no_over_read` harnesses ran a *duplicated* `decode_tlv` walk and never
entered the shipped code — a textbook "proving a copy". A structural review caught it; the fix drives
the shipped `Elements` iterator and computes the expectation from a **separate** one-step decode at an
offset the harness carries itself. A first draft of the fix derived the offset from the iterator's own
cursor, which is self-referential and would have let a mis-advance survive; that draft was caught in
review too. The row above reflects the fixed version. Rationale: `DECISIONS.md` D33.

**Why this matters to a consumer:** none of the crate's gates would have caught it. The manifest gate
counts harnesses, bounds, stubs and covers — and none of those numbers move when a harness verifies a
copy of the shipped walk. A green gate is not a claim that the harnesses point at shipped code.

### 6.3 `set_of::no_over_read` is deliberately weaker than its sibling (`DER-C-SETOF-3`)

The asymmetry is in the *shipped code*, not in effort spent, and the crate states it in the docstring,
in `PROOF_MANIFEST.md` §8.3, and in `DER-REMAINING-WORK.md` R1:

| | drives | gets |
|---|---|---|
| `sequence::no_over_read` | `Elements` — the cursor is an observable field | per-child: the shipped advance is pinned to an independent oracle |
| `set_of::no_over_read` | `decode_set_of` — the cursor is a local, the output is a count | bounded no-out-of-bounds-access **+ an extensional `Ok(k)` tiling postcondition** |

`set_of` does **not** show the shipped loop used the same per-child boundaries as the oracle's re-walk,
and a terminal over-advance past the final read would neither panic nor change `k`. The fix requires
refactoring shipped code onto `sequence::Elements` — a behavioural change, deliberately not bundled
into a proof-integrity fix.

### 6.4 Three harnesses cannot witness their own happy path (`DER-X-VALID`, `DER-X-EXT-1`, `DER-X-TBS-1`)

Three harnesses report `0 of 1 cover properties satisfied`, and `check.sh` **does not fail on that**:

| harness | buffer | why unsatisfiable | companion witness | witness uses stubs? |
|---|---|---|---|---|
| `x509_validity::parse_never_panics` | `[u8; 16]` | a minimal `Validity` needs ~32 octets | `parse_validity_ok_path_witnessed` | no |
| `x509_extension::validate_extensions_never_panics` | `[u8; 13]` | two minimal `Extension`s need 16 | `validate_extensions_ok_path_witnessed` | no |
| `x509_tbs_certificate::parse_tbs_certificate_never_panics` | `[u8; 10]` | a minimal TBS body is far larger | `parse_tbs_certificate_ok_path_witnessed` | **yes — glue reachability only** |

The cause is arithmetic, not a cover-authoring error: the buffer is too small for a well-formed object
to exist inside it. So each of those three panic-freedom proofs ranges over an input space in which
**every input is rejected early**. They are honest proofs of "no panic on garbage"; they are not
evidence that the accept path is safe. The companion witnesses supply reachability at concrete
fixtures — and the `x509_tbs_certificate` one does so with three stubs, so it witnesses the glue, not
the parser. Separately, `x509_name::validate_rdn_never_panics` has **no cover at all**, and its sibling
stubs `validate_rdn`, so nothing witnesses the RDN parser's own accept path.

`R2` in `DER-REMAINING-WORK.md` records a further open residual: seven structural harnesses were widened
to symbolic input length in 2026-08-23; only the two rewritten by D33 got covers. **The other five have
none, so nothing witnesses that their widened loops iterate at all.** A second-model review asked for
those covers before publish; the maintainer disclosed rather than fixed, and recorded it as a
judgement call. The covers are owed.

> **What the 2026-08-26 mutation pass added to this section, and it cuts both ways.**
>
> - **The companion witnesses cannot report a claim false through their verdict** (§7, **E-6**).
>   `parse_tbs_certificate_ok_path_witnessed` and `validate_extensions_ok_path_witnessed` contain
>   nothing but a `kani::cover`. A perturbation that stops the parse reaching its `Ok` tail leaves
>   `VERIFICATION:- SUCCESSFUL` and moves only the tally, so for those two the **cover line is the
>   recipe's answer** and the exit status is not. Their rows' `expect` says so.
> - **The unsatisfiable covers are not the only thing the small buffers cost.** Perturbing
>   `parse_validity` *past* its notBefore field — a genuine out-of-bounds read on a real input — left
>   `x509_validity::parse_never_panics` **green**, because that line is unreachable at `[u8; 16]`
>   (§7, **E-7**). The `0 of 1` cover was already saying this; the mutation says it in the form a
>   consumer can act on. Read together: *the panic-freedom claim covers the prefix of the parser a
>   too-small input can execute, and stops there.*

### 6.5 Bounds versus reality (`DER-X-BOUND`)

The outermost parsers are proved panic-free on buffers **an order of magnitude smaller than a real
input**: `x509_certificate` at ≤12 bytes against a ~170-byte certificate, `rsa_private_key` at ≤20
bytes against a ~317-byte key. Real-size panic-freedom rests on a compositional argument that is
written down and reviewed but **not machine-checked**. This is the single largest gap between what
"203/203 verified" sounds like and what it is.

---

## 7. Findings this envelope produced

**E-1 — three module docstrings attribute a check to a layer that does not perform it.**
`bit_string.rs:8-9`, `utc_time.rs:5-6` and `generalized_time.rs:5-6` tell the reader that the tag
identity and the primitive/definite form *"are enforced (and proven) upstream by [`crate::tag`] /
[`crate::tlv`]"*. Stated precisely, after review:

- **The "definite" half is true.** `tlv.rs:71` delegates to `decode_length`, which rejects the
  indefinite form at `length.rs:82`. That part of the docstring is correct.
- **The "primitive form" and "tag identity" halves are false of `tag`/`tlv`.** `PROOF_MANIFEST.md`
  §6.3 is right: `decode_tag` *"attaches no meaning to the combination"* and `decode_tlv` passes the
  parsed `Tag` through untouched. Neither module has so much as a `Constructed` error variant.
- **But the rules are not enforced *nowhere*.** Specific typed callers do check them — BIT STRING at
  `x509_spki.rs:145` and `x509_certificate.rs:205`, both time types at `x509_validity.rs:139`. The
  check is real; it lives at the call site, not upstream, and not in the codec whose docstring makes
  the claim.

Corrected statement: *the standalone content codecs do not enforce tag identity or primitive form,
and `tag`/`tlv` do not enforce those two rules either; particular typed callers do.* The defect is
that a reader of `bit_string.rs` concludes the rule is handled for them when they call
`decode_bit_string` directly — which is exactly the `DER-F-8` residual arriving through a different
door.

Severity: documentation, in a public crate, pointing at a safety-relevant check that is not performed
where it says. Fix is a docstring correction in three files. **Lid-safe**: none of the three is in the
Aeneas lid set (`big_integer`, `length`, `oid`, `sequence`, `tag`, `tlv`), so a docs-only edit there
cannot break the Lean line-span extraction.

**STATUS: FIXED 2026-08-25, at commit `3725018`.** All three docstrings now split the §10.2
requirement into its two halves — the *definite*-length half, which `tlv` genuinely does enforce via
`length`, and the *primitive*-form and tag-identity halves, which neither `tag` nor `tlv` enforces —
and name where each is actually decided: the specific typed callers (`x509_spki.rs`'s
`decode_public_key_tlv`, `x509_certificate.rs`'s signatureValue step, `x509_validity.rs`'s
`decode_time_tlv`, each read and verified rather than copied from this envelope) and, generically,
the new `identifier_form`. Each docstring now ends with the consequence stated plainly: *a direct
caller of this decoder must decide the identifier itself.*
**The lid-safety prediction held, and was checked rather than assumed:** the full-gate run at
`3725018` re-extracted all six Lean models clean and reported `lean lid: lid-source-state.txt
unchanged (hashes identical)` — i.e. the three edited files are genuinely outside the lid source
set, so the docs-only edits could not have moved a line span.

A caveat added by review, because the first version of this fix over-credited the new module:
`identifier_form` decides **form only**. Tag *identity* — "this is UNIVERSAL 3 and not something
else" — is decided by the typed callers and by nothing else, and the corrected docstrings now say
so. A caller who reaches for `identifier_form` instead of a typed parser still has no identity
check.

**E-3 — three `not-covered` rows promised a grep-zero that was never zero.** `DER-P-5`, `DER-P-6`
and `DER-P-7` each named an absence-grep scoped to `der-verified/src/profile.rs`. Run at `130de97`:

```
grep -nic 'BasicConstraints\|basic_constraints' der-verified/src/profile.rs   → 14      (claimed: empty)
grep -nic 'key_usage'                            der-verified/src/profile.rs   → 0       (claimed: empty ✓)
grep -nic 'name_constraint'                      der-verified/src/profile.rs   → 0       (claimed: empty ✓)
```

All 14 hits are in `profile.rs`'s own `mod tests` (line 474 onward): a `basicConstraints` extension
blob used as a *generic* extension fixture for the `DER-P-2` v3 tests, at `EXT_BASIC_CONSTRAINTS_DEFAULT`
and its thirteen call sites. **The row's conclusion is still correct** — basic-constraints validation
genuinely is not implemented, which the rewritten recipe `E` now shows with a scoped check and two
executed controls — but the row's *evidence*
was not. Anyone who ran the command would have seen 14 hits and had no way to tell whether they had
found unclaimed coverage or a fixture.

Two things make this worth writing down rather than quietly fixing:

- **It was wrong at `2b9f3d55` as well** (`git show 2b9f3d55:der-verified/src/profile.rs` → the same
  14). It is not drift introduced by the new commits; it shipped broken and survived a full
  second-model review, which reviewed the *labels* carefully and did not re-run the *recipes*.
- **The envelope had already written the warning that would have caught it**, one row up: *"a
  repo-wide grep hits comments and test fixtures and proves nothing."* The author scoped the grep to
  one file and treated that as sufficient — but a Rust module's unit tests live *in* the file, so
  file-scoping does not exclude fixtures. The general rule survived; its application had an
  off-by-one-layer error.

Severity: a broken self-verify recipe on a `not-covered` row — the failure mode is a consumer who
runs the command, sees hits, and either distrusts the whole table or wrongly concludes the rule is
covered. **This finding is the re-certification's own product**: it exists only because the pass
re-ran the recipes instead of re-reading the rows.

**The first fix for E-3 was itself wrong, and that is part of the finding.** It replaced the grep
with an *enumeration of `ProfileError`'s four variants*, on the argument that the enum is a closed
set of what the profile layer decides. It is not: the docstring gives *variant ⇒ enforced rule* and
not the converse, and **`DER-P-4` is the counterexample in this very crate** — error precedence is an
enforced, contract-graded rule with no variant of its own. `COVERAGE.md` §4 withdrew that recipe;
this envelope was conformed to the withdrawal on 2026-08-26 and `E` is now a *scoped, comment-filtered
absence check with two positive controls* (§4). Three attempts, and the third is the first that
decides anything: a wrong scope, then a wrong closure argument, then a control pair.

**E-4 — a positive control that is not available must be declared missing, not inherited.**
`COVERAGE.md` gives `DER-P-6` (key usage) and `DER-P-7` (name constraints) the note *"same controls"*
as `DER-P-5`. Measured at `130de97` on 2026-08-26: unscoped, `key_?usage` and `name_?constraint`
return **0** over `profile.rs` as well — there are no fixtures naming them anywhere in the file, so
removing the scope changes nothing and **control 2 cannot fire on either row.** Only `DER-P-5` has a
fixture population for the scope to exclude. The rows' conclusions are unaffected and their control 1
is real; what was wrong was the claim that a *second* control stood behind them. A control asserted
by inheritance from a neighbouring row is the same defect class as the lying grep it was invented to
catch — a control that has not been run is not a control. The two rows now carry control 1 and say so.

**E-5 — `DER-C-OCT-2`'s oracle was derived from the state under test, and the mutation is what
showed it.** The row claimed, at `CONTRACT`, that *"an accepted OCTET STRING's content is exactly the
TLV's value window"*. Its harness, `octet_string::proofs::accepted_content_is_the_tlv_value`, compares
`decode_octet_string`'s output against `decode_tlv(input).unwrap()` — the very function the subject
calls. Perturbing `decode_tlv` so its value slice became the whole tail rather than the declared
`header..header+len` window moved subject and oracle together, and the harness stayed **GREEN**. Only
perturbing `decode_octet_string`'s own forwarding turned it red. So the harness decides *forwarding
fidelity*, not *the window*. The row is re-graded to `PROBE`, its item narrowed to what is decided,
and the window half is split out as the unweighted, compositional `DER-C-OCT-2b`. **This is the same
defect `COVERAGE.md` had a second-model review adjudicate on `DER-F-1`** (a round trip against the crate's own
`encode_tag`), found independently, by mutation rather than by reading — which is the argument for
mutation controls in one paragraph.

**E-6 — two recipes name a harness whose verdict cannot report the claim false, and the mutation
pass proved it rather than arguing it.** Kani reports a
harness whose `kani::cover` is unsatisfiable as `VERIFICATION:- SUCCESSFUL`, with `0 of N cover
properties satisfied`, and `check.sh` does not fail on that (§4). `x509_tbs_certificate::proofs::
parse_tbs_certificate_ok_path_witnessed` and `x509_extension::proofs::validate_extensions_ok_path_
witnessed` assert **nothing but a cover**: their whole content is `kani::cover(result.is_ok(), ..)`.
A perturbation that stops the parse reaching its `Ok` tail therefore leaves the verdict green and
moves only the tally. So for those rows the *verdict* is not the recipe's answer — the **cover line
is** — and a row that names the harness without naming the tally has not told the consumer how to
fail it (`core.md` §3 rule 2). Their `expect` now names the tally. The general form: **a
cover-only harness is a reachability witness, not an oracle**, and weighting one on its exit status
would be weighting a command that cannot say no.

**Demonstrated, both directions, 2026-08-26.** Perturbing `parse_extension`'s post-extnID slice, and
separately breaking `parse_tbs_certificate`'s strict-tiling rule, each left the verdict at
`VERIFICATION:- SUCCESSFUL` **and dropped the tally from `1 of 1` to `0 of 1`**; restoring returned
both to `1 of 1`. So these two recipes *do* discriminate — through the tally. A checker reading only
the exit status would have called both perturbations green, which is precisely the shape of green
this envelope exists to take apart.

**And the sharper limit, on `DER-X-TBS-1` alone: that companion runs ONE input.** Only a perturbation
on that specimen's own path can ever be seen. The first mutation tried there — removing the
missing-serialNumber guard — moved neither verdict nor tally, because the specimen has a serial
number and never reaches the guard. A cover over a single fixture is a witness that *this* input
reaches the tail, and it is nothing else.

**E-7 — a mutation that stays green sometimes measures the harness's REACH, not the claim.** Two
perturbations did not turn their harness red, and neither is a defect in the shipped code:

- `DER-X-VALID`: shifting the post-`notBefore` slice by one — an out-of-bounds read on a real input —
  left `x509_validity::proofs::parse_never_panics` green. At `[u8; 16]` a `Time` TLV cannot decode at
  all (a UTCTime needs 15 octets inside a SEQUENCE header), so **that line is unreachable at the
  bound**. It is the same vacuity §6.4 already discloses through the `0 of 1` cover, arriving from
  the other side: the row's panic-freedom claim covers only the prefix of `parse_validity` a
  16-octet input can execute.
- `DER-C-CTX`: replacing `decode_tlv`'s `checked_add` header/length overflow guard with a plain `+`
  left `context_tag::proofs::decode_explicit_context_never_panics` green, because at 16 octets the
  addition cannot overflow.

Recorded on both rows rather than dropped, because *"the mutation did not go red"* is the answer to a
question a consumer is entitled to ask, and the correct reading is **"the bound does not reach that
line"**, not *"the proof is fine"*. Both rows still carry a witness from a perturbation the bound
does reach.

**E-8 — `DER-F-4`'s Kani half had `DER-F-1`'s defect. ADJUDICATED 2026-08-26; the row is now split
and re-graded.** `length::proofs::decode_accepts_only_canonical` is, line for line, the same shape
as the harness that got `DER-F-1` demoted to `PROBE`: decode, re-encode with the crate's own
`encode_length`, compare to the input. The envelope raised this as an open question rather than
re-grading unilaterally — `DER-F-1`'s demotion was adjudicated, so this one had to be — and the
adjudication came back in three parts:

- **The Kani half is a `PROBE`.** Its oracle is the crate's own encoder, so it decides canonicality
  and not that the length octets were read as §10.1 requires. That it is bounded is the smaller
  problem; the oracle is the larger one. It keeps its weight, because it has its mutation witness
  and the witness is honest about what it falsifies.
- **The Lean lid is the independent oracle, and it is what would carry the rule.** The
  independence question the envelope raised is answered in the lid's favour: a kernel-checked
  statement over all input lengths is not the crate's encoder vouching for the crate's decoder.
- **But the lid is unwitnessed here**, for the same toolchain reason as `DER-F-1b`, so it may not
  be folded into a single row's grade alongside evidence that does not support it. It becomes
  `DER-F-4b`, at `CONTRACT`, **unweighted**.

The general form, which is why this is recorded as a finding and not a correction: **a row holding
a weak witnessed claim and a strong unwitnessed one grades as the strong claim and is falsifiable
only as the weak one.** Splitting is not bookkeeping — it is the only way the tier marker can tell
the truth about both halves. `DER-F-1`/`DER-F-1b`, `DER-C-OCT-2`/`DER-C-OCT-2b` and now
`DER-F-4`/`DER-F-4b` are the same move three times.

**E-2 — the strongest and weakest layers are inverted relative to customer risk.** The framing and
codec layers carry the `CONTRACT` rows. The X.509 layer — the part a customer
actually feeds a hostile certificate to — has **no conformance `CONTRACT` row at all**: it is
panic-freedom probes, two concrete rule tests, an inspection argument for realistic sizes, and
uncovered semantics, with three unsatisfied covers and the smallest bounds in the crate.

That is the cost curve, not a defect: those are the 7–20 GB harnesses, and the crate
says so. It is invisible in the headline count, and visible in one glance here. *(That sentence
used to quote "191 of 191" — a figure from an earlier commit, left behind when the crate grew to
203 harnesses. Corrected 2026-08-26 to name no number at all: this envelope has exactly one place
that states the harness count, §1, and it is read out of the crate's generated regions rather than
typed. A second copy of a count is a second thing to drift, which is the defect §8 warns about
happening inside the document that warns about it.)*

---

## 8. Provenance of this envelope

Hand-built, 2026-08-25, against `2b9f3d55`; **re-certified the same day against `130de97`** (§8.1).
**Nothing here was generated**, which means this file can lie in ways the crate's own generated
documents cannot. Three mitigations, and they are the reason hand-building is acceptable:

1. **Every row carries a runnable recipe.** A hand-asserted row that names a command is falsifiable by
   the consumer in one step. That is a different risk profile from a hand-asserted row that names only
   a conclusion.
2. **Derived fields are marked as derived.** The counts quoted in §1 and in the rows below (203, 485,
   34, 6 lids; and 84 public entry points / 73 harnessed / 11 not, 186 covers, cited in §5.5 and §6)
   are read out of the crate's own gate-enforced generated regions via
   `python3 gates/gen_proof_manifest.py --json`, not typed from memory. Judgement
   fields — every `strength` cell, and §6/§7 — are this envelope's author's, and are wrong if the
   recipe beside them says otherwise.
3. **Added 2026-08-26: every weighted row's recipe has been watched to fail.** The first two
   mitigations both stop at *"the row names a command"*. They do not establish that the command
   would notice the claim being false, and a command that would pass with the implementation deleted
   decided nothing. So each weighted row now carries a structured witness naming what was perturbed
   and what was observed — and the perturbation really was made: in a scratch `git worktree` off a
   backup ref, never in the certified tree, with the harness run memory-capped, the source restored
   by `git checkout`, and the harness run again to confirm it comes back green.

   **What this does not establish, stated because §4.1 says the field invites over-reading.** The
   witness text is prose written by the same author as the row. A reader cannot tell a real
   observation from a plausible invented one, and no checker can either — structure raises the cost
   of the lie and moves the residual to review. What it *does* establish, and what the previous two
   mitigations could not, is that somebody ran the command against a broken version of the thing it
   claims to decide. Four times in this pass the answer came back **green** — twice because the
   perturbation was unreachable at the harness's declared bound (§7, **E-7**), once because a
   fixture-shaped harness's concrete input dodged it (`DER-C-SEQ-3`), and once because the oracle
   moved with the subject (§7, **E-5**). Those four are on the rows and in §7 rather than dropped,
   which is the only reason to give the other sixty-odd any credit.

### 8.1 What "re-certified at `130de97`" actually means

The word is only worth something if it names a procedure, so here is the one that ran. It is
deliberately mechanical, because the point is that it can be re-run by someone who does not trust
the author.

1. **Freshness.** `git diff bffab69..HEAD -- der-verified/src lean` → empty. The two commits between
   the receipt and HEAD touch only `CHANGELOG.md`, `PROOF_MANIFEST.md` and the evidence logs, so the
   `bffab69` run speaks for `130de97`.
2. **Counts re-derived, never re-typed.** Every number in §1 and §5.5 came from
   `gates/gen_proof_manifest.py --json` at HEAD. This is what caught the `DER-S-3` drift (80/69 →
   84/73) and a description error beside it: the "nine `restricted_string` per-type wrappers" are
   eight wrappers plus `Charset::tag_number`.
3. **Every `K` recipe re-checked, mechanically.** All **82** distinct harness paths named in the
   `verify` column were extracted from this file and checked twice: that the function still exists in
   the module it names at HEAD, and that a `Checking harness <H>...` line for it appears in
   `evidence/check-bffab69.log`. **82 of 82 passed both.** The run those lines belong to closed
   `Complete - 203 successfully verified harnesses, 0 failures, 203 total`, so no cited harness is
   stale, renamed, or unrun.
4. **Every `A` recipe actually executed**, with its positive control. This is the step that produced
   **E-3** — and the step that a re-read rather than a re-run would have skipped for a second time.
5. **`N`, `T`, `R` recipes spot-checked at HEAD.** The seven cited Lean theorems were located in the
   files named (`TagProofs`, `LengthProofs`, `TlvProofs`, `SequenceProofs`, `BigIntProofs`,
   `OidProofs`); the three `test-only` rows' tests were located by name; the four `R` rows' cover
   tallies were re-read out of the new log — the three disclosed-unsatisfiable covers are still
   exactly `x509_validity`, `x509_extension`, `x509_tbs_certificate` and no others, and
   `sequence::no_over_read` still reports `2 of 2 cover properties satisfied`.

**What this procedure does NOT establish**, stated because a list of green steps invites the
opposite reading: nothing above grades any harness's *oracle*. A harness that verifies the wrong
property appears in the log exactly like one that verifies the right property, and step 3 would pass
on both. Oracle quality is what the `strength` column asserts, and that column is reviewed, not
gated. The crate's own run log makes the same disclaimer about itself in its header — and both
defects fixed at `bffab69` were found by **review**, with every gate green across both.

**Reviewed.** A second-model review checked this envelope against the sources on 2026-08-25 and
returned FIX-THEN-SHIP with three blockers. All were real and all are folded above: `DER-F-1` claimed
an L4 strength the tag lid does not provide (its theorems are totality and consumption bounds, not
canonicality — now split into `DER-F-1`/`DER-F-1b`); seven rows were labelled `CONTRACT` on
fixture-shaped or monomorphic evidence (`DER-F-3`, `DER-F-7`, `DER-C-SETOF-1/2/3`, `DER-P-1`,
`DER-S-2`, plus `DER-X-EXT-2`/`DER-X-TBS-2` → `test-only`); and three recipes were unsound as written
— `check.sh` PASS does not imply the Lean stage ran, a bare `grep` of the run log shows neither the
verdict nor the cover tally, and two absence-greps returned matches. **That a hand-built envelope's
first draft overclaimed seven rows is itself a finding**: the labels are the part that needs review,
and the recipes are what made the review cheap enough to be worth running.

Sources read: `PROOF_MANIFEST.md` (§1, §3.2, §3.4, §4.1, §6.1–6.3, §8.1–8.4), `README.md` (scope,
verification map, strict decoding), `DER-REMAINING-WORK.md` (§3, §4, R1, R2), `DECISIONS.md` D13/D33,
`check.sh`, `gates/tiers.txt`, `gates/map_declared.txt`, `evidence/check-bffab69.log`, and the module
sources for every row cited.

**Note on the earlier "three recipes were unsound" blocker.** That review caught three, and the
third was recorded as *"two absence-greps returned matches"* — fixed by scoping them to
`profile.rs`. E-3 is the residue of that fix: file-scoping does not exclude a Rust module's own unit
tests, so one of the two was still wrong afterwards. The class of defect was identified correctly in
review and the repair was incomplete, which is an argument for **re-running** recipes on every
re-certification rather than trusting that a previously-reviewed row stays reviewed.

**Relationship to the crate's own copy.** A consumer-facing version of this ledger now ships **inside
the subject**, as `COVERAGE.md` at the repository root, linked from `README.md`'s verification map.
That copy is written for a reader who arrives at the crate, carries the same rows and recipes, and
adds nothing this file does not support. Its crate-total counts are **gate-enforced** — `COVERAGE.md`
is registered in `gates/gen_proof_manifest.py`'s `GUARDED_DOCS`, so a stale harness or test count in
it fails `./check_fast.sh`. That is a strictly stronger position than this file enjoys, and it is the
first case of an envelope's derived fields being machine-guarded rather than hand-checked.

This file is derived from an internal working copy; identifying detail about internal review
tooling has been generalized for publication. `COVERAGE.md` (the crate's own copy of this ledger)
was written directly for public consumption and carries no such detail.
