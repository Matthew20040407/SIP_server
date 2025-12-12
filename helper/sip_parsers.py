import logging

from model.sip_message import (
    MediaDescription,
    SDPMessage,
    SIPHeaders,
    SIPMethod,
    SIPRequest,
    SIPRequestLine,
    SIPResponse,
    SIPStatusLine,
    TimeDescription,
)


class SipMessageParser:
    def __init__(self) -> None:
        self.logger = logging.getLogger("SipMessageParser")

    def parse_sip_message(self, raw_message: str) -> SIPRequest | SIPResponse:
        lines = raw_message.split("\n")
        first_line = lines[0].strip()

        empty_line_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if not line.strip():
                empty_line_idx = i
                break

        if empty_line_idx is None:
            raise ValueError("Invalid SIP message: no empty line")

        headers = {}
        for line in lines[1:empty_line_idx]:
            line = line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key in headers:
                headers[key] += "\n" + value
            else:
                headers[key] = value

        body = "\n".join(lines[empty_line_idx + 1 :]).strip()
        sip_headers = SIPHeaders(**headers)
        if headers.get("Content-Type") == "application/sdp" and body:
            try:
                body = self.parse_sdp_message(body)
            except Exception as e:
                self.logger.error(f"[Parser] {e}")
                pass

        parts = first_line.split(None, 2)

        if parts[0].startswith("SIP/"):
            return SIPResponse(
                status_line=SIPStatusLine(
                    version=parts[0],
                    status_code=int(parts[1]),
                    reason_phrase=parts[2] if len(parts) > 2 else "",
                ),
                headers=sip_headers,
                body=body,
            )
        else:
            return SIPRequest(
                request_line=SIPRequestLine(
                    method=SIPMethod(parts[0]),
                    uri=parts[1],
                    version=parts[2] if len(parts) > 2 else "SIP/2.0",
                ),
                headers=sip_headers,
                body=body,
            )

    def parse_sdp_message(self, raw_sdp_message: str) -> SDPMessage:
        """
        Parse SDP message.

        Good taste:
        1. Split at first 'm=' → session vs media
        2. Parse session and media with same logic
        3. No special cases, no magic indexes
        """
        if not raw_sdp_message.strip():
            raise ValueError("Empty SDP message")

        first_media_pos = raw_sdp_message.find("\nm=")

        if first_media_pos == -1:
            if raw_sdp_message.startswith("m="):
                session_text = ""
                media_text = raw_sdp_message
            else:
                session_text = raw_sdp_message
                media_text = ""
        else:
            session_text = raw_sdp_message[:first_media_pos]
            media_text = raw_sdp_message[first_media_pos + 1 :]

        session_data = self._parse_sdp_fields(session_text)

        media_descriptions = []
        if media_text:
            media_blocks = media_text.split("\nm=")

            for i, block in enumerate(media_blocks):
                if i > 0:
                    block = "m=" + block

                media_data = self._parse_sdp_fields(block)

                media_descriptions.append(
                    MediaDescription(
                        m=str(media_data.get("media", "")),
                        i=str(media_data.get("title")),
                        c=str(media_data.get("connection_info")),
                        k=str(media_data.get("encryption_key")),
                    )
                )

        return SDPMessage(
            **session_data,
            media_descriptions=(media_descriptions if media_descriptions else None),  # pyright: ignore[reportCallIssue]
        )

    def _parse_sdp_fields(self, text: str) -> dict[str, str | list[str] | int]:
        """
        Parse SDP fields from text.

        Good taste: Data-driven, not if-elif hell.
        Works for both session-level and media-level fields.
        """

        FIELD_SPECS = {
            "v": ("version", int, False),
            "o": ("origin", str, False),
            "s": ("session_name", str, False),
            "i": ("title", str, False),
            "u": ("uri", str, False),
            "e": ("email", str, True),
            "p": ("phone", str, True),
            "c": ("connection_info", str, False),
            "b": ("bandwidth_info", str, True),
            "t": ("time_descriptions", "TimeDescription", True),
            "z": ("timezone_adjustments", str, True),
            "k": ("encryption_key", str, False),
            "a": ("attributes", str, True),
            "m": ("media", str, False),
        }

        result = {}

        for line in text.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue

            prefix, _, value = line.partition("=")
            prefix = prefix.strip()
            value = value.strip()

            if prefix not in FIELD_SPECS:
                self.logger.warning(f"Unknown SDP field: {prefix}={value}")
                continue

            field_name, field_type, is_list = FIELD_SPECS[prefix]

            try:
                if isinstance(field_type, int):
                    parsed_value = int(value)
                elif field_type == "TimeDescription":
                    parsed_value = TimeDescription(t=value)
                else:
                    parsed_value = value

                if is_list:
                    result.setdefault(field_name, []).append(parsed_value)
                else:
                    result[field_name] = parsed_value

            except (ValueError, TypeError) as e:
                self.logger.error(f"Failed to parse {prefix}={value}: {e}")

                if isinstance(field_type, int):
                    result[field_name] = 0
                elif not is_list:
                    result[field_name] = ""

        return result


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
