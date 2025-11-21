# Code by DHT@Matthew
import asyncio
import logging

import websockets  # pyright: ignore[reportMissingImports]


class WebSocketServer:
    def __init__(self, host: str = "192.168.1.101", port: int = 8080) -> None:
        self.logger = logging.getLogger("WebSocketServer")

        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self._server: websockets.server.Serve = None
        self._clients: set[websockets.WebSocketServerProtocol] = set()
        self._loop = asyncio.get_event_loop()

    async def _handler(self, ws: websockets.WebSocketServerProtocol):
        self._clients.add(ws)
        try:
            async for message in ws:
                await self.handle_message_recv(message)
        finally:
            self._clients.discard(ws)

    def start(self) -> None:
        self._server = websockets.serve(self._handler, self.host, self.port)
        self._loop.run_until_complete(self._server)
        asyncio.ensure_future(self._server)

    def stop(self) -> None:
        if self._server is None:
            return
        for ws in list(self._clients):
            self._loop.create_task(ws.close())
        self._server.ws_server.close()

    async def handle_message_send(self, message: str) -> None:
        dead = []
        for client in self._clients:
            try:
                await client.send(message)
            except Exception as e:
                self.logger.error(e)
                dead.append(client)
        for d in dead:
            self._clients.discard(d)

    async def handle_message_recv(self, message: str) -> str:
        self.logger.info(f"[RECV] {message}")
        return message


ws = WebSocketServer()
