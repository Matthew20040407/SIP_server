# Code by DHT@Matthew

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from secrets import randbits

import websockets

from helper.rtp_handler import RTPHandler
from model.sip_message import MediaDescription, SDPMessage, TimeDescription


@dataclass
class RTPSessionParams:
    """
    Extracted RTP parameters from SDPMessage.
    This is the bridge between Pydantic (SDP) and RTPHandle (network).
    """

    remote_ip: str
    remote_port: int
    payload_type: int
    codec: str
    sample_rate: int

    @classmethod
    def from_sdp(cls, sdp: SDPMessage) -> "RTPSessionParams":
        """
        Extract RTP info from your Pydantic SDPMessage.

        Args:
            sdp: Parsed SDP from SIP INVITE

        Returns:
            RTPSessionParams ready for RTPHandle initialization

        Raises:
            ValueError: If SDP is invalid or missing required fields
        """
        # Step 1: Get remote IP from connection_info
        # Format: "IN IP4 192.168.1.170"
        logger = logging.getLogger("RTPSessionParams")
        logger.info(sdp)

        if not sdp.media_descriptions:
            raise ValueError("No media descriptions in SDP")

        if sdp.connection_info:
            sdp_connection_info = sdp.connection_info
        elif sdp.media_descriptions[0].connection_info:
            sdp_connection_info = sdp.media_descriptions[0].connection_info
        else:
            logger.info(sdp.media_descriptions[0].connection_info)
            raise ValueError("No connection_info in SDP")

        conn_parts = sdp_connection_info.split()
        if len(conn_parts) < 3:
            raise ValueError(f"Invalid connection_info: {sdp_connection_info}")

        remote_ip = conn_parts[2]

        # Step 2: Get media description (first audio stream)
        if not sdp.media_descriptions:
            raise ValueError("No media descriptions in SDP")

        audio_media = sdp.media_descriptions[0]

        # Media-level connection_info overrides session-level
        if audio_media.connection_info:
            media_conn = audio_media.connection_info.split()
            remote_ip = media_conn[2]

        # Step 3: Parse media line
        # Format: "audio 4000 RTP/AVP 0 8 96"
        #          ^     ^    ^       ^^^^^^^
        #          type  port proto   payload types
        media_parts = audio_media.media.split()

        if len(media_parts) < 4:
            raise ValueError(f"Invalid media line: {audio_media.media}")

        media_type = media_parts[0]
        if media_type != "audio":
            raise ValueError(f"Only audio media supported, got: {media_type}")

        remote_port = int(media_parts[1])

        # Get first payload type
        payload_type = int(media_parts[3])

        # Step 4: Extract codec info from rtpmap attribute
        codec = cls._get_codec_name(payload_type)
        sample_rate = 8000  # Default

        if audio_media.attributes:
            for attr in audio_media.attributes:
                if attr.startswith("rtpmap:"):
                    rtpmap_value = attr.split(":", 1)[1]
                    pt_str, codec_info = rtpmap_value.split(" ", 1)

                    if int(pt_str) == payload_type:
                        codec_parts = codec_info.split("/")
                        codec = codec_parts[0]
                        if len(codec_parts) > 1:
                            sample_rate = int(codec_parts[1])
                        break

        return cls(
            remote_ip=remote_ip,
            remote_port=remote_port,
            payload_type=payload_type,
            codec=codec,
            sample_rate=sample_rate,
        )

    @staticmethod
    def _get_codec_name(payload_type: int) -> str:
        """
        Get codec name from payload type (for well-known types).
        RFC 3551 static payload types.
        """
        STATIC_PAYLOAD_TYPES = {
            0: "PCMU",  # G.711 μ-law
            3: "GSM",
            4: "G723",
            5: "DVI4",
            6: "DVI4",
            7: "LPC",
            8: "PCMA",  # G.711 A-law
            9: "G722",
            10: "L16",
            11: "L16",
            12: "QCELP",
            13: "CN",
            14: "MPA",
            15: "G728",
            16: "DVI4",
            17: "DVI4",
            18: "G729",
        }
        return STATIC_PAYLOAD_TYPES.get(payload_type, "unknown")


class RTPPortAllocator:
    """
    Simple port allocator for RTP/RTCP pairs.

    RTP convention:
    - RTP uses even port (e.g., 10000)
    - RTCP uses next odd port (e.g., 10001)

    We allocate pairs: (send_port, recv_port)
    """

    def __init__(self, start_port: int = 31000, end_port: int = 31010):
        """
        Args:
            start_port: Start of port range (must be even)
            end_port: End of port range
        """
        if start_port % 2 != 0:
            raise ValueError("start_port must be even")

        self.start_port = start_port
        self.end_port = end_port
        self.next_port = start_port
        self.allocated: set[int] = set()

    def allocate_pair(self) -> tuple[int, int]:
        """
        Allocate a pair of ports: (send_port, recv_port)

        Returns:
            (send_port, recv_port): Both even numbers, 2 apart

        Raises:
            RuntimeError: If no ports available
        """
        # Find next available even port
        while self.next_port < self.end_port:
            send_port = self.next_port
            recv_port = self.next_port + 2

            self.next_port += 4  # Skip to next pair

            # Check if already allocated
            if send_port not in self.allocated and recv_port not in self.allocated:
                self.allocated.add(send_port)
                self.allocated.add(recv_port)
                return (send_port, recv_port)

        raise RuntimeError("No available ports in range")

    def release_pair(self, send_port: int, recv_port: int):
        """Release a previously allocated pair"""
        self.allocated.discard(send_port)
        self.allocated.discard(recv_port)


