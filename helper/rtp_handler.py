# Code by DHT@Matthew

import audioop
import logging
import queue
import socket
import tempfile
import threading
import time
import wave
from collections import deque
from pathlib import Path

import numpy as np
import torch
from pydub import AudioSegment
from silero_vad import load_silero_vad

from helper.ws_helper import ws_server
from model.rtp import PayloadType, RTPPacket
from model.ws_command import CommandType


class VADHandler:
    """
    Voice Activity Detection (VAD) handler using a Silero VAD model.
    Processes incoming PCM audio packets to determine speech activity.
    """

    def __init__(self, vad_model, sample_rate=8000, vad_chunk_size=256):
        self.logger = logging.getLogger("VADHandler")
        self.vad = vad_model
        self.sample_rate = sample_rate
        self.vad_chunk_size = vad_chunk_size

        self.window = deque(maxlen=vad_chunk_size)

        self.speech_count = 0
        self.silence_count = 0
        self.threshold_frames = 2

        self.is_speaking = False

    def process_packet(self, pcm_bytes: bytes) -> bool:
        audio_np = np.frombuffer(pcm_bytes, dtype=np.int16)
        audio_float = audio_np.astype(np.float32) / 32768.0

        self.window.extend(audio_float)

        if len(self.window) < self.vad_chunk_size:
            return self.is_speaking

        vad_input = torch.tensor(list(self.window), dtype=torch.float32)

        speech_prob = self.vad(vad_input, self.sample_rate)
        self.logger.debug(f"[VAD] speech probability: {speech_prob.item():.4f}")
        has_speech = speech_prob > 0.5

        if has_speech:
            self.speech_count += 1
            self.silence_count = 0
        else:
            self.silence_count += 1
            self.speech_count = 0

        if self.speech_count >= self.threshold_frames:
            self.is_speaking = True
        elif self.silence_count >= self.threshold_frames:
            self.is_speaking = False

        return self.is_speaking


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

        # Voice activity detection control
        self._paused = False

    def start(self) -> None:
        if self._running:
            raise RuntimeError("Sender already running!")

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Previous thread still alive!")

        self._running = True
        self._thread = threading.Thread(
            target=self._send_loop,
            name="RTPSender",
        )
        self._thread.daemon = True  # Die with main thread
        self._thread.start()

    def _send_loop(self) -> None:
        while self._running:
            try:
                if self._paused:
                    while not self._send_queue.empty():
                        try:
                            self._send_queue.get_nowait()
                        except queue.Empty:
                            break

                    payload = b"\xd5" * 160
                else:
                    try:
                        payload = self._send_queue.get(block=True, timeout=0.02)
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
                    status = "PAUSED" if self._paused else "ACTIVE"
                    self.logger.info(
                        f"[SEND {status}] {self.sequence=}, {payload[:10].hex()=}"
                    )

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
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def send_rtp_packet(self, packet: bytes) -> None:
        self._send_queue.put(packet)

    def pause(self) -> None:
        if not self._paused:
            self._paused = True
            self.logger.info("[SENDER] Paused - user is speaking")

    def resume(self) -> None:
        if self._paused:
            self._paused = False
            self.logger.info("[SENDER] Resumed - user stopped speaking")

    def is_paused(self) -> bool:
        return self._paused

    def get_send_queue(self) -> queue.Queue[bytes]:
        return self._send_queue


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
        self.logger = logging.getLogger("RTPReceiver")
        self.sock = sock

        self.recv_buffer: list[bytes] = []
        self._running = False
        self._thread: threading.Thread | None = None

        self.audio_codec = codec

        self._recv_queue: queue.Queue[RTPPacket] = queue.Queue()

    def start(self) -> None:
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
        number_of_packets = 0

        while self._running:
            try:
                # Step 1: Receive raw bytes
                data, addr = self.sock.recvfrom(2048)

                # Step 2: Parse RTP packet
                number_of_packets += 1
                if number_of_packets % 50 == 0 and logging.root.level != logging.DEBUG:
                    self.logger.info(
                        f"[RTP-RECV] Received {len(data)} byte from {addr}"
                    )
                try:
                    packet = RTPPacket.unpack(data)

                    self.logger.debug(f"[RTP-RECV] Received packet: {packet}")
                    if (
                        number_of_packets % 50 == 0
                        and logging.root.level != logging.DEBUG
                    ):
                        self.logger.info(
                            f"[RTP-RECV] {number_of_packets=}, {packet.payload[:10].hex()=}"
                        )

                except ValueError as e:
                    self.logger.error(f"[RTP-RECV] parse error: {e}")
                    continue

                # Step 3: Save payload for WAV writing
                self.recv_buffer.append(packet.payload)
                self._recv_queue.put(packet)

                # Step 4: Sent to ws
                try:
                    msg = ws_server.builder(
                        CommandType.RTP,
                        message=f"{packet.payload_type}##{packet.payload.hex()}",
                    )
                    ws_server.send_message(msg)
                except queue.Empty:
                    continue
                except queue.Full:
                    self.logger.error("[RTP-RECV] WS send queue full, dropping packet")
                    self._recv_queue.get()

            except socket.timeout as e:
                self.logger.debug(f"[RTP-RECV] Receiver timeout: {e}")
                continue

            except Exception as e:
                if self._running:
                    self.logger.warning(
                        f"[RTP-RECV] Receiver error: ({type(e).__name__}): {e}"
                    )
                continue

        self.logger.info(
            f"[RECV] Loop stopped after {number_of_packets} packets, {self._running=}"
        )

    def save_wav(self, output_path: Path) -> None:
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
            wav.setnchannels(1)  # Mono (RTP audio is mono)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            for pcm in pcm_data:
                wav.writeframes(pcm)

        self.logger.info(f"Saved to {output_path} as {self.audio_codec=}")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_rtp_packet(self, timeout: float = 0.07) -> RTPPacket | None:
        try:
            return self._recv_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_recv_queue(self) -> queue.Queue[RTPPacket]:
        return self._recv_queue


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

        self.vad = VADHandler(load_silero_vad())

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"[RTPHandler] {remote_recv_addr=} {local_port=}")

    def start(self) -> None:
        self.receiver.start()
        self.sender.start()

    def send_wav(self, audio_file_path: Path) -> None:
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
        self.receiver.save_wav(output_path)

    def stop(self) -> None:
        self.sender.stop()
        self.receiver.stop()
        self.sock.close()
        self.logger.info("Socket closed")

    def send_packet(self, packet: bytes) -> None:
        self.sender.send_rtp_packet(packet)

    # def recv_packet(self) -> RTPPacket | None:
    #     return self.receiver.get_rtp_packet()

    def pause_sending(self) -> None:
        self.sender.pause()

    def resume_sending(self) -> None:
        self.sender.resume()

    def update_sending_state(self) -> None:
        packet = self.receiver.get_rtp_packet()
        if packet is None:
            return

        is_speaking = self.vad.process_packet(packet.payload)
        if is_speaking:
            self.sender.pause()
            self.logger.debug("VAD: SPEECH detected - pausing sender")
        else:
            self.sender.resume()
            self.logger.debug("VAD: SILENCE detected - resuming sender")

    def __enter__(self) -> "RTPHandler":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        return None
