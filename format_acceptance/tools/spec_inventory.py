#!/usr/bin/env python3
"""spec_inventory.py — the generic B19 spec-inventory generator (core.md B19, spec/format.md).

`make SPEC.md` prints a `[spec].inventory`-shaped TOML document to stdout: one `[inventory]`
header and one `[[item]]` row per Markdown heading (level >= 2) in `SPEC.md`, in document order.
An item's id is its own trailing `{#id}` anchor when present; otherwise it is the heading's
position path built from heading NESTING alone (`S-<n>` for the n-th level-2 heading in document
order, `S-<n>.<m>` for the m-th level-3 heading nested under it, and so on) — never from any
number that already appears in the heading text. This is the same `S-<n>[.<m>...]` convention
`spec/format.md`'s own schema example already uses for `clause`. Output is a pure function of
`SPEC.md`'s bytes: identical input produces byte-identical output (deterministic).

`check SPEC.md INVENTORY.toml` regenerates the inventory from `SPEC.md` and reports drift against
the given `INVENTORY.toml`'s `[[item]]` rows: ids only the fresh generation has (ADDED), ids only
the given file has (REMOVED), and ids present in both whose `title` differs (RETITLED). Exit 0 with
no drift, 1 otherwise. A heading that loses or gains an explicit `{#id}` anchor, or that moves
across a level-2 ancestor's position, surfaces as an ADDED/REMOVED pair rather than a guessed
rename — id stability across restructuring is what `{#id}` anchors are for.

`digest INVENTORY.toml` prints `[spec].inventory_digest`'s wire form: the B16 `inventory:` domain
digest over the file's raw bytes, via `hashdomains.py`.

This tool only produces/inspects the inventory document; `check_core.check_inventory` is the class
check that a manifest's `[spec].inventory`/`[spec].inventory_digest` and claims obey B19.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import hashdomains

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ANCHOR_RE = re.compile(r"\{#([A-Za-z0-9][A-Za-z0-9._-]*)\}\s*$")

NUMBERING_NOTE = (
    "S-<n> per top-level (level-2) heading in document order, S-<n>.<m> for a nested "
    "level-3 heading under it (and so on by nesting depth alone, never by any number "
    "already in the heading text), or the heading's own {#id} anchor when present"
)


def _toml_string(value: str) -> str:
    # TOML basic strings share JSON's escape rules for \, ", and control characters.
    return json.dumps(value, ensure_ascii=False)


def generate_items(text: str) -> tuple[str | None, list[dict]]:
    """Returns (document title, items). Items are in document order; each has at least
    id/title, plus parent when nested under another generated item."""
    title: str | None = None
    counters: dict[int, int] = {}
    parent_at: dict[int, str] = {}
    items: list[dict] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        heading_text = match.group(2)
        anchor = ANCHOR_RE.search(heading_text)
        explicit_id = None
        if anchor:
            explicit_id = anchor.group(1)
            heading_text = heading_text[: anchor.start()].rstrip()
        if level == 1:
            if title is None:
                title = heading_text
            continue
        for deeper in [lvl for lvl in counters if lvl > level]:
            del counters[deeper]
            parent_at.pop(deeper, None)
        counters[level] = counters.get(level, 0) + 1
        item_id = explicit_id or "S-" + ".".join(
            str(counters[lvl]) for lvl in sorted(counters) if lvl <= level
        )
        shallower = [lvl for lvl in parent_at if lvl < level]
        item = {"id": item_id, "title": heading_text}
        if shallower:
            item["parent"] = parent_at[max(shallower)]
        parent_at[level] = item_id
        items.append(item)
    return title, items


def render(source: str, title: str | None, items: list[dict]) -> str:
    stem = Path(source).stem or "spec"
    lines = [
        "[inventory]",
        f"id = {_toml_string(stem)}",
        f"title = {_toml_string(title or stem)}",
        f"source = {_toml_string(source)}",
        f"numbering = {_toml_string(NUMBERING_NOTE)}",
    ]
    for item in items:
        lines.append("")
        lines.append("[[item]]")
        lines.append(f"id = {_toml_string(item['id'])}")
        lines.append(f"title = {_toml_string(item['title'])}")
        if "parent" in item:
            lines.append(f"parent = {_toml_string(item['parent'])}")
    return "\n".join(lines) + "\n"


def cmd_make(args: argparse.Namespace) -> int:
    text = Path(args.spec).read_text(encoding="utf-8")
    title, items = generate_items(text)
    sys.stdout.write(render(args.spec, title, items))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    import tomllib

    text = Path(args.spec).read_text(encoding="utf-8")
    _, fresh_items = generate_items(text)
    fresh = {row["id"]: row["title"] for row in fresh_items}
    try:
        given_doc = tomllib.loads(Path(args.inventory).read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"UNREADABLE {args.inventory}: {exc}", file=sys.stderr)
        return 2
    given_items = given_doc.get("item", [])
    given = {
        row["id"]: row.get("title")
        for row in given_items
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    added = sorted(fresh.keys() - given.keys())
    removed = sorted(given.keys() - fresh.keys())
    retitled = sorted(k for k in fresh.keys() & given.keys() if fresh[k] != given[k])
    for item_id in added:
        print(f"ADDED {item_id} {fresh[item_id]!r}")
    for item_id in removed:
        print(f"REMOVED {item_id} {given[item_id]!r}")
    for item_id in retitled:
        print(f"RETITLED {item_id}: {given[item_id]!r} -> {fresh[item_id]!r}")
    if not (added or removed or retitled):
        print(f"CLEAN {args.spec} matches {args.inventory}: {len(fresh)} item(s)")
        return 0
    return 1


def cmd_digest(args: argparse.Namespace) -> int:
    raw = Path(args.inventory).read_bytes()
    print(hashdomains.digest("inventory:", raw))
    return 0


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec_inventory.py", description=__doc__)
    sub = parser.add_subparsers(dest="verb", required=True)

    sp = sub.add_parser("make", help="generate a spec inventory from a Markdown document")
    sp.add_argument("spec")
    sp.set_defaults(func=cmd_make)

    sp = sub.add_parser("check", help="report drift between a spec document and a generated inventory")
    sp.add_argument("spec")
    sp.add_argument("inventory")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("digest", help="print [spec].inventory_digest's wire form for an inventory file")
    sp.add_argument("inventory")
    sp.set_defaults(func=cmd_digest)

    return parser


# --------------------------------------------------------------------------
# Selftest
# --------------------------------------------------------------------------

SAMPLE_SPEC = """# Example Spec

