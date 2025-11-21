# Code by DHT@Matthew

import logging
import re

from model.sip_message import (
    MediaDescription,
    SDPMessage,
    SIPMessage,
    SIPRequestLine,
    TimeDescription,
)


class SipMessageParser:
    def __init__(self) -> None:
        self.logger = logging.getLogger("SipMessageParser")

    def parse_sip_message(self, raw_sip_message: str) -> SIPMessage:
        self.logger.debug(raw_sip_message)

        header_part, _, body = raw_sip_message.partition("\r\n\r\n")
        if not body:
            header_part, _, body = raw_sip_message.partition("\n\n")

        lines = [line.strip() for line in header_part.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Empty SIP message")

        # Parse request line
        request_line_match = re.match(r"^(\w+)\s+(\S+)\s+(SIP/\d\.\d)$", lines[0])
        if not request_line_match:
            raise ValueError(f"Invalid SIP request line: {lines[0]}")
        method, uri, version = request_line_match.groups()

        # Parse headers
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()

        parsed_sdp_message = (
            self.parse_sdp_message(raw_sdp_message=body) if body else None
        )

        return SIPMessage(
            request_line=SIPRequestLine(method=method, uri=uri, version=version),
            headers=headers,
            body=parsed_sdp_message if parsed_sdp_message else "",
        )

    def parse_sdp_message(self, raw_sdp_message: str = "") -> SDPMessage:
        if not raw_sdp_message:
            raise ValueError("Empty SDP message")
        self.logger.debug(raw_sdp_message)
        sections = re.split(r"(m=)", raw_sdp_message, flags=re.MULTILINE)

        sdp_message = self._operator_parser(sections[0])

        media_data_list = []
        for i in range(1, len(sections), 2):
            media_data = self._operator_parser("m=" + sections[i + 1])

            media_data_list.append(
                MediaDescription(
                    m=media_data["media"],
                    a=media_data["attributes"],
                    c=media_data["connection_info"],
                    b=media_data["bandwidth_info"],
                )
            )
        return SDPMessage(**sdp_message, media_descriptions=media_data_list)

    def _operator_parser(self, sections) -> dict[str, str | list[str] | int]:
        session_data = {}
        for line in sections.splitlines():
            prefix, _, value = line.partition("=")
            prefix = prefix.replace(" ", "")
            self.logger.debug(prefix, value)
            # self.logger.debug(prefix, value)

            if prefix == "v":
                session_data["version"] = int(value)

            elif prefix == "o":
                session_data["origin"] = value

            elif prefix == "s":
                session_data["session_name"] = value

            elif prefix == "i":
                session_data["title"] = value | ""

            elif prefix == "u":
                session_data["uri"] = value | ""

            elif prefix == "e":
                session_data["email"] = value | ""

            elif prefix == "p":
                session_data["phone"] = value | ""

            elif prefix == "c":
                session_data["connection_info"] = value

            elif prefix == "b":
                session_data.setdefault("bandwidth_info", []).append(value)

            elif prefix == "t":
                session_data.setdefault("time_descriptions", []).append(
                    TimeDescription(t=value)
                )

            elif prefix == "z":
                session_data.setdefault("timezone_adjustments", []).append(value)

            elif prefix == "k":
                session_data["encryption_key"] = value | ""

            elif prefix == "m":
                session_data["media"] = value

            elif prefix == "a":
                session_data.setdefault("attributes", []).append(value)

        return session_data


if __name__ == "__main__":
    raw_sip = """INVITE sip:192.168.157.126:5062 SIP/2.0
Via: SIP/2.0/UDP 192.168.1.170:5060;rport;branch=z9hG4bKPjyCB22ZUerubmGLpC-GzTFzNmGfiam1QA
Max-Forwards: 70
From: "0903383638" <sip:0903383638@192.168.1.170>;tag=eTQzZsIFvOXQJW-YBE7C9OJA8hS.32V8
To: sip:192.168.157.126
Contact: <sip:192.168.1.170:5060;ob>
Call-ID: 6zo14J0DbghBJ.JrrUvKRIQqLVPhAJxq
CSeq: 26086 INVITE
Allow: PRACK, INVITE, ACK, BYE, CANCEL, UPDATE, INFO, SUBSCRIBE, NOTIFY, REFER, MESSAGE, OPTIONS
Supported: replaces, 100rel, timer, norefersub
Session-Expires: 1800
Min-SE: 90
User-Agent: XZ6116/1.2.1-26207050-24092400-08
Remote-Party-ID: "0903383638" <sip:0903383638@192.168.1.170>;party=calling;screen=yes;privacy=off
Content-Type: application/sdp
Content-Length:   342

v=0
o=- 485 654 IN IP4 192.168.1.170
s=-
c=IN IP4 192.168.1.170
t=0 0
m=audio 4000 RTP/AVP 0 8 96
a=rtpmap:0 PCMU/8000
"""
