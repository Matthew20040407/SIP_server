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

from pydub import AudioSegment  # pyright: ignore[reportMissingImports]

from model.rtp import PayloadType, RTPPacket


class RTPSender:
    def __init__(
        self,
        remote_addr: tuple[str, int],
        ssrc: int,
        sock: socket.socket,
        local_port: int | None = None,
    ) -> None:
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
        self._running = False
        self._thread: threading.Thread | None = None

        self._send_queue: queue.Queue[bytes] = queue.Queue()

    def start(self) -> None:
        """
        Start sender thread.

        audio_generator: A function that returns G.711 A-law bytes (160 bytes for 20ms)
                        Return empty bytes to stop.
        """
        if self._running:
            raise RuntimeError("Sender already running!")

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Previous thread still alive!")

        self._running = True
        self._thread = threading.Thread(
            target=self._send_loop,
            # args=(callback_func,),
            name="RTPSender",  # Thread name for debugging
        )
        self._thread.daemon = True  # Die with main thread
        self._thread.start()

    def _send_loop(self) -> None:
        while self._running:
            try:
                payload = b"\xd5" * 160
                if not self._send_queue.empty():
                    payload = self._send_queue.get_nowait()

                packet = RTPPacket(
                    payload_type=PayloadType.PCMA,
                    sequence=self.sequence,
                    timestamp=self.timestamp,
                    ssrc=self.ssrc,
                    payload=payload,
                )
                self.logger.debug(
                    f"[RTP] Sending {len(payload)} byte to {self.remote_addr}"
                )
                self.sock.sendto(packet.pack(), self.remote_addr)

                if self.sequence % 50 == 0 and logging.root.level != logging.DEBUG:
                    self.logger.info(f"[SEND] {self.sequence=}, {payload[:10].hex()=}")

                # Update state
                self.sequence = (self.sequence + 1) & 0xFFFF
                # Assuming 160 samples per packet (20ms at 8000Hz)
                self.timestamp = (self.timestamp + 160) & 0xFFFFFFFF

                # Sleep 20ms for real-time pacing
                time.sleep(0.020)

            except Exception as e:
                self.logger.exception(
                    f"[SENDER] Exception at packet {self.sequence}: {e}"
                )
                break

        self.logger.info(
            f"[SEND] Loop stopped after {self.sequence} packets, {self._running=}"
        )

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)


class RTPReceiver:
    """
    Pure receiver with optional callback mechanism.

    The callback is invoked IN THE RECEIVER THREAD.
    This means:
    1. Your callback must be fast (< 1ms ideal)
    2. Your callback should not block (no sleep, no heavy I/O)
    3. If callback raises exception, packet is dropped but thread continues
    """

    def __init__(self, sock: socket.socket):
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

        self._recv_queue: queue.Queue[RTPPacket] = queue.Queue()

    def start(self) -> None:
        """
        Start receiver thread.

        Example:
            >>> def log_packet(pkt: RTPPacket):
            ...     print(f"seq={pkt.sequence} ts={pkt.timestamp}")
            >>> receiver.start(log_packet)
        """
        if self._running:
            raise RuntimeError("Sender already running!")

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Previous thread still alive!")

        self._running = True
        self._thread = threading.Thread(
            target=self._recv_loop,
            # args=(packet_callback,),
            name="RTPReceiver",
        )
        self._thread.daemon = True
        self._thread.start()

    def _recv_loop(
        self,
        # packet_callback: Callable[[RTPPacket], None] | None,
    ):
        """
        Main receive loop. Runs in dedicated thread.

        Flow:
        1. Block on socket.recvfrom() (with 1s timeout)
        2. Parse RTP packet
        3. Update internal buffer (for WAV saving)
        4. Update statistics
        ~~5. Invoke callback (if provided)~~
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

                # # Step 5: Invoke user callback (if provided)
                # if packet_callback:
                #     try:
                #         packet_callback(packet)
                #     except Exception as e:
                #         self.logger.exception(f"Callback error: {e}")

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
        """Save received G.711 μ-law to WAV"""

        self.logger.info(f"Saving From buffer: {len(self.recv_buffer)}")
        if not self.recv_buffer:
            return

        pcm_data = []
        for buffer_bytes in self.recv_buffer:
            pcm_bytes = audioop.alaw2lin(buffer_bytes, 2)
            pcm_data.append(pcm_bytes)
        self.logger.info(f"Saving PCM data: {len(pcm_data)}")

        # Write WAV
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            for pcm in pcm_data:
                wav.writeframes(pcm)

        self.logger.info(f"Saved to {output_path}")

    def stop(self) -> None:
        """Graceful shutdown"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _update_stats(self, packet: RTPPacket):
        """
        Internal statistics tracking.
        This shows why callback is cleaner than exposing this via API.
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


class RTPHandler:
    """
    SIP RTP handler with dual ports.

    No shared state between sender and receiver.
    Each owns its own socket, state, and thread.
    """

    def __init__(
        self,
        remote_recv_addr: tuple[str, int],
        local_port: int | None = None,
        ssrc: int = 0x12345678,
    ) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", local_port))
        self.sock.settimeout(1.0)

        self.sender = RTPSender(sock=self.sock, remote_addr=remote_recv_addr, ssrc=ssrc)
        self.receiver = RTPReceiver(sock=self.sock)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"[RTPHandler] {remote_recv_addr=} {local_port=}")

    def start_receiving(self) -> None:
        """Start receiver thread"""
        self.receiver.start()

    def start_sending(self) -> None:
        """Start sending thread"""
        self.sender.start()

    def save_received_wav(self, output_path: Path) -> None:
        """Save all received packets to WAV"""
        self.receiver.save_wav(output_path)

    def stop(self) -> None:
        self.sender.stop()
        self.receiver.stop()
        self.sock.close()
        self.logger.info("Socket closed")

    def put_send_queue(self, audio_packet: list[bytes]) -> None:
        number_of_audio_packet = len(audio_packet)
        self.logger.debug(f"[SEND] Putting {number_of_audio_packet=} into send queue")

        for i, packet in enumerate(audio_packet):
            self.sender._send_queue.put(packet)
            self.logger.debug(f"[SEND] {i} / {number_of_audio_packet} in queue")

    def get_recv_queue(self) -> RTPPacket | None:
        number_of_packet_in_recv_queue = self.receiver._recv_queue.qsize()
        self.logger.debug(f"[RECV] {number_of_packet_in_recv_queue=} in queue")
        self.receiver._recv_queue.get_nowait()

    def wav2bytes(self, audio_file_path: Path) -> list[bytes]:
        """Start sending WAV file (must be 8000Hz mono)"""

        input_path = Path(audio_file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Audio file not found: {input_path}")

        # This part can be comment if websocket generate correct wav file
        #################################################################
        # convert to mono and 8kHz
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
        #################################################################

        packet: list[bytes] = []
        offset = 0
        bytes_per_packet = 160 * 2

        while offset < len(all_frames):
            pcm_bytes = all_frames[offset : offset + bytes_per_packet]
            if len(pcm_bytes) < bytes_per_packet:
                # Pad last packet with silence
                pcm_bytes += b"\x00\x00" * ((bytes_per_packet - len(pcm_bytes)) // 2)

            alaw_bytes = audioop.lin2alaw(pcm_bytes, 2)
            packet.append(alaw_bytes)
            offset += bytes_per_packet

        return packet
