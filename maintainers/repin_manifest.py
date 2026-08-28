#!/usr/bin/env python3
"""repin_manifest.py -- re-pin the root acceptance.toml (this repo's own self-manifest) after
maintainers/capture_evidence.py has regenerated its evidence/*.txt transcripts, per the
self-certification convention (format.md "`[format]` self-location", "Self-certification
convention -- the one-commit lag").

MECHANICAL re-cert edits ONLY -- driven by the OLD pin found IN the manifest itself, never
hardcoded, so this script keeps working the next time it is re-run against a different old pin:

  - [format].spec_sha's CURRENT value (the old pin, full 40-hex) -> the new commit
  - the old pin's first 12 hex chars, wherever they appear as a `...@<sha12>` tool-identity
    suffix -> the new commit's first 12 hex chars
  - any OTHER `...@<sha12>` token (a partial-recertification exception -- a record captured at a
    later commit than [subject].commit, format.md "Partial re-certification") -> the new pin too,
    and the "NOTE on the self-certification convention's one-commit lag" comment block that
    discloses such an exception is DROPPED: a full recapture (which is what
    maintainers/capture_evidence.py just did) dissolves a partial-recert exception, it does not
    leave it stale beside a pin that has moved past it.
  - generated_at -> capture time (now, UTC)
  - every evidence record_hash -> freshly recomputed M11 digest of its (just recaptured)
    transcript, via tools/m11.py as a library

NOT touched, by design (this is a MECHANICAL tool, not a content editor): claim statements,
self_verify.expect/watched_fail text, or any other normative prose -- including prose that quotes
a count (e.g. SELF-7's tracked-file-count text) which a recapture can make stale. Content drift
like that is a reviewed, hand-made edit; re-pinning only makes the FILE-IDENTITY fields agree with
what was actually captured. Run `python3 tools/check_acceptance.py --strict --strict-weight
acceptance.toml` after this script and read its output -- a clean structural PASS is not the same
claim as "every statement is still accurate," and this tool does not claim the second one.

Usage: python3 repin_manifest.py <repo-root> [--new-sha <40-hex>]   (default: git rev-parse HEAD
at <repo-root>)

One-off tooling used to assemble this repository (2026-08-28), made repo-root relative and
self-contained: this version detects the old pin by reading the file instead of hardcoding it.
"""
import argparse
import re
import subprocess
import sys
import pathlib


def git_head(root: pathlib.Path) -> str:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()


def utc_now() -> str:
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                           capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_root")
    ap.add_argument("--new-sha", default=None,
                     help="40-hex commit to pin to (default: current HEAD)")
    args = ap.parse_args()

    root = pathlib.Path(args.repo_root).resolve()
    new_sha = args.new_sha or git_head(root)
    if not re.fullmatch(r"[0-9a-f]{40}", new_sha):
        print(f"error: --new-sha must be 40 lower-case hex chars, got {new_sha!r}", file=sys.stderr)
        return 2
    new_12 = new_sha[:12]
    gen_at = utc_now()

    sys.path.insert(0, str(root / "tools"))
    import m11  # noqa: E402

    manifest = root / "acceptance.toml"
    text = manifest.read_text()

    m = re.search(r'spec_sha\s*=\s*"([0-9a-f]{40})"', text)
    if not m:
        print("error: could not find [format].spec_sha in acceptance.toml", file=sys.stderr)
        return 1
    old_full = m.group(1)
    old_12 = old_full[:12]

    # 1. Drop any partial-recertification NOTE block (contiguous run of comment lines starting
    #    with the fixed marker).
    lines = text.split("\n")
    out, i, dropped = [], 0, 0
    while i < len(lines):
        if lines[i].lstrip().startswith("# NOTE on the self-certification convention's one-commit lag"):
            while i < len(lines) and lines[i].lstrip().startswith("#"):
                i += 1
                dropped += 1
            continue
        out.append(lines[i])
        i += 1
    text = "\n".join(out)

    # 2. full-40 pin -> new (must run BEFORE the 12-char pass; the 40 contains the 12 as a prefix)
    n_full = text.count(old_full)
    text = text.replace(old_full, new_sha)

    # 3. 12-char pin -> new
    n_12 = text.count(old_12)
    text = text.replace(old_12, new_12)

    # 4. Any OTHER `@<sha12>` token still present is a partial-recert exception; retarget it too.
    n_exceptions = 0
    for tok in sorted(set(re.findall(r"@([0-9a-f]{12})\b", text))):
        if tok == new_12:
            continue
        n_exceptions += text.count(f"@{tok}")
        text = text.replace(f"@{tok}", f"@{new_12}")

    # 5. generated_at
    text, n_gen = re.subn(r'(generated_at\s*=\s*")[^"]*(")',
                           lambda mm: mm.group(1) + gen_at + mm.group(2), text, count=1)
    if n_gen != 1:
        print(f"error: expected exactly 1 generated_at field, found {n_gen}", file=sys.stderr)
        return 1

    # 6. record_hash refresh, matched per cited record path.
    n_hash = 0
    for m_ev in re.finditer(r'record\s*=\s*"([^"]+)"', text):
        relp = m_ev.group(1)
        ev_path = root / relp
        if not ev_path.is_file():
            print(f"warning: record {relp!r} not found on disk, record_hash left unchanged",
                  file=sys.stderr)
            continue
        newh = m11.digest_file("evidence-record", str(ev_path))[len("sha-512:"):]
        pat = re.compile(r'(record\s*=\s*"' + re.escape(relp)
                          + r'"\s*\n\s*record_hash\s*=\s*"sha-512:)[0-9a-f]{128}(")')
        text, k = pat.subn(lambda mm: mm.group(1) + newh + mm.group(2), text)
        n_hash += k

    manifest.write_text(text)
    print(f"old_sha={old_full}  new_sha={new_sha}  new_12={new_12}  generated_at={gen_at}")
    print(f"dropped partial-recert NOTE lines: {dropped}")
    print(f"replaced: full-40 pin x{n_full}, 12-char pin x{n_12}, "
          f"other @<sha12> exceptions x{n_exceptions}, record_hash x{n_hash}")
    print("remaining sha-ish tokens (excl. sha-512 digests) -- review these by hand:")
    for tok in sorted(set(re.findall(r"\b[0-9a-f]{7,40}\b", text))):
        if len(tok) == 128:
            continue
        print("   ", tok, "x", text.count(tok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
