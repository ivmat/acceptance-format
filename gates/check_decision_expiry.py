#!/usr/bin/env python3
"""Regression gate for the rust-delivery shipped decision's UTC expiry. `run_all.sh` already runs
`check-decision --effect --allow-conditions --now 2026-09-28` on the shipped decision, proving it
is effect-eligible on a date inside its validity window; this gate is an ADDITIONAL, independent
assertion, checked independently of that CLI's own reasoning: `[validity].stale_after` MUST equal
`[document].issued_at` + the bound contract's `[acceptance].stale_after` DURATION, computed in
UTC -- the exact arithmetic an earlier defect (`make_decision.py` calling
`datetime.datetime.now(...)` twice, once for issuance and again for the expiry base) got wrong by
one day. That defect was silent: the shipped decision still validated and was still (barely)
unexpired, so nothing else in the suite caught it.

Duplicates `acceptance_protocol.py`'s `duration_to_timedelta` approximation (Y=365d, M=30d) rather
than importing it, so this gate verifies the shipped file's arithmetic independently of the tool
under test, the same way a second implementation of a check is worth more than re-running the
first one.

Stdlib only. Prints PASS/FAIL, exits 0/1.
"""
from __future__ import annotations

import datetime
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
RD = ROOT / "protocol_acceptance/examples/rust-delivery"

_ISO8601_DURATION_RE = re.compile(
    r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?"
    r"(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
)


def duration_to_timedelta(s: str) -> datetime.timedelta:
    m = _ISO8601_DURATION_RE.match(s)
    if not m:
        raise ValueError(f"not an ISO-8601 duration: {s!r}")
    y, mo, w, d, h, mi, sec = (int(g) if g else 0 for g in m.groups())
    days = y * 365 + mo * 30 + w * 7 + d
    return datetime.timedelta(days=days, hours=h, minutes=mi, seconds=sec)


def expected_expiry(issued_at: str, duration: str) -> str:
    issued_dt = datetime.datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    return (issued_dt + duration_to_timedelta(duration)).date().isoformat()


def expiry_matches(issued_at: str, duration: str, actual_expiry: str) -> tuple[bool, str]:
    expected = expected_expiry(issued_at, duration)
    return actual_expiry == expected, expected


def main() -> int:
    contract = tomllib.loads((RD / "acceptance-contract.toml").read_text())
    decision = tomllib.loads((RD / "acceptance-decision.toml").read_text())
    issued_at = decision["document"]["issued_at"]
    duration = contract["acceptance"]["stale_after"]
    actual = decision["validity"]["stale_after"]

    ok, expected = expiry_matches(issued_at, duration, actual)
    errors = []
    if not ok:
        errors.append(
            f"shipped decision expiry drift: issued_at={issued_at!r} + [acceptance].stale_after="
            f"{duration!r} (UTC) = {expected!r}, but [validity].stale_after = {actual!r}"
        )

    # Able-to-fail control: the SAME comparison, given a deliberately one-day-drifted expiry
    # (the exact shape of the fixed defect), must report a mismatch -- proving this assertion is
    # a real check, not vacuously true for this file's particular values.
    drifted = (datetime.date.fromisoformat(expected) + datetime.timedelta(days=1)).isoformat()
    control_ok, _ = expiry_matches(issued_at, duration, drifted)
    if control_ok:
        errors.append(
            f"able-to-fail control failed: a one-day-drifted expiry {drifted!r} was accepted as "
            f"matching {expected!r}"
        )

    if errors:
        for e in errors:
            print("FAIL", e)
        return 1
    print(
        f"PASS check_decision_expiry: rust-delivery issued_at={issued_at!r} + [acceptance]."
        f"stale_after={duration!r} (UTC) == [validity].stale_after={actual!r}; a one-day-drifted "
        f"expiry {drifted!r} is correctly refused by the same comparison"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
