#!/usr/bin/env python3
"""Content-leak gate — ported from rs-verified-der's gates/check_content_leaks.py, adapted for a
repo whose baseline starts, and must stay, empty.

Every other gate in this repo checks proof/doc structure; none of them would notice a hard-coded
credential, a private absolute path, or a private working-vocabulary word sitting in tracked
source. This gate closes that class, in three layers, plus a commit-message mode (`--message`):

  1. credentials  — key-material / token patterns; scanned in EVERY tracked file, no exemptions,
     NEVER baseline-eligible (see BASELINE below — a credential match always fails, period).
  2. absolute paths — generic `/home/*`, `/Users/*`, `~/repo` prefixes, the personal-machine-path
     class (deliberately not restated here as literal examples).
  3. private vocabulary — a fixed list of private-repo-internal names, stored as SHA-256 hashes of
     the normalized tokens (see rs-verified-der's original for the rationale: a plaintext list
     would itself be a leak vector if this file were ever copied out of a repo that still carried
     those names — so, deliberately, THIS docstring does not restate the words). Add a token with
     `--hash <token>` (prints the hash to embed, never writes the word anywhere).

BASELINE — why this repo starts, and stays, at `{}`:

  This repo was cut fresh from a private working repo, with the leak scrub done BEFORE the first
  commit, not after. `gates/leak_baseline.json` is an explicit empty JSON object — not an absent
  file, which the gate would also treat as empty, but a stated claim that this repo starts clean.
  Unlike a repo that inherits pre-existing findings, there is no budget here: the gate FAILS on
  ANY hit, in any tracked file, full stop. Baselining a new finding in this repo would be
  re-creating, on day one, exactly the debt a fresh cut exists to avoid — so don't. Fix the file
  that triggered the gate; never add an entry to `gates/leak_baseline.json`.

  Credentials are excluded from the (nonexistent) baselining mechanism entirely, structurally, not
  by discipline: `--update-baseline` refuses to write one in, even if asked.

Scope, stated loudly: scans the WORKING-TREE content of `git ls-files`-tracked files (matching this
repo's other gates), skips itself and its test by exact relpath (both legitimately contain the
patterns as source/fixtures) and NAMES those two files on the PASS line, so the coverage claim is
readable rather than asserted. This tree DOES carry an `evidence/` directory (the self-manifest's
run transcripts) and it is scanned like everything else -- PATH_EXEMPT_DIRS stays empty on purpose;
an evidence transcript is exactly the kind of file a private absolute path leaks into.

FAILS CLOSED ON A FILE IT CANNOT READ (2026-08-28). A tracked file whose bytes are not valid UTF-8,
or that cannot be read at all, used to be skipped silently while still being counted as scanned --
so the certificate's "across all git-tracked files" was false by exactly the files most likely to
be hiding something. Credentials are now matched over RAW BYTES, so a binary is still
credential-checked, and any undecodable/unreadable file is reported as a failure naming the file.

Prints PASS/FAIL, exits 0/1, fails closed on git errors. Pure stdlib.

Run:  python3 gates/check_content_leaks.py                   (tree scan against the baseline; wired into gates/run_all.sh)
      python3 gates/check_content_leaks.py --message FILE    (commit-message scan; no baseline -- see check_message)
      python3 gates/check_content_leaks.py --hash TOKEN      (maintenance: print a vocab hash)
      python3 gates/check_content_leaks.py --update-baseline (maintenance: rewrite leak_baseline.json from a fresh tree scan; refuses if any credential is found)
"""
import collections
import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "gates" / "leak_baseline.json"

