import json
import threading
import socket
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import requests
import pytest


class _Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/players":
            q = parse_qs(p.query)
            name = q.get("name", [""])[0]
            # return a single match with deterministic id
            self._send_json([{"id": 777, "full_name": name}])
            return

        if p.path.startswith("/gamelog/"):
            parts = p.path.strip("/").split("/")
            if len(parts) >= 2:
                pid = parts[1]
            else:
                pid = "0"
            # return two simple games
            games = [{"game_id": 1, "PTS": 12, "player_id": int(pid)}, {"game_id": 2, "PTS": 18, "player_id": int(pid)}]
            self._send_json(games)
            return

        # default
        self._send_json({"error": "not found"}, status=404)


def _start_server():
    # pick an available port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()

    server = HTTPServer(("127.0.0.1", port), _Handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, port


@pytest.mark.integration
def test_nba_client_against_local_proxy(monkeypatch):
    server, thread, port = _start_server()
    base = f"http://127.0.0.1:{port}"

    # Patch players.find_players_by_full_name to call our proxy
    def find_players_by_full_name(name):
        r = requests.get(f"{base}/players", params={"name": name}, timeout=2)
        return r.json()

    # Fake PlayerGameLog class
    class FakePGL:
        def __init__(self, player_id=None):
            self.player_id = player_id

        def get_data_frames(self):
            r = requests.get(f"{base}/gamelog/{self.player_id}", timeout=2)
            rows = r.json()

            class DF:
                def __init__(self, rows):
                    self._rows = rows

                def head(self, n):
                    return DF(self._rows[:n])

                def to_dict(self, orient="records"):
                    return self._rows

            return [DF(rows)]

    import backend.services.nba_stats_client as ns

    monkeypatch.setattr(ns, "players", types.SimpleNamespace(find_players_by_full_name=find_players_by_full_name))
    monkeypatch.setattr(ns, "playergamelog", types.SimpleNamespace(PlayerGameLog=FakePGL))
    monkeypatch.setattr(ns, "_redis_client", lambda: None)

    # Run client functions
    pid = ns.find_player_id_by_name("Alice Example")
    assert pid == 777

    games = ns.fetch_recent_games(pid, limit=2)
    assert isinstance(games, list)
    assert len(games) == 2
    assert games[0]["PTS"] == 12

    # Shutdown
    server.shutdown()
    thread.join(timeout=2)
