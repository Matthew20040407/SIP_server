# Code by DHT@Matthew
import asyncio
import logging

from websockets.asyncio.server import serve


class WebSocketServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.logger = logging.getLogger("WebSocketServer")
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"

    async def recv_loop(self, websocket):
        async for message in websocket:
            ...

    async def send_loop(self, websocket):
        while True:
            await asyncio.sleep(1)
            await websocket.send("server ping")

    async def handler(self, websocket):
        recv_task = asyncio.create_task(self.recv_loop(websocket))
        send_task = asyncio.create_task(self.send_loop(websocket))

        done, pending = await asyncio.wait(
            {recv_task, send_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )

        for task in pending:
            task.cancel()

    async def _run(self):
        async with serve(self.handler, self.host, self.port):
            await asyncio.Future()

    def start(self) -> None:
        asyncio.run(self._run())


if __name__ == "__main__":
    WebSocketServer().start()