CREDENTIAL_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws-akia", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("openai-sk", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("anthropic-sk", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}\b")),
    ("github-pat", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("github-fine-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{36,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
]

PATH_PATTERNS = [
    ("abs-home", re.compile(r"/home/[A-Za-z0-9_.-]")),
    ("abs-users", re.compile(r"/Users/[A-Za-z0-9_.-]")),
    ("tilde-repo", re.compile(r"~/repo\b")),
]
# DELIBERATELY EMPTY. This tree does carry an `evidence/` directory (the self-manifest's run
# transcripts, added after this gate was ported), and it is scanned with everything else: a
# transcript captured from a real shell is a prime carrier of a private absolute path, which is the
# opposite of a reason to exempt it. Kept as an empty tuple (rather than deleted) so the mechanism
# is one line to revive if a genuinely exempt directory ever appears.
PATH_EXEMPT_DIRS = ()

# SHA-256 of normalized (strip+lowercase) private-vocabulary tokens -- see module docstring for the
# seed list and rationale. Regenerate/extend with `--hash <token>`.
VOCAB_HASHES = {
    "7902e9d10689e328349417ba2cb40cbb0d79587a2e5f4e38f555b186a46f92e7",
    "fd65e22d139c4255e091534e8825ce34684cb03f609696049df50c2449da5902",
    "f0435255497c74aefda7f8efb9029dc06eb3063175104cf766e89452ebc22919",
    "7633a18ffd565c7d81bd10337b9a6a2f773b6b797c7fd0d6eab027f82f60562e",
    "c88a27d0bdf6023830af792292e118374bece4ade9aa94bb535ce7f7f3b05cf2",
    "b3f6a67e041389bbd013b30a3c4587df567a5e77315214ac3b539b7ddba76331",
    "bd1b16004d22b1a8de82b70f369bd2b7c7fbeecab53706e47bb9e814274daab5",
    "5e5b62b6117ba77578a671150ace15cea220d00dedba186ab56c816b107ccbcc",
    "97d991b384c179398fef7119cb52a6c89d644487e98b0bfbe56399f2059450cd",
    "554eabe6f71c7f467dd1a2d2697617e1cb6f3f5a8911b6c1650a2cd4a1018cdf",
    "349cf9765467015a1e3cc89163cfdf471451ad5c4c63c7faed080ab58bd713c3",
    "c857d09db23e6822e3600bc06ad8d58f92ed62bc8efd81c753f77048662cb97d",
    "e12ce8285efc67c6d93d3a122e2589ed95089bcbb775ba5634d94e2b8385db07",
    "c9ad8f2cc1294afa0ef22fc2c019ff7243cdd272b2147ddca3f34c5036b05768",
    "09cf980b5ff304ac11b7f6d2c5c263da2a867425798ef5cc5d2ebcf55c4fcd23",
    "5d72436256ada53828b51895a94bb8489e9f1ac4fe937a8024ef1594e7045ff6",
    "57de4cf40144bdf7d00010f2f5557a7d642c2b9705309bfade167dd313e2ca93",
    # Extension 2026-08-25: four additional tokens (categories withheld, per the discipline above).
    "ddcee5a447c418b788dee9f2f62969d9b7ad373987bb91a5dcedc20fa6f3cb4a",
    "b0a9d642d12f553129c39513f7ce26058c34ba4b9062475a8eaac157603e1233",
    # (one token removed 2026-08-29: its subject became PUBLIC by owner act, so it is
    # no longer private vocabulary; guarding a public name only breeds false positives)
    "dfb316701857783dac69a14d1fe3fd60cff21d56e830baf7f0e3871bd73eee39",
}

TOKEN_RE = re.compile(r"[a-z0-9_-]+")

# This gate and its test contain every pattern above as source/fixtures; exact relpaths only, so a
# violation cannot be smuggled by reusing the basename elsewhere in the tree.
SKIP_PATHS = {"gates/check_content_leaks.py", "gates/test_check_content_leaks.py"}


def hash_token(token):
    return hashlib.sha256(token.strip().lower().encode("utf-8")).hexdigest()


def scan_credentials(text):
    """The credential layer alone: list of pattern names that matched.

    Split out so the tree scan can run this layer over a file's RAW BYTES (decoded
    lossily) while the path/vocabulary layers run over its decoded text -- a binary or
    otherwise non-UTF-8 file must still be credential-checked, and before 2026-08-28 it was
    checked by nothing at all."""
    return [name for name, rx in CREDENTIAL_PATTERNS if rx.search(text)]


def scan_text(text, relpath=None, path_exempt=False, include_credentials=True):
    """All findings in one string: list of (relpath-or-None, layer:name, evidence).

    `include_credentials=False` is for the tree scan, which has already run that layer over the
    raw bytes and must not double-count it."""
    findings = []
    if include_credentials:
        for name in scan_credentials(text):
            findings.append((relpath, f"credential:{name}", ""))
    if not path_exempt:
        for name, rx in PATH_PATTERNS:
            m = rx.search(text)
            if m:
                findings.append((relpath, f"path:{name}", m.group(0)))
    # TOKEN_RE keeps `-` IN the token class, so a hyphenated compound (e.g. "foo-bar-2026-08")
    # matches as ONE run, not four -- a hashed bare name never matches its own hyphenated/dotted
    # compounds unless each run is also split and its sub-tokens checked. `.` is never inside a
    # TOKEN_RE match (it is not in the character class), so a run never itself contains a dot --
    # splitting on both here is for symmetry/robustness, not because it is reachable today.
    hits = set()
    for run in TOKEN_RE.findall(text.lower()):
        candidates = {run}
        candidates.update(p for p in re.split(r"[.-]", run) if p)
        for cand in candidates:
            if hash_token(cand) in VOCAB_HASHES:
                hits.add(cand)
    for _ in sorted(hits):
        # deliberately do NOT print the matched word (that would re-leak it into logs the moment
        # the gate fires in CI output someone pastes); the file+layer is enough to find it
        findings.append((relpath, "vocabulary:hashed-token", ""))
    return findings


def tracked_files():
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True, check=True,
    )
    return [p for p in out.stdout.decode("utf-8").split("\0") if p]


