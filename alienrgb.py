#!/usr/bin/env python3
"""Small Linux AlienFX v4 experiment for the AA16250's 187c:0551 controller.

Protocol adapted from tr1xem/alienfx-linux (GPL-3.0); see SOURCES.md.
"""
import argparse
import ctypes as C
import ctypes.util
import json
import os
from pathlib import Path
import sys
import time

MODEL = "Alienware 16 Area-51 AA16250"
HID_ID = "0003:0000187C:00000551"
DESCRIPTOR = bytes.fromhex(
    "06 00 ff 09 01 a1 01 15 00 26 ff 00 75 08 95 21 09 01 81 00 09 01 91 00 c0"
)

# A bounded visual experiment, not a discovered hardware zone map.
MAP_GROUPS = [
    (list(range(0, 4)), (255, 0, 0), 'red'),
    (list(range(4, 8)), (0, 255, 0), 'green'),
    (list(range(8, 12)), (255, 255, 0), 'yellow'),
    (list(range(12, 16)), (255, 0, 255), 'magenta'),
    (list(range(16, 20)), (255, 255, 255), 'white'),
]
EXTRA_MAP_GROUPS = [
    (list(range(20, 24)), (255, 0, 0), 'red'),
    (list(range(24, 28)), (0, 255, 0), 'green'),
    (list(range(28, 32)), (255, 0, 255), 'magenta'),
]


def discover():
    devices = []
    for entry in sorted(Path('/sys/class/hidraw').glob('*')):
        info = dict(line.split('=', 1) for line in
                    (entry / 'device/uevent').read_text().splitlines() if '=' in line)
        if info.get('HID_ID') not in (HID_ID, '0003:00000D62:00001BBC'):
            continue
        path = '/dev/' + entry.name
        supported = (info['HID_ID'] == HID_ID and
                     (entry / 'device/report_descriptor').read_bytes() == DESCRIPTOR)
        devices.append(dict(path=path, name=info.get('HID_NAME'),
                            hid_id=info['HID_ID'], supported=supported,
                            accessible=os.access(path, os.R_OK | os.W_OK)))
    return devices


def packet(*data):
    if len(data) > 34:
        raise ValueError('Report too long')
    return bytes(data) + bytes(34 - len(data))


def color_reports(light, rgb):
    if not 0 <= light <= 255:
        raise ValueError('Light ID must be between 0 and 255')
    if len(rgb) != 3 or any(not 0 <= value <= 255 for value in rgb):
        raise ValueError('RGB channels must be between 0 and 255')
    return [
        packet(0, 3, 0x21, 0, 4, 0xff, 0xff),
        packet(0, 3, 0x21, 0, 1, 0xff, 0xff),
        packet(0, 3, 0x27, *rgb, 0, 1, light),
        packet(0, 3, 0x21, 0, 3, 0xff, 0xff),
    ]


def parse_color(text):
    value = text.removeprefix('#')
    if len(value) != 6:
        raise argparse.ArgumentTypeError('Use six hex digits, e.g. 00FF00')
    try:
        rgb = tuple(bytes.fromhex(value))
        if len(rgb) != 3:
            raise ValueError('Invalid hex color')
        return rgb
    except ValueError:
        raise argparse.ArgumentTypeError('Use six hex digits, e.g. 00FF00') from None


def action_reports(light, rgb):
    return group_action_reports([light], rgb)


def group_action_reports(lights, rgb):
    # The reference AWCC zone probe uses animation 0 and explicit undimming.
    if not 1 <= len(lights) <= 28 or len(set(lights)) != len(lights):
        raise ValueError('Choose 1 to 28 distinct light IDs')
    for light in lights:
        color_reports(light, rgb)
    return [
        packet(0, 3, 0x26, 0, 0, len(lights), *lights),
        packet(0, 3, 0x21, 0, 1, 0, 0),
        packet(0, 3, 0x23, 1, 0, len(lights), *lights),
        packet(0, 3, 0x24, 0, 0, 1, 0, 2, *rgb),
        packet(0, 3, 0x21, 0, 3, 0, 0),
    ]


def mapping_groups(extended=False, detail=False):
    if detail:
        colors = [((255, 0, 0), 'red'), ((0, 255, 0), 'green'),
                  ((0, 0, 255), 'blue'), ((255, 255, 255), 'white')]
        return MAP_GROUPS + EXTRA_MAP_GROUPS[:1] + [
            ([light], *colors[(light - 24) % 4]) for light in range(24, 32)]
    return MAP_GROUPS + EXTRA_MAP_GROUPS if extended else MAP_GROUPS


def mapping_reports(extended=False, detail=False):
    groups = mapping_groups(extended, detail)
    reports = []
    for lights, color, _ in groups:
        reports.append(group_action_reports(lights, color)[0])
    reports.append(packet(0, 3, 0x21, 0, 1, 0, 0))
    for lights, color, _ in groups:
        reports.extend(group_action_reports(lights, color)[2:4])
    reports.append(packet(0, 3, 0x21, 0, 3, 0, 0))
    return reports