class SDPBuilder:
    """
    Build SDPMessage for SIP responses.
    Works with your existing Pydantic models.
    """

    @staticmethod
    def build_answer(
        local_ip: str,
        local_recv_port: int,
        offer_params: RTPSessionParams,
        session_id: int | None = None,
    ) -> SDPMessage:
        """
        Build SDP answer for 200 OK response.

        Args:
            local_ip: Your server's IP address
            local_recv_port: Port where you'll receive RTP (CRITICAL!)
            offer_params: Extracted params from INVITE
            session_id: Unique session ID (default: random)

        Returns:
            SDPMessage ready to serialize into 200 OK

        CRITICAL: local_recv_port must match the port where your
                  RTPHandle.receiver is listening!
        """
        if session_id is None:
            import random

            session_id = random.randint(1000000, 9999999)

        # Build origin line: "- {sess_id} {sess_version} IN IP4 {ip}"
        origin = f"- {session_id} {session_id} IN IP4 {local_ip}"

        # Build media description
        media_desc = MediaDescription(
            m=f"audio {local_recv_port} RTP/AVP {offer_params.payload_type}",
            a=[
                f"rtpmap:{offer_params.payload_type} {offer_params.codec}/{offer_params.sample_rate}"
            ],
        )

        # Build complete SDP
        return SDPMessage(
            v=0,
            o=origin,
            s="-",  # Session name (usually just "-")
            c=f"IN IP4 {local_ip}",
            t=[TimeDescription(t="0 0")],  # Active time (0 0 = permanent)
            m=[media_desc],
        )


class SIPSession:
    """
    Complete SIP + RTP session handler.
    Integrates with your existing Pydantic SDPMessage models.

    Usage:
        session = SIPRTPSession(local_ip="192.168.157.126")

        # When INVITE arrives
        sdp_offer = SDPMessage.model_validate(parsed_sip_body)
        sdp_answer = session.handle_invite(sdp_offer)

        # Send 200 OK with sdp_answer.model_dump()

        # After ACK received
        session.start_audio(mode="tone")

        # On BYE
        session.stop_and_save(Path("recording.wav"))
    """

    def __init__(self, local_ip: str):
        """
        Args:
            local_ip: Your SIP server's IP address (for SDP)
        """
        self.logger = logging.getLogger("SIP-RTP session")
        self.local_ip = local_ip

        # RTP state
        self.rtp_handle: RTPHandler | None = None
        self.params: RTPSessionParams | None = None
        self.local_send_port: int | None = None
        self.local_recv_port: int | None = None

        self.rtp_port_allocator = RTPPortAllocator()

    def create_sdp_offer(
        self,
        payload_type: int = 0,
        codec: str = "PCMA",
        sample_rate: int = 8000,
    ) -> SDPMessage:
        """
        Create SDP offer for outgoing calls.

        Args:
            payload_type: RTP payload type (default: 0 for PCMU)
            codec: Codec name (default: "PCMU")
            sample_rate: Sample rate in Hz (default: 8000)

        Returns:
            SDPMessage offer to include in INVITE

        Example:
            >>> session = SIPRTPSession(local_ip="192.168.1.101")
            >>> sdp_offer = session.create_sdp_offer()
            >>> # Include sdp_offer in INVITE request
        """
        # Allocate local RTP ports
        self.local_send_port, self.local_recv_port = (
            self.rtp_port_allocator.allocate_pair()
        )

        self.logger.info("> Creating SDP offer for outgoing call")
        self.logger.info(f"   Send: {self.local_send_port}")
        self.logger.info(f"   Recv: {self.local_recv_port}")

        # Generate session ID
        import random

        session_id = random.randint(1000000, 9999999)

        # Build origin line
        origin = f"- {session_id} {session_id} IN IP4 {self.local_ip}"

        # Build media description
        media_desc = MediaDescription(
            m=f"audio {self.local_recv_port} RTP/AVP {payload_type}",
            a=[f"rtpmap:{payload_type} {codec}/{sample_rate}"],
        )

        # Build complete SDP offer
        sdp_offer = SDPMessage(
            v=0,
            o=origin,
            s="-",
            c=f"IN IP4 {self.local_ip}",
            t=[TimeDescription(t="0 0")],
            m=[media_desc],
        )

        self.logger.info("> SDP offer created")

        return sdp_offer

    def handle_invite(
        self,
        sdp_offer: SDPMessage,
    ) -> SDPMessage:
        """
        Process SIP INVITE with SDP offer, setup RTP, return SDP answer.

        Args:
            sdp_offer: Parsed SDP from INVITE (your Pydantic model)

        Returns:
            SDPMessage answer (serialize this into 200 OK body)

        Example:
            >>> # In your SIP handler
            >>> sdp_offer = SDPMessage.model_validate(invite_body)
            >>> sdp_answer = session.handle_invite(sdp_offer)
            >>> response_body = sdp_answer.model_dump(by_alias=True, exclude_none=True)
        """
        # Step 1: Extract RTP parameters from SDP offer
        self.params = RTPSessionParams.from_sdp(sdp_offer)

        self.logger.info("> Incoming call")
        self.logger.info(
            f"   Remote: {self.params.remote_ip}:{self.params.remote_port}"
        )
        self.logger.info(f"   Codec: {self.params.codec}/{self.params.sample_rate}Hz")
        self.logger.info(f"   Payload Type: {self.params.payload_type}")
        self.logger.info(self.params)  # Debug

        # Step 2: Allocate local RTP ports
        self.local_send_port, self.local_recv_port = (
            self.rtp_port_allocator.allocate_pair()
        )

        self.logger.info("> Allocated RTP ports:")
        self.logger.info(f"   Send: {self.local_send_port}")
        self.logger.info(f"   Recv: {self.local_recv_port}")

        # Step 3: Create RTPHandle
        self.rtp_handle = RTPHandler(
            local_port=self.local_send_port,
            remote_recv_addr=(self.params.remote_ip, self.params.remote_port),
            ssrc=randbits(32),
        )

        # Step 4: Build SDP answer
        sdp_answer = SDPBuilder.build_answer(
            local_ip=self.local_ip,
            local_recv_port=self.local_recv_port,
            offer_params=self.params,
        )

        self.logger.info("> RTP session ready")

        return sdp_answer


