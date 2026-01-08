# Code by DHT@Matthew

import logging
import time

import torch
from transformers import (
    AutoModelForCausalLM,  # type: ignore[reportPrivateImportUsage]
    AutoTokenizer,  # type: ignore[reportPrivateImportUsage]
)

from helper.llm_backends.models import LLMBackend


class LocalBackend(LLMBackend):
    def __init__(
        self,
        system_prompt: str | None = None,
    ) -> None:
        self.logger = logging.getLogger("LocalLLM")
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

        self.system_prompt = system_prompt

        self.past_key_values = None
        self.cached_token_count = 0

    async def generate(
        self, messages: list[dict[str, str]], language: str = "zh", **kwargs
    ) -> str:
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