class Controller:
    def __init__(self, path):
        name = ctypes.util.find_library('hidapi-hidraw')
        if not name:
            raise RuntimeError('The hidapi library is missing')
        self.lib = C.CDLL(name)
        self.lib.hid_open_path.argtypes = [C.c_char_p]
        self.lib.hid_open_path.restype = C.c_void_p
        self.lib.hid_close.argtypes = [C.c_void_p]
        self.lib.hid_close.restype = None
        self.lib.hid_error.argtypes = [C.c_void_p]
        self.lib.hid_error.restype = C.c_wchar_p
        for symbol in ('hid_get_input_report', 'hid_send_output_report'):
            func = getattr(self.lib, symbol)
            func.argtypes = [C.c_void_p, C.POINTER(C.c_ubyte), C.c_size_t]
            func.restype = C.c_int
        self.handle = self.lib.hid_open_path(path.encode())
        if not self.handle:
            raise RuntimeError('Cannot open ' + path + ': ' + self.error())

    def error(self):
        return self.lib.hid_error(self.handle) or 'unknown HID error'

    def close(self):
        self.lib.hid_close(self.handle)

    def status(self):
        buf = (C.c_ubyte * 34)()
        count = self.lib.hid_get_input_report(self.handle, buf, 34)
        if count < 3:
            raise RuntimeError('Status read failed: ' + self.error())
        return buf[2], bytes(buf[:count])

    def ready(self, allow_zero_status=False):
        deadline = time.monotonic() + 2
        while True:
            status, raw = self.status()
            if status == 0x21:
                return raw
            if allow_zero_status and raw == bytes(34):
                print('Controller returned a full zero status report; attempting the requested experimental color transaction.', file=sys.stderr)
                return raw
            if status != 0x22:
                raise RuntimeError(f'Unexpected status 0x{status:02x}; no color sent. Report: {raw.hex(" ")}')
            if time.monotonic() >= deadline:
                raise RuntimeError('Controller stayed busy; no color sent')
            time.sleep(0.05)

    def send(self, report):
        buf = (C.c_ubyte * len(report)).from_buffer_copy(report)
        count = self.lib.hid_send_output_report(self.handle, buf, len(report))
        if count != len(report):
            raise RuntimeError(f'Output report failed ({count} bytes): ' + self.error())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('detect', help='List RGB devices without opening them')
    commands.add_parser('status', help='Read the chassis controller status')
    mapcmd = commands.add_parser('map', help='Color IDs 0–19 in five groups for visual identification')
    mapcmd.add_argument('--dry-run', action='store_true')
    mapcmd.add_argument('--extended', action='store_true', help='Include candidate IDs 20–31 while retaining the first pattern')
    mapcmd.add_argument('--detail', action='store_true', help='Give IDs 24–31 individual colors to identify the logo, fans, and power light')
    setcmd = commands.add_parser('set', help='Set one experimental numeric light ID')
    selection = setcmd.add_mutually_exclusive_group(required=True)
    selection.add_argument('--light', type=int, choices=range(256), metavar='0..255')
    selection.add_argument('--lights', type=int, nargs='+', choices=range(256), metavar='0..255',
                           help='Set several IDs together; requires --method action')
    setcmd.add_argument('--color', type=parse_color, required=True, metavar='RRGGBB')
    setcmd.add_argument('--dry-run', action='store_true', help='Print reports without accessing hardware')
    setcmd.add_argument('--method', choices=('direct', 'action'), default='direct',
                        help='Action uses a static animation and explicitly undims the selected light')
    setcmd.add_argument('--allow-zero-status', action='store_true',
                        help='Experimentally proceed on a full all-zero status report; does not bypass read errors or busy status')
    args = parser.parse_args(argv)
    if args.command == 'map':
        reports = mapping_reports(args.extended, args.detail)
    if args.command == 'set':
        if args.lights is not None:
            if args.method != 'action':
                parser.error('--lights requires --method action')
            try:
                reports = group_action_reports(args.lights, args.color)
            except ValueError as exc:
                parser.error(str(exc))
        else:
            reports = (action_reports if args.method == 'action' else color_reports)(args.light, args.color)
    if args.command in ('set', 'map') and args.dry_run:
        for report in reports:
            print(report.hex(' '))
        return 0
    devices = discover()
    if args.command == 'detect':
        print(json.dumps(devices, indent=2))
        return 0
    model = Path('/sys/class/dmi/id/product_name').read_text().strip()
    if model != MODEL:
        raise RuntimeError('This prototype only enables hardware access on ' + MODEL)
    supported = [d for d in devices if d['supported']]
    if len(supported) != 1:
        raise RuntimeError('Expected exactly one 187c:0551 controller with the verified report descriptor')
    device = supported[0]
    if not device['accessible']:
        raise RuntimeError(f'Access required for {device["path"]}. See README.md for the temporary access command.')
    controller = Controller(device['path'])
    try:
        if args.command == 'status':
            status, raw = controller.status()
            print(f'Status: 0x{status:02x} (21=ready, 22=busy); report: {raw.hex(" ")}')
        else:
            if args.command == 'set' and args.method == 'direct':
                controller.ready(allow_zero_status=args.allow_zero_status)
            # The reference action probe does not poll the passive status buffer,
            # which may contain a previous query reply instead of a ready state.
            for report in reports:
                controller.send(report)
            if args.command == 'map':
                for lights, _, name in mapping_groups(args.extended, args.detail):
                    print(f'IDs {lights[0]}–{lights[-1]}: {name}')
                print('Mapping pattern sent. Physical sections require visual confirmation.')
            else:
                print(f'Color command delivered to light IDs {args.lights if args.lights is not None else [args.light]}. Check the laptop to confirm the visible result.')
    finally:
        controller.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, AttributeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