def load_baseline():
    if not BASELINE_PATH.exists():
        return {}
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _collect(files):
    """Returns (credential_hits, counts, scanned, unreadable):

      credential_hits  [(relpath, layer, evidence)] -- matched over RAW BYTES, so a binary file is
                       still credential-checked.
      counts           counts[relpath][layer] = n, for the non-credential layers, which need real
                       text (a token list, an absolute path) and so run on the decoded content.
      scanned          the relpaths actually examined on every layer -- what the PASS line reports.
      unreadable       [(relpath, reason)] -- tracked files that could not be decoded or read at
                       all. A FAILURE, never a silent skip: these used to `continue` while still
                       being counted as scanned, so "across all git-tracked files" was false for
                       precisely the files whose content nobody could see.
    """
    credential_hits = []
    counts = collections.defaultdict(collections.Counter)
    scanned = []
    unreadable = []
    for rel in files:
        if rel in SKIP_PATHS:
            continue
        p = ROOT / rel
        try:
            raw = p.read_bytes()
        except OSError as e:
            # deleted-in-worktree, unreadable permissions, a dangling symlink: nothing was
            # examined, so nothing may be claimed.
            unreadable.append((rel, f"cannot read ({e.__class__.__name__})"))
            continue

        # Credentials, layer 1: over the raw bytes, decoded lossily so undecodable bytes become
        # U+FFFD -- a NON-word character, which is the right neighbour for the \b-anchored patterns
        # when a key is embedded in binary. Every credential pattern is pure ASCII, so this decode
        # cannot manufacture or hide a match in valid text: for a valid-UTF-8 file it is identical
        # to a strict decode.
        for name in scan_credentials(raw.decode("utf-8", errors="replace")):
            credential_hits.append((rel, f"credential:{name}", ""))

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            unreadable.append((rel, f"not valid UTF-8 (byte {e.start}: {e.reason})"))
            continue

        scanned.append(rel)
        exempt = rel.startswith(PATH_EXEMPT_DIRS) if PATH_EXEMPT_DIRS else False
        for _rel, layer, evidence in scan_text(
            text, rel, path_exempt=exempt, include_credentials=False
        ):
            counts[rel][layer] += 1
    return credential_hits, counts, scanned, unreadable


