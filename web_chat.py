import logging
from datetime import datetime
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

app = FastAPI()

HTML_PAGE = open("./chat.html").read()


class ChatMessage(BaseModel):
    call_id: str
    role: str  # "user" or "assistant"
    content: str
    language: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatBroadcaster:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.messages: list[ChatMessage] = []
        self.max_messages = 100

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        # Send existing messages to new connection
        for msg in self.messages[-50:]:
            await websocket.send_json(msg.model_dump(mode="json"))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: ChatMessage) -> None:
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

        data = message.model_dump(mode="json")
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.add(connection)

        for conn in disconnected:
            self.active_connections.discard(conn)

    def add_message_sync(self, message: ChatMessage) -> None:
        """Thread-safe method to add message from sync context"""
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]


broadcaster = ChatBroadcaster()


@app.get("/", response_class=HTMLResponse)
async def get_chat_page():
    return HTMLResponse(HTML_PAGE)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)


async def broadcast_message(
    call_id: str, role: str, content: str, language: str = "zh"
):
    """Broadcast a chat message to all connected clients"""
    message = ChatMessage(
        call_id=call_id,
        role=role,
        content=content,
        language=language,
    )
    await broadcaster.broadcast(message)


def get_broadcaster() -> ChatBroadcaster:
    return broadcaster
