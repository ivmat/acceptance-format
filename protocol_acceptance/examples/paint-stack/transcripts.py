"""Normalize machine-local paths before publishing or hashing captured output."""
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
REPO = WORKSPACE.parents[2]


def normalize(text: str) -> str:
    for path, label in ((WORKSPACE, "<WORKSPACE>"), (REPO, "<REPO>"), (Path.home(), "<HOME>")):
        text = text.replace(str(path), label)
    # Kani embeds build-machine Rust source paths as well as local workspace paths.
    return re.sub(r"/(?:Users|home)/[^/\s]+", "<BUILD_HOME>", text)
