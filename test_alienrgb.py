import argparse
import unittest
from unittest.mock import Mock, patch

import alienrgb as rgb


class ProtocolTests(unittest.TestCase):
    def test_detailed_mapping_isolates_tail_ids(self):
        reports = rgb.mapping_reports(detail=True)
        selections = [p for p in reports if p[2] == 0x23]
        self.assertEqual([list(p[6:6+p[5]]) for p in selections[-8:]], [[i] for i in range(24, 32)])
        self.assertEqual([p[4] for p in reports if p[2] == 0x21], [1, 3])
        self.assertTrue(all(len(p) == 34 for p in reports))

    def test_extended_mapping_covers_32_ids_without_extra_commits(self):
        reports = rgb.mapping_reports(extended=True)
        self.assertTrue(all(len(p) == 34 for p in reports))
        selections = [p for p in reports if p[2] == 0x23]
        self.assertEqual([i for p in selections for i in p[6:6+p[5]]], list(range(32)))
        self.assertEqual([p[4] for p in reports if p[2] == 0x21], [1, 3])

    def test_mapping_uses_one_animation_and_exactly_twenty_ids(self):
        reports = rgb.mapping_reports()
        self.assertTrue(all(len(p) == 34 for p in reports))
        self.assertEqual([p[4] for p in reports if p[2] == 0x21], [1, 3])
        selections = [p for p in reports if p[2] == 0x23]
        self.assertEqual([i for p in selections for i in p[6:6+p[5]]], list(range(20)))
        self.assertEqual(len([p for p in reports if p[2] == 0x24]), 5)

    def test_mapping_dry_run_never_opens_hardware(self):
        with patch.object(rgb, 'Controller') as controller, patch.object(rgb, 'discover') as discover, patch('builtins.print'):
            self.assertEqual(rgb.main(['map', '--dry-run']), 0)
            controller.assert_not_called()
            discover.assert_not_called()

    def test_group_is_selected_in_one_transaction(self):
        reports = rgb.group_action_reports([0, 1, 2], (255, 0, 0))
        self.assertEqual(len(reports), 5)
        self.assertEqual(reports[0][:9], bytes.fromhex('00 03 26 00 00 03 00 01 02'))
        self.assertEqual(reports[2][:9], bytes.fromhex('00 03 23 01 00 03 00 01 02'))
        self.assertEqual(reports[3][8:11], bytes([255, 0, 0]))
        for lights in ([], [1, 1], list(range(29))):
            with self.assertRaises(ValueError):
                rgb.group_action_reports(lights, (255, 0, 0))

    def test_action_probe_undims_one_zone_without_saving(self):
        reports = rgb.action_reports(1, (0, 255, 0))
        self.assertEqual([len(p) for p in reports], [34] * 5)
        self.assertEqual(reports[0][:7], bytes.fromhex('00 03 26 00 00 01 01'))
        self.assertEqual(reports[2][:7], bytes.fromhex('00 03 23 01 00 01 01'))
        self.assertEqual(reports[3][:11], bytes.fromhex('00 03 24 00 00 01 00 02 00 ff 00'))
        self.assertEqual([p[4] for p in reports if p[2] == 0x21], [1, 3])

    def test_single_light_green_transaction(self):
        reports = rgb.color_reports(1, (0, 255, 0))
        self.assertEqual([len(p) for p in reports], [34] * 4)
        self.assertEqual(reports[2][:9], bytes.fromhex('00 03 27 00 ff 00 00 01 01'))
        self.assertEqual([p[4] for p in (reports[0], reports[1], reports[3])], [4, 1, 3])
        # Control 2 saves to nonvolatile storage; this MVP must never emit it.
        self.assertNotIn(2, [p[4] for p in reports if p[2] == 0x21])

    def test_reject_invalid_inputs(self):
        for light in (-1, 256):
            with self.assertRaises(ValueError):
                rgb.color_reports(light, (0, 0, 0))
        for color in ('zzzzzz', 'ffffff00', 'ff ff ', 'abc'):
            with self.assertRaises(argparse.ArgumentTypeError):
                rgb.parse_color(color)
        self.assertEqual(rgb.parse_color('#00FF7f'), (0, 255, 127))

    def test_dry_run_never_discovers_or_opens_hardware(self):
        with patch.object(rgb, 'discover') as discover, patch.object(rgb, 'Controller') as controller, patch('builtins.print'):
            self.assertEqual(rgb.main(['set', '--light', '1', '--color', '00ff00', '--dry-run']), 0)
            discover.assert_not_called()
            controller.assert_not_called()

    def test_unknown_status_fails_closed(self):
        controller = object.__new__(rgb.Controller)
        controller.status = Mock(return_value=(0, b'\x00' * 34))
        with self.assertRaisesRegex(RuntimeError, 'Unexpected status'):
            controller.ready()

    def test_busy_timeout_is_bounded(self):
        controller = object.__new__(rgb.Controller)
        controller.status = Mock(return_value=(0x22, b'\x00' * 34))
        with patch.object(rgb.time, 'monotonic', side_effect=[0, 3]):
            with self.assertRaisesRegex(RuntimeError, 'stayed busy'):
                controller.ready()

    def test_zero_status_exception_requires_full_zero_report(self):
        controller = object.__new__(rgb.Controller)
        controller.status = Mock(return_value=(0, bytes(34)))
        with patch('builtins.print'):
            self.assertEqual(controller.ready(allow_zero_status=True), bytes(34))
        for raw in (bytes(3), bytes(33) + b'\x01'):
            controller.status.return_value = (0, raw)
            with self.assertRaisesRegex(RuntimeError, 'Unexpected status'):
                controller.ready(allow_zero_status=True)

    def test_zero_status_option_does_not_bypass_read_failure(self):
        controller = object.__new__(rgb.Controller)
        controller.status = Mock(side_effect=RuntimeError('Status read failed'))
        with self.assertRaisesRegex(RuntimeError, 'Status read failed'):
            controller.ready(allow_zero_status=True)

    def test_short_output_is_failure(self):
        controller = object.__new__(rgb.Controller)
        controller.lib = Mock()
        controller.handle = 1
        controller.lib.hid_send_output_report.return_value = 12
        controller.lib.hid_error.return_value = 'short write'
        with self.assertRaisesRegex(RuntimeError, 'Output report failed'):
            controller.send(rgb.color_reports(1, (0, 255, 0))[0])


if __name__ == '__main__':
    unittest.main()
