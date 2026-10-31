#!/usr/bin/env python3
"""Smoke the verification wrapper's selftest dispatch without rerunning core fixtures."""
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'format_acceptance/tools'
sys.path.insert(0, str(TOOLS))
import check_core
import check_acceptance


def dispatch_smoke(status):
    argv = [str(TOOLS / 'check_acceptance.py'), '--selftest']
    # Only the expensive battery is replaced: execute the real wrapper __main__,
    # core argument parser and --selftest route, including SystemExit propagation.
    with patch.object(sys, 'argv', argv), \
         patch.object(check_core, 'selftest', return_value=status) as battery, \
         patch.object(check_core, 'main', wraps=check_core.main) as main:
        try:
            runpy.run_path(argv[0], run_name='__main__')
        except SystemExit as exc:
            assert exc.code == status, (exc.code, status)
        else:
            raise AssertionError('wrapper did not propagate SystemExit')
        main.assert_called_once_with(argv, bound_meaning='verification')
        battery.assert_called_once_with()


def main():
    assert check_acceptance.selftest is check_core.selftest, 'wrapper has a separate selftest battery'
    dispatch_smoke(0)
    dispatch_smoke(7)
    # A dispatch that reports success without entering the core battery must fail
    # this same smoke, even though its exit status alone looks green.
    with patch.object(check_core, 'main', return_value=0):
        try:
            dispatch_smoke(0)
        except AssertionError:
            pass
        else:
            raise AssertionError('broken-dispatch control was not detected')
    print('PASS check_acceptance_entry: shared battery, success/failure dispatch, broken dispatch refused')
    return 0


if __name__ == '__main__':
    sys.exit(main())