Some prose.

## First Section

Body.

### First Subsection

Nested body.

### Second Subsection {#custom-id}

Anchored body.

## Second Section

More body.
"""


def selftest() -> int:
    import tempfile
    import tomllib
    from contextlib import redirect_stdout
    from io import StringIO

    failures: list[str] = []
    checks_run = 0

    def check(name, condition):
        nonlocal checks_run
        checks_run += 1
        if not condition:
            failures.append(name)

    title, items = generate_items(SAMPLE_SPEC)
    check("title", title == "Example Spec")
    ids = [item["id"] for item in items]
    check("computed-ids", ids == ["S-1", "S-1.1", "custom-id", "S-2"])
    check("anchor-overrides-position", items[2]["id"] == "custom-id")
    check("parent-of-nested", items[1].get("parent") == "S-1")
    check("parent-of-anchored-child", items[2].get("parent") == "S-1")
    check("top-level-has-no-parent", "parent" not in items[0])

    rendered_once = render("SPEC.md", title, items)
    rendered_twice = render("SPEC.md", *generate_items(SAMPLE_SPEC))
    check("deterministic", rendered_once == rendered_twice)
    check("no-firmness-emitted", "firmness" not in rendered_once)

    _, repeated_items = generate_items(SAMPLE_SPEC + SAMPLE_SPEC)
    repeated_ids = [i["id"] for i in repeated_items]
    check("repeat-headings-increment", repeated_ids[:4] == ["S-1", "S-1.1", "custom-id", "S-2"])
    check("repeat-headings-continue", repeated_ids[4:] == ["S-3", "S-3.1", "custom-id", "S-4"])

    parsed = tomllib.loads(rendered_once)
    check("parses-as-toml", parsed.get("inventory", {}).get("id") == "SPEC")
    check("item-count", len(parsed.get("item", [])) == 4)

    raw = rendered_once.encode("utf-8")
    expected_digest = hashdomains.digest("inventory:", raw)
    check(
        "digest-wire-form",
        expected_digest.startswith("inventory:sha-512:")
        and len(expected_digest) == len("inventory:sha-512:") + 128,
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        spec_path = root / "SPEC.md"
        spec_path.write_text(SAMPLE_SPEC, encoding="utf-8")
        inventory_path = root / "inventory.toml"
        inventory_path.write_text(rendered_once, encoding="utf-8")

        expected_make = render(str(spec_path), title, items)
        out = StringIO()
        with redirect_stdout(out):
            exit_code = cmd_make(argparse.Namespace(spec=str(spec_path)))
        check("cmd-make-matches-render", exit_code == 0 and out.getvalue() == expected_make)

        out = StringIO()
        with redirect_stdout(out):
            exit_code = cmd_check(argparse.Namespace(spec=str(spec_path), inventory=str(inventory_path)))
        check("cmd-check-clean", exit_code == 0 and out.getvalue().startswith("CLEAN "))

        out = StringIO()
        with redirect_stdout(out):
            exit_code = cmd_digest(argparse.Namespace(inventory=str(inventory_path)))
        check("cmd-digest-matches", exit_code == 0 and out.getvalue().strip() == expected_digest)

        # Drift fixture: retitle S-1, drop S-1.1 from the "given" file the generator's fresh
        # regeneration is compared against — S-1.1 then reports ADDED (fresh has it, given does
        # not), and S-1 reports RETITLED.
        drifted_items = [dict(row) for row in parsed["item"]]
        drifted_items[0]["title"] = "A different title"
        removed_id = drifted_items.pop(1)["id"]
        drift_lines = [
            "[inventory]",
            f"id = {_toml_string(parsed['inventory']['id'])}",
            f"title = {_toml_string(parsed['inventory']['title'])}",
            f"source = {_toml_string(parsed['inventory']['source'])}",
            f"numbering = {_toml_string(parsed['inventory']['numbering'])}",
        ]
        for row in drifted_items:
            drift_lines += ["", "[[item]]", f"id = {_toml_string(row['id'])}", f"title = {_toml_string(row['title'])}"]
            if "parent" in row:
                drift_lines.append(f"parent = {_toml_string(row['parent'])}")
        drift_path = root / "drifted.toml"
        drift_path.write_text("\n".join(drift_lines) + "\n", encoding="utf-8")

        out = StringIO()
        with redirect_stdout(out):
            exit_code = cmd_check(argparse.Namespace(spec=str(spec_path), inventory=str(drift_path)))
        report = out.getvalue()
        check("cmd-check-exit-1-on-drift", exit_code == 1)
        check("cmd-check-reports-retitled", f"RETITLED {parsed['item'][0]['id']}:" in report)
        check("cmd-check-reports-added", f"ADDED {removed_id} " in report)

    if failures:
        print("SELFTEST FAIL: " + ", ".join(failures), file=sys.stderr)
        return 1
    print(f"SELFTEST PASS: {checks_run} spec-inventory fixtures")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv[1:]:
        if len(argv) != 2:
            print("usage: spec_inventory.py --selftest", file=sys.stderr)
            return 2
        return selftest()
    if len(argv) < 2:
        print("usage: spec_inventory.py {make,check,digest} ...  (or --selftest)", file=sys.stderr)
        return 2
    parser = build_argparser()
    args = parser.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
