# Code by DHT@Matthew

import logging
import re

from model.ws_command import CommandType, WebSocketCommand


class WSCommandHelper:
    def __init__(self) -> None:
        self.logger = logging.getLogger("WSCommandParser")
        self.pattern = re.compile(
            r"(^(CALL|ANS|RING_ANS|RTP|CALL_ANS|CALL_IGNORE|HANGUP|BYE)(:[\w\W]+)?)$"
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
            raise Exception(f"No command found {message}")

        match raw_command:
            case s if s.startswith("CALL:"):
                self.logger.debug("[WS Parser] Match Call")

                _, phone_number = raw_command.split(":")

                # Validate phone number format (support international and Taiwan numbers)
                # Allow: digits only, optional + prefix, min 7 digits, max 15 digits
                phone_pattern = r'^\+?\d{7,15}$'
                if not re.match(phone_pattern, phone_number):
                    raise ValueError(f"Invalid phone number format: {phone_number}. Must be 7-15 digits, optionally starting with +")

                command = WebSocketCommand(type=CommandType.CALL, content=phone_number)

            case s if s.startswith("RTP:"):
                self.logger.debug("[WS Parser] Match RTP")

                _, packet_string = raw_command.split(":")

                command = WebSocketCommand(type=CommandType.RTP, content=packet_string)
            case s if s.startswith("BYE"):
                self.logger.debug("[WS Parser] Match BYE")
                _, call_info = raw_command.split(":")
                command = WebSocketCommand(type=CommandType.BYE, content=call_info)

            case s if s.startswith("CALL_ANS"):
                self.logger.debug("[WS Parser] Match CALL_ANS")
                _, call_info = raw_command.split(":")
                command = WebSocketCommand(type=CommandType.CALL_ANS, content=call_info)

            case s if s.startswith("CALL_IGNORE"):
                self.logger.debug("[WS Parser] Match CALL_IGNORE")
                _, call_info = raw_command.split(":")
                command = WebSocketCommand(
                    type=CommandType.CALL_IGNORE, content=call_info
                )

            case s if s.startswith("HANGUP"):
                self.logger.debug("[WS Parser] Match HANGUP")

                command = WebSocketCommand(type=CommandType.HANGUP)

            case s if s.startswith("RING_ANS"):
                self.logger.debug("[WS Parser] Match RING_ANS")
                _, ring_info = raw_command.split(":")
                command = WebSocketCommand(type=CommandType.RING_ANS, content=ring_info)

            case s if s.startswith("RING_IGNORE"):
                self.logger.debug("[WS Parser] Match RING_IGNORE")
                _, ring_info = raw_command.split(":")
                command = WebSocketCommand(
                    type=CommandType.RING_IGNORE, content=ring_info
                )

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
