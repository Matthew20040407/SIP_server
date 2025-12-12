# Code by DHT@Matthew

import audioop
import base64
import wave
from pathlib import Path
from uuid import uuid4

from pydub import AudioSegment

from model.rtp import PayloadType


class WavHandler:
    @staticmethod
    def _normalize_audio(audio: AudioSegment) -> AudioSegment:
        if audio.channels == 1 and audio.frame_rate == 8000:
            return audio

        return audio.set_channels(1).set_frame_rate(8000)

    @staticmethod
    def _get_pcm_data(audio: AudioSegment) -> bytes:
        return audio.raw_data  # pyright: ignore[reportReturnType]

    @staticmethod
    def _encode_packets(
        pcm_data: bytes, codec: PayloadType = PayloadType.PCMA
    ) -> list[bytes]:
        """160 samples/packet @ 8kHz = 20ms"""
        packets = []
        bytes_per_packet = 160 * 2  # 160 samples * 2 bytes

        for offset in range(0, len(pcm_data), bytes_per_packet):
            chunk = pcm_data[offset : offset + bytes_per_packet]

            if len(chunk) < bytes_per_packet:
                chunk += b"\x00" * (bytes_per_packet - len(chunk))

            if codec == PayloadType.PCMA:
                encoded = audioop.lin2alaw(chunk, 2)
            elif codec == PayloadType.PCMU:
                encoded = audioop.lin2ulaw(chunk, 2)
            else:
                raise ValueError(f"Unsupported codec: {codec}")

            packets.append(encoded)

        return packets

    def _audio_to_packets(
        self, audio: AudioSegment, codec: PayloadType = PayloadType.PCMA
    ) -> list[bytes]:
        normalized = self._normalize_audio(audio)
        pcm_data = self._get_pcm_data(normalized)
        return self._encode_packets(pcm_data, codec)

    def wav2pcm(
        self, wav_path: Path, codec: PayloadType = PayloadType.PCMA
    ) -> list[bytes]:
        audio = AudioSegment.from_file(wav_path)
        return self._audio_to_packets(audio, codec)

    def hex2pcm(
        self,
        list_of_bytes: list[bytes],
        codec: PayloadType = PayloadType.PCMA,
    ) -> list[bytes]:
        pcm_data = []
        for buffer_bytes in list_of_bytes:
            match codec:
                case PayloadType.PCMA:
                    pcm_bytes = audioop.alaw2lin(buffer_bytes, 2)

                case PayloadType.PCMU:
                    pcm_bytes = audioop.ulaw2lin(buffer_bytes, 2)

                case _:
                    pcm_bytes = audioop.alaw2lin(buffer_bytes, 2)

            pcm_data.append(pcm_bytes)
        return pcm_data

    def hex2wav(
        self,
        list_of_bytes: list[bytes],
        codec: PayloadType = PayloadType.PCMA,
        output_wav_path: Path | None = None,
    ) -> Path:
        output_path = (
            output_wav_path
            if output_wav_path and output_wav_path.exists()
            else Path(f"./output/convented/{uuid4()}.wav")
        )

        pcm_data = self.hex2pcm(list_of_bytes, codec)

        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            for pcm in pcm_data:
                wav.writeframes(pcm)

        return output_path

    def b642pcm(
        self,
        b64_string: str,
        codec: PayloadType = PayloadType.PCMA,
        sample_rate: int = 8000,
        channels: int = 1,
    ) -> list[bytes]:
        pcm_bytes = base64.b64decode(b64_string)
        audio = AudioSegment(
            data=pcm_bytes, sample_width=2, frame_rate=sample_rate, channels=channels
        )
        return self._audio_to_packets(audio, codec)

    def wav2base64(self, wav_path: Path) -> str:
        audio = AudioSegment.from_file(wav_path)
        normalized = self._normalize_audio(audio)
        return base64.b64encode(normalized.raw_data).decode("ascii")  # pyright: ignore[reportArgumentType]

    def convert_wav(self, input_path: Path, output_path: Path) -> None:
        audio = AudioSegment.from_file(input_path)
        normalized = self._normalize_audio(audio)
        normalized.export(output_path, format="wav")
