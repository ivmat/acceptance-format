#!/usr/bin/env python3
"""test_check_content_leaks.py — the content-leak gate's own gate (ported from rs-verified-der).

Every check here is a negative fixture first: a planted violation must be OBSERVED refused, layer
by layer (credential / absolute path / hashed vocabulary), before the baseline/passing cases mean
anything. Vocabulary tests use an injected fixture token, never the real (private) list.

Runs against throwaway `git init` repos in temp dirs with the module's ROOT and BASELINE_PATH
monkeypatched -- no mutation of the real repo tree.

Run:  python3 gates/test_check_content_leaks.py      (pure stdlib; wired into gates/run_all.sh)
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load("check_content_leaks", "check_content_leaks.py")

FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_HOME_PATH = "/ho" + "me/someuser/secret-checkout/notes.txt"
FIXTURE_VOCAB_TOKEN = "zzz_fixture_private_reponame"


def _run_git(root, *args, check=True):
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@example.com",
    )
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=check, env=env,
    )


@contextlib.contextmanager
def repo_fixture(files, extra_vocab_hashes=frozenset(), baseline=None):
    """A throwaway TRACKED tree: `files` = {relpath: text}, all git-added. Monkeypatches gate.ROOT,
    gate.BASELINE_PATH, and (additively) gate.VOCAB_HASHES."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        _run_git(root, "init", "-q")
        for rel, content in files.items():
            fp = root / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                fp.write_bytes(content)
            else:
                fp.write_text(content, encoding="utf-8")
        _run_git(root, "add", "-A")
        old_root, old_vocab, old_baseline_path = gate.ROOT, gate.VOCAB_HASHES, gate.BASELINE_PATH
        gate.ROOT = root
        gate.VOCAB_HASHES = old_vocab | set(extra_vocab_hashes)
        gate.BASELINE_PATH = root / "gates" / "leak_baseline.json"
        if baseline is not None:
            gate.BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
            gate.BASELINE_PATH.write_text(json.dumps(baseline), encoding="utf-8")
        try:
            yield root
        finally:
            gate.ROOT, gate.VOCAB_HASHES, gate.BASELINE_PATH = old_root, old_vocab, old_baseline_path


def run_tree():
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        rc = gate.check_tree()
    return rc, buf_out.getvalue(), buf_err.getvalue()


def run_message(text):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            rc = gate.check_message(path)
        return rc, buf_out.getvalue(), buf_err.getvalue()
    finally:
        os.unlink(path)


class CleanTreePasses(unittest.TestCase):
    def test_clean_repo_passes(self):
        with repo_fixture({"src/lib.rs": "pub fn f() {}\n", "README.md": "a format\n"}):
            rc, out, err = run_tree()
        self.assertEqual(rc, 0, err)
        self.assertIn("PASS check_content_leaks", out)


class PlantedCredentialsRefused(unittest.TestCase):
    def test_aws_key_fails_naming_file_and_layer(self):
        with repo_fixture({"src/lib.rs": f"const K: &str = \"{FAKE_AWS}\";\n"}):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("src/lib.rs", err)
        self.assertIn("credential:aws-akia", err)

    def test_credential_never_baseline_eligible(self):
        # even a baseline entry claiming this credential is "known" must NOT suppress it
        with repo_fixture(
            {"src/lib.rs": f"const K: &str = \"{FAKE_AWS}\";\n"},
            baseline={"src/lib.rs": {"credential:aws-akia": 1}},
        ):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("NEVER baseline-eligible", err)


class PlantedPathsRefused(unittest.TestCase):
    def test_home_path_fails(self):
        with repo_fixture({"src/lib.rs": f"// see {FAKE_HOME_PATH}\n"}):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("path:abs-home", err)


class BaselineMechanism(unittest.TestCase):
    def test_baselined_finding_passes(self):
        h = gate.hash_token(FIXTURE_VOCAB_TOKEN)
        with repo_fixture(
            {"notes.md": f"borrowed from {FIXTURE_VOCAB_TOKEN}\n"},
            extra_vocab_hashes={h},
            baseline={"notes.md": {"vocabulary:hashed-token": 1}},
        ):
            rc, out, err = run_tree()
        self.assertEqual(rc, 0, err)
        self.assertIn("1 pre-existing finding", out)

    def test_new_finding_beyond_baseline_fails(self):
        h = gate.hash_token(FIXTURE_VOCAB_TOKEN)
        with repo_fixture(
            {"notes.md": f"borrowed from {FIXTURE_VOCAB_TOKEN}\n"},
            extra_vocab_hashes={h},
            baseline={},  # nothing baselined -- this is a NEW hit
        ):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("vocabulary:hashed-token", err)
        self.assertIn("NEW leak beyond", err)

    def test_new_file_not_in_baseline_fails(self):
        with repo_fixture(
            {"clean.md": "nothing here\n", "leaky.md": f"see {FAKE_HOME_PATH}\n"},
            baseline={"other-file.md": {"path:abs-home": 1}},
        ):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("leaky.md", err)

    def test_shrinking_baseline_never_penalized(self):
        # baseline says 2 hits were known; only 1 remains (cleanup happened) -- must still pass
        h = gate.hash_token(FIXTURE_VOCAB_TOKEN)
        with repo_fixture(
            {"notes.md": f"only {FIXTURE_VOCAB_TOKEN} once now\n"},
            extra_vocab_hashes={h},
            baseline={"notes.md": {"vocabulary:hashed-token": 2}},
        ):
            rc, out, err = run_tree()
        self.assertEqual(rc, 0, err)

    def test_missing_baseline_file_treated_as_empty(self):
        with repo_fixture({"leaky.md": f"see {FAKE_HOME_PATH}\n"}, baseline=None):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("NEW leak beyond", err)