def check_tree():
    try:
        files = tracked_files()
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"FAIL check_content_leaks: cannot list tracked files ({e})", file=sys.stderr)
        return 1

    credential_hits, counts, scanned, unreadable = _collect(files)
    baseline = load_baseline()

    over_baseline = []
    baselined_total = 0
    for rel, layer_counts in counts.items():
        base_file = baseline.get(rel, {})
        for layer, n in layer_counts.items():
            b = base_file.get(layer, 0)
            if n > b:
                over_baseline.append((rel, layer, n, b))
            baselined_total += min(n, b)

    if credential_hits or over_baseline or unreadable:
        lines = []
        for rel, layer, ev in credential_hits:
            lines.append(f"{rel}: {layer}" + (f" ({ev})" if ev else "") + " [credentials are NEVER baseline-eligible]")
        for rel, layer, n, b in over_baseline:
            lines.append(f"{rel}: {layer} -- {n} hit(s) found, {b} baselined (NEW leak beyond gates/leak_baseline.json)")
        for rel, reason in unreadable:
            lines.append(
                f"{rel}: UNSCANNABLE -- {reason}. A tracked file this gate cannot read is not a "
                f"file it can vouch for: fail closed, never skip (its credential layer DID run "
                f"over the raw bytes and found nothing, which is not the same as clean)"
            )
        print("FAIL check_content_leaks:\n  " + "\n  ".join(lines), file=sys.stderr)
        return 1

    baseline_note = (
        f"; {baselined_total} pre-existing finding(s) still within gates/leak_baseline.json "
        "-- NOT clean; this repo's baseline is meant to stay empty, so this should never happen"
        if baselined_total else "; baseline is empty"
    )
    # The count is the number of files ACTUALLY examined on every layer, and the skipped ones are
    # named rather than subtracted silently -- the whole defect this line used to carry was a
    # coverage claim a reader could not check (SELF-7 says "across all git-tracked files").
    skipped = sorted(SKIP_PATHS & set(files))
    skip_note = (
        f"; {len(skipped)} of {len(files)} tracked file(s) skipped by exact relpath "
        f"(this gate and its own fixtures, which contain every pattern as source): "
        + ", ".join(skipped)
        if skipped else "; no files skipped"
    )
    print(
        f"PASS check_content_leaks: {len(scanned)} tracked files scanned"
        f"{baseline_note}{skip_note}"
    )
    return 0


def check_message(msg_path):
    try:
        text = pathlib.Path(msg_path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"FAIL check_content_leaks --message: cannot read {msg_path} ({e})", file=sys.stderr)
        return 1
    # comment lines are stripped by git before the message is recorded -- don't scan them
    text = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    bad = scan_text(text, path_exempt=False)  # no exemptions, no baseline: a message is never a build log
    if bad:
        lines = "\n  ".join(f"commit message: {layer}" + (f" ({ev})" if ev else "") for _r, layer, ev in bad)
        print(f"FAIL check_content_leaks (commit message):\n  {lines}", file=sys.stderr)
        return 1
    print("PASS check_content_leaks: commit message clean")
    return 0


def update_baseline():
    try:
        files = tracked_files()
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"FAIL check_content_leaks --update-baseline: cannot list tracked files ({e})", file=sys.stderr)
        return 1
    credential_hits, counts, _scanned, unreadable = _collect(files)
    if credential_hits:
        lines = "\n  ".join(f"{rel}: {layer}" for rel, layer, _ev in credential_hits)
        print(
            "REFUSED --update-baseline: credential hit(s) present -- fix these, never baseline them:\n  "
            + lines,
            file=sys.stderr,
        )
        return 1
    if unreadable:
        # Same fail-closed rule as check_tree: a baseline written over a tree the gate could not
        # fully read would record "known findings" for files nothing examined.
        lines = "\n  ".join(f"{rel}: {reason}" for rel, reason in unreadable)
        print(
            "REFUSED --update-baseline: tracked file(s) this gate cannot read -- a baseline over "
            "a partially-scanned tree records nothing about them:\n  " + lines,
            file=sys.stderr,
        )
        return 1
    new_baseline = {rel: dict(layer_counts) for rel, layer_counts in counts.items() if layer_counts}
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(new_baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    total = sum(sum(lc.values()) for lc in new_baseline.values())
    print(f"wrote gates/leak_baseline.json: {len(new_baseline)} file(s), {total} finding(s)")
    return 0


def main(argv):
    if len(argv) == 3 and argv[1] == "--message":
        return check_message(argv[2])
    if len(argv) == 3 and argv[1] == "--hash":
        print(hash_token(argv[2]))
        return 0
    if len(argv) == 2 and argv[1] == "--update-baseline":
        return update_baseline()
    if len(argv) == 1:
        return check_tree()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
