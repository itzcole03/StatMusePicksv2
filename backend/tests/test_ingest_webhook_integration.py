import threading
import http.server
import socketserver
import json
import os
import sys
import time
from types import SimpleNamespace
from datetime import date
import threading
import http.server
import socketserver
import json
import os
import sys
import time
from types import SimpleNamespace
from datetime import date

received = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        received['body'] = body
        # copy headers into a plain dict
        received['headers'] = {k: v for k, v in self.headers.items()}
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # silence default logging from BaseHTTPRequestHandler
        return


def run_server(server):
    try:
        server.serve_forever()
    except Exception:
        pass


def test_ingest_alerts_posted_to_webhook(tmp_path):
    # start a local HTTP server on an ephemeral port to receive the webhook
    server = socketserver.TCPServer(('127.0.0.1', 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()

    try:
        # configure env for the test
        os.environ['INGEST_ALERT_WEBHOOK'] = f'http://127.0.0.1:{port}/webhook'
        os.environ['INGEST_ALERT_SECRET'] = 'test-secret-123'
        os.environ['INGEST_ALERT_RETRIES'] = '2'
        os.environ['INGEST_ALERT_BACKOFF'] = '0.1'

        # inject a fake provider that returns one bad record (missing home_team)
        sys.modules['backend.services.nba_stats_client'] = SimpleNamespace(
            fetch_yesterday_games=lambda: [
                {"game_id": "g1", "game_date": "2025-11-12T00:00:00", "away_team": "BOS", "home_team": None, "value": 10},
                {"game_id": "g2", "game_date": "2025-11-12T00:00:00", "away_team": "NYK", "home_team": "LAL", "value": 12},
            ]
        )

        # run the sync which should attempt to POST a validation alert
        from backend.services import data_ingestion_service as dis
        res = dis.run_daily_sync(when=date(2025, 11, 12))

        # give server a moment to receive the POST
        time.sleep(0.2)

        # ensure server got a POST payload
        assert 'body' in received, 'Webhook server did not receive a POST'
        payload = json.loads(received['body'])
        assert payload.get('missing_count', 0) >= 1
        # header keys are normalized; check secret header
        assert received['headers'].get('X-Ingest-Secret') == 'test-secret-123'

    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass
        # configure env for the test
