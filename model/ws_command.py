# Code by DHT@Matthew

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


class WebSocketCommand(BaseModel):
    type: CommandType
    content: str | bytes | None = None

    def __str__(self) -> str:
        if self.content:
            return f"{self.type}:{self.content}"
        else:
            return self.type


# class CallCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.CALL
#     content: str


# class RPTCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.RPT
#     content: bytes


# class CallAnswerCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.CALL_ANS
#     content: None


# class CallIgnoreCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.CALL_IGNORE
#     content: None


# class HangUpCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.HANGUP
#     content: None


# class ByeCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.BYE
#     content: None


# class RingAnswerCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.RING_ANS
#     content: None


# class RingIgnoreCommand(BasicWebSocketCommand):
#     type: CommandType = CommandType.RING_IGNORE
#     content: None
