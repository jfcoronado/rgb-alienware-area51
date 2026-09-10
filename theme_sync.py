"""Omarchy theme integration using its user hooks. GPL-3.0."""
import argparse
import fcntl
import json
from pathlib import Path
import sys
import tomllib

import lighting_service as service

CURRENT = Path.home() / '.local/state/omarchy/current'
CONFIG = Path.home() / '.config/omarchy/alienware-lights.json'


def theme_color(directory):
    keyboard = directory / 'keyboard.rgb'
    if keyboard.exists():
        try:
            return service.normalize_color(keyboard.read_text().strip()), 'keyboard.rgb'
        except ValueError:
            pass
    with (directory / 'colors.toml').open('rb') as source:
        colors = tomllib.load(source)
    return service.normalize_color(colors['accent']), 'accent'


def enabled():
    if not CONFIG.exists():
        return True
    config = json.loads(CONFIG.read_text())
    value = config.get('enabled', True)
    if not isinstance(value, bool):
        raise ValueError('Theme sync enabled must be true or false.')
    return value


def sync(dry_run=False, automatic=False):
    # Read the current theme after acquiring the lock. Delayed hooks therefore
    # follow the latest theme, never an outdated event argument.
    with (service.ROOT / '.theme-sync.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if automatic and not enabled():
            return 'Theme sync is paused.'
        color, source = theme_color(CURRENT / 'theme')
        theme = (CURRENT / 'theme.name').read_text().strip()
        if dry_run:
            return f'{theme}: #{color} from {source}; no lights changed.'
        service.apply_color(color)
        if color != '000000':
            service.save_color(color)
        return f'Applied {theme} color #{color} to all lights.'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--automatic', action='store_true', help='Honor the enabled preference')
    args = parser.parse_args(argv)
    try:
        print(sync(args.dry_run, args.automatic))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f'Alienware theme sync failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
