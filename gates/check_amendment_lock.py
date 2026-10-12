#!/usr/bin/env python3
"""P13: real-process amendment exclusion and fail-closed recovery controls.

--root selects a source snapshot for red/green proof against the same test entry.
The first worker pauses at successor construction, after its real pointer check;
the second worker must finish before the first is released. No sleeps decide the
winner and neither pointer reads nor lock operations are mocked.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--root', type=Path, default=ROOT)
options, rest = parser.parse_known_args()
ROOT = options.root.resolve()
sys.argv[1:] = rest
sys.path.insert(0, str(ROOT / 'protocol_acceptance/tools'))
import acceptance_protocol as ap
from fixtures.verification_chain import _SPECIFICATION_TOML

# An actual subprocess drives main()/the CLI parser. Only the scheduling point is
# instrumented; this works unchanged against the original unprotected applier.
WORKER = '''
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import acceptance_protocol as ap
ready, release, action = map(str, sys.argv[2:5])
original = ap.apply_amendment_build
def held(*args, **kwargs):
    Path(ready).touch()
    deadline = time.monotonic() + 15
    while not Path(release).exists():
        if time.monotonic() > deadline:
            raise RuntimeError('test coordinator timed out')
        time.sleep(.01)
    if action == 'advance-error':
        def fail_replace(*args):
            raise OSError('injected pointer replace failure')
        ap.os.replace = fail_replace
    elif action == 'build-errors':
        return {}, ['injected build rejection']
    elif action != 'continue':
        raise {'error': RuntimeError, 'interrupt': KeyboardInterrupt,
               'exit': SystemExit}[action](17)
    return original(*args, **kwargs)
ap.apply_amendment_build = held
sys.exit(ap.main(['acceptance_protocol.py', *sys.argv[5:]]))
'''


class AmendmentLock(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='amendment-lock-')
        self.addCleanup(scratch.cleanup)
        self.work = Path(scratch.name)
        self.specification = self.work / 'base.toml'
        self.specification.write_text(_SPECIFICATION_TOML)
        self.base = {'id': 'AC-TEST-1', 'hash': ap.m11.digest_file('specification', self.specification)}
        self.amendment = self.work / 'amend.toml'
        self.amendment.write_text('''
[document]
protocol = "acceptance-protocol/1"
minor = 0
kind = "amendment"
id = "AM-TEST-1"
issued_at = "2026-09-17T09:00:00Z"
issued_by = "producer"
status = "proposed"
[binds]
specification = { id = "AC-TEST-1", hash = "HASH" }
[[change]]
op = "tighten"
requirement = "R2"
reason = "require a control"
[change.proposed]
min_tier = "T3"
weighted_required = true
control_required = true
recipe_required = false
freshness = "any"
independence = "none"
'''.replace('HASH', self.base['hash']))
        self.pointer = self.work / 'acceptance-specification.current'
        self.lock = self.work / 'acceptance-specification.current.lock'
        self.ready, self.release = self.work / 'ready', self.work / 'release'

    def args(self, name='one', pointer=None):
        return ['apply-amendment', str(self.amendment), '--spec', str(self.specification),
                '--pointer', str(pointer or self.pointer), '--out', str(self.work / f'{name}.toml'),
                '--id', f'AC-{name}', '--accept-by', 'Acme Test / lead']

    def run_cli(self, args):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'protocol_acceptance/tools/acceptance_protocol.py'),
                               *args], capture_output=True, text=True, timeout=15)

    def worker(self, action='continue'):
        p = subprocess.Popen([sys.executable, '-B', '-c', WORKER,
                              str(ROOT / 'protocol_acceptance/tools'), str(self.ready),
                              str(self.release), action, *self.args()],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=5)
        self.addCleanup(cleanup)
        deadline = time.monotonic() + 15
        while not self.ready.exists():
            if p.poll() is not None or time.monotonic() > deadline:
                self.fail(f'worker did not reach pointer check: {p.poll()}')
            time.sleep(.01)
        return p

    def race(self, initialized=False, alias=False):
        if initialized:
            self.pointer.write_text(json.dumps(self.base))
        pointer = self.pointer
        if alias:
            pointer = self.work / 'alias.current'
            pointer.symlink_to(self.pointer)
        first = self.worker()
        second = self.run_cli(self.args('two', pointer))
        self.release.touch()
        out, err = first.communicate(timeout=15)
        codes = [first.returncode, second.returncode]
        print(f'P13 race (initialized={initialized}, alias={alias}): exits={codes}')
        self.assertEqual(codes, [0, 1], out + err + second.stdout + second.stderr)
        self.assertIn('amendment lock exists', second.stdout)
        self.assertFalse((self.work / 'two.toml').exists())
        self.assertFalse(self.lock.exists())
        self.assertEqual(json.loads(self.pointer.read_text()), {
            'id': 'AC-one', 'hash': ap.m11.digest_file('specification', self.work / 'one.toml')})
        later = self.run_cli(self.args('two'))
        self.assertEqual(later.returncode, 1, later.stdout + later.stderr)
        self.assertIn('pointer moved', later.stdout)
        self.assertFalse(self.lock.exists())

    def test_race_existing_pointer(self):
        self.race(initialized=True)

    def test_race_first_use(self):
        self.race()

    def test_race_symlink_alias(self):
        self.race(initialized=True, alias=True)

    def test_stale_lock_never_stolen(self):
        self.lock.write_text('pid=999999999\n')
        os.utime(self.lock, (1, 1))
        result = self.run_cli(self.args())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Refusing to steal', result.stdout)
        self.assertIn('manually removing', result.stdout)
        self.assertEqual(self.lock.read_text(), 'pid=999999999\n')
        self.assertFalse(self.pointer.exists())
        self.assertFalse((self.work / 'one.toml').exists())

    def test_unwinding_releases(self):
        for action in ('error', 'interrupt', 'exit'):
            with self.subTest(action=action):
                self.ready.unlink(missing_ok=True)
                self.release.unlink(missing_ok=True)
                worker = self.worker(action)
                self.release.touch()
                worker.communicate(timeout=15)
                self.assertNotEqual(worker.returncode, 0)
                self.assertFalse(self.lock.exists())
                self.assertEqual(json.loads(self.pointer.read_text()), self.base)

    def test_signals_release(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum):
                self.ready.unlink(missing_ok=True)
                worker = self.worker()
                worker.send_signal(signum)
                worker.communicate(timeout=15)
                self.assertEqual(worker.returncode, 128 + signum)
                self.assertFalse(self.lock.exists())
                self.assertEqual(json.loads(self.pointer.read_text()), self.base)

    def test_sigkill_leaves_refusing_lock(self):
        worker = self.worker()
        worker.kill()
        worker.communicate(timeout=15)
        result = self.run_cli(self.args('two'))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Refusing to steal', result.stdout)
        self.assertTrue(self.lock.exists())

    def test_output_failure_releases(self):
        (self.work / 'one.toml').mkdir()
        result = self.run_cli(self.args())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(self.lock.exists())
        self.assertEqual(json.loads(self.pointer.read_text()), self.base)
        (self.work / 'one.toml').rmdir()
        self.assertEqual(self.run_cli(self.args()).returncode, 0)

    def test_advance_failure_releases_and_cleans_temp(self):
        worker = self.worker('advance-error')
        self.release.touch()
        out, err = worker.communicate(timeout=15)
        self.assertEqual(worker.returncode, 1, out + err)
        self.assertIn('injected pointer replace failure', out)
        self.assertNotIn('Traceback', err)
        self.assertFalse(self.lock.exists())
        self.assertEqual(list(self.work.glob('.*.tmp-*')), [])
        self.assertEqual(json.loads(self.pointer.read_text()), self.base)
        # The documented non-transactional residual is observable, not hidden.
        self.assertTrue((self.work / 'one.toml').exists())

    def test_build_rejection_releases(self):
        worker = self.worker('build-errors')
        self.release.touch()
        out, err = worker.communicate(timeout=15)
        self.assertEqual(worker.returncode, 1, out + err)
        self.assertIn('injected build rejection', out)
        self.assertFalse(self.lock.exists())
        self.assertFalse((self.work / 'one.toml').exists())
        self.assertEqual(json.loads(self.pointer.read_text()), self.base)

    def test_invalid_pointer_releases(self):
        self.pointer.write_text('broken JSON')
        result = self.run_cli(self.args())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.pointer.read_text(), 'broken JSON')

    def test_dry_run_releases_without_advance(self):
        result = self.run_cli([*self.args(), '--dry-run'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.lock.exists())
        self.assertFalse((self.work / 'one.toml').exists())
        self.assertEqual(json.loads(self.pointer.read_text()), self.base)


if __name__ == '__main__':
    unittest.main()
