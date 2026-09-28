# Clause inventories

A clause inventory is an **in-tree, normalised slice of an external standard**: clause numbers
and short titles in our own words. It is not the standard. Its selection, titles and classifications
are judgment-level assertions of faithfulness to that standard. Nothing mechanically decides that
faithfulness. Parsing, counting and hashing decide only properties of the inventory file.

Each `<standard-id>.clauses.toml` contains one `[standard]` table and one `[[clause]]` table
per admitted reference. A slice makes no completeness claim about the external standard.

## Fields

Every field below is required. Strings are TOML strings; `slice` is a TOML boolean.

`[standard]`:

- `id`: stable, lowercase, hyphenated inventory identity; also the filename stem before
  `.clauses.toml`, for example `itu-t-x690-2021`.
- `title`: short identification of the external standard and its edition, in our own words.
- `edition`: the cited edition, for example `2021-02`; not the inventory's edit date.
- `provenance`: `"external"`. The source of authority is external even though this inventory is
  stored in the tree.
- `slice`: `true`. These inventories declare slices, not complete standards.
- `slice_note`: nonempty description of the selected scope and its limits.
- `numbering`: `"the standard's own clause numbers"`. Do not substitute module or harness names.

`[[clause]]`:

- `id`: stable reference key, unique within the inventory; convention below.
- `ref`: human-readable external locator, for example `§8.1.2.4.2 c)` or `Table 1`.
- `title`: short title in our own words, at most 12 whitespace-separated words; never a quotation.
- `force`: one of `shall`, `shall-not`, `should`, `may`, `definition`, `informative`. Respectively:
  requirement, prohibition, recommendation, permission, definition, or context without an obligation
  in this slice. Classify the cited rule; do not infer a force from the subject's implementation.
- `side`: one of `encoder`, `decoder`, `both`; who can violate the rule in the declared codec scope.
  This classifies the rule's reach, not which side a particular subject implements.

The `force` and `side` sets are closed. Neither field records applicability, evidence, assurance or
completion. Broad clauses can contain several rules with different forces; the single `force`
field is a coarse classification, not a replacement for consulting the standard. `side = "both"`
on a definition or informative row records relevance to both sides, not an extra obligation.

## Reference keys

Use `<PREFIX>-<clause number>`; retain dots and append any list letter without a space or closing
parenthesis. Thus `§8.1.2.4.2 c)` becomes `X690-8.1.2.4.2c`. Table references use `T<number>`;
X.680 Table 1 is `X680-T1`. Do not renumber references to make an inventory consecutive.

The registered prefixes are `X690-`, `X680-`, `RFC5280-`, `RFC5208-`, `RFC5958-`, `RFC8017-`,
`RFC5915-`, `RFC3279-`, `RFC5480-` and `RFC8410-`. The standard identity includes the edition;
the clause prefix does not. Resolve a clause key within the pinned inventory.

Parent clauses and selected subclauses may both have rows. Each row counts once; parentage does
not add unlisted children, discharge a child's claim or make the rows independent obligations.

## Copyright and uncertain references

X.690 and X.680 are ITU copyrighted; RFC text has its own licence. Carry clause numbers and short
titles in our own words only. Never copy normative text or quote the standard, including in comments.
Work from the subject crate's own source comments and knowledge of the standards' structure. A
source comment is a citation lead, not proof of accuracy.

If a subclause number is uncertain, omit its `[[clause]]` row. Record the candidate reference and
the uncertainty in a trailing `# UNVERIFIED:` comment block. The block may also flag a disputed
rule-to-clause mapping. Do not invent a number to close a coverage gap. Comments are not clauses,
do not enter the clause count and cannot be claimed as inventory rows. Review must resolve an
uncertain reference before it becomes a row.

## Manifest pinning

A manifest binds the inventory under [the format's F2 rule](../../../spec/format.md).
Set `[spec].path` to the inventory path, `[spec].provenance = "external"`,
and `[spec].version` to `normative-reference:sha-512:<128-lowercase-hex>`.

Inventory identity is bound by digest only: a consumer compares a manifest's `[spec].version`
against the canonical inventory's digest out-of-band. The checker rejects
absolute `[spec].path` and `applicability_record` paths and paths resolving outside the repo root
(the nearest ancestor containing `.git`, or `--root`).

Compute the hex digest as SHA-512 of `b"normative-reference:"` concatenated directly with the
inventory file's raw bytes. Do not parse, reserialize, normalize newlines or strip comments first.
The separate applicability-record hash changes nothing in F2's construction or wire form.
For example, run from the repository root:

```sh
python3 - <<'PY'
import hashlib
from pathlib import Path

path = Path("profiles/conformance/standards/itu-t-x690-2021.clauses.toml")
digest = hashlib.sha512(b"normative-reference:" + path.read_bytes()).hexdigest()
print("normative-reference:sha-512:" + digest)
PY
```

The manifest header must state in a comment that this digest pins the in-tree normalised inventory
slice. It does not hash the external standard or decide the inventory's faithfulness. Any byte
change, including a comment edit, requires a new pin.

Set `[spec].axis` to one claim per clause of the declared slice, identify the external edition in
`[spec].external`, and name the inventory's `id` in `[conformance].standard`. The clause total is
the number of `[[clause]]` rows. Each row has exactly one manifest claim, including rows declared
not applicable or excluded; no claim may cite a key outside that inventory. Set
`[coverage].denominator = "slice"` if the core validator accepts it; otherwise omit it and report
that limitation. Record the scope in `[coverage].slice_note`.
