import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import webrtcvad
from websockets.sync.client import connect

from config import Config
from helper.custom_sts_handler import LLM, Speech2Text, Text2Speech
from helper.PROMPT import SYSTEM_PROMPT
from helper.wav_handler import WavHandler
from helper.ws_command import WSCommandHelper
from model.rtp import PayloadType
from model.ws_command import CommandType

# from helper.openai_handler import OpenAiLLM, OpenAiSTT, OpenAiTTS

ws_cmd = WSCommandHelper()
wav_handler = WavHandler()
logger = logging.getLogger()


@dataclass
class RTPPacket:
    payload_type: PayloadType
    data: bytes

    @classmethod
    def from_hex(cls, payload_type: int, hex_string: str) -> "RTPPacket":
        return cls(
            payload_type=PayloadType(payload_type), data=bytes.fromhex(hex_string)
        )


class RTPSession:
    def __init__(
        self,
        vad_mode: int = 0,
        sample_rate: int = 8000,
        frame_duration_ms: int = 20,
    ):
        self.call_id: str = ""
        self.sample_rate: int = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.codec: PayloadType = PayloadType.PCMA
        self.samples_per_frame = (sample_rate * frame_duration_ms) // 1000

        self.buffer: list[RTPPacket] = []

        self.vad = webrtcvad.Vad(vad_mode)
        self.minimum_number_packet = 50

    def add_packet(self, packet: RTPPacket) -> bool:
        pcm_data = wav_handler.hex2pcm([packet.data])

        is_speech_frame = self.vad.is_speech(b"".join(pcm_data), self.sample_rate)
        logger.debug(f"{is_speech_frame=} {pcm_data[0][:20]=}")
        if is_speech_frame:
            self.buffer.append(packet)
            logger.info(f"number of packet {len(self.buffer)}")
        else:
            if len(self.buffer) >= self.minimum_number_packet:
                return True
        return False

    def flush(self) -> list[bytes]:
        data = [p.data for p in self.buffer]
        self.clear()
        return data

    def clear(self) -> None:
        self.buffer.clear()


def main() -> None:
    session = RTPSession()
    llm_handler = LLM(SYSTEM_PROMPT)
    stt = Speech2Text()
    tts = Text2Speech()

    logger.info("LLM and STT/TTS initialized")
    packet_count = 0
    ws_url = os.getenv("WS_URL", "ws://192.168.1.101:8080")
    try:
        with connect(ws_url) as websocket:
            logger.info("WebSocket connected")

            for message in websocket:
                try:
                    cmd = ws_cmd.parser(str(message))
                except Exception as e:
                    logger.warning(
                        f"Invalid message format for call {session.call_id}: {e}"
                    )
                    continue

                if not isinstance(cmd.content, str):
                    continue

                if cmd.type == CommandType.CALL_ANS:
                    session.clear()
                    session.call_id = cmd.content
                    logger.info(f"Call started: {session.call_id}")
                    continue

                if cmd.type == CommandType.BYE:
                    logger.info(f"Call ended: {session.call_id}")
                    continue

                if cmd.type != CommandType.RTP:
                    continue

                try:
                    payload_type, rtp_hex = cmd.content.split("##")
                    packet = RTPPacket.from_hex(int(payload_type), rtp_hex)
                except (ValueError, AttributeError) as e:
                    logger.warning(
                        f"Malformed RTP packet for call {session.call_id}, packet count {packet_count}: {e}"
                    )
                    continue
                except Exception as e:
                    logger.error(
                        f"Unexpected error: {e}",
                        exc_info=True,
                    )
                    continue

                session.codec = packet.payload_type
                if session.call_id == "":
                    continue

                if session.add_packet(packet):
                    packet_count += Config.CALL_CENTER_BUFFER_SIZE
                    logger.info(f"Processed {packet_count} packets")

                    wav_path = None
                    response_audio_path = Path(f"./output/response/{uuid4()}.wav")
                    try:
                        wav_path = wav_handler.hex2wav(session.flush(), session.codec)
                        logger.info(f"WAV file converted at {wav_path}")

                        audio_transcribe, language = stt.transcribe(wav_path)
                        llm_response = llm_handler.generate_response(
                            audio_transcribe, language
                        )
                        logger.info(f"LLM Response: {llm_response}")
                        tts.generate(llm_response, response_audio_path, language)
                        wav_data = wav_handler.wav2base64(response_audio_path)
                        logger.info(f"WAV data: {wav_data[:30]}...")

                        websocket.send(
                            str(
                                ws_cmd.builder(
                                    CommandType.RTP, f"{session.call_id}##{wav_data}"
                                )
                            )
                        )
                        logger.info("Audio sent")
                    except Exception as e:
                        logger.error(
                            f"Processing failed for call {session.call_id}: {e}"
                        )
                        session.clear()
                    finally:
                        logging.info("Cleaning up temporary files")
                        if wav_path and wav_path.exists():
                            wav_path.unlink()
                        if response_audio_path and response_audio_path.exists():
                            response_audio_path.unlink()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] - %(asctime)s - %(message)s - %(pathname)s:%(lineno)d",
        filemode="w+",
        filename="call_center.log",
        datefmt="%y-%m-%d %H:%M:%S",
    )
    main()
