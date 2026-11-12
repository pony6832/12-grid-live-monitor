import json
import unittest

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication
from app.core.chrome_session import PlayerConnection, PlaybackHealth


class ChromeSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner = QObject()
        self.connection = PlayerConnection('test_marker', 'https://www.youtube.com/watch?v=test', self.owner)
        self.connection.timer.stop()
        self.calls = []
        self.connection._send = lambda ident, method, params: self.calls.append((ident, method, params))

    def tearDown(self):
        self.connection.close()

    def test_navigate_to_local_player_without_modifying_youtube(self):
        self.connection._connected()
        self.assertEqual(self.calls[-1][1], 'Page.enable')
        self.connection._message(json.dumps({'id': 0, 'result': {}}))
        self.assertEqual(self.calls[-1][1], 'Page.navigate')
        self.assertTrue(self.connection.repair_timer.isActive())
        self.connection.close()
        self.assertFalse(self.connection.repair_timer.isActive())

    def test_navigation_failure_does_not_report_ready(self):
        failures, ready = [], []
        self.connection.failed.connect(failures.append)
        self.connection.ready.connect(lambda: ready.append(True))
        self.connection._message(json.dumps({'id': 2, 'result': {'errorText': 'net::ERR_CONNECTION_RESET'}}))
        self.assertEqual(len(failures), 1)
        self.assertEqual(ready, [])

    def test_playback_status_comes_from_video_state(self):
        states = []
        self.connection.playback.connect(states.append)
        for snapshot in [{'state': -1}, {'state': 1, 'time': 10}, {'state': 2}, {'error': 150}]:
            self.connection._message(json.dumps({'id': 5, 'result': {'result': {'value': snapshot}}}))
        self.assertEqual(states, ['loading', 'playing', 'paused', 'error'])


class PlaybackHealthTests(unittest.TestCase):
    def test_stalled_playing_state_does_not_stay_green_forever(self):
        health = PlaybackHealth()
        start = health.last_progress
        self.assertEqual(health.observe({'state': 1, 'time': 5}, start), ('playing', False))
        self.assertEqual(health.observe({'state': 1, 'time': 5}, start + 31), ('retrying', True))

    def test_pausing_does_not_trigger_reload(self):
        health = PlaybackHealth()
        self.assertEqual(health.observe({'state': 2}, health.last_progress + 100), ('paused', False))

    def test_permanent_errors_never_reload(self):
        for error in [100, 101, 150, 153]:
            health = PlaybackHealth()
            self.assertEqual(health.observe({'error': error}, health.last_progress + 100), ('error', False))

    def test_transient_errors_back_off_then_keep_retrying_slowly(self):
        health = PlaybackHealth()
        start = health.last_progress
        for elapsed in [31, 92, 213]:
            self.assertEqual(health.observe({'error': 5}, start + elapsed), ('retrying', True))
            self.assertFalse(health.observe({'error': 5}, start + elapsed + 1)[1])
        self.assertEqual(health.observe({'error': 5}, start + 500), ('waiting', False))
        self.assertEqual(health.observe({'error': 5}, start + 213 + 600), ('retrying', True))
        self.assertEqual(health.observe({'error': 5}, start + 213 + 601), ('waiting', False))

    def test_sustained_playback_restores_fast_retries(self):
        health = PlaybackHealth()
        start = health.last_progress
        for elapsed in [31, 92, 213]:
            health.observe({'error': 5}, start + elapsed)
        self.assertEqual(health.retries, 3)
        t = start + 900
        for step in range(0, 125, 3):
            self.assertEqual(health.observe({'state': 1, 'time': step}, t + step), ('playing', False))
        self.assertEqual(health.retries, 0)

    def test_short_playback_burst_keeps_retry_count(self):
        health = PlaybackHealth()
        start = health.last_progress
        health.observe({'error': 5}, start + 31)
        health.observe({'state': 1, 'time': 1}, start + 40)
        health.observe({'state': 1, 'time': 4}, start + 43)
        self.assertEqual(health.retries, 1)


class PlayerConnectionAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner = QObject()
        self.connection = PlayerConnection('m', 'http://127.0.0.1/player', self.owner)
        self.connection.timer.stop()
        self.calls = []
        self.connection._send = lambda ident, method, params: self.calls.append((ident, method, params))

    def tearDown(self):
        self.connection.close()

    def test_audio_is_applied_inside_youtube_frame_with_gesture(self):
        frame_calls = []
        self.connection._frame_connected = lambda: True
        self.connection._send_frame = lambda method, params: frame_calls.append((method, params))
        self.connection._maintain()
        self.assertEqual(self.calls[-1][1], 'Runtime.evaluate')
        self.assertIn('const want = true;', frame_calls[-1][1]['expression'])
        self.connection.set_muted(False)
        self.assertIn('const want = false;', frame_calls[-1][1]['expression'])
        self.assertTrue(frame_calls[-1][1]['userGesture'])

    def test_frame_is_discovered_only_after_page_is_known(self):
        discovered = []
        self.connection._discover_frame = lambda: discovered.append(True)
        self.connection.set_muted(False)
        self.assertEqual(discovered, [])
        self.connection.page_id = 'PAGE'
        self.connection.set_muted(False)
        self.assertEqual(discovered, [True])

    def test_failed_poll_does_not_report_failure(self):
        failures = []
        self.connection.failed.connect(failures.append)
        self.connection._message(json.dumps({'id': 5, 'error': {'message': 'Cannot find context'}}))
        self.assertEqual(failures, [])
        self.connection._message(json.dumps({'id': 2, 'error': {'message': 'boom'}}))
        self.assertEqual(len(failures), 1)


if __name__ == '__main__':
    unittest.main()
