# Code by DHT@Matthew

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


class OpenAiSTT:
    def __init__(self, api_key: str, model: str = "whisper-1"):
        if not api_key:
            raise ValueError("API key cannot be empty")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def transcribe(self, audio: Path, language: str = "zh") -> str:
        audio_path = Path(audio) if isinstance(audio, str) else audio
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with open(audio_path, "rb") as audio_file:
            transcript = self._client.audio.transcriptions.create(
                model=self._model, file=audio_file, language=language
            )
        return transcript.text


class OpenAiTTS:
    """Text-to-Speech using OpenAI's TTS API"""

    def __init__(
        self, api_key: str, model: str = "gpt-4o-mini-tts", voice: str = "alloy"
    ):
        if not api_key:
            raise ValueError("API key cannot be empty")
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._voice = voice

    def speak(
        self,
        text: str,
        output: Path | None = None,
        voice: str = "alloy",
        speed: float = 1.0,
    ) -> bytes:
        if not text:
            raise ValueError("Text cannot be empty")
        if not (0.25 <= speed <= 4.0):
            raise ValueError("Speed must be between 0.25 and 4.0")

        response = self._client.audio.speech.create(
            model=self._model, voice=voice or self._voice, input=text, speed=speed
        )

        audio_data = response.read()

        if output:
            output_path = Path(output) if isinstance(output, str) else output
            output_path.write_bytes(audio_data)

        return audio_data


class OpenAiLLM:
    """Language Model using OpenAI's Chat API"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        if not api_key:
            raise ValueError("API key cannot be empty")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def chat(
        self, message: str, system_prompt: str = "use one sentence to summarize"
    ) -> str:
        if not message:
            raise ValueError("Message cannot be empty")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        response = self._client.chat.completions.create(
            model=self._model, messages=messages
        )
        if not response.choices[0].message.content:
            raise Exception("OpenAI Error")
        return response.choices[0].message.content


class VoicePipeline:
    """Pipeline: Audio → Text → LLM → Text → Audio

    This is a COMPOSITOR, not a new abstraction.
    It takes existing services and chains them together.
    """

    def __init__(self, stt: OpenAiSTT, llm: OpenAiLLM, tts: OpenAiTTS):
        """Initialize with ANY services that match the protocols.

        You can swap OpenAI for Google, Azure, local models - doesn't matter.
        Duck typing FTW.
        """
        self._stt = stt
        self._llm = llm
        self._tts = tts

    def process(
        self,
        audio_input: Path,
        output_path: Path | None = None,
        language: str = "zh",
    ) -> tuple[str, str, bytes]:
        """Process audio through the full pipeline.

        Args:
            audio_input: Path to input audio file
            output_path: Optional path to save output audio
            language: Optional language code for STT

        Returns:
            tuple of (transcribed_text, llm_response_text, audio_bytes)
        """

        transcribed = self._stt.transcribe(audio_input, language=language)

        response_text = self._llm.chat(transcribed)

        audio_bytes = self._tts.speak(response_text, output=output_path)

        return transcribed, response_text, audio_bytes


if __name__ == "__main__":
    load_dotenv("./.env")
    api_key = os.getenv("OPENAI_API_KEY", None)

    if not api_key:
        raise Exception("No OPENAI_API_KEY")

    stt = OpenAiSTT(api_key)
    tts = OpenAiTTS(api_key)
    llm = OpenAiLLM(api_key, model="gpt-4o-mini")

    pipeline = VoicePipeline(stt=stt, llm=llm, tts=tts)

    transcribed, response, audio = pipeline.process(
        audio_input=Path("./message.wav"),
        output_path=Path("./output.mp3"),
        language="zh",
    )

    print(f"User said: {transcribed}")
    print(f"AI replied: {response}")

    # text = stt.transcribe(Path("./message.wav"))
    # reply = llm.chat(text)
    # audio = tts.speak(reply, output=Path("./reply.mp3"))
