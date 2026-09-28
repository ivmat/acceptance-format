#!/usr/bin/env python3
"""Check package-generator build inputs without running evidence commands."""
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location(
        'gen_package', ROOT / 'protocol_acceptance/examples/rust-delivery/gen_package.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    block, missing = generator.build_inputs_block()
    assert not missing and block.count('[[claim.evidence.build_inputs]]') == 2
    with tempfile.TemporaryDirectory(prefix='build-inputs-') as td:
        generator.SCRIPT_DIR = Path(td)
        generator.CRATE_DIR = Path(td) / 'iban-check'
        generator.CRATE_DIR.mkdir()
        for name in generator.REQUIRED_BUILD_INPUT_NAMES:
            (generator.CRATE_DIR / name).write_bytes(b'input bytes\n')
        symlink_block, missing = generator.build_inputs_block()
        assert not missing
        for name in generator.REQUIRED_BUILD_INPUT_NAMES:
            path = Path(td) / name
            assert path.is_symlink() and path.readlink() == Path('iban-check') / name
            path.unlink()
            path.write_bytes((generator.CRATE_DIR / name).read_bytes())
        assert generator.build_inputs_block() == (symlink_block, [])
        for name in generator.REQUIRED_BUILD_INPUT_NAMES:
            path = Path(td) / name
            path.write_bytes(b'differing input\n')
            try:
                generator.build_inputs_block()
            except RuntimeError as exc:
                assert 'differs from the crate build input' in str(exc)
            else:
                raise AssertionError(f'drift accepted: {name}')
            assert path.read_bytes() == b'differing input\n'
            path.write_bytes((generator.CRATE_DIR / name).read_bytes())
    print('PASS check_build_inputs: shipped layout, symlinks and identical copies accepted; both differing copies refused without overwrite (5 controls); no evidence commands run')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
