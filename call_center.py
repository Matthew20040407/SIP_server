import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from websockets.sync.client import connect

from helper.wav_handler import WavHandler
from helper.ws_command import WSCommandHelper
from model.rtp import PayloadType
from model.ws_command import CommandType
from reply_handler import OpenAiLLM, OpenAiSTT, OpenAiTTS

load_dotenv("./.env")
ws_cmd = WSCommandHelper()
wav_handler = WavHandler()
logger = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] - %(asctime)s - %(message)s - %(pathname)s:%(lineno)d",
    filemode="w+",
    filename="call_center.log",
    datefmt="%y-%m-%d %H:%M:%S",
)


class Config:
    BUFFER_SIZE = 120
    LOG_INTERVAL = 50


class LLMHandler:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", None)

        if not api_key:
            raise Exception("No OPENAI_API_KEY")

        self.stt = OpenAiSTT(api_key)
        self.tts = OpenAiTTS(api_key)
        self.llm = OpenAiLLM(api_key, model="gpt-4o-mini")

    def transcript(
        self, audio_input: Path, audio_output: Path, lang: str = "zh"
    ) -> None:
        text = self.stt.transcribe(audio_input)
        reply = self.llm.chat(text)
        self.tts.speak(reply, output=audio_output)


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
    def __init__(self):
        self.call_id: str = ""
        self.codec: PayloadType = PayloadType.PCMA
        self.buffer: list[RTPPacket] = []

    def add_packet(self, packet: RTPPacket) -> bool:
        self.buffer.append(packet)
        logger.debug(len(self.buffer))
        return len(self.buffer) >= Config.BUFFER_SIZE

    def flush(self) -> list[bytes]:
        data = [p.data for p in self.buffer]
        self.buffer.clear()
        return data


def main() -> None:
    session = RTPSession()
    llm_handler = LLMHandler()
    packet_count = 0

    try:
        with connect("ws://192.168.1.101:8080") as websocket:
            logger.info("WebSocket connected")

            for message in websocket:
                try:
                    cmd = ws_cmd.parser(str(message))
                except Exception as e:
                    logger.warning(f"Invalid message format: {e}")
                    continue

                if not isinstance(cmd.content, str):
                    return

                if cmd.type == CommandType.CALL_ANS:
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
                    logger.warning(f"Malformed RTP packet: {e}")
                    continue

                session.codec = packet.payload_type

                if session.add_packet(packet):
                    packet_count += Config.BUFFER_SIZE
                    logger.info(f"Processed {packet_count} packets")

                    try:
                        wav_path = wav_handler.hex2wav(session.flush(), session.codec)
                        # logger.info(wav_data)
                        response_audio_path = Path(f"./output/response/{uuid4()}.wav")
                        llm_handler.transcript(wav_path, response_audio_path)
                        wav_data = wav_handler.wav2base64(response_audio_path)

                        websocket.send(
                            str(
                                ws_cmd.builder(
                                    CommandType.RTP, f"{session.call_id}##{wav_data}"
                                )
                            )
                        )
                    except Exception as e:
                        logger.error(f"WAV conversion failed: {e}")
                        session.buffer.clear()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
