# Code by DHT@Matthew

import struct
from dataclasses import dataclass
from enum import IntEnum


class PayloadType(IntEnum):
    PCMU = 0  # (G.711 μ-law, 8000Hz) - 北美/日本標準
    PCMA = 8  # (G.711 A-law, 8000Hz) - 歐洲標準


@dataclass
class RTPPacket:
    """Same as before, nothing changes here"""

    version: int = 2
    padding: bool = False
    extension: bool = False
    csrc_count: int = 0
    marker: bool = False
    payload_type: PayloadType = PayloadType.PCMA
    sequence: int = 0
    timestamp: int = 0
    ssrc: int = 0
    payload: bytes = b""

    def pack(self) -> bytes:
        b0 = (
            (self.version << 6)
            | (int(self.padding) << 5)
            | (int(self.extension) << 4)
            | self.csrc_count
        )
        b1 = (int(self.marker) << 7) | self.payload_type

        header = struct.pack("!BBHII", b0, b1, self.sequence, self.timestamp, self.ssrc)
        return header + self.payload

    @classmethod
    def unpack(cls, data: bytes) -> "RTPPacket":
        if len(data) < 12:
            raise ValueError("RTP packet too short")

        header = struct.unpack("!BBHII", data[:12])
        b0, b1 = header[0], header[1]

        return cls(
            version=(b0 >> 6) & 0x3,
            padding=bool((b0 >> 5) & 0x1),
            extension=bool((b0 >> 4) & 0x1),
            csrc_count=b0 & 0xF,
            marker=bool((b1 >> 7) & 0x1),
            payload_type=PayloadType(b1 & 0x7F),
            sequence=header[2],
            timestamp=header[3],
            ssrc=header[4],
            payload=data[12:],
        )
