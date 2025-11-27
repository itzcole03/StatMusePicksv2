import hashlib
import hmac
import http.server
import os
import socketserver
import sys
import threading
import time
from datetime import date
from types import SimpleNamespace

received = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        received["body"] = body
        # copy headers into a plain dict
        received["headers"] = {k: v for k, v in self.headers.items()}
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_server(server):
    try:
        server.serve_forever()
    except Exception:
        pass


def test_hmac_signature_is_sent(tmp_path):
    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()

    try:
        # configure env for the test
        os.environ["INGEST_ALERT_WEBHOOK"] = f"http://127.0.0.1:{port}/webhook"
        os.environ["INGEST_ALERT_HMAC_SECRET"] = "hmac-secret-xyz"
        os.environ["INGEST_ALERT_RETRIES"] = "1"
        os.environ["INGEST_ALERT_BACKOFF"] = "0.01"

        # inject fake provider with a bad record
        sys.modules["backend.services.nba_stats_client"] = SimpleNamespace(
            fetch_yesterday_games=lambda: [
                {
                    "game_id": "g1",
                    "game_date": "2025-11-12T00:00:00",
                    "away_team": "BOS",
                    "home_team": None,
                    "value": 10,
                },
            ]
        )

        from backend.services import data_ingestion_service as dis

        res = dis.run_daily_sync(when=date(2025, 11, 12))

        time.sleep(0.2)

        assert "body" in received, "Webhook did not receive POST"
        body = received["body"]
        # compute expected signature
        expected = hmac.new(b"hmac-secret-xyz", body, hashlib.sha256).hexdigest()
        sig_header = received["headers"].get("X-Ingest-Signature")
        assert sig_header is not None, "Missing signature header"
        assert sig_header == f"sha256={expected}"

    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass
