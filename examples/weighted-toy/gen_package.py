#!/usr/bin/env python3
"""Regenerate the protocol binding; retain the historical subject/evidence receipt.

The unchanged slug implementation and its recorded 2026-08-28 test/control remain
historical evidence. This operation makes no claim of a new evidence execution.
"""
from pathlib import Path
import re
import sys
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'protocol_acceptance/tools/m11.py').is_file())
sys.path.insert(0, str(ROOT / 'protocol_acceptance/tools'))
import m11

spec = HERE / 'acceptance-specification.toml'
package = HERE / 'acceptance.toml'
doc = tomllib.loads(spec.read_text())
assert doc['document']['protocol'] == 'acceptance-protocol/1'
assert doc['document']['kind'] == 'specification'
assert tomllib.loads(package.read_text())['specification']['id'] == doc['document']['id']
value = m11.digest_file('specification', spec)
text, count = re.subn(r'(?m)^hash = "specification:sha-512:[0-9a-f]+"$',
                     f'hash = "{value}"', package.read_text())
assert count == 1
package.write_text(text)
print('PASS weighted-toy: specification binding regenerated; historical evidence retained')
