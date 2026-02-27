# Code by DHT@Matthew

import logging
import time
import wave
from pathlib import Path
from typing import Literal

import langid
import torch
from faster_whisper import WhisperModel
from piper import PiperVoice

from helper.llm_backends.api import APIBackend
from helper.llm_backends.llm_backend import LLM
from helper.PROMPT import SYSTEM_PROMPT


class Speech2Text:
    def __init__(
        self,
        model_size: str = "large-v3",
        device: Literal["cuda", "cpu"] = "cuda",
        compute_type: Literal["float16", "int8"] = "float16",
    ) -> None:
        """
        Initialize the model. This is slow, so do it once.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: "cuda" or "cpu" - don't use "auto", tell me what you want
            compute_type: "float16" (GPU) or "int8" (CPU)
        """
        self.logger = logging.getLogger(__name__)

        has_cuda = torch.cuda.is_available()
        self.logger.info(f"{has_cuda=}")

        self.logger.info(f"Initializing Whisper model: {model_size} on {device}")
        start_time = time.time()

        self.model = WhisperModel(
            model_size,
            device=has_cuda and device or "cpu",
            compute_type=has_cuda and compute_type or "int8",
        )

        init_time = time.time() - start_time
        self.logger.info(f"Model loaded in {init_time:.2f}s")

    def transcribe(
        self,
        audio_path: str | Path,
        beam_size: int = 5,
        vad_filter: bool = True,
        language: str | None = None,
    ) -> tuple[str, str]:
        """
        Convert audio to text.

        Args:
            audio_path: Path to audio file
            beam_size: Beam search size, larger = more accurate but slower (5 is fine)
            vad_filter: Voice activity detection, filters silence (highly recommended)
            language: Specify language (None = auto-detect)

        Returns:
            Transcribed text with all segments concatenated

        Raises:
            FileNotFoundError: If audio file doesn't exist
        """
        # Check file exists before wasting time
        if not Path(audio_path).exists():
            self.logger.error(f"Audio file not found: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self.logger.info(f"Transcribing: {audio_path}")
        start_time = time.time()

        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=beam_size,
            vad_filter=vad_filter,
            language=language,
        )

        text = "".join(segment.text for segment in segments)

        elapsed = time.time() - start_time
        self.logger.info(
            f"Transcription complete in {elapsed:.2f}s "
            f"(language: {info.language}, probability: {info.language_probability:.2f})"
        )

        return text, info.language

    def transcribe_detailed(
        self,
        audio_path: str,
        beam_size: int = 5,
        vad_filter: bool = True,
        language: str | None = None,
    ) -> list[dict[str, float | str]]:
        """
        Return results with timestamps.

        Only use this when you actually need timestamps.
        99% of the time, you just need transcribe().

        Args:
            audio_path: Path to audio file
            beam_size: Beam search size
            vad_filter: Voice activity detection
            language: Specify language

        Returns:
            [{"start": 0.0, "end": 2.5, "text": "hello"}, ...]

        Raises:
            FileNotFoundError: If audio file doesn't exist
        """
        if not Path(audio_path).exists():
            self.logger.error(f"Audio file not found: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self.logger.info(f"Transcribing (detailed): {audio_path}")
        start_time = time.time()

        segments, info = self.model.transcribe(
            audio_path, beam_size=beam_size, vad_filter=vad_filter, language=language
        )

        result = [
            {"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments
        ]

        elapsed = time.time() - start_time
        self.logger.info(
            f"Detailed transcription complete in {elapsed:.2f}s "
            f"({len(result)} segments, language: {info.language})"
        )

        return result


class Text2Speech:
    VOICE_MAP = {
        "en": "./voices/en/en_US-lessac-medium.onnx",
        "zh": "./voices/zh/zh_CN-huayan-medium.onnx",
        "zh-tw": "./voices/zh/zh_CN-huayan-medium.onnx",
        "es": "./voices/es/es_ES-sharvard-medium.onnx",
        "fr": "./voices/fr/fr_FR-mls-medium.onnx",
        "de": "./voices/de/de_DE-thorsten-medium.onnx",
        "ar": "./voices/ar/ar_JO-kareem-medium.onnx",
    }

    LANG_CODE_MAP = {
        "en": "en",
        "zh": "zh",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "ar": "ar",
    }

    def __init__(self, default_lang: str = "zh", min_confidence: float = 0.5):
        self.logger = logging.getLogger("TTS")
        if default_lang not in self.VOICE_MAP:
            raise ValueError(f"Invalid default_lang: {default_lang}")

        self.default_lang = default_lang
        self.min_confidence = min_confidence
        self._voices = {}

    def detect_language(self, text: str) -> tuple[str, float]:
        text = text.strip()

        if not text or not any(c.isalpha() for c in text):
            return self.default_lang, 0.0

        detected_lang, confidence = langid.classify(text)

        if detected_lang in self.LANG_CODE_MAP:
            mapped_lang = self.LANG_CODE_MAP[detected_lang]
        else:
            return self.default_lang, 0.0

        if confidence < self.min_confidence:
            return self.default_lang, confidence

        return mapped_lang, confidence

    def _get_voice(self, lang: str) -> PiperVoice:
        if lang not in self.VOICE_MAP:
            raise ValueError(
                f"Unsupported Lang: {lang}, Supported: {list(self.VOICE_MAP.keys())}"
            )

        if lang not in self._voices:
            model_name = self.VOICE_MAP[lang]
            self.logger.info(f"Loading {lang} model: {model_name}...")
            self._voices[lang] = PiperVoice.load(model_name)

        return self._voices[lang]

    def generate(
        self, text: str, output_path: str | Path, lang: str | None = None
    ) -> tuple[str, float]:
        confidence = 1.0

        if lang is None:
            lang, confidence = self.detect_language(text)
        elif lang not in self.VOICE_MAP:
            self.logger.warning(
                f"Unsupported language got: {lang}, using default: {self.default_lang}."
            )
            lang = self.default_lang

        self.logger.info(f"Synthesizing in {lang} (confidence: {confidence:.2f})...")
        voice = self._get_voice(lang)
        with wave.open(str(output_path), "wb") as f:
            voice.synthesize_wav(text, f)

        self.logger.info(f"TTS audio saved to: {output_path}")
        return lang, confidence


async def main() -> None:
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] - %(asctime)s - %(message)s - %(pathname)s:%(lineno)d",
        filemode="w+",
        filename="testing.log",
        datefmt="%y-%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    logger = logging.getLogger()
    logger.addHandler(console_handler)

    llm_backend = APIBackend(system_prompt=SYSTEM_PROMPT)
    stt = Speech2Text()
    llm = LLM(backend=llm_backend)
    tts = Text2Speech()

    print("Start testing...")
    st_time = time.time()
    incoming_voice, _ = stt.transcribe("./audio.wav")
    print(f"Transcription time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    response = await llm.generate_response(incoming_voice, user_id=1234)
    print(response)
    print(f"LLM time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    tts.generate(response, "./output/response/demo1.wav")
    print(f"TTS time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    response = await llm.generate_response(incoming_voice, user_id=1234)
    print(response)
    print(f"LLM time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    tts.generate(response, "./output/response/demo2.wav")
    print(f"TTS time: {time.time() - st_time:.2f}s")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
