# Code by DHT@Matthew

import logging
import queue
import threading

from websockets.sync.server import Server, ServerConnection, serve

from helper.ws_command import WSCommandHelper
from model.ws_command import WebSocketCommand


class WebsocketServer:
    def __init__(self, host: str = "192.168.1.1", port: int = 8080):
        self.logger = logging.getLogger("WebsocketServer")
        self.host = host
        self.port = port

        self._send_queue: queue.Queue[WebSocketCommand] = queue.Queue()
        self._recv_queue: queue.Queue[WebSocketCommand] = queue.Queue()

        self.ws_server: Server | None = None
        self.running = False

        self.command_helper = WSCommandHelper()
        self.parser = self.command_helper.parser
        self.builder = self.command_helper.builder

        self.status: dict[str, int] = {"send": 0, "recv": 0}

    def recv_loop(self, websocket: ServerConnection) -> None:
        self.logger.info("recv_loop STARTED")
        try:
            for message in websocket:
                self.logger.debug(f"Received RAW: {repr(message)}")

                command = self.parser(message=str(message))
                self._recv_queue.put(command)
                self.status["recv"] += 1
        except Exception as e:
            self.logger.error(f"recv_loop CRASHED: {e}", exc_info=True)
        finally:
            self.logger.info("recv_loop ENDED")

    def send_loop(self, websocket: ServerConnection) -> None:
        while self.running:
            try:
                message = self._send_queue.get(timeout=1.0)
                websocket.send(str(message))
                self.logger.debug(f"Sent: {message}")
                self.status["send"] += 1
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"send_loop error: {e}")
                break

    def send_message(self, message: WebSocketCommand) -> None:
        self._send_queue.put(message)

    def get_message(self) -> WebSocketCommand | None:
        try:
            return self._recv_queue.get(block=False)
        except queue.Empty:
            return None

    def handler(self, websocket: ServerConnection) -> None:
        self.running = True

        recv_thread = threading.Thread(
            target=self.recv_loop, args=(websocket,), daemon=True
        )
        send_thread = threading.Thread(
            target=self.send_loop, args=(websocket,), daemon=True
        )

        recv_thread.start()
        send_thread.start()

        recv_thread.join()
        self.running = False
        send_thread.join()

    def _run(self) -> None:
        with serve(self.handler, self.host, self.port) as server:
            self.ws_server = server
            self.logger.info(f"[WebSocket] server started on {self.host}:{self.port}")
            self.ws_server.serve_forever()

    def start_ws(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop_ws(self) -> None:
        if not self.ws_server:
            self.logger.warning("No ws server created")
            return

        self.running = False
        self.ws_server.shutdown()
        self.logger.info("[WebSocket] server stopped")


ws_server = WebsocketServer("192.168.1.101", 8080)
ws_server.start_ws()

if __name__ == "__main__":
    ...
