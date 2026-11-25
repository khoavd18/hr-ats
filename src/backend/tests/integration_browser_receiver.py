import json
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import uuid4

from app.services.integration_events import verify_webhook_signature


@contextmanager
def fake_integration_receiver():
    secret = uuid4().hex + uuid4().hex

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if not verify_webhook_signature(
                secret,
                self.headers.get("X-HR-ATS-Timestamp", ""),
                self.path,
                body,
                self.headers.get("X-HR-ATS-Signature", ""),
                datetime.now(UTC),
            ):
                self.send_error(403)
                return
            if self.path == "/webhook/hr-ats/pipeline":
                self.send_error(503)
                return
            event = json.loads(body)
            reply = json.dumps({"received": True, "event_id": event["event_id"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    with ThreadingHTTPServer(("127.0.0.1", 0), Receiver) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", secret
        finally:
            server.shutdown()
            thread.join()
