"""Command-line interface for whole-laptop lighting. GPL-3.0."""
import argparse
import json
import subprocess
import sys

import lighting_service as service

VERSION = (service.ROOT / 'VERSION').read_text().strip() if (service.ROOT / 'VERSION').exists() else 'development'

COLORS = {
    'purple': '8000FF', 'blue': '0066FF', 'cyan': '00FFFF',
    'green': '00FF40', 'pink': 'FF0080', 'red': 'FF0000',
    'amber': 'FF8000', 'white': 'FFFFFF', 'black': '000000',
}


def color_value(value):
    try:
        return service.normalize_color(COLORS.get(value.lower(), value))
    except ValueError:
        raise argparse.ArgumentTypeError('Use a color name or six hex digits, for example purple or 8000FF.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(prog='alienlights', description='One color across all Alienware lights, including the keyboard.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    sub = parser.add_subparsers(dest='command', required=True)
    setcmd = sub.add_parser('set', help='Apply a named or hex color to all lights')
    setcmd.add_argument('color', type=color_value, metavar='COLOR')
    for cmd in (setcmd, sub.add_parser('off', help='Turn all lights off'),
                sub.add_parser('on', help='Restore the last saved color (purple initially)')):
        cmd.add_argument('--dry-run', action='store_true', help='Preview without accessing hardware or saving changes')
    status = sub.add_parser('status', help='Check controller access and show the saved color')
    status.add_argument('--json', action='store_true', help='Print machine-readable status')
    sub.add_parser('colors', help='List named colors')
    sub.add_parser('access', help='Request temporary access to both controllers (administrator authentication)')
    theme = sub.add_parser('theme', help='Apply the current Omarchy theme color now')
    theme.add_argument('--dry-run', action='store_true', help='Show the theme color without changing lights')
    args = parser.parse_args(argv)
    try:
        if args.command == 'theme':
            from theme_sync import sync
            print(sync(dry_run=args.dry_run))
            return 0
        if args.command == 'colors':
            for name, color in COLORS.items():
                print(f'{name:8} #{color}')
            return 0
        if args.command == 'status':
            devices = service.devices()
            ready = all(d['accessible'] for d in devices)
            saved = '#' + service.saved_color()
            if args.json:
                print(json.dumps({'ready': ready, 'saved_color': saved,
                                  'current_color': None, 'devices': devices}, indent=2))
            else:
                print('Ready.' if ready else 'Access needed. Run: alienlights access')
                for d in devices:
                    print(f'{d["name"]}: {d["path"]} — {"accessible" if d["accessible"] else "access required"}')
                print(f'Saved color: {saved} (not a readback of the lights).')
            return 0 if ready else 1
        if args.command == 'access':
            service.enable_access()
            print('Access enabled. You can now set a color.')
            return 0
        color = args.color if args.command == 'set' else '000000' if args.command == 'off' else service.saved_color()
        if args.dry_run:
            print(f'Would set all chassis lights (IDs 0–40) and the whole keyboard to #{color}.')
            return 0
        service.apply_color(color)
        print('Off command sent to all lights.' if color == '000000' else f'Applied #{color} to all lights.')
        if color != '000000':
            try:
                service.save_color(color)
            except OSError as exc:
                print(f'Warning: color applied, but could not save it for next time: {exc}', file=sys.stderr)
        return 0
    except PermissionError:
        print('Access required. Run: alienlights access, then retry.', file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; an in-progress operation may have changed some lights.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
