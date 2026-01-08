# Code by DHT@Matthew


class LLMBackend:
    def __init__(self) -> None:
        self.system_prompt: str | None = None

    async def generate(
        self, messages: list[dict[str, str]], language: str = "zh", **kwargs
    ) -> str:
        raise NotImplementedError
