import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import theme_sync as sync


class ThemeTests(unittest.TestCase):
    def test_keyboard_rgb_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'keyboard.rgb').write_text('#123abc\n')
            (path/'colors.toml').write_text('accent = "#ffffff"\n')
            self.assertEqual(sync.theme_color(path), ('123ABC','keyboard.rgb'))

    def test_missing_or_invalid_keyboard_color_uses_accent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'colors.toml').write_text('accent = "#7d82d9"\n')
            self.assertEqual(sync.theme_color(path), ('7D82D9','accent'))
            (path/'keyboard.rgb').write_text('not a color')
            self.assertEqual(sync.theme_color(path), ('7D82D9','accent'))

    def test_invalid_theme_never_applies(self):
        with patch.object(sync, 'theme_color', side_effect=ValueError('invalid')), patch.object(sync.service, 'apply_color') as apply:
            with self.assertRaises(ValueError):
                sync.sync()
            apply.assert_not_called()

    def test_disabled_hook_does_not_read_theme_or_apply(self):
        with patch.object(sync, 'enabled', return_value=False), patch.object(sync, 'theme_color') as read, patch.object(sync.service, 'apply_color') as apply:
            self.assertEqual(sync.sync(automatic=True), 'Theme sync is paused.')
            read.assert_not_called()
            apply.assert_not_called()

    def test_preview_does_not_apply_or_save(self):
        with patch.object(sync, 'theme_color', return_value=('123456','accent')), patch.object(Path, 'read_text', return_value='test'), patch.object(sync.service, 'apply_color') as apply, patch.object(sync.service, 'save_color') as save:
            self.assertIn('#123456',sync.sync(dry_run=True))
            apply.assert_not_called()
            save.assert_not_called()
