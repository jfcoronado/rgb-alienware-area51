import unittest
from unittest.mock import patch
import json
import tempfile
from pathlib import Path
import lighting_service as service


class ServiceTests(unittest.TestCase):
    def test_saved_color_migrates_from_legacy_location(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            legacy = path / 'legacy.json'
            legacy.write_text(json.dumps({'color':'abcdef'}))
            with patch.object(service, 'STATE', path/'missing.json'), patch.object(service, 'LEGACY_STATE', legacy):
                self.assertEqual(service.saved_color(), 'ABCDEF')

    def test_save_color_uses_state_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'new-state'
            with patch.object(service, 'STATE_DIR', directory), patch.object(service, 'STATE', directory/'state.json'):
                service.save_color('#123abc')
                self.assertEqual(json.loads((directory/'state.json').read_text()), {'color':'123ABC'})

    def test_no_writes_if_either_controller_is_inaccessible(self):
        with patch.object(service, 'devices', return_value=[{'accessible':True},{'accessible':False}]), patch.object(service, 'run') as run:
            with self.assertRaises(PermissionError):
                service.apply_color('8000FF')
            run.assert_not_called()

    def test_all_chassis_ids_and_keyboard_receive_same_color(self):
        with patch.object(service, 'devices', return_value=[{'accessible':True}]), patch.object(service, 'run') as run:
            service.apply_color('#123abc')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 3)
        ids = []
        for command in commands[:2]:
            ids += list(map(int, command[command.index('--lights')+1:command.index('--color')]))
        self.assertEqual(ids, list(range(41)))
        self.assertTrue(all(c[c.index('--color')+1]=='123ABC' for c in commands))

    def test_partial_failure_stops_and_is_reported(self):
        with patch.object(service, 'devices', return_value=[{'accessible':True}]), patch.object(service, 'run', side_effect=[None,RuntimeError('disconnected')]) as run:
            with self.assertRaisesRegex(RuntimeError, 'Some lights may have changed'):
                service.apply_color('8000FF')
            self.assertEqual(run.call_count, 2)

    def test_bad_color_never_reaches_hardware(self):
        with patch.object(service, 'devices') as devices:
            with self.assertRaises(ValueError):
                service.apply_color('red;anything')
            devices.assert_not_called()
