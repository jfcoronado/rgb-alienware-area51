#!/usr/bin/env python3
"""Experimental whole-keyboard static color for AA16250 / 0d62:1bbc.

GPL-3.0. Protocol: AlienFX SDK SetGlobalEffects, API_V5; ProfilesDialog.cpp
ge_types5 maps Static to 1. No individual key IDs are used.
"""
import argparse
import ctypes as C
import os
from pathlib import Path
import sys

from alienrgb import Controller, MODEL, discover, parse_color


def reports(rgb):
    def report(*values):
        return bytes(values) + bytes(64-len(values))
    return [
        report(0xcc, 0x94),
        report(0xcc, 0x83, 0x38, 0x9c, 100),
        report(0xcc, 0x80, 1, 7, 0, 0, 1, 1, 1, 0, *rgb, *rgb),
        report(0xcc, 0x8b, 1, 0xff),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--color', type=parse_color, default=(255, 0, 0))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    data = reports(args.color)
    if args.dry_run:
        for r in data:
            print(r.hex(' '))
        return
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != MODEL:
        raise RuntimeError('Unexpected laptop model')
    matches = [d for d in discover() if d['hid_id'] == '0003:00000D62:00001BBC']
    if len(matches) != 1:
        raise RuntimeError('Expected one 0d62:1bbc keyboard')
    path = matches[0]['path']
    descriptor = (Path('/sys/class/hidraw') / Path(path).name / 'device/report_descriptor').read_bytes()
    if bytes.fromhex('85 cc 09 01 15 00 26 ff 00 75 08 95 3f b1 00') not in descriptor:
        raise RuntimeError('Keyboard does not have the expected 64-byte feature report')
    if not os.access(path, os.R_OK | os.W_OK):
        raise RuntimeError(f'Temporary access is required for {path}')
    controller = Controller(path)
    try:
        send = controller.lib.hid_send_feature_report
        send.argtypes = [C.c_void_p, C.POINTER(C.c_ubyte), C.c_size_t]
        send.restype = C.c_int
        for r in data:
            buf = (C.c_ubyte * len(r)).from_buffer_copy(r)
            count = send(controller.handle, buf, len(r))
            if count != len(r):
                raise RuntimeError(f'Keyboard report failed ({count}): {controller.error()}')
        print('Whole-keyboard static color sent. Visible confirmation is required.')
    finally:
        controller.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, AttributeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
