import http.server
import os
import socketserver
import sys
import threading
import time
from datetime import date
from types import SimpleNamespace

calls = {"count": 0, "bodies": []}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        calls["count"] += 1
        calls["bodies"].append(body)
        # Simulate transient failures for the first two attempts
        if calls["count"] <= 2:
            self.send_response(500)
            self.end_headers()
            return
        # On third+ attempt, accept
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_server(server):
    try:
        server.serve_forever()
    except Exception:
        pass


def test_retry_backoff_respects_retries_and_succeeds(tmp_path):
    # start a local HTTP server on an ephemeral port
    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()

    try:
        # configure env so send_alert uses retries/backoff
        os.environ["INGEST_ALERT_WEBHOOK"] = f"http://127.0.0.1:{port}/webhook"
        os.environ["INGEST_ALERT_RETRIES"] = "4"
        os.environ["INGEST_ALERT_BACKOFF"] = "0.01"

        # inject a fake provider that returns one bad record to trigger alert
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

        # allow server time to process retries
        time.sleep(0.5)

        # We expect at least 3 calls: two 500s then a 200
        assert calls["count"] >= 3, f"expected >=3 calls, got {calls['count']}"
        # The final body should be present
        assert calls["bodies"][-1], "no body received on final attempt"

    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass
