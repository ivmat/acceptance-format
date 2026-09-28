#!/usr/bin/env python3
"""Gate the Kani adoption-template selftest and its five real controls. Stdlib only."""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "protocol_acceptance" / "adoption" / "templates" / "selftest_templates.py"
REQUIRED_MARKERS = (
    "SELFTEST PASS: selftest_templates (5 controls:",
    "filled-pair-check-package-and-coverage",
)


def check(tool: Path) -> list[str]:
    if not tool.is_file():
        return [f"{tool}: missing"]
    label = tool.relative_to(ROOT) if tool.is_relative_to(ROOT) else tool
    result = subprocess.run([sys.executable, str(tool)], capture_output=True, text=True,
                            cwd=str(ROOT), timeout=300)
    out = result.stdout + result.stderr
    if result.returncode != 0:
        return [f"{label}: exit {result.returncode}\n{out.strip()}"]
    return [f"{label}: expected marker {marker!r} not found"
            for marker in REQUIRED_MARKERS if marker not in out]


_FAKE_TOOL_MISSING_MARKER = '''\
import sys
print("SELFTEST PASS: selftest_templates (5 controls:)")
sys.exit(0)
'''


def selftest() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "selftest_templates.py"
        fake.write_text(_FAKE_TOOL_MISSING_MARKER, encoding="utf-8")
        errors = check(fake)
        if not any("expected marker" in error for error in errors):
            print("SELFTEST FAIL: a fake template selftest missing the control marker was not caught")
            ok = False
    if check(TOOL):
        print("SELFTEST FAIL: the real selftest_templates.py does not pass")
        ok = False
    print("SELFTEST PASS: check_adoption_templates (2 controls)" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    errors = check(TOOL)
    for error in errors:
        print("ERROR", error)
    if errors:
        print(f"FAIL check_adoption_templates: {len(errors)} error(s)")
        return 1
    print("PASS check_adoption_templates: selftest_templates.py is green with 5 controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
