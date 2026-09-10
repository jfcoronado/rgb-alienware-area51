"""Shared single-color operations. GPL-3.0; existing protocol tools do the writes."""
import json
import fcntl
import os
from pathlib import Path
import re
import subprocess
import sys

from alienrgb import MODEL, discover

ROOT = Path(__file__).resolve().parent
STATE_DIR = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'alienware-lights'
STATE = STATE_DIR / 'state.json'
LEGACY_STATE = ROOT / '.last-color.json'
KEYBOARD_ID = '0003:00000D62:00001BBC'


def normalize_color(value):
    value = value.removeprefix('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', value):
        raise ValueError('Enter a six-digit color, such as #8000FF.')
    return value.upper()


def devices():
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != MODEL:
        raise RuntimeError('This app is configured for your Alienware 16 Area-51.')
    found = discover()
    chassis = [d for d in found if d['supported']]
    keyboard = [d for d in found if d['hid_id'] == KEYBOARD_ID]
    if len(chassis) != 1 or len(keyboard) != 1:
        raise RuntimeError('Both lighting controllers must be connected. Try again after the laptop finishes starting.')
    descriptor = (Path('/sys/class/hidraw') / Path(keyboard[0]['path']).name / 'device/report_descriptor').read_bytes()
    if bytes.fromhex('85 cc 09 01 15 00 26 ff 00 75 08 95 3f b1 00') not in descriptor:
        raise RuntimeError('The keyboard does not match the tested lighting protocol.')
    return chassis + keyboard


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or 'The controller command failed.')


def apply_color(value):
    color = normalize_color(value)
    # A theme hook and a manual GUI/CLI update must not interleave reports.
    with (ROOT / '.lighting.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _apply_color(color)


def _apply_color(value):
    color = normalize_color(value)
    if any(not d['accessible'] for d in devices()):
        raise PermissionError('Click Enable access, then apply your color again.')
    stages = [
        ('rear bar and power light', [sys.executable, str(ROOT/'alienrgb.py'), 'set', '--lights',
          *map(str, range(28)), '--color', color, '--method', 'action']),
        ('logo, fans and trackpad', [sys.executable, str(ROOT/'alienrgb.py'), 'set', '--lights',
          *map(str, range(28, 41)), '--color', color, '--method', 'action']),
        ('keyboard', [sys.executable, str(ROOT/'keyboard_test.py'), '--color', color]),
    ]
    for name, command in stages:
        try:
            run(command)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f'Could not finish applying to {name}. Some lights may have changed. {exc}') from exc
    return color


def enable_access():
    paths = [d['path'] for d in devices()]
    # Narrow, session-only ACL on the two verified controllers; never run the GUI as root.
    result = subprocess.run(['/usr/bin/pkexec', '/usr/bin/setfacl', '-m',
                             f'u:{os.getuid()}:rw', *paths], capture_output=True,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Access was not enabled. The administrator prompt may have been cancelled.')
    if any(not d['accessible'] for d in devices()):
        raise RuntimeError('Access is still unavailable. Try reopening the app.')


def saved_color():
    for state in (STATE, LEGACY_STATE):
        try:
            return normalize_color(json.loads(state.read_text())['color'])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return '8000FF'


def save_color(color):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps({'color': normalize_color(color)}) + '\n')
    temporary.replace(STATE)

