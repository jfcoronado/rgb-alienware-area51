import contextlib
import io
import unittest
from unittest.mock import patch

import lighting_cli as cli


class CLITests(unittest.TestCase):
    def test_named_color_is_shared_with_gui(self):
        with patch.object(cli.service, 'apply_color') as apply, patch.object(cli.service, 'save_color') as save, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['set', 'Purple']), 0)
            apply.assert_called_once_with('8000FF')
            save.assert_called_once_with('8000FF')

    def test_off_preserves_saved_color(self):
        with patch.object(cli.service, 'apply_color') as apply, patch.object(cli.service, 'save_color') as save, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['off']), 0)
            apply.assert_called_once_with('000000')
            save.assert_not_called()

    def test_dry_run_never_writes_or_opens_hardware(self):
        with patch.object(cli.service, 'apply_color') as apply, patch.object(cli.service, 'save_color') as save, patch.object(cli.service, 'devices') as devices, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['set', '#123abc', '--dry-run']), 0)
            apply.assert_not_called()
            save.assert_not_called()
            devices.assert_not_called()

    def test_failure_does_not_save(self):
        with patch.object(cli.service, 'apply_color', side_effect=RuntimeError('failed')), patch.object(cli.service, 'save_color') as save, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['set', 'purple']), 1)
            save.assert_not_called()

    def test_on_uses_remembered_color(self):
        with patch.object(cli.service, 'saved_color', return_value='123456'), patch.object(cli.service, 'apply_color') as apply, patch.object(cli.service, 'save_color'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['on']), 0)
            apply.assert_called_once_with('123456')
