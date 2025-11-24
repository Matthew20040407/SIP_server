# Code by DHT@Matthew

import logging
import queue
import threading

from websockets.sync.server import ServerConnection, serve

from helper.ws_command import WSCommandHelper
from model.ws_command import WebSocketCommand


class WebsocketServer:
    def __init__(self, host: str = "192.168.1.1", port: int = 8080):
        self.logger = logging.getLogger("WebsocketServer")
        self.host = host
        self.port = port

        self.send_queue: queue.Queue[WebSocketCommand] = queue.Queue()
        self.recv_queue: queue.Queue[WebSocketCommand] = queue.Queue()

        self.ws_server = None
        self.running = False

        self.command_helper = WSCommandHelper()
        self.parser = self.command_helper.parser
        self.builder = self.command_helper.builder

        self.status: dict[str, int] = {"send": 0, "recv": 0}

    def recv_loop(self, websocket: ServerConnection) -> None:
        try:
            for message in websocket:
                self.logger.info(f"Received: {message}")
                command = self.parser(message=str(message))
                self.recv_queue.put(command, timeout=0.1)
                self.status["recv"] += 1
        except Exception as e:
            self.logger.error(f"recv_loop error: {e}")

    def send_loop(self, websocket: ServerConnection) -> None:
        while self.running:
            try:
                message = self.send_queue.get(timeout=1.0)
                websocket.send(str(message))
                self.logger.info(f"Sent: {message}")
                self.status["send"] += 1
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"send_loop error: {e}")
                break

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

    def send_message(self, message: WebSocketCommand) -> None:
        self.send_queue.put(message)

    def get_message(self) -> WebSocketCommand | None:
        if self.recv_queue.empty():
            return
        return self.recv_queue.get(timeout=0.1)

    def get_status(self) -> None: ...


ws_server = WebsocketServer("0.0.0.0", 8080)
ws_server.start_ws()

if __name__ == "__main__":
    ...
    # server.send_message("Hello from server")

    # try:
    #     msg = server.get_message()
    #     print(f"Got message: {msg}")
    # except queue.Empty:
    #     print("No message received")

    # server.stop_ws()