class HyphenatedCompoundTokenIsCaught(unittest.TestCase):
    """TOKEN_RE keeps `-` in the token class, so a hashed bare name embedded inside a larger
    hyphenated compound (e.g. FIXTURE_VOCAB_TOKEN glued to a date suffix) used to match as ONE
    run whose hash was never in VOCAB_HASHES, and so was MISSED entirely (2026-08-28 fix: also
    hash every hyphen/dot-split sub-token of each run). Watched-fail: before the fix, this
    fixture passed clean; after, it is refused."""

    def test_bare_token_glued_into_a_hyphenated_compound_is_caught(self):
        h = gate.hash_token(FIXTURE_VOCAB_TOKEN)
        compound = f"{FIXTURE_VOCAB_TOKEN}-corr-2026-08"
        with repo_fixture(
            {"notes.md": f"calibration = \"{compound}\"\n"},
            extra_vocab_hashes={h},
            baseline={},
        ):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1, "hyphenated compound containing a hashed bare token must be caught")
        self.assertIn("vocabulary:hashed-token", err)
        self.assertIn("NEW leak beyond", err)


class ScopeIsTrackedFilesOnly(unittest.TestCase):
    def test_untracked_violation_passes_scope_documented(self):
        with repo_fixture({"src/lib.rs": "pub fn f() {}\n"}) as root:
            (root / "scratch.txt").write_text(f"{FAKE_AWS}\n", encoding="utf-8")  # never git-added
            rc, _out, err = run_tree()
        self.assertEqual(rc, 0, err)

    def test_gate_and_test_skipped_by_exact_relpath_only(self):
        with repo_fixture({"src/check_content_leaks.py": f"# {FAKE_HOME_PATH}\n"}):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("path:abs-home", err)

    def test_not_a_git_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_root = gate.ROOT
            gate.ROOT = pathlib.Path(tmp)  # plain dir, no .git
            try:
                rc, _out, err = run_tree()
            finally:
                gate.ROOT = old_root
        self.assertEqual(rc, 1)
        self.assertIn("cannot list tracked files", err)


class ScannedCountIsHonest(unittest.TestCase):
    """The PASS line's coverage claim must be checkable (2026-08-28). It used to print a count
    derived by subtraction and name nothing, while SELF-7's certificate said the scan covered
    "all git-tracked files"."""

    def test_pass_line_counts_only_files_actually_scanned_and_names_the_skips(self):
        files = {
            "src/lib.rs": "pub fn f() {}\n",
            "README.md": "a format\n",
            "docs/x.md": "notes\n",
            # the two exact relpaths the gate skips -- planted with a real path pattern, which
            # must NOT be reported (that is what the skip is for) and must be NAMED as skipped
            "gates/check_content_leaks.py": f"# {FAKE_HOME_PATH}\n",
            "gates/test_check_content_leaks.py": f"# {FAKE_HOME_PATH}\n",
        }
        with repo_fixture(files):
            rc, out, err = run_tree()
        self.assertEqual(rc, 0, err)
        self.assertIn("3 tracked files scanned", out)
        self.assertIn("2 of 5 tracked file(s) skipped by exact relpath", out)
        self.assertIn("gates/check_content_leaks.py", out)
        self.assertIn("gates/test_check_content_leaks.py", out)

    def test_pass_line_says_so_when_nothing_was_skipped(self):
        with repo_fixture({"src/lib.rs": "pub fn f() {}\n"}):
            rc, out, err = run_tree()
        self.assertEqual(rc, 0, err)
        self.assertIn("1 tracked files scanned", out)
        self.assertIn("no files skipped", out)


