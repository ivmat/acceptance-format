"""Code binding: admission, git identity and a clean retrospective subject."""
import sys
from pathlib import Path
import re
import tomllib
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from check_core import Finding


def declaration(name):
    path = Path(__file__).resolve().parents[2] / "profiles" / "bindings" / (name + ".md")
    result = {}
    for block in re.findall(r"```toml\s*\n(.*?)```", path.read_text(), re.S):
        result.update(tomllib.loads(block))
    return result


DECLARATION = declaration("code")
ADMITS = frozenset(DECLARATION["admits"])
IDENTITY = frozenset(DECLARATION["identity"])


def check(doc, ctx):
    subject = doc.get("subject", {})
    if not isinstance(subject, dict):
        return []  # class shape check owns malformed tables
    findings = []
    if subject.get("kind") not in ADMITS:
        findings.append(Finding("error", "B14: code does not admit subject kind"))
    if subject.get("mode", "retrospective") == "retrospective":
        if "commit" not in subject or "components" in subject:
            findings.append(Finding("error", "B1: code requires git-revision identity"))
        if subject.get("dirty") is not False:
            findings.append(Finding("error", "B1: code retrospective subject requires dirty = false"))
    return findings


if __name__ == "__main__":
    from fixtures.binding_cases import selftest
    sys.exit(selftest("code") if sys.argv[1:] == ["--selftest"] else 2)
