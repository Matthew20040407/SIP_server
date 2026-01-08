# Code by DHT@Matthew

import logging

from helper.llm_backends.models import LLMBackend


class ConversationHistory:
    def __init__(self, system_prompt: str | None = None, max_turns: int = 10):
        self._messages = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})
        self._max_turns = max_turns

    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._trim_if_needed()

    def add_assistant_message(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict]:
        return self._messages.copy()

    def clear(self) -> None:
        system = (
            self._messages[0]
            if self._messages and self._messages[0]["role"] == "system"
            else None
        )
        self._messages = [system] if system else []

    def _trim_if_needed(self) -> None:
        system_msg = [m for m in self._messages if m["role"] == "system"]
        conversation = [m for m in self._messages if m["role"] != "system"]

        if len(conversation) > self._max_turns * 2:
            conversation = conversation[-(self._max_turns * 2) :]

        self._messages = system_msg + conversation


class LLM:
    def __init__(
        self,
        backend: LLMBackend,
        system_prompt: str | None = None,
        max_history_turns: int = 10,
    ):
        self.backend = backend
        self.history = ConversationHistory(
            system_prompt if system_prompt else backend.system_prompt, max_history_turns
        )
        self.logger = logging.getLogger("LLM")

    async def generate_response(
        self, user_input: str, language: str = "zh", **kwargs
    ) -> str:
        self.history.add_user_message(user_input)
        response = await self.backend.generate(
            self.history.get_messages(), language, **kwargs
        )

        self.history.add_assistant_message(response)
        return response

    def clear_history(self) -> None:
        self.history.clear()
