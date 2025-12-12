# Code by DHT@Matthew

import logging
import time
import wave
from pathlib import Path

import langid
import torch
from faster_whisper import WhisperModel
from piper import PiperVoice
from transformers import (
    AutoModelForCausalLM,  # type: ignore[reportPrivateImportUsage]
    AutoTokenizer,  # type: ignore[reportPrivateImportUsage]
)

PROMPT = """
# AI 助理聊天機器人核心指令

你是一個 AI 助理聊天機器人。你來自 DHT Solution 的呼叫中心聊天機器人，你的名字是DD

### **通用行為準則**
1.  **首要任務**: 你的核心職責是完成「附加指令」和「今日特別任務」中定義的目標。請主動、自然地引導對話以達成這些目標。若無特定任務，則專注於高效解答用戶問題。
2.  **極度簡潔**: 為了保證語音對話的流暢性，每一句回覆都應簡潔明瞭，盡量不超過250字。
3.  **語言跟隨**: 嚴格使用用戶**上一句話**的語言進行回覆，除非用戶明確要求翻譯。
4.  **語音容錯**: 用戶的語音輸入可能不準確。請根據上下文盡力推斷其真實意圖。

### **應對策略**
*   **不確定時**: 禮貌地請求用戶澄清。例：「不好意思，我不太確定您的意思，可以請您換個方式說嗎？」
*   **有把握時**: 大膽預測並直接回答，同時可加上引導性確認。例：「聽起來您是想了解預約流程，是嗎？流程是這樣的...」
"""


class Speech2Text:
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
    ) -> None:
        """
        Initialize the model. This is slow, so do it once.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: "cuda" or "cpu" - don't use "auto", tell me what you want
            compute_type: "float16" (GPU) or "int8" (CPU)
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing Whisper model: {model_size} on {device}")
        start_time = time.time()

        self.model = WhisperModel(model_size, device="cuda", compute_type=compute_type)

        init_time = time.time() - start_time
        self.logger.info(f"Model loaded in {init_time:.2f}s")

    def transcribe(
        self,
        audio_path: str,
        beam_size: int = 5,
        vad_filter: bool = True,
        language: str | None = None,
    ) -> str:
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
            audio_path, beam_size=beam_size, vad_filter=vad_filter, language=language
        )

        text = "".join(segment.text for segment in segments)

        elapsed = time.time() - start_time
        self.logger.info(
            f"Transcription complete in {elapsed:.2f}s "
            f"(language: {info.language}, probability: {info.language_probability:.2f})"
        )

        return text

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


class LLM:
    def __init__(
        self,
        system_prompt: str | None = None,
        max_history_turns: int = 10,
    ) -> None:
        self.logger = logging.getLogger("LLM")
        start_time = time.time()

        self.logger.info("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen3-1.7B",
            revision="70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
        )

        self.logger.info("Loading model...")
        self.model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen3-1.7B",
            revision="70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
            device_map="cuda",
        )

        init_time = time.time() - start_time
        self.logger.info(f"LLM initialized in {init_time:.2f}s")

        self.max_history_turns = max_history_turns
        self.history = []
        if system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

        self.past_key_values = None
        self.cached_token_count = 0

    def generate_response(self, user_input: str):
        self.history.append({"role": "user", "content": "/no_think" + user_input})

        messages = self.history.copy()
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        model_inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        input_ids = model_inputs.input_ids

        if self.past_key_values is not None and len(self.history) > 2:
            new_tokens = input_ids[:, self.cached_token_count :]
            attention_mask = torch.ones(
                (1, self.cached_token_count + new_tokens.shape[1]),
                device=self.model.device,
            )
        else:
            new_tokens = input_ids
            attention_mask = model_inputs.attention_mask

        outputs = self.model.generate(
            new_tokens,
            max_new_tokens=128,
            past_key_values=self.past_key_values,
            attention_mask=attention_mask,
            use_cache=True,
            do_sample=False,
        )

        self.past_key_values = (
            outputs.past_key_values if hasattr(outputs, "past_key_values") else None
        )
        self.cached_token_count = input_ids.shape[1]

        response_ids = outputs[0][new_tokens.shape[1] :]
        response = self.tokenizer.decode(response_ids, skip_special_tokens=True)
        response = response.replace("<think>", "").replace("</think>", "").strip()

        self.history.append({"role": "assistant", "content": response})

        return response

    def clear_history(self) -> None:
        self.history = [self.history[0]]
        self.past_key_values = None
        self.cached_token_count = 0


class Text2Speech:
    """多語言 TTS，使用 langid 進行語言檢測"""

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
        self, text: str, output_path: str, lang: str | None = None
    ) -> tuple[str, float]:
        confidence = 1.0

        if lang is None:
            lang, confidence = self.detect_language(text)
        elif lang not in self.VOICE_MAP:
            raise ValueError(
                f"Unsupported Lang: {lang}, Supported: {list(self.VOICE_MAP.keys())}"
            )

        self.logger.info(f"Synthesizing in {lang} (confidence: {confidence:.2f})...")
        voice = self._get_voice(lang)
        with wave.open(output_path, "wb") as f:
            voice.synthesize_wav(text, f)

        return lang, confidence


if __name__ == "__main__":
    stt = Speech2Text()
    llm = LLM(system_prompt=PROMPT)
    tts = Text2Speech()

    print("Start testing...")
    st_time = time.time()
    incoming_voice = stt.transcribe("./audio.wav")
    print(f"Transcription time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    response = llm.generate_response(incoming_voice)
    print(response)
    print(f"LLM time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    tts.generate(response, "./output/response/demo1.wav")
    print(f"TTS time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    response = llm.generate_response(incoming_voice)
    print(response)
    print(f"LLM time: {time.time() - st_time:.2f}s")

    st_time = time.time()
    tts.generate(response, "./output/response/demo2.wav")
    print(f"TTS time: {time.time() - st_time:.2f}s")
