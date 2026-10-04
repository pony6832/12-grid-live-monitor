import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from app.core.player_host import PlayerHost


class PlayerHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = PlayerHost()

    @classmethod
    def tearDownClass(cls):
        cls.host.close()

    def test_player_has_real_origin_and_fills_window(self):
        url = self.host.player_url('https://youtu.be/ylYJSBUgaMA')
        with urlopen(url, timeout=2) as response:
            self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
            page = response.read().decode()
        self.assertIn('origin:location.origin', page)
        self.assertIn('position:fixed; inset:0', page)
        self.assertIn('new YT.Player', page)
        self.assertNotIn('document.querySelector(\'#movie_player\')', page)

    def test_playlist_is_preserved(self):
        url = self.host.player_url('https://www.youtube.com/playlist?list=PL_example')
        self.assertEqual(parse_qs(urlsplit(url).query)['list'], ['PL_example'])
        with urlopen(url, timeout=2) as response:
            self.assertEqual(response.status, 200)

    def test_untrusted_ids_cannot_inject_script(self):
        for path in ['/player?v=%3Cscript%3E', '/player?v=ylYJSBUgaMA&list=%22%3E', '/config.json']:
            with self.subTest(path=path), self.assertRaises(HTTPError):
                urlopen(self.host.origin + path, timeout=2)
