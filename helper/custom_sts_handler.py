# Code by DHT@Matthew

import logging
import time
from pathlib import Path
from typing import Literal, Protocol

import langid
import soundfile as sf
import torch
from transformers import pipeline

torch.set_float32_matmul_precision("high")


class S2T(Protocol):
    def transcribe(
        self,
        audio_path: str | Path,
        beam_size: int = 5,
        vad_filter: bool = True,
        language: str | None = None,
    ) -> tuple[str, str]: ...


class T2S(Protocol):
    def generate(
        self,
        text: str,
        output_path: str | Path,
        lang: str = "",
        top_k: int = 20,
        top_p: float = 0.5,
        temperature: float = 0.3,
        max_new_tokens: int = 1024,
    ) -> None: ...


class STT_Whisper:
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
        try:
            from faster_whisper import (
                WhisperModel,  # type: ignore[reportMissingImports]
            )
        except ImportError:
            return
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


class STT_VibeVoice:
    MODEL_ID = "microsoft/VibeVoice-ASR"

    def __init__(
        self,
        device: Literal["cuda", "cpu"] = "cuda",
    ) -> None:
        self.logger = logging.getLogger(__name__)

        resolved_device = device if torch.cuda.is_available() else "cpu"
        self.logger.info(f"Initializing VibeVoice-ASR on {resolved_device}")
        start_time = time.time()

        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.MODEL_ID,
            device=resolved_device,
        )

        self.logger.info(f"Model loaded in {time.time() - start_time:.2f}s")

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

        Returns:
            (transcribed_text, detected_language_code)

        Raises:
            FileNotFoundError: If audio file doesn't exist
        """

        if not Path(audio_path).exists():
            self.logger.error(f"Audio file not found: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self.logger.info(f"Transcribing: {audio_path}")
        start_time = time.time()

        result: dict = self.pipe(str(audio_path))  # type: ignore[assignment]
        text = result["text"].strip()
        lang, _ = langid.classify(text)

        self.logger.info(
            f"Transcription complete in {time.time() - start_time:.2f}s "
            f"(detected language: {lang})"
        )

        return text, lang


class TTS_Qwen3:
    MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"

    def __init__(
        self,
        device: str = "cuda:0",
        dtype: torch.dtype = torch.bfloat16,
        speaker: str = "Serena",
        language: str = "Chinese",
        instruct: str = "用溫柔親切的客服語氣說",
    ):
        try:
            from qwen_tts import Qwen3TTSModel  # type: ignore[reportMissingImports]
        except ImportError:
            return

        self.logger = logging.getLogger("TTS")
        self.speaker = speaker
        self.language = language
        self.instruct = instruct

        self.logger.info(f"Loading Qwen3TTS model: {self.MODEL_ID}")
        start_time = time.time()
        self.model = Qwen3TTSModel.from_pretrained(
            self.MODEL_ID,
            device_map=device,
            dtype=dtype,
            attn_implementation="flash_attention_2",
        )
        self.logger.info(f"Model loaded in {time.time() - start_time:.2f}s")

    def generate(
        self,
        text: str,
        output_path: str | Path,
        lang: str = "",
        top_k: int = 20,
        top_p: float = 0.5,
        temperature: float = 0.3,
        max_new_tokens: int = 1024,
    ) -> None:
        self.logger.info(f"Synthesizing: {text[:50]}...")
        start_time = time.time()

        wavs, sr = self.model.generate_custom_voice(
            text="".join(char for char in text if char.isalnum()),
            language=lang if lang else self.language,
            speaker=self.speaker,
            instruct=self.instruct,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            non_streaming_mode=False,
        )

        sf.write(str(output_path), wavs[0], sr)
        self.logger.info(
            f"TTS audio saved to {output_path} in {time.time() - start_time:.2f}s"
        )


# test
async def main() -> None:
    import sys

    # from helper.llm_backends.api import APIBackend
    # from helper.llm_backends.llm_backend import LLM
    # from helper.PROMPT import SYSTEM_PROMPT

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

    # llm_backend = APIBackend(system_prompt=SYSTEM_PROMPT)
    stt: S2T = STT_VibeVoice()
    # llm = LLM(backend=llm_backend)
    tts: T2S = TTS_Qwen3()

    print("Start testing...")
    st_time = time.time()
    incoming_voice, _ = stt.transcribe("./audio.wav")
    print(f"Transcription time: {time.time() - st_time:.2f}s")

    # st_time = time.time()
    # response = await llm.generate_response(incoming_voice, user_id=1234)
    # print(response)
    # print(f"LLM time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    tts.generate("請您自我介紹一下好嗎", "./output/response/demo1.wav")
    print(f"TTS time: {time.time() - st_time:.2f}s")

    # st_time = time.time()
    # response = await llm.generate_response(incoming_voice, user_id=1234)
    # print(response)
    # print(f"LLM time: {time.time() - st_time:.2f}s")

    # st_time = time.time()
    # tts.generate(response, "./output/response/demo2.wav")
    # print(f"TTS time: {time.time() - st_time:.2f}s")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
