from enum import StrEnum

from pydantic import BaseModel


class CommandType(StrEnum):
    CALL = "CALL"
    RTP = "RTP"
    CALL_ANS = "CALL_ANS"
    CALL_IGNORE = "CALL_IGNORE"
    HANGUP = "HANGUP"
    BYE = "BYE"
    RING_ANS = "RING_ANS"
    RING_IGNORE = "RING_IGNORE"
    CALL_FAILED = "CALL_FAILED"


class WebSocketCommand(BaseModel):
    type: CommandType
    content: str | bytes | None = None

    def __str__(self) -> str:
        if self.content:
            return f"{self.type}:{self.content}"
        else:
            return self.type
