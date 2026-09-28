#!/usr/bin/env python3
"""Compatibility entry point with the verification meaning explicitly bound."""
import sys
import check_core
verification = check_core._module(check_core.MODULE_ROOT / "profiles" / "verification.py", "meaning")


def validate(path, strict, strict_weight=False, **kwargs):
    kwargs.setdefault("bound_meaning", "verification")
    return check_core.validate(path, strict, strict_weight, **kwargs)


def __getattr__(name):
    if hasattr(check_core, name):
        return getattr(check_core, name)
    # Existing protocol consumers use these declarations; their owner is the meaning module.
    return getattr(verification, name)


if __name__ == "__main__":
    sys.exit(check_core.main(sys.argv, bound_meaning="verification"))
