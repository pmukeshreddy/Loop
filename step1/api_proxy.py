"""CONNECT proxy for benchmark containers: only the public OpenAI API."""

import select
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Server(ThreadingHTTPServer):
    daemon_threads = True


class Proxy(BaseHTTPRequestHandler):
    def do_CONNECT(self):
        if self.path != "api.openai.com:443":
            self.send_error(403, "Only api.openai.com:443 is allowed")
            return
        try:
            upstream = socket.create_connection(("api.openai.com", 443), timeout=30)
        except OSError:
            self.send_error(502)
            return
        with upstream:
            self.send_response(200, "Connection Established")
            self.end_headers()
            self.wfile.flush()
            self.connection.settimeout(180)
            upstream.settimeout(180)
            sockets = [self.connection, upstream]
            try:
                while True:
                    ready, _, _ = select.select(sockets, [], [], 180)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        destination = (
                            upstream if source is self.connection else self.connection
                        )
                        destination.sendall(data)
            except OSError:
                return

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    Server(("0.0.0.0", 8080), Proxy).serve_forever()