class UnreadableFilesFailClosed(unittest.TestCase):
    """A tracked file the gate cannot read is a FAILURE naming the file, never a silent skip that
    still counts toward the scanned total (2026-08-28)."""

    # invalid UTF-8: a lone continuation byte, plus a NUL, is not decodable text
    BINARY_BLOB = b"\x00\x01\xff\xfe binary payload \x80\x81\n"

    def test_non_utf8_tracked_file_fails_and_names_the_file(self):
        with repo_fixture({"src/lib.rs": "pub fn f() {}\n", "data/blob.bin": self.BINARY_BLOB}):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("data/blob.bin", err)
        self.assertIn("UNSCANNABLE", err)
        self.assertIn("not valid UTF-8", err)

    def test_credential_inside_a_binary_file_is_still_caught(self):
        # the whole point of scanning credentials over RAW BYTES: before this, a key in a
        # non-UTF-8 file was examined by nothing at all.
        blob = b"\x00\xff prefix " + FAKE_AWS.encode("ascii") + b" \x80 suffix\n"
        with repo_fixture({"data/blob.bin": blob}):
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("credential:aws-akia", err)
        self.assertIn("data/blob.bin", err)

    def test_tracked_but_deleted_from_worktree_fails(self):
        with repo_fixture({"src/lib.rs": "pub fn f() {}\n", "gone.md": "here for now\n"}) as root:
            (root / "gone.md").unlink()
            rc, _out, err = run_tree()
        self.assertEqual(rc, 1)
        self.assertIn("gone.md", err)
        self.assertIn("UNSCANNABLE", err)

    def test_valid_utf8_non_ascii_content_still_passes(self):
        # the fail-closed rule must not fire on legitimate non-ASCII text -- this repo's own spec
        # files are full of it (section signs, em dashes, accented names)
        with repo_fixture({"spec/core.md": "§5 bounds — café naïve\n"}):
            rc, out, err = run_tree()
        self.assertEqual(rc, 0, err)
        self.assertIn("1 tracked files scanned", out)

    def test_update_baseline_refuses_over_an_unreadable_tree(self):
        with repo_fixture({"notes.md": "clean\n", "data/blob.bin": self.BINARY_BLOB}):
            buf_err = io.StringIO()
            with contextlib.redirect_stderr(buf_err):
                rc = gate.update_baseline()
            self.assertEqual(rc, 1)
            self.assertIn("REFUSED", buf_err.getvalue())
            self.assertIn("data/blob.bin", buf_err.getvalue())
            self.assertFalse(gate.BASELINE_PATH.exists())


class CommitMessageMode(unittest.TestCase):
    def test_clean_message_passes(self):
        rc, out, err = run_message("gate: add doc link check\n\nroutine wiring.\n")
        self.assertEqual(rc, 0, err)
        self.assertIn("commit message clean", out)

    def test_credential_in_message_fails(self):
        rc, _out, err = run_message(f"debug: key was {FAKE_AWS}\n")
        self.assertEqual(rc, 1)
        self.assertIn("credential:aws-akia", err)

    def test_path_in_message_fails(self):
        rc, _out, err = run_message(f"ran from {FAKE_HOME_PATH}\n")
        self.assertEqual(rc, 1)
        self.assertIn("path:abs-home", err)

    def test_git_comment_lines_not_scanned(self):
        rc, _out, err = run_message(f"clean subject\n# On branch main {FAKE_HOME_PATH}\n")
        self.assertEqual(rc, 0, err)


class HashMaintenanceMode(unittest.TestCase):
    def test_hash_token_normalizes(self):
        self.assertEqual(gate.hash_token("  MiXeD-Case  "), gate.hash_token("mixed-case"))

    def test_real_hash_list_is_nonempty_wellformed_hex(self):
        self.assertGreater(len(gate.VOCAB_HASHES), 0)
        for h in gate.VOCAB_HASHES:
            self.assertRegex(h, r"^[0-9a-f]{64}$")


class UpdateBaselineMode(unittest.TestCase):
    def test_update_baseline_writes_current_findings(self):
        h = gate.hash_token(FIXTURE_VOCAB_TOKEN)
        with repo_fixture(
            {"notes.md": f"see {FIXTURE_VOCAB_TOKEN}\n"}, extra_vocab_hashes={h}
        ) as root:
            buf_out = io.StringIO()
            with contextlib.redirect_stdout(buf_out):
                rc = gate.update_baseline()
            self.assertEqual(rc, 0)
            written = json.loads((root / "gates" / "leak_baseline.json").read_text())
        self.assertEqual(written, {"notes.md": {"vocabulary:hashed-token": 1}})

    def test_update_baseline_refuses_to_write_credential(self):
        with repo_fixture({"src/lib.rs": f"const K = \"{FAKE_AWS}\";\n"}):
            buf_err = io.StringIO()
            with contextlib.redirect_stderr(buf_err):
                rc = gate.update_baseline()
            self.assertEqual(rc, 1)
            self.assertIn("REFUSED", buf_err.getvalue())
            self.assertFalse(gate.BASELINE_PATH.exists())


if __name__ == "__main__":
    unittest.main()