class SIPRTPSession(SIPSession):
    def __init__(self, local_ip: str):
        super().__init__(local_ip)

    def start_audio(self, mode: str = "wav", wav_path: Path | None = None):
        """
        Start sending audio after call established (ACK received).

        Args:
            mode: "dummy" or "wav"
            wav_path: Path to WAV file (required if mode="wav")
            frequency: Tone frequency in Hz (default: 1000Hz)

        Raises:
            RuntimeError: If RTPHandle not initialized (call handle_invite first)
            ValueError: If invalid mode or missing wav_path
        """
        if not self.rtp_handle:
            raise RuntimeError("Call handle_invite() first")

        self.logger.info(f"[Mode] {mode}")
        self.logger.info(f"Send from {self.local_send_port}")
        self.logger.info(f"Listening {self.local_recv_port}")

        self.rtp_handle.start_receiving()

        if mode == "wav":
            if not wav_path:
                raise ValueError("wav_path required for mode='wav'")
            if not wav_path.exists():
                raise ValueError(f"WAV file not found: {wav_path}")

            wav_packet = self.rtp_handle.wav2bytes(wav_path)
            self.rtp_handle.put_send_queue(wav_packet)
            self.logger.info(f"\tFile: {wav_path}")
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def stop_and_save(self, output_path: Path | None = None):
        """
        Stop RTP session and optionally save received audio.

        Args:
            output_path: Where to save received audio (None = don't save)
        """
        if not self.rtp_handle:
            return

        self.rtp_handle.stop()

        if output_path:
            self.logger.info(f"> Saving received audio to {output_path}")
            self.rtp_handle.save_received_wav(output_path)

        # Release ports
        if self.local_send_port and self.local_recv_port:
            self.rtp_port_allocator.release_pair(
                self.local_send_port, self.local_recv_port
            )

        self.logger.info("> Session ended")


class SIPWSSession(SIPSession):
    def __init__(self, local_ip: str):
        super().__init__(local_ip)

    def start_communication(
        self,
        host: str = "192.168.1.101",
        port: int = 8080,
    ) -> None:
        if not self.rtp_handle:
            raise RuntimeError("Call handle_invite() first")

        uri = f"ws://{host}:{port}"
        self.logger.info("[Mode] WS communication")
        self.logger.info(f"Send from {self.local_send_port}")
        self.logger.info(f"Listening {self.local_recv_port}")
        self.logger.info(f"[WS] {uri=}")

        asyncio.get_event_loop().run_until_complete(
            websockets.serve(self.echo, "localhost", port)
        )

        asyncio.get_event_loop().run_forever()

    async def hello(self, uri):
        async with websockets.connect(uri) as websocket:
            await websocket.send("Jimmy")
            await websocket.recv()

    async def echo(self, websocket, path):
        async for message in websocket:
            print(message, "received from client")
            greeting = f"Hello {message}!"
            await websocket.send(greeting)
            print(f"> {greeting}")
