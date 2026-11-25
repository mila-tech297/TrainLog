import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old_database = app.DATABASE
        app.DATABASE = Path(self.directory.name) / 'trainlog.sqlite3'
        app.initialize()
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        app.DATABASE = self.old_database
        self.directory.cleanup()

    def post(self, path, body, token=app.TOKEN):
        request = Request(self.base + path, data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json', 'X-Trainlog-Token': token})
        try:
            with urlopen(request) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def workout(self, **changes):
        body = {'date': dt.date.today().isoformat(), 'distance': 5, 'duration': 30, 'note': 'Fijn gelopen'}
        body.update(changes)
        return self.post('/api/workouts', body)

    def test_save_reload_goal_summary_delete(self):
        status, data = self.workout()
        self.assertEqual(status, 200)
        workout_id = data['workouts'][0]['id']
        # Opnieuw initialiseren mag bestaande gegevens niet verwijderen.
        app.initialize()
        with urlopen(self.base + '/api/state') as response:
            self.assertEqual(json.load(response)['workouts'][0]['distance'], 5)
        status, data = self.post('/api/goal', {'distance': 10, 'deadline': dt.date.today().isoformat()})
        self.assertEqual(status, 200)
        self.assertEqual(data['goal']['distance'], 10)
        status, data = self.post('/api/summary', {'ai': False})
        self.assertEqual(status, 200)
        self.assertIn('5 km in 30 minuten', data['text'])
        self.assertIn('geen AI', data['source'])
        status, data = self.post('/api/workouts/delete', {'id': workout_id})
        self.assertEqual(data['workouts'], [])

    def test_invalid_data_does_not_reach_database(self):
        for distance in [-1, 0, 'NaN', 'Infinity', True, 'geen getal']:
            self.assertEqual(self.workout(distance=distance)[0], 400)
        future = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        self.assertEqual(self.workout(date=future)[0], 400)
        self.assertEqual(self.workout(note='x' * 501)[0], 400)
        self.assertEqual(app.state()['workouts'], [])
        self.assertEqual(self.post('/api/workouts', {}, token='verkeerd')[0], 403)

    def test_ai_is_real_request_and_excludes_notes(self):
        self.workout(note='PRIVE NOTITIE')
        output = {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Je liep 5 kilometer.'}]}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('app.urlopen', return_value=io.BytesIO(json.dumps(output).encode())) as mocked:
                result = app.weekly_summary(True)
                request = mocked.call_args.args[0]
                payload = json.loads(request.data)
                self.assertNotIn('PRIVE NOTITIE', payload['input'])
                self.assertFalse(payload['store'])
                self.assertEqual(result['text'], 'Je liep 5 kilometer.')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.post('/api/summary', {'ai': True})[0], 400)

    def test_static_assets_and_no_database_exposure(self):
        for path in ['/', '/app.js', '/style.css', '/icon.svg', '/manifest.webmanifest']:
            with urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read())
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + '/data/trainlog.sqlite3')
        self.assertEqual(error.exception.code, 404)

    def test_summary_empty_and_previous_week(self):
        self.assertEqual(self.post('/api/summary', {'ai': False})[0], 400)
        earlier = (dt.date.today() - dt.timedelta(days=7)).isoformat()
        self.workout(date=earlier, distance=3)
        self.workout(distance=5)
        result = app.weekly_summary(False)
        self.assertIn('2 km meer', result['text'])


if __name__ == '__main__':
    unittest.main()
