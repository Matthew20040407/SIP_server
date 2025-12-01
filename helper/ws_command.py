# Code by DHT@Matthew

import logging
import re

from model.ws_command import CommandType, WebSocketCommand


class WSCommandHelper:
    def __init__(self) -> None:
        self.logger = logging.getLogger("WSCommandParser")
        self.pattern = re.compile(
            r"(CALL:\d+|RTP:[\w\W]+@[\x00-\xFF]+|CALL_ANS|CALL_IGNORE|HANGUP|BYE|RING_ANS|RING_IGNORE)$"
        )

    def parser(self, message: str) -> WebSocketCommand:
        if not isinstance(message, str):
            raise Exception("Invalid message type")

        message = str(message)
        m = self.pattern.match(message)
        if m:
            raw_command = m.group(0)
            self.logger.debug(f"[WS Parser] {raw_command=}")
        else:
            raise Exception("No command found")

        match raw_command:
            case s if s.startswith("CALL:"):
                self.logger.debug("[WS Parser] Match Call")

                _, phone_number = raw_command.split(":")

                if len(phone_number) != 10:
                    raise ValueError(f"Invalid length {len(phone_number)=}")
                command = WebSocketCommand(type=CommandType.CALL, content=phone_number)

            case s if s.startswith("RTP:"):
                self.logger.debug("[WS Parser] Match RTP")

                _, packet_string = raw_command.split(":")
                # if len(rtp_string) % 2 != 0:
                #     raise ValueError(f"Invalid length {len(rtp_string)=}")
                # byte_string = bytes.fromhex(rtp_string)
                # self.logger.debug(byte_string)

                command = WebSocketCommand(type=CommandType.RTP, content=packet_string)
            case s if s.startswith("BYE"):
                self.logger.debug("[WS Parser] Match BYE")

                command = WebSocketCommand(type=CommandType.BYE)

            case s if s.startswith("CALL_ANS"):
                self.logger.debug("[WS Parser] Match CALL_ANS")

                command = WebSocketCommand(type=CommandType.CALL_ANS)

            case s if s.startswith("CALL_IGNORE"):
                self.logger.debug("[WS Parser] Match CALL_IGNORE")

                command = WebSocketCommand(type=CommandType.CALL_IGNORE)

            case s if s.startswith("HANGUP"):
                self.logger.debug("[WS Parser] Match HANGUP")

                command = WebSocketCommand(type=CommandType.HANGUP)

            case s if s.startswith("RING_ANS"):
                self.logger.debug("[WS Parser] Match RING_ANS")

                command = WebSocketCommand(type=CommandType.RING_ANS)

            case s if s.startswith("RING_IGNORE"):
                self.logger.debug("[WS Parser] Match RING_IGNORE")

                command = WebSocketCommand(type=CommandType.RING_IGNORE)

            case _:
                raise Exception(f"Invalid command {raw_command}")

        return command

    def builder(
        self,
        message_type: CommandType,
        message: bytes | str | None = None,
    ) -> WebSocketCommand:
        return WebSocketCommand(type=message_type, content=message)


if __name__ == "__main__":
    WSCommandHelper().parser("CALL:0903383638")
