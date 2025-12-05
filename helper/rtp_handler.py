# Code by DHT@Matthew

import audioop
import logging
import queue
import socket
import tempfile
import threading
import time
import wave
from pathlib import Path

from pydub import AudioSegment

from helper.ws_helper import ws_server
from model.rtp import PayloadType, RTPPacket
from model.ws_command import CommandType


class RTPSender:
    """
    RTP packet sender with threaded transmission.

    Sends RTP audio packets at 20ms intervals (50 packets/second) to the
    remote endpoint. Packets are queued for transmission to prevent blocking.

    Attributes:
        remote_addr: Destination (IP, port) for RTP packets
        ssrc: Synchronization source identifier (unique per stream)
        sock: UDP socket for transmission
        codec: Audio codec (PCMA or PCMU)
        sequence: RTP sequence number (0-65535, wraps around)
        timestamp: RTP timestamp (increments by 160 per packet)
    """

    def __init__(
        self,
        remote_addr: tuple[str, int],
        ssrc: int,
        sock: socket.socket,
        codec: PayloadType,
        local_port: int | None = None,
    ) -> None:
        """
        Initialize RTP sender.

        Args:
            remote_addr: Destination (IP, port) tuple
            ssrc: Synchronization source identifier
            sock: UDP socket for sending packets
            codec: Audio payload type (PCMA or PCMU)
            local_port: Local port number (optional, for logging)
        """
        self.logger = logging.getLogger("RTPSender")

        if local_port is not None:
            self.logger.info(f"RTPSender bound to port {local_port}")
        else:
            self.logger.info("RTPSender using kernel-assigned port")

        self.logger.info(f"[RTPSender] {remote_addr=} {local_port=}")
        self.sock = sock

        self.remote_addr = remote_addr
        self.ssrc = ssrc
        self.sequence = 0
        self.timestamp = 0
        self.audio_codec = codec
        self._running = False
        self._thread: threading.Thread | None = None

        self._send_queue: queue.Queue[bytes] = queue.Queue()

    def start(self) -> None:
        """
        Start the RTP sender thread.

        Begins sending RTP packets at 20ms intervals. Packets are retrieved
        from the send queue or filled with silence (0xd5) if queue is empty.

        Raises:
            RuntimeError: If sender is already running or previous thread still alive
        """
        if self._running:
            raise RuntimeError("Sender already running!")

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Previous thread still alive!")

        self._running = True
        self._thread = threading.Thread(
            target=self._send_loop,
            # args=(audio_generator,),
            name="RTPSender",  # Thread name for debugging
        )
        self._thread.daemon = True  # Die with main thread
        self._thread.start()

    def _send_loop(self) -> None:
        """
        Internal send loop running in dedicated thread.

        Continuously sends RTP packets every 20ms (50 packets/second).
        Updates sequence numbers and timestamps automatically.
        """
        while self._running:
            try:
                payload = b"\xd5" * 160

                try:
                    payload = self._send_queue.get()
                except queue.Empty:
                    payload = b"\xd5" * 160

                packet = RTPPacket(
                    payload_type=self.audio_codec,
                    sequence=self.sequence,
                    timestamp=self.timestamp,
                    ssrc=self.ssrc,
                    payload=payload,
                )
                self.sock.sendto(packet.pack(), self.remote_addr)

                if self.sequence % 50 == 0 and logging.root.level != logging.DEBUG:
                    self.logger.info(f"[SEND] {self.sequence=}, {payload[:10].hex()=}")

                # Update state
                self.sequence = (self.sequence + 1) & 0xFFFF
                # Assuming 160 samples per packet (20ms at 8000Hz)
                self.timestamp = (self.timestamp + 160) & 0xFFFFFFFF

                time.sleep(0.01)

            except Exception as e:
                self.logger.exception(
                    f"[SENDER] Exception at packet {self.sequence}: {e}"
                )
                break

        self.logger.info(
            f"[SEND] Loop stopped after {self.sequence} packets, {self._running=}"
        )

    def stop(self) -> None:
        """
        Stop the sender thread gracefully.

        Waits up to 1 second for the thread to terminate.
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def send_rtp_packet(self, packet: bytes) -> None:
        """
        Queue an audio packet for transmission.

        Args:
            packet: G.711 encoded audio data (160 bytes for 20ms)
        """
        self._send_queue.put(packet)


class RTPReceiver:
    """
    Pure receiver with optional callback mechanism.

    The callback is invoked IN THE RECEIVER THREAD.
    This means:
    1. Your callback must be fast (< 1ms ideal)
    2. Your callback should not block (no sleep, no heavy I/O)
    3. If callback raises exception, packet is dropped but thread continues
    """

    def __init__(self, sock: socket.socket, codec: PayloadType):
        """
        Initialize RTP receiver.

        Args:
            sock: UDP socket for receiving RTP packets
            codec: Audio codec for decoding (PCMA or PCMU)
        """
        self.logger = logging.getLogger("RTPReceiver")
        self.sock = sock

        self.recv_buffer: list[bytes] = []
        self._running = False
        self._thread: threading.Thread | None = None

        # Statistics (example of why callback is useful)
        self.stats = {
            "total_packets": 0,
            "total_bytes": 0,
            "lost_packets": 0,
            "last_sequence": -1,
        }

        self.audio_codec = codec

        self._recv_queue: queue.Queue[RTPPacket] = queue.Queue()

    def start(self) -> None:
        """
        Start the RTP receiver thread.

        Begins receiving and processing RTP packets. Received packets
        are stored in the buffer for WAV export and forwarded to WebSocket.

        Raises:
            RuntimeError: If receiver is already running or previous thread still alive
        """
        if self._running:
            raise RuntimeError("Sender already running!")

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Previous thread still alive!")

        self._running = True
        self._thread = threading.Thread(
            target=self._recv_loop,
            name="RTPReceiver",
        )
        self._thread.daemon = True
        self._thread.start()

    def _recv_loop(self):
        """
        Main receive loop. Runs in dedicated thread.

        Flow:
        1. Block on socket.recvfrom() (with 1s timeout)
        2. Parse RTP packet
        3. Update internal buffer (for WAV saving)
        4. Update statistics
        5. Invoke callback (if provided)
        6. Repeat

        Exception handling:
        - Socket timeout: normal, used for checking _running flag
        - Parse error: log and continue (bad packet, keep receiving)
        - Callback exception: log and continue (don't crash receiver)
        """
        number_of_packets = 0

        while self._running:
            try:
                # Step 1: Receive raw bytes
                data, addr = self.sock.recvfrom(2048)

                # Step 2: Parse RTP packet
                number_of_packets += 1
                if number_of_packets % 50 == 0 and logging.root.level != logging.DEBUG:
                    self.logger.info(f"[RTP] Received {len(data)} byte from {addr}")
                try:
                    packet = RTPPacket.unpack(data)

                    # self.logger.info(f"[RECV] Received packet: {packet}")
                    if (
                        number_of_packets % 50 == 0
                        and logging.root.level != logging.DEBUG
                    ):
                        self.logger.info(
                            f"[RECV] {number_of_packets=}, {packet.payload[:10].hex()=}"
                        )

                except ValueError as e:
                    self.logger.error(f"[RTP] parse error: {e}")
                    continue

                # Step 3: Save payload for WAV writing
                self.recv_buffer.append(packet.payload)
                self._recv_queue.put(packet)
                # Step 4: Update statistics
                self._update_stats(packet)

                # Step 5: Sent to ws
                msg = ws_server.builder(
                    CommandType.RTP,
                    message=f"{packet.payload_type}##{packet.payload.hex()}",
                )
                ws_server.send_message(msg)

            except socket.timeout as e:
                self.logger.debug(f"[RTP] Receiver timeout: {e}")
                continue

            except Exception as e:
                if self._running:  # Only log if not shutting down
                    self.logger.warning(
                        f"[RTP] Receiver error: ({type(e).__name__}): {e}"
                    )
                continue

        self.logger.info(
            f"[RECV] Loop stopped after {number_of_packets} packets, {self._running=}"
        )

    def save_wav(self, output_path: Path) -> None:
        """
        Export received audio to WAV file.

        Decodes all buffered G.711 packets to PCM and writes a
        WAV file (8000Hz, stereo, 16-bit).

        Args:
            output_path: Destination file path for WAV output

        Note:
            Returns silently if no packets have been received.
        """
        self.logger.info(f"Saving From buffer: {len(self.recv_buffer)}")
        if not self.recv_buffer:
            return

        pcm_data = []
        # Decode each G.711 packet to PCM
        for buffer_bytes in self.recv_buffer:
            match self.audio_codec:
                case PayloadType.PCMA:
                    pcm_bytes = audioop.alaw2lin(buffer_bytes, 2)

                case PayloadType.PCMU:
                    pcm_bytes = audioop.ulaw2lin(buffer_bytes, 2)

                case _:
                    pcm_bytes = audioop.alaw2lin(buffer_bytes, 2)

            pcm_data.append(pcm_bytes)
        self.logger.info(f"Saving PCM data: {len(pcm_data)}")

        # Write WAV file
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            for pcm in pcm_data:
                wav.writeframes(pcm)

        self.logger.info(f"Saved to {output_path} as {self.audio_codec=}")

    def stop(self) -> None:
        """
        Stop the receiver thread gracefully.

        Waits up to 2 seconds for the thread to terminate.
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _update_stats(self, packet: RTPPacket):
        """
        Track packet statistics and detect packet loss.

        Updates counters for total packets, bytes, and detects
        sequence number gaps to identify lost packets.

        Args:
            packet: RTPPacket to process for statistics
        """
        self.stats["total_packets"] += 1
        self.stats["total_bytes"] += len(packet.payload)

        # Detect packet loss (sequence number gap)
        if self.stats["last_sequence"] >= 0:
            expected_seq = (self.stats["last_sequence"] + 1) & 0xFFFF
            if packet.sequence != expected_seq:
                # Handle sequence number wraparound
                if packet.sequence > expected_seq:
                    lost = packet.sequence - expected_seq
                else:
                    lost = (0xFFFF - expected_seq) + packet.sequence + 1
                self.stats["lost_packets"] += lost

        self.stats["last_sequence"] = packet.sequence

    def get_stats(self) -> dict:
        """
        Thread-safe stats read.
        Returns a copy to avoid race conditions.
        """
        return self.stats.copy()

    def get_rtp_packet(self, timeout: float = 0.07) -> RTPPacket | None:
        """
        Retrieve next RTP packet from receive queue.

        Args:
            timeout: Maximum time to wait for packet in seconds

        Returns:
            RTPPacket if available within timeout, None otherwise
        """
        try:
            return self._recv_queue.get(timeout=timeout)
        except queue.Empty:
            return None


class RTPHandler:
    """
    Unified RTP sender and receiver handler.

    Combines RTP transmission and reception on a single UDP socket,
    with support for WAV file playback and recording.

    Attributes:
        sock: UDP socket for RTP communication
        sender: RTP packet sender instance
        receiver: RTP packet receiver instance
        audio_codec: Audio codec (PCMA or PCMU)
    """

    def __init__(
        self,
        remote_recv_addr: tuple[str, int],
        local_ip: str = "192.168.1.101",
        local_port: int | None = None,
        ssrc: int = 0x12345678,
        codec: PayloadType = PayloadType.PCMA,
    ) -> None:
        """
        Initialize RTP handler with sender and receiver.

        Args:
            remote_recv_addr: Remote endpoint (IP, port) for sending RTP
            local_ip: Local IP address to bind to
            local_port: Local port to bind to (None = kernel assigned)
            ssrc: Synchronization source identifier
            codec: Audio codec (PCMA or PCMU)
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((local_ip, local_port))
        self.sock.settimeout(1.0)

        self.audio_codec = codec
        self.sender = RTPSender(
            sock=self.sock,
            remote_addr=remote_recv_addr,
            ssrc=ssrc,
            codec=self.audio_codec,
        )
        self.receiver = RTPReceiver(sock=self.sock, codec=self.audio_codec)

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"[RTPHandler] {remote_recv_addr=} {local_port=}")

    def start(self) -> None:
        """
        Start both RTP sender and receiver threads.

        Begins receiving RTP packets and starts the sender thread
        which will send packets as they are queued.
        """
        self.receiver.start()
        self.sender.start()

    def send_wav(self, audio_file_path: Path) -> None:
        """
        Load and send a WAV file as RTP packets.

        The WAV file is automatically converted to 8000Hz mono and
        encoded with the configured codec (PCMA/PCMU). Audio is sent
        at 20ms intervals (160 samples per packet).

        Args:
            audio_file_path: Path to WAV audio file

        Raises:
            FileNotFoundError: If audio file doesn't exist
            ValueError: If WAV format validation fails after conversion
        """

        input_path = Path(audio_file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Audio file not found: {input_path}")

        # Convert to mono and 8kHz
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_channels(1).set_frame_rate(8000)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            audio.export(tmp.name, format="wav")
            with wave.open(tmp.name, "rb") as wav:
                if wav.getframerate() != 8000:
                    raise ValueError("WAV must be 8000Hz")
                if wav.getnchannels() != 1:
                    raise ValueError("WAV must be mono")

                all_frames = wav.readframes(wav.getnframes())

        packets: list[bytes] = []
        offset = 0
        bytes_per_packet = 160 * 2

        while offset < len(all_frames):
            pcm_bytes = all_frames[offset : offset + bytes_per_packet]
            if len(pcm_bytes) < bytes_per_packet:
                # Pad last packet with silence
                pcm_bytes += b"\x00\x00" * ((bytes_per_packet - len(pcm_bytes)) // 2)

            match self.audio_codec:
                case PayloadType.PCMA:
                    alaw_bytes = audioop.lin2alaw(pcm_bytes, 2)

                case PayloadType.PCMU:
                    alaw_bytes = audioop.lin2ulaw(pcm_bytes, 2)

            packets.append(alaw_bytes)
            self.send_packet(alaw_bytes)
            offset += bytes_per_packet

    def save_received_wav(self, output_path: Path) -> None:
        """
        Save all received RTP packets as a WAV file.

        Decodes received G.711 packets to PCM and writes a WAV file
        at 8000Hz stereo (2 channels, 16-bit).

        Args:
            output_path: Destination file path for WAV file
        """
        self.receiver.save_wav(output_path)

    def stop(self) -> None:
        """
        Stop RTP handler and close socket.

        Gracefully stops both sender and receiver threads,
        then closes the UDP socket.
        """
        self.sender.stop()
        self.receiver.stop()
        self.sock.close()
        self.logger.info("Socket closed")

    def send_packet(self, packet: bytes) -> None:
        """
        Queue a single audio packet for transmission.

        Args:
            packet: G.711 encoded audio (160 bytes)
        """
        self.sender.send_rtp_packet(packet)

    def recv_packet(self) -> RTPPacket | None:
        """
        Retrieve a received RTP packet from the queue.

        Returns:
            RTPPacket if available, None if queue is empty after timeout
        """
        return self.receiver.get_rtp_packet()
