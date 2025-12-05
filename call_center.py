import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from websockets.sync.client import connect

from config import Config
from helper.wav_handler import WavHandler
from helper.ws_command import WSCommandHelper
from model.rtp import PayloadType
from model.ws_command import CommandType
from reply_handler import OpenAiLLM, OpenAiSTT, OpenAiTTS

ws_cmd = WSCommandHelper()
wav_handler = WavHandler()
logger = logging.getLogger()


class LLMHandler:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", None)

        if not api_key:
            raise Exception("No OPENAI_API_KEY")

        self.stt = OpenAiSTT(api_key)
        self.tts = OpenAiTTS(api_key)
        self.llm = OpenAiLLM(api_key, model="gpt-4o-mini")

    def transcript(self, audio_input: Path, audio_output: Path) -> None:
        text = self.stt.transcribe(audio_input)
        logger.info(f"User: {text}")
        reply = self.llm.chat(text)
        logger.info(f"AI: {reply}")
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
        return len(self.buffer) >= Config.CALL_CENTER_BUFFER_SIZE

    def flush(self) -> list[bytes]:
        data = [p.data for p in self.buffer]
        self.buffer.clear()
        return data


def main() -> None:
    session = RTPSession()
    llm_handler = LLMHandler()
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
                    session.buffer.clear()
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

                session.codec = packet.payload_type

                if session.add_packet(packet):
                    packet_count += Config.CALL_CENTER_BUFFER_SIZE
                    logger.info(f"Processed {packet_count} packets")

                    wav_path = None
                    response_audio_path = None
                    try:
                        wav_path = wav_handler.hex2wav(session.flush(), session.codec)
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
                        logger.error(
                            f"Processing failed for call {session.call_id}: {e}"
                        )
                        session.buffer.clear()
                    finally:
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
