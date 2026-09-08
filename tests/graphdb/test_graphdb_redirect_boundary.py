"""An approved GraphDB endpoint cannot redirect reads to another origin."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from kg_mnp.graphdb.client import GraphDBClient, GraphDBClientError


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_graphdb_redirect_is_rejected_before_reaching_another_origin(status):
    observed = []
    class Target(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            observed.append(self.path)
            self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"[]")
    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(status)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/unapproved")
            self.send_header("Content-Length", "0"); self.end_headers()
    origin = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threads = [Thread(target=server.serve_forever, daemon=True) for server in (origin, target)]
    for thread in threads: thread.start()
    try:
        client = GraphDBClient(base_url=f"http://127.0.0.1:{origin.server_port}", retries=0)
        with pytest.raises(GraphDBClientError, match="redirect"):
            client.health_check()
        assert observed == []
    finally:
        for server in (origin, target): server.shutdown(); server.server_close()
        for thread in threads: thread.join(5)
